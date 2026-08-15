"""Exact raw-byte serial logging."""

from pathlib import Path
from typing import BinaryIO


class RawLoggerError(Exception):
    """A user-presentable raw logging failure."""


class RawLogger:
    """Own a buffered binary log file and its byte count."""

    def __init__(self) -> None:
        self._file: BinaryIO | None = None
        self._path: Path | None = None
        self._bytes_written = 0

    @property
    def is_recording(self) -> bool:
        return self._file is not None

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def bytes_written(self) -> int:
        return self._bytes_written

    def start(self, path: Path) -> None:
        """Create a binary log and begin a new logging count."""
        if self.is_recording:
            raise RawLoggerError("Raw logging is already active.")

        try:
            log_file = path.open("wb")
        except (OSError, ValueError) as error:
            raise RawLoggerError(f"Could not open log file: {error}") from error

        self._file = log_file
        self._path = path
        self._bytes_written = 0

    def write(self, data: bytes) -> int:
        """Write an exact raw RX chunk and return its byte count."""
        if self._file is None:
            raise RawLoggerError("Raw logging is not active.")

        try:
            written = self._file.write(data)
            if written != len(data):
                raise OSError(f"only {written} of {len(data)} bytes were written")
        except (OSError, ValueError) as error:
            self._close_after_failure()
            raise RawLoggerError(f"Could not write log file: {error}") from error

        self._bytes_written += written
        return written

    def flush(self) -> None:
        """Push buffered bytes to the OS without closing the file."""
        if self._file is None:
            return
        try:
            self._file.flush()
        except (OSError, ValueError) as error:
            self._close_after_failure()
            raise RawLoggerError(f"Could not flush log file: {error}") from error

    def stop(self) -> None:
        """Flush, close, and release the current log file."""
        if self._file is None:
            return

        log_file = self._file
        self._file = None
        try:
            log_file.flush()
            log_file.close()
        except (OSError, ValueError) as error:
            try:
                log_file.close()
            except (OSError, ValueError):
                pass
            raise RawLoggerError(f"Could not close log file: {error}") from error

    def _close_after_failure(self) -> None:
        log_file = self._file
        self._file = None
        if log_file is not None:
            try:
                log_file.close()
            except (OSError, ValueError):
                pass
