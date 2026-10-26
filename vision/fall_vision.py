"""
Fall Guardian - OpenCV 5 vision pipeline (PROTOTYPE, rule-based).

Method
------
1. Each frame is downscaled to a fixed width and passed to OpenCV's MOG2
   background subtractor, which separates moving foreground from background.
2. Foreground is cleaned with a morphological opening, and the largest
   contour above a minimum area is taken as the person.
3. From that contour we compute the bounding-box aspect ratio (height / width)
   and the vertical centroid position (normalized to frame height).
4. A small state machine flags a fall when the person goes from upright
   (tall box) to lying (wide box) within a short window, the centroid moves
   downward by a minimum fraction of the frame, and the lying posture is held
   for a minimum time.

Limitations (see TECHNICAL REPORT)
----------------------------------
* Rules and thresholds were set by hand. They have not been fitted to real data.
* MOG2 eventually absorbs a motionless object into the background. A person who
  lies still for a long time may stop being detected. The learning rate limits
  how fast this happens but does not remove it.
* Only one person is expected in view. Several people, cameras that move, and
  poor lighting are not handled.
* Output is a candidate event for human review, not a diagnosis.
"""

from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np

STATE_NO_PERSON = 'NO_PERSON'
STATE_UPRIGHT = 'UPRIGHT'
STATE_LYING_CANDIDATE = 'LYING_CANDIDATE'
STATE_FALL_EVENT = 'FALL_EVENT'
STATE_OTHER = 'OTHER_POSTURE'
STATE_WARMUP = 'WARMUP'


@dataclass
class FrameReading:
    frame_idx: int
    t_s: float
    box: Optional[Tuple[int, int, int, int]]
    aspect: Optional[float]
    cy_norm: Optional[float]
    state: str


@dataclass
class FallEvent:
    frame_idx: int
    t_s: float
    rule: str
    aspect_before: float
    aspect_after: float
    centroid_drop: float   # fraction of standing body height
    hold_s: float

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['t_s'] = round(d['t_s'], 3)
        for k in ('aspect_before', 'aspect_after', 'centroid_drop', 'hold_s'):
            d[k] = round(d[k], 3)
        return d


@dataclass
class VisionConfig:
    width: int = 320                 # frames are resized to this width
    min_area: int = 600              # px at the working resolution
    upright_aspect: float = 1.2      # h/w at or above this = standing
    lying_aspect: float = 0.9        # h/w at or below this = lying
    drop_fraction: float = 0.25      # centroid must fall by this fraction of standing body height
    transition_window_s: float = 1.0 # upright -> lying must happen within this time
    hold_s: float = 1.5              # lying must persist this long to emit an event
    learning_rate: float = 0.002     # MOG2 background learning rate
    history: int = 120               # MOG2 history frames
    warmup_frames: int = 30          # frames used only to learn the background
    lying_grace_s: float = 0.5       # brief aspect jumps within a lying episode do not end it ...
    grace_cy_tol: float = 0.03      # ... provided the centroid stays this low (fraction of frame height)


