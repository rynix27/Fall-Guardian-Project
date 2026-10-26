"""
Fall Guardian - emergency response coordinator.

Entry points
------------
detect_fall(user_id, accelerometer, heart_rate)
    Runs the accelerometer prototype detector. Only a FALL_DETECTED result
    starts the emergency workflow.
confirm_fall_event(user_id, severity, location, source)
    Starts the same workflow for an event that a human has already confirmed
    (for example, a vision event approved by a caregiver). Used by the
    approval agent.

Modes
-----
DEMO         Every outward action is SIMULATED. No provider is ever called.
INTEGRATION  Each action calls the provider registered for it. A provider
             reports success only by returning {'confirmed': True, ...}.
             A channel with no provider is NOT_CONFIGURED, never SUCCESS.

Channel status values
---------------------
SUCCESS, SIMULATED, NOT_CONFIGURED, FAILED, TIMEOUT

Overall status values
---------------------
NO_FALL_DETECTED, DUPLICATE_SUPPRESSED, VALIDATION_FAILED, FAILED,
SIMULATED_ONLY, COMPLETE, PARTIAL_FAILURE, INCOMPLETE
"""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import database_setup as db
from bee_detection.fall_detector import FallDetector

logger = logging.getLogger(__name__)

MODE_DEMO = 'DEMO'
MODE_INTEGRATION = 'INTEGRATION'
VALID_MODES = (MODE_DEMO, MODE_INTEGRATION)

CHANNELS = ('family_notification', 'emergency_dispatch', 'smart_lock', 'dashboard')

_ALERT_STATUS = {
    'SUCCESS': 'SENT',
    'SIMULATED': 'SIMULATED',
    'NOT_CONFIGURED': 'NOT_CONFIGURED',
    'FAILED': 'FAILED',
    'TIMEOUT': 'TIMEOUT',
}


def _contacts_from_env():
    raw = os.environ.get('EMERGENCY_CONTACTS', '')
    return [c.strip() for c in raw.split(',') if c.strip()]


def _new_response(mode, user_id, source):
    return {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'user_id': user_id,
        'mode': mode,
        'source': source,
        'status': None,
        'detection_status': None,
        'prototype_score': None,
        'severity': 0,
        'incident_id': None,
        'channels': {},
        'errors': [],
        'response_time_ms': 0,
    }


