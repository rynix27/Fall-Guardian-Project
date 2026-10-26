"""
Evidence provider: lets the agent examine a defined time window of video
after a candidate event (additional analysis, not a new detection).
"""
from typing import List, Optional

from vision.fall_vision import FrameReading, VisionFallDetector


class VideoEvidence:
    """Runs the vision pipeline once over a clip and serves time windows from it."""

    def __init__(self, path: str, detector: Optional[VisionFallDetector] = None):
        self.path = path
        _, self._trace = (detector or VisionFallDetector()).process_video(path, keep_trace=True)

    def window_after(self, t_s: float, seconds: float) -> List[FrameReading]:
        return [r for r in self._trace if t_s < r.t_s <= t_s + seconds]
