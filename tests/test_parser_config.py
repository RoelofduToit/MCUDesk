from serialscope.parsing import (
    ColumnMapping,
    ParserConfiguration,
    ParserConfigurationError,
    SerialStreamParser,
    preview_sample,
)
from serialscope.parsing.parser_config import generic_channel_name
import pytest


def test_default_configuration_matches_legacy_auto_behavior() -> None:
    configuration = ParserConfiguration()
    assert configuration.mode == "auto"
    assert configuration.is_default
    parser = SerialStreamParser(configuration)
    updates = parser.feed(b"Count,Temperature\n1,25.4\n")
    assert parser.active_format == "csv"
    assert updates[0].channels == {"Count": 1, "Temperature": 25.4}


def test_serialization_round_trip_preserves_mapping() -> None:
    original = ParserConfiguration(
        mode="delimited",
        delimiter="|",
        header_mode="none",
        columns=(
            ColumnMapping(0, "TC1"),
            ColumnMapping(1, "TC2"),
            ColumnMapping(2, "PRESSURE"),
            ColumnMapping(3, "RPM", enabled=False),
        ),
    )
    restored = ParserConfiguration.from_mapping(original.to_dict())
    assert restored == original


def test_old_mapping_without_parser_fields_loads_as_auto() -> None:
    restored = ParserConfiguration.from_mapping(None, default_mode="auto")
    assert restored == ParserConfiguration()


def test_invalid_configuration_is_rejected_deterministically() -> None:
    with pytest.raises(ParserConfigurationError, match="Unsupported parser mode"):
        ParserConfiguration(mode="regex")
    with pytest.raises(ParserConfigurationError, match="must not be empty"):
        ParserConfiguration(mode="delimited", delimiter="")
    with pytest.raises(ParserConfigurationError, match="unique"):
        ParserConfiguration(
            mode="delimited",
            header_mode="none",
            columns=(ColumnMapping(0, "TC1"), ColumnMapping(1, "TC1")),
        )
    with pytest.raises(ParserConfigurationError, match="must have a channel name"):
        ParserConfiguration(
            mode="delimited",
            header_mode="none",
            columns=(ColumnMapping(0, "  ", enabled=True),),
        )
    with pytest.raises(ParserConfigurationError, match="must be different"):
        ParserConfiguration(
            mode="key_value",
            pair_separator=":",
            name_value_separator=":",
        )


def test_generic_channel_names_match_existing_headerless_scheme() -> None:
    assert generic_channel_name(0) == "Channel 1"
    assert generic_channel_name(3) == "Channel 4"


def test_preview_shows_mapped_delimited_sample() -> None:
    configuration = ParserConfiguration(
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
    preview = preview_sample(configuration, "23.4|25.1|101.3|1450")
    assert preview.message == "OK"
    assert [entry.channel for entry in preview.entries] == [
        "TC1",
        "TC2",
        "PRESSURE",
        "RPM",
    ]
    assert [entry.value for entry in preview.entries] == [
        "23.4",
        "25.1",
        "101.3",
        "1450",
    ]
