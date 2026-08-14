from datetime import datetime, timezone
import csv
import json

import pytest

from serialscope.logging import (
    MultiSourceRecordingSession,
    RawLogger,
    RawLoggerError,
    RecordingSessionError,
    RecordingSourceConfig,
    StructuredCsvLogger,
)
from serialscope.logging.structured_csv_logger import StructuredCsvLoggerError
from serialscope.parsing import ChannelUpdate
from serialscope.replay import load_replay_session


class Clock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value


def test_multi_source_recording_is_separate_with_common_origin(tmp_path) -> None:
    monotonic = Clock()
    session = MultiSourceRecordingSession(
        datetime_clock=lambda: datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc),
        monotonic_clock=monotonic,
    )
    directory = session.start(
        tmp_path,
        "Overnight Test",
        (
            RecordingSourceConfig("pico", "Pi Pico", "COM4", 115200),
            RecordingSourceConfig("arduino", "Arduino Uno", "COM5", 9600),
        ),
    )
    monotonic.value = 100.125
    session.write("pico", b"pico raw\n")
    session.write_structured("pico", ChannelUpdate(("TC1",), (10,)))
    monotonic.value = 100.450
    session.write("arduino", b"arduino raw\n")
    session.write_structured("arduino", ChannelUpdate(("TC1", "RPM"), (20, 1500)))
    session.stop("normal", {"pico": 9, "arduino": 12})

    assert (directory / "Pi_Pico" / "raw.log").read_bytes() == b"pico raw\n"
    assert (directory / "Arduino_Uno" / "raw.log").read_bytes() == b"arduino raw\n"
    with (directory / "Pi_Pico" / "data.csv").open(newline="") as stream:
        pico_rows = list(csv.reader(stream))
    with (directory / "Arduino_Uno" / "data.csv").open(newline="") as stream:
        arduino_rows = list(csv.reader(stream))
    assert pico_rows == [["elapsed_s", "TC1"], ["0.125", "10"]]
    assert arduino_rows == [["elapsed_s", "TC1", "RPM"], ["0.450", "20", "1500"]]
    metadata = json.loads((directory / "session.json").read_text())
    assert [item["source_id"] for item in metadata["devices"]] == ["pico", "arduino"]
    assert metadata["common_time_origin"] == "host_monotonic_at_recording_start"

    replay = load_replay_session(directory)
    assert tuple(source.source_id for source in replay.sources) == ("pico", "arduino")
    assert replay.source("pico").latest_values["TC1"] == 10
    assert replay.source("arduino").latest_values["TC1"] == 20


def test_partial_logger_start_failure_closes_already_open_files(tmp_path) -> None:
    raw_loggers: list[RawLogger] = []

    def raw_factory() -> RawLogger:
        logger = RawLogger()
        raw_loggers.append(logger)
        return logger

    class FailingStructuredLogger(StructuredCsvLogger):
        def start(self, *_args, **_kwargs) -> None:
            raise StructuredCsvLoggerError("data.csv is read-only")

    session = MultiSourceRecordingSession(
        raw_logger_factory=raw_factory,
        structured_logger_factory=FailingStructuredLogger,
    )

    with pytest.raises(RecordingSessionError, match="read-only"):
        session.start(
            tmp_path,
            "Failure test",
            (RecordingSourceConfig("pico", "Pico", "COM4", 115200),),
        )

    assert raw_loggers and not raw_loggers[0].is_recording
    assert not session.is_recording


def test_metadata_start_failure_closes_all_source_loggers(
    tmp_path, monkeypatch
) -> None:
    session = MultiSourceRecordingSession()
    monkeypatch.setattr(
        "serialscope.logging.multi_session.atomic_write_json",
        lambda *_args: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(RecordingSessionError, match="disk full"):
        session.start(
            tmp_path,
            "Metadata failure",
            (
                RecordingSourceConfig("pico", "Pico", "COM4", 115200),
                RecordingSourceConfig("uno", "Uno", "COM5", 9600),
            ),
        )

    assert not session.is_recording
    assert session.active_source_ids == ()


def test_failed_device_logger_can_finalize_while_peer_continues(tmp_path) -> None:
    class FailingRawLogger(RawLogger):
        def write(self, _data: bytes) -> int:
            raise RawLoggerError("simulated disk failure")

    raw_loggers = iter((FailingRawLogger(), RawLogger()))
    session = MultiSourceRecordingSession(raw_logger_factory=lambda: next(raw_loggers))
    directory = session.start(
        tmp_path,
        "Two device run",
        (
            RecordingSourceConfig("pico", "Pico", "COM4", 115200),
            RecordingSourceConfig("uno", "Uno", "COM5", 9600),
        ),
    )

    with pytest.raises(RecordingSessionError, match="simulated disk failure"):
        session.write("pico", b"lost")
    session.stop_source("pico", "logging_error")
    assert session.active_source_ids == ("uno",)
    assert session.write("uno", b"preserved") == 9
    session.stop("normal", {"pico": 0, "uno": 9})

    metadata = json.loads((directory / "session.json").read_text("utf-8"))
    devices = {item["source_id"]: item for item in metadata["devices"]}
    assert devices["pico"]["end_reason"] == "logging_error"
    assert devices["uno"]["end_reason"] == "normal"
    assert (directory / "Uno" / "raw.log").read_bytes() == b"preserved"


def test_each_recording_source_snapshots_its_own_profile(tmp_path) -> None:
    session = MultiSourceRecordingSession()
    directory = session.start(
        tmp_path,
        "Profile experiment",
        (
            RecordingSourceConfig(
                "pico",
                "Pico",
                "COM4",
                115200,
                profile_id="pico-profile",
                profile_name="Reactor Pico",
                line_ending="CRLF",
            ),
            RecordingSourceConfig(
                "uno",
                "Arduino",
                "COM5",
                9600,
                profile_id="uno-profile",
                profile_name="Pressure Arduino",
            ),
        ),
    )
    session.stop("normal", {})
    devices = json.loads((directory / "session.json").read_text("utf-8"))["devices"]

    assert devices[0]["device_profile"]["profile_id"] == "pico-profile"
    assert devices[0]["line_ending"] == "CRLF"
    assert devices[1]["device_profile"]["profile_name"] == "Pressure Arduino"
