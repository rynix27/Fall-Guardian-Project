"""
Agentic perception -> decision -> action loop with a human in the loop.

  vision event  ->  agent requests caregiver approval  ->  decision
      APPROVED   -> emergency workflow runs (simulated in DEMO mode)
      DENIED     -> no action, logged
      TIMEOUT    -> NO automatic dispatch; logged for manual follow-up

The vision output changes the agent's next action (the approval request), and
the approval decision changes the next tool call (the emergency workflow). Every
step is written to a JSON-lines trace so the sequence can be inspected.

The agent never contacts emergency services on its own. Its only automatic
actions are writing the trace and asking a human.
"""
import json
import threading
import time
import uuid
from datetime import datetime, timezone

from agent.approval_ledger import ApprovalLedger
from typing import Callable, Dict, Optional

APPROVED = 'APPROVED'
DENIED = 'DENIED'
TIMEOUT = 'TIMEOUT'

REQUIRED_EVENT_FIELDS = ('t_s', 'rule')

EVIDENCE_WINDOW_S = 5.0
MIN_VALID_FRAMES = 5           # fewer valid frames than this = unresolved
NO_RECOVERY_SEVERITY_BUMP = 2  # applied when the person stays down through the window

EVIDENCE_RECOVERED = 'RECOVERED_WITHIN_WINDOW'
EVIDENCE_NO_RECOVERY = 'NO_RECOVERY_OBSERVED'
EVIDENCE_UNRESOLVED = 'UNRESOLVED_TRACKING_LOST'
EVIDENCE_INSUFFICIENT = 'INSUFFICIENT_EVIDENCE'


def assess_evidence(readings) -> Dict:
    """
    Classify the post-event window. Deterministic; no model involved.

    - No readings at all (window not observed, e.g. the video ended)  -> INSUFFICIENT_EVIDENCE
    - Readings, but no visible person in any of them (tracking lost)  -> UNRESOLVED_TRACKING_LOST
    - Some visible frames, but fewer than MIN_VALID_FRAMES            -> INSUFFICIENT_EVIDENCE
    - Upright posture seen again in the window                        -> RECOVERED_WITHIN_WINDOW
    - Otherwise the person stayed low through the window               -> NO_RECOVERY_OBSERVED

    Missing frames are never read as proof that the person stayed down or recovered.
    """
    from vision.fall_vision import STATE_UPRIGHT
    readings = list(readings)
    valid = [r for r in readings if r.box is not None]
    base = {'valid_frames': len(valid), 'window_frames': len(readings)}
    if not readings:
        return {'label': EVIDENCE_INSUFFICIENT, 'severity_delta': 0, **base,
                'note': 'The post-event window was not observed (no frames available).'}
    if not valid:
        return {'label': EVIDENCE_UNRESOLVED, 'severity_delta': 0, **base,
                'note': 'No person visible in the window; tracking lost. Recovery cannot be assessed.'}
    if len(valid) < MIN_VALID_FRAMES:
        return {'label': EVIDENCE_INSUFFICIENT, 'severity_delta': 0, **base,
                'note': 'Too few frames with a visible person to assess recovery.'}
    if any(r.state == STATE_UPRIGHT for r in valid):
        return {'label': EVIDENCE_RECOVERED, 'severity_delta': 0, **base,
                'note': 'Person appears upright again within the window. Still requires human review.'}
    return {'label': EVIDENCE_NO_RECOVERY, 'severity_delta': NO_RECOVERY_SEVERITY_BUMP, **base,
            'note': 'Person remained lying or low through the window (post-event inactivity).'}


def _validate_event(event):
    """Return a list of problems. Empty list means the event is acceptable."""
    problems = []
    if not isinstance(event, dict):
        return ['event must be an object']
    missing = [f for f in REQUIRED_EVENT_FIELDS if f not in event]
    if missing:
        return [f'missing fields {missing}']
    t = event['t_s']
    if isinstance(t, bool) or not isinstance(t, (int, float)) or t != t or t < 0 or t == float('inf'):
        problems.append('t_s must be a finite non-negative number')
    if not isinstance(event['rule'], str) or not event['rule'].strip():
        problems.append('rule must be a non-empty string')
    return problems


