"""
End-to-end: video file -> OpenCV detection -> evidence window -> agent ->
human decision -> Lambda-style storage (local table) -> simulated workflow -> trace.

The vision pipeline is the real one. Only the human decision, the store and
the emergency channels are test doubles. Nothing is sent to anyone.
"""
import json
import os

import pytest

import database_setup as db
from agent.approval_agent import (ApprovalAgent, RecordingNotifier, ScriptedApproval,
                                  TraceLog, APPROVED, DENIED, TIMEOUT)
from aws.fall_event_handler import handler
from aws.local_table import LocalTable
from emergency_response_service import EmergencyResponseService
from vision.evidence import VideoEvidence
from vision.fall_vision import VisionFallDetector
from vision.synthetic_clips import make_clip


@pytest.fixture(scope='module')
def fall_clip(tmp_path_factory):
    return make_clip('fall', str(tmp_path_factory.mktemp('e2e') / 'fall.mp4'))


@pytest.fixture(scope='module')
def walk_clip(tmp_path_factory):
    return make_clip('walk', str(tmp_path_factory.mktemp('e2e_walk') / 'walk.mp4'))


def run_pipeline(clip, user_id, decision, tmp_path, table=None, store_raises=False):
    events, _ = VisionFallDetector().process_video(clip)
    table = table if table is not None else LocalTable()

    def store(payload):
        if store_raises:
            raise RuntimeError('dynamodb unavailable')
        return handler(payload, table=table)

    service = EmergencyResponseService(mode='DEMO')
    notifier = RecordingNotifier()
    trace_path = tmp_path / 'trace.jsonl'
    agent = ApprovalAgent(service, notifier, ScriptedApproval(decision),
                          trace=TraceLog(str(trace_path)), approval_timeout_s=1, store=store)
    results = []
    evidence = VideoEvidence(clip)
    for e in events:
        results.append(agent.handle_vision_event(user_id, e.to_dict(), severity=6, evidence=evidence))
    service.close()
    steps = [json.loads(l) for l in trace_path.read_text().splitlines()] if trace_path.exists() else []
    return {'events': events, 'results': results, 'table': table,
            'notifier': notifier, 'steps': steps}


def test_success_path_detects_examines_approves_stores_and_audits(user_id, fall_clip, tmp_path):
    out = run_pipeline(fall_clip, user_id, APPROVED, tmp_path)
    assert len(out['events']) == 1
    r = out['results'][0]
    assert r['status'] == 'WORKFLOW_RUN'
    assert r['workflow_status'] == 'SIMULATED_ONLY'
    assert r['store_status'] == 201
    assert len(out['table'].items) == 1
    steps = [s['step'] for s in out['steps']]
    assert steps == ['VISION_EVENT_RECEIVED', 'EVIDENCE_EXAMINED', 'APPROVAL_REQUESTED',
                     'DECISION', 'STORE_RESULT', 'WORKFLOW_RESULT']


def test_denied_path_stores_nothing_and_runs_no_workflow(user_id, fall_clip, tmp_path):
    out = run_pipeline(fall_clip, user_id, DENIED, tmp_path)
    assert out['results'][0]['status'] == 'NO_ACTION'
    assert out['table'].items == {}
    assert db.get_user_falls(user_id) == []


def test_timeout_path_dispatches_nothing_automatically(user_id, fall_clip, tmp_path):
    out = run_pipeline(fall_clip, user_id, TIMEOUT, tmp_path)
    assert out['results'][0]['status'] == 'NO_RESPONSE'
    assert out['results'][0]['action'] == 'none'
    assert out['table'].items == {}
    assert db.get_user_falls(user_id) == []


def test_storage_failure_is_reported_and_does_not_block_workflow(user_id, fall_clip, tmp_path):
    out = run_pipeline(fall_clip, user_id, APPROVED, tmp_path, store_raises=True)
    r = out['results'][0]
    assert r['store_status'].startswith('error')
    assert r['workflow_status'] == 'SIMULATED_ONLY'
    assert db.get_incident(r['incident_id']) is not None


def test_non_fall_clip_produces_no_candidate_and_no_request(user_id, walk_clip, tmp_path):
    out = run_pipeline(walk_clip, user_id, APPROVED, tmp_path)
    assert out['events'] == []
    assert out['results'] == []
    assert out['notifier'].sent == []


def test_repeated_delivery_of_same_approved_event_is_idempotent(user_id, fall_clip, tmp_path):
    table = LocalTable()
    run_pipeline(fall_clip, user_id, APPROVED, tmp_path, table=table)
    # Replay the stored payload: the same run id must not create a second incident.
    stored = list(table.items.values())[0]
    replay = handler({'user_id': stored['user_id'], 'event_type': 'vision_fall',
                      'timestamp': stored['timestamp'], 'decision': 'APPROVED',
                      'idempotency_key': stored['idempotency_key']}, table=table)
    assert replay['statusCode'] == 200
    assert len(table.items) == 1
