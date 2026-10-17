from collections import deque

import numpy as np

from ..config import SequenceConfig
from ..contracts import FramePacket, PreparedSequence
from .preprocessing import prepare_bgr


class SequenceBuilder:
    """Istoric separat de coada AI; în demo se pregătește întregul cadru sintetic."""

    def __init__(self, config: SequenceConfig, *, demo: bool, max_frames: int = 128):
        if not demo:
            raise NotImplementedError("P2-S3.1: selectează decupajul real înainte de pregătire")
        if max_frames < config.frames:
            raise ValueError("Istoric mai mic decât secvența")
        self.config = config
        self.history: deque[FramePacket] = deque(maxlen=max_frames)
        self.last_window_end: float | None = None

    def clear(self) -> None:
        self.history.clear()
        self.last_window_end = None

    def add(self, packet: FramePacket) -> PreparedSequence | None:
        if self.history:
            previous = self.history[-1]
            if (packet.run_id != previous.run_id or packet.source_id != previous.source_id
                    or packet.media_time_s <= previous.media_time_s):
                self.clear()
        self.history.append(packet)
        end = packet.media_time_s
        start = end - self.config.window_seconds
        while len(self.history) > 1 and self.history[1].media_time_s < start:
            self.history.popleft()
        if len(self.history) < self.config.frames or self.history[0].media_time_s > start + 1e-8:
            return None
        if self.last_window_end is not None and end - self.last_window_end < self.config.stride_seconds - 1e-8:
            return None
        times = np.array([p.media_time_s for p in self.history])
        targets = np.linspace(start, end, self.config.frames)
        indices = np.abs(times[:, None] - targets).argmin(axis=0)
        if len(set(indices)) != self.config.frames or np.max(np.abs(times[indices] - targets)) > self.config.sample_tolerance_s:
            return None
        frames = np.stack([prepare_bgr(self.history[i].image, self.config) for i in indices])
        self.last_window_end = end
        return PreparedSequence(frames, tuple(float(t) for t in times[indices]), self.config.preprocessing_id)
