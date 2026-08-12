import pytest

from serialscope.parsing import CsvChannelParser


def test_complete_header_and_numeric_row_are_detected() -> None:
    parser = CsvChannelParser()

    updates = parser.feed(
        b"Count,Temperature_C,Pressure_bar,RPM\n2,25.08,2.471,1506\n"
    )

    assert parser.header == ("Count", "Temperature_C", "Pressure_bar", "RPM")
    assert updates[0].channels == {
        "Count": 2,
        "Temperature_C": 25.08,
        "Pressure_bar": 2.471,
        "RPM": 1506,
    }
    assert isinstance(updates[0].channels["Count"], int)
    assert isinstance(updates[0].channels["Temperature_C"], float)


def test_header_and_data_row_can_span_arbitrary_chunks() -> None:
    parser = CsvChannelParser()

    assert parser.feed(b"Count,Temper") == []
    assert parser.feed(b"ature_C,Pressure_bar,RPM\n0,24.") == []
    updates = parser.feed(b"72,2.486,1517\n")

    assert updates[0].channels == {
        "Count": 0,
        "Temperature_C": 24.72,
        "Pressure_bar": 2.486,
        "RPM": 1517,
    }


def test_multiple_crlf_lines_in_one_chunk_produce_multiple_updates() -> None:
    parser = CsvChannelParser()

    updates = parser.feed(b"A,B\r\n1,2.5\r\n2,3.5\r\n")

    assert [update.channels for update in updates] == [
        {"A": 1, "B": 2.5},
        {"A": 2, "B": 3.5},
    ]


@pytest.mark.parametrize(
    "header",
    [
        b"OnlyOne\n",
        b"A,,C\n",
        b"A,A\n",
        b"1,2\n",
        b"A,2\n",
    ],
)
def test_invalid_or_numeric_header_is_rejected(header: bytes) -> None:
    parser = CsvChannelParser()

    assert parser.feed(header) == []
    assert parser.header is None


def test_malformed_and_wrong_width_rows_do_not_destroy_channels() -> None:
    parser = CsvChannelParser()
    parser.feed(b"A,B,C\n")

    assert parser.feed(b"1,2\n") == []
    assert parser.feed(b'"unterminated,2,3\n') == []
    assert parser.feed(b"1,nope,3\n") == []
    updates = parser.feed(b"4,5,6\n")

    assert parser.header == ("A", "B", "C")
    assert updates[0].channels == {"A": 4, "B": 5, "C": 6}


def test_reset_discards_header_and_partial_line() -> None:
    parser = CsvChannelParser()
    parser.feed(b"Old,Header\n1,")

    parser.reset()
    updates = parser.feed(b"New,Channels\n7,8\n")

    assert parser.header == ("New", "Channels")
    assert updates[0].channels == {"New": 7, "Channels": 8}


def test_three_consistent_numeric_rows_create_generic_channels() -> None:
    parser = CsvChannelParser()

    assert parser.feed(b"3,25.82,2.502,1512\n") == []
    assert parser.feed(b"4,24.72,2.448,1466\n") == []
    updates = parser.feed(b"5,24.60,2.402,1509\n")

    assert parser.header == (
        "Channel 1",
        "Channel 2",
        "Channel 3",
        "Channel 4",
    )
    assert updates[0].channels == {
        "Channel 1": 5,
        "Channel 2": 24.6,
        "Channel 3": 2.402,
        "Channel 4": 1509,
    }
    assert isinstance(updates[0].channels["Channel 1"], int)
    assert isinstance(updates[0].channels["Channel 2"], float)


def test_one_or_two_numeric_rows_do_not_create_channels() -> None:
    parser = CsvChannelParser()

    assert parser.feed(b"1,2.5\n2,3.5\n") == []
    assert parser.header is None


def test_generic_channels_continue_with_latest_values() -> None:
    parser = CsvChannelParser()
    parser.feed(b"1,1.1\n2,2.2\n3,3.3\n")

    updates = parser.feed(b"4,4.4\n5,5.5\n")

    assert [update.channels for update in updates] == [
        {"Channel 1": 4, "Channel 2": 4.4},
        {"Channel 1": 5, "Channel 2": 5.5},
    ]


def test_inconsistent_width_prevents_false_headerless_detection() -> None:
    parser = CsvChannelParser()

    updates = parser.feed(b"1,2\n1,2,3\n4,5\n6,7\n")

    assert updates == []
    assert parser.header is None
    confirmed = parser.feed(b"8,9\n")
    assert confirmed[0].channels == {"Channel 1": 8, "Channel 2": 9}


def test_malformed_line_resets_unconfirmed_numeric_candidate() -> None:
    parser = CsvChannelParser()

    assert parser.feed(b'1,2\n2,3\n"unterminated,4\n3,4\n') == []
    assert parser.header is None
    assert parser.feed(b"4,5\n") == []
    updates = parser.feed(b"5,6\n")

    assert updates[0].channels == {"Channel 1": 5, "Channel 2": 6}


def test_real_header_replaces_generic_names_immediately() -> None:
    parser = CsvChannelParser()
    parser.feed(b"3,25.82,2.502,1512\n4,24.72,2.448,1466\n5,24.60,2.402,1509\n")

    renamed = parser.feed(b"Count,Temperature_C,Pressure_bar,RPM\n")

    assert parser.header == ("Count", "Temperature_C", "Pressure_bar", "RPM")
    assert renamed[0].channels == {
        "Count": 5,
        "Temperature_C": 24.6,
        "Pressure_bar": 2.402,
        "RPM": 1509,
    }
    updates = parser.feed(b"6,25.10,2.500,1510\n")
    assert updates[0].channels["Count"] == 6


def test_headerless_detection_supports_partial_chunks_and_crlf() -> None:
    parser = CsvChannelParser()

    assert parser.feed(b"1,2.") == []
    assert parser.feed(b"5\r\n2,3.5\r") == []
    updates = parser.feed(b"\n3,4.5\r\n")

    assert updates[0].channels == {"Channel 1": 3, "Channel 2": 4.5}


def test_key_value_line_is_not_claimed_as_csv_header() -> None:
    parser = CsvChannelParser()

    assert parser.feed(b"TEMP=25.4,PRESSURE=2.51,RPM=1487\n") == []
    assert parser.header is None
