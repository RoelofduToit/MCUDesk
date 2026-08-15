import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from serialscope.logging import (
    MultiSourceRecordingSession,
    RecordingRecoveryError,
    RecordingSourceConfig,
    RecordingSession,
    SessionConfig,
    discard_interrupted_recording,
    find_interrupted_recordings,
    inspect_interrupted_recording,
    is_interrupted_recording,
    recover_interrupted_recording,
)
from serialscope.logging.recovery import IN_PROGRESS_NAME, in_progress_path
from serialscope.parsing import ChannelUpdate
from serialscope.replay import load_replay_session


def _config(session_name: str = "Interrupted run") -> SessionConfig:
    return SessionConfig(
        session_name=session_name,
        device="COM4",
        baud_rate=115200,
        line_ending="LF",
    )


def _write_session_json(directory: Path, **fields: object) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    metadata = {
        "session_name": directory.name,
        "status": "recording",
        "recording_start_local": "2026-08-16T12:00:00+00:00",
        "structured_data_delimiter": ",",
        "events_file": "events.csv",
        "session_id": "session-a",
    }
    metadata.update(fields)
    (directory / "session.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


def _write_data_csv(
    path: Path, rows: list[list[object]], *, delimiter: str = ",", extra: str = ""
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter=delimiter)
        writer.writerow(["elapsed_s", "TC1", "TC2"])
        writer.writerows(rows)
    if extra:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(extra)


def _write_events_csv(path: Path, rows: list[list[object]], *, extra: str = "") -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["elapsed_s", "event_id", "event"])
        writer.writerows(rows)
    if extra:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(extra)


def _simulate_crash(session: RecordingSession | MultiSourceRecordingSession) -> None:
    """Close open log handles without finalizing metadata, as a process death would."""
    if isinstance(session, MultiSourceRecordingSession):
        for item in session._sources.values():
            try:
                item.raw.stop()
            except Exception:
                pass
            try:
                item.structured.stop()
            except Exception:
                pass
        try:
            session._event_logger.stop()
        except Exception:
            pass
        session._clear_active_state()
        return
    try:
        session._raw_logger.stop()
    except Exception:
        pass
    try:
        session._structured_logger.stop()
    except Exception:
        pass
    try:
        session._event_logger.stop()
    except Exception:
        pass
    session._clear_active_state()


def _abandoned_session(tmp_path: Path, name: str = "Crash test") -> Path:
    session = RecordingSession()
    directory = session.start(tmp_path, _config(name))
    session.write(b"raw line\n")
    session.write_structured(ChannelUpdate(("TC1", "TC2"), (21.5, 98.0)))
    session.write_structured(ChannelUpdate(("TC1", "TC2"), (22.0, 97.5)))
    session.flush()
    _simulate_crash(session)
    return directory


def test_abandoned_recording_is_detected_as_interrupted(tmp_path: Path) -> None:
    directory = _abandoned_session(tmp_path)

    assert (directory / IN_PROGRESS_NAME).is_file()
    assert is_interrupted_recording(directory)
    inspected = inspect_interrupted_recording(directory)
    assert inspected is not None
    assert inspected.session_name == "Crash test"
    assert inspected.started_local
    assert inspected.sample_count == 2
    assert inspected.logged_bytes == len(b"raw line\n")
    found = find_interrupted_recordings((directory,))
    assert [item.directory for item in found] == [directory]


def test_recovered_session_preserves_valid_data_and_is_replayable(tmp_path: Path) -> None:
    directory = _abandoned_session(tmp_path, "Recover me")

    recovered = recover_interrupted_recording(directory)

    assert not is_interrupted_recording(directory)
    assert not (directory / IN_PROGRESS_NAME).exists()
    metadata = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert metadata["end_reason"] == "recovered"
    assert metadata["recovered"] is True
    assert recovered.sample_count == 2
    replay = load_replay_session(directory)
    assert replay.name == "Recover me"
    assert [sample.values["TC1"] for sample in replay.samples] == [21.5, 22.0]
    assert (directory / "raw.log").read_bytes() == b"raw line\n"


