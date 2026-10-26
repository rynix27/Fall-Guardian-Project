"""
Fall Guardian - SQLite persistence layer.

The database file path is configurable:
  * environment variable FALL_GUARDIAN_DB, or
  * set_db_path() at runtime (used by the test suite to isolate test data).

All SQL uses parameterized queries. Every public function validates its inputs
and raises ValueError for invalid data; database failures are re-raised after
rollback so callers can distinguish them from successful writes.

Incident model: each row in `falls` is one incident. Its id is the incident id.
Incident status is one of OPEN, ACKNOWLEDGED, RESOLVED, CANCELLED.
"""

import logging
import os
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DEFAULT_DB_FILE = 'fall_guardian.db'
_db_path = os.environ.get('FALL_GUARDIAN_DB', DEFAULT_DB_FILE)

INCIDENT_STATUSES = ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'CANCELLED')
# Allowed status transitions. Anything else is rejected.
_ALLOWED_TRANSITIONS = {
    'OPEN': {'ACKNOWLEDGED', 'RESOLVED', 'CANCELLED'},
    'ACKNOWLEDGED': {'RESOLVED', 'CANCELLED'},
    'RESOLVED': set(),
    'CANCELLED': set(),
}


def set_db_path(path):
    """Point all database operations at a different SQLite file."""
    global _db_path
    _db_path = str(path)


def get_db_path():
    return _db_path


