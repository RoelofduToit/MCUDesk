"""Required sample formats and malformed-input behavior."""

from serialscope.parsing import (
    ColumnMapping,
    ParserConfiguration,
    SerialStreamParser,
)
from serialscope.replay import load_replay_session
import csv
import json
from pathlib import Path


def test_sample_a_header_present_csv() -> None:
    parser = SerialStreamParser(
        ParserConfiguration(mode="delimited", delimiter=",", header_mode="present")
    )
    updates = parser.feed(
        b"TC1,TC2,PRESSURE,RPM\n23.4,25.1,101.3,1450\n"
    )
    assert updates[0].channels == {
        "TC1": 23.4,
        "TC2": 25.1,
        "PRESSURE": 101.3,
        "RPM": 1450,
    }


def test_sample_b_pipe_mapped_headerless() -> None:
    parser = SerialStreamParser(
        ParserConfiguration(
            mode="delimited",
            delimiter="|",
            header_mode="none",
            columns=(
                ColumnMapping(0, "TC1"),
                ColumnMapping(1, "TC2"),
                ColumnMapping(2, "PRESSURE"),
                ColumnMapping(3, "RPM"),
            ),
        )
    )
    updates = parser.feed(b"23.4|25.1|101.3|1450\n")
    assert updates[0].channels == {
        "TC1": 23.4,
        "TC2": 25.1,
        "PRESSURE": 101.3,
        "RPM": 1450,
    }


def test_sample_c_semicolon_colon_key_value() -> None:
    parser = SerialStreamParser(
        ParserConfiguration(
            mode="key_value",
            pair_separator=";",
            name_value_separator=":",
        )
    )
    updates = parser.feed(b"TEMP:23.4;PRESS:101.3;RPM:1450\n")
    assert updates[0].channels == {"TEMP": 23.4, "PRESS": 101.3, "RPM": 1450}


def test_sample_d_json_lines() -> None:
    parser = SerialStreamParser(ParserConfiguration(mode="json"))
    updates = parser.feed(
        b'{"TC1":23.4,"TC2":25.1,"PRESSURE":101.3,"RPM":1450}\n'
    )
    assert updates[0].channels == {
        "TC1": 23.4,
        "TC2": 25.1,
        "PRESSURE": 101.3,
        "RPM": 1450,
    }


def test_malformed_samples_do_not_crash_or_invent_values() -> None:
    mapped = SerialStreamParser(
        ParserConfiguration(
            mode="delimited",
            delimiter="|",
            header_mode="none",
            columns=(
                ColumnMapping(0, "TC1"),
                ColumnMapping(1, "TC2"),
                ColumnMapping(2, "PRESSURE"),
                ColumnMapping(3, "RPM"),
            ),
        )
    )
    assert mapped.feed(b"\n") == []
    assert mapped.feed(b"not-a-row\n") == []
    missing = mapped.feed(b"23.4|25.1\n")
    assert missing[0].channels == {"TC1": 23.4, "TC2": 25.1}
    extra = mapped.feed(b"23.4|25.1|101.3|1450|99\n")
    assert extra[0].channels == {
        "TC1": 23.4,
        "TC2": 25.1,
        "PRESSURE": 101.3,
        "RPM": 1450,
    }
    invalid = mapped.feed(b"23.4|abc|101.3|1450\n")
    assert invalid[0].channels == {"TC1": 23.4, "PRESSURE": 101.3, "RPM": 1450}

    key_value = SerialStreamParser(
        ParserConfiguration(
            mode="key_value",
            pair_separator=";",
            name_value_separator=":",
        )
    )
    assert key_value.feed(b"TEMP:abc;PRESS:\n") == []
    assert key_value.feed(b'{"broken":\n') == []

    json_parser = SerialStreamParser(ParserConfiguration(mode="json"))
    assert json_parser.feed(b"{not json}\n") == []
    assert json_parser.feed(b"23.4|25.1\n") == []


def test_replay_ignores_parser_metadata_and_loads_structured_csv(
    tmp_path: Path,
) -> None:
    path = tmp_path / "session"
    path.mkdir()
    (path / "session.json").write_text(
        json.dumps(
            {
                "session_name": "Mapped soak",
                "serialscope_version": "0.13.0",
                "structured_data_delimiter": ",",
                "parser": {
                    "mode": "delimited",
                    "delimiter": "|",
                    "header_mode": "none",
                },
                "serial": {"device": "COM4", "baud_rate": 115200},
                "elapsed_seconds": 1,
                "structured_row_count": 1,
                "channels": {"TC1": {"alias": "", "unit": ""}},
            }
        ),
        encoding="utf-8",
    )
    with (path / "data.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerows([["elapsed_s", "TC1", "RPM"], ["0.5", "23.4", "1450"]])
    session = load_replay_session(path)
    assert session.channel_names == ("TC1", "RPM")
    assert session.latest_values["TC1"] == 23.4
    assert session.latest_values["RPM"] == 1450
