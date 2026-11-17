"""Test manual IMAGE cu model local: python test_face_landmarker.py --help."""
import argparse
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MediaPipe Face Landmarker pe o fotografie locală")
    parser.add_argument("--input", type=Path, required=True, help="imaginea de procesat")
    parser.add_argument("--model", type=Path, default=Path("models/face_landmarker.task"), help="model .task local")
    parser.add_argument("--output", type=Path, default=Path("results/face_landmarker_result.jpg"), help="imaginea cu landmarks")
    parser.add_argument("--neutral-image", type=Path, help="fotografie neutră pentru orientare, EAR și poziția irisurilor")
    parser.add_argument("--min-open-ratio", type=float, help="limită individuală EAR/EAR_neutru pentru disponibilitatea irisului")
    parser.add_argument("--min-iris-aperture-px", type=float, default=1.0, help="apertura geometrică minimă în pixeli (implicit 1)")
    args = parser.parse_args(argv)

    from audience_analysis.face_landmarker import FaceLandmarker, draw_landmarks, load_image, save_image
    from audience_analysis.head_pose import HeadPoseEstimator, draw_head_pose
    from audience_analysis.eye_features import EyeFeaturesEstimator, draw_eye_features
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError("Calea --output trebuie să fie diferită de fotografia originală.")
        if args.neutral_image and args.neutral_image.resolve() == args.output.resolve():
            raise ValueError("Calea --output trebuie să fie diferită de fotografia neutră.")
        estimator = HeadPoseEstimator()
        eye_estimator = EyeFeaturesEstimator(min_iris_aperture_px=args.min_iris_aperture_px,
                                             min_open_ratio=args.min_open_ratio)
        image = load_image(args.input)
        with FaceLandmarker(args.model) as landmarker:
            if args.neutral_image:
                neutral_image = load_image(args.neutral_image)
                neutral = landmarker.process(neutral_image)
                if not neutral.faces:
                    raise ValueError("Fotografia neutră nu conține o față detectabilă.")
                estimator.calibrate(neutral.faces[0].transformation_matrix)
                neutral_size = (neutral_image.shape[1], neutral_image.shape[0])
                neutral_eyes = eye_estimator.estimate(neutral.faces[0], neutral_size)
                sides = tuple(side for side in ("left", "right") if getattr(neutral_eyes, side).iris_position is not None)
                if sides:
                    eye_estimator.calibrate(neutral.faces[0], neutral_size, sides=sides)
                if len(sides) != 2:
                    print("Calibrare ochi incompletă: referința nu are geometrie validă pentru ambii ochi.")
            result = landmarker.process(image)
        print(f"Fețe detectate: {len(result.faces)} (maximum configurat: 1)")
        if not result.faces:
            print("Nu a fost detectată nicio față; imaginea de ieșire păstrează originalul fără puncte.")
        for index, face in enumerate(result.faces, start=1):
            print(f"\nFața {index}: {len(face.landmarks)} landmarks")
            print("Top 10 blendshapes:")
            for category in sorted(face.blendshapes, key=lambda item: item.score, reverse=True)[:10]:
                print(f"  {category.name}: {category.score:.4f}")
            print("Matricea de transformare facială brută (nu unghiuri yaw/pitch/roll):")
            print(face.transformation_matrix if face.transformation_matrix is not None else "indisponibilă")
        pose = estimator.estimate(result.faces[0].transformation_matrix if result.faces else None)
        if pose.valid:
            print(f"Yaw: {pose.yaw:+.2f}°; pitch: {pose.pitch:+.2f}°; roll: {pose.roll:+.2f}°")
            print("Reper: poziție neutră" if pose.calibrated else "Reper: cameră, fără calibrare neutră")
            if pose.gimbal_lock:
                print("Singularitate Euler: roll fixat la 0; yaw/pitch/roll nu sunt unice.")
        else:
            print(f"Orientare indisponibilă: {pose.reason}")
        eyes = eye_estimator.estimate(result.faces[0] if result.faces else None, (image.shape[1], image.shape[0]))
        for features in (eyes.left, eyes.right):
            print(f"Ochi {features.subject_side} (subiect): EAR={features.ear}; iris relativ={features.iris_position}")
            if features.ear_relative is not None:
                print(f"  EAR/EAR_neutru={features.ear_relative:.3f}; delta iris={features.gaze_delta}")
            if features.reason:
                print(f"  {features.reason}")
        annotated = draw_eye_features(draw_head_pose(draw_landmarks(image, result), pose), eyes)
        save_image(args.output, annotated)
        print(f"\nImagine salvată: {args.output.resolve()}")
        return 0
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"Eroare: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