def test_normal_recordings_are_not_marked_interrupted(tmp_path: Path) -> None:
    session = RecordingSession()
    directory = session.start(tmp_path, _config("Clean run"))
    session.write(b"ok\n")
    session.write_structured(ChannelUpdate(("TC1",), (1.0,)))
    session.flush()
    assert is_interrupted_recording(directory)
    session.stop("normal", 3)

    metadata = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert metadata["end_reason"] == "normal"
    assert "recovered" not in metadata
    assert not (directory / IN_PROGRESS_NAME).exists()
    assert not is_interrupted_recording(directory)
    assert find_interrupted_recordings((directory,)) == ()


def test_partial_trailing_row_does_not_destroy_recovery(tmp_path: Path) -> None:
    directory = tmp_path / "Partial_2026-08-16_1200"
    _write_session_json(directory, session_name="Partial tail")
    _write_data_csv(
        directory / "data.csv",
        [["0.000", "10", "20"], ["0.250", "11", "21"]],
        extra="0.500,12",
    )
    (directory / "raw.log").write_bytes(b"partial raw")
    _write_events_csv(
        directory / "events.csv",
        [["0.1", "evt-1", "note"]],
        extra="0.2,evt-2",
    )
    (directory / IN_PROGRESS_NAME).write_text("{}", encoding="utf-8")

    recovered = recover_interrupted_recording(directory)

    assert recovered.sample_count == 2
    replay = load_replay_session(directory)
    assert [sample.elapsed_s for sample in replay.samples] == [0.0, 0.25]
    assert replay.events[0].event_id == "evt-1"
    assert len(replay.events) == 1
    data = (directory / "data.csv").read_text(encoding="utf-8")
    assert "0.500,12,2" not in data
    assert "0.250,11,21" in data.replace(" ", "")


def test_discarding_interrupted_recording_keeps_files(tmp_path: Path) -> None:
    directory = _abandoned_session(tmp_path, "Discard me")
    raw = (directory / "raw.log").read_bytes()
    csv_text = (directory / "data.csv").read_text(encoding="utf-8")

    discard_interrupted_recording(directory)

    assert not is_interrupted_recording(directory)
    assert not (directory / IN_PROGRESS_NAME).exists()
    metadata = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "discarded"
    assert metadata["end_reason"] == "discarded"
    assert (directory / "raw.log").read_bytes() == raw
    assert (directory / "data.csv").read_text(encoding="utf-8") == csv_text
    assert directory.is_dir()


def test_recovering_one_session_does_not_overwrite_another(tmp_path: Path) -> None:
    first = tmp_path / "First_2026-08-16_1200"
    second = tmp_path / "Second_2026-08-16_1201"
    _write_session_json(first, session_name="First", session_id="id-first")
    _write_data_csv(first / "data.csv", [["0.000", "1", "2"]])
    (first / "raw.log").write_bytes(b"first")
    (first / IN_PROGRESS_NAME).write_text("{}", encoding="utf-8")
    _write_session_json(
        second,
        session_name="Second",
        session_id="id-second",
        status="completed",
        end_reason="normal",
        recovered=False,
    )
    _write_data_csv(second / "data.csv", [["0.000", "9", "8"], ["1.000", "7", "6"]])
    (second / "raw.log").write_bytes(b"second-complete")
    original_second = (second / "session.json").read_text(encoding="utf-8")
    original_second_csv = (second / "data.csv").read_text(encoding="utf-8")

    recover_interrupted_recording(first)

    assert json.loads((first / "session.json").read_text(encoding="utf-8"))[
        "session_id"
    ] == "id-first"
    assert (second / "session.json").read_text(encoding="utf-8") == original_second
    assert (second / "data.csv").read_text(encoding="utf-8") == original_second_csv
    assert (second / "raw.log").read_bytes() == b"second-complete"
    with pytest.raises(RecordingRecoveryError, match="already complete"):
        recover_interrupted_recording(second)
    assert (second / "session.json").read_text(encoding="utf-8") == original_second


