"""Geometrie sintetică: niciun model AI nu este folosit în aceste teste."""
from dataclasses import replace
from types import SimpleNamespace as NS

import numpy as np
import pytest

from audience_analysis.eye_features import (
    LEFT_EAR, LEFT_EYE, LEFT_IRIS, RIGHT_EAR, RIGHT_EYE, RIGHT_IRIS,
    EyeFeaturesEstimator, draw_eye_features, eye_aspect_ratio,
)
from audience_analysis.face_landmarker import FaceLandmarks, Landmark
from audience_analysis.vision import MediaPipeHeadPose


SIZE = (800, 400)


def face_fixture(dx=0, dy=0, lid_height=30):
    points = [Landmark(.5, .5, 0) for _ in range(478)]
    for side, center_x, contour, six, iris in (
        ("left", 600, LEFT_EYE, LEFT_EAR, LEFT_IRIS),
        ("right", 200, RIGHT_EYE, RIGHT_EAR, RIGHT_IRIS),
    ):
        def put(index, x, y):
            points[index] = Landmark((center_x + x) / SIZE[0], (200 + y) / SIZE[1], 0)
        for j, index in enumerate(contour):
            a = j * 2 * np.pi / len(contour)
            if side == "right":
                a = np.pi - a
            put(index, 50 * np.cos(a), lid_height / 2 * np.sin(a))
        six_coordinates = [(-50, 0), (-25, -lid_height / 2), (25, -lid_height / 2),
                           (50, 0), (25, lid_height / 2), (-25, lid_height / 2)]
        for index, (x, y) in zip(six, six_coordinates):
            put(index, x, y)
        for index, (x, y) in zip(iris, [(10, 0), (0, 10), (-10, 0), (0, -10)]):
            put(index, x + dx, y + dy)
    return FaceLandmarks(tuple(points), (), np.eye(4))


def test_ear_and_centered_iris_in_non_square_image():
    result = EyeFeaturesEstimator().estimate(face_fixture(), SIZE)
    for eye in (result.left, result.right):
        assert eye.ear == pytest.approx(.3)
        assert eye.iris_position == pytest.approx((.5, .5))
        assert eye.gaze_delta is None
    assert result.left.iris_center == pytest.approx((.75, .5))
    assert result.right.iris_center == pytest.approx((.25, .5))
    assert result.left.subject_side == "left"  # dreapta imaginii nemirorate


def test_iris_shift_and_neutral_calibration():
    estimator = EyeFeaturesEstimator()
    estimator.calibrate(face_fixture(), SIZE)
    result = estimator.estimate(face_fixture(dx=20, dy=3), SIZE)
    for eye in (result.left, result.right):
        assert eye.iris_position == pytest.approx((.7, .6))
        assert eye.gaze_delta == pytest.approx((.2, .1))
        assert eye.ear_relative == pytest.approx(1)
    estimator.clear_calibration()
    assert estimator.estimate(face_fixture(), SIZE).left.gaze_delta is None


def test_individual_calibration_can_select_one_eye():
    estimator = EyeFeaturesEstimator()
    estimator.calibrate(face_fixture(), SIZE, sides=("left",))
    result = estimator.estimate(face_fixture(), SIZE)
    assert result.left.ear_relative == pytest.approx(1)
    assert result.right.ear_relative is None
    with pytest.raises(ValueError):
        estimator.calibrate(None, SIZE)
    assert estimator.estimate(face_fixture(), SIZE).left.ear_relative == pytest.approx(1)


def test_resolution_invariance_and_local_roll():
    face = face_fixture(dx=10, dy=2)
    estimator = EyeFeaturesEstimator()
    before = estimator.estimate(face, SIZE)
    resized = estimator.estimate(face, (1600, 800))
    assert resized.left.ear == pytest.approx(before.left.ear)
    assert resized.left.iris_position == pytest.approx(before.left.iris_position)
    points = list(face.landmarks)
    a = np.deg2rad(35)
    rotation = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    for center, contour, iris in [(np.array([600, 200]), LEFT_EYE, LEFT_IRIS),
                                   (np.array([200, 200]), RIGHT_EYE, RIGHT_IRIS)]:
        for index in set(contour + iris):
            xy = rotation @ (np.array([points[index].x, points[index].y]) * SIZE - center) + center
            points[index] = Landmark(*(xy / SIZE), 0)
    after = estimator.estimate(replace(face, landmarks=tuple(points)), SIZE)
    assert after.left.ear == pytest.approx(before.left.ear)
    assert after.left.iris_position == pytest.approx(before.left.iris_position)


def test_missing_iris_keeps_ear():
    face = replace(face_fixture(), landmarks=face_fixture().landmarks[:468])
    result = EyeFeaturesEstimator().estimate(face, SIZE)
    assert result.left.ear == pytest.approx(.3)
    assert result.right.ear == pytest.approx(.3)
    assert result.left.iris_position is None
    assert result.right.reason


