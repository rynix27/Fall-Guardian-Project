"""
Explicit video-source selection with clear errors.

Specs:
  file:<path>        a video file on disk
  synthetic:<name>   a generated test clip (see vision/synthetic_clips.py)
  camera:<index>     a local camera index, e.g. camera:0 (needs real hardware)

Nothing here opens a camera unless the spec asks for one. Core tests never do.
"""
import os
import tempfile

import cv2

from vision.synthetic_clips import make_clip, _scenario_frames


class SourceError(Exception):
    """A source could not be opened. The message says what to check."""


def parse_spec(spec: str):
    if not isinstance(spec, str) or ':' not in spec:
        raise SourceError("source must look like file:<path>, synthetic:<name> or camera:<index>")
    kind, _, value = spec.partition(':')
    if kind not in ('file', 'synthetic', 'camera') or not value:
        raise SourceError("source must be file:<path>, synthetic:<name> or camera:<index>")
    return kind, value


def resolve_video_path(spec: str, workdir: str = None) -> str:
    """Return a path to a readable video for file: and synthetic: specs."""
    kind, value = parse_spec(spec)
    if kind == 'file':
        if not os.path.isfile(value):
            raise SourceError(f"no such file: {value}")
        return value
    if kind == 'synthetic':
        try:
            _scenario_frames(value)   # validates the name without generating anything
        except ValueError:
            raise SourceError(f"unknown synthetic scenario: {value}")
        workdir = workdir or tempfile.mkdtemp(prefix='fg_synth_')
        return make_clip(value, os.path.join(workdir, f'synthetic_{value}.mp4'))
    raise SourceError('camera sources are not read as files; use open_camera()')


def open_camera(index: str):
    """Open a live camera. Raises SourceError if none is available."""
    try:
        idx = int(index)
    except ValueError:
        raise SourceError(f"camera index must be an integer, got {index!r}")
    if idx < 0:
        raise SourceError('camera index must be zero or positive')
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        cap.release()
        raise SourceError(f"no camera available at index {idx}; check that it is connected and not in use")
    return cap
