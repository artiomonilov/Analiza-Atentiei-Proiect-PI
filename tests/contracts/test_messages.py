from dataclasses import replace

import numpy as np
import pytest

from audience_analysis.config import SequenceConfig, validate_sequence
from audience_analysis.contracts import FramePacket, ModelOutput, PredictionResult, SourceConfig, Status


def test_identifiers_and_counters(make_request):
    with pytest.raises(ValueError):
        SourceConfig("bad id", "Participant", "demo")
    with pytest.raises(ValueError):
        replace(make_request(), request_id=-1)
    with pytest.raises(ValueError):
        replace(make_request(), run_id="")
    with pytest.raises(ValueError):
        replace(make_request(), window_end_s=0.1)


def test_sequence_shape_config_and_snapshot(sequence, config):
    validate_sequence(sequence, config)
    with pytest.raises(ValueError):
        replace(sequence, frames=sequence.frames.astype(np.float64))
    with pytest.raises(ValueError):
        replace(sequence, sample_times_s=(0.0,)*4)
    with pytest.raises(ValueError):
        validate_sequence(sequence, SequenceConfig(width=100))
    with pytest.raises(ValueError):
        sequence.frames[0, 0, 0, 0] = 1


def test_frame_snapshot_and_matching_boxes():
    image = np.zeros((20, 20, 3), np.uint8)
    packet = FramePacket("P01", "run1", 0, 0, image, ((1, 1, 5, 5),))
    image[:] = 255
    assert not packet.image.any()
    with pytest.raises(ValueError):
        replace(packet, face_boxes=((0, 0, 25, 25),))


@pytest.mark.parametrize("level", [-1, 4, True, 2.0])
def test_levels_reject_invalid_values(level):
    with pytest.raises(ValueError):
        ModelOutput({"engagement": level}, "v1", True)


def test_errors_cannot_have_levels():
    with pytest.raises(ValueError):
        PredictionResult("P01", "run1", 0, 0, 1, Status.ERROR, {"engagement": 0}, "v1", True, 0, 0)
