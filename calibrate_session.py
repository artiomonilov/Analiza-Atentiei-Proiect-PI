"""Creare explicită profil local din fotografii neutre și/sau secvențe EAR."""
import argparse
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Calibrare neutră și EAR individual")
    parser.add_argument("--neutral-image", type=Path, nargs="+")
    parser.add_argument("--model", type=Path, default=Path("models/face_landmarker.task"))
    parser.add_argument("--open-measurements", type=Path)
    parser.add_argument("--closed-measurements", type=Path)
    parser.add_argument("--session-id", action="append", required=True, help="ID anonim; repetă pentru toate sesiunile folosite")
    parser.add_argument("--output", type=Path, required=True, help="profil JSON nou")
    parser.add_argument("--raw-source", type=Path, action="append", default=[], help="material brut C autorizat; se salvează doar hashul")
    args = parser.parse_args(argv)
    from audience_analysis.calibration import CalibrationManager
    from audience_analysis.validation import read_measurements, valid
    try:
        manager = CalibrationManager(args.session_id)
        if args.neutral_image:
            from audience_analysis.experimental import file_digest
            manager.bind_model_hash(file_digest(args.model))
            from audience_analysis.face_landmarker import FaceLandmarker, load_image
            observations = []
            with FaceLandmarker(args.model) as detector:
                for path in args.neutral_image:
                    image = load_image(path)
                    result = detector.process(image)
                    if not result.faces:
                        raise ValueError(f"Față lipsă în referința neutră: {path}")
                    observations.append((result.faces[0], (image.shape[1], image.shape[0])))
            manager.calibrate_neutral(observations)
        if bool(args.open_measurements) != bool(args.closed_measurements):
            raise ValueError("Oferă ambele CSV-uri EAR: deschis și închis.")
        if args.open_measurements:
            manager.register_measurement_source(args.open_measurements)
            manager.register_measurement_source(args.closed_measurements)
            opened, closed = read_measurements(args.open_measurements), read_measurements(args.closed_measurements)
            for side in ("left", "right"):
                manager.calibrate_ear(side, [r[side + "_ear"] for r in opened if valid(r, side + "_ear")],
                                      [r[side + "_ear"] for r in closed if valid(r, side + "_ear")])
        if not args.neutral_image and not args.open_measurements:
            raise ValueError("Furnizează fotografii neutre sau secvențe EAR.")
        manager.register_materials(args.raw_source, kind="raw")
        manager.register_materials(args.neutral_image or [], kind="neutral_image")
        manager.register_materials([p for p in (args.open_measurements, args.closed_measurements) if p], kind="measurements")
        manager.save(args.output)
        print(f"Profil salvat: {args.output.resolve()}")
        return 0
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"Eroare: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
