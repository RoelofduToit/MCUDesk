import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

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


def test_partial_updates_add_channels_without_removing_missing_channels() -> None:
    application = QApplication.instance() or QApplication([])
    widget = ChannelsWidget()
    widget.update_channels(
        ChannelUpdate(("TEMP", "RPM"), (25.4, 1487), replace_channels=False)
    )

    widget.update_channels(
        ChannelUpdate(("TEMP", "FLOW"), (25.7, 0.42), replace_channels=False)
    )

    assert widget.value_text("TEMP") == "25.7"
    assert widget.value_text("RPM") == "1487"
    assert widget.value_text("FLOW") == "0.42"
    application.processEvents()


def test_long_channel_names_wrap_without_horizontal_scrolling() -> None:
    application = QApplication.instance() or QApplication([])
    widget = ChannelsWidget()
    widget.resize(238, 180)
    widget.update_channels(
        ChannelUpdate(
            ("Reactor Temperature Sensor With A Long Engineering Alias",),
            (24.7,),
        )
    )
    widget.show()
    application.processEvents()

    name_labels = widget.findChildren(QLabel, "channelNameLabel")
    assert len(name_labels) == 1
    assert name_labels[0].wordWrap()
    assert (
        widget.scroll_area.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert widget.scroll_area.horizontalScrollBar().maximum() == 0

    widget.close()
    application.processEvents()
