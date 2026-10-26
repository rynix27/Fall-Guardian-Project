"""
Approval ledger: one record per approval request, with explicit states.

States:  PENDING -> APPROVED | DENIED | EXPIRED
Rules:
  * A request is decided at most once. Repeating the same decision is an
    idempotent no-op (ALREADY_DECIDED). A different decision is rejected (CONFLICT).
  * A request past its expiry time cannot be approved (EXPIRED).
  * Unknown request ids and invalid decision values are rejected, never guessed.
  * Only APPROVED permits dispatch. Every other state dispatches nothing.

The ledger is in memory: it protects a single process. It is NOT a durable or
multi-instance control. Persisting decisions across restarts is listed as a
limitation in SECURITY_REVIEW.md.
"""
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

PENDING = 'PENDING'
APPROVED = 'APPROVED'
DENIED = 'DENIED'
EXPIRED = 'EXPIRED'
VALID_DECISIONS = (APPROVED, DENIED)

OUTCOME_RECORDED = 'RECORDED'
OUTCOME_ALREADY_DECIDED = 'ALREADY_DECIDED'
OUTCOME_CONFLICT = 'CONFLICT'
OUTCOME_EXPIRED = 'EXPIRED'
OUTCOME_UNKNOWN_REQUEST = 'UNKNOWN_REQUEST'
OUTCOME_INVALID_DECISION = 'INVALID_DECISION'


@dataclass
class ApprovalRecord:
    request_id: str
    expires_at: float
    state: str = PENDING
    operator_id: Optional[str] = None
    decided_at: Optional[float] = None


@dataclass
class DecisionResult:
    outcome: str
    state: str
    dispatch_allowed: bool
    detail: str = ''


class ApprovalLedger:
    def __init__(self, clock: Callable[[], float]):
        self._clock = clock
        self._records: Dict[str, ApprovalRecord] = {}

    def open_request(self, request_id: str, ttl_s: float) -> ApprovalRecord:
        if not isinstance(request_id, str) or not request_id:
            raise ValueError('request_id must be a non-empty string')
        if ttl_s <= 0:
            raise ValueError('ttl_s must be positive')
        if request_id in self._records:
            raise ValueError('request_id already exists')
        rec = ApprovalRecord(request_id=request_id, expires_at=self._clock() + ttl_s)
        self._records[request_id] = rec
        return rec

    def state(self, request_id: str) -> Optional[str]:
        rec = self._records.get(request_id)
        if rec is None:
            return None
        if rec.state == PENDING and self._clock() >= rec.expires_at:
            rec.state = EXPIRED
        return rec.state

    def expire(self, request_id: str) -> DecisionResult:
        """Mark a pending request expired (used when no answer arrives in time)."""
        rec = self._records.get(request_id)
        if rec is None:
            return DecisionResult(OUTCOME_UNKNOWN_REQUEST, '', False, 'no such request')
        if rec.state == PENDING:
            rec.state = EXPIRED
            rec.decided_at = self._clock()
            return DecisionResult(OUTCOME_EXPIRED, EXPIRED, False, 'no decision before timeout')
        return DecisionResult(OUTCOME_ALREADY_DECIDED if rec.state != EXPIRED else OUTCOME_EXPIRED,
                              rec.state, rec.state == APPROVED, 'request already decided')

    def decide(self, request_id: str, decision: str, operator_id: str) -> DecisionResult:
        if decision not in VALID_DECISIONS:
            return DecisionResult(OUTCOME_INVALID_DECISION, self.state(request_id) or '', False,
                                  'decision must be APPROVED or DENIED')
        if not isinstance(operator_id, str) or not operator_id.strip():
            return DecisionResult(OUTCOME_INVALID_DECISION, self.state(request_id) or '', False,
                                  'operator_id is required')
        rec = self._records.get(request_id)
        if rec is None:
            return DecisionResult(OUTCOME_UNKNOWN_REQUEST, '', False, 'no such request')
        state = self.state(request_id)
        if state == EXPIRED:
            return DecisionResult(OUTCOME_EXPIRED, EXPIRED, False, 'request expired before a decision')
        if state != PENDING:
            if state == decision:
                # Never dispatch again: the original decision already had its effect (or not).
                return DecisionResult(OUTCOME_ALREADY_DECIDED, state, False,
                                      'duplicate of an existing decision; no further action')
            return DecisionResult(OUTCOME_CONFLICT, state, False,
                                  f'request already {state}; conflicting decision rejected')
        rec.state = decision
        rec.operator_id = operator_id
        rec.decided_at = self._clock()
        return DecisionResult(OUTCOME_RECORDED, decision, decision == APPROVED, 'recorded')


# ---------------------------------------------------------------------------
# Durable ledger: the same rules, stored in SQLite so decisions survive restarts
# and are shared by every process that opens the same file.
#
# Each decision is a single conditional UPDATE (WHERE state = 'PENDING') inside
# BEGIN IMMEDIATE, so two writers cannot both record a decision. Times are
# wall-clock (time.time) because monotonic clocks do not survive restarts.
# ---------------------------------------------------------------------------
import sqlite3
import time as _time


