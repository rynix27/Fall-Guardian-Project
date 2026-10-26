"""
Fall detector - PROTOTYPE.

This module contains a threshold-based heuristic. It is NOT a trained model and
its output is NOT a calibrated probability. The value reported as
`prototype_score` is an uncalibrated heuristic in [0, 1] derived from
hand-picked thresholds. It has not been evaluated on real fall data, and no
accuracy, sensitivity or specificity claim is made for it.

If a trained Keras model path is supplied and loads successfully, the model
output is used instead. If a model path is supplied but cannot be loaded, the
detector falls back to the threshold heuristic and reports this in
`model_status` and `detection_method`, so callers can see that the fallback
happened.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

MODEL_STATUS_NOT_REQUESTED = 'NOT_REQUESTED'
MODEL_STATUS_LOADED = 'LOADED'
MODEL_STATUS_MISSING = 'MISSING'
MODEL_STATUS_LOAD_FAILED = 'LOAD_FAILED'

METHOD_TRAINED_MODEL = 'TRAINED_MODEL'
METHOD_THRESHOLD = 'THRESHOLD_PROTOTYPE'


class FallDetector:
    """Prototype fall detector (threshold heuristic, not clinically validated)."""

    ACCEL_THRESHOLD = 12.0      # magnitude (m/s^2) above which the heuristic starts scoring
    HR_THRESHOLD = 100          # bpm above which the heart-rate term contributes
    FALL_SCORE_THRESHOLD = 0.65 # score at or above which FALL_DETECTED is reported
    POSSIBLE_FALL_THRESHOLD = 0.40
    HR_MIN, HR_MAX = 0, 300

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model = None
        self.version = "1.0-PROTOTYPE"
        if model_path is None:
            self.model_status = MODEL_STATUS_NOT_REQUESTED
            logger.warning("No trained model provided; using threshold heuristic (PROTOTYPE)")
        else:
            self._load_model(model_path)

    @property
    def model_loaded(self) -> bool:
        return self.model_status == MODEL_STATUS_LOADED

    def _load_model(self, model_path: str) -> None:
        import os
        if not os.path.isfile(model_path):
            self.model_status = MODEL_STATUS_MISSING
            logger.error(f"Model file not found: {model_path}; using threshold heuristic")
            return
        try:
            import tensorflow as tf  # optional dependency
            self.model = tf.keras.models.load_model(model_path)
            self.model_status = MODEL_STATUS_LOADED
            logger.info(f"Model loaded from: {model_path}")
        except ImportError:
            self.model_status = MODEL_STATUS_LOAD_FAILED
            logger.error("TensorFlow is not installed; using threshold heuristic")
        except Exception as e:
            self.model_status = MODEL_STATUS_LOAD_FAILED
            logger.error(f"Failed to load model: {e}; using threshold heuristic")

    # ------------------------------------------------------------------ validation
    @classmethod
    def _validate_accelerometer(cls, accel_data) -> Tuple[bool, str]:
        if accel_data is None:
            return False, "Accelerometer data is missing"
        try:
            arr = np.array(accel_data, dtype=float)
        except (ValueError, TypeError):
            return False, "Accelerometer data is not numeric"
        if arr.size == 0:
            return False, "Accelerometer data is empty"
        if arr.ndim == 1:
            if arr.shape[0] != 3:
                return False, f"Expected 3 values [x, y, z], got {arr.shape[0]}"
        elif arr.ndim == 2:
            if arr.shape[1] != 3:
                return False, f"Expected 3 columns [x, y, z], got {arr.shape[1]}"
            if arr.shape[0] == 0:
                return False, "Accelerometer data has no samples"
        else:
            return False, f"Invalid accelerometer dimensions: {arr.shape}"
        if not np.all(np.isfinite(arr)):
            return False, "Accelerometer data contains NaN or infinite values"
        return True, "Valid"

    @classmethod
    def _validate_heart_rate(cls, heart_rate) -> Tuple[bool, str]:
        """Heart rate is optional. None is valid and means 'not available'."""
        if heart_rate is None:
            return True, "Not provided"
        if isinstance(heart_rate, bool):
            return False, "Heart rate must be numeric"
        try:
            hr = float(heart_rate)
        except (ValueError, TypeError):
            return False, "Heart rate is not numeric"
        if not math.isfinite(hr):
            return False, "Heart rate is NaN or infinite"
        if hr < cls.HR_MIN or hr > cls.HR_MAX:
            return False, f"Heart rate {hr} outside [{cls.HR_MIN}, {cls.HR_MAX}]"
        return True, "Valid"

    # ------------------------------------------------------------------ detection
    def detect_fall(self, accelerometer_data, heart_rate=None) -> Dict:
        result = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'detection_status': 'INSUFFICIENT_DATA',
            'prototype_score': None,
            'is_calibrated_probability': False,
            'severity': 0,
            'model_version': self.version,
            'model_status': self.model_status,
            'detection_method': None,
            'processing_status': 'STARTED',
            'validation_errors': [],
        }

        ok, msg = self._validate_accelerometer(accelerometer_data)
        if not ok:
            result['processing_status'] = 'VALIDATION_ERROR'
            result['validation_errors'].append(f"Accelerometer: {msg}")
            return result

        hr_ok, hr_msg = self._validate_heart_rate(heart_rate)
        if not hr_ok:
            # Bad heart-rate data does not invalidate the accelerometer reading;
            # it is dropped and recorded.
            result['validation_errors'].append(f"Heart rate ignored: {hr_msg}")
            heart_rate = None

        try:
            arr = np.array(accelerometer_data, dtype=float)
            if arr.ndim == 1:
                arr = arr.reshape(1, 3)
            magnitudes = np.sqrt(np.sum(arr ** 2, axis=1))
            max_accel = float(np.max(magnitudes))

            if self.model_loaded:
                prediction = self.model.predict(arr.reshape(1, -1, 3), verbose=0)
                score = float(np.asarray(prediction).reshape(-1)[0])
                result['detection_method'] = METHOD_TRAINED_MODEL
            else:
                score = self._threshold_score(max_accel, heart_rate)
                result['detection_method'] = METHOD_THRESHOLD

            score = min(1.0, max(0.0, score))
            result['prototype_score'] = round(score, 4)

            if score >= self.FALL_SCORE_THRESHOLD:
                result['detection_status'] = 'FALL_DETECTED'
                result['severity'] = int(min(10, max(0, max_accel / 2)))
            elif score >= self.POSSIBLE_FALL_THRESHOLD:
                result['detection_status'] = 'POSSIBLE_FALL'
                result['severity'] = int(min(10, max(0, max_accel / 3)))
            else:
                result['detection_status'] = 'NORMAL_ACTIVITY'

            result['processing_status'] = 'COMPLETE'
            logger.info(f"Detection: {result['detection_status']} "
                        f"(score={score:.2f}, method={result['detection_method']})")
            return result
        except Exception as e:
            result['processing_status'] = 'ERROR'
            result['detection_status'] = 'INSUFFICIENT_DATA'
            result['validation_errors'].append(f"Processing error: {e}")
            logger.error(f"Fall detection error: {e}", exc_info=True)
            return result

    def _threshold_score(self, max_accel: float, heart_rate: Optional[float] = None) -> float:
        score = 0.0
        if max_accel > self.ACCEL_THRESHOLD:
            score += min(1.0, (max_accel - self.ACCEL_THRESHOLD) / 8.0) * 0.8
        if heart_rate is not None and heart_rate > self.HR_THRESHOLD:
            score += min(1.0, (heart_rate - self.HR_THRESHOLD) / 50.0) * 0.2
        return min(1.0, score)
