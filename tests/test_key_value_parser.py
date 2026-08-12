from serialscope.parsing import KeyValueChannelParser


def test_normal_key_value_line_detects_numeric_channels() -> None:
    parser = KeyValueChannelParser()

    updates = parser.feed(b"TEMP=25.4,PRESSURE=2.51,RPM=1487\n")

    assert updates[0].channels == {
        "TEMP": 25.4,
        "PRESSURE": 2.51,
        "RPM": 1487,
    }
    assert not updates[0].replace_channels


def test_spaces_negative_and_scientific_values_are_supported() -> None:
    parser = KeyValueChannelParser()

    updates = parser.feed(b" TEMP = -12.4 , FLOW = 1.25e-3 , RPM = 1500 \n")

    assert updates[0].channels == {
        "TEMP": -12.4,
        "FLOW": 0.00125,
        "RPM": 1500,
    }


def test_split_chunks_multiple_lines_and_crlf_are_supported() -> None:
    parser = KeyValueChannelParser()

    assert parser.feed(b"TEMP=25.") == []
    updates = parser.feed(
        b"4,PRESSURE=2.51\r\nTEMP=25.6,PRESSURE=2.49\r\n"
    )

    assert [update.channels for update in updates] == [
        {"TEMP": 25.4, "PRESSURE": 2.51},
        {"TEMP": 25.6, "PRESSURE": 2.49},
    ]


def test_malformed_and_nonnumeric_items_are_ignored_safely() -> None:
    parser = KeyValueChannelParser()

    updates = parser.feed(
        b"TEMP=25.4,BROKEN,=2.0,RPM=1500,NOTE=abc,EMPTY=\n"
    )

    assert updates[0].channels == {"TEMP": 25.4, "RPM": 1500}
    assert parser.feed(b"TEMP=abc,RPM=\n") == []


def test_fewer_than_two_valid_pairs_is_not_detected() -> None:
    parser = KeyValueChannelParser()

    assert parser.feed(b"TEMP=25.4,BROKEN\n") == []
