from serialscope.data import (
    CalculatedChannel,
    CalculatedChannelStore,
    bindings_for_expression,
    evaluate_calculated_channels,
    identifier_for,
    topological_order,
)


def test_identifier_generation_and_bindings_use_authoritative_names() -> None:
    assert identifier_for("Channel 7") == "Channel_7"
    assert identifier_for("TC1") == "TC1"
    bindings = bindings_for_expression(
        "Channel_7 - Channel_8", ("Channel 7", "Channel 8")
    )
    assert bindings == {"Channel_7": "Channel 7", "Channel_8": "Channel 8"}


def test_calculated_channels_evaluate_in_dependency_order() -> None:
    delta = CalculatedChannel.create("DeltaT", "TC1 - TC2", available_names=("TC1", "TC2"))
    efficiency = CalculatedChannel.create(
        "Efficiency",
        "DeltaT / Flow",
        available_names=("DeltaT", "Flow"),
    )
    result = evaluate_calculated_channels(
        (efficiency, delta),
        {"TC1": 30, "TC2": 20, "Flow": 5},
    )

    assert result.update is not None
    assert result.update.channels == {"DeltaT": 10, "Efficiency": 2}
    assert result.errors == {}


def test_circular_calculated_channels_are_rejected() -> None:
    first = CalculatedChannel.create("A", "B + 1", available_names=("B",))
    second = CalculatedChannel.create("B", "A + 1", available_names=("A",))
    result = evaluate_calculated_channels((first, second), {})

    assert result.update is None
    assert "A" in result.errors
    assert "B" in result.errors
    assert "itself" in result.errors["A"]


def test_missing_source_does_not_raise() -> None:
    channel = CalculatedChannel.create(
        "Pressure_Drop", "Pressure_In - Pressure_Out", available_names=("Pressure_In",)
    )
    result = evaluate_calculated_channels((channel,), {"Pressure_In": 4.2})

    assert result.update is None
    assert "Pressure_Out" in result.errors["Pressure_Drop"]


def test_topological_order_puts_dependencies_first() -> None:
    order, cyclic = topological_order(
        ("Efficiency", "DeltaT"),
        {"Efficiency": ("DeltaT",), "DeltaT": ()},
    )
    assert cyclic == ()
    assert order == ("DeltaT", "Efficiency")


def test_calculated_store_round_trips_per_source(tmp_path) -> None:
    path = tmp_path / "calculated_channels.json"
    store = CalculatedChannelStore(path)
    channel = CalculatedChannel.create("DeltaT", "TC1 - TC2", unit="°C")
    store.replace_source("default", (channel,))

    restored = CalculatedChannelStore(path)
    loaded = restored.for_source("default")
    assert len(loaded) == 1
    assert loaded[0].name == "DeltaT"
    assert loaded[0].expression == "TC1 - TC2"
    assert loaded[0].unit == "°C"
    assert loaded[0].binding_map["TC1"] == "TC1"
