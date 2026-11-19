"""Export incremental comun pentru VideoProcessor și workerul P2; fără captură."""
from contextlib import ExitStack
from dataclasses import asdict
import csv
from pathlib import Path

from .temporal_analysis import BlinkEvent, temporal_csv_row
from .video_processor import VideoMeasurement


TEMPORAL_FIELDS = ["timestamp_ms", "window_s", "sample_count", "observed_span_ms", "history_truncated",
                   "head_json", "left_gaze_json", "right_gaze_json", "left_blink_json", "right_blink_json",
                   "filtered_head_json", "filtered_left_iris_json", "filtered_right_iris_json"]


class FacialCSVExport:
    def __init__(self, measurements=None, temporal=None, blinks=None, *, metadata_fields=()):
        self.stack = ExitStack()
        self.metadata_fields = tuple(metadata_fields)
        self.writers, self.streams = {}, []
        try:
            specifications = (
                ("measurements", measurements, list(VideoMeasurement.__dataclass_fields__)),
                ("temporal", temporal, TEMPORAL_FIELDS),
                ("blinks", blinks, list(BlinkEvent.__dataclass_fields__)),
            )
            paths = [Path(path).resolve() for _, path, _ in specifications if path is not None]
            if len(set(paths)) != len(paths):
                raise ValueError("Exporturile faciale trebuie să fie distincte")
            for key, path, fields in specifications:
                if path is None:
                    continue
                path = Path(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                stream = self.stack.enter_context(path.open("x", newline="", encoding="utf-8"))
                writer = csv.DictWriter(stream, fieldnames=[*fields, *self.metadata_fields])
                writer.writeheader()
                self.writers[key] = writer
                self.streams.append(stream)
        except BaseException:
            self.stack.close()
            raise

    def write(self, record, temporal, metadata=None):
        metadata = metadata or {}
        if set(metadata) - set(self.metadata_fields):
            raise ValueError("Metadate CSV nedeclarate")
        if "measurements" in self.writers:
            self.writers["measurements"].writerow({**asdict(record), **metadata})
        if "temporal" in self.writers:
            for window in temporal.windows:
                self.writers["temporal"].writerow({**temporal_csv_row(temporal, window), **metadata})
        if "blinks" in self.writers:
            for event in temporal.new_blinks:
                self.writers["blinks"].writerow({**asdict(event), **metadata})
        for stream in self.streams:
            stream.flush()

    def close(self):
        self.stack.close()

    def __enter__(self):
        return self

    def __exit__(self, *_error):
        self.close()
