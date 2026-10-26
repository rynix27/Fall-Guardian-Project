"""
Generates SYNTHETIC test clips: a rectangle stands in for a person.

These clips exercise the detection logic under controlled conditions. They are
NOT real footage and results on them are NOT evidence of real-world performance.
"""
import os
from typing import Callable, List, Tuple

import cv2
import numpy as np

W, H, FPS = 320, 240, 15
BG = 60
PERSON = 210
GROUND_Y = 200          # bottom edge of the person when standing


def _pose(kind: str, t: float):
    """Return (width, height, bottom_y, x_center) for a pose parameter t in [0,1]."""
    if kind == 'stand':
        return 30, 90, GROUND_Y, 160
    if kind == 'sit':
        return int(30 + 20 * t), int(90 - 35 * t), GROUND_Y, 160
    if kind == 'walk':
        return 30, 90, GROUND_Y, int(60 + 200 * t)
    raise ValueError(kind)


def _scenario_frames(name: str) -> List[Tuple[str, float]]:
    """Return list of (pose_kind, parameter) per frame after the warm-up."""
    frames = []
    if name == 'fall':
        frames += [('stand', 0.0)] * 20
        for i in range(10):                      # tip over
            frames.append(('tip', (i + 1) / 10))
        frames += [('lying', 1.0)] * 45          # lie still ~3 s
    elif name == 'sit_down':
        frames += [('stand', 0.0)] * 20
        for i in range(12):
            frames.append(('sit', (i + 1) / 12))
        frames += [('sit', 1.0)] * 30
    elif name == 'bend':
        frames += [('stand', 0.0)] * 20
        for i in range(8):
            frames.append(('sit', 0.4 * (i + 1) / 8))
        frames += [('stand', 0.0)] * 20
    elif name == 'walk':
        for i in range(60):
            frames.append(('walk', i / 60))
    elif name == 'slow_fall':                    # tips over over ~2 s instead of ~0.7 s
        frames += [('stand', 0.0)] * 20
        for i in range(30):
            frames.append(('tip', (i + 1) / 30))
        frames += [('lying', 1.0)] * 45
    elif name == 'fall_then_up':                 # falls, then gets back up after ~1 s
        frames += [('stand', 0.0)] * 20
        for i in range(10):
            frames.append(('tip', (i + 1) / 10))
        frames += [('lying', 1.0)] * 15
        for i in range(10):
            frames.append(('tip', 1 - (i + 1) / 10))
        frames += [('stand', 0.0)] * 20
    elif name == 'fall_recover':                 # falls, lies ~2 s (event fires), then gets up
        frames += [('stand', 0.0)] * 20
        for i in range(10):
            frames.append(('tip', (i + 1) / 10))
        frames += [('lying', 1.0)] * 30
        for i in range(10):
            frames.append(('tip', 1 - (i + 1) / 10))
        frames += [('stand', 0.0)] * 30
    elif name == 'intentional_lie':              # deliberate, slow lie-down; NOT a fall
        frames += [('stand', 0.0)] * 20
        for i in range(30):
            frames.append(('tip', (i + 1) / 30))
        frames += [('lying', 1.0)] * 45
    elif name == 'long_lie':                     # lies still for ~10 s (tests background absorption)
        frames += [('stand', 0.0)] * 20
        for i in range(10):
            frames.append(('tip', (i + 1) / 10))
        frames += [('lying', 1.0)] * 150
    else:
        raise ValueError(name)
    return frames


def _draw(frame_kind, param, scale: float = 1.0) -> np.ndarray:
    img = np.full((H, W, 3), BG, np.uint8)
    if frame_kind == 'tip':
        w0, h0 = 30, 90
        w1, h1 = 90, 30
        w = int(w0 + (w1 - w0) * param); h = int(h0 + (h1 - h0) * param)
        cx, bottom = 160, GROUND_Y
    elif frame_kind == 'lying':
        w, h, bottom, cx = 90, 30, GROUND_Y, 160
    else:
        w, h, bottom, cx = _pose(frame_kind, param)
    w = max(1, int(round(w * scale))); h = max(1, int(round(h * scale)))
    x0 = cx - w // 2
    y0 = bottom - h
    cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), (PERSON, PERSON, PERSON), -1)
    return img


def make_clip(name: str, path: str, seed: int = 0, warmup_frames: int = 60, scale: float = 1.0) -> str:
    rng = np.random.default_rng(seed)
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), FPS, (W, H))
    if not writer.isOpened():
        raise IOError(f"Cannot write {path}")
    try:
        for _ in range(warmup_frames):
            bg = np.full((H, W, 3), BG, np.uint8)
            noise = rng.integers(-3, 4, size=bg.shape, dtype=np.int16)
            writer.write(np.clip(bg.astype(np.int16) + noise, 0, 255).astype(np.uint8))
        for kind, param in _scenario_frames(name):
            frame = _draw(kind, param, scale)
            noise = rng.integers(-3, 4, size=frame.shape, dtype=np.int16)
            writer.write(np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8))
    finally:
        writer.release()
    return path


SCENARIOS = {'fall': 1, 'slow_fall': 1, 'fall_then_up': 1, 'long_lie': 1,
             'sit_down': 0, 'bend': 0, 'walk': 0}


def make_suite(outdir: str, seed: int = 0) -> List[Tuple[str, int]]:
    """Create one clip per scenario and return [(path, label)]. Label 1 = fall."""
    os.makedirs(outdir, exist_ok=True)
    out = []
    for i, (name, label) in enumerate(SCENARIOS.items()):
        path = os.path.join(outdir, f"synthetic_{name}.mp4")
        make_clip(name, path, seed=seed + i)
        out.append((path, label))
    return out
