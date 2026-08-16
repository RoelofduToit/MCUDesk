import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from serialscope.data import CalculatedChannel, CalculatedChannelStore
from serialscope.parsing import ChannelUpdate
from serialscope.ui.channel_settings_dialog import ChannelSettingsDialog
from serialscope.ui.main_window import MainWindow


def _calculated_window(tmp_path, channels: tuple[CalculatedChannel, ...]) -> MainWindow:
    store = CalculatedChannelStore(tmp_path / "calculated_channels.json")
    store.replace_source("default", channels)
    window = MainWindow(port_scanner=lambda: [], calculated_store=store)
    window.dashboard_widget.show()
    return window


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


def test_calculated_dashboard_tile_remains_after_subsequent_csv_samples(
    tmp_path,
) -> None:
    application = QApplication.instance() or QApplication([])
    window = _calculated_window(
        tmp_path, (CalculatedChannel.create("SUM", "A + B"),)
    )
    window._handle_source_update("default", ChannelUpdate(("A", "B"), (1.0, 2.0)))
    window.dashboard_widget.set_channel_selected("A", True)
    window.dashboard_widget.set_channel_selected("SUM", True)

    window._handle_source_update("default", ChannelUpdate(("A", "B"), (3.0, 4.0)))
    window._handle_source_update("default", ChannelUpdate(("A", "B"), (5.0, 6.0)))

    assert window.dashboard_widget.selected_channels == ("A", "SUM")
    assert window.dashboard_widget.tile_count == 2
    assert window.dashboard_widget.tile_value_text("A") == "5"
    assert window.dashboard_widget.tile_value_text("SUM") == "11"
    window.close()
    application.processEvents()


def test_physical_dashboard_tile_remains_when_calculated_channels_are_active(
    tmp_path,
) -> None:
    application = QApplication.instance() or QApplication([])
    window = _calculated_window(
        tmp_path, (CalculatedChannel.create("SUM", "A + B"),)
    )
    window._handle_source_update("default", ChannelUpdate(("A", "B"), (1.0, 2.0)))
    window.dashboard_widget.set_channel_selected("A", True)

    window._handle_source_update("default", ChannelUpdate(("A", "B"), (10.0, 20.0)))

    assert window.dashboard_widget.selected_channels == ("A",)
    assert window.dashboard_widget.tile_value_text("A") == "10"
    window.close()
    application.processEvents()


