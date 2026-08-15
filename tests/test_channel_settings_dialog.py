from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from serialscope.data import ChannelMetadataRegistry
from serialscope.parsing import ChannelUpdate
from serialscope.ui.channel_settings_dialog import ChannelSettingsDialog
from serialscope.ui.main_window import MainWindow
from serialscope.data import AlarmLimits
import pytest


def test_dialog_preserves_read_only_source_and_applies_trimmed_unicode() -> None:
    application = QApplication.instance() or QApplication([])
    registry = ChannelMetadataRegistry()
    registry.ensure(("TC1", "AI0"))
    dialog = ChannelSettingsDialog(registry)

    assert not dialog.table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable
    dialog.alias_editors["TC1"].setText("  Reactor Temperature ")
    dialog.unit_selectors["TC1"].set_unit(" °C ")
    dialog.unit_selectors["AI0"].set_unit("µA")
    dialog.apply()

    assert registry.get("TC1").source_name == "TC1"
    assert registry.get("TC1").alias == "Reactor Temperature"
    assert registry.get("TC1").unit == "°C"
    assert registry.get("AI0").unit == "µA"
    dialog.close()
    application.processEvents()


def test_dialog_applies_partial_alarm_limits_and_rejects_bad_order() -> None:
    application = QApplication.instance() or QApplication([])
    registry = ChannelMetadataRegistry()
    registry.ensure(("TC1",))
    dialog = ChannelSettingsDialog(registry)
    dialog.alarm_editors["TC1"][1].setText("10")
    dialog.alarm_editors["TC1"][2].setText("20")

    dialog.apply()
    assert registry.get("TC1").alarms == AlarmLimits(low=10, high=20)

    dialog.alarm_editors["TC1"][1].setText("30")
    dialog.alarm_editors["TC1"][2].setText("20")
    with pytest.raises(ValueError, match="must increase"):
        dialog.apply()
    dialog.close()
    application.processEvents()


def test_dialog_preserves_unknown_custom_unit() -> None:
    application = QApplication.instance() or QApplication([])
    registry = ChannelMetadataRegistry()
    registry.set("FLOW", "", "kgmol/h")
    dialog = ChannelSettingsDialog(registry)
    assert dialog.unit_selectors["FLOW"].unit == "kgmol/h"
    assert dialog.unit_selectors["FLOW"].is_custom
    dialog.apply()
    assert registry.get("FLOW").unit == "kgmol/h"
    dialog.close()
    application.processEvents()


def test_single_source_metadata_apply_does_not_leak_storage_keys() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])
    window._handle_source_update(
        "default", ChannelUpdate(("Channel 1", "Channel 2"), (1.0, 2.0))
    )
    window._apply_channel_metadata()

    names = window._channel_metadata.source_names
    assert names == ("Channel 1", "Channel 2")
    assert all("\x1f" not in name for name in names)

    dialog = ChannelSettingsDialog(window._channel_metadata)
    shown = [
        dialog.table.item(row, 0).text() for row in range(dialog.table.rowCount())
    ]
    assert shown == ["Channel 1", "Channel 2"]
    assert dialog.table.currentRow() == 0
    assert dialog.table.verticalScrollBar().value() == 0
    dialog.close()
    window.close()
    application.processEvents()


def test_dialog_recovers_from_already_leaked_storage_keys() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])
    window._channel_metadata.ensure(("Channel 7",))
    window._channel_metadata.set("default\x1fChannel 1", "", "")
    window._channel_metadata.set("default\x1fChannel 2", "Inlet", "bar")
    window._sanitize_source_metadata()

    assert window._channel_metadata.source_names == (
        "Channel 7",
        "Channel 1",
        "Channel 2",
    )
    assert window._channel_metadata.get("Channel 2").alias == "Inlet"
    dialog = ChannelSettingsDialog(window._channel_metadata)
    shown = [
        dialog.table.item(row, 0).text() for row in range(dialog.table.rowCount())
    ]
    assert shown == ["Channel 7", "Channel 1", "Channel 2"]
    assert all("\x1f" not in name and not name.startswith("default") for name in shown)
    dialog.close()
    window.close()
    application.processEvents()


def test_dialog_separates_sections_and_shows_empty_calculated_state() -> None:
    application = QApplication.instance() or QApplication([])
    registry = ChannelMetadataRegistry()
    registry.ensure(("TC1",))
    dialog = ChannelSettingsDialog(registry)
    dialog.show()
    application.processEvents()

    assert dialog.add_calculated_button.text() == "+ Add Calculated Channel"
    assert dialog.delete_calculated_button.objectName() == "deleteCalculatedButton"
    assert dialog.calculated_empty_label.isVisibleTo(dialog)
    assert dialog.calculated_table.isHidden()
    assert dialog.alias_editors["TC1"].placeholderText() == "Alias"
    assert dialog.alarm_editors["TC1"][0].placeholderText() == "Low-Low"
    dialog.close()
    application.processEvents()


def test_physical_table_uses_item_only_for_original_name() -> None:
    application = QApplication.instance() or QApplication([])
    registry = ChannelMetadataRegistry()
    registry.ensure(("Channel 1", "Channel 10", "Reactor Temperature"))
    dialog = ChannelSettingsDialog(registry)
    dialog.resize(980, 560)
    dialog.show()
    application.processEvents()

    assert dialog.table.cellWidget(0, 0) is None
    assert dialog.table.item(0, 0).text() == "Channel 1"
    assert dialog.table.columnWidth(0) >= 140
    assert dialog.table.columnWidth(1) >= 140
    assert dialog.table.rowHeight(0) >= 40
    dialog.close()
    application.processEvents()
