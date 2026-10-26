"""
Event contracts for Fall Guardian.

Two record types cross component boundaries:

1. CANDIDATE: a vision-pipeline candidate, produced by vision/fall_vision.py and
   consumed by agent/approval_agent.py.
2. APPROVED_RECORD: an approved incident, written by the AWS Lambda handler
   (aws/fall_event_handler.py). Only human-approved records are accepted.

Every validation problem has a stable code (see ERROR_CODES). Messages never
echo the offending value, so personal data is not reflected back to clients.

The contract is versioned. SCHEMA_VERSION identifies this revision; a record
with another major version is rejected with UNSUPPORTED_SCHEMA_VERSION.
"""
import json
import math
import re
from datetime import datetime, timedelta, timezone

SCHEMA_VERSION = '1.0'
MAX_PAYLOAD_BYTES = 8 * 1024
MAX_METADATA_KEYS = 8
MAX_METADATA_VALUE_CHARS = 200
MAX_FUTURE_SKEW = timedelta(minutes=5)

ID_RE = re.compile(r'^[A-Za-z0-9_\-]{8,64}$')
USER_ID_RE = re.compile(r'^[A-Za-z0-9_\-]{1,64}$')

ERROR_CODES = (
    'NOT_AN_OBJECT', 'PAYLOAD_TOO_LARGE', 'MISSING_FIELD', 'UNKNOWN_FIELD', 'WRONG_TYPE',
    'INVALID_IDENTIFIER', 'INVALID_TIMESTAMP', 'TIMESTAMP_IN_FUTURE', 'INVALID_ENUM',
    'OUT_OF_RANGE', 'INVALID_TEXT', 'INVALID_METADATA', 'UNSUPPORTED_SCHEMA_VERSION',
    'NOT_APPROVED',
)

CANDIDATE_FIELDS = {
    'required': {'schema_version', 'event_id', 'timestamp', 'source', 'detector_type',
                 't_s', 'rule'},
    'optional': {'incident_id', 'track_id', 'severity', 'detection_status', 'evidence',
                 'approval_status', 'metadata'},
}
SOURCES = ('vision_pipeline', 'simulation', 'test')
DETECTOR_TYPES = ('threshold_heuristic_v1',)
DETECTION_STATUSES = ('CANDIDATE', 'CONFIRMED')
APPROVAL_STATUSES = ('NOT_REQUESTED', 'PENDING', 'APPROVED', 'DENIED', 'EXPIRED')
EVIDENCE_LABELS = ('RECOVERED_WITHIN_WINDOW', 'NO_RECOVERY_OBSERVED',
                   'UNRESOLVED_TRACKING_LOST', 'INSUFFICIENT_EVIDENCE')

APPROVED_FIELDS = {
    'required': {'user_id', 'event_type', 'timestamp', 'decision', 'idempotency_key'},
    'optional': {'schema_version'},
}


class Problem:
    def __init__(self, code, field, message):
        self.code, self.field, self.message = code, field, message

    def as_dict(self):
        return {'code': self.code, 'field': self.field, 'message': self.message}

    def __repr__(self):
        return f'Problem({self.code}, {self.field})'


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def parse_timestamp(value):
    """Return an aware UTC datetime, or raise ValueError. Naive timestamps are rejected."""
    if not isinstance(value, str):
        raise ValueError('timestamp must be a string')
    text = value.replace('Z', '+00:00') if value.endswith('Z') else value
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError('timestamp must include a timezone')
    return dt.astimezone(timezone.utc)


def _check_payload_size(raw_bytes):
    if raw_bytes is not None and len(raw_bytes) > MAX_PAYLOAD_BYTES:
        return [Problem('PAYLOAD_TOO_LARGE', None, f'payload exceeds {MAX_PAYLOAD_BYTES} bytes')]
    return []


def _check_fields(payload, spec):
    problems = []
    for f in sorted(spec['required']):
        if f not in payload:
            problems.append(Problem('MISSING_FIELD', f, f'required field {f!r} is missing'))
    allowed = spec['required'] | spec['optional']
    for f in sorted(payload):
        if f not in allowed:
            problems.append(Problem('UNKNOWN_FIELD', f, 'field is not part of the contract'))
    return problems


def _check_timestamp(value, field, now):
    try:
        dt = parse_timestamp(value)
    except (ValueError, TypeError):
        return [Problem('INVALID_TIMESTAMP', field, 'timestamp must be ISO 8601 with a timezone')]
    if dt > now + MAX_FUTURE_SKEW:
        return [Problem('TIMESTAMP_IN_FUTURE', field, 'timestamp is later than the allowed clock skew')]
    return []


def _check_enum(value, allowed, field):
    if not isinstance(value, str) or value not in allowed:
        return [Problem('INVALID_ENUM', field, f'must be one of {", ".join(allowed)}')]
    return []


