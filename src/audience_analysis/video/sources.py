import numpy as np

from ..contracts import FramePacket


def synthetic_frame(source_id: str, run_id: str, frame_id: int, media_time_s: float) -> FramePacket:
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    image[:, :, 0] = 35
    x = frame_id % 48
    image[16:32, x:x+16] = (80, 180, 240)
    return FramePacket(source_id, run_id, frame_id, media_time_s, image, ())


def open_real_source(config):
    # TODO P2-S3.1/P2-S5.1: intrare SourceConfig real; adaptează captura existentă
    # la worker cooperativ; ieșire FramePacket cu media_time_s verificat;
    # teste: fișier autorizat, EOF, stop, apoi cameră/rețea documentate.
    raise NotImplementedError("P2-S3/P2-S5: sursele reale nu sunt activate în mini-template")