def test_multiple_calculated_dashboard_tiles_remain(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    window = _calculated_window(
        tmp_path,
        (
            CalculatedChannel.create("SUM", "A + B"),
            CalculatedChannel.create("DIFF", "A - B"),
        ),
    )
    window._handle_source_update("default", ChannelUpdate(("A", "B"), (8.0, 3.0)))
    window.dashboard_widget.set_channel_selected("SUM", True)
    window.dashboard_widget.set_channel_selected("DIFF", True)

    window._handle_source_update("default", ChannelUpdate(("A", "B"), (9.0, 4.0)))

    assert window.dashboard_widget.selected_channels == ("SUM", "DIFF")
    assert window.dashboard_widget.tile_value_text("SUM") == "13"
    assert window.dashboard_widget.tile_value_text("DIFF") == "5"
    window.close()
    application.processEvents()


def test_metadata_refresh_does_not_remove_calculated_tiles(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    window = _calculated_window(
        tmp_path, (CalculatedChannel.create("SUM", "A + B", unit=""),)
    )
    window._handle_source_update("default", ChannelUpdate(("A", "B"), (1.0, 2.0)))
    window.dashboard_widget.set_channel_selected("SUM", True)
    window._channel_metadata.set("SUM", "Total", "u")
    window._apply_channel_metadata()
    window._handle_source_update("default", ChannelUpdate(("A", "B"), (2.0, 2.0)))

    assert window.dashboard_widget.selected_channels == ("SUM",)
    assert window.dashboard_widget.tile_value_text("SUM") == "4"
    window.close()
    application.processEvents()


def test_tab_changes_do_not_remove_calculated_tiles(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    window = _calculated_window(
        tmp_path, (CalculatedChannel.create("SUM", "A + B"),)
    )
    window.show()
    application.processEvents()
    window._handle_source_update("default", ChannelUpdate(("A", "B"), (1.0, 2.0)))
    window.workspace_tabs.setCurrentWidget(window.dashboard_widget)
    application.processEvents()
    window.dashboard_widget.set_channel_selected("SUM", True)

    window.workspace_tabs.setCurrentWidget(window.terminal)
    application.processEvents()
    window.workspace_tabs.setCurrentWidget(window.dashboard_widget)
    application.processEvents()
    window._handle_source_update("default", ChannelUpdate(("A", "B"), (4.0, 1.0)))

    assert window.dashboard_widget.selected_channels == ("SUM",)
    assert window.dashboard_widget.tile_count == 1
    window.close()
    application.processEvents()


def test_temporary_missing_calculated_value_keeps_selected_tile(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    window = _calculated_window(
        tmp_path, (CalculatedChannel.create("SUM", "A + B"),)
    )
    window._handle_source_update("default", ChannelUpdate(("A", "B"), (1.0, 2.0)))
    window.dashboard_widget.set_channel_selected("SUM", True)
    window.dashboard_widget.set_channel_selected("B", True)
    window._selected_source.latest_values.pop("A", None)

    window._handle_source_update("default", ChannelUpdate(("B",), (9.0,)))

    assert set(window.dashboard_widget.selected_channels) == {"SUM", "B"}
    assert window.dashboard_widget.tile_value_text("SUM") == "3"
    assert window.dashboard_widget.tile_status_text("SUM") == "UNKNOWN"
    assert window.dashboard_widget.tile_value_text("B") == "9"
    assert window.data_widget.status_text("SUM") == "UNKNOWN"
    assert window.data_widget.value_text("SUM") == "3.0"

    window._handle_source_update("default", ChannelUpdate(("A", "B"), (4.0, 6.0)))

    assert set(window.dashboard_widget.selected_channels) == {"SUM", "B"}
    assert window.dashboard_widget.tile_value_text("SUM") == "10"
    assert window.dashboard_widget.tile_status_text("SUM") == "NORMAL"
    assert window.dashboard_widget.tile_value_text("B") == "6"
    window.close()
    application.processEvents()


def test_deleting_calculated_definition_removes_dashboard_tile(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    window = _calculated_window(
        tmp_path, (CalculatedChannel.create("SUM", "A + B"),)
    )
    window._handle_source_update("default", ChannelUpdate(("A", "B"), (1.0, 2.0)))
    window.dashboard_widget.set_channel_selected("SUM", True)
    window.dashboard_widget.set_channel_selected("A", True)

    window._remove_calculated_channels("default", {"SUM"})

    assert "SUM" not in window.dashboard_widget.channel_names
    assert window.dashboard_widget.selected_channels == ("A",)
    assert window.data_widget.value_text("SUM") is None
    assert "SUM" not in window.graphs_widget.channel_names
    window.close()
    application.processEvents()


def test_failed_calculated_sample_is_not_recorded(tmp_path) -> None:
    from serialscope.logging import RecordingSession, SessionConfig

    application = QApplication.instance() or QApplication([])
    window = _calculated_window(
        tmp_path, (CalculatedChannel.create("SUM", "A + B"),)
    )
    session = RecordingSession()
    directory = session.start(
        tmp_path, SessionConfig("Calc", "COM4", 115200, "LF")
    )
    window._recording_session = session
    window._handle_source_update("default", ChannelUpdate(("A", "B"), (1.0, 2.0)))
    window._selected_source.latest_values.pop("A", None)
    window._handle_source_update("default", ChannelUpdate(("B",), (9.0,)))
    session.stop("normal", 0)

    rows = (directory / "data.csv").read_text(encoding="utf-8").splitlines()
    assert rows[0] == "elapsed_s,A,B,SUM"
    assert rows[1].endswith(",1.0,2.0,3.0")
    assert rows[2].endswith(",,9.0,")
    window.close()
    application.processEvents()
