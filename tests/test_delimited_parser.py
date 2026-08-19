from serialscope.parsing import (
    ColumnMapping,
    CsvChannelParser,
    ParserConfiguration,
    SerialStreamParser,
)


def test_comma_semicolon_pipe_and_tab_delimiters() -> None:
    cases = (
        (",", b"23.4,25.1,101.3\n"),
        (";", b"23.4;25.1;101.3\n"),
        ("|", b"23.4|25.1|101.3\n"),
        ("\t", b"23.4\t25.1\t101.3\n"),
    )
    for delimiter, payload in cases:
        parser = CsvChannelParser(
            delimiter=delimiter,
            header_mode="none",
            columns=(
                ColumnMapping(0, "TC1"),
                ColumnMapping(1, "TC2"),
                ColumnMapping(2, "PRESSURE"),
            ),
        )
        assert parser.feed(payload)[0].channels == {
            "TC1": 23.4,
            "TC2": 25.1,
            "PRESSURE": 101.3,
        }


def test_header_present_uses_header_names() -> None:
    parser = CsvChannelParser(header_mode="present")
    assert parser.feed(b"TC1,TC2,PRESSURE,RPM\n") == []
    updates = parser.feed(b"23.4,25.1,101.3,1450\n")
    assert updates[0].channels == {
        "TC1": 23.4,
        "TC2": 25.1,
        "PRESSURE": 101.3,
        "RPM": 1450,
    }


def test_no_header_without_mapping_uses_generic_names_immediately() -> None:
    parser = CsvChannelParser(delimiter="|", header_mode="none")
    updates = parser.feed(b"23.4|25.1|101.3|1450\n")
    assert updates[0].channels == {
        "Channel 1": 23.4,
        "Channel 2": 25.1,
        "Channel 3": 101.3,
        "Channel 4": 1450,
    }


def test_manual_column_mapping_and_disabled_column() -> None:
    parser = CsvChannelParser(
        delimiter="|",
        header_mode="none",
        columns=(
            ColumnMapping(0, "TC1"),
            ColumnMapping(1, "TC2", enabled=False),
            ColumnMapping(2, "PRESSURE"),
            ColumnMapping(3, "RPM"),
        ),
    )
    updates = parser.feed(b"23.4|25.1|101.3|1450\n")
    assert updates[0].channels == {"TC1": 23.4, "PRESSURE": 101.3, "RPM": 1450}


def test_missing_extra_blank_and_invalid_fields_are_safe() -> None:
    parser = CsvChannelParser(
        delimiter="|",
        header_mode="none",
        columns=(
            ColumnMapping(0, "TC1"),
            ColumnMapping(1, "TC2"),
            ColumnMapping(2, "PRESSURE"),
            ColumnMapping(3, "RPM"),
        ),
    )
    assert parser.feed(b"\n") == []
    missing = parser.feed(b"23.4|25.1|101.3\n")
    assert missing[0].channels == {"TC1": 23.4, "TC2": 25.1, "PRESSURE": 101.3}
    extra = parser.feed(b"23.4|25.1|101.3|1450|99\n")
    assert extra[0].channels == {
        "TC1": 23.4,
        "TC2": 25.1,
        "PRESSURE": 101.3,
        "RPM": 1450,
    }
    blank = parser.feed(b"23.4||101.3|1450\n")
    assert blank[0].channels == {"TC1": 23.4, "PRESSURE": 101.3, "RPM": 1450}
    invalid = parser.feed(b"23.4|nope|101.3|1450\n")
    assert invalid[0].channels == {"TC1": 23.4, "PRESSURE": 101.3, "RPM": 1450}


def test_whitespace_is_trimmed_before_numeric_parse() -> None:
    parser = CsvChannelParser(
        delimiter="|",
        header_mode="none",
        columns=(ColumnMapping(0, "TC1"), ColumnMapping(1, "TC2")),
    )
    updates = parser.feed(b" 23.4 | 25.1 \n")
    assert updates[0].channels == {"TC1": 23.4, "TC2": 25.1}


def test_forced_delimited_mode_does_not_use_json_or_key_value() -> None:
    parser = SerialStreamParser(
        ParserConfiguration(
            mode="delimited",
            delimiter="|",
            header_mode="none",
            columns=(ColumnMapping(0, "TC1"), ColumnMapping(1, "TC2")),
        )
    )
    assert parser.feed(b'{"TC1":1,"TC2":2}\n') == []
    updates = parser.feed(b"23.4|25.1\n")
    assert updates[0].channels == {"TC1": 23.4, "TC2": 25.1}
