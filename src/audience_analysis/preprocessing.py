"""The same detector, RGB conversion and normalization serve offline and desktop paths."""
from collections import deque
from pathlib import Path
import cv2
import numpy as np

from .legacy_contracts import PipelineConfig, SequenceBatch, Status


class FacePreprocessor:
    def __init__(self, config: PipelineConfig):
        self.config = config
        detector_path = Path(__file__).parent / "assets" / "face_detection_yunet_2023mar.onnx"
        self.detector = cv2.FaceDetectorYN.create(str(detector_path), "", (320, 320), 0.8, 0.3, 5000)

    def process(self, bgr):
        height, width = bgr.shape[:2]
        scale = 320/max(height, width)
        resized = cv2.resize(bgr, (max(1, round(width*scale)), max(1, round(height*scale))))
        padded = np.zeros((320, 320, 3), np.uint8)
        padded[:resized.shape[0], :resized.shape[1]] = resized
        _, faces = self.detector.detect(padded)
        boxes = [] if faces is None else np.rint(faces[:, :4]/scale).astype(int)
        return self.crop(bgr, boxes)

    def crop(self, bgr, boxes):
        boxes = [tuple(map(int, box)) for box in boxes]
        if not boxes:
            return Status.NO_FACE, None, boxes
        if len(boxes) != 1:
            return Status.AMBIGUOUS, None, boxes
        x, y, w, h = boxes[0]
        if min(w, h) < self.config.min_face_pixels:
            return Status.LOW_QUALITY, None, boxes
        margin = int(max(w, h) * self.config.crop_margin)
        height, width = bgr.shape[:2]
        crop = bgr[max(0, y-margin):min(height, y+h+margin), max(0, x-margin):min(width, x+w+margin)]
        if crop.size == 0:
            return Status.LOW_QUALITY, None, boxes
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (self.config.image_size, self.config.image_size), interpolation=cv2.INTER_AREA)
        return Status.READY, rgb, boxes


def normalize(frames):
    data = frames.astype(np.float32) / 255.0
    data = (data - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
    return np.ascontiguousarray(data.transpose(0, 3, 1, 2))


class SequenceBuilder:
    def __init__(self, config, source_id, participant_id):
        self.config = config
        self.source_id = source_id
        self.participant_id = participant_id
        self.generation = 0
        self.history = deque()
        self.last_seen = None
        self.last_emitted = None
        # At most about 2T crops per source, regardless of camera FPS.
        self.sample_period = config.window_seconds / (2 * (config.frames - 1))

    def reset(self):
        self.history.clear()
        self.last_seen = None
        self.last_emitted = None
        self.generation += 1

    def add(self, timestamp, rgb, status=Status.READY):
        if not np.isfinite(timestamp):
            self.reset()
            return None
        if self.last_seen is not None and (timestamp <= self.last_seen or timestamp - self.last_seen > self.config.max_gap_seconds):
            self.reset()
        if status != Status.READY or rgb is None:
            self.reset()
            return None
        self.last_seen = timestamp
        if self.history and timestamp - self.history[-1][0] < self.sample_period - 1e-8:
            return None
        self.history.append((timestamp, rgb))
        cutoff = timestamp - self.config.window_seconds
        # Keep one sample at or before the start, needed for nearest-time sampling.
        while len(self.history) > 1 and self.history[1][0] <= cutoff:
            self.history.popleft()
        # A nominal 10 s clip's last frame precedes 10.0 s. Permit one sampling
        # interval at the boundary; always report the actual observed interval.
        if timestamp - self.history[0][0] < self.config.window_seconds - self.sample_period - 1e-8:
            return None
        if self.last_emitted is not None and timestamp - self.last_emitted < self.config.stride_seconds - 1e-8:
            return None
        times = np.array([sample[0] for sample in self.history])
        targets = np.linspace(max(cutoff, self.history[0][0]), timestamp, self.config.frames)
        indices = np.abs(times[:, None] - targets[None, :]).argmin(axis=0)
        if len(set(indices)) != self.config.frames:
            return None
        if np.max(np.abs(times[indices] - targets)) > self.config.max_gap_seconds:
            return None
        self.last_emitted = timestamp
        frames = np.stack([self.history[i][1] for i in indices])
        return SequenceBatch(self.source_id, self.participant_id, self.generation, float(times[indices[0]]), float(times[indices[-1]]), frames)

