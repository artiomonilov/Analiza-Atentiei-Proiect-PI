import numpy as np
import pytest

from audience_analysis.contracts import SourceConfig
from audience_analysis.video.preprocessing import prepare_bgr, detect_real_face
from audience_analysis.video.sequences import SequenceBuilder
from audience_analysis.video.sources import synthetic_frame, open_real_source


def test_bgr_rgb_normalized_once(config):
    image = np.zeros((10, 10, 3), np.uint8)
    image[:, :, 2] = 255
    prepared = prepare_bgr(image, config)
    assert prepared.dtype == np.float32
    assert prepared.shape == (3, config.height, config.width)
    assert np.all(prepared[0] == 1)
    assert np.all(prepared[2] == 0)


def test_temporal_selection_and_run_reset(config):
    builder = SequenceBuilder(config, demo=True)
    results = []
    for i in range(30):
        packet = synthetic_frame("P01", "run1", i, i/20)
        assert packet.face_boxes == ()
        result = builder.add(packet)
        if result is not None:
            results.append(result)
    assert results
    first_copy = results[0].frames.copy()
    assert len(builder.history) <= 128
    assert len(set(results[0].sample_times_s)) == config.frames
    builder.add(synthetic_frame("P01", "run2", 0, 0))
    assert len(builder.history) == 1
    assert np.array_equal(first_copy, results[0].frames)


def test_real_adapters_are_explicit(config):
    with pytest.raises(NotImplementedError):
        open_real_source(SourceConfig("P01", "Clip", "file", "not-opened.mp4"))
    with pytest.raises(NotImplementedError):
        detect_real_face(np.zeros((10, 10, 3), np.uint8))
    with pytest.raises(NotImplementedError):
        SequenceBuilder(config, demo=False)
