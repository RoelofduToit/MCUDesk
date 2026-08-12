import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from serialscope.parsing import ChannelUpdate
from serialscope.ui.channels_widget import ChannelsWidget


def test_channels_view_shows_names_and_updates_values_in_place() -> None:
    application = QApplication.instance() or QApplication([])
    widget = ChannelsWidget()
    widget.update_channels(ChannelUpdate(("Count", "Temperature_C"), (1, 24.72)))
    original_label = widget._value_labels["Temperature_C"]

    widget.update_channels(ChannelUpdate(("Count", "Temperature_C"), (2, 25.08)))

    assert widget.empty_label.isHidden()
    assert widget.value_text("Count") == "2"
    assert widget.value_text("Temperature_C") == "25.08"
    assert widget._value_labels["Temperature_C"] is original_label
    application.processEvents()


def test_channels_view_reset_restores_empty_state() -> None:
    application = QApplication.instance() or QApplication([])
    widget = ChannelsWidget()
    widget.update_channels(ChannelUpdate(("A", "B"), (1, 2)))

    widget.reset()

    assert widget.value_text("A") is None
    assert widget.empty_label.text() == "No channels detected"
    assert widget.scroll_area.isHidden()
    application.processEvents()
