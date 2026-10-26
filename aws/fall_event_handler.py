"""
AWS Lambda handler: stores a human-approved vision fall event in DynamoDB.

Idempotency
-----------
Each request must carry an `idempotency_key` (the agent uses the run id). The
incident id is derived from that key with uuid5, so a retried request maps to
the same incident id. The DynamoDB write is conditional on the item not existing.
A retry therefore returns 200 with duplicate=True and does not create a second
incident.

Environment
-----------
FALLS_TABLE   DynamoDB table name (default: fall-guardian-events)

Responses
---------
201  stored (new incident)
200  duplicate request (same idempotency key already stored)
400  invalid input (nothing written)
500  storage failure (nothing confirmed as stored)

Nothing here contacts emergency services.
"""
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REQUIRED = ('user_id', 'event_type', 'timestamp', 'decision', 'idempotency_key')
ALLOWED_DECISIONS = ('APPROVED',)     # only human-approved events are stored
MAX_BODY_BYTES = 8 * 1024
_KEY_RE = re.compile(r'^[A-Za-z0-9_\-]{8,64}$')
_USER_RE = re.compile(r'^[A-Za-z0-9_\-]{1,64}$')
_TABLE_RE = re.compile(r'^[A-Za-z0-9_.\-]{3,255}$')
ALLOWED_FIELDS = set(REQUIRED) | {'schema_version'}
_INCIDENT_NS = uuid.UUID('6f1c2a9e-4b7d-4e35-9a7c-0f0e1d2c3b4a')  # fixed namespace for uuid5


class StorageError(Exception):
    pass


def _parse(event):
    if isinstance(event, dict) and 'body' in event:
        body = event['body']
        if body is None:
            raise ValueError("body is missing")
        if isinstance(body, str):
            if len(body.encode('utf-8')) > MAX_BODY_BYTES:
                raise ValueError("body too large")
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                raise ValueError("body is not valid JSON")
        if isinstance(body, dict):
            return body
        raise ValueError("body must be a JSON object")
    if isinstance(event, dict):
        return event
    raise ValueError("event must be a JSON object")


def validate(payload):
    if not isinstance(payload, dict):
        return ["payload must be a JSON object"]
    errors = []
    for f in REQUIRED:
        if f not in payload:
            errors.append(f"missing field: {f}")
    if 'user_id' in payload and (not isinstance(payload['user_id'], str) or not _USER_RE.match(payload['user_id'])):
        errors.append("user_id must be 1-64 letters, digits, '-' or '_'")
    for f in sorted(payload):
        if f not in ALLOWED_FIELDS:
            errors.append(f"unknown field: {f}")
    if 'schema_version' in payload and payload['schema_version'] != '1.0':
        errors.append("unsupported schema_version")
    if payload.get('event_type') != 'vision_fall':
        errors.append("event_type must be 'vision_fall'")
    if 'decision' in payload and payload['decision'] not in ALLOWED_DECISIONS:
        errors.append("only human-approved events (decision=APPROVED) are stored")
    if 'timestamp' in payload:
        try:
            parsed = datetime.fromisoformat(str(payload['timestamp']).replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                raise ValueError('naive')
        except ValueError:
            errors.append("timestamp must be ISO 8601 with a timezone")
    if 'idempotency_key' in payload and (not isinstance(payload['idempotency_key'], str)
                                         or not _KEY_RE.match(payload['idempotency_key'])):
        errors.append("idempotency_key must be 8-64 characters: letters, digits, '-' or '_'")
    return errors


def _response(code, body):
    return {'statusCode': code, 'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(body)}


def _is_conditional_failure(exc):
    resp = getattr(exc, 'response', None) or {}
    code = (resp.get('Error') or {}).get('Code')
    return code == 'ConditionalCheckFailedException' or type(exc).__name__ == 'ConditionalCheckFailedException'


class ConfigurationError(Exception):
    pass


def table_name():
    """Return the configured table name, or raise ConfigurationError (never a default that hides a typo)."""
    name = os.environ.get('FALLS_TABLE', 'fall-guardian-events')
    if not _TABLE_RE.match(name or ''):
        raise ConfigurationError('FALLS_TABLE is missing or not a valid DynamoDB table name')
    return name


def _get_table(table):
    if table is not None:
        return table
    import boto3   # imported lazily so tests do not need AWS libraries
    return boto3.resource('dynamodb').Table(table_name())


def handler(event, context=None, table=None):
    try:
        payload = _parse(event)
    except ValueError as e:
        return _response(400, {'error': str(e)})

    errors = validate(payload)
    if errors:
        # Do not echo the payload: it may contain personal data.
        return _response(400, {'errors': errors})

    incident_id = str(uuid.uuid5(_INCIDENT_NS, payload['idempotency_key']))
    item = {
        'incident_id': incident_id,
        'user_id': payload['user_id'],
        'event_type': payload['event_type'],
        'timestamp': str(payload['timestamp']),
        'decision': payload['decision'],
        'idempotency_key': payload['idempotency_key'],
        'stored_at': datetime.now(timezone.utc).isoformat(),
        'source': 'vision_human_approved',
    }
    try:
        target = _get_table(table)
    except ConfigurationError as e:
        logger.error("configuration error: %s", e)
        return _response(500, {'error': 'service misconfigured'})
    try:
        target.put_item(Item=item, ConditionExpression='attribute_not_exists(incident_id)')
    except Exception as e:
        if _is_conditional_failure(e):
            logger.info("duplicate request ignored (idempotent)")
            return _response(200, {'incident_id': incident_id, 'duplicate': True})
        logger.error("storage failure: %s", type(e).__name__)
        return _response(500, {'error': 'storage failed', 'detail': type(e).__name__})
    logger.info("event stored")
    return _response(201, {'incident_id': incident_id, 'duplicate': False})