@pytest.mark.parametrize("face", [None, FaceLandmarks((), (), None)])
def test_no_face_or_incomplete_landmarks(face):
    result = EyeFeaturesEstimator().estimate(face, SIZE)
    assert result.left.ear is result.right.ear is None
    assert result.left.iris_position is result.right.iris_position is None


@pytest.mark.parametrize("bad_xy", [(float("nan"), .5), (float("inf"), .5), (-.1, .5), (.5, 1.1)])
def test_invalid_or_partially_visible_eye_does_not_invalidate_other_eye(bad_xy):
    face = face_fixture()
    points = list(face.landmarks)
    points[33] = Landmark(*bad_xy, 0)
    result = EyeFeaturesEstimator().estimate(replace(face, landmarks=tuple(points)), SIZE)
    assert result.right.ear is None
    assert result.left.ear == pytest.approx(.3)


def test_closed_eye_and_partial_aperture():
    closed = EyeFeaturesEstimator().estimate(face_fixture(lid_height=0), SIZE)
    assert closed.left.ear == pytest.approx(0)
    assert closed.left.iris_position is None
    # Ochi parțial închis, cu EAR numeric, dar iris sub limita individuală.
    estimator = EyeFeaturesEstimator(min_open_ratio=.7)
    estimator.calibrate(face_fixture(), SIZE)
    partial = estimator.estimate(face_fixture(lid_height=15), SIZE)
    assert partial.left.ear == pytest.approx(.15)
    assert partial.left.ear_relative == pytest.approx(.5)
    assert partial.left.iris_position is None
    # Fără calibrare, acest prag nu decide clipiri sau starea ochiului.
    assert EyeFeaturesEstimator().estimate(face_fixture(lid_height=15), SIZE).left.iris_position is not None


def test_iris_outside_eye_or_collapsed_ring():
    result = EyeFeaturesEstimator().estimate(face_fixture(dy=40), SIZE)
    assert result.left.ear is not None and result.left.iris_position is None
    face = face_fixture()
    points = list(face.landmarks)
    for index in LEFT_IRIS:
        points[index] = Landmark(.75, .5, 0)
    assert EyeFeaturesEstimator().estimate(replace(face, landmarks=tuple(points)), SIZE).left.iris_center is None


def test_caller_supplied_occlusion():
    result = EyeFeaturesEstimator().estimate(face_fixture(), SIZE, occluded_eyes=("left",))
    assert result.left.ear is None
    assert result.right.ear is not None


@pytest.mark.parametrize("size", [(0, 10), (10, -1), (float("nan"), 10), (10,)])
def test_invalid_image_size(size):
    with pytest.raises(ValueError):
        EyeFeaturesEstimator().estimate(face_fixture(), size)


def test_degenerate_ear():
    with pytest.raises(ValueError):
        eye_aspect_ratio(np.zeros((6, 2)))


def test_vision_geometry_uses_one_existing_inference():
    calls = []
    adapter = MediaPipeHeadPose(None)
    adapter.landmarker = NS(process=lambda frame: (calls.append(frame), NS(faces=[face_fixture()]))[1])
    result = adapter.geometry(np.zeros((400, 800, 3), np.uint8))
    assert len(calls) == 1
    assert result.head_pose.valid
    assert result.eyes.left.iris_position == pytest.approx((.5, .5))


def test_eye_overlay_preserves_original_and_saves(tmp_path):
    pytest.importorskip("cv2")
    from audience_analysis.face_landmarker import load_image, save_image
    image = np.zeros((400, 800, 3), np.uint8)
    output = draw_eye_features(image, EyeFeaturesEstimator().estimate(face_fixture(), SIZE))
    assert output.any() and not image.any()
    path = tmp_path / "eyes.png"
    save_image(path, output)
    np.testing.assert_array_equal(load_image(path), output)


def test_photo_script_reuses_model_for_neutral_and_current(monkeypatch, tmp_path, capsys):
    import runpy
    from pathlib import Path
    pytest.importorskip("cv2")
    import audience_analysis.face_landmarker as module
    counters = {"init": 0, "process": 0, "close": 0}

    class FakeLandmarker:
        def __init__(self, _model):
            counters["init"] += 1

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            counters["close"] += 1

        def process(self, _image):
            counters["process"] += 1
            return module.LandmarkerResult((face_fixture(),))

    monkeypatch.setattr(module, "FaceLandmarker", FakeLandmarker)
    source = tmp_path / "input.png"
    output = tmp_path / "annotated.png"
    module.save_image(source, np.zeros((400, 800, 3), np.uint8))
    main = runpy.run_path(str(Path(__file__).resolve().parents[2] / "test_face_landmarker.py"))["main"]
    assert main(["--input", str(source), "--neutral-image", str(source), "--output", str(output)]) == 0
    assert counters == {"init": 1, "process": 2, "close": 1}
    console = capsys.readouterr().out
    assert "EAR=0.3" in console and "delta iris=(0.0, 0.0)" in console
    assert module.load_image(output).any()
