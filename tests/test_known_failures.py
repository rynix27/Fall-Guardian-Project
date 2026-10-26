"""
Regression and known-failure tests for the vision detector.

History
-------
Development v1 (7 synthetic clips) missed slow_fall and fall_then_up.

Corrected diagnosis (from per-frame traces, not the earlier guess):
  * slow_fall: the upright->lying transition was NOT the problem (0.33 s, inside
    the 1.0 s window). The lying run was cut short by background absorption: the
    lying box jumped from aspect 0.34 to 1.03 at ~7.7 s with the centroid unchanged,
    resetting the 1.5 s hold timer.
  * fall_then_up: the hold time was reached, but the centroid rise during standing
    up cancelled the drop condition on that exact frame.

Fixes: a grace period inside lying episodes (0.5 s, centroid must stay low) and
a latched drop (largest drop in the episode is kept).

These two clips are now REGRESSION tests asserting the desired behaviour.
They were the motivating cases, so they are development evidence, not validation.
Held-out results are in EVALUATION_REPORT.md.
"""
import os

import pytest

from vision.fall_vision import VisionFallDetector
from vision.synthetic_clips import make_clip


@pytest.fixture(scope='module')
def clip_dir(tmp_path_factory):
    return tmp_path_factory.mktemp('regression_clips')


def _events(path):
    events, _ = VisionFallDetector().process_video(path)
    return events


def test_regression_slow_fall_is_detected(clip_dir):
    path = make_clip('slow_fall', os.path.join(clip_dir, 'slow.mp4'))
    assert len(_events(path)) == 1


def test_regression_fall_then_standing_is_detected(clip_dir):
    # Fall with ~1.6 s on the floor, then standing up. Must produce a candidate
    # for human review; standing up does not erase it.
    path = make_clip('fall_then_up', os.path.join(clip_dir, 'up.mp4'))
    assert len(_events(path)) == 1


@pytest.mark.xfail(strict=True, reason='held-out: slow fall at 0.7x scale is still missed')
def test_known_miss_slow_fall_small_person(clip_dir):
    path = make_clip('slow_fall', os.path.join(clip_dir, 'slow07.mp4'), scale=0.7)
    assert len(_events(path)) == 1


@pytest.mark.xfail(strict=True, reason='known limitation: intentional lie-down looks like a slow fall')
def test_known_false_alarm_intentional_lie_down(clip_dir):
    path = make_clip('intentional_lie', os.path.join(clip_dir, 'intent.mp4'), scale=1.3)
    assert _events(path) == []
