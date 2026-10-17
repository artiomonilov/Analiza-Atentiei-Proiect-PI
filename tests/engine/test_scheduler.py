from audience_analysis.contracts import PredictionResult, Status
from audience_analysis.engine.scheduler import LatestScheduler, ResultGate
from audience_analysis.engine.workers import PreviewStore
from audience_analysis.video.sources import synthetic_frame


def test_pending_replacement_and_inflight_preserved(make_request):
    scheduler = LatestScheduler()
    scheduler.activate("P01", "run1")
    scheduler.submit(make_request(number=0))
    inflight = scheduler.take(block=False)
    scheduler.submit(make_request(number=1))
    scheduler.submit(make_request(number=2))
    assert inflight.request_id == 0
    assert scheduler.pending_counts() == {"P01": 1}
    assert scheduler.replaced["P01"] == 1
    assert scheduler.take(block=False).request_id == 2
    assert scheduler.take(block=False) is None
    scheduler.close()
    assert scheduler.take() is None


def test_two_sources_alternate_and_keep_identity(make_request):
    scheduler = LatestScheduler()
    for source in ("P01", "P02"):
        scheduler.activate(source, "run1")
        scheduler.submit(make_request(source))
    assert scheduler.take(block=False).source_id == "P01"
    scheduler.submit(make_request("P01", number=1))
    assert scheduler.take(block=False).source_id == "P02"
    assert scheduler.take(block=False).source_id == "P01"


def test_gate_accepts_inflight_and_rejects_old_runs():
    gate = ResultGate()
    gate.activate("P01", "run1")
    result = PredictionResult("P01", "run1", 0, 0, 1, Status.OK, {"engagement": 2}, "v1", True, 0, 0)
    assert gate.accept(result)
    assert not gate.accept(result)
    gate.invalidate("P01")
    gate.activate("P01", "run2")
    assert not gate.accept(result)


def test_reset_clears_pending_and_preview(make_request):
    scheduler = LatestScheduler()
    scheduler.activate("P01", "run1")
    scheduler.submit(make_request())
    scheduler.deactivate("P01")
    scheduler.activate("P01", "run2")
    assert not scheduler.submit(make_request())
    assert scheduler.take(block=False) is None
    previews = PreviewStore()
    previews.activate("P01", "run1")
    for i in range(100):
        previews.put(synthetic_frame("P01", "run1", i, i/20))
    assert len(previews.frames) == 1
    assert previews.take("P01").frame_id == 99
    previews.invalidate("P01")
    previews.put(synthetic_frame("P01", "run1", 100, 5))
    assert previews.take("P01") is None