class TraceLog:
    def __init__(self, path: Optional[str] = None):
        self.path = path
        self.entries = []

    def record(self, run_id: str, step: str, **data):
        entry = {'run_id': run_id, 'step': step,
                 'timestamp': datetime.now(timezone.utc).isoformat(), **data}
        self.entries.append(entry)
        if self.path:
            with open(self.path, 'a') as f:
                f.write(json.dumps(entry, default=str) + "\n")
        return entry


class RecordingNotifier:
    """Test double: records approval requests instead of sending anything."""
    def __init__(self):
        self.sent = []

    def request_approval(self, user_id, event, run_id):
        self.sent.append({'user_id': user_id, 'run_id': run_id, 'event': event})


class ConsoleNotifier:
    """Prints the request. Nothing is sent to a real caregiver."""
    def request_approval(self, user_id, event, run_id):
        print(f"[SIMULATED CAREGIVER REQUEST] run={run_id} user={user_id} "
              f"possible fall at t={event.get('t_s')}s - approve? (yes/no)")


class ScriptedApproval:
    """Test double / simulation: returns a fixed decision (or TIMEOUT). Not a real operator."""
    def __init__(self, decision: str, operator_id: str = 'simulated-operator'):
        self.decision = decision
        self.operator_id = operator_id

    def wait_for_decision(self, timeout_s: float) -> str:
        return self.decision


class ConsoleApproval:
    """Asks a person at the terminal. Returns TIMEOUT if no answer in time."""
    def __init__(self, input_fn: Callable[[str], str] = input, operator_id: str = 'console-operator'):
        self.input_fn = input_fn
        self.operator_id = operator_id

    def wait_for_decision(self, timeout_s: float) -> str:
        result = {}

        def ask():
            try:
                result['answer'] = self.input_fn("Approve emergency workflow? [yes/no]: ")
            except EOFError:
                result['answer'] = ''

        t = threading.Thread(target=ask, daemon=True)
        t.start()
        t.join(timeout_s)
        if t.is_alive():
            return TIMEOUT
        return APPROVED if result.get('answer', '').strip().lower() in ('y', 'yes') else DENIED