class EmergencyResponseService:
    def __init__(self, mode: str = MODE_DEMO, timeout_ms: int = 5000,
                 contacts: Optional[List[str]] = None,
                 providers: Optional[Dict[str, Callable[[dict], dict]]] = None,
                 duplicate_window_s: int = 120):
        if mode not in VALID_MODES:
            raise ValueError(f"mode must be one of {VALID_MODES}")
        if not isinstance(timeout_ms, int) or timeout_ms <= 0:
            raise ValueError("timeout_ms must be a positive integer")
        unknown = set(providers or {}) - set(CHANNELS)
        if unknown:
            raise ValueError(f"Unknown provider channels: {sorted(unknown)}")

        self.mode = mode
        self.timeout_ms = timeout_ms
        self.contacts = list(contacts) if contacts is not None else _contacts_from_env()
        self.providers = dict(providers or {})
        self.duplicate_window_s = duplicate_window_s
        self.detector = FallDetector()
        self.response_log: List[Dict] = []
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='fg-channel')
        logger.info(f"Emergency response service started in {mode} mode")

    # ------------------------------------------------------------ public API
    def detect_fall(self, user_id, accelerometer_data, heart_rate=None) -> Dict:
        """Run the accelerometer detector and, only on FALL_DETECTED, the workflow."""
        started = time.monotonic()
        response = _new_response(self.mode, user_id, 'accelerometer')

        if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
            response['status'] = 'VALIDATION_FAILED'
            response['errors'].append(f"Invalid user_id: {user_id}")
            return self._finish(response, started)

        detection = self.detector.detect_fall(accelerometer_data, heart_rate)
        response['detection_status'] = detection['detection_status']
        response['prototype_score'] = detection['prototype_score']
        response['severity'] = detection['severity']
        response['errors'].extend(detection['validation_errors'])

        if detection['detection_status'] == 'INSUFFICIENT_DATA':
            response['status'] = 'VALIDATION_FAILED'
            return self._finish(response, started)
        if detection['detection_status'] != 'FALL_DETECTED':
            response['status'] = 'NO_FALL_DETECTED'
            return self._finish(response, started)

        return self._run_workflow(response, started, detection['severity'], 'Unknown Location')

    def confirm_fall_event(self, user_id, severity, location='Unknown Location',
                           source='human_confirmed') -> Dict:
        """Run the workflow for an event a human has already confirmed."""
        started = time.monotonic()
        response = _new_response(self.mode, user_id, source)
        response['detection_status'] = 'CONFIRMED_BY_HUMAN'
        response['severity'] = severity

        if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
            response['status'] = 'VALIDATION_FAILED'
            response['errors'].append(f"Invalid user_id: {user_id}")
            return self._finish(response, started)
        if not isinstance(severity, int) or isinstance(severity, bool) or not 0 <= severity <= 10:
            response['status'] = 'VALIDATION_FAILED'
            response['errors'].append(f"Invalid severity: {severity}")
            return self._finish(response, started)

        return self._run_workflow(response, started, severity, location)

    def get_response_history(self) -> List[Dict]:
        return list(self.response_log)

    def close(self):
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------ internals
    def _run_workflow(self, response, started, severity, location):
        user_id = response['user_id']
        try:
            user = db.get_user(user_id)
        except Exception as e:
            response['status'] = 'FAILED'
            response['errors'].append(f"Could not read user: {e}")
            return self._finish(response, started)
        if user is None:
            response['status'] = 'VALIDATION_FAILED'
            response['errors'].append(f"User {user_id} does not exist")
            return self._finish(response, started)
        user_name, user_age = user[1], user[2]

        try:
            existing = db.find_open_duplicate(user_id, self.duplicate_window_s)
        except Exception as e:
            response['status'] = 'FAILED'
            response['errors'].append(f"Duplicate check failed: {e}")
            return self._finish(response, started)
        if existing is not None:
            response['status'] = 'DUPLICATE_SUPPRESSED'
            response['incident_id'] = existing
            response['errors'].append(f"Open incident {existing} already exists; no new actions taken")
            return self._finish(response, started)

        try:
            incident_id = db.log_fall(user_id, severity, location, 0)
        except Exception as e:
            response['status'] = 'FAILED'
            response['errors'].append(f"Could not record incident: {e}")
            return self._finish(response, started)
        response['incident_id'] = incident_id

        payload = {
            'incident_id': incident_id,
            'user_id': user_id,
            'user_name': user_name,
            'user_age': user_age,
            'severity': severity,
            'location': location,
            'source': response['source'],
            'contacts': self.contacts,
        }
        for channel in CHANNELS:
            result = self._run_channel(channel, payload)
            response['channels'][channel] = result
            if result['status'] not in ('SUCCESS', 'SIMULATED'):
                response['errors'].append(f"{channel}: {result['status']} - {result['detail']}")
            try:
                db.send_alert(incident_id, channel, result.get('recipient') or 'N/A',
                              _ALERT_STATUS.get(result['status'], result['status']))
            except Exception as e:
                response['errors'].append(f"Could not record {channel} attempt: {e}")

        response['status'] = self._overall_status(response['channels'])
        logger.info(f"Incident {incident_id} workflow finished: {response['status']}")
        return self._finish(response, started)

    def _run_channel(self, channel: str, payload: dict) -> Dict:
        if self.mode == MODE_DEMO:
            return {'status': 'SIMULATED', 'detail': f"{channel} simulated (nothing contacted)",
                    'recipient': None}

        if channel == 'family_notification' and not self.contacts:
            return {'status': 'NOT_CONFIGURED', 'detail': 'No emergency contacts configured',
                    'recipient': None}

        provider = self.providers.get(channel)
        if provider is None:
            return {'status': 'NOT_CONFIGURED',
                    'detail': f"No provider registered for {channel}", 'recipient': None}

        future = self._executor.submit(provider, payload)
        try:
            outcome = future.result(timeout=self.timeout_ms / 1000.0)
        except FutureTimeout:
            return {'status': 'TIMEOUT', 'detail': f"No response within {self.timeout_ms} ms",
                    'recipient': None}
        except Exception as e:
            return {'status': 'FAILED', 'detail': f"Provider raised {type(e).__name__}: {e}",
                    'recipient': None}

        if not isinstance(outcome, dict):
            return {'status': 'FAILED', 'detail': 'Provider returned an invalid result',
                    'recipient': None}
        if outcome.get('confirmed') is True:
            return {'status': 'SUCCESS', 'detail': str(outcome.get('detail', 'confirmed')),
                    'recipient': outcome.get('recipient')}
        return {'status': 'FAILED', 'detail': str(outcome.get('detail', 'not confirmed')),
                'recipient': outcome.get('recipient')}

    @staticmethod
    def _overall_status(channels: Dict[str, Dict]) -> str:
        statuses = {c['status'] for c in channels.values()}
        if statuses <= {'SIMULATED'}:
            return 'SIMULATED_ONLY'
        if statuses <= {'SUCCESS'}:
            return 'COMPLETE'
        if statuses & {'FAILED', 'TIMEOUT'}:
            return 'PARTIAL_FAILURE'
        return 'INCOMPLETE'

    def _finish(self, response: Dict, started: float) -> Dict:
        response['response_time_ms'] = int((time.monotonic() - started) * 1000)
        self.response_log.append(response)
        return response
