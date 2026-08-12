from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from serialscope import __version__
from serialscope.logging import (
    RecordingSession,
    SessionConfig,
    sanitize_session_name,
)


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current


def _config(session_name: str = "") -> SessionConfig:
    return SessionConfig(
        session_name=session_name,
        device="COM4",
        baud_rate=115200,
        line_ending="LF",
    )


@pytest.mark.parametrize(
    ("name", "sanitized"),
    [
        ("Pico temperature test", "Pico_temperature_test"),
        ('bad<>:"/\\|?* name', "bad_name"),
        ("  ", "SerialSession"),
        ("CON", "Session_CON"),
    ],
)
def test_session_name_sanitization(name: str, sanitized: str) -> None:
    assert sanitize_session_name(name) == sanitized


def test_default_and_custom_session_folder_names(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 8, 12, 18, 15, tzinfo=timezone.utc))
    default_session = RecordingSession(clock=clock)
    custom_session = RecordingSession(clock=clock)

    default_directory = default_session.start(tmp_path, _config())
    custom_directory = custom_session.start(
        tmp_path,
        _config("Pico temperature test"),
    )

    assert default_directory.name == "SerialSession_2026-08-12_1815"
    assert custom_directory.name == "Pico_temperature_test_2026-08-12_1815"
    default_session.stop("normal", 0)
    custom_session.stop("normal", 0)


def test_existing_session_directory_is_not_overwritten(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 8, 12, 18, 15, tzinfo=timezone.utc))
    existing = tmp_path / "SerialSession_2026-08-12_1815"
    existing.mkdir()
    (existing / "keep.txt").write_text("keep", encoding="utf-8")
    session = RecordingSession(clock=clock)

    directory = session.start(tmp_path, _config())

    assert directory.name == "SerialSession_2026-08-12_1815_2"
    assert (existing / "keep.txt").read_text(encoding="utf-8") == "keep"
    session.stop("normal", 0)


def test_session_writes_exact_raw_data_and_complete_metadata(tmp_path: Path) -> None:
    start = datetime(
        2026,
        8,
        12,
        18,
        15,
        tzinfo=timezone(timedelta(hours=2)),
    )
    clock = MutableClock(start)
    session = RecordingSession(clock=clock)
    config = _config("Pico temperature test")

    directory = session.start(tmp_path, config)
    start_metadata = json.loads((directory / "session.json").read_text("utf-8"))
    session.write(b"text\n")
    session.write(b"\xff\x00binary")
    clock.current += timedelta(seconds=161.5)
    session.stop("normal", 42)

    metadata = json.loads((directory / "session.json").read_text("utf-8"))
    assert (directory / "raw.log").read_bytes() == b"text\n\xff\x00binary"
    assert start_metadata["serialscope_version"] == __version__
    assert start_metadata["session_name"] == "Pico temperature test"
    assert start_metadata["recording_start_local"] == start.isoformat()
    assert start_metadata["recording_start_utc"] == start.astimezone(timezone.utc).isoformat()
    assert start_metadata["serial"] == {
        "device": "COM4",
        "baud_rate": 115200,
        "data_bits": 8,
        "parity": "none",
        "stop_bits": 1,
        "line_ending": "LF",
    }
    assert start_metadata["status"] == "recording"
    assert metadata["status"] == "completed"
    assert metadata["end_reason"] == "normal"
    assert metadata["elapsed_seconds"] == 161.5
    assert metadata["logged_byte_count"] == 13
    assert metadata["total_rx_byte_count"] == 42
    assert metadata["recording_end_local"] == clock.current.isoformat()


def test_disconnect_end_reason_is_recorded(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 8, 12, 18, 15, tzinfo=timezone.utc))
    session = RecordingSession(clock=clock)
    directory = session.start(tmp_path, _config("Disconnect test"))

    session.stop("serial_disconnected", 10)

    metadata = json.loads((directory / "session.json").read_text("utf-8"))
    assert metadata["end_reason"] == "serial_disconnected"
    assert metadata["status"] == "completed"
