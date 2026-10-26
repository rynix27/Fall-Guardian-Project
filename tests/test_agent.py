"""
Approval agent tests. Assertions check the database and trace, not just return values.
"""
import json

import pytest

import database_setup as db
from agent.approval_agent import (ApprovalAgent, RecordingNotifier, ScriptedApproval,
                                  TraceLog, APPROVED, DENIED, TIMEOUT)
from emergency_response_service import EmergencyResponseService

EVENT = {'t_s': 7.2, 'rule': 'upright->lying', 'aspect_before': 2.9, 'aspect_after': 0.3}


def make_agent(decision, tmp_path=None):
    service = EmergencyResponseService(mode='DEMO')
    trace_path = str(tmp_path / 'trace.jsonl') if tmp_path else None
    notifier = RecordingNotifier()
    agent = ApprovalAgent(service, notifier, ScriptedApproval(decision),
                          trace=TraceLog(trace_path), approval_timeout_s=1)
    return agent, service, notifier


def test_approved_event_runs_workflow_and_records_incident(user_id, tmp_path):
    agent, service, notifier = make_agent(APPROVED, tmp_path)
    result = agent.handle_vision_event(user_id, EVENT)
    service.close()

    assert result['status'] == 'WORKFLOW_RUN'
    assert result['workflow_status'] == 'SIMULATED_ONLY'
    incident = db.get_incident(result['incident_id'])
    assert incident is not None and incident['status'] == 'OPEN'
    assert incident['user_id'] == user_id
    assert len(notifier.sent) == 1


def test_trace_records_every_step_in_order(user_id, tmp_path):
    agent, service, _ = make_agent(APPROVED, tmp_path)
    result = agent.handle_vision_event(user_id, EVENT)
    service.close()
    steps = [json.loads(l)['step'] for l in (tmp_path / 'trace.jsonl').read_text().splitlines()]
    assert steps == ['VISION_EVENT_RECEIVED', 'APPROVAL_REQUESTED', 'DECISION', 'WORKFLOW_RESULT']
    assert all(json.loads(l)['run_id'] == result['run_id']
               for l in (tmp_path / 'trace.jsonl').read_text().splitlines())


def test_denied_event_does_not_run_workflow(user_id):
    agent, service, _ = make_agent(DENIED)
    result = agent.handle_vision_event(user_id, EVENT)
    service.close()
    assert result['status'] == 'NO_ACTION'
    assert db.get_user_falls(user_id) == []


def test_timeout_does_not_dispatch_automatically(user_id):
    agent, service, _ = make_agent(TIMEOUT)
    result = agent.handle_vision_event(user_id, EVENT)
    service.close()
    assert result['status'] == 'NO_RESPONSE'
    assert result['action'] == 'none'
    assert db.get_user_falls(user_id) == []


def test_event_missing_required_fields_is_rejected(user_id):
    agent, service, _ = make_agent(APPROVED)
    result = agent.handle_vision_event(user_id, {'t_s': 1.0})
    service.close()
    assert result['status'] == 'REJECTED'
    assert db.get_user_falls(user_id) == []


def test_unknown_user_is_not_turned_into_incident(user_id):
    agent, service, _ = make_agent(APPROVED)
    result = agent.handle_vision_event(987654, EVENT)
    service.close()
    assert result['status'] == 'WORKFLOW_RUN'
    assert result['workflow_status'] == 'VALIDATION_FAILED'
    assert result['incident_id'] is None


def test_second_approved_event_is_suppressed_as_duplicate(user_id):
    agent, service, _ = make_agent(APPROVED)
    first = agent.handle_vision_event(user_id, EVENT)
    second = agent.handle_vision_event(user_id, EVENT)
    service.close()
    assert first['workflow_status'] == 'SIMULATED_ONLY'
    assert second['workflow_status'] == 'DUPLICATE_SUPPRESSED'
    assert len(db.get_user_falls(user_id)) == 1


def test_approved_event_is_stored_via_store_callable(user_id):
    from aws.fall_event_handler import handler
    from aws.local_table import LocalTable
    table = LocalTable()
    service = EmergencyResponseService(mode='DEMO')
    agent = ApprovalAgent(service, RecordingNotifier(), ScriptedApproval(APPROVED),
                          approval_timeout_s=1,
                          store=lambda payload: handler(payload, table=table))
    result = agent.handle_vision_event(user_id, EVENT)
    service.close()
    assert result['store_status'] == 201
    assert len(table.items) == 1
    assert list(table.items.values())[0]['decision'] == 'APPROVED'


def test_store_failure_does_not_block_workflow(user_id):
    service = EmergencyResponseService(mode='DEMO')

    def broken_store(payload):
        raise RuntimeError('dynamodb unavailable')

    agent = ApprovalAgent(service, RecordingNotifier(), ScriptedApproval(APPROVED),
                          approval_timeout_s=1, store=broken_store)
    result = agent.handle_vision_event(user_id, EVENT)
    service.close()
    assert result['store_status'].startswith('error')
    assert result['workflow_status'] == 'SIMULATED_ONLY'
    assert db.get_incident(result['incident_id']) is not None


def test_store_is_not_called_unless_approved(user_id):
    service = EmergencyResponseService(mode='DEMO')
    calls = []
    agent = ApprovalAgent(service, RecordingNotifier(), ScriptedApproval(DENIED),
                          approval_timeout_s=1, store=lambda p: calls.append(p) or {'statusCode': 201})
    agent.handle_vision_event(user_id, EVENT)
    service.close()
    assert calls == []


def test_agent_store_payload_has_idempotency_key_matching_run(user_id):
    from aws.fall_event_handler import handler
    from aws.local_table import LocalTable
    table = LocalTable()
    service = EmergencyResponseService(mode='DEMO')
    agent = ApprovalAgent(service, RecordingNotifier(), ScriptedApproval(APPROVED),
                          approval_timeout_s=1,
                          store=lambda payload: handler(payload, table=table))
    result = agent.handle_vision_event(user_id, EVENT)
    service.close()
    assert result['store_status'] == 201
    item = list(table.items.values())[0]
    assert item['idempotency_key'] == result['run_id']


def test_approval_arriving_after_expiry_is_not_dispatched(user_id):
    from agent.approval_ledger import ApprovalLedger
    clock = {'t': 1000.0}

    class LateApproval:
        operator_id = 'late-operator'
        def wait_for_decision(self, timeout_s):
            clock['t'] += timeout_s + 5   # the answer arrives after the deadline
            return APPROVED

    service = EmergencyResponseService(mode='DEMO')
    agent = ApprovalAgent(service, RecordingNotifier(), LateApproval(), approval_timeout_s=10,
                          ledger=ApprovalLedger(lambda: clock['t']))
    result = agent.handle_vision_event(user_id, EVENT, severity=5)
    service.close()
    assert result['status'] == 'NO_ACTION'
    assert result['ledger_outcome'] == 'EXPIRED'
    assert db.get_user_falls(user_id) == []


def test_decision_trace_records_operator_and_ledger_outcome(user_id, tmp_path):
    agent, service, _ = make_agent(APPROVED, tmp_path)
    agent.approval.operator_id = 'op-trace-test'
    agent.handle_vision_event(user_id, EVENT)
    service.close()
    decisions = [json.loads(l) for l in (tmp_path / 'trace.jsonl').read_text().splitlines()
                 if json.loads(l)['step'] == 'DECISION']
    assert decisions[0]['ledger_outcome'] == 'RECORDED'
    assert decisions[0]['operator_id'] == 'op-trace-test'
