from pathlib import Path
from unittest.mock import Mock

import pytest

from serialscope.logging import RawLogger, RawLoggerError


def test_logger_starts_writes_exact_chunks_and_stops(tmp_path: Path) -> None:
    path = tmp_path / "raw.log"
    logger = RawLogger()

    logger.start(path)
    first_count = logger.write(b"text\n")
    second_count = logger.write(b"\x00\xff\r\n")
    logger.stop()

    assert first_count == 5
    assert second_count == 4
    assert logger.bytes_written == 9
    assert not logger.is_recording
    assert path.read_bytes() == b"text\n\x00\xff\r\n"


def test_logger_stop_flushes_and_closes_file(monkeypatch, tmp_path: Path) -> None:
    log_file = Mock()
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: log_file)
    logger = RawLogger()
    logger.start(tmp_path / "raw.log")

    logger.stop()

    log_file.flush.assert_called_once_with()
    log_file.close.assert_called_once_with()
    assert not logger.is_recording


def test_logger_open_failure_is_translated(monkeypatch, tmp_path: Path) -> None:
    def fail_open(*_args, **_kwargs):
        raise PermissionError("permission denied")

    monkeypatch.setattr(Path, "open", fail_open)
    logger = RawLogger()

    with pytest.raises(RawLoggerError, match="permission denied"):
        logger.start(tmp_path / "raw.log")

    assert not logger.is_recording


def test_logger_write_failure_stops_and_closes(monkeypatch, tmp_path: Path) -> None:
    log_file = Mock()
    log_file.write.side_effect = OSError("disk unavailable")
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: log_file)
    logger = RawLogger()
    logger.start(tmp_path / "raw.log")

    with pytest.raises(RawLoggerError, match="disk unavailable"):
        logger.write(b"raw bytes")

    assert not logger.is_recording
    assert logger.bytes_written == 0
    log_file.close.assert_called_once_with()


def test_logger_flush_failure_stops_recording(monkeypatch, tmp_path: Path) -> None:
    log_file = Mock()
    log_file.flush.side_effect = OSError("disk full")
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: log_file)
    logger = RawLogger()
    logger.start(tmp_path / "raw.log")

    with pytest.raises(RawLoggerError, match="disk full"):
        logger.flush()

    assert not logger.is_recording
    log_file.close.assert_called()


def test_unexpectedly_closed_file_is_handled(monkeypatch, tmp_path: Path) -> None:
    log_file = Mock()
    log_file.write.side_effect = ValueError("write to closed file")
    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: log_file)
    logger = RawLogger()
    logger.start(tmp_path / "raw.log")

    with pytest.raises(RawLoggerError, match="closed file"):
        logger.write(b"raw bytes")

    assert not logger.is_recording
