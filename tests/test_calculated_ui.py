from PySide6.QtWidgets import QApplication

from serialscope.data import CalculatedChannel, CalculatedChannelStore
from serialscope.parsing import ChannelUpdate
from serialscope.ui.channel_settings_dialog import ChannelSettingsDialog
from serialscope.ui.main_window import MainWindow


def test_calculated_channel_reaches_data_graphs_dashboard_and_recording(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    store = CalculatedChannelStore(tmp_path / "calculated_channels.json")
    store.replace_source(
        "default",
        (CalculatedChannel.create("DeltaT", "TC1 - TC2", unit="°C"),),
    )
    window = MainWindow(port_scanner=lambda: [], calculated_store=store)
    window._handle_source_update(
        "default", ChannelUpdate(("TC1", "TC2"), (30.0, 20.0), False)
    )

    assert window.data_widget.value_text("DeltaT") == "10.0"
    assert "DeltaT" in window.graphs_widget.channel_names
    assert "DeltaT" in window.dashboard_widget.channel_names
    assert window._selected_source.latest_values["DeltaT"] == 10.0
    assert window._channel_metadata.get("DeltaT").unit == "°C"
    selector = window.graphs_widget.active_widget.channel_selector
    selector.set_channel_calculated("DeltaT", True)
    assert not selector.toggles["DeltaT"].badge.isHidden()
    window.close()
    application.processEvents()


def test_channel_settings_keeps_calculated_rows_separate() -> None:
    application = QApplication.instance() or QApplication([])
    from serialscope.data import ChannelMetadataRegistry

    registry = ChannelMetadataRegistry()
    registry.ensure(("TC1", "TC2", "DeltaT"))
    dialog = ChannelSettingsDialog(
        registry,
        calculated_channels=(CalculatedChannel.create("DeltaT", "TC1 - TC2"),),
        available_names=("TC1", "TC2", "DeltaT"),
        latest_values={"TC1": 5, "TC2": 2},
    )
    physical = [
        dialog.table.item(row, 0).text() for row in range(dialog.table.rowCount())
    ]
    assert physical == ["TC1", "TC2"]
    assert dialog.calculated_table.item(0, 0).text() == "DeltaT"
    assert dialog.calculated_table.item(0, 1).text() == "TC1 - TC2"
    dialog.close()
    application.processEvents()
