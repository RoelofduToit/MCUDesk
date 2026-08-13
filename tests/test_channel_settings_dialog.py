from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from serialscope.data import ChannelMetadataRegistry
from serialscope.ui.channel_settings_dialog import ChannelSettingsDialog


def test_dialog_preserves_read_only_source_and_applies_trimmed_unicode() -> None:
    application = QApplication.instance() or QApplication([])
    registry = ChannelMetadataRegistry()
    registry.ensure(("TC1", "AI0"))
    dialog = ChannelSettingsDialog(registry)

    assert not dialog.table.item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable
    dialog.table.item(0, 1).setText("  Reactor Temperature ")
    dialog.table.item(0, 2).setText(" °C ")
    dialog.table.item(1, 2).setText("µA")
    dialog.apply()

    assert registry.get("TC1").source_name == "TC1"
    assert registry.get("TC1").alias == "Reactor Temperature"
    assert registry.get("TC1").unit == "°C"
    assert registry.get("AI0").unit == "µA"
    dialog.close()
    application.processEvents()