def _check_metadata(value):
    if not isinstance(value, dict):
        return [Problem('INVALID_METADATA', 'metadata', 'metadata must be an object')]
    problems = []
    if len(value) > MAX_METADATA_KEYS:
        problems.append(Problem('INVALID_METADATA', 'metadata', f'at most {MAX_METADATA_KEYS} keys'))
    for k, v in value.items():
        if not isinstance(k, str) or not re.match(r'^[a-z][a-z0-9_]{0,31}$', k):
            problems.append(Problem('INVALID_METADATA', 'metadata', 'metadata keys must be short snake_case'))
            break
        if isinstance(v, (dict, list)):
            problems.append(Problem('INVALID_METADATA', 'metadata', 'metadata values must be scalars'))
            break
        if isinstance(v, str) and len(v) > MAX_METADATA_VALUE_CHARS:
            problems.append(Problem('INVALID_METADATA', 'metadata', 'metadata text value too long'))
            break
    return problems


def validate_candidate(payload, now=None, raw_bytes=None):
    """Return a list of Problems for a vision candidate. Empty list = valid."""
    now = now or datetime.now(timezone.utc)
    problems = _check_payload_size(raw_bytes)
    if problems:
        return problems
    if not isinstance(payload, dict):
        return [Problem('NOT_AN_OBJECT', None, 'payload must be a JSON object')]
    problems += _check_fields(payload, CANDIDATE_FIELDS)
    if 'schema_version' in payload and payload['schema_version'] != SCHEMA_VERSION:
        problems.append(Problem('UNSUPPORTED_SCHEMA_VERSION', 'schema_version',
                                f'this contract is version {SCHEMA_VERSION}'))
    for f in ('event_id', 'incident_id', 'track_id'):
        if f in payload and (not isinstance(payload[f], str) or not ID_RE.match(payload[f])):
            problems.append(Problem('INVALID_IDENTIFIER', f, 'identifier must be 8-64 letters, digits, - or _'))
    if 'timestamp' in payload:
        problems += _check_timestamp(payload['timestamp'], 'timestamp', now)
    if 'source' in payload:
        problems += _check_enum(payload['source'], SOURCES, 'source')
    if 'detector_type' in payload:
        problems += _check_enum(payload['detector_type'], DETECTOR_TYPES, 'detector_type')
    if 't_s' in payload:
        t = payload['t_s']
        if not _is_number(t):
            problems.append(Problem('WRONG_TYPE', 't_s', 't_s must be a finite number'))
        elif t < 0:
            problems.append(Problem('OUT_OF_RANGE', 't_s', 't_s must be non-negative'))
    if 'rule' in payload and (not isinstance(payload['rule'], str) or not payload['rule'].strip()):
        problems.append(Problem('INVALID_TEXT', 'rule', 'rule must be a non-empty string'))
    if 'severity' in payload:
        s = payload['severity']
        if not _is_int(s):
            problems.append(Problem('WRONG_TYPE', 'severity', 'severity must be an integer'))
        elif not 0 <= s <= 10:
            problems.append(Problem('OUT_OF_RANGE', 'severity', 'severity must be 0-10'))
    if 'detection_status' in payload:
        problems += _check_enum(payload['detection_status'], DETECTION_STATUSES, 'detection_status')
    if 'approval_status' in payload:
        problems += _check_enum(payload['approval_status'], APPROVAL_STATUSES, 'approval_status')
    if 'evidence' in payload:
        problems += _check_enum(payload['evidence'], EVIDENCE_LABELS, 'evidence')
    if 'metadata' in payload:
        problems += _check_metadata(payload['metadata'])
    return problems


def validate_approved_record(payload, now=None, raw_bytes=None):
    """Return a list of Problems for an approved-incident record (the Lambda's storage input)."""
    now = now or datetime.now(timezone.utc)
    problems = _check_payload_size(raw_bytes)
    if problems:
        return problems
    if not isinstance(payload, dict):
        return [Problem('NOT_AN_OBJECT', None, 'payload must be a JSON object')]
    problems += _check_fields(payload, APPROVED_FIELDS)
    if 'schema_version' in payload and payload['schema_version'] != SCHEMA_VERSION:
        problems.append(Problem('UNSUPPORTED_SCHEMA_VERSION', 'schema_version',
                                f'this contract is version {SCHEMA_VERSION}'))
    if 'user_id' in payload and (not isinstance(payload['user_id'], str)
                                 or not USER_ID_RE.match(payload['user_id'])):
        problems.append(Problem('INVALID_IDENTIFIER', 'user_id', 'user_id must be 1-64 letters, digits, - or _'))
    if 'idempotency_key' in payload and (not isinstance(payload['idempotency_key'], str)
                                         or not ID_RE.match(payload['idempotency_key'])):
        problems.append(Problem('INVALID_IDENTIFIER', 'idempotency_key',
                                'idempotency_key must be 8-64 letters, digits, - or _'))
    if 'event_type' in payload and payload['event_type'] != 'vision_fall':
        problems.append(Problem('INVALID_ENUM', 'event_type', "event_type must be 'vision_fall'"))
    if 'decision' in payload and payload['decision'] != 'APPROVED':
        problems.append(Problem('NOT_APPROVED', 'decision', 'only APPROVED records may be stored'))
    if 'timestamp' in payload:
        problems += _check_timestamp(payload['timestamp'], 'timestamp', now)
    return problems


def is_valid(problems):
    return not problems


def load_fixture(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
