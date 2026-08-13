from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from serialscope.data import ChannelMetadataRegistry
from serialscope.ui.channel_settings_dialog import ChannelSettingsDialog
from serialscope.data import AlarmLimits
import pytest


def test_dialog_preserves_read_only_source_and_applies_trimmed_unicode() -> None:
    application = QApplication.instance() or QApplication([])
    registry = ChannelMetadataRegistry()
    registry.ensure(("TC1", "AI0"))
    dialog = ChannelSettingsDialog(registry)

    assert not dialog.table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable
    dialog.table.item(0, 1).setText("  Reactor Temperature ")
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
    dialog.table.item(0, 4).setText("10")
    dialog.table.item(0, 5).setText("20")

    dialog.apply()
    assert registry.get("TC1").alarms == AlarmLimits(low=10, high=20)

    dialog.table.item(0, 4).setText("30")
    dialog.table.item(0, 5).setText("20")
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
