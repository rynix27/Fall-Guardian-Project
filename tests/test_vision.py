"""
Vision pipeline tests on SYNTHETIC clips (generated in tmp_path).
These confirm the rule logic on controlled inputs. They are not evidence of
real-world fall-detection performance.
"""
import os

import pytest

from vision.fall_vision import VisionFallDetector, VisionConfig, STATE_NO_PERSON, STATE_WARMUP
from vision.synthetic_clips import make_clip


@pytest.fixture(scope='module')
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp('clips')
    return {name: make_clip(name, os.path.join(d, f'{name}.mp4'))
            for name in ('fall', 'sit_down', 'bend', 'walk', 'long_lie')}


def test_synthetic_fall_produces_one_event(clips):
    events, _ = VisionFallDetector().process_video(clips['fall'])
    assert len(events) == 1
    e = events[0]
    assert e.aspect_before >= VisionConfig().upright_aspect
    assert e.aspect_after <= VisionConfig().lying_aspect
    assert e.hold_s >= VisionConfig().hold_s
    assert e.centroid_drop >= VisionConfig().drop_fraction


@pytest.mark.parametrize('name', ['sit_down', 'bend', 'walk'])
def test_non_fall_activity_produces_no_event(clips, name):
    events, _ = VisionFallDetector().process_video(clips[name])
    assert events == []


def test_long_lie_is_detected_on_this_clip(clips):
    # Documents current behaviour: lying still for ~10 s still produced an event
    # on this clip. Background absorption may change this on other clips.
    events, _ = VisionFallDetector().process_video(clips['long_lie'])
    assert len(events) == 1


def test_event_fires_only_once_per_lying_episode(clips):
    events, _ = VisionFallDetector().process_video(clips['long_lie'])
    assert len(events) <= 1


def test_warmup_frames_are_reported_as_warmup_and_emit_nothing(clips):
    cfg = VisionConfig()
    _, trace = VisionFallDetector().process_video(clips['walk'], keep_trace=True)
    warm = trace[:cfg.warmup_frames]
    assert all(r.state == STATE_WARMUP for r in warm)
    assert all(r.box is None for r in warm)


def test_empty_scene_after_warmup_reports_no_person(clips):
    cfg = VisionConfig()
    _, trace = VisionFallDetector().process_video(clips['walk'], keep_trace=True)
    empty_after = [r for r in trace[cfg.warmup_frames:cfg.warmup_frames + 10] if r.box is None]
    assert len(empty_after) > 0   # walk clip starts with an empty scene after warm-up


def test_unreadable_video_raises(tmp_path):
    bad = tmp_path / 'not_a_video.mp4'
    bad.write_bytes(b'garbage')
    with pytest.raises(IOError):
        VisionFallDetector().process_video(str(bad))


def test_missing_video_raises(tmp_path):
    with pytest.raises(IOError):
        VisionFallDetector().process_video(str(tmp_path / 'nope.mp4'))


def test_file_that_opens_but_decodes_no_frames_is_an_error(monkeypatch):
    # Exercises the zero-frame guard specifically: isOpened() is True, read() returns nothing.
    import vision.fall_vision as fv

    class OpenButEmpty:
        def __init__(self, path):
            pass
        def isOpened(self):
            return True
        def get(self, prop):
            return 15.0
        def read(self):
            return False, None
        def release(self):
            pass

    monkeypatch.setattr(fv.cv2, 'VideoCapture', OpenButEmpty)
    with pytest.raises(IOError, match='No frames'):
        VisionFallDetector().process_video('anything.mp4')
