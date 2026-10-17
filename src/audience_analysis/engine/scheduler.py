from collections import deque
from queue import Empty, Full, Queue
from threading import Condition

from ..contracts import InferenceRequest, PredictionResult


class LatestScheduler:
    """O coadă de capacitate 1/sursă; toate operațiile compuse folosesc aceeași încuietoare."""

    def __init__(self):
        self.condition = Condition()
        self.queues: dict[str, Queue] = {}
        self.runs: dict[str, str] = {}
        self.last_submitted: dict[str, int] = {}
        self.order: deque[str] = deque()
        self.replaced: dict[str, int] = {}
        self.closed = False

    def activate(self, source_id: str, run_id: str) -> None:
        with self.condition:
            if self.closed:
                raise RuntimeError("Motorul este închis")
            if source_id not in self.queues:
                self.order.append(source_id)
            self.queues[source_id] = Queue(maxsize=1)
            self.runs[source_id] = run_id
            self.last_submitted[source_id] = -1
            self.replaced.setdefault(source_id, 0)

    def deactivate(self, source_id: str) -> None:
        with self.condition:
            self.queues.pop(source_id, None)
            self.runs.pop(source_id, None)
            self.last_submitted.pop(source_id, None)
            if source_id in self.order:
                self.order.remove(source_id)

    def submit(self, request: InferenceRequest) -> bool:
        with self.condition:
            source_id = request.source_id
            if self.closed or self.runs.get(source_id) != request.run_id:
                return False
            if request.request_id <= self.last_submitted[source_id]:
                return False
            mailbox = self.queues[source_id]
            try:
                mailbox.put_nowait(request)
            except Full:
                mailbox.get_nowait()  # producătorul și consumatorul dețin aceeași încuietoare
                self.replaced[source_id] += 1
                mailbox.put_nowait(request)
            self.last_submitted[source_id] = request.request_id
            self.condition.notify()
            return True

    def take(self, *, block: bool = True) -> InferenceRequest | None:
        with self.condition:
            while not self.closed:
                for _ in range(len(self.order)):
                    source_id = self.order[0]
                    self.order.rotate(-1)
                    try:
                        return self.queues[source_id].get_nowait()
                    except Empty:
                        continue
                if not block:
                    return None
                self.condition.wait()
            return None

    def pending_counts(self) -> dict[str, int]:
        with self.condition:
            return {source: mailbox.qsize() for source, mailbox in self.queues.items()}

    def close(self) -> None:
        with self.condition:
            self.closed = True
            self.queues.clear()
            self.runs.clear()
            self.order.clear()
            self.condition.notify_all()


class ResultGate:
    """Folosit numai în firul controllerului. Nu compară cu cea mai nouă cerere formată."""

    def __init__(self):
        self.runs: dict[str, str] = {}
        self.accepted: dict[str, int] = {}

    def activate(self, source_id: str, run_id: str) -> None:
        self.runs[source_id] = run_id
        self.accepted[source_id] = -1

    def invalidate(self, source_id: str) -> None:
        self.runs.pop(source_id, None)
        self.accepted.pop(source_id, None)

    def accept(self, result: PredictionResult) -> bool:
        if (self.runs.get(result.source_id) != result.run_id
                or result.request_id <= self.accepted.get(result.source_id, -1)):
            return False
        self.accepted[result.source_id] = result.request_id
        return True
