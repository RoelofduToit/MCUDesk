import csv
from datetime import datetime, timezone
import json
from itertools import count

import pytest

from serialscope.data import EventMarker
from serialscope.logging import (
    EventLogger,
    EventLoggerError,
    MultiSourceRecordingSession,
    RecordingSessionError,
    RecordingSourceConfig,
)
from serialscope.parsing import ChannelUpdate
from serialscope.replay import ReplaySessionError, load_replay_session


class MonotonicClock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def _start_session(tmp_path, *, event_logger=None):
    clock = MonotonicClock()
    identifiers = count(1)
    session = MultiSourceRecordingSession(
        datetime_clock=lambda: datetime(2026, 8, 14, tzinfo=timezone.utc),
        monotonic_clock=clock,
        event_logger=event_logger,
        event_id_factory=lambda: f"event-{next(identifiers)}",
    )
    directory = session.start(
        tmp_path,
        "Heat test",
        (RecordingSourceConfig("pico", "Pico", "COM4", 115200),),
    )
    return session, directory, clock


def test_parent_session_events_use_stable_identity_and_elapsed_time(tmp_path) -> None:
    session, directory, clock = _start_session(tmp_path)
    clock.value = 112.375
    marker = session.add_event(session.elapsed_now(), " Valve opened ")
    session.stop_source("pico", "serial_disconnected")

    assert marker == EventMarker("event-1", 12.375, "Valve opened")
    assert session.event_logging_available
    session.stop("normal", {"pico": 0})
    with (directory / "events.csv").open(newline="", encoding="utf-8") as stream:
        assert list(csv.reader(stream)) == [
            ["elapsed_s", "event_id", "event"],
            ["12.375", "event-1", "Valve opened"],
        ]
    metadata = json.loads((directory / "session.json").read_text("utf-8"))
    assert metadata["events_file"] == "events.csv"
    assert metadata["event_count"] == 1
    assert not (directory / "Pico" / "events.csv").exists()
    assert (directory / "Pico" / "raw.log").read_bytes() == b""
    assert "event" not in (directory / "Pico" / "data.csv").read_text("utf-8")


def test_csv_round_trips_engineering_text_and_repeated_descriptions(tmp_path) -> None:
    session, directory, clock = _start_session(tmp_path)
    descriptions = (
        'Opened valve, then set "AUTO" at 450 °C',
        "Flow 12 µL/min",
        "Flow 12 µL/min",
    )
    for description in descriptions:
        clock.value += 1.0
        session.add_event(session.elapsed_now(), description)
    session.write_structured("pico", ChannelUpdate(("TC1",), (25.0,)))
    session.stop("normal", {"pico": 0})

    replay = load_replay_session(directory)
    assert tuple(marker.text for marker in replay.events) == descriptions
    assert len({marker.event_id for marker in replay.events}) == 3


def test_events_replay_and_sessions_without_events_file_are_supported(tmp_path) -> None:
    session, directory, clock = _start_session(tmp_path)
    clock.value = 101.5
    session.add_event(session.elapsed_now(), "Pump enabled")
    session.write_structured("pico", ChannelUpdate(("TC1",), (25.0,)))
    session.stop("normal", {"pico": 0})
    replay = load_replay_session(directory)
    assert replay.events == (EventMarker("event-1", 1.5, "Pump enabled"),)

    (directory / "events.csv").unlink()
    assert load_replay_session(directory).events == ()


def test_malformed_events_file_has_concise_replay_error(tmp_path) -> None:
    session, directory, _clock = _start_session(tmp_path)
    session.write_structured("pico", ChannelUpdate(("TC1",), (25.0,)))
    session.stop("normal", {"pico": 0})
    (directory / "events.csv").write_text("bad,header\n", encoding="utf-8")
    with pytest.raises(ReplaySessionError, match="events.csv"):
        load_replay_session(directory)


def test_event_write_failure_does_not_stop_measurement_recording(tmp_path) -> None:
    class FailingEventLogger(EventLogger):
        def write(self, marker: EventMarker) -> None:
            self._close_after_failure()
            raise EventLoggerError("disk unavailable")

    session, _directory, clock = _start_session(
        tmp_path, event_logger=FailingEventLogger()
    )
    clock.value = 102.0
    with pytest.raises(RecordingSessionError, match="disk unavailable"):
        session.add_event(session.elapsed_now(), "Will fail")

    assert session.is_recording
    assert not session.event_logging_available
    assert session.write("pico", b"measurement") == 11
    session.stop("normal", {"pico": 11})


def test_whitespace_event_is_rejected_without_csv_row(tmp_path) -> None:
    session, directory, clock = _start_session(tmp_path)
    clock.value = 110.0
    with pytest.raises(RecordingSessionError, match="empty"):
        session.add_event(session.elapsed_now(), "   ")
    assert session.events == ()
    session.stop("normal", {"pico": 0})
    with (directory / "events.csv").open(encoding="utf-8") as stream:
        assert len(stream.readlines()) == 1
