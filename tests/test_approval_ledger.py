"""Approval ledger: single decision, duplicates, conflicts, expiry, unknown and malformed input."""
import pytest

from agent.approval_ledger import (ApprovalLedger, APPROVED, DENIED, EXPIRED, PENDING,
                                   OUTCOME_RECORDED, OUTCOME_ALREADY_DECIDED, OUTCOME_CONFLICT,
                                   OUTCOME_EXPIRED, OUTCOME_UNKNOWN_REQUEST, OUTCOME_INVALID_DECISION)


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t
    def __call__(self):
        return self.t


def make(ttl=60.0):
    clock = FakeClock()
    ledger = ApprovalLedger(clock)
    ledger.open_request('req-1', ttl_s=ttl)
    return ledger, clock


def test_first_approval_is_recorded_and_allows_dispatch():
    ledger, _ = make()
    r = ledger.decide('req-1', APPROVED, 'op-7')
    assert r.outcome == OUTCOME_RECORDED and r.state == APPROVED and r.dispatch_allowed


def test_first_denial_is_recorded_and_forbids_dispatch():
    ledger, _ = make()
    r = ledger.decide('req-1', DENIED, 'op-7')
    assert r.outcome == OUTCOME_RECORDED and r.state == DENIED and not r.dispatch_allowed


def test_duplicate_approval_is_idempotent_and_never_dispatches_twice():
    ledger, _ = make()
    ledger.decide('req-1', APPROVED, 'op-7')
    r = ledger.decide('req-1', APPROVED, 'op-7')
    assert r.outcome == OUTCOME_ALREADY_DECIDED
    assert r.state == APPROVED
    assert r.dispatch_allowed is False


def test_conflicting_decision_is_rejected_and_state_unchanged():
    ledger, _ = make()
    ledger.decide('req-1', APPROVED, 'op-7')
    r = ledger.decide('req-1', DENIED, 'op-8')
    assert r.outcome == OUTCOME_CONFLICT
    assert ledger.state('req-1') == APPROVED


def test_decision_after_expiry_is_refused():
    ledger, clock = make(ttl=60)
    clock.t += 61
    r = ledger.decide('req-1', APPROVED, 'op-7')
    assert r.outcome == OUTCOME_EXPIRED and r.state == EXPIRED and not r.dispatch_allowed


def test_state_reports_expiry_without_a_decision():
    ledger, clock = make(ttl=10)
    assert ledger.state('req-1') == PENDING
    clock.t += 10
    assert ledger.state('req-1') == EXPIRED


def test_expire_marks_pending_request_and_cannot_be_undone():
    ledger, _ = make()
    assert ledger.expire('req-1').outcome == OUTCOME_EXPIRED
    r = ledger.decide('req-1', APPROVED, 'op-7')
    assert r.outcome == OUTCOME_EXPIRED and not r.dispatch_allowed


def test_expire_after_decision_does_not_change_it():
    ledger, _ = make()
    ledger.decide('req-1', APPROVED, 'op-7')
    ledger.expire('req-1')
    assert ledger.state('req-1') == APPROVED


def test_unknown_request_is_rejected():
    ledger, _ = make()
    r = ledger.decide('no-such-request', APPROVED, 'op-7')
    assert r.outcome == OUTCOME_UNKNOWN_REQUEST and not r.dispatch_allowed


@pytest.mark.parametrize('bad', ['MAYBE', 'approved', '', None, 1])
def test_invalid_decision_values_are_rejected_without_state_change(bad):
    ledger, _ = make()
    r = ledger.decide('req-1', bad, 'op-7')
    assert r.outcome == OUTCOME_INVALID_DECISION
    assert ledger.state('req-1') == PENDING


@pytest.mark.parametrize('operator', ['', '   ', None])
def test_decision_without_operator_identity_is_rejected(operator):
    ledger, _ = make()
    r = ledger.decide('req-1', APPROVED, operator)
    assert r.outcome == OUTCOME_INVALID_DECISION and not r.dispatch_allowed
    assert ledger.state('req-1') == PENDING


def test_open_request_rejects_duplicates_and_bad_ttl():
    ledger, _ = make()
    with pytest.raises(ValueError):
        ledger.open_request('req-1', ttl_s=60)
    with pytest.raises(ValueError):
        ledger.open_request('req-2', ttl_s=0)
    with pytest.raises(ValueError):
        ledger.open_request('', ttl_s=60)
