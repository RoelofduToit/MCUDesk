from serialscope.parsing import JsonChannelParser, ParserConfiguration, SerialStreamParser


def test_valid_json_exposes_numeric_channels() -> None:
    parser = JsonChannelParser()

    updates = parser.feed(b'{"RPM":1500,"TEMP":-12.4,"FLOW":0.00125}\n')

    assert updates[0].channels == {"RPM": 1500, "TEMP": -12.4, "FLOW": 0.00125}
    assert updates[0].replace_channels is False


def test_partial_json_waits_for_complete_line() -> None:
    parser = JsonChannelParser()

    assert parser.feed(b'{"TC1":10') == []
    assert parser.feed(b'0.4,"TC2":98.7}') == []
    assert parser.feed(b"\n")[0].channels == {"TC1": 100.4, "TC2": 98.7}


def test_multiple_crlf_json_lines_are_parsed() -> None:
    parser = JsonChannelParser()

    updates = parser.feed(b'{"A":1}\r\n{"A":2.5}\r\n')

    assert [update.channels for update in updates] == [{"A": 1}, {"A": 2.5}]


def test_malformed_json_and_arrays_are_rejected() -> None:
    parser = JsonChannelParser()

    assert parser.feed(b'{"A":1,\n[1,2,3]\n') == []


def test_unsupported_values_are_ignored() -> None:
    parser = JsonChannelParser()

    updates = parser.feed(
        b'{"number":2,"nested":{"A":1},"items":[1],'
        b'"enabled":true,"missing":null,"label":"two"}\n'
    )

    assert updates[0].channels == {"number": 2}


def test_later_objects_can_add_and_omit_numeric_keys() -> None:
    parser = JsonChannelParser()

    updates = parser.feed(
        b'{"TC1":100.4,"TC2":98.7}\n'
        b'{"TC1":101.2,"TC2":99.1,"TC3":105.7}\n'
        b'{"TC1":101.4,"TC3":105.5}\n'
    )

    assert updates[1].channels == {"TC1": 101.2, "TC2": 99.1, "TC3": 105.7}
    assert updates[2].channels == {"TC1": 101.4, "TC3": 105.5}
    assert all(not update.replace_channels for update in updates)


def test_object_without_numeric_values_is_ignored() -> None:
    parser = JsonChannelParser()

    assert parser.feed(b'{"enabled":false,"label":"idle"}\n') == []


def test_nonstandard_and_non_finite_numbers_are_ignored() -> None:
    parser = JsonChannelParser()

    assert parser.feed(b'{"A":NaN}\n{"A":1e400}\n') == []


def test_reset_discards_an_incomplete_line() -> None:
    parser = JsonChannelParser()
    parser.feed(b'{"old":1')

    parser.reset()

    assert parser.feed(b'{"new":2}\n')[0].channels == {"new": 2}


def test_forced_json_mode_keeps_existing_object_behavior() -> None:
    parser = SerialStreamParser(ParserConfiguration(mode="json"))
    updates = parser.feed(b'{"TC1":23.4,"TC2":25.1,"PRESSURE":101.3,"RPM":1450}\n')
    assert updates[0].channels == {
        "TC1": 23.4,
        "TC2": 25.1,
        "PRESSURE": 101.3,
        "RPM": 1450,
    }
    assert parser.feed(b"23.4|25.1|101.3|1450\n") == []
