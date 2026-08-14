from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from serialscope import __version__
from serialscope.logging import (
    RecordingSession,
    RecordingSessionError,
    SessionConfig,
    StructuredCsvLogger,
    sanitize_session_name,
)
from serialscope.parsing import ChannelUpdate


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def __call__(self) -> datetime:
        return self.current


def _config(session_name: str = "Test session") -> SessionConfig:
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
        ("  ", ""),
        ("CON", "Session_CON"),
    ],
)
def test_session_name_sanitization(name: str, sanitized: str) -> None:
    assert sanitize_session_name(name) == sanitized


def test_custom_session_folder_name_is_sanitized(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 8, 12, 18, 15, tzinfo=timezone.utc))
    custom_session = RecordingSession(clock=clock)

    custom_directory = custom_session.start(
        tmp_path,
        _config("Reactor Test #3 - Hot Run"),
    )

    assert custom_directory.name == "Reactor_Test_#3_-_Hot_Run_2026-08-12_1815"
    custom_session.stop("normal", 0)


@pytest.mark.parametrize("session_name", ["", "   "])
def test_blank_session_name_is_rejected(
    tmp_path: Path,
    session_name: str,
) -> None:
    session = RecordingSession()

    with pytest.raises(
        RecordingSessionError,
        match="Enter a session name before starting a recording",
    ):
        session.start(tmp_path, _config(session_name))

    assert list(tmp_path.iterdir()) == []


def test_existing_session_directory_is_not_overwritten(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 8, 12, 18, 15, tzinfo=timezone.utc))
    existing = tmp_path / "Test_session_2026-08-12_1815"
    existing.mkdir()
    (existing / "keep.txt").write_text("keep", encoding="utf-8")
    session = RecordingSession(clock=clock)

    directory = session.start(tmp_path, _config())

    assert directory.name == "Test_session_2026-08-12_1815_2"
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
    monotonic_values = iter((50.0, 50.25))
    session = RecordingSession(
        clock=clock,
        structured_logger=StructuredCsvLogger(
            clock=lambda: next(monotonic_values)
        ),
    )
    config = _config("Reactor Test #3 - Hot Run")

    directory = session.start(tmp_path, config)
    start_metadata = json.loads((directory / "session.json").read_text("utf-8"))
    session.write(b"text\n")
    session.write(b"\xff\x00binary")
    session.write_structured(ChannelUpdate(("TC1", "TC2"), (100.4, 98.7)))
    clock.current += timedelta(seconds=161.5)
    session.stop("normal", 42)

    metadata = json.loads((directory / "session.json").read_text("utf-8"))
    assert (directory / "raw.log").read_bytes() == b"text\n\xff\x00binary"
    assert (directory / "data.csv").read_text(encoding="utf-8") == (
        "elapsed_s,TC1,TC2\n0.250,100.4,98.7\n"
    )
    assert start_metadata["serialscope_version"] == __version__
    assert start_metadata["session_name"] == "Reactor Test #3 - Hot Run"
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
    assert start_metadata["structured_data_file"] == "data.csv"
    assert metadata["status"] == "completed"
    assert metadata["end_reason"] == "normal"
    assert metadata["elapsed_seconds"] == 161.5
    assert metadata["logged_byte_count"] == 13
    assert metadata["total_rx_byte_count"] == 42
    assert metadata["structured_row_count"] == 1
    assert metadata["structured_columns"] == ["TC1", "TC2"]
    assert metadata["structured_ignored_channels"] == []
    assert metadata["recording_end_local"] == clock.current.isoformat()


def test_disconnect_end_reason_is_recorded(tmp_path: Path) -> None:
    clock = MutableClock(datetime(2026, 8, 12, 18, 15, tzinfo=timezone.utc))
    session = RecordingSession(clock=clock)
    directory = session.start(tmp_path, _config("Disconnect test"))

    session.stop("serial_disconnected", 10)

    metadata = json.loads((directory / "session.json").read_text("utf-8"))
    assert metadata["end_reason"] == "serial_disconnected"
    assert metadata["status"] == "completed"


