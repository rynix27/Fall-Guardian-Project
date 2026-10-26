"""
Shared pytest fixtures.

Every test gets its own temporary SQLite file. The project's real
fall_guardian.db is never opened by the test suite.
"""
import pytest

import database_setup as db


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / 'test_fall_guardian.db'
    monkeypatch.delenv('EMERGENCY_CONTACTS', raising=False)
    db.set_db_path(path)
    db.init_database()
    yield path
    db.set_db_path(db.DEFAULT_DB_FILE)


@pytest.fixture
def user_id():
    return db.add_user('Test Patient', 75, '+1-555-0000', 'patient@example.test')
