"""
Durable approval ledger: decisions survive restarts and are safe under concurrency.
All files live in pytest's temporary directory.
"""
import sqlite3
import threading

import pytest

from agent.approval_ledger import (DurableApprovalLedger, APPROVED, DENIED, EXPIRED, PENDING,
                                   OUTCOME_RECORDED, OUTCOME_ALREADY_DECIDED, OUTCOME_CONFLICT,
                                   OUTCOME_EXPIRED, OUTCOME_UNKNOWN_REQUEST, OUTCOME_INVALID_DECISION)


class FakeClock:
    def __init__(self, t=1_700_000_000.0):
        self.t = t
    def __call__(self):
        return self.t


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / 'approvals.db')


def test_decision_survives_a_restart(db_path):
    clock = FakeClock()
    first = DurableApprovalLedger(db_path, clock)
    first.open_request('req-restart-1', ttl_s=600)
    assert first.decide('req-restart-1', APPROVED, 'op-1').outcome == OUTCOME_RECORDED
    del first                                             # "process exits"
    second = DurableApprovalLedger(db_path, clock)        # "process restarts"
    assert second.state('req-restart-1') == APPROVED
    r = second.decide('req-restart-1', APPROVED, 'op-1')
    assert r.outcome == OUTCOME_ALREADY_DECIDED and r.dispatch_allowed is False


def test_conflicting_decision_after_restart_is_rejected(db_path):
    clock = FakeClock()
    DurableApprovalLedger(db_path, clock).open_request('req-restart-2', ttl_s=600)
    DurableApprovalLedger(db_path, clock).decide('req-restart-2', DENIED, 'op-1')
    r = DurableApprovalLedger(db_path, clock).decide('req-restart-2', APPROVED, 'op-2')
    assert r.outcome == OUTCOME_CONFLICT and r.dispatch_allowed is False
    assert DurableApprovalLedger(db_path, clock).state('req-restart-2') == DENIED


def test_expiry_is_recorded_and_survives_restart(db_path):
    clock = FakeClock()
    DurableApprovalLedger(db_path, clock).open_request('req-exp-1', ttl_s=60)
    clock.t += 61
    r = DurableApprovalLedger(db_path, clock).decide('req-exp-1', APPROVED, 'op-1')
    assert r.outcome == OUTCOME_EXPIRED and not r.dispatch_allowed
    assert DurableApprovalLedger(db_path, clock).state('req-exp-1') == EXPIRED


ROUNDS = 30
CONTENDERS = 12


def _race_once(db_path, clock, request_id):
    DurableApprovalLedger(db_path, clock).open_request(request_id, ttl_s=600)
    outcomes, errors = [], []
    lock = threading.Lock()
    barrier = threading.Barrier(CONTENDERS)

    def contender(i):
        try:
            ledger = DurableApprovalLedger(db_path, clock)   # each thread has its own connection
            decision = APPROVED if i % 2 == 0 else DENIED
            barrier.wait()
            r = ledger.decide(request_id, decision, f'op-{i}')
            with lock:
                outcomes.append(r)
        except Exception as e:          # a database error is a failure, not a silent drop
            with lock:
                errors.append(repr(e))

    threads = [threading.Thread(target=contender, args=(i,)) for i in range(CONTENDERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return outcomes, errors


def test_concurrent_decisions_record_exactly_one_outcome(db_path):
    clock = FakeClock()
    for n in range(ROUNDS):
        rid = f'req-race-{n:03d}'
        outcomes, errors = _race_once(db_path, clock, rid)
        assert errors == [], f'round {n}: contenders raised: {errors}'
        assert len(outcomes) == CONTENDERS, f'round {n}: only {len(outcomes)} reported back'
        recorded = [o for o in outcomes if o.outcome == OUTCOME_RECORDED]
        assert len(recorded) == 1, f'round {n}: {[o.outcome for o in outcomes]}'
        final = DurableApprovalLedger(db_path, clock).state(rid)
        assert final == recorded[0].state
        dispatching = [o for o in outcomes if o.dispatch_allowed]
        assert len(dispatching) == (1 if final == APPROVED else 0), f'round {n}: dispatch mismatch'


def test_unknown_request_and_invalid_input(db_path):
    ledger = DurableApprovalLedger(db_path, FakeClock())
    assert ledger.decide('nope-nope-nope', APPROVED, 'op').outcome == OUTCOME_UNKNOWN_REQUEST
    ledger.open_request('req-input-1', ttl_s=60)
    assert ledger.decide('req-input-1', 'MAYBE', 'op').outcome == OUTCOME_INVALID_DECISION
    assert ledger.decide('req-input-1', APPROVED, '').outcome == OUTCOME_INVALID_DECISION
    assert ledger.state('req-input-1') == PENDING


def test_duplicate_request_id_is_refused(db_path):
    ledger = DurableApprovalLedger(db_path, FakeClock())
    ledger.open_request('req-dup-1', ttl_s=60)
    with pytest.raises(ValueError):
        ledger.open_request('req-dup-1', ttl_s=60)


def test_unwritable_location_raises_instead_of_pretending(tmp_path):
    bad = str(tmp_path / 'no_such_dir' / 'approvals.db')
    with pytest.raises(sqlite3.OperationalError):
        DurableApprovalLedger(bad, FakeClock())