def test_session_snapshots_profile_reference_without_profile_dependency(tmp_path: Path) -> None:
    session = RecordingSession()
    config = SessionConfig(
        "Profile run",
        "COM4",
        115200,
        "LF",
        profile_id="stable-profile-id",
        profile_name="Reactor Pico",
    )
    directory = session.start(tmp_path, config)
    session.stop("normal", 0)

    metadata = json.loads((directory / "session.json").read_text("utf-8"))
    assert metadata["device_profile"] == {
        "profile_id": "stable-profile-id",
        "profile_name": "Reactor Pico",
    }


def test_selected_structured_delimiter_is_stored_in_metadata(tmp_path: Path) -> None:
    session = RecordingSession()
    config = SessionConfig(
        session_name="Tab data",
        device="COM4",
        baud_rate=115200,
        line_ending="LF",
        structured_data_delimiter="\t",
    )

    directory = session.start(tmp_path, config)
    session.stop("normal", 0)

    metadata = json.loads((directory / "session.json").read_text("utf-8"))
    assert metadata["structured_data_delimiter"] == "\t"


def test_channel_metadata_is_stored_but_csv_keeps_source_names(tmp_path: Path) -> None:
    monotonic_values = iter((10.0, 10.5))
    session = RecordingSession(
        structured_logger=StructuredCsvLogger(clock=lambda: next(monotonic_values))
    )
    config = SessionConfig(
        session_name="Metadata",
        device="COM4",
        baud_rate=115200,
        line_ending="LF",
        channels={"TC1": {"alias": "Temperature", "unit": "°C"}},
    )
    directory = session.start(tmp_path, config)
    session.write_structured(ChannelUpdate(("TC1",), (100.0,)))
    session.set_channel_metadata(
        {"TC1": {"alias": "Reactor Temperature", "unit": "°C"}}
    )
    session.stop("normal", 0)

    metadata = json.loads((directory / "session.json").read_text("utf-8"))
    assert metadata["channels"] == {
        "TC1": {"alias": "Reactor Temperature", "unit": "°C"}
    }
    assert (directory / "data.csv").read_text(encoding="utf-8").startswith(
        "elapsed_s,TC1\n"
    )


def test_alarm_limits_are_metadata_only_and_raw_data_is_exact(tmp_path: Path) -> None:
    session = RecordingSession()
    config = SessionConfig(
        session_name="Alarm limits",
        device="COM4",
        baud_rate=115200,
        line_ending="LF",
        channels={
            "TC1": {
                "alias": "Temperature",
                "unit": "°C",
                "alarms": {"low": 90, "high": 110, "high_high": 120},
            }
        },
    )
    directory = session.start(tmp_path, config)
    raw = b"TC1\n125.2\n"
    session.write(raw)
    session.write_structured(ChannelUpdate(("TC1",), (125.2,)))
    session.stop("normal", len(raw))

    metadata = json.loads((directory / "session.json").read_text("utf-8"))
    assert metadata["channels"]["TC1"]["alarms"] == {
        "low": 90.0,
        "high": 110.0,
        "high_high": 120.0,
    }
    assert (directory / "raw.log").read_bytes() == raw
    assert "TC1" in (directory / "data.csv").read_text(encoding="utf-8").splitlines()[0]
    assert "Temperature" not in (directory / "data.csv").read_text(encoding="utf-8")


def test_custom_unit_is_stored_as_readable_string(tmp_path: Path) -> None:
    session = RecordingSession()
    directory = session.start(
        tmp_path,
        SessionConfig(
            session_name="Custom unit",
            device="COM4",
            baud_rate=9600,
            line_ending="LF",
            channels={"FLOW": {"alias": "Flow", "unit": "Nm³/h"}},
        ),
    )
    session.stop("normal", 0)
    metadata = json.loads((directory / "session.json").read_text("utf-8"))
    assert metadata["channels"]["FLOW"]["unit"] == "Nm³/h"
