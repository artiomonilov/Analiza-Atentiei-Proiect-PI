import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from audience_analysis.legacy_contracts import PipelineConfig
from audience_analysis.experiment import train, evaluate, write_json
from audience_analysis.models import EngagementModel


class ExperimentTests(unittest.TestCase):
    def test_training_export_and_evaluation_with_synthetic_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = PipelineConfig(image_size=32, frames=4)
            rows = []
            rng = np.random.default_rng(7)
            for split in ("train", "validation"):
                for target in range(4):
                    name = f"{split}_{target}.npz"
                    np.savez_compressed(root/name, frames=rng.integers(0, 256, (4, 32, 32, 3), dtype=np.uint8))
                    rows.append({"clip_id": name, "participant_id": name, "split": split, "engagement": target,
                                 "accepted": True, "file": name, "start": 0, "end": 10, "rejections": {}})
            write_json(root/"index.json", {"pipeline": config.to_dict(), "manifest_sha256": "synthetic-unit-test",
                                         "unit": "synthetic test fixture", "rows": rows})
            for architecture in ("mean", "gru"):
                model_path = root/f"{architecture}.pt"
                args = argparse.Namespace(cache=str(root), architecture=architecture, output=str(model_path),
                    epochs=1, seed=42, batch_size=2, lr=0.01, class_weights=True, threads=1)
                # No network or ImageNet download in the test. Production train uses pretrained=True.
                with patch("audience_analysis.models.EngagementModel", side_effect=lambda arch, pretrained: EngagementModel(arch, pretrained=False)):
                    train(args)
                report_path = root/f"{architecture}-evaluation.json"
                evaluate(argparse.Namespace(cache=str(root), model=str(model_path), split="validation", output=str(report_path), threads=1))
                report = json.loads(report_path.read_text())
                self.assertEqual(report["coverage"], 1)
                self.assertEqual(report["accepted"], 4)
                self.assertTrue(report["reference_verified"])
                self.assertEqual(report["R0_same_accepted_subset"]["accuracy"], 0.25)
                self.assertEqual(report["metrics_on_accepted_only"]["support"], [1, 1, 1, 1])


if __name__ == "__main__":
    unittest.main()
