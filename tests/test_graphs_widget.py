import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from serialscope.parsing import ChannelUpdate
from serialscope.ui.graphs_widget import GraphsWidget


def test_detected_channels_appear_once_and_are_unselected() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget()
    update = ChannelUpdate(("TC1", "TC2"), (100.4, 98.7))

    widget.update_channels(update)
    widget.update_channels(update)

    assert widget.channel_names == ("TC1", "TC2")
    assert widget.selected_channels == ()
    assert not widget.has_series("TC1")
    widget.close()
    application.processEvents()


def test_selecting_and_deselecting_channel_controls_series() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget()
    widget.update_channels(ChannelUpdate(("TC1", "TC2"), (100.4, 98.7)))

    widget.set_channel_selected("TC1", True)
    widget.set_channel_selected("TC2", True)

    assert widget.selected_channels == ("TC1", "TC2")
    assert widget.has_series("TC1")
    assert widget.has_series("TC2")

    widget.set_channel_selected("TC1", False)
    assert not widget.has_series("TC1")
    assert widget.has_series("TC2")
    widget.close()
    application.processEvents()


def test_selected_series_receives_history_values() -> None:
    application = QApplication.instance() or QApplication([])
    times = iter((10.0, 10.4))
    widget = GraphsWidget(clock=lambda: next(times))
    widget.update_channels(ChannelUpdate(("TC1",), (100.4,)))
    widget.set_channel_selected("TC1", True)
    widget.update_channels(ChannelUpdate(("TC1",), (101.2,)))

    widget.refresh_plot()

    x_values, y_values = widget._series["TC1"].getData()
    assert x_values.tolist() == pytest.approx([0.0, 0.4])
    assert y_values.tolist() == [100.4, 101.2]
    widget.close()
    application.processEvents()
