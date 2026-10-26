"""
Event contract tests. Fixtures in contracts/examples are data-driven: each states
whether it is valid and, if not, the stable error code that must be reported.

Drift test: the Lambda handler must agree with the contract on every approved-record fixture.
"""
import glob
import json
import os
from datetime import datetime, timezone

import pytest

from contracts.incident_contract import (validate_candidate, validate_approved_record,
                                         SCHEMA_VERSION, ERROR_CODES)
from aws.fall_event_handler import handler
from aws.local_table import LocalTable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = sorted(glob.glob(os.path.join(ROOT, 'contracts', 'examples', '*.json')))
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)   # fixed clock for deterministic tests


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def verdict(doc):
    fn = validate_candidate if doc['kind'] == 'candidate' else validate_approved_record
    return fn(doc['payload'], now=NOW)


@pytest.mark.parametrize('path', FIXTURES, ids=[os.path.basename(p) for p in FIXTURES])
def test_fixture_verdict_matches_expectation(path):
    doc = load(path)
    problems = verdict(doc)
    if doc['expect_valid']:
        assert problems == [], [p.as_dict() for p in problems]
    else:
        assert problems, 'invalid fixture was accepted'
        codes = [p.code for p in problems]
        assert doc['expected_code'] in codes, codes


# Codes that cannot be produced by a JSON fixture; each has a dedicated test below.
DIRECT_TEST_CODES = {'PAYLOAD_TOO_LARGE', 'NOT_AN_OBJECT'}


def test_every_error_code_is_exercised_by_a_fixture_or_a_direct_test():
    seen = set()
    for path in FIXTURES:
        seen.update(p.code for p in verdict(load(path)))
    uncovered = set(ERROR_CODES) - seen - DIRECT_TEST_CODES
    assert uncovered == set(), f'error codes without a fixture: {sorted(uncovered)}'


def test_oversized_payload_is_rejected_before_inspection():
    problems = validate_candidate({'x': 'y'}, now=NOW, raw_bytes=b'x' * (8 * 1024 + 1))
    assert [p.code for p in problems] == ['PAYLOAD_TOO_LARGE']


def test_non_object_payloads_are_rejected():
    for bad in (None, 'text', 12, [1, 2]):
        assert [p.code for p in validate_candidate(bad, now=NOW)] == ['NOT_AN_OBJECT']
        assert [p.code for p in validate_approved_record(bad, now=NOW)] == ['NOT_AN_OBJECT']


def test_error_messages_do_not_echo_offending_values():
    doc = {'kind': 'approved', 'payload': {
        'user_id': 'Margaret Smith (phone 555-0199)', 'event_type': 'vision_fall',
        'timestamp': '2026-10-20T10:00:00Z', 'decision': 'APPROVED',
        'idempotency_key': 'run-abcdef123456'}}
    for p in verdict(doc):
        assert 'Margaret' not in p.message and '555-0199' not in p.message


def test_schema_version_constant_is_stated():
    assert SCHEMA_VERSION == '1.0'


@pytest.mark.parametrize('path', [p for p in FIXTURES if 'approved_' in os.path.basename(p)],
                         ids=[os.path.basename(p) for p in FIXTURES if 'approved_' in os.path.basename(p)])
def test_lambda_handler_agrees_with_contract_on_approved_fixtures(path):
    doc = load(path)
    contract_accepts = not verdict(doc)
    body = json.dumps(doc['payload'])
    # The handler does not check the future-timestamp rule, so the fixtures keep timestamps in the past.
    response = handler({'body': body}, table=LocalTable())
    handler_accepts = response['statusCode'] in (200, 201)
    assert handler_accepts == contract_accepts, (response, [p.as_dict() for p in verdict(doc)])
