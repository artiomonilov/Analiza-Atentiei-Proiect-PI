
from collections import deque
from threading import Condition

from ..contracts import InferenceRequest, PredictionResult


class LatestScheduler:
    """O cerere în așteptare per (sursă, față); toate operațiile compuse folosesc aceeași încuietoare."""

    def __init__(self):
        self.condition = Condition()
        self.queues: dict[str, dict[int | None, InferenceRequest]] = {}
        self.runs: dict[str, str] = {}
        self.last_submitted: dict[str, int] = {}
        self.outstanding: dict[str, set[int]] = {}  # cereri trimise, neînlocuite, încă fără rezultat
        self.order: deque[str] = deque()
        self.replaced: dict[str, int] = {}
        self.closed = False

    def activate(self, source_id: str, run_id: str) -> None:
        """Pregătește o sursă pentru o rulare nouă: golește coada ei și reține run_id."""
        with self.condition:
            if self.closed:
                raise RuntimeError("Motorul este închis")
            if source_id not in self.queues:
                self.order.append(source_id)
            self.queues[source_id] = {}
            self.runs[source_id] = run_id
            self.last_submitted[source_id] = -1
            self.outstanding[source_id] = set()
            self.replaced.setdefault(source_id, 0)

    def deactivate(self, source_id: str) -> None:
        """Scoate sursa: șterge cererile ei în așteptare și contoarele. Cererile care sosesc după sunt refuzate."""
        with self.condition:
            self.queues.pop(source_id, None)
            self.runs.pop(source_id, None)
            self.last_submitted.pop(source_id, None)
            self.outstanding.pop(source_id, None)
            if source_id in self.order:
                self.order.remove(source_id)

    def submit(self, request: InferenceRequest) -> bool:
        """Pune o cerere în coadă; dacă fața are deja o cerere în așteptare, o înlocuiește."""
        with self.condition:
            source_id = request.source_id
            if self.closed or self.runs.get(source_id) != request.run_id:
                return False
            if request.request_id <= self.last_submitted[source_id]:
                return False
            mailbox = self.queues[source_id]
            old = mailbox.pop(request.track_id, None)  # pop + inserare la final: fața ajunge ultima la rând
            if old is not None:
                self.replaced[source_id] += 1
                self.outstanding[source_id].discard(old.request_id)
            mailbox[request.track_id] = request
            self.last_submitted[source_id] = request.request_id
            self.outstanding[source_id].add(request.request_id)
            self.condition.notify()
            return True

    def take(self, *, block: bool = True) -> InferenceRequest | None:
        """Scoate următoarea cerere pentru model: sursele pe rând, iar în sursă fața care așteaptă de mai mult timp."""
        with self.condition:
            while not self.closed:
                for _ in range(len(self.order)):  # sursele pe rând, ca niciuna să nu fie favorizată
                    source_id = self.order[0]
                    self.order.rotate(-1)
                    mailbox = self.queues[source_id]
                    if mailbox:
                        return mailbox.pop(next(iter(mailbox)))  # fața care așteaptă de cel mai mult
                if not block:
                    return None
                self.condition.wait()
            return None

    def complete(self, source_id: str, request_id: int) -> None:
        """Marchează cererea ca terminată; chemat de controller când sosește rezultatul ei."""
        with self.condition:
            self.outstanding.get(source_id, set()).discard(request_id)

    def has_outstanding(self, source_id: str) -> bool:
        """True dacă sursa mai are cereri trimise (neînlocuite) care încă nu au primit rezultat."""
        with self.condition:
            return bool(self.outstanding.get(source_id))

    def last_submitted_id(self, source_id: str) -> int:
        """request_id-ul ultimei cereri acceptate pentru sursă, sau -1."""
        with self.condition:
            return self.last_submitted.get(source_id, -1)

    def replaced_counts(self) -> dict[str, int]:
        """Câte cereri au fost înlocuite înainte de model, per sursă (cumulat de la pornirea motorului)."""
        with self.condition:
            return dict(self.replaced)

    def pending_counts(self) -> dict[str, int]:
        """Câte cereri așteaptă acum, per sursă (pentru teste și diagnoză)."""
        with self.condition:
            return {source: len(mailbox) for source, mailbox in self.queues.items()}

    def close(self) -> None:
        """Închide schedulerul: golește tot și trezește firul AI, care iese din take()."""
        with self.condition:
            self.closed = True
            self.queues.clear()
            self.runs.clear()
            self.outstanding.clear()
            self.order.clear()
            self.condition.notify_all()


class ResultGate:
    """Filtrul rezultatelor; folosit numai în firul controllerului. Ordinea se verifică separat pentru fiecare față."""

    def __init__(self):
        self.runs: dict[str, str] = {}
        self.accepted: dict[tuple[str, int | None], int] = {}

    def activate(self, source_id: str, run_id: str) -> None:
        """Începe o rulare nouă pentru sursă și uită rezultatele acceptate anterior."""
        self.invalidate(source_id)
        self.runs[source_id] = run_id

    def invalidate(self, source_id: str) -> None:
        """Oprește acceptarea rezultatelor pentru sursă (oprire, eroare, sfârșit)."""
        self.runs.pop(source_id, None)
        for key in [key for key in self.accepted if key[0] == source_id]:
            del self.accepted[key]

    def accept(self, result: PredictionResult) -> bool:
        """Decide dacă un rezultat ajunge în UI."""
        key = (result.source_id, result.track_id)
        if self.runs.get(result.source_id) != result.run_id or result.request_id <= self.accepted.get(key, -1):
            return False
        self.accepted[key] = result.request_id
        return True