class VisionFallDetector:
    def __init__(self, config: Optional[VisionConfig] = None):
        self.cfg = config or VisionConfig()
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=self.cfg.history, varThreshold=16, detectShadows=False)
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self._history: Deque[Tuple[float, float]] = deque()  # (t, cy_norm)
        self._last_upright_t: Optional[float] = None
        self._last_upright_cy: Optional[float] = None
        self._last_upright_h: Optional[float] = None
        self._lying_since: Optional[float] = None
        self._lying_pre_cy: Optional[float] = None
        self._lying_aspect_before: Optional[float] = None
        self._last_lying_t: Optional[float] = None
        self._episode_low_cy: Optional[float] = None
        self._episode_max_drop: float = 0.0
        self._event_emitted = False
        self._state = STATE_NO_PERSON
        self._frames_seen = 0
        self._last_upright_aspect: Optional[float] = None

    def reset(self):
        self.__init__(self.cfg)

    # ----------------------------------------------------------- per frame
    def _segment(self, frame_bgr) -> Optional[Tuple[Tuple[int, int, int, int], float]]:
        h0, w0 = frame_bgr.shape[:2]
        scale = self.cfg.width / float(w0)
        small = cv2.resize(frame_bgr, (self.cfg.width, int(h0 * scale)), interpolation=cv2.INTER_AREA)
        fg = self._subtractor.apply(small, learningRate=self.cfg.learning_rate)
        fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)[1]
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, self._kernel)
        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < self.cfg.min_area:
            return None
        x, y, w, h = cv2.boundingRect(largest)
        return (x, y, w, h), float(small.shape[0])

    def process_frame(self, frame_bgr, frame_idx: int, t_s: float) -> Tuple[FrameReading, Optional[FallEvent]]:
        seg = self._segment(frame_bgr)
        self._frames_seen += 1
        if self._frames_seen <= self.cfg.warmup_frames:
            # MOG2 has no background model yet and flags most of the frame as
            # foreground. Learn the background; do not report anything.
            self._set_state(STATE_WARMUP)
            return FrameReading(frame_idx, t_s, None, None, None, self._state), None
        if seg is None:
            self._set_state(STATE_NO_PERSON)
            self._lying_since = None
            return FrameReading(frame_idx, t_s, None, None, None, self._state), None

        (x, y, w, h), frame_h = seg
        aspect = h / float(w)
        cy = (y + h / 2.0) / frame_h
        self._history.append((t_s, cy))
        while self._history and t_s - self._history[0][0] > self.cfg.transition_window_s:
            self._history.popleft()

        event = None
        lying_now = aspect <= self.cfg.lying_aspect
        in_episode = self._lying_since is not None

        # Grace: inside a lying episode, a brief aspect jump (e.g. background
        # absorption) does not end the episode if the centroid stays low.
        in_grace = (
            not lying_now and in_episode and aspect < self.cfg.upright_aspect
            and self._last_lying_t is not None
            and t_s - self._last_lying_t <= self.cfg.lying_grace_s
            and self._episode_low_cy is not None
            and cy >= self._episode_low_cy - self.cfg.grace_cy_tol
        )

        if aspect >= self.cfg.upright_aspect:
            self._set_state(STATE_UPRIGHT)
            self._last_upright_t = t_s
            self._last_upright_cy = cy
            self._last_upright_aspect = aspect
            self._last_upright_h = h / frame_h
            self._lying_since = None
            self._last_lying_t = None
            self._episode_low_cy = None
            self._episode_max_drop = 0.0
            self._event_emitted = False
        elif lying_now or in_grace:
            if not in_episode:
                # Candidate transition only if we were upright shortly before.
                if self._last_upright_t is not None and \
                   t_s - self._last_upright_t <= self.cfg.transition_window_s:
                    self._lying_since = t_s
                    self._lying_pre_cy = self._last_upright_cy
                    self._lying_aspect_before = self._last_upright_aspect
                    self._episode_low_cy = cy
                    self._episode_max_drop = 0.0
                    self._set_state(STATE_LYING_CANDIDATE)
                else:
                    self._set_state(STATE_OTHER)
            if lying_now:
                self._last_lying_t = t_s
            if self._lying_since is not None:
                self._set_state(STATE_LYING_CANDIDATE)
                self._episode_low_cy = max(self._episode_low_cy or cy, cy)
                body_h = self._last_upright_h or 0.3
                drop_now = (cy - (self._lying_pre_cy if self._lying_pre_cy is not None else cy)) / body_h
                # Latch: keep the largest drop seen in this episode, so a small
                # rise while the person starts to get up cannot cancel it.
                self._episode_max_drop = max(self._episode_max_drop, drop_now)
                hold = t_s - self._lying_since
                if (hold >= self.cfg.hold_s and self._episode_max_drop >= self.cfg.drop_fraction
                        and not self._event_emitted):
                    self._event_emitted = True
                    self._set_state(STATE_FALL_EVENT)
                    event = FallEvent(
                        frame_idx=frame_idx, t_s=t_s,
                        rule='upright->lying within window, centroid dropped, lying held',
                        aspect_before=self._lying_aspect_before or 0.0,
                        aspect_after=aspect,
                        centroid_drop=self._episode_max_drop, hold_s=hold)
        else:
            self._set_state(STATE_OTHER)

        return FrameReading(frame_idx, t_s, (x, y, w, h), aspect, cy, self._state), event

    def _set_state(self, s):
        self._state = s

    # ----------------------------------------------------------- whole video
    def process_video(self, path: str, keep_trace: bool = False):
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise IOError(f"Cannot open video: {path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
        events: List[FallEvent] = []
        trace: List[FrameReading] = []
        idx = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                reading, event = self.process_frame(frame, idx, idx / fps)
                if keep_trace:
                    trace.append(reading)
                if event:
                    events.append(event)
                idx += 1
        finally:
            cap.release()
        if idx == 0:
            # A file that opens but decodes no frames must not look like 'no falls'.
            raise IOError(f"No frames could be decoded from: {path}")
        return events, trace
