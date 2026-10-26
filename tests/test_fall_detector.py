"""
Tests for the PROTOTYPE threshold detector.

These use synthetic inputs chosen to exercise code paths. They do NOT measure
real-world fall-detection performance; no such claim is made anywhere in the
project until a labelled clinical dataset has been evaluated.
"""
import math

import pytest

from bee_detection.fall_detector import (
    FallDetector, MODEL_STATUS_LOAD_FAILED, MODEL_STATUS_MISSING,
    MODEL_STATUS_NOT_REQUESTED, METHOD_THRESHOLD,
)


@pytest.fixture
def detector():
    return FallDetector()


def test_normal_activity_is_classified_as_normal(detector):
    r = detector.detect_fall([0.9, 0.1, 0.2], 72)
    assert r['detection_status'] == 'NORMAL_ACTIVITY'
    assert r['prototype_score'] == 0.0
    assert r['detection_method'] == METHOD_THRESHOLD


def test_fall_like_spike_is_detected(detector):
    r = detector.detect_fall([15.2, 14.8, 16.1], 95)
    assert r['detection_status'] == 'FALL_DETECTED'
    assert r['prototype_score'] >= FallDetector.FALL_SCORE_THRESHOLD
    assert r['severity'] > 0


def test_intermediate_spike_is_possible_fall(detector):
    # magnitude 17 -> heuristic score 0.5, inside the POSSIBLE band [0.40, 0.65)
    r = detector.detect_fall([17.0, 0.0, 0.0])
    assert r['detection_status'] == 'POSSIBLE_FALL'
    assert FallDetector.POSSIBLE_FALL_THRESHOLD <= r['prototype_score'] < FallDetector.FALL_SCORE_THRESHOLD


def test_output_never_claims_calibrated_probability(detector):
    r = detector.detect_fall([15.2, 14.8, 16.1], 95)
    assert r['is_calibrated_probability'] is False
    assert 'fall_probability' not in r
    assert 'confidence' not in r


def test_multi_sample_window_uses_peak_magnitude(detector):
    window = [[0.9, 0.1, 0.2], [1.0, 0.0, 0.1], [15.2, 14.8, 16.1]]
    r = detector.detect_fall(window)
    assert r['detection_status'] == 'FALL_DETECTED'


def test_missing_accelerometer_is_insufficient_data(detector):
    r = detector.detect_fall(None, 72)
    assert r['detection_status'] == 'INSUFFICIENT_DATA'
    assert r['processing_status'] == 'VALIDATION_ERROR'
    assert r['prototype_score'] is None


@pytest.mark.parametrize('bad', [
    [],                       # empty
    [1.0, 2.0],               # too few values
    [1.0, 2.0, 3.0, 4.0],     # too many values
    [[1.0, 2.0], [3.0, 4.0]], # wrong column count
    ['a', 'b', 'c'],          # non-numeric
    [float('nan'), 0.0, 0.0], # NaN
    [float('inf'), 0.0, 0.0], # infinity
    [[[1.0, 2.0, 3.0]]],      # 3-D nesting
])
def test_malformed_accelerometer_is_rejected(detector, bad):
    r = detector.detect_fall(bad, 72)
    assert r['detection_status'] == 'INSUFFICIENT_DATA'
    assert r['validation_errors']
    assert r['prototype_score'] is None


def test_missing_heart_rate_still_classifies_accelerometer(detector):
    r = detector.detect_fall([15.2, 14.8, 16.1], None)
    assert r['detection_status'] == 'FALL_DETECTED'


@pytest.mark.parametrize('hr', [-5, 400, float('nan'), 'fast', True])
def test_invalid_heart_rate_is_ignored_and_recorded(detector, hr):
    r = detector.detect_fall([0.9, 0.1, 0.2], hr)
    assert r['detection_status'] == 'NORMAL_ACTIVITY'
    assert any('Heart rate ignored' in e for e in r['validation_errors'])


def test_elevated_heart_rate_alone_does_not_trigger_fall(detector):
    r = detector.detect_fall([0.9, 0.1, 0.2], 180)
    assert r['detection_status'] == 'NORMAL_ACTIVITY'


def test_no_model_path_reports_not_requested(detector):
    assert detector.model_status == MODEL_STATUS_NOT_REQUESTED
    assert detector.model_loaded is False


def test_missing_model_file_is_reported_and_falls_back(tmp_path):
    d = FallDetector(model_path=str(tmp_path / 'does_not_exist.keras'))
    assert d.model_status == MODEL_STATUS_MISSING
    r = d.detect_fall([15.2, 14.8, 16.1], 95)
    assert r['model_status'] == MODEL_STATUS_MISSING
    assert r['detection_method'] == METHOD_THRESHOLD
    assert r['detection_status'] == 'FALL_DETECTED'


def test_corrupt_model_file_is_reported_as_load_failed(tmp_path):
    bad = tmp_path / 'corrupt.keras'
    bad.write_bytes(b'not a model')
    d = FallDetector(model_path=str(bad))
    assert d.model_status in (MODEL_STATUS_LOAD_FAILED,)
    assert d.model_loaded is False
