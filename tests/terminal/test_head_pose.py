"""Geometrie verificată fără model, fotografie sau rețea."""
import numpy as np
import pytest

from audience_analysis.head_pose import HeadPoseEstimator, draw_head_pose, extract_rotation
from audience_analysis.vision import MediaPipeHeadPose, rotation_to_angles


def transform(yaw=0, pitch=0, roll=0):
    # Rotații elementare active în sistem drept; compuse în ordinea documentată.
    x, y, z = np.deg2rad([pitch, yaw, roll])
    rx = np.array([[1, 0, 0], [0, np.cos(x), -np.sin(x)], [0, np.sin(x), np.cos(x)]])
    ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    rz = np.array([[np.cos(z), -np.sin(z), 0], [np.sin(z), np.cos(z), 0], [0, 0, 1]])
    matrix = np.eye(4)
    matrix[:3, :3] = rz @ ry @ rx
    return matrix


@pytest.mark.parametrize("angles", [(0, 0, 0), (30, 0, 0), (-35, 0, 0), (0, 25, 0),
                                  (0, -45, 0), (0, 0, 70), (0, 0, -80), (32, -24, 51), (-40, 55, -25)])
def test_known_rotations(angles):
    pose = HeadPoseEstimator().estimate(transform(*angles))
    assert pose.valid
    assert (pose.yaw, pose.pitch, pose.roll) == pytest.approx(angles, abs=1e-8)


@pytest.mark.parametrize("stretch", [np.eye(3) * 3, np.diag([2, 3, 4]),
                                    np.array([[2, .2, .1], [.2, 3, .3], [.1, .3, 4]])])
def test_removes_scale_stretch_and_translation(stretch):
    matrix = transform(20, -30, 15)
    matrix[:3, :3] = matrix[:3, :3] @ stretch
    matrix[:3, 3] = [400, -30, 80]
    pose = HeadPoseEstimator().estimate(matrix)
    assert (pose.yaw, pose.pitch, pose.roll) == pytest.approx((20, -30, 15))
    rotation = extract_rotation(matrix)
    np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-12)
    assert np.linalg.det(rotation) == pytest.approx(1)


def test_neutral_calibration_uses_relative_rotation_not_euler_subtraction():
    neutral = transform(25, -15, 30)
    delta = transform(-20, 18, 12)
    current = neutral @ delta
    estimator = HeadPoseEstimator()
    estimator.calibrate(neutral)
    zero = estimator.estimate(neutral)
    assert (zero.yaw, zero.pitch, zero.roll) == pytest.approx((0, 0, 0), abs=1e-10)
    pose = estimator.estimate(current)
    assert pose.calibrated
    assert (pose.yaw, pose.pitch, pose.roll) == pytest.approx((-20, 18, 12))
    with pytest.raises(ValueError):
        estimator.calibrate(np.zeros((4, 4)))
    assert estimator.estimate(current) == pose
    estimator.clear_calibration()
    assert not estimator.estimate(current).calibrated


@pytest.mark.parametrize("matrix", [None, np.eye(3), np.zeros((4, 4)), np.full((4, 4), np.nan),
                                   np.full((4, 4), np.inf), np.diag([-1, 1, 1, 1]),
                                   np.diag([1, 1, 0, 1]), np.diag([1, 1, 1e-12, 1]),
                                   [["invalid"] * 4] * 4])
def test_invalid_or_missing_matrix_is_unavailable(matrix):
    result = HeadPoseEstimator().estimate(matrix)
    assert not result.valid
    assert result.reason
    assert result.yaw is result.pitch is result.roll is None


@pytest.mark.parametrize("yaw", [-90, 90, -89.9999999, 89.9999999])
def test_gimbal_lock_is_explicit_and_reconstructs_rotation(yaw):
    matrix = transform(yaw, 20, 35)
    pose = HeadPoseEstimator().estimate(matrix)
    assert pose.valid and pose.gimbal_lock
    assert pose.roll == 0
    reconstructed = transform(pose.yaw, pose.pitch, pose.roll)
    np.testing.assert_allclose(reconstructed, matrix, atol=1e-7)


def test_rejects_projective_bottom_row():
    matrix = np.eye(4)
    matrix[3, 0] = .2
    assert not HeadPoseEstimator().estimate(matrix).valid


def test_legacy_wrapper_keeps_pitch_yaw_roll_order():
    assert rotation_to_angles(transform(20, 10, 30)[:3, :3] * 2) == pytest.approx((10, 20, 30))


def test_adapter_only_returns_angles_even_with_legacy_calibrated_flag():
    from types import SimpleNamespace as NS
    adapter = MediaPipeHeadPose(None, calibrated=True)
    adapter.landmarker = NS(process=lambda _: NS(faces=[NS(transformation_matrix=transform(20, 10, 30))]))
    estimate = adapter.estimate(None)
    assert estimate.status == "unknown"
    assert (estimate.yaw, estimate.pitch, estimate.roll) == pytest.approx((20, 10, 30))


def test_overlay_keeps_original_unchanged():
    pytest.importorskip("cv2")
    image = np.zeros((240, 500, 3), np.uint8)
    output = draw_head_pose(image, HeadPoseEstimator().estimate(np.eye(4)))
    assert output.any()
    assert not image.any()