class ApprovalAgent:
    def __init__(self, service, notifier, approval, trace: Optional[TraceLog] = None,
                 approval_timeout_s: float = 60.0,
                 store: Optional[Callable[[Dict], Dict]] = None,
                 ledger=None, clock: Optional[Callable[[], float]] = None):
        self.service = service
        self.notifier = notifier
        self.approval = approval
        self.trace = trace or TraceLog()
        self.approval_timeout_s = approval_timeout_s
        # Optional: records an APPROVED event, e.g. the AWS Lambda handler.
        # Called only after human approval. Its failure does not block the workflow.
        self.store = store
        self.ledger = ledger or ApprovalLedger(clock or time.monotonic)

    def handle_vision_event(self, user_id: int, event: Dict, severity: int = 5,
                            location: str = 'Camera zone', evidence=None) -> Dict:
        run_id = uuid.uuid4().hex[:12]
        self.trace.record(run_id, 'VISION_EVENT_RECEIVED', user_id=user_id,
                          event={k: event.get(k) for k in ('t_s', 'rule')} if isinstance(event, dict) else None)

        problems = _validate_event(event)
        if problems:
            self.trace.record(run_id, 'REJECTED', reason=problems)
            return {'run_id': run_id, 'status': 'REJECTED', 'action': 'none', 'problems': problems}
        if not isinstance(severity, int) or isinstance(severity, bool) or not 0 <= severity <= 10:
            self.trace.record(run_id, 'REJECTED', reason='severity must be an integer 0-10')
            return {'run_id': run_id, 'status': 'REJECTED', 'action': 'none',
                    'problems': ['severity must be an integer 0-10']}

        # Additional analysis: examine the window after the candidate event.
        evidence_result = None
        ev_label = None
        if evidence is not None:
            readings = evidence.window_after(float(event['t_s']), EVIDENCE_WINDOW_S)
            evidence_result = assess_evidence(readings)
            self.trace.record(run_id, 'EVIDENCE_EXAMINED', window_s=EVIDENCE_WINDOW_S,
                              **{k: v for k, v in evidence_result.items()})
            severity = min(10, severity + evidence_result['severity_delta'])
            ev_label = evidence_result['label']
            event = {**event, 'evidence': evidence_result['label']}

        self.notifier.request_approval(user_id, event, run_id)
        self.trace.record(run_id, 'APPROVAL_REQUESTED', timeout_s=self.approval_timeout_s,
                          evidence=evidence_result['label'] if evidence_result else None,
                          severity=severity)

        self.ledger.open_request(run_id, ttl_s=self.approval_timeout_s)
        decision = self.approval.wait_for_decision(self.approval_timeout_s)
        operator_id = getattr(self.approval, 'operator_id', 'unknown-operator')
        if decision == TIMEOUT:
            ledger_result = self.ledger.expire(run_id)
        else:
            ledger_result = self.ledger.decide(run_id, decision, operator_id)
        self.trace.record(run_id, 'DECISION', decision=decision,
                          ledger_outcome=ledger_result.outcome, ledger_state=ledger_result.state,
                          operator_id=operator_id if ledger_result.outcome == 'RECORDED' else None)

        if ledger_result.dispatch_allowed:
            decision = APPROVED
        elif decision == APPROVED:
            # The approval source said yes, but the ledger refused (e.g. expired). Nothing runs.
            self.trace.record(run_id, 'NO_ACTION', reason=f'ledger refused: {ledger_result.outcome}')
            return {'run_id': run_id, 'status': 'NO_ACTION', 'action': 'none',
                    'evidence': ev_label, 'ledger_outcome': ledger_result.outcome}

        if decision == APPROVED:
            store_status = None
            if self.store is not None:
                # Field set must match contracts/incident_contract.py (APPROVED_FIELDS).
                # The run id travels as idempotency_key; retries reuse it.
                payload = {'schema_version': '1.0', 'user_id': str(user_id), 'event_type': 'vision_fall',
                           'timestamp': datetime.now(timezone.utc).isoformat(),
                           'decision': APPROVED, 'idempotency_key': run_id}
                try:
                    stored = self.store(payload)
                    store_status = stored.get('statusCode')
                except Exception as e:
                    store_status = f"error: {type(e).__name__}"
                self.trace.record(run_id, 'STORE_RESULT', status=store_status)

            result = self.service.confirm_fall_event(
                user_id, severity, location, source='vision_human_approved')
            self.trace.record(run_id, 'WORKFLOW_RESULT', status=result['status'],
                              incident_id=result['incident_id'],
                              channels={k: v['status'] for k, v in result['channels'].items()})
            return {'run_id': run_id, 'status': 'WORKFLOW_RUN', 'action': 'emergency_workflow', 'evidence': ev_label, 'ledger_outcome': ledger_result.outcome,
                    'workflow_status': result['status'], 'incident_id': result['incident_id'],
                    'store_status': store_status}

        if decision == DENIED:
            self.trace.record(run_id, 'NO_ACTION', reason='caregiver denied')
            return {'run_id': run_id, 'status': 'NO_ACTION', 'action': 'none', 'evidence': ev_label, 'ledger_outcome': ledger_result.outcome}

        self.trace.record(run_id, 'NO_RESPONSE', reason='no decision before timeout',
                          action='no automatic dispatch; manual follow-up required')
        return {'run_id': run_id, 'status': 'NO_RESPONSE', 'action': 'none', 'evidence': ev_label, 'ledger_outcome': ledger_result.outcome}
