"""
The nine test cases from the original custom runner, ported to pytest.
Names are kept so results can be compared with earlier reports.
"""
import pytest

import database_setup as db
from bee_detection.fall_detector import FallDetector
from emergency_response_service import EmergencyResponseService


def test_database_initialization(temp_db):
    db.init_database()
    assert db.verify_database() is True


def test_user_creation(temp_db):
    uid = db.add_user('Test User', 75, '555-0000', 'test@example.com')
    assert uid > 0
    user = db.get_user(uid)
    assert user is not None and user[1] == 'Test User' and user[2] == 75


def test_user_input_validation(temp_db):
    with pytest.raises(ValueError):
        db.add_user('', 75, '555-0000', 'test@example.com')
    with pytest.raises(ValueError):
        db.add_user('Test', 200, '555-0000', 'test@example.com')


def test_fall_logging(user_id):
    fall_id = db.log_fall(user_id, 8, 'Bathroom', 250)
    assert fall_id > 0
    falls = db.get_user_falls(user_id)
    assert len(falls) == 1 and falls[0][0] == fall_id


def test_fall_validation(user_id):
    with pytest.raises(ValueError):
        db.log_fall(-1, 5, 'Location', 100)
    with pytest.raises(ValueError):
        db.log_fall(user_id, 15, 'Location', 100)
    with pytest.raises(ValueError):
        db.log_fall(user_id, -1, 'Location', 100)


def test_medication_tracking(user_id):
    db.add_medication(user_id, 'Lisinopril', '10mg', 'Once daily', 1.8)
    meds = db.get_user_medications(user_id)
    assert len(meds) == 1 and meds[0][2] == 'Lisinopril'


def test_fall_detector():
    d = FallDetector()
    assert d.detect_fall([0.9, 0.1, 0.2], 72)['detection_status'] == 'NORMAL_ACTIVITY'
    assert d.detect_fall([15.2, 14.8, 16.1], 95)['detection_status'] == 'FALL_DETECTED'
    assert d.detect_fall(None, 72)['detection_status'] == 'INSUFFICIENT_DATA'


def test_emergency_response(user_id):
    svc = EmergencyResponseService(mode='DEMO', contacts=['+1-555-0100'])
    r = svc.detect_fall(user_id, [15.2, 14.8, 16.1], 95)
    svc.close()
    assert r['status'] == 'SIMULATED_ONLY'
    assert db.get_incident(r['incident_id']) is not None


def test_alert_system(user_id):
    fall_id = db.log_fall(user_id, 6, 'Hall', 90)
    db.send_alert(fall_id, 'EMERGENCY', '555-0100', 'LOGGED')
    alerts = db.get_alerts(fall_id)
    assert len(alerts) == 1 and alerts[0]['alert_type'] == 'EMERGENCY'
