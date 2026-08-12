import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from serialscope.parsing import ChannelUpdate
from serialscope.ui.graphs_widget import GraphsWidget, visible_x_range


@pytest.mark.parametrize(
    ("latest_time", "window_seconds", "expected"),
    [
        (0.0, 60.0, (0.0, 60.0)),
        (10.0, 60.0, (0.0, 60.0)),
        (59.0, 60.0, (0.0, 60.0)),
        (60.0, 60.0, (0.0, 60.0)),
        (75.0, 60.0, (15.0, 75.0)),
        (10.0, 30.0, (0.0, 30.0)),
        (45.0, 30.0, (15.0, 45.0)),
        (0.0, 300.0, (0.0, 300.0)),
        (0.0, 3_600.0, (0.0, 3_600.0)),
        (1_800.0, 3_600.0, (0.0, 3_600.0)),
        (5_400.0, 3_600.0, (1_800.0, 5_400.0)),
        (-5.0, 60.0, (0.0, 60.0)),
    ],
)
def test_visible_x_range_never_shows_negative_elapsed_time(
    latest_time: float,
    window_seconds: float,
    expected: tuple[float, float],
) -> None:
    assert visible_x_range(latest_time, window_seconds) == expected


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


@pytest.mark.parametrize(
    ("label", "seconds"),
    [
        ("10 s", 10.0),
        ("30 s", 30.0),
        ("60 s", 60.0),
        ("5 min", 300.0),
        ("10 min", 600.0),
        ("30 min", 1_800.0),
        ("1 hour", 3_600.0),
    ],
)
def test_time_window_options_preserve_selection(label: str, seconds: float) -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget()
    widget.update_channels(ChannelUpdate(("TC1",), (100.4,)))
    widget.set_channel_selected("TC1", True)

    widget.time_window_combo.setCurrentText(label)

    assert widget.time_window_seconds == seconds
    assert widget.selected_channels == ("TC1",)
    assert widget.plot_widget.viewRange()[0] == pytest.approx([0.0, seconds])
    widget.close()
    application.processEvents()


def test_switching_between_short_and_long_windows_preserves_selection() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget()
    widget.update_channels(ChannelUpdate(("TC1", "TC2"), (100.4, 98.7)))
    widget.set_channel_selected("TC1", True)

    widget.time_window_combo.setCurrentText("1 hour")
    assert widget.selected_channels == ("TC1",)
    assert widget.plot_widget.viewRange()[0] == pytest.approx([0.0, 3_600.0])

    widget.time_window_combo.setCurrentText("10 s")
    assert widget.selected_channels == ("TC1",)
    assert widget.plot_widget.viewRange()[0] == pytest.approx([0.0, 10.0])
    widget.close()
    application.processEvents()


def test_default_time_window_is_sixty_seconds() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget()

    assert widget.time_window_combo.currentText() == "60 s"
    assert widget.time_window_seconds == 60.0
    assert widget.plot_widget.viewRange()[0] == pytest.approx([0.0, 60.0])
    assert widget.plot_widget.getAxis("bottom") is widget.elapsed_time_axis
    assert widget.elapsed_time_axis.labelText == "Elapsed Time"
    widget.close()
    application.processEvents()


def test_pause_freezes_series_while_history_continues_then_resume_catches_up() -> None:
    application = QApplication.instance() or QApplication([])
    times = iter((10.0, 11.0))
    widget = GraphsWidget(clock=lambda: next(times))
    widget.update_channels(ChannelUpdate(("TC1",), (100.4,)))
    widget.set_channel_selected("TC1", True)
    widget.toggle_pause()
    displayed_before_pause = widget._series["TC1"].getData()[1].tolist()
    range_before_pause = widget.plot_widget.viewRange()[0]

    widget.update_channels(ChannelUpdate(("TC1",), (101.2,)))
    widget.refresh_plot()

    assert widget.is_paused
    assert widget.pause_button.text() == "Resume"
    assert widget.history.points("TC1")[1] == (100.4, 101.2)
    assert widget._series["TC1"].getData()[1].tolist() == displayed_before_pause
    assert widget.plot_widget.viewRange()[0] == pytest.approx(range_before_pause)

    widget.toggle_pause()
    assert not widget.is_paused
    assert widget.pause_button.text() == "Pause"
    assert widget._series["TC1"].getData()[1].tolist() == [100.4, 101.2]
    assert widget.plot_widget.viewRange()[0] == pytest.approx([0.0, 60.0])
    widget.close()
    application.processEvents()


def test_clear_empties_history_and_series_but_preserves_selection() -> None:
    application = QApplication.instance() or QApplication([])
    times = iter((10.0, 20.0))
    widget = GraphsWidget(clock=lambda: next(times))
    widget.update_channels(ChannelUpdate(("TC1",), (100.4,)))
    widget.set_channel_selected("TC1", True)

    widget.clear_history()

    assert widget.history.points("TC1") == ((), ())
    assert widget.selected_channels == ("TC1",)
    assert widget.has_series("TC1")
    assert widget._series["TC1"].getData()[1] is None

    widget.update_channels(ChannelUpdate(("TC1",), (101.2,)))
    widget.refresh_plot()
    assert widget.history.points("TC1") == ((0.0,), (101.2,))
    assert widget._series["TC1"].getData()[1].tolist() == [101.2]
    widget.close()
    application.processEvents()
