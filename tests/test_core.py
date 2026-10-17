import csv
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from audience_analysis.legacy_contracts import PipelineConfig, PredictionResult, SourceConfig, Status
from audience_analysis.dataset import read_manifest, audit_manifest
from audience_analysis.metrics import classification_metrics
from audience_analysis.preprocessing import FacePreprocessor, SequenceBuilder, normalize
from audience_analysis.reporting import SessionLog


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.config = PipelineConfig(window_seconds=2, frames=4, stride_seconds=1, image_size=32, max_gap_seconds=0.6)
        self.frame = np.zeros((32, 32, 3), np.uint8)
        self.builder = SequenceBuilder(self.config, "P01", "P01")

    def test_time_sampling_and_stride(self):
        results = [self.builder.add(i/10, self.frame) for i in range(41)]
        results = [r for r in results if r is not None]
        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0].frames.shape, (4, 32, 32, 3))
        self.assertGreaterEqual(results[0].end-results[0].start, 2-self.builder.sample_period)
        self.assertGreaterEqual(results[1].end-results[0].end, 1)
        self.assertLessEqual(len(self.builder.history), 9)

    def test_invalid_frame_clears_continuity(self):
        for i in range(18):
            self.builder.add(i/10, self.frame)
        generation = self.builder.generation
        self.builder.add(1.8, None, Status.NO_FACE)
        self.assertGreater(self.builder.generation, generation)
        self.assertIsNone(self.builder.add(1.9, self.frame))
        self.assertEqual(len(self.builder.history), 1)

    def test_seek_and_gap_reset(self):
        self.builder.add(0, self.frame)
        self.builder.add(0.4, self.frame)
        self.builder.add(2, self.frame)
        self.assertEqual(len(self.builder.history), 1)
        self.builder.add(0, self.frame)
        self.assertEqual(self.builder.generation, 2)

    def test_nominal_ten_second_clip(self):
        builder = SequenceBuilder(PipelineConfig(image_size=32), "P01", "P01")
        results = [builder.add(i/8, self.frame) for i in range(80)]
        self.assertTrue(any(result is not None for result in results))


class PreprocessingTests(unittest.TestCase):
    def test_rejects_missing_ambiguous_and_small_faces(self):
        processor = FacePreprocessor(PipelineConfig(image_size=32))
        frame = np.zeros((100, 100, 3), np.uint8)
        self.assertEqual(processor.crop(frame, [])[0], Status.NO_FACE)
        self.assertEqual(processor.crop(frame, [(0, 0, 50, 50)]*2)[0], Status.AMBIGUOUS)
        self.assertEqual(processor.crop(frame, [(0, 0, 20, 20)])[0], Status.LOW_QUALITY)

    def test_bgr_to_rgb_and_normalization(self):
        processor = FacePreprocessor(PipelineConfig(image_size=32))
        frame = np.zeros((100, 100, 3), np.uint8)
        frame[:, :, 2] = 255
        status, crop, _ = processor.crop(frame, [(0, 0, 80, 80)])
        self.assertEqual(status, Status.READY)
        self.assertEqual(crop[0, 0].tolist(), [255, 0, 0])
        normalized = normalize(crop[None])
        self.assertAlmostEqual(float(normalized[0, 0, 0, 0]), (1-0.485)/0.229, places=5)


class ReportingTests(unittest.TestCase):
    def setUp(self):
        source = SourceConfig("P01", "network", "rtsp://user:SECRET@host/stream?token=TOKEN", "P01")
        self.session = SessionLog("Experiment", [source], PipelineConfig())
        self.session.invalidate("P01", 2)

    def test_late_results_and_old_generations_rejected(self):
        self.assertFalse(self.session.append(PredictionResult("P01", "P01", 1, 0, 10, Status.READY, 2)))
        self.assertTrue(self.session.append(PredictionResult("P01", "P01", 2, 0, 12, Status.READY, 2)))
        self.assertFalse(self.session.append(PredictionResult("P01", "P01", 2, 0, 10, Status.READY, 1)))

    def test_export_has_null_not_zero_and_no_source_credentials(self):
        self.session.append(PredictionResult("P01", "P01", 2, 0, 0, Status.NO_FACE))
        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory)/"session.json"
            self.session.export(json_path)
            self.session.export(Path(directory)/"session.csv")
            raw = json_path.read_text(encoding="utf-8")
            self.assertNotIn("SECRET", raw)
            self.assertNotIn("TOKEN", raw)
            self.assertNotIn("rtsp", raw)
            self.assertIsNone(json.loads(raw)["records"][0]["label"])
            with (Path(directory)/"session.csv").open(encoding="utf-8-sig") as handle:
                row = next(csv.DictReader(handle))
                self.assertEqual(row["label"], "")
                self.assertEqual(row["status"], "NO_FACE")


class DatasetTests(unittest.TestCase):
    def test_participant_leakage_and_invalid_label(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"manifest.csv"
            header = "clip_id,participant_id,path,split,engagement\n"
            path.write_text(header+"a,p,a.mp4,train,0\nb,p,b.mp4,test,1\n")
            with self.assertRaisesRegex(ValueError, "Participant"):
                read_manifest(path)
            path.write_text(header+"a,p,a.mp4,train,\n")
            with self.assertRaisesRegex(ValueError, "Etichetă"):
                read_manifest(path)

    def test_content_duplicate_and_missing_file_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"a.mp4").write_bytes(b"same video")
            (root/"b.mp4").write_bytes(b"same video")
            path = root/"manifest.csv"
            path.write_text("clip_id,participant_id,path,split,engagement\na,p,a.mp4,train,0\nb,q,b.mp4,test,1\nc,r,c.mp4,validation,2\n")
            report = audit_manifest(path)
            self.assertEqual(report["duplicate_content"], [["a", "b"]])
            self.assertEqual(report["missing_files"], ["c"])


class MetricTests(unittest.TestCase):
    def test_known_confusion_matrix(self):
        result = classification_metrics([0, 0, 1, 1, 2, 3], [0, 1, 1, 1, 2, 3])
        self.assertAlmostEqual(result["accuracy"], 5/6)
        self.assertAlmostEqual(result["balanced_accuracy"], 0.875)
        self.assertAlmostEqual(result["macro_f1"], (2/3+0.8+1+1)/4)


if __name__ == "__main__":
    unittest.main()
