import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from serialscope.parsing import ChannelUpdate
from serialscope.ui.graphs_widget import GraphsWidget, visible_x_range
from serialscope.ui.theme import DARK_GRAPH_PALETTE, LIGHT_GRAPH_PALETTE
from serialscope.data import ChannelMetadataRegistry


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


def test_display_processing_controls_have_safe_defaults() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget()

    assert widget.interpolation_combo.currentData() == "off"
    assert widget.density_combo.currentData() == 5
    assert widget.max_gap_combo.currentData() == 5.0
    assert widget.smoothing_combo.currentData() == "off"
    assert widget.moving_average_spin.value() == 5
    assert widget.ema_alpha_spin.value() == pytest.approx(0.2)
    assert not widget.measured_points_checkbox.isChecked()
    widget.close()
    application.processEvents()


def test_measured_points_toggle_and_processing_do_not_change_history() -> None:
    application = QApplication.instance() or QApplication([])
    times = iter((10.0, 11.0, 12.0))
    widget = GraphsWidget(clock=lambda: next(times))
    for value in (0, 10, 5):
        widget.update_channels(ChannelUpdate(("A",), (value,)))
    widget.set_channel_selected("A", True)
    source_before = widget.history.points("A")

    widget.interpolation_combo.setCurrentText("PCHIP")
    widget.smoothing_combo.setCurrentText("EMA")
    widget.measured_points_checkbox.setChecked(True)

    assert widget._measured_series["A"].isVisible()
    assert len(widget._series["A"].getData()[0]) > len(source_before[0])
    assert widget.history.points("A") == source_before
    widget.close()
    application.processEvents()


def test_cursor_and_statistics_use_measured_values() -> None:
    application = QApplication.instance() or QApplication([])
    times = iter((10.0, 12.0, 15.0))
    widget = GraphsWidget(clock=lambda: next(times))
    for value in (2, 8, 5):
        widget.update_channels(ChannelUpdate(("A",), (value,)))
    widget.set_channel_selected("A", True)
    widget.interpolation_combo.setCurrentText("Linear")

    assert widget.inspect_at(3.0) == {"A": (2.0, 8)}
    assert "Min 2" in widget.statistics_label.text()
    assert "Max 8" in widget.statistics_label.text()
    assert "Avg 5" in widget.statistics_label.text()
    widget.close()
    application.processEvents()


def test_reset_zoom_preserves_history_selection_and_replay_data(tmp_path) -> None:
    import csv
    import json
    from serialscope.replay import load_replay_session

    application = QApplication.instance() or QApplication([])
    directory = tmp_path / "session"
    directory.mkdir()
    (directory / "session.json").write_text(
        json.dumps({"structured_data_delimiter": ","}), encoding="utf-8"
    )
    with (directory / "data.csv").open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream).writerows(
            [["elapsed_s", "A"], ["0", "1"], ["120", "2"]]
        )
    widget = GraphsWidget()
    widget.load_replay(load_replay_session(directory))
    widget.set_channel_selected("A", True)
    source_before = widget._replay_session.samples
    widget.plot_widget.setXRange(40, 50, padding=0)

    widget.reset_zoom()

    assert widget.selected_channels == ("A",)
    assert widget._replay_session.samples == source_before
    assert widget.plot_widget.viewRange()[0] == pytest.approx([60.0, 120.0])
    widget.close()
    application.processEvents()


def test_processing_changes_while_paused_do_not_redraw_until_resume() -> None:
    application = QApplication.instance() or QApplication([])
    times = iter((10.0, 11.0))
    widget = GraphsWidget(clock=lambda: next(times))
    widget.update_channels(ChannelUpdate(("A",), (1,)))
    widget.set_channel_selected("A", True)
    widget.toggle_pause()
    before = widget._series["A"].getData()[0].tolist()
    widget.update_channels(ChannelUpdate(("A",), (2,)))
    widget.interpolation_combo.setCurrentText("Linear")
    assert widget._series["A"].getData()[0].tolist() == before

    widget.toggle_pause()
    assert len(widget._series["A"].getData()[0]) > len(before)
    widget.close()
    application.processEvents()


def test_replay_processing_always_regenerates_from_recorded_measurements(tmp_path) -> None:
    import csv
    import json
    from serialscope.replay import load_replay_session

    application = QApplication.instance() or QApplication([])
    directory = tmp_path / "session"
    directory.mkdir()
    (directory / "session.json").write_text(
        json.dumps({"structured_data_delimiter": ","}), encoding="utf-8"
    )
    with (directory / "data.csv").open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream).writerows(
            [["elapsed_s", "A"], ["0", "0"], ["1", "10"], ["2", "0"]]
        )
    session = load_replay_session(directory)
    widget = GraphsWidget()
    widget.load_replay(session)
    widget.set_channel_selected("A", True)
    source_before = session.points("A")

    widget.smoothing_combo.setCurrentText("Moving Average")
    first_display = widget._series["A"].getData()[1].tolist()
    widget.smoothing_combo.setCurrentText("Off")
    widget.smoothing_combo.setCurrentText("Moving Average")

    assert widget._series["A"].getData()[1].tolist() == first_display
    assert session.points("A") == source_before
    widget.close()
    application.processEvents()


def test_graph_inspection_elements_remain_functional_in_both_themes() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget()
    widget.update_channels(ChannelUpdate(("A",), (1,)))
    widget.set_channel_selected("A", True)

    for palette in (LIGHT_GRAPH_PALETTE, DARK_GRAPH_PALETTE):
        widget.apply_theme(palette)
        assert widget.selected_channels == ("A",)
        assert widget.inspect_at(0.0) == {"A": (0.0, 1)}
        assert widget.cursor_line.pen.color().name() == palette.cursor

    widget.close()
    application.processEvents()


def test_alias_and_unit_update_legend_cursor_statistics_without_reset() -> None:
    application = QApplication.instance() or QApplication([])
    times = iter((10.0, 11.0, 12.0))
    widget = GraphsWidget(clock=lambda: next(times))
    for value in (98.4, 104.6, 100.6):
        widget.update_channels(ChannelUpdate(("TC1",), (value,)))
    widget.set_channel_selected("TC1", True)
    history_before = widget.history.points("TC1")
    registry = ChannelMetadataRegistry()
    registry.set("TC1", "Reactor Temperature", "°C")

    widget.set_channel_metadata(registry)
    widget._update_statistics(widget._source_points())

    assert widget.channel_names == ("TC1",)
    assert widget.selected_channels == ("TC1",)
    assert widget.history.points("TC1") == history_before
    assert widget._series["TC1"].name() == "Reactor Temperature"
    presentation = registry.get("TC1")
    nearest = widget.inspect_at(1.1)["TC1"]
    assert presentation.display_name == "Reactor Temperature"
    assert nearest == (1.0, 104.6)
    assert "Reactor Temperature: 104.6 °C" in widget.cursor_text_at(1.1)
    assert "Reactor Temperature" in widget.statistics_label.text()
    assert "°C" in widget.statistics_label.text()
    widget.close()
    application.processEvents()
