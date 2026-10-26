"""
Agentic evidence step: the post-event window changes what the agent does.
Synthetic clips only. These tests check the decision logic, not real-world accuracy.
"""
import json
import os

import pytest

import database_setup as db
from agent.approval_agent import (ApprovalAgent, RecordingNotifier, ScriptedApproval,
                                  TraceLog, APPROVED, assess_evidence,
                                  EVIDENCE_RECOVERED, EVIDENCE_NO_RECOVERY, EVIDENCE_UNRESOLVED,
                                  EVIDENCE_INSUFFICIENT)
from emergency_response_service import EmergencyResponseService
from vision.evidence import VideoEvidence
from vision.fall_vision import FrameReading, STATE_UPRIGHT, STATE_OTHER, STATE_NO_PERSON
from vision.synthetic_clips import make_clip

EVENT_T = 7.2
EVENT = {'t_s': EVENT_T, 'rule': 'upright->lying within window, centroid dropped, lying held'}


@pytest.fixture(scope='module')
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp('evidence_clips')
    return {n: make_clip(n, os.path.join(d, f'{n}.mp4')) for n in ('fall', 'fall_recover')}


def _reading(t, state, box=(0, 0, 30, 90)):
    return FrameReading(frame_idx=int(t * 15), t_s=t, box=box,
                        aspect=3.0 if box else None, cy_norm=0.6 if box else None, state=state)


# ---- pure decision logic -------------------------------------------------

def test_no_person_visible_in_window_is_tracking_lost():
    r = [_reading(EVENT_T + i * 0.1, STATE_OTHER, box=None) for i in range(1, 30)]
    out = assess_evidence(r)
    assert out['label'] == EVIDENCE_UNRESOLVED
    assert out['severity_delta'] == 0


def test_empty_window_is_insufficient_not_tracking_loss():
    out = assess_evidence([])
    assert out['label'] == EVIDENCE_INSUFFICIENT
    assert out['severity_delta'] == 0


def test_few_visible_frames_is_insufficient_evidence_not_recovery():
    r = [_reading(EVENT_T + 0.1, STATE_OTHER), _reading(EVENT_T + 0.2, STATE_OTHER)]
    r += [_reading(EVENT_T + i * 0.1, STATE_OTHER, box=None) for i in range(3, 30)]
    out = assess_evidence(r)
    assert out['label'] == EVIDENCE_INSUFFICIENT
    assert out['severity_delta'] == 0


def test_upright_frame_in_window_is_recovered_with_no_severity_bump():
    r = [_reading(EVENT_T + i * 0.1, STATE_OTHER) for i in range(1, 20)]
    r.insert(10, _reading(EVENT_T + 1.5, STATE_UPRIGHT))
    out = assess_evidence(r)
    assert out['label'] == EVIDENCE_RECOVERED
    assert out['severity_delta'] == 0


def test_person_staying_down_is_no_recovery_with_severity_bump():
    r = [_reading(EVENT_T + i * 0.1, STATE_OTHER) for i in range(1, 40)]
    out = assess_evidence(r)
    assert out['label'] == EVIDENCE_NO_RECOVERY
    assert out['severity_delta'] == 2


def test_window_helper_returns_only_frames_inside_the_window(clips):
    ev = VideoEvidence(clips['fall'])
    w = ev.window_after(EVENT_T, 5.0)
    assert all(EVENT_T < r.t_s <= EVENT_T + 5.0 for r in w)
    assert len(w) > 0


# ---- agent behaviour with real clips -----------------------------------

def _agent(tmp_path=None):
    service = EmergencyResponseService(mode='DEMO')
    notifier = RecordingNotifier()
    trace = TraceLog(str(tmp_path / 'trace.jsonl') if tmp_path else None)
    agent = ApprovalAgent(service, notifier, ScriptedApproval(APPROVED),
                          trace=trace, approval_timeout_s=1)
    return agent, service, notifier


def test_staying_down_raises_severity_and_is_recorded(user_id, clips, tmp_path):
    agent, service, notifier = _agent(tmp_path)
    result = agent.handle_vision_event(user_id, EVENT, severity=5, evidence=VideoEvidence(clips['fall']))
    service.close()
    assert result['workflow_status'] == 'SIMULATED_ONLY'
    assert db.get_incident(result['incident_id'])['severity'] == 7
    assert notifier.sent[0]['event']['evidence'] == EVIDENCE_NO_RECOVERY
    steps = [json.loads(l)['step'] for l in (tmp_path / 'trace.jsonl').read_text().splitlines()]
    assert 'EVIDENCE_EXAMINED' in steps


def test_recovery_still_asks_a_human_and_keeps_severity(user_id, clips, tmp_path):
    agent, service, notifier = _agent(tmp_path)
    result = agent.handle_vision_event(user_id, EVENT, severity=5, evidence=VideoEvidence(clips['fall_recover']))
    service.close()
    assert notifier.sent, "a recovered person is still reported for human review"
    assert notifier.sent[0]['event']['evidence'] == EVIDENCE_RECOVERED
    assert db.get_incident(result['incident_id'])['severity'] == 5


def test_insufficient_evidence_does_not_claim_a_fall_was_confirmed(user_id):
    class NoVisibility:
        def window_after(self, t, s):
            return []
    agent, service, notifier = _agent()
    result = agent.handle_vision_event(user_id, EVENT, severity=5, evidence=NoVisibility())
    service.close()
    assert notifier.sent[0]['event']['evidence'] == EVIDENCE_INSUFFICIENT
    assert db.get_incident(result['incident_id'])['severity'] == 5


def test_without_evidence_behaviour_is_unchanged(user_id):
    agent, service, notifier = _agent()
    result = agent.handle_vision_event(user_id, EVENT, severity=5)
    service.close()
    assert result['workflow_status'] == 'SIMULATED_ONLY'
    assert 'evidence' not in notifier.sent[0]['event']


# ---- input validation before any action -------------------------------

@pytest.mark.parametrize('bad_event', [
    {'t_s': -1.0, 'rule': 'x'},
    {'t_s': float('nan'), 'rule': 'x'},
    {'t_s': True, 'rule': 'x'},
    {'t_s': 1.0, 'rule': ''},
    {'t_s': 1.0, 'rule': 42},
    'not a dict',
])
def test_invalid_event_is_rejected_before_any_request(user_id, bad_event):
    agent, service, notifier = _agent()
    result = agent.handle_vision_event(user_id, bad_event)
    service.close()
    assert result['status'] == 'REJECTED'
    assert notifier.sent == []
    assert db.get_user_falls(user_id) == []


@pytest.mark.parametrize('sev', [-1, 11, 5.5, '5', True])
def test_invalid_severity_is_rejected(user_id, sev):
    agent, service, notifier = _agent()
    result = agent.handle_vision_event(user_id, EVENT, severity=sev)
    service.close()
    assert result['status'] == 'REJECTED'
    assert notifier.sent == []
