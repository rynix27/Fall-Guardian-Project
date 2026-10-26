import sqlite3

import pytest

import database_setup as db


def test_init_is_repeatable_and_creates_all_tables(temp_db):
    db.init_database()
    db.init_database()  # second call must not fail or duplicate tables
    assert db.verify_database() is True
    with sqlite3.connect(temp_db) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'users', 'falls', 'medications', 'alerts'} <= tables


def test_database_file_is_isolated_from_default(temp_db):
    assert db.get_db_path() == str(temp_db)
    assert str(temp_db) != db.DEFAULT_DB_FILE


def test_add_user_stores_and_returns_row(user_id):
    user = db.get_user(user_id)
    assert user is not None
    assert user[1] == 'Test Patient'
    assert user[2] == 75


@pytest.mark.parametrize('name', ['', '   ', None])
def test_add_user_rejects_empty_name(name):
    with pytest.raises(ValueError):
        db.add_user(name, 70, None, None)


@pytest.mark.parametrize('age', [-1, 151, 72.5, '72', True])
def test_add_user_rejects_invalid_age(age):
    with pytest.raises(ValueError):
        db.add_user('Valid Name', age, None, None)


def test_sql_metacharacters_are_stored_literally(user_id):
    evil = "Robert'); DROP TABLE users;--"
    uid = db.add_user(evil, 60, None, None)
    assert db.get_user(uid)[1] == evil
    assert db.get_user(user_id) is not None  # table still exists


def test_log_fall_creates_open_incident_not_marked_notified(user_id):
    fall_id = db.log_fall(user_id, 7, 'Kitchen', 120)
    incident = db.get_incident(fall_id)
    assert incident['status'] == 'OPEN'
    assert incident['notified'] == 0
    assert incident['severity'] == 7
    assert incident['location'] == 'Kitchen'


@pytest.mark.parametrize('user_id_arg, severity, rt', [
    (-1, 5, 100),          # invalid user id
    (True, 5, 100),        # bool is not an id
    (1, 11, 100),          # severity too high
    (1, -1, 100),          # severity negative
    (1, 5.5, 100),         # non-integer severity
    (1, 5, -10),           # negative response time
])
def test_log_fall_rejects_invalid_input(user_id_arg, severity, rt):
    with pytest.raises(ValueError):
        db.log_fall(user_id_arg, severity, 'Loc', rt)


def test_log_fall_rejects_unknown_user(temp_db):
    with pytest.raises(ValueError, match='does not exist'):
        db.log_fall(9999, 5, 'Loc', 100)


def test_get_incident_missing_returns_none():
    assert db.get_incident(424242) is None


@pytest.mark.parametrize('bad_id', [0, -3, '1', None])
def test_get_incident_rejects_invalid_id(bad_id):
    with pytest.raises(ValueError):
        db.get_incident(bad_id)


def test_legal_status_transitions_are_applied(user_id):
    fall_id = db.log_fall(user_id, 5, 'Hall', 50)
    assert db.update_incident_status(fall_id, 'ACKNOWLEDGED') is True
    assert db.get_incident(fall_id)['status'] == 'ACKNOWLEDGED'
    assert db.update_incident_status(fall_id, 'RESOLVED') is True
    assert db.get_incident(fall_id)['status'] == 'RESOLVED'


def test_same_status_update_is_noop(user_id):
    fall_id = db.log_fall(user_id, 5, 'Hall', 50)
    assert db.update_incident_status(fall_id, 'OPEN') is False


@pytest.mark.parametrize('setup, target', [
    (['RESOLVED'], 'OPEN'),          # terminal -> anything
    (['RESOLVED'], 'CANCELLED'),
    (['CANCELLED'], 'RESOLVED'),
    (['ACKNOWLEDGED'], 'OPEN'),      # cannot move backwards
])
def test_illegal_status_transitions_are_rejected(user_id, setup, target):
    fall_id = db.log_fall(user_id, 5, 'Hall', 50)
    for step in setup:
        db.update_incident_status(fall_id, step)
    before = db.get_incident(fall_id)['status']
    with pytest.raises(ValueError, match='Illegal'):
        db.update_incident_status(fall_id, target)
    assert db.get_incident(fall_id)['status'] == before


def test_unknown_status_rejected(user_id):
    fall_id = db.log_fall(user_id, 5, 'Hall', 50)
    with pytest.raises(ValueError, match='Unknown status'):
        db.update_incident_status(fall_id, 'DELETED')


def test_duplicate_open_incident_detected_within_window(user_id):
    fall_id = db.log_fall(user_id, 6, 'Bathroom', 80)
    assert db.find_open_duplicate(user_id, window_seconds=120) == fall_id


def test_old_incident_is_not_a_duplicate_outside_window(temp_db, user_id):
    fall_id = db.log_fall(user_id, 6, 'Bathroom', 80)
    # Backdate the incident by one hour so it falls outside a 120-second window.
    with sqlite3.connect(temp_db) as conn:
        conn.execute("UPDATE falls SET timestamp = datetime('now', '-1 hour') WHERE id = ?", (fall_id,))
    assert db.find_open_duplicate(user_id, window_seconds=120) is None


def test_resolved_incident_is_not_a_duplicate(user_id):
    fall_id = db.log_fall(user_id, 6, 'Bathroom', 80)
    db.update_incident_status(fall_id, 'RESOLVED')
    assert db.find_open_duplicate(user_id, window_seconds=120) is None


def test_alert_status_is_recorded_as_given(user_id):
    fall_id = db.log_fall(user_id, 4, 'Porch', 30)
    db.send_alert(fall_id, 'family_notification', '+1-555-0100', 'SIMULATED')
    db.send_alert(fall_id, 'emergency_dispatch', 'N/A', 'NOT_CONFIGURED')
    statuses = [a['status'] for a in db.get_alerts(fall_id)]
    assert statuses == ['SIMULATED', 'NOT_CONFIGURED']


def test_alert_for_missing_fall_is_rejected():
    with pytest.raises(ValueError):
        db.send_alert(777777, 'family_notification', 'x', 'SENT')


def test_medication_tracking(user_id):
    db.add_medication(user_id, 'Lisinopril', '10mg', 'Once daily', 1.8)
    meds = db.get_user_medications(user_id)
    assert len(meds) == 1
    assert meds[0][2] == 'Lisinopril'


def test_medication_rejects_unknown_user_and_bad_risk(user_id):
    with pytest.raises(ValueError):
        db.add_medication(8888, 'Aspirin', '81mg', 'Daily', 1.0)
    with pytest.raises(ValueError):
        db.add_medication(user_id, 'Aspirin', '81mg', 'Daily', -2)


def test_database_error_is_raised_not_swallowed(tmp_path, monkeypatch):
    # Point at a directory that does not exist: SQLite cannot open the file.
    db.set_db_path(tmp_path / 'missing_dir' / 'x.db')
    with pytest.raises(sqlite3.OperationalError):
        db.init_database()
