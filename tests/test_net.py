"""Experiment manual istoric, acum fără efecte secundare la import/colectare."""


def main(argv=None):
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Statistică de expresie pe o imagine locală autorizată")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--allow-model-download", action="store_true")
    args = parser.parse_args(argv)
    import cv2
    from audience_analysis.model_stats import EmotionStatisticsModel
    frame = cv2.imread(str(args.image))
    if frame is None: parser.error("Imagine locală lipsă sau invalidă.")
    print(EmotionStatisticsModel(allow_download=args.allow_model_download).predict_bgr(frame))
    return 0


def test_import_does_not_load_transformers_or_access_network():
    import subprocess
    import sys
    from pathlib import Path
    source = Path(__file__).resolve()
    code = "import runpy,sys,socket; socket.socket=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network')); runpy.run_path(sys.argv[1],run_name='offline_import_probe'); assert 'transformers' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code, str(source)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    raise SystemExit(main())
