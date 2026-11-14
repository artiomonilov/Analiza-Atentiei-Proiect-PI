"""Test manual IMAGE cu model local: python test_face_landmarker.py --help."""
import argparse
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MediaPipe Face Landmarker pe o fotografie locală")
    parser.add_argument("--input", type=Path, required=True, help="imaginea de procesat")
    parser.add_argument("--model", type=Path, default=Path("models/face_landmarker.task"), help="model .task local")
    parser.add_argument("--output", type=Path, default=Path("results/face_landmarker_result.jpg"), help="imaginea cu landmarks")
    args = parser.parse_args(argv)

    from audience_analysis.face_landmarker import FaceLandmarker, draw_landmarks, load_image, save_image
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError("Calea --output trebuie să fie diferită de fotografia originală.")
        image = load_image(args.input)
        with FaceLandmarker(args.model) as landmarker:
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
        save_image(args.output, draw_landmarks(image, result))
        print(f"\nImagine salvată: {args.output.resolve()}")
        return 0
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"Eroare: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
