from serialscope.data import ChannelMetadataRegistry


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
