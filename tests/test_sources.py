"""Video source selection: clear errors, no camera needed for the core tests."""
import pytest

import cv2

from vision import sources
from vision.sources import SourceError, parse_spec, resolve_video_path, open_camera


@pytest.mark.parametrize('bad', ['', 'nocolon', 'webcam:0', 'file:', 'synthetic:', None, 42])
def test_malformed_specs_are_rejected(bad):
    with pytest.raises(SourceError):
        parse_spec(bad)


def test_missing_file_gives_a_clear_error(tmp_path):
    with pytest.raises(SourceError, match='no such file'):
        resolve_video_path(f'file:{tmp_path / "missing.mp4"}')


def test_existing_file_is_returned_unchanged(tmp_path):
    f = tmp_path / 'clip.mp4'
    f.write_bytes(b'placeholder')
    assert resolve_video_path(f'file:{f}') == str(f)


def test_unknown_synthetic_scenario_is_rejected(tmp_path):
    with pytest.raises(SourceError, match='unknown synthetic scenario'):
        resolve_video_path('synthetic:not_a_scenario', workdir=str(tmp_path))


def test_synthetic_scenario_generates_a_readable_clip(tmp_path):
    path = resolve_video_path('synthetic:walk', workdir=str(tmp_path))
    cap = cv2.VideoCapture(path)
    assert cap.isOpened()
    assert cap.read()[0] is True
    cap.release()


def test_camera_index_must_be_an_integer():
    with pytest.raises(SourceError, match='integer'):
        open_camera('front-door')


def test_negative_camera_index_is_rejected():
    with pytest.raises(SourceError):
        open_camera('-1')


def test_missing_camera_gives_a_clear_error_without_touching_hardware(monkeypatch):
    class ClosedCapture:
        def __init__(self, index):
            self.index = index
        def isOpened(self):
            return False
        def release(self):
            self.released = True

    monkeypatch.setattr(sources.cv2, 'VideoCapture', ClosedCapture)
    with pytest.raises(SourceError, match='no camera available at index 3'):
        open_camera('3')


def test_video_file_demo_reports_missing_file_with_exit_code_2(tmp_path):
    import subprocess, sys, os
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run([sys.executable, os.path.join(repo, 'run_cv_demo.py'),
                           '--video', str(tmp_path / 'nope.mp4'), '--trace', str(tmp_path / 't.jsonl')],
                          cwd=tmp_path, capture_output=True, text=True, timeout=60,
                          env={**os.environ, 'PYTHONPATH': repo})
    assert proc.returncode == 2
    assert 'no such file' in proc.stdout
