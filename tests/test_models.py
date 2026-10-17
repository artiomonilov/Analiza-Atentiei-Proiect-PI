from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

from audience_analysis.legacy_contracts import PipelineConfig, SequenceBatch
from audience_analysis.models import EngagementModel, Predictor, save_bundle


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_real_optimizer_step_both_architectures_and_frozen_encoder(self):
        for architecture in ("mean", "gru"):
            model = EngagementModel(architecture, pretrained=False).train()
            self.assertFalse(model.encoder.training)
            before = model.classifier.weight.detach().clone()
            optimizer = torch.optim.Adam(model.classifier.parameters(), lr=0.01)
            frames = torch.randn(2, 4, 3, 32, 32)
            logits = model(frames)
            loss = torch.nn.functional.cross_entropy(logits, torch.tensor([0, 3]))
            loss.backward()
            optimizer.step()
            self.assertEqual(logits.shape, (2, 4))
            self.assertFalse(torch.equal(before, model.classifier.weight))
            self.assertTrue(all(p.grad is None for p in model.encoder.parameters()))

    def test_bundle_parity_and_shape_validation(self):
        config = PipelineConfig(image_size=32, frames=4)
        frames = np.random.default_rng(1).integers(0, 256, (4, 32, 32, 3), dtype=np.uint8)
        model = EngagementModel(pretrained=False).eval()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"test-only.pt"
            # Technical fixture only; never shipped or claimed as an engagement model.
            save_bundle(path, model, config, {"trained": True, "purpose": "unit-test fixture"}, frames)
            predictor = Predictor(path)
            self.assertTrue(predictor.reference_verified)
            batch = SequenceBatch("P01", "P01", 0, 0, 10, frames)
            result = predictor.predict(batch)
            self.assertEqual(len(result.scores), 4)
            self.assertAlmostEqual(sum(result.scores), 1, places=5)
            batch.frames = frames[:2]
            with self.assertRaises(ValueError):
                predictor.predict(batch)

    def test_export_rejects_untrained_marker(self):
        with self.assertRaises(ValueError):
            save_bundle("unused.pt", EngagementModel(), PipelineConfig(), {"trained": False})


if __name__ == "__main__":
    unittest.main()
