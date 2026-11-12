"""P2 — Surse video: de unde vin cadrele.

Conține:
    synthetic_frame(...)   -> FramePacket   cadru artificial pentru demo (fără persoane)
    IMAGE_SUFFIXES                           extensiile tratate ca poze (imagine statică)
    FileSource                               citește un fișier video (sau o poză) cadru cu cadru (OpenCV)
    open_real_source(cfg)  -> FileSource     alege adaptorul potrivit pentru o SourceConfig reală

Convenții:
    - Imaginile sunt BGR uint8 [H, W, 3] (formatul OpenCV).
    - media_time_s = momentul cadrului în video, în secunde (nu ceasul calculatorului).
    - cv2 se importă doar când e nevoie, ca modulul să meargă și fără OpenCV.
"""
import math
from pathlib import Path

import numpy as np

from ..contracts import FramePacket, SourceConfig


def synthetic_frame(source_id: str, run_id: str, frame_id: int, media_time_s: float) -> FramePacket:
    """Creează un cadru sintetic 64x48: fundal albastru închis + un pătrat care se mișcă orizontal."""
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    image[:, :, 0] = 35
    x = frame_id % 48
    image[16:32, x:x+16] = (80, 180, 240)
    return FramePacket(source_id, run_id, frame_id, media_time_s, image, ())


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}  # deschise de OpenCV ca 1 cadru


class FileSource:
    """Citește un fișier video cadru cu cadru; se apelează numai din firul lucrătorului (SourceWorker)."""

    def __init__(self, path: str | Path):
        import cv2  # import leneș: modulul rămâne importabil fără OpenCV
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError("Fișierul video nu există")
        self._capture = cv2.VideoCapture(str(path))
        try:
            if not self._capture.isOpened():
                raise OSError("Fișierul video nu poate fi deschis")
            fps = float(self._capture.get(cv2.CAP_PROP_FPS))
            if not math.isfinite(fps) or not 1.0 <= fps <= 240.0:
                raise ValueError("FPS invalid în fișierul video")
        except BaseException:
            self.close()
            raise
        self.fps = fps
        self.width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.frame_count = int(self._capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration_s = self.frame_count / fps if self.frame_count > 0 else None
        self.is_image = path.suffix.lower() in IMAGE_SUFFIXES or self.frame_count == 1
        self._next_id = 0

    def read(self) -> tuple[int, float, np.ndarray] | None:
        """Citește următorul cadru."""
        ok, image = self._capture.read()
        if not ok or image is None:
            return None
        if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Cadrul citit nu este BGR uint8")
        frame_id = self._next_id
        self._next_id += 1
        return frame_id, frame_id / self.fps, image

    def close(self) -> None:
        """Eliberează fișierul (cv2.VideoCapture.release). Se apelează mereu la final, și după erori."""
        self._capture.release()


def open_real_source(config: SourceConfig) -> FileSource:
    """Alege adaptorul pentru o sursă reală (P2-S3.1)."""
    if config.kind == "file":
        return FileSource(config.location)
    raise NotImplementedError("P2-S5.1: camera și fluxul de rețea nu sunt activate încă")