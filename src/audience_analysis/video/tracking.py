
from dataclasses import dataclass

Box = tuple[int, int, int, int]


def iou(a: Box, b: Box) -> float:
    """Intersection over Union: aria comună / aria reunită a două casete."""
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    ix = max(0, min(ax0 + aw, bx0 + bw) - max(ax0, bx0))
    iy = max(0, min(ay0 + ah, by0 + bh) - max(ay0, by0))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


@dataclass
class _Track:
    """Starea internă a unei fețe urmărite: ultima casetă (box) și ultimul moment în care a fost văzută (last_seen_s)."""
    box: Box
    last_seen_s: float


class FaceTracker:
    """Asociere greedy după IoU între casetele cadrului curent și ultimele casete ale fiecărei urmăriri."""

    def __init__(self, *, iou_threshold: float = 0.3, max_missed_s: float = 0.5):
        if not 0 < iou_threshold <= 1 or max_missed_s < 0:
            raise ValueError("Parametri de urmărire invalizi")
        self.iou_threshold, self.max_missed_s = iou_threshold, max_missed_s
        self.tracks: dict[int, _Track] = {}
        self._next_id = 0

    def reset(self) -> list[int]:
        """Uită toate fețele. Întoarce lista track_id-urilor încheiate."""
        ended = list(self.tracks)
        self.tracks.clear()
        return ended

    def update(self, boxes, media_time_s: float) -> tuple[tuple[int, ...], list[int]]:
        """Actualizează urmăririle cu casetele unui cadru nou."""
        boxes = [tuple(int(v) for v in box) for box in boxes]
        # toate perechile (suprapunere, față veche, casetă nouă), de la cea mai mare suprapunere
        pairs = sorted(((iou(track.box, box), track_id, index)
                        for track_id, track in self.tracks.items() for index, box in enumerate(boxes)), reverse=True)
        assigned: dict[int, int] = {}  # index casetă -> față veche
        used_tracks: set[int] = set()
        for score, track_id, index in pairs:
            if score < self.iou_threshold:
                break
            if track_id in used_tracks or index in assigned:
                continue
            assigned[index] = track_id
            used_tracks.add(track_id)
        ids = []  # casetele nepotrivite primesc un număr nou
        for index, box in enumerate(boxes):
            track_id = assigned.get(index)
            if track_id is None:
                track_id = self._next_id
                self._next_id += 1
            self.tracks[track_id] = _Track(box, media_time_s)
            ids.append(track_id)
        # fețele care lipsesc de prea mult timp se încheie
        ended = [track_id for track_id, track in self.tracks.items()
                 if track_id not in ids and media_time_s - track.last_seen_s > self.max_missed_s]
        for track_id in ended:
            del self.tracks[track_id]
        return tuple(ids), ended
