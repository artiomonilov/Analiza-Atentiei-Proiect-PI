import numpy as np

from ..config import SequenceConfig


def prepare_bgr(image: np.ndarray, config: SequenceConfig) -> np.ndarray:
    """Pregătește un decupaj BGR o singură dată; redimensionare nearest în NumPy."""
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 1:
        raise ValueError("Decupajul trebuie să fie BGR uint8")
    rows = np.linspace(0, image.shape[0]-1, config.height).astype(int)
    columns = np.linspace(0, image.shape[1]-1, config.width).astype(int)
    rgb = image[rows[:, None], columns[None, :], ::-1].astype(np.float32)
    rgb *= config.scale
    rgb = (rgb - np.asarray(config.mean, np.float32)) / np.asarray(config.std, np.float32)
    return np.ascontiguousarray(rgb.transpose(2, 0, 1))


def detect_real_face(image: np.ndarray):
    # TODO P2-S3.1: intrare BGR; adaptează detectorul existent și decupează fața;
    # ieșire casete ale aceluiași cadru + crop valid sau stare explicită;
    # verificare: 0/1/mai multe fețe, fără alegere arbitrară.
    raise NotImplementedError("P2-S3.1: detecția feței reale nu este activă în demo")
