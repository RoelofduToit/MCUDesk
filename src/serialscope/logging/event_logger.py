"""Parent-session CSV logging for sparse operator annotations."""

import csv
from pathlib import Path
from typing import TextIO

from serialscope.data import EventMarker


class EventLoggerError(Exception):
    """A user-presentable event logging failure."""


class EventLogger:
    """Stream event markers to one parent-level UTF-8 CSV file."""

    HEADER = ("elapsed_s", "event_id", "event")

    def __init__(self) -> None:
        self._file: TextIO | None = None
        self._writer: csv.writer | None = None
        self._event_count = 0

    @property
    def is_recording(self) -> bool:
        return self._file is not None

    @property
    def event_count(self) -> int:
        return self._event_count

    def start(self, path: Path) -> None:
        if self.is_recording:
            raise EventLoggerError("Event logging is already active.")
        stream: TextIO | None = None
        try:
            stream = Path(path).open("w", encoding="utf-8", newline="")
            writer = csv.writer(stream)
            writer.writerow(self.HEADER)
            stream.flush()
        except (OSError, ValueError, csv.Error) as error:
            if stream is not None:
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass
            raise EventLoggerError(f"Could not create events.csv: {error}") from error
        self._file = stream
        self._writer = writer
        self._event_count = 0

    def write(self, marker: EventMarker) -> None:
        if self._file is None or self._writer is None:
            raise EventLoggerError("Event logging is unavailable.")
        try:
            self._writer.writerow((repr(marker.elapsed_s), marker.event_id, marker.text))
            # Events are sparse and operator-authored, so make each confirmed
            # annotation visible to the filesystem immediately.
            self._file.flush()
        except (OSError, ValueError, csv.Error) as error:
            self._close_after_failure()
            raise EventLoggerError(f"Could not write events.csv: {error}") from error
        self._event_count += 1

    def stop(self) -> None:
        if self._file is None:
            return
        stream = self._file
        self._file = None
        self._writer = None
        try:
            stream.flush()
            stream.close()
        except (OSError, ValueError) as error:
            try:
                stream.close()
            except (OSError, ValueError):
                pass
            raise EventLoggerError(f"Could not close events.csv: {error}") from error

    def _close_after_failure(self) -> None:
        stream = self._file
        self._file = None
        self._writer = None
        if stream is not None:
            try:
                stream.close()
            except (OSError, ValueError):
                pass
