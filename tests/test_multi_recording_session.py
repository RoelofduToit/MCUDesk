from datetime import datetime, timezone
import csv
import json

from serialscope.logging import MultiSourceRecordingSession, RecordingSourceConfig
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
