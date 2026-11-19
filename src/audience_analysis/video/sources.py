import math
import re
import threading
import time
from pathlib import Path

import numpy as np

from ..contracts import FramePacket, SourceConfig
from ..video_processor import FrameClock


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
    live = False  # are sfârșit; timpul vine din numărul cadrului

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
        except BaseException:
            self.close()
            raise
        self.fps = fps
        def metadata_count(prop):
            value = float(self._capture.get(prop))
            return int(value) if math.isfinite(value) and value > 0 else 0
        self.width = metadata_count(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = metadata_count(cv2.CAP_PROP_FRAME_HEIGHT)
        self.frame_count = metadata_count(cv2.CAP_PROP_FRAME_COUNT)
        self.duration_s = self.frame_count / fps if self.frame_count > 0 and math.isfinite(fps) and fps > 0 else None
        self.is_image = path.suffix.lower() in IMAGE_SUFFIXES or self.frame_count == 1
        self._next_id = 0
        self._clock = FrameClock(webcam=False, source_fps=fps, start=time.monotonic())
        self.timestamp_source = "unspecified"

    def read(self) -> tuple[int, float, np.ndarray] | None:
        """Citește următorul cadru."""
        ok, image = self._capture.read()
        if not ok or image is None:
            return None
        if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Cadrul citit nu este BGR uint8")
        frame_id = self._next_id
        self._next_id += 1
        timestamp, self.timestamp_source = self._clock.next(frame_id, float(self._capture.get(self._cv_position_property())), time.monotonic())
        return frame_id, timestamp / 1000, image

    @staticmethod
    def _cv_position_property():
        import cv2
        return cv2.CAP_PROP_POS_MSEC

    def close(self) -> None:
        """Eliberează fișierul (cv2.VideoCapture.release). Se apelează mereu la final, și după erori."""
        self._capture.release()


LIVE_URL = re.compile(r"^(rtsps?|https?|rtmp|udp|tcp)://", re.IGNORECASE)
_LIVE_OWNERS = set()
_LIVE_OWNER_LOCK = threading.Lock()


def redact(location: str) -> str:
    """Adresa fără parolă și fără parametri (?token=...), ca să poată apărea în mesaje fără să scape secrete."""
    location = re.sub(r"(://[^:/@\s]+):[^@/\s]*@", r"\1:***@", location)
    return location.split("?", 1)[0] + ("?…" if "?" in location else "")


def resolve_source(config: SourceConfig) -> tuple[str, str]:
    """Decide tipul real al sursei: "file", "camera" sau "network".

    Formularul din UI trimite orice text ca "file", așa că recunoaștem aici:
    număr (0, 1 ...) sau /dev/videoN -> cameră; rtsp://, http(s):// ... -> flux de rețea.
    """
    kind, location = config.kind, config.location.strip()
    if kind == "file":
        if LIVE_URL.match(location):
            return "network", location
        if location.isdigit() or re.fullmatch(r"/dev/video\d+", location):
            return "camera", location
    return kind, location


def _open_capture(location: str, kind: str, open_timeout_s: float, read_timeout_s: float):
    """Deschide cv2.VideoCapture pentru cameră sau rețea, cu limite de timp unde OpenCV le suportă."""
    import cv2
    if kind == "camera":
        capture = cv2.VideoCapture(int(location) if location.isdigit() else location)

        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        capture.set(cv2.CAP_PROP_FPS, 30)
    else:
        params = []
        for name, seconds in (("CAP_PROP_OPEN_TIMEOUT_MSEC", open_timeout_s), ("CAP_PROP_READ_TIMEOUT_MSEC", read_timeout_s)):
            prop = getattr(cv2, name, None)  # disponibile în OpenCV >= 4.6 (backend FFmpeg)
            if prop is not None:
                params += [prop, int(seconds * 1000)]
        capture = cv2.VideoCapture(location, cv2.CAP_FFMPEG, params)
    try:
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # cât mai puține cadre vechi în tamponul backendului
    except Exception:
        pass
    return capture


class LiveSource:
    """Cameră locală sau flux de rețea. Un fir intern citește continuu și păstrează doar cel mai nou cadru,
    ca analiza să nu rămână în urmă când procesarea e mai lentă decât camera."""
    live = True       # nu are sfârșit; se oprește doar la stop sau la pierderea conexiunii
    is_image = False

    def __init__(self, location: str, *, kind: str, clock_origin: float | None = None,
                 open_timeout_s: float = 5.0, read_timeout_s: float = 5.0, capture_factory=None):
        if kind not in {"camera", "network"}:
            raise ValueError("Tip de sursă live invalid")
        self.kind, self.name = kind, (f"camera {location}" if kind == "camera" else redact(location))
        self._lease_key = (kind, location)
        with _LIVE_OWNER_LOCK:
            if self._lease_key in _LIVE_OWNERS or len(_LIVE_OWNERS) >= 16:
                raise ConnectionError("Captura este încă ocupată sau bugetul live a fost atins")
            _LIVE_OWNERS.add(self._lease_key)
        self.read_timeout_s = read_timeout_s
        self._origin = time.monotonic() if clock_origin is None else clock_origin  # timpul 0 al sursei
        try:
            self._capture = (capture_factory or _open_capture)(location, kind, open_timeout_s, read_timeout_s)
            if not self._capture.isOpened():
                self._capture.release()
                raise ConnectionError(f"Nu se poate deschide {self.name}")
        except BaseException:
            with _LIVE_OWNER_LOCK:
                _LIVE_OWNERS.discard(self._lease_key)
            raise
        self._condition = threading.Condition()
        self._latest: tuple[float, np.ndarray] | None = None
        self._received = self._delivered = 0  # câte cadre au venit / câte au fost date mai departe
        self._failed = self._closing = False
        self._next_id = 0
        self.timestamp_source = "webcam_monotonic" if kind == "camera" else "network_monotonic"
        self._clock = FrameClock(webcam=True, source_fps=0, start=self._origin)
        self._thread = threading.Thread(target=self._grab, name=f"captura {self.name}", daemon=True)
        try:
            self._thread.start()
        except BaseException:
            self._capture.release()
            with _LIVE_OWNER_LOCK:
                _LIVE_OWNERS.discard(self._lease_key)
            raise

    def _grab(self) -> None:
        """Firul de captură: citește cât de repede vin cadrele; fiecare cadru nou îl înlocuiește pe cel vechi."""
        try:
            while not self._closing:
                try:
                    ok, image = self._capture.read()
                except Exception:
                    ok, image = False, None
                if self._closing:
                    return
                valid = ok and image is not None and image.dtype == np.uint8 and image.ndim == 3 and image.shape[2] == 3
                with self._condition:
                    if not valid:
                        self._failed = True
                        self._condition.notify_all()
                        return
                    self._latest = (time.monotonic(), image)
                    self._received += 1
                    self._condition.notify_all()
        finally:
            try:
                self._capture.release()  # numai firul proprietar eliberează captura
            finally:
                with _LIVE_OWNER_LOCK:
                    _LIVE_OWNERS.discard(self._lease_key)

    def read(self, stop_event: threading.Event | None = None) -> tuple[int, float, np.ndarray] | None:
        """Cel mai nou cadru nevăzut; None dacă s-a cerut oprirea. ConnectionError dacă sursa nu mai trimite."""
        deadline = time.monotonic() + self.read_timeout_s
        with self._condition:
            while self._received == self._delivered:
                if self._failed:
                    raise ConnectionError(f"Conexiunea cu {self.name} s-a pierdut")
                if stop_event is not None and stop_event.is_set():
                    return None
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ConnectionError(f"{self.name} nu a mai trimis cadre de {self.read_timeout_s:g} s")
                self._condition.wait(min(remaining, 0.1))
            captured_at, image = self._latest
            self._delivered = self._received
        frame_id = self._next_id
        self._next_id += 1
        timestamp, origin = self._clock.next(frame_id, 0, captured_at)
        self.timestamp_source = origin.replace("webcam", "network") if self.kind == "network" else origin
        return frame_id, timestamp / 1000, image

    def close(self) -> None:
        """Oprește firul de captură și eliberează camera/fluxul."""
        self._closing = True
        with self._condition:
            self._condition.notify_all()
        self._thread.join(timeout=self.read_timeout_s + 1)
        if self._thread.is_alive():
            raise TimeoutError("Backendul de captură încă citește; captura rămâne rezervată până la eliberare")
        # Altfel firul e încă blocat în backend; nu eliberăm captura sub el (OpenCV poate crăpa).
        # Firul e daemon și se termină singur la expirarea limitei de citire.


def open_real_source(config: SourceConfig, *, clock_origin: float | None = None) -> FileSource | LiveSource:
    """Alege adaptorul pentru o sursă reală (P2-S3.1, P2-S5.1)."""
    kind, location = resolve_source(config)
    if kind == "file":
        return FileSource(location)
    return LiveSource(location, kind=kind, clock_origin=clock_origin)