def test_multiple_interrupted_sessions_are_handled_independently(tmp_path: Path) -> None:
    first = tmp_path / "Alpha_2026-08-16_1000"
    second = tmp_path / "Beta_2026-08-16_1001"
    _write_session_json(first, session_name="Alpha", session_id="alpha")
    _write_data_csv(first / "data.csv", [["0.000", "1", "2"], ["0.100", "3", "4"]])
    (first / "raw.log").write_bytes(b"alpha")
    (first / IN_PROGRESS_NAME).write_text("{}", encoding="utf-8")
    _write_session_json(second, session_name="Beta", session_id="beta")
    _write_data_csv(second / "data.csv", [["0.000", "5", "6"]])
    (second / "raw.log").write_bytes(b"beta")
    (second / IN_PROGRESS_NAME).write_text("{}", encoding="utf-8")

    found = find_interrupted_recordings((first, second, first))
    assert [item.session_name for item in found] == ["Alpha", "Beta"]

    recover_interrupted_recording(first)
    assert not is_interrupted_recording(first)
    assert is_interrupted_recording(second)
    discard_interrupted_recording(second)
    assert not is_interrupted_recording(second)
    assert json.loads((first / "session.json").read_text(encoding="utf-8"))[
        "end_reason"
    ] == "recovered"
    assert json.loads((second / "session.json").read_text(encoding="utf-8"))[
        "status"
    ] == "discarded"
    replay = load_replay_session(first)
    assert replay.samples[0].values["TC1"] == 1


def test_normal_stop_removes_in_progress_state(tmp_path: Path) -> None:
    session = RecordingSession()
    directory = session.start(tmp_path, _config("Finalize"))
    assert in_progress_path(directory).is_file()
    session.write(b"bytes")
    session.write_structured(ChannelUpdate(("TC1",), (4.0,)))
    session.flush()
    checkpoint = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "recording"
    assert checkpoint["last_checkpoint_utc"]
    session.stop("user_stopped", 5)

    assert not in_progress_path(directory).exists()
    metadata = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert metadata["end_reason"] == "user_stopped"
    assert not is_interrupted_recording(directory)


def test_multi_source_abandoned_session_can_be_recovered(tmp_path: Path) -> None:
    session = MultiSourceRecordingSession(
        datetime_clock=lambda: datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    )
    directory = session.start(
        tmp_path,
        "Overnight",
        (
            RecordingSourceConfig("pico", "Pi Pico", "COM4", 115200),
            RecordingSourceConfig("uno", "Arduino", "COM5", 9600),
        ),
    )
    session.write("pico", b"pico\n")
    session.write_structured("pico", ChannelUpdate(("TC1",), (10,)))
    session.write("uno", b"uno\n")
    session.write_structured("uno", ChannelUpdate(("RPM",), (1500,)))
    session.flush()
    _simulate_crash(session)

    assert is_interrupted_recording(directory)
    recovered = recover_interrupted_recording(directory)
    assert recovered.sample_count == 2
    replay = load_replay_session(directory)
    assert replay.source("pico").latest_values["TC1"] == 10
    assert replay.source("uno").latest_values["RPM"] == 1500
    metadata = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    assert metadata["recovered"] is True
    assert metadata["devices"][0]["end_reason"] == "recovered"


def test_unique_session_directories_prevent_overwrite(tmp_path: Path) -> None:
    clock_time = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    first = RecordingSession(clock=lambda: clock_time)
    first_dir = first.start(tmp_path, _config("Same name"))
    first.stop("normal", 0)
    second = RecordingSession(clock=lambda: clock_time)
    second_dir = second.start(tmp_path, _config("Same name"))

    assert first_dir != second_dir
    assert first_dir.name != second_dir.name
    assert (first_dir / "session.json").is_file()
    assert json.loads((first_dir / "session.json").read_text(encoding="utf-8"))[
        "status"
    ] == "completed"
    second.stop("normal", 0)
