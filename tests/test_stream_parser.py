from serialscope.parsing import SerialStreamParser


def test_key_value_format_locks_on_first_confident_update() -> None:
    parser = SerialStreamParser()

    updates = parser.feed(b"TEMP=25.4,PRESSURE=2.51\n")

    assert parser.active_format == "key_value"
    assert updates[0].channels == {"TEMP": 25.4, "PRESSURE": 2.51}
    assert parser.feed(b"A,B\n1,2\n") == []


def test_explicit_csv_still_locks_on_first_data_row() -> None:
    parser = SerialStreamParser()

    updates = parser.feed(b"Count,Temperature\n1,25.4\n")

    assert parser.active_format == "csv"
    assert updates[0].channels == {"Count": 1, "Temperature": 25.4}


def test_headerless_csv_locks_after_confirmation() -> None:
    parser = SerialStreamParser()

    updates = parser.feed(b"1,2\n2,3\n3,4\n")

    assert parser.active_format == "csv"
    assert updates[0].channels == {"Channel 1": 3, "Channel 2": 4}


def test_reset_allows_a_different_format() -> None:
    parser = SerialStreamParser()
    parser.feed(b"TEMP=25.4,RPM=1500\n")

    parser.reset()
    updates = parser.feed(b"A,B\n1,2\n")

    assert parser.active_format == "csv"
    assert updates[0].channels == {"A": 1, "B": 2}
