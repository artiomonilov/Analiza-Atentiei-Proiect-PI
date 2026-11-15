"""Contract și lifecycle testate fără model, rețea sau fotografie personală."""
import sys
from types import SimpleNamespace as NS

import numpy as np
import pytest

from audience_analysis.face_landmarker import (
    Blendshape, FaceLandmarker, FaceLandmarkerError, FaceLandmarks,
    Landmark, LandmarkerResult, draw_landmarks, load_image, save_image,
)


@pytest.fixture
def fake_mp(monkeypatch, tmp_path):
    state = NS(closed=0, raw=NS(face_landmarks=[], face_blendshapes=[], facial_transformation_matrixes=[]))

    def create(options):
        state.options = options
        return NS(detect=detect, detect_for_video=detect_video, close=close)

    def detect(image):
        state.rgb = image.data
        return state.raw

    def detect_video(image, timestamp):
        state.timestamp = timestamp
        return detect(image)

    def close():
        state.closed += 1

    mp = NS(tasks=NS(BaseOptions=lambda **kw: NS(**kw), vision=NS(
        FaceLandmarkerOptions=lambda **kw: NS(**kw), RunningMode=NS(IMAGE="IMAGE", VIDEO="VIDEO"),
        FaceLandmarker=NS(create_from_options=create))), Image=lambda **kw: NS(**kw), ImageFormat=NS(SRGB="SRGB"))
    monkeypatch.setitem(sys.modules, "mediapipe", mp)
    state.path = tmp_path / "model.task"
    state.path.touch()
    return state


def test_options_rgb_contiguity_and_no_face(fake_mp):
    image = np.full((3, 4, 3), [1, 2, 3], dtype=np.uint8)
    with FaceLandmarker(fake_mp.path) as detector:
        assert detector.process(image).faces == ()
    assert fake_mp.options.running_mode == "IMAGE"
    assert fake_mp.options.num_faces == 1
    assert fake_mp.options.output_face_blendshapes
    assert fake_mp.options.output_facial_transformation_matrixes
    assert fake_mp.rgb[0, 0].tolist() == [3, 2, 1]
    assert fake_mp.rgb.flags.c_contiguous
    assert fake_mp.closed == 1


def test_video_mode_enforces_strict_timestamps_and_photo_compatibility(fake_mp):
    frame = np.zeros((3, 4, 3), np.uint8)
    with FaceLandmarker(fake_mp.path, mode="VIDEO") as detector:
        assert detector.process_video(frame, 0).faces == ()
        detector.process_video(frame, 40)
        assert fake_mp.timestamp == 40
        assert fake_mp.options.running_mode == "VIDEO"
        for invalid in (40, 39, -1, 40.5):
            with pytest.raises(ValueError):
                detector.process_video(frame, invalid)
        with pytest.raises(FaceLandmarkerError):
            detector.process(frame)
    with FaceLandmarker(fake_mp.path) as detector:
        with pytest.raises(FaceLandmarkerError):
            detector.process_video(frame, 0)
        assert detector.process(frame).faces == ()


def test_extracts_points_blendshapes_and_matrix(fake_mp):
    fake_mp.raw = NS(face_landmarks=[[NS(x=.1, y=.2, z=.3)] * 478],
                     face_blendshapes=[[NS(category_name="eyeBlinkLeft", score=.7)]],
                     facial_transformation_matrixes=[np.eye(4)])
    with FaceLandmarker(fake_mp.path) as detector:
        result = detector.process(np.zeros((8, 8, 3), np.uint8))
    assert len(result.faces[0].landmarks) == 478
    assert result.faces[0].blendshapes == (Blendshape("eyeBlinkLeft", .7),)
    np.testing.assert_array_equal(result.faces[0].transformation_matrix, np.eye(4))


@pytest.mark.parametrize("image", [None, np.zeros((2, 2), np.uint8), np.zeros((0, 2, 3), np.uint8), np.zeros((2, 2, 3))])
def test_invalid_images_close_resources(fake_mp, image):
    with pytest.raises(ValueError), FaceLandmarker(fake_mp.path) as detector:
        detector.process(image)
    assert fake_mp.closed == 1


def test_closed_model_and_missing_files(fake_mp, tmp_path):
    detector = FaceLandmarker(fake_mp.path)
    detector.close()
    detector.close()
    assert fake_mp.closed == 1
    with pytest.raises(FaceLandmarkerError, match="închis"):
        detector.process(np.zeros((2, 2, 3), np.uint8))
    with pytest.raises(FileNotFoundError):
        FaceLandmarker(tmp_path / "missing.task")
    with pytest.raises(FileNotFoundError):
        load_image(tmp_path / "missing.png")


def test_annotation_roundtrip_without_modifying_original(tmp_path):
    pytest.importorskip("cv2")
    image = np.zeros((30, 30, 3), np.uint8)
    face = FaceLandmarks((Landmark(.5, .5, 0),), (), None)
    annotated = draw_landmarks(image, LandmarkerResult((face,)))
    assert not image.any()
    assert annotated[15, 15].tolist() == [0, 255, 0]
    path = tmp_path / "rezultate șț" / "poză.png"
    save_image(path, annotated)
    np.testing.assert_array_equal(load_image(path), annotated)
