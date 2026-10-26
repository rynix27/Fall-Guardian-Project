"""
Lambda handler tests using the local table stand-in, which enforces the same
conditional-write rule as DynamoDB. No AWS calls are made.
"""
import json

import pytest

from aws.fall_event_handler import handler, MAX_BODY_BYTES
from aws.local_table import LocalTable, ConditionalCheckFailedException

GOOD = {'user_id': 'u-42', 'event_type': 'vision_fall',
        'timestamp': '2026-10-24T10:00:00Z', 'decision': 'APPROVED',
        'idempotency_key': 'run-abcdef123456'}


class BrokenTable:
    """Raises a non-conditional error, e.g. throttling or a timeout."""
    def put_item(self, Item, ConditionExpression=None):
        raise RuntimeError('ProvisionedThroughputExceeded')


def test_approved_event_is_stored_once_with_201():
    t = LocalTable()
    r = handler({'body': json.dumps(GOOD)}, table=t)
    assert r['statusCode'] == 201
    body = json.loads(r['body'])
    assert body['duplicate'] is False
    assert t.count == 1
    stored = t.items[body['incident_id']]
    assert stored['source'] == 'vision_human_approved'
    assert stored['idempotency_key'] == GOOD['idempotency_key']


def test_retry_with_same_key_does_not_create_second_incident():
    t = LocalTable()
    first = json.loads(handler({'body': json.dumps(GOOD)}, table=t)['body'])
    retry = handler({'body': json.dumps(GOOD)}, table=t)
    assert retry['statusCode'] == 200
    assert json.loads(retry['body'])['duplicate'] is True
    assert json.loads(retry['body'])['incident_id'] == first['incident_id']
    assert t.count == 1


def test_different_keys_create_different_incidents():
    t = LocalTable()
    a = json.loads(handler({'body': json.dumps(GOOD)}, table=t)['body'])
    b = json.loads(handler({'body': json.dumps({**GOOD, 'idempotency_key': 'run-zzzzzz999999'})}, table=t)['body'])
    assert a['incident_id'] != b['incident_id']
    assert t.count == 2


def test_direct_dict_event_is_accepted():
    t = LocalTable()
    assert handler(GOOD, table=t)['statusCode'] == 201


def test_unapproved_event_is_rejected_and_not_stored():
    t = LocalTable()
    r = handler({**GOOD, 'decision': 'PENDING'}, table=t)
    assert r['statusCode'] == 400
    assert t.count == 0


def test_missing_user_id_is_rejected():
    bad = {k: v for k, v in GOOD.items() if k != 'user_id'}
    r = handler(bad, table=LocalTable())
    assert r['statusCode'] == 400
    assert 'missing field: user_id' in json.loads(r['body'])['errors']


def test_missing_idempotency_key_is_rejected():
    bad = {k: v for k, v in GOOD.items() if k != 'idempotency_key'}
    r = handler(bad, table=LocalTable())
    assert r['statusCode'] == 400


@pytest.mark.parametrize('key', ['short', 'has spaces in it', 'x' * 129, 'bad/slash/key', 123])
def test_invalid_idempotency_key_is_rejected(key):
    r = handler({**GOOD, 'idempotency_key': key}, table=LocalTable())
    assert r['statusCode'] == 400


def test_bad_timestamp_is_rejected():
    r = handler({**GOOD, 'timestamp': 'yesterday'}, table=LocalTable())
    assert r['statusCode'] == 400


def test_invalid_json_body_is_rejected():
    r = handler({'body': '{not json'}, table=LocalTable())
    assert r['statusCode'] == 400


def test_oversized_body_is_rejected_before_parsing():
    r = handler({'body': 'x' * (MAX_BODY_BYTES + 1)}, table=LocalTable())
    assert r['statusCode'] == 400


def test_error_response_does_not_echo_personal_data():
    r = handler({**GOOD, 'decision': 'PENDING', 'user_id': 'Margaret Smith'}, table=LocalTable())
    assert 'Margaret Smith' not in r['body']


def test_non_conditional_storage_failure_returns_500_not_201():
    r = handler({'body': json.dumps(GOOD)}, table=BrokenTable())
    assert r['statusCode'] == 500
    assert 'ProvisionedThroughputExceeded' in r['body'] or 'RuntimeError' in r['body']


def test_conditional_failure_is_not_reported_as_storage_error():
    t = LocalTable()
    handler({'body': json.dumps(GOOD)}, table=t)
    r = handler({'body': json.dumps(GOOD)}, table=t)
    assert r['statusCode'] == 200
