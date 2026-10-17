"""Bounded per-source capture processes and one inference worker.

Process isolation lets Stop release even a camera backend blocked in read().
Qt only polls small bounded mailboxes; workers never access widgets.
"""
from collections import OrderedDict
from dataclasses import dataclass
import multiprocessing as mp
import os
import queue
import threading
import time

# Bound native BLAS thread pools before spawning the per-source processes.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import cv2

from .legacy_contracts import PredictionResult, Status
from .preprocessing import FacePreprocessor, SequenceBuilder


def put_latest(mailbox, value):
    try:
        mailbox.put_nowait(value)
        return
    except queue.Full:
        pass
    try:
        mailbox.get_nowait()
    except queue.Empty:
        pass
    try:
        mailbox.put_nowait(value)
    except queue.Full:
        pass  # A racing consumer/producer may replace this preview on the next frame.


def capture_source(source, config, output, stop):
    capture = None
    builder = SequenceBuilder(config, source.source_id, source.participant_id)
    last_time = 0.0
    try:
        cv2.setNumThreads(1)
        preprocessor = FacePreprocessor(config)
        location = int(source.location) if source.kind == "camera" else source.location
        if source.kind == "network":
            capture = cv2.VideoCapture(location, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 2000])
        else:
            capture = cv2.VideoCapture(location)
        if not capture.isOpened():
            raise OSError("Sursă indisponibilă")
        fps = capture.get(cv2.CAP_PROP_FPS)
        if source.kind == "file" and not (0 < fps <= 1000):
            raise ValueError("FPS necunoscut; cronologia fișierului nu poate fi stabilită")
        anchor = time.monotonic()
        index = 0
        last_preview = -1.0
        last_media = -1.0
        while not stop.is_set():
            ok, bgr = capture.read()
            if not ok:
                terminal = Status.ENDED if source.kind == "file" else Status.DISCONNECTED
                break
            if source.kind == "file":
                reported = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                last_time = reported if reported > last_media else index/fps
                if last_time < last_media:
                    builder.reset()
                    anchor = time.monotonic() - last_time
                if stop.wait(max(0, anchor + last_time - time.monotonic())):
                    terminal = Status.STOPPED
                    break
                last_media = last_time
            else:
                last_time = time.monotonic() - anchor
            index += 1
            # Decode every frame, but detect at <= 8 Hz. Sampling remains time-based.
            if last_time - last_preview < 0.125:
                continue
            last_preview = last_time
            status, rgb, boxes = preprocessor.process(bgr)
            batch = builder.add(last_time, rgb, status)
            display = bgr.copy()
            for x, y, w, h in boxes:
                cv2.rectangle(display, (x, y), (x+w, y+h), (100, 200, 70), 2)
            scale = min(1, 640/display.shape[1])
            display = cv2.resize(display, None, fx=scale, fy=scale)
            put_latest(output, {"generation": builder.generation, "timestamp": last_time,
                       "status": status if status != Status.READY else Status.COLLECTING,
                       "frame": display, "batch": batch})
        else:
            terminal = Status.STOPPED
    except OSError:
        # Backend errors may contain credentials; never send raw exception strings.
        terminal = Status.DISCONNECTED
    except Exception:
        terminal = Status.ERROR
    finally:
        if capture is not None:
            capture.release()
        builder.reset()
        # Final event must survive a full preview queue; GUI drains it regularly.
        final = {"generation": builder.generation, "timestamp": last_time, "status": terminal, "frame": None, "batch": None}
        while True:
            try:
                output.put(final, timeout=0.2)
                break
            except queue.Full:
                if stop.is_set():
                    break


class CaptureHandle:
    def __init__(self, source, config):
        context = mp.get_context("spawn")
        self.source = source
        self.output = context.Queue(maxsize=2)
        self.stop_event = context.Event()
        self.process = context.Process(target=capture_source, args=(source, config, self.output, self.stop_event), daemon=True)
        self.stop_requested_at = None
        self.process.start()

    def stop(self):
        self.stop_event.set()
        self.stop_requested_at = time.monotonic()

    def reap(self):
        if self.process.is_alive() and self.stop_requested_at is not None and time.monotonic() - self.stop_requested_at > 2.5:
            self.process.terminate()
        if self.process.is_alive():
            return False
        self.process.join(timeout=0)
        return True

    def close(self):
        self.output.cancel_join_thread()
        self.output.close()
        self.process.close()


class InferenceWorker:
    def __init__(self, model_path=None):
        self.condition = threading.Condition()
        self.pending = OrderedDict()
        self.output = queue.Queue(maxsize=32)
        self.closed = False
        self.state = "loading" if model_path else "ready"
        self.predictor = None
        self.error = None
        self.replaced = 0
        self.model_path = model_path
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def submit(self, batch):
        with self.condition:
            if batch.source_id in self.pending:
                self.replaced += 1
            self.pending[batch.source_id] = batch
            self.condition.notify()

    def run(self):
        if self.model_path:
            try:
                from .models import Predictor
                self.predictor = Predictor(self.model_path)
                self.state = "ready"
            except Exception:
                self.error = "Model incompatibil, corupt sau dependențe ML indisponibile."
                self.state = "error"
                return
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.closed or bool(self.pending))
                if self.closed:
                    return
                _, batch = self.pending.popitem(last=False)
            try:
                if self.predictor:
                    result = self.predictor.predict(batch)
                else:
                    result = PredictionResult(batch.source_id, batch.participant_id, batch.generation, batch.start, batch.end, Status.NO_MODEL)
            except Exception:
                result = PredictionResult(batch.source_id, batch.participant_id, batch.generation, batch.start, batch.end, Status.ERROR)
            put_latest(self.output, result)

    def stop(self):
        with self.condition:
            self.closed = True
            self.pending.clear()
            self.condition.notify_all()
