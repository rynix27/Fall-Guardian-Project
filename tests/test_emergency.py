"""
Emergency workflow tests.

No real SMS, 911, smart-lock or dashboard call is possible from these tests:
DEMO mode never calls providers, and INTEGRATION-mode tests use fake providers
defined here. Assertions check recorded status values and database state,
not merely that a function returned.
"""
import threading
import time

import pytest

import database_setup as db
import emergency_response_service as ers
from emergency_response_service import EmergencyResponseService as Service

FALL = [15.2, 14.8, 16.1]     # detector -> FALL_DETECTED
NORMAL = [0.9, 0.1, 0.2]      # detector -> NORMAL_ACTIVITY


class RecordingProvider:
    """Fake provider that records calls and returns a configured outcome."""

    def __init__(self, outcome=None, exc=None):
        self.calls = []
        self.outcome = outcome or {'confirmed': True, 'detail': 'fake ok'}
        self.exc = exc

    def __call__(self, payload):
        self.calls.append(payload)
        if self.exc:
            raise self.exc
        return self.outcome


def all_confirmed():
    return {c: RecordingProvider() for c in ers.CHANNELS}


# ---------------------------------------------------------------- DEMO mode

def test_demo_fall_simulates_every_channel_and_calls_no_provider(user_id):
    providers = all_confirmed()
    svc = Service(mode='DEMO', contacts=['+1-555-0100'], providers=providers)
    r = svc.detect_fall(user_id, FALL, 95)
    svc.close()

    assert r['status'] == 'SIMULATED_ONLY'
    assert r['detection_status'] == 'FALL_DETECTED'
    assert set(r['channels']) == set(ers.CHANNELS)
    assert all(c['status'] == 'SIMULATED' for c in r['channels'].values())
    assert all(p.calls == [] for p in providers.values()), "DEMO must never call providers"


def test_demo_fall_records_incident_and_simulated_alerts(user_id):
    svc = Service(mode='DEMO', contacts=['+1-555-0100'])
    r = svc.detect_fall(user_id, FALL, 95)
    svc.close()
    incident = db.get_incident(r['incident_id'])
    assert incident['status'] == 'OPEN'
    alerts = db.get_alerts(r['incident_id'])
    assert len(alerts) == len(ers.CHANNELS)
    assert {a['status'] for a in alerts} == {'SIMULATED'}


# ------------------------------------------------------- detection gating

def test_normal_activity_takes_no_emergency_action(user_id):
    providers = all_confirmed()
    svc = Service(mode='INTEGRATION', contacts=['+1-555-0100'], providers=providers)
    r = svc.detect_fall(user_id, NORMAL, 72)
    svc.close()
    assert r['status'] == 'NO_FALL_DETECTED'
    assert r['incident_id'] is None
    assert db.get_user_falls(user_id) == []
    assert all(p.calls == [] for p in providers.values())


def test_invalid_user_id_is_rejected_without_writes(user_id):
    svc = Service(mode='DEMO')
    r = svc.detect_fall(-1, FALL, 95)
    svc.close()
    assert r['status'] == 'VALIDATION_FAILED'
    assert r['incident_id'] is None


def test_unknown_user_is_rejected(user_id):
    svc = Service(mode='DEMO')
    r = svc.detect_fall(987654, FALL, 95)
    svc.close()
    assert r['status'] == 'VALIDATION_FAILED'
    assert 'does not exist' in r['errors'][0]


def test_malformed_sensor_data_is_validation_failure(user_id):
    svc = Service(mode='DEMO')
    r = svc.detect_fall(user_id, None, 95)
    svc.close()
    assert r['status'] == 'VALIDATION_FAILED'
    assert db.get_user_falls(user_id) == []


# -------------------------------------------------- INTEGRATION honesty

def test_integration_without_providers_never_reports_success(user_id):
    svc = Service(mode='INTEGRATION', contacts=['+1-555-0100'], providers={})
    r = svc.detect_fall(user_id, FALL, 95)
    svc.close()
    statuses = {c['status'] for c in r['channels'].values()}
    assert 'SUCCESS' not in statuses
    assert statuses == {'NOT_CONFIGURED'}
    assert r['status'] == 'INCOMPLETE'
    assert {a['status'] for a in db.get_alerts(r['incident_id'])} == {'NOT_CONFIGURED'}


def test_integration_without_contacts_marks_family_not_configured(user_id):
    providers = all_confirmed()
    svc = Service(mode='INTEGRATION', contacts=[], providers=providers)
    r = svc.detect_fall(user_id, FALL, 95)
    svc.close()
    assert r['channels']['family_notification']['status'] == 'NOT_CONFIGURED'
    assert providers['family_notification'].calls == []


def test_contacts_are_read_from_environment(user_id, monkeypatch):
    monkeypatch.setenv('EMERGENCY_CONTACTS', '555-0100, 555-0101 ,')
    svc = Service(mode='INTEGRATION', providers=all_confirmed())
    assert svc.contacts == ['555-0100', '555-0101']
    svc.close()


def test_all_channels_confirmed_gives_complete(user_id):
    providers = all_confirmed()
    svc = Service(mode='INTEGRATION', contacts=['+1-555-0100'], providers=providers)
    r = svc.detect_fall(user_id, FALL, 95)
    svc.close()
    assert r['status'] == 'COMPLETE'
    assert all(c['status'] == 'SUCCESS' for c in r['channels'].values())
    assert {a['status'] for a in db.get_alerts(r['incident_id'])} == {'SENT'}
    # providers received the incident id
    assert all(p.calls[0]['incident_id'] == r['incident_id'] for p in providers.values())


