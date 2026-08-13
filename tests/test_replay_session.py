import csv
import json
from pathlib import Path

import pytest

from serialscope.replay import ReplaySessionError, load_replay_session


def write_session(
    directory: Path,
    *,
    delimiter: str = ",",
    rows: list[list[str]] | None = None,
    metadata_extra: dict[str, object] | None = None,
) -> Path:
    directory.mkdir()
    metadata = {
        "session_name": "Bench run",
        "serialscope_version": "0.5.2",
        "structured_data_delimiter": delimiter,
        "serial": {"device": "COM4", "baud_rate": 115200},
    }
    metadata.update(metadata_extra or {})
    (directory / "session.json").write_text(json.dumps(metadata), encoding="utf-8")
    with (directory / "data.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter=delimiter)
        writer.writerow(["elapsed_s", "Temperature", "RPM"])
        writer.writerows(rows or [["0", "20", ""], ["0.75", "20.5", "1500"]])
    return directory


@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
def test_loads_supported_delimiters_and_preserves_irregular_timestamps(
    tmp_path: Path, delimiter: str
) -> None:
    session = load_replay_session(write_session(tmp_path / "session", delimiter=delimiter))

    assert session.name == "Bench run"
    assert session.channel_names == ("Temperature", "RPM")
    assert [sample.elapsed_s for sample in session.samples] == [0.0, 0.75]
    assert session.samples[0].values["RPM"] is None
    assert session.latest_values == {"Temperature": 20.5, "RPM": 1500}


def test_long_recording_is_loaded_without_live_history_truncation(tmp_path: Path) -> None:
    session = load_replay_session(
        write_session(
            tmp_path / "long",
            rows=[["0", "1", ""], ["3600", "2", "10"], ["7200", "3", "11"]],
        )
    )

    assert session.points("Temperature")[0] == (0.0, 3600.0, 7200.0)
    assert session.points("RPM")[0] == (3600.0, 7200.0)


@pytest.mark.parametrize(
    ("missing", "message"),
    [("session.json", "session.json"), ("data.csv", "data.csv")],
)
def test_missing_required_file_is_rejected(tmp_path: Path, missing: str, message: str) -> None:
    directory = write_session(tmp_path / "session")
    (directory / missing).unlink()
    with pytest.raises(ReplaySessionError, match=message):
        load_replay_session(directory)


def test_malformed_metadata_is_rejected(tmp_path: Path) -> None:
    directory = write_session(tmp_path / "session")
    (directory / "session.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(ReplaySessionError, match="malformed"):
        load_replay_session(directory)


@pytest.mark.parametrize(
    "rows",
    [[], [["bad", "1", "2"]], [["0", "not numeric", "2"]], [["0", "1"]]],
)
def test_empty_or_malformed_data_is_rejected(tmp_path: Path, rows: list[list[str]]) -> None:
    directory = write_session(tmp_path / "session", rows=rows or [["0", "1", "2"]])
    if not rows:
        (directory / "data.csv").write_text("elapsed_s,Temperature,RPM\n", encoding="utf-8")
    with pytest.raises(ReplaySessionError):
        load_replay_session(directory)


def test_unknown_metadata_and_old_version_are_tolerated(tmp_path: Path) -> None:
    session = load_replay_session(
        write_session(
            tmp_path / "session",
            metadata_extra={"serialscope_version": "0.1.0", "future_field": {"x": 1}},
        )
    )
    assert session.metadata["future_field"] == {"x": 1}
