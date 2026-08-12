"""Rectangular CSV logging for accepted structured channel samples."""

from collections.abc import Callable
import csv
from pathlib import Path
import time
from typing import TextIO

from serialscope.parsing import ChannelUpdate


SUPPORTED_DELIMITERS = {",", ";", "\t"}


class StructuredCsvLoggerError(Exception):
    """A user-presentable structured logging failure."""


class StructuredCsvLogger:
    """Write structured updates using stable first-sample columns."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._file: TextIO | None = None
        self._writer: csv.writer | None = None
        self._started_at: float | None = None
        self._columns: tuple[str, ...] = ()
        self._ignored_channels: list[str] = []
        self._row_count = 0
        self._delimiter = ","

    @property
    def is_recording(self) -> bool:
        return self._file is not None

    @property
    def columns(self) -> tuple[str, ...]:
        return self._columns

    @property
    def row_count(self) -> int:
        return self._row_count

    @property
    def ignored_channels(self) -> tuple[str, ...]:
        return tuple(self._ignored_channels)

    @property
    def delimiter(self) -> str:
        return self._delimiter

    def start(self, path: Path, delimiter: str = ",") -> None:
        """Create an empty UTF-8 CSV and begin monotonic session timing."""
        if self.is_recording:
            raise StructuredCsvLoggerError("Structured logging is already active.")
        if delimiter not in SUPPORTED_DELIMITERS:
            raise StructuredCsvLoggerError("Unsupported structured data delimiter.")
        try:
            log_file = path.open("w", encoding="utf-8", newline="")
        except (OSError, ValueError) as error:
            raise StructuredCsvLoggerError(
                f"Could not open structured data file: {error}"
            ) from error

        self._file = log_file
        self._writer = csv.writer(log_file, delimiter=delimiter)
        self._started_at = self._clock()
        self._columns = ()
        self._ignored_channels = []
        self._row_count = 0
        self._delimiter = delimiter
        try:
            self._writer.writerow(("elapsed_s",))
        except (OSError, ValueError, csv.Error) as error:
            self._close_after_failure()
            raise StructuredCsvLoggerError(
                f"Could not initialize structured data file: {error}"
            ) from error

    def write(self, update: ChannelUpdate) -> None:
        """Write one sample; later unknown channels are explicitly ignored."""
        if self._file is None or self._writer is None or self._started_at is None:
            raise StructuredCsvLoggerError("Structured logging is not active.")

        try:
            if not self._columns:
                self._columns = update.names
                self._file.seek(0)
                self._file.truncate()
                self._writer.writerow(("elapsed_s", *self._columns))

            for name in update.names:
                if name not in self._columns and name not in self._ignored_channels:
                    self._ignored_channels.append(name)

            values = update.channels
            elapsed = max(0.0, self._clock() - self._started_at)
            self._writer.writerow(
                (f"{elapsed:.3f}", *(values.get(name, "") for name in self._columns))
            )
        except (OSError, ValueError, csv.Error) as error:
            self._close_after_failure()
            raise StructuredCsvLoggerError(
                f"Could not write structured data file: {error}"
            ) from error
        self._row_count += 1

    def stop(self) -> None:
        """Flush, close, and release the structured CSV file."""
        if self._file is None:
            return
        log_file = self._file
        self._file = None
        self._writer = None
        self._started_at = None
        try:
            log_file.flush()
            log_file.close()
        except (OSError, ValueError) as error:
            try:
                log_file.close()
            except (OSError, ValueError):
                pass
            raise StructuredCsvLoggerError(
                f"Could not close structured data file: {error}"
            ) from error

    def _close_after_failure(self) -> None:
        log_file = self._file
        self._file = None
        self._writer = None
        self._started_at = None
        if log_file is not None:
            try:
                log_file.close()
            except (OSError, ValueError):
                pass