@contextmanager
def get_db_connection():
    """Open a connection; commit on success, roll back and re-raise on error."""
    conn = sqlite3.connect(_db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _ensure_column(conn, table, column, definition):
    """Add a column to an existing table if it is missing (simple migration)."""
    cols = [row[1] for row in conn.execute(f'PRAGMA table_info({table})')]
    if column not in cols:
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


def init_database():
    """Create tables and indices if they do not exist. Safe to call repeatedly."""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER,
                phone TEXT,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS falls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                severity INTEGER CHECK(severity >= 0 AND severity <= 10),
                location TEXT,
                response_time_ms INTEGER,
                notified INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'OPEN',
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS medications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                drug_name TEXT NOT NULL,
                dosage TEXT,
                frequency TEXT,
                fall_risk_multiplier REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fall_id INTEGER NOT NULL,
                alert_type TEXT NOT NULL,
                recipient TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'LOGGED',
                FOREIGN KEY(fall_id) REFERENCES falls(id) ON DELETE CASCADE
            )
        ''')
        # Migrations for databases created by earlier versions.
        _ensure_column(conn, 'falls', 'status', "TEXT NOT NULL DEFAULT 'OPEN'")
        c.execute('CREATE INDEX IF NOT EXISTS idx_falls_user_id ON falls(user_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_falls_timestamp ON falls(timestamp)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_alerts_fall_id ON alerts(fall_id)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_medications_user_id ON medications(user_id)')
    logger.info(f"Database initialized: {_db_path}")
    return True


def add_user(name, age, phone, email):
    """Add a user. Raises ValueError on invalid name or age."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("User name cannot be empty")
    if age is not None and (not _is_int(age) or age < 0 or age > 150):
        raise ValueError("Age must be an integer between 0 and 150")
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO users (name, age, phone, email) VALUES (?, ?, ?, ?)',
                  (name.strip(), age, phone, email))
        user_id = c.lastrowid
    logger.info(f"User added: ID={user_id}")
    return user_id


def _validate_fall_inputs(user_id, severity, response_time_ms):
    if not _is_int(user_id) or user_id <= 0:
        raise ValueError("Invalid user_id")
    if not _is_int(severity) or severity < 0 or severity > 10:
        raise ValueError("Severity must be an integer between 0 and 10")
    if response_time_ms is not None and (not _is_int(response_time_ms) or response_time_ms < 0):
        raise ValueError("Response time must be a non-negative integer")


def _require_user(c, user_id):
    c.execute('SELECT id FROM users WHERE id = ?', (user_id,))
    if c.fetchone() is None:
        raise ValueError(f"User {user_id} does not exist")


def log_fall(user_id, severity, location, response_time_ms):
    """
    Record a new incident (status OPEN). `notified` is 0 because this function
    does not contact anyone; notification is recorded separately via alerts.
    Returns the incident id.
    """
    _validate_fall_inputs(user_id, severity, response_time_ms)
    with get_db_connection() as conn:
        c = conn.cursor()
        _require_user(c, user_id)
        c.execute('''
            INSERT INTO falls (user_id, severity, location, response_time_ms, notified, status)
            VALUES (?, ?, ?, ?, 0, 'OPEN')
        ''', (user_id, severity, location, response_time_ms))
        fall_id = c.lastrowid
    logger.info(f"Incident logged: ID={fall_id}, User={user_id}, Severity={severity}")
    return fall_id


def find_open_duplicate(user_id, window_seconds=120):
    """
    Return the id of an OPEN incident for this user created within the last
    `window_seconds`, or None. Used to avoid creating duplicate incidents when
    the same fall is reported twice in quick succession.
    """
    if not _is_int(user_id) or user_id <= 0:
        raise ValueError("Invalid user_id")
    if not _is_int(window_seconds) or window_seconds < 0:
        raise ValueError("window_seconds must be a non-negative integer")
    with get_db_connection() as conn:
        row = conn.execute('''
            SELECT id FROM falls
            WHERE user_id = ? AND status = 'OPEN'
              AND (julianday('now') - julianday(timestamp)) * 86400.0 <= ?
            ORDER BY id DESC LIMIT 1
        ''', (user_id, window_seconds)).fetchone()
    return row['id'] if row else None


def get_incident(incident_id):
    """Return the incident as a dict, or None if it does not exist."""
    if not _is_int(incident_id) or incident_id <= 0:
        raise ValueError("Invalid incident_id")
    with get_db_connection() as conn:
        row = conn.execute('SELECT * FROM falls WHERE id = ?', (incident_id,)).fetchone()
    return dict(row) if row else None


def update_incident_status(incident_id, new_status):
    """
    Change an incident's status. Only transitions in _ALLOWED_TRANSITIONS are
    accepted; RESOLVED and CANCELLED are terminal.
    """
    if not _is_int(incident_id) or incident_id <= 0:
        raise ValueError("Invalid incident_id")
    if new_status not in INCIDENT_STATUSES:
        raise ValueError(f"Unknown status: {new_status}")
    with get_db_connection() as conn:
        row = conn.execute('SELECT status FROM falls WHERE id = ?', (incident_id,)).fetchone()
        if row is None:
            raise ValueError(f"Incident {incident_id} does not exist")
        current = row['status']
        if new_status == current:
            return False  # no-op
        if new_status not in _ALLOWED_TRANSITIONS[current]:
            raise ValueError(f"Illegal status transition {current} -> {new_status}")
        conn.execute('UPDATE falls SET status = ? WHERE id = ?', (new_status, incident_id))
    logger.info(f"Incident {incident_id}: {current} -> {new_status}")
    return True


def send_alert(fall_id, alert_type, recipient, status='LOGGED'):
    """
    Record an alert attempt. `status` must describe what really happened:
    LOGGED (recorded only), SIMULATED, SENT (provider confirmed), FAILED, TIMEOUT.
    """
    if not _is_int(fall_id) or fall_id <= 0:
        raise ValueError("Invalid fall_id")
    if not isinstance(alert_type, str) or not alert_type.strip():
        raise ValueError("Alert type cannot be empty")
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT id FROM falls WHERE id = ?', (fall_id,))
        if c.fetchone() is None:
            raise ValueError(f"Fall {fall_id} does not exist")
        c.execute('INSERT INTO alerts (fall_id, alert_type, recipient, status) VALUES (?, ?, ?, ?)',
                  (fall_id, alert_type, recipient, status))
        alert_id = c.lastrowid
    logger.info(f"Alert recorded: Fall={fall_id}, Type={alert_type}, Status={status}")
    return alert_id


def get_alerts(fall_id):
    if not _is_int(fall_id) or fall_id <= 0:
        raise ValueError("Invalid fall_id")
    with get_db_connection() as conn:
        rows = conn.execute('SELECT * FROM alerts WHERE fall_id = ? ORDER BY id', (fall_id,)).fetchall()
    return [dict(r) for r in rows]


def add_medication(user_id, drug_name, dosage, frequency, fall_risk):
    if not _is_int(user_id) or user_id <= 0:
        raise ValueError("Invalid user_id")
    if not isinstance(drug_name, str) or not drug_name.strip():
        raise ValueError("Drug name cannot be empty")
    if fall_risk is not None and (not isinstance(fall_risk, (int, float)) or fall_risk < 0):
        raise ValueError("Fall risk must be a non-negative number")
    with get_db_connection() as conn:
        c = conn.cursor()
        _require_user(c, user_id)
        c.execute('''
            INSERT INTO medications (user_id, drug_name, dosage, frequency, fall_risk_multiplier)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, drug_name, dosage, frequency, fall_risk))
    logger.info(f"Medication added: User={user_id}")


def get_user(user_id):
    """Return the user row as a tuple (id, name, age, phone, email, created_at) or None."""
    if not _is_int(user_id) or user_id <= 0:
        raise ValueError("Invalid user_id")
    with get_db_connection() as conn:
        row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    return tuple(row) if row else None


def get_user_falls(user_id):
    if not _is_int(user_id) or user_id <= 0:
        raise ValueError("Invalid user_id")
    with get_db_connection() as conn:
        rows = conn.execute('SELECT * FROM falls WHERE user_id = ? ORDER BY timestamp DESC, id DESC',
                            (user_id,)).fetchall()
    return [tuple(r) for r in rows]


def get_user_medications(user_id):
    if not _is_int(user_id) or user_id <= 0:
        raise ValueError("Invalid user_id")
    with get_db_connection() as conn:
        rows = conn.execute('SELECT * FROM medications WHERE user_id = ?', (user_id,)).fetchall()
    return [tuple(r) for r in rows]


def verify_database():
    """Check that all required tables exist. Raises if not."""
    with get_db_connection() as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    required = ['users', 'falls', 'medications', 'alerts']
    missing = [t for t in required if t not in tables]
    if missing:
        raise RuntimeError(f"Missing tables: {missing}")
    logger.info(f"Database verification PASSED: {len(tables)} tables found")
    return True
