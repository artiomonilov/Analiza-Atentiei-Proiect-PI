import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import queue
import tempfile
import time
import unittest

import cv2
import numpy as np

from audience_analysis.legacy_contracts import PipelineConfig, PredictionResult, SourceConfig, Status
from audience_analysis.runtime import CaptureHandle, InferenceWorker


def make_clip(path, seconds=0.5):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (96, 96))
    if not writer.isOpened():
        raise RuntimeError("MJPG indisponibil în mediul de test")
    for _ in range(int(seconds*10)):
        writer.write(np.zeros((96, 96, 3), np.uint8))
    writer.release()


class CaptureTests(unittest.TestCase):
    def test_no_face_end_of_file_and_source_release(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"blank.avi"
            make_clip(path)
            handle = CaptureHandle(SourceConfig("P01", "file", str(path), "P01"), PipelineConfig())
            statuses = []
            try:
                deadline = time.monotonic()+15
                while time.monotonic() < deadline:
                    try:
                        packet = handle.output.get(timeout=0.2)
                        statuses.append(packet["status"])
                        self.assertIsNone(packet["batch"])
                        if packet["status"] == Status.ENDED:
                            break
                    except queue.Empty:
                        pass
                self.assertIn(Status.NO_FACE, statuses)
                self.assertIn(Status.ENDED, statuses)
            finally:
                handle.stop()
                deadline = time.monotonic()+5
                while not handle.reap() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertFalse(handle.process.is_alive())
                handle.close()

    def test_unavailable_file_reports_disconnected(self):
        handle = CaptureHandle(SourceConfig("P01", "file", "missing-file.avi", "P01"), PipelineConfig())
        try:
            packet = handle.output.get(timeout=15)
            self.assertEqual(packet["status"], Status.DISCONNECTED)
        finally:
            handle.stop()
            deadline = time.monotonic()+5
            while not handle.reap() and time.monotonic() < deadline:
                time.sleep(0.05)
            handle.close()


class DesktopTests(unittest.TestCase):
    def test_old_media_result_is_not_counted_as_evaluable(self):
        from audience_analysis.qt import QtWidgets
        from audience_analysis.legacy_ui import MainWindow
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        window = MainWindow()
        window.timer.stop()
        window.sources = [SourceConfig("P01", "file", "not-opened.avi", "P01")]
        window.rebuild_cards()
        result = PredictionResult("P01", "P01", 0, 0, 10, Status.READY, 2)
        window.latest_prediction["P01"] = (result, time.monotonic())
        window.last_arrival["P01"] = time.monotonic()
        window.latest_time["P01"] = 20
        window.poll()
        self.assertIn("0 evaluabile", window.summary.text())
        window.latest_time["P01"] = 10
        window.poll()
        self.assertIn("1 evaluabile", window.summary.text())
        window.close()
        app.processEvents()

    def test_four_source_session_and_export(self):
        from audience_analysis.qt import QtWidgets
        from audience_analysis.legacy_ui import MainWindow
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        window = MainWindow()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"blank.avi"
            make_clip(path)
            window.sources = [SourceConfig(f"P{i}", "file", str(path), f"P{i}") for i in range(4)]
            window.rebuild_cards()
            window.start_session()
            deadline = time.monotonic()+20
            while (window.worker or window.handles) and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.02)
            try:
                self.assertFalse(window.handles)
                self.assertIsNone(window.worker)
                self.assertEqual(len(window.cards), 4)
                ended = {r.source_id for r in window.session.records if r.status == Status.ENDED}
                self.assertEqual(len(ended), 4)
                self.assertTrue(all(r.label is None for r in window.session.records))
                window.session.export(Path(directory)/"report.json")
                self.assertTrue(window.start_button.isEnabled())
            finally:
                window.close()
                app.processEvents()


if __name__ == "__main__":
    unittest.main()
