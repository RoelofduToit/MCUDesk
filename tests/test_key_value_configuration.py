from serialscope.parsing import KeyValueChannelParser, ParserConfiguration, SerialStreamParser


def test_comma_equals_and_semicolon_colon_are_supported() -> None:
    comma = KeyValueChannelParser()
    colon = KeyValueChannelParser(
        pair_separator=";",
        name_value_separator=":",
        min_pairs=1,
    )
    assert comma.feed(b"TEMP=25.4,PRESSURE=2.51,RPM=1487\n")[0].channels == {
        "TEMP": 25.4,
        "PRESSURE": 2.51,
        "RPM": 1487,
    }
    assert colon.feed(b"TEMP:23.4;PRESS:101.3;RPM:1450\n")[0].channels == {
        "TEMP": 23.4,
        "PRESS": 101.3,
        "RPM": 1450,
    }


def test_key_value_trims_whitespace_around_separators() -> None:
    parser = KeyValueChannelParser(
        pair_separator=";",
        name_value_separator=":",
        min_pairs=1,
    )
    updates = parser.feed(b" TEMP : 23.4 ; PRESS : 101.3 \n")
    assert updates[0].channels == {"TEMP": 23.4, "PRESS": 101.3}


def test_malformed_missing_duplicate_and_invalid_pairs_are_skipped() -> None:
    parser = KeyValueChannelParser(
        pair_separator=";",
        name_value_separator=":",
        min_pairs=1,
    )
    updates = parser.feed(
        b"TEMP:23.4;BROKEN;PRESS:;PRESS:101.3;NOTE:abc;RPM:1450\n"
    )
    assert updates[0].channels == {"TEMP": 23.4, "PRESS": 101.3, "RPM": 1450}
    assert parser.feed(b"TEMP:abc\n") == []


def test_forced_key_value_mode_accepts_a_single_pair() -> None:
    parser = SerialStreamParser(
        ParserConfiguration(
            mode="key_value",
            pair_separator=";",
            name_value_separator=":",
        )
    )
    updates = parser.feed(b"TEMP:23.4\n")
    assert updates[0].channels == {"TEMP": 23.4}
    assert parser.feed(b"23.4|25.1\n") == []