class DurableApprovalLedger:
    """SQLite-backed ledger with the same outcomes as ApprovalLedger."""

    def __init__(self, path: str, clock: Callable[[], float] = _time.time):
        self._path = path
        self._clock = clock
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS approval_requests (
                request_id TEXT PRIMARY KEY,
                expires_at REAL NOT NULL,
                state TEXT NOT NULL,
                operator_id TEXT,
                decided_at REAL)""")

    def _conn(self):
        conn = sqlite3.connect(self._path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return _Closing(conn)

    def open_request(self, request_id: str, ttl_s: float) -> ApprovalRecord:
        if not isinstance(request_id, str) or not request_id:
            raise ValueError('request_id must be a non-empty string')
        if ttl_s <= 0:
            raise ValueError('ttl_s must be positive')
        expires = self._clock() + ttl_s
        with self._conn() as c:
            try:
                c.execute('INSERT INTO approval_requests (request_id, expires_at, state) VALUES (?, ?, ?)',
                          (request_id, expires, PENDING))
            except sqlite3.IntegrityError:
                raise ValueError('request_id already exists')
        return ApprovalRecord(request_id=request_id, expires_at=expires)

    def state(self, request_id: str) -> Optional[str]:
        with self._conn() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT state, expires_at FROM approval_requests WHERE request_id = ?',
                            (request_id,)).fetchone()
            if row is None:
                c.execute('COMMIT')
                return None
            if row['state'] == PENDING and self._clock() >= row['expires_at']:
                c.execute("UPDATE approval_requests SET state = ?, decided_at = ? "
                          "WHERE request_id = ? AND state = ?",
                          (EXPIRED, self._clock(), request_id, PENDING))
                c.execute('COMMIT')
                return EXPIRED
            c.execute('COMMIT')
            return row['state']

    def expire(self, request_id: str) -> DecisionResult:
        with self._conn() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT state FROM approval_requests WHERE request_id = ?',
                            (request_id,)).fetchone()
            if row is None:
                c.execute('COMMIT')
                return DecisionResult(OUTCOME_UNKNOWN_REQUEST, '', False, 'no such request')
            if row['state'] == PENDING:
                c.execute("UPDATE approval_requests SET state = ?, decided_at = ? "
                          "WHERE request_id = ? AND state = ?",
                          (EXPIRED, self._clock(), request_id, PENDING))
                c.execute('COMMIT')
                return DecisionResult(OUTCOME_EXPIRED, EXPIRED, False, 'no decision before timeout')
            c.execute('COMMIT')
            return DecisionResult(OUTCOME_ALREADY_DECIDED if row['state'] != EXPIRED else OUTCOME_EXPIRED,
                                  row['state'], row['state'] == APPROVED, 'request already decided')

    def decide(self, request_id: str, decision: str, operator_id: str) -> DecisionResult:
        if decision not in VALID_DECISIONS:
            return DecisionResult(OUTCOME_INVALID_DECISION, self.state(request_id) or '', False,
                                  'decision must be APPROVED or DENIED')
        if not isinstance(operator_id, str) or not operator_id.strip():
            return DecisionResult(OUTCOME_INVALID_DECISION, self.state(request_id) or '', False,
                                  'operator_id is required')
        with self._conn() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT state, expires_at FROM approval_requests WHERE request_id = ?',
                            (request_id,)).fetchone()
            if row is None:
                c.execute('COMMIT')
                return DecisionResult(OUTCOME_UNKNOWN_REQUEST, '', False, 'no such request')
            state = row['state']
            if state == PENDING and self._clock() >= row['expires_at']:
                c.execute("UPDATE approval_requests SET state = ?, decided_at = ? "
                          "WHERE request_id = ? AND state = ?",
                          (EXPIRED, self._clock(), request_id, PENDING))
                c.execute('COMMIT')
                return DecisionResult(OUTCOME_EXPIRED, EXPIRED, False, 'request expired before a decision')
            if state != PENDING:
                c.execute('COMMIT')
                if state == EXPIRED:
                    return DecisionResult(OUTCOME_EXPIRED, EXPIRED, False, 'request expired before a decision')
                if state == decision:
                    return DecisionResult(OUTCOME_ALREADY_DECIDED, state, False,
                                          'duplicate of an existing decision; no further action')
                return DecisionResult(OUTCOME_CONFLICT, state, False,
                                      f'request already {state}; conflicting decision rejected')
            cur = c.execute("UPDATE approval_requests SET state = ?, operator_id = ?, decided_at = ? "
                            "WHERE request_id = ? AND state = ?",
                            (decision, operator_id, self._clock(), request_id, PENDING))
            c.execute('COMMIT')
            if cur.rowcount != 1:
                # Lost a race that BEGIN IMMEDIATE should have prevented; report, never guess.
                return DecisionResult(OUTCOME_CONFLICT, '', False, 'concurrent decision detected')
            return DecisionResult(OUTCOME_RECORDED, decision, decision == APPROVED, 'recorded')


class _Closing:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self._conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            try:
                self._conn.execute('ROLLBACK')
            except sqlite3.Error:
                pass
        self._conn.close()
        return False   # never swallow errors
