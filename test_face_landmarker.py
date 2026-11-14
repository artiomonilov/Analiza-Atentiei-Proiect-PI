"""Test manual IMAGE cu model local: python test_face_landmarker.py --help."""
import argparse
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MediaPipe Face Landmarker pe o fotografie locală")
    parser.add_argument("--input", type=Path, required=True, help="imaginea de procesat")
    parser.add_argument("--model", type=Path, default=Path("models/face_landmarker.task"), help="model .task local")
    parser.add_argument("--output", type=Path, default=Path("results/face_landmarker_result.jpg"), help="imaginea cu landmarks")
    parser.add_argument("--neutral-image", type=Path, help="fotografie cu poziția neutră pentru calibrarea orientării")
    args = parser.parse_args(argv)

    from audience_analysis.face_landmarker import FaceLandmarker, draw_landmarks, load_image, save_image
    from audience_analysis.head_pose import HeadPoseEstimator, draw_head_pose
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError("Calea --output trebuie să fie diferită de fotografia originală.")
        if args.neutral_image and args.neutral_image.resolve() == args.output.resolve():
            raise ValueError("Calea --output trebuie să fie diferită de fotografia neutră.")
        estimator = HeadPoseEstimator()
        image = load_image(args.input)
        with FaceLandmarker(args.model) as landmarker:
            if args.neutral_image:
                neutral = landmarker.process(load_image(args.neutral_image))
                if not neutral.faces:
                    raise ValueError("Fotografia neutră nu conține o față detectabilă.")
                estimator.calibrate(neutral.faces[0].transformation_matrix)
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
        save_image(args.output, draw_head_pose(draw_landmarks(image, result), pose))
        print(f"\nImagine salvată: {args.output.resolve()}")
        return 0
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"Eroare: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
