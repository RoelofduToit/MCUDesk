from serialscope.data import AlarmLimits, ChannelMetadataRegistry


def test_source_identity_alias_and_unit_lifecycle() -> None:
    registry = ChannelMetadataRegistry()
    registry.ensure(("TC1",))

    registry.set("TC1", "  Reactor Temperature  ", " °C ")
    assert registry.get("TC1").source_name == "TC1"
    assert registry.get("TC1").display_name == "Reactor Temperature"
    assert registry.get("TC1").unit == "°C"

    registry.set("TC1", "Outlet Temperature", "µA")
    assert registry.get("TC1").display_name == "Outlet Temperature"
    assert registry.get("TC1").unit == "µA"

    registry.set("TC1", "  ", "  ")
    assert registry.get("TC1").display_name == "TC1"
    assert registry.get("TC1").unit == ""


def test_duplicate_aliases_never_merge_source_channels() -> None:
    registry = ChannelMetadataRegistry()
    registry.set("TC1", "Temperature", "°C")
    registry.set("TC2", "Temperature", "°C")

    assert registry.source_names == ("TC1", "TC2")
    assert registry.get("TC1").source_name != registry.get("TC2").source_name
    assert registry.snapshot()["TC1"] == registry.snapshot()["TC2"]


def test_replace_ignores_unknown_and_supports_old_empty_metadata() -> None:
    registry = ChannelMetadataRegistry()
    registry.replace({"UNKNOWN": {"alias": "No"}}, ("A", "B"))
    assert registry.source_names == ("A", "B")
    assert registry.get("A").display_name == "A"


def test_discard_composite_identities_keeps_parser_names_and_merges_metadata() -> None:
    registry = ChannelMetadataRegistry()
    registry.ensure(("Channel 1", "Channel 2"))
    registry.set("default\x1fChannel 1", "Reactor", "°C", AlarmLimits(high=90))
    registry.set("default\x1fChannel 3", "Spare", "V")

    registry.discard_composite_identities()

    assert registry.source_names == ("Channel 1", "Channel 2", "Channel 3")
    assert all("\x1f" not in name for name in registry.source_names)
    assert registry.get("Channel 1").alias == "Reactor"
    assert registry.get("Channel 1").unit == "°C"
    assert registry.get("Channel 1").alarms == AlarmLimits(high=90)
    assert registry.get("Channel 3").alias == "Spare"


def test_replace_normalizes_leaked_storage_keys() -> None:
    registry = ChannelMetadataRegistry()
    registry.replace(
        {
            "default\x1fChannel 1": {"alias": "From storage", "unit": "°C"},
            "Channel 1": {"alias": "From parser", "unit": "K"},
        },
        ("Channel 1",),
    )

    assert registry.source_names == ("Channel 1",)
    assert registry.get("Channel 1").alias == "From parser"
    assert registry.get("Channel 1").unit == "K"


def test_alarm_metadata_round_trips_without_changing_alias_or_unit() -> None:
    registry = ChannelMetadataRegistry()
    limits = AlarmLimits(low_low=80, low=90, high=110, high_high=120)
    registry.set("TC1", "Temperature", "°C", limits)
    snapshot = registry.snapshot()

    restored = ChannelMetadataRegistry()
    restored.replace(snapshot, ("TC1",))

    assert restored.get("TC1").alias == "Temperature"
    assert restored.get("TC1").unit == "°C"
    assert restored.get("TC1").alarms == limits