def test_provider_exception_is_failed_not_success(user_id):
    providers = all_confirmed()
    providers['emergency_dispatch'] = RecordingProvider(exc=ConnectionError('network down'))
    svc = Service(mode='INTEGRATION', contacts=['+1-555-0100'], providers=providers)
    r = svc.detect_fall(user_id, FALL, 95)
    svc.close()
    assert r['channels']['emergency_dispatch']['status'] == 'FAILED'
    assert 'network down' in r['channels']['emergency_dispatch']['detail']
    assert r['status'] == 'PARTIAL_FAILURE'


def test_unconfirmed_provider_result_is_failed(user_id):
    providers = all_confirmed()
    providers['smart_lock'] = RecordingProvider(outcome={'confirmed': False, 'detail': 'lock offline'})
    svc = Service(mode='INTEGRATION', contacts=['+1-555-0100'], providers=providers)
    r = svc.detect_fall(user_id, FALL, 95)
    svc.close()
    assert r['channels']['smart_lock']['status'] == 'FAILED'
    assert 'lock offline' in r['channels']['smart_lock']['detail']


def test_truthy_but_unconfirmed_result_is_not_success(user_id):
    providers = all_confirmed()
    providers['dashboard'] = RecordingProvider(outcome={'confirmed': 'yes'})
    svc = Service(mode='INTEGRATION', contacts=['+1-555-0100'], providers=providers)
    r = svc.detect_fall(user_id, FALL, 95)
    svc.close()
    assert r['channels']['dashboard']['status'] == 'FAILED'


def test_provider_timeout_is_recorded_as_timeout(user_id):
    release = threading.Event()

    def slow(payload):
        release.wait(timeout=5)
        return {'confirmed': True}

    providers = all_confirmed()
    providers['emergency_dispatch'] = slow
    svc = Service(mode='INTEGRATION', timeout_ms=100, contacts=['+1-555-0100'], providers=providers)
    start = time.monotonic()
    r = svc.detect_fall(user_id, FALL, 95)
    elapsed = time.monotonic() - start
    release.set()
    svc.close()

    assert r['channels']['emergency_dispatch']['status'] == 'TIMEOUT'
    assert r['status'] == 'PARTIAL_FAILURE'
    assert elapsed < 2.0, "workflow must not wait for the hung provider"
    # the other channels still completed
    assert r['channels']['smart_lock']['status'] == 'SUCCESS'


def test_partial_failure_keeps_incident_and_successful_channels(user_id):
    providers = all_confirmed()
    providers['family_notification'] = RecordingProvider(exc=RuntimeError('SMS gateway 503'))
    svc = Service(mode='INTEGRATION', contacts=['+1-555-0100'], providers=providers)
    r = svc.detect_fall(user_id, FALL, 95)
    svc.close()

    assert r['status'] == 'PARTIAL_FAILURE'
    assert db.get_incident(r['incident_id'])['status'] == 'OPEN'
    by_channel = {a['alert_type']: a['status'] for a in db.get_alerts(r['incident_id'])}
    assert by_channel['family_notification'] == 'FAILED'
    assert by_channel['emergency_dispatch'] == 'SENT'


def test_database_failure_stops_workflow_before_any_provider(user_id, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError('disk I/O error')

    monkeypatch.setattr(db, 'log_fall', broken)
    providers = all_confirmed()
    svc = Service(mode='INTEGRATION', contacts=['+1-555-0100'], providers=providers)
    r = svc.detect_fall(user_id, FALL, 95)
    svc.close()
    assert r['status'] == 'FAILED'
    assert r['incident_id'] is None
    assert all(p.calls == [] for p in providers.values()), "no outward action without a logged incident"


# ---------------------------------------------------- duplicates & status

def test_second_event_within_window_is_suppressed(user_id):
    providers = all_confirmed()
    svc = Service(mode='INTEGRATION', contacts=['+1-555-0100'], providers=providers)
    first = svc.detect_fall(user_id, FALL, 95)
    second = svc.detect_fall(user_id, FALL, 95)
    svc.close()

    assert first['status'] == 'COMPLETE'
    assert second['status'] == 'DUPLICATE_SUPPRESSED'
    assert second['incident_id'] == first['incident_id']
    assert len(db.get_user_falls(user_id)) == 1
    assert all(len(p.calls) == 1 for p in providers.values()), "no second round of actions"


def test_incident_can_be_acknowledged_then_resolved(user_id):
    svc = Service(mode='DEMO')
    r = svc.detect_fall(user_id, FALL, 95)
    svc.close()
    iid = r['incident_id']
    db.update_incident_status(iid, 'ACKNOWLEDGED')
    db.update_incident_status(iid, 'RESOLVED')
    assert db.get_incident(iid)['status'] == 'RESOLVED'


def test_resolved_incident_allows_new_incident_for_same_user(user_id):
    svc = Service(mode='DEMO')
    first = svc.detect_fall(user_id, FALL, 95)
    db.update_incident_status(first['incident_id'], 'RESOLVED')
    second = svc.detect_fall(user_id, FALL, 95)
    svc.close()
    assert second['status'] == 'SIMULATED_ONLY'
    assert second['incident_id'] != first['incident_id']


def test_service_rejects_bad_configuration():
    with pytest.raises(ValueError):
        Service(mode='PRODUCTION')
    with pytest.raises(ValueError):
        Service(timeout_ms=0)
    with pytest.raises(ValueError):
        Service(providers={'pager_duty': RecordingProvider()})
