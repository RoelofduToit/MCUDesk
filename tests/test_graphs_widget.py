import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QLabel, QSizePolicy, QWidget

from serialscope.parsing import ChannelUpdate
from serialscope.ui.graphs_widget import GraphsWidget, visible_x_range
from serialscope.ui.multi_graphs_widget import MultiSourceGraphsWidget
from serialscope.ui.channel_selector import ChannelToggle
from serialscope.ui.graph_display import format_cursor_time
from serialscope.ui.theme import (
    DARK_GRAPH_PALETTE,
    LIGHT_GRAPH_PALETTE,
    apply_application_theme,
)
from serialscope.ui.style import DARK_STYLE, LIGHT_STYLE
from serialscope.data import AlarmLimits, ChannelMetadataRegistry, EventMarker


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


@pytest.mark.parametrize("stylesheet", [DARK_STYLE, LIGHT_STYLE])
def test_graph_channel_layout_does_not_compress_selector_labels(
    stylesheet: str,
) -> None:
    application = QApplication.instance() or QApplication([])
    application.setStyleSheet(stylesheet)
    labels = (
        "Channel 1",
        "Channel 2",
        "Channel 8",
        "Channel 9",
        "Channel 10",
        "PRESSURE",
        "Reactor Temperature",
        "Outlet Pressure",
    )
    widget = GraphsWidget()
    widget.resize(700, 600)
    widget.show()
    widget.update_channels(ChannelUpdate(labels, tuple(range(len(labels)))))
    application.processEvents()

    assert all(isinstance(toggle, ChannelToggle) for toggle in widget._selectors.values())

    for checked, focused, enabled in (
        (False, False, True),
        (True, False, True),
        (True, True, True),
        (False, True, True),
        (False, False, False),
        (True, False, False),
    ):
        for checkbox in widget._selectors.values():
            checkbox.setEnabled(enabled)
            checkbox.setChecked(checked)
            if focused:
                checkbox.setFocus(Qt.FocusReason.OtherFocusReason)
            else:
                checkbox.clearFocus()
        application.processEvents()
        for checkbox in widget._selectors.values():
            assert checkbox.width() >= checkbox.minimumSizeHint().width()
            assert checkbox.width() >= checkbox.sizeHint().width()

    assert widget.selector_scroll.horizontalScrollBar().maximum() > 0
    widget.close()
    application.processEvents()


def test_event_markers_are_presentational_and_keep_measurement_history() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget(clock=lambda: 10.0)
    widget.update_channels(ChannelUpdate(("TC1",), (100.4,)))
    history = widget.history.points("TC1")

    widget.set_events((EventMarker("one", 2.5, "Valve opened"),))

    assert widget.events[0].text == "Valve opened"
    assert len(widget._event_lines) == 1
    assert "Valve opened" in widget._event_lines[0].toolTip()
    assert widget.history.points("TC1") == history
    widget.apply_theme(LIGHT_GRAPH_PALETTE)
    assert widget.events[0].elapsed_s == 2.5
    assert widget.history.points("TC1") == history
    widget.close()
    application.processEvents()


def test_parent_events_appear_on_every_device_graph() -> None:
    application = QApplication.instance() or QApplication([])
    widget = MultiSourceGraphsWidget()
    pico = widget.ensure_source("pico", "Pico")
    arduino = widget.ensure_source("arduino", "Arduino")
    event = EventMarker("one", 12.438, "Opened reactor valve")

    widget.set_events((event,))

    assert pico.events == (event,)
    assert arduino.events == (event,)
    assert pico._event_lines[0].value() == pytest.approx(12.438)
    assert arduino._event_lines[0].value() == pytest.approx(12.438)
    widget.close()
    application.processEvents()


def test_cursor_shows_alarm_state_without_changing_graph_source() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget(clock=lambda: 10.0)
    widget.update_channels(ChannelUpdate(("TC1",), (118.4,)))
    widget.set_channel_selected("TC1", True)
    registry = ChannelMetadataRegistry()
    registry.set("TC1", "Temperature", "°C", AlarmLimits(high=110))
    history_before = widget.history.points("TC1")

    widget.set_channel_metadata(registry)
    widget._update_cursor_values(0.0)

    assert widget.cursor_table.channel_text("TC1") == "Temperature"
    assert widget.cursor_table.value_text("TC1") == "118.40 °C"
    assert widget.cursor_table.status_text("TC1") == "HIGH"
    assert widget.history.points("TC1") == history_before
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
    assert widget.elapsed_time_axis.window_seconds == seconds
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
    statistics_before_pause = widget.statistics_table.value_text("TC1", "avg")
    range_before_pause = widget.plot_widget.viewRange()[0]

    widget.update_channels(ChannelUpdate(("TC1",), (101.2,)))
    widget.refresh_plot()

    assert widget.is_paused
    assert widget.pause_button.text() == "Resume"
    assert widget.history.points("TC1")[1] == (100.4, 101.2)
    assert widget._series["TC1"].getData()[1].tolist() == displayed_before_pause
    assert widget.statistics_table.value_text("TC1", "avg") == statistics_before_pause
    assert widget.plot_widget.viewRange()[0] == pytest.approx(range_before_pause)

    widget.toggle_pause()
    assert not widget.is_paused
    assert widget.pause_button.text() == "Pause"
    assert widget._series["TC1"].getData()[1].tolist() == [100.4, 101.2]
    assert widget.statistics_table.value_text("TC1", "avg") == "100.80"
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
    assert not widget.density_combo.isEnabled()
    assert not widget.max_gap_combo.isEnabled()
    assert not widget.density_label.isEnabled()
    assert not widget.max_gap_label.isEnabled()
    widget.close()
    application.processEvents()


def test_graph_settings_groups_stay_readable_at_narrow_and_wide_widths() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget()
    panel = widget.findChild(QWidget, "graphSettingsPanel")
    view = widget.findChild(QWidget, "graphControls")
    interpolation = widget.findChild(QWidget, "graphProcessingControls")
    smoothing = widget.findChild(QWidget, "graphSmoothingControls")
    assert panel is not None
    widget.resize(1100, 780)
    widget.show()
    application.processEvents()

    for group in (view, interpolation, smoothing):
        assert group.isVisibleTo(widget)
        assert group.height() < 110
        assert group.geometry().right() <= panel.width()

    widget.resize(520, 780)
    application.processEvents()
    assert panel.height() >= view.height()
    assert interpolation.geometry().top() >= view.geometry().top()
    assert widget.pause_button.isVisibleTo(widget)
    assert widget.time_window_combo.isVisibleTo(widget)
    assert widget.interpolation_combo.isVisibleTo(widget)
    assert widget.smoothing_combo.isVisibleTo(widget)
    widget.interpolation_combo.setCurrentText("Linear")
    assert widget.density_combo.isEnabled()
    assert widget.max_gap_combo.isEnabled()
    assert widget.density_label.isEnabled()
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
    assert widget.statistics_table.source_names == ("A",)
    assert widget.statistics_table.value_text("A", "min") == "2.00"
    assert widget.statistics_table.value_text("A", "avg") == "5.00"
    assert widget.statistics_table.value_text("A", "max") == "8.00"
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


def test_replay_uses_the_same_structured_statistics_table(tmp_path) -> None:
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
            [["elapsed_s", "A"], ["0", "1.25"], ["60", "2.5"], ["120", "3.75"]]
        )
    widget = GraphsWidget()
    widget.load_replay(load_replay_session(directory))
    widget.time_window_combo.setCurrentText("5 min")
    widget.set_channel_selected("A", True)
    widget._update_cursor_values(70.0)

    assert widget.statistics_table.source_names == ("A",)
    assert widget.statistics_table.value_text("A", "min") == "1.25"
    assert widget.statistics_table.value_text("A", "avg") == "2.50"
    assert widget.statistics_table.value_text("A", "max") == "3.75"
    assert widget.cursor_table.source_names == ("A",)
    assert widget.cursor_table.value_text("A") == "2.50"
    assert widget.cursor_table.status_text("A") == "NORMAL"
    assert widget.cursor_time_label.text() == "Cursor: 1:10"
    assert "Measurement: 1:00.00" in (
        widget.cursor_table.measurement_tooltip("A") or ""
    )
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
        assert widget.statistics_table.source_names == ("A",)
        assert widget.statistics_table.value_text("A", "avg") == "1.00"

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
    widget._update_cursor_values(1.1)
    assert widget.cursor_table.channel_text("TC1") == "Reactor Temperature"
    assert widget.cursor_table.value_text("TC1") == "104.60 °C"
    assert widget.cursor_table.status_text("TC1") == "NORMAL"
    assert widget.statistics_table.channel_text("TC1") == "Reactor Temperature (°C)"
    assert widget.statistics_table.value_text("TC1", "min") == "98.40"
    assert widget.statistics_table.value_text("TC1", "avg") == "101.20"
    assert widget.statistics_table.value_text("TC1", "max") == "104.60"
    widget.close()
    application.processEvents()


def test_statistics_table_contains_only_selected_channels_and_line_colors() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget(clock=lambda: 10.0)
    widget.update_channels(ChannelUpdate(("A", "B"), (1.234, 99.0)))
    widget.set_channel_selected("A", True)

    assert widget.statistics_table.source_names == ("A",)
    assert widget.statistics_table.value_text("A", "min") == "1.23"
    assert widget.statistics_table.value_text("B", "min") is None
    assert widget.statistics_table.swatch_color("A") == widget._series[
        "A"
    ].opts["pen"].color().name()
    assert widget.statistics_table.horizontalScrollBarPolicy() == (
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    widget.close()
    application.processEvents()


def test_statistics_table_expands_with_rows_and_does_not_scroll_internally() -> None:
    application = QApplication.instance() or QApplication([])
    names = tuple(f"Channel {index}" for index in range(1, 10))
    widget = GraphsWidget(clock=lambda: 10.0)
    widget.update_channels(ChannelUpdate(names, tuple(range(1, 10))))
    for name in names:
        widget.set_channel_selected(name, True)
    widget.resize(900, 800)
    widget.show()
    application.processEvents()

    expected_height = (
        max(widget.statistics_table.horizontalHeader().sizeHint().height(), 28)
        + 9 * widget.statistics_table.verticalHeader().defaultSectionSize()
        + widget.statistics_table.frameWidth() * 2
    )
    assert widget.statistics_table.rowCount() == 9
    assert widget.statistics_table.height() == expected_height
    assert widget.statistics_table.verticalScrollBarPolicy() == (
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert widget.statistics_table.verticalScrollBar().maximum() == 0
    assert widget.page_scroll.verticalScrollBar().maximum() > 0
    min_width = widget.statistics_table.columnWidth(1)
    assert min_width == widget.statistics_table.columnWidth(2)
    assert min_width == widget.statistics_table.columnWidth(3)
    assert min_width >= 88
    widget.resize(700, 800)
    application.processEvents()
    assert widget.statistics_table.columnWidth(1) == widget.statistics_table.columnWidth(3)
    widget.close()
    application.processEvents()


def test_multi_source_statistics_remain_isolated() -> None:
    application = QApplication.instance() or QApplication([])
    widget = MultiSourceGraphsWidget()
    pico = widget.ensure_source("pico", "Pico")
    arduino = widget.ensure_source("arduino", "Arduino")
    pico.update_channels(ChannelUpdate(("TEMP",), (25.0,)))
    arduino.update_channels(ChannelUpdate(("RPM",), (1_500,)))
    pico.set_channel_selected("TEMP", True)
    arduino.set_channel_selected("RPM", True)

    assert pico.statistics_table.source_names == ("TEMP",)
    assert pico.statistics_table.value_text("TEMP", "avg") == "25.00"
    assert pico.statistics_table.value_text("RPM", "avg") is None
    assert arduino.statistics_table.source_names == ("RPM",)
    assert arduino.statistics_table.value_text("RPM", "avg") == "1500.00"
    assert arduino.statistics_table.value_text("TEMP", "avg") is None
    widget.close()
    application.processEvents()


def test_graph_page_scrolls_vertically_with_graph_before_detail_tables() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget()
    layout = widget.page_content.layout()
    widget.resize(900, 650)
    widget.show()
    application.processEvents()

    assert widget.page_scroll.widgetResizable()
    assert widget.page_scroll.horizontalScrollBarPolicy() == (
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert widget.page_scroll.verticalScrollBarPolicy() == (
        Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    assert layout.indexOf(widget.plot_widget) < layout.indexOf(widget.cursor_panel)
    assert layout.indexOf(widget.cursor_panel) < layout.indexOf(widget.statistics_panel)
    cursor_layout = widget.cursor_panel.layout()
    statistics_layout = widget.statistics_panel.layout()
    assert cursor_layout.indexOf(widget.cursor_heading) < cursor_layout.indexOf(
        widget.cursor_table
    )
    assert statistics_layout.indexOf(widget.statistics_heading) < (
        statistics_layout.indexOf(widget.statistics_table)
    )
    assert widget.plot_widget.minimumHeight() == 500
    assert widget.plot_widget.sizePolicy().verticalPolicy() == (
        QSizePolicy.Policy.Expanding
    )
    assert widget.page_scroll.verticalScrollBar().maximum() > 0
    assert widget.page_scroll.horizontalScrollBar().maximum() == 0
    assert widget.page_scroll.verticalScrollBar().value() == 0
    assert not widget.eventFilter(
        widget.plot_widget.viewport(),
        QEvent(QEvent.Type.Wheel),
    )

    widget.resize(600, 650)
    application.processEvents()

    assert widget.page_scroll.horizontalScrollBar().maximum() == 0
    assert widget.page_content.width() <= widget.page_scroll.viewport().width()
    widget.close()
    application.processEvents()


def test_graph_expands_in_a_taller_scroll_viewport_without_losing_minimum() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget()
    widget.resize(1_000, 700)
    widget.show()
    application.processEvents()
    short_height = widget.plot_widget.height()

    widget.resize(1_000, 1_400)
    application.processEvents()

    assert short_height >= 500
    assert widget.plot_widget.height() > short_height
    widget.close()
    application.processEvents()


def test_live_updates_continue_while_graph_page_is_scrolled_down() -> None:
    application = QApplication.instance() or QApplication([])
    times = iter((10.0, 11.0))
    widget = GraphsWidget(clock=lambda: next(times))
    widget.resize(900, 650)
    widget.show()
    widget.update_channels(ChannelUpdate(("A",), (1.0,)))
    widget.set_channel_selected("A", True)
    application.processEvents()
    scrollbar = widget.page_scroll.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())
    scrolled_position = scrollbar.value()

    widget.update_channels(ChannelUpdate(("A",), (3.0,)))
    widget.refresh_plot()

    assert scrolled_position > 0
    assert scrollbar.value() == scrolled_position
    assert widget.history.points("A")[1] == (1.0, 3.0)
    assert widget._series["A"].getData()[1].tolist() == [1.0, 3.0]
    assert widget.statistics_table.value_text("A", "avg") == "2.00"
    widget.close()
    application.processEvents()


def test_reset_returns_graph_page_to_top() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget()
    widget.resize(900, 650)
    widget.show()
    application.processEvents()
    scrollbar = widget.page_scroll.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())
    assert scrollbar.value() > 0

    widget.reset()

    assert scrollbar.value() == 0
    widget.close()
    application.processEvents()


def test_wheel_over_plot_zooms_graph_while_page_background_scrolls() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget()
    widget.resize(1_000, 700)
    widget.show()
    application.processEvents()
    plot_range = widget.plot_widget.viewRange()
    page_position = widget.page_scroll.verticalScrollBar().value()

    plot_viewport = widget.plot_widget.viewport()
    plot_center = plot_viewport.rect().center()
    zoom_event = QWheelEvent(
        QPointF(plot_center),
        QPointF(plot_viewport.mapToGlobal(plot_center)),
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(plot_viewport, zoom_event)
    application.processEvents()

    assert zoom_event.isAccepted()
    assert widget.plot_widget.viewRange() != plot_range
    assert widget.page_scroll.verticalScrollBar().value() == page_position

    page_viewport = widget.page_scroll.viewport()
    page_center = page_viewport.rect().center()
    scroll_event = QWheelEvent(
        QPointF(page_center),
        QPointF(page_viewport.mapToGlobal(page_center)),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(page_viewport, scroll_event)
    application.processEvents()

    assert scroll_event.isAccepted()
    assert widget.page_scroll.verticalScrollBar().value() > page_position
    widget.close()
    application.processEvents()


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        (42.34, "42.3 s"),
        (613.11, "10:13"),
        (4_363.0, "01:12:43"),
    ],
)
def test_cursor_time_uses_human_friendly_elapsed_format(
    elapsed: float,
    expected: str,
) -> None:
    assert format_cursor_time(elapsed) == expected


def test_cursor_time_rejects_non_finite_input() -> None:
    assert format_cursor_time(float("nan")) == "—"
    assert format_cursor_time(float("inf")) == "—"


def test_cursor_table_tracks_selected_channels_and_reuses_rows() -> None:
    application = QApplication.instance() or QApplication([])
    times = iter((10.0, 11.0))
    widget = GraphsWidget(clock=lambda: next(times))
    widget.update_channels(ChannelUpdate(("A", "B"), (1.234, 9.0)))
    widget.update_channels(ChannelUpdate(("A", "B"), (2.345, 8.0)))
    widget.set_channel_selected("A", True)

    assert widget.cursor_table.source_names == ("A",)
    assert widget.cursor_table.value_text("A") == "—"
    original_row = widget.cursor_table.row_widget("A")
    widget._update_cursor_values(0.8)

    assert widget.cursor_table.row_widget("A") is original_row
    assert widget.cursor_table.value_text("A") == "2.35"
    assert widget.cursor_table.status_text("A") == "NORMAL"
    assert widget.cursor_time_label.text() == "Cursor: 0.8 s"

    widget.set_channel_selected("B", True)
    assert widget.cursor_table.source_names == ("A", "B")
    widget.set_channel_selected("A", False)
    assert widget.cursor_table.source_names == ("B",)
    assert widget.cursor_table.value_text("A") is None
    widget.close()
    application.processEvents()


def test_cursor_table_uses_alias_unit_color_status_and_measurement_tooltip() -> None:
    application = QApplication.instance() or QApplication([])
    times = iter((10.0, 12.0))
    widget = GraphsWidget(clock=lambda: next(times))
    widget.update_channels(ChannelUpdate(("P",), (4.0,)))
    widget.update_channels(ChannelUpdate(("P",), (4.25,)))
    widget.set_channel_selected("P", True)
    metadata = ChannelMetadataRegistry()
    metadata.set("P", "Reactor Pressure", "bar", AlarmLimits(high=4.2))
    widget.set_channel_metadata(metadata)

    widget._update_cursor_values(1.8)

    assert widget.cursor_table.channel_text("P") == "Reactor Pressure"
    assert widget.cursor_table.value_text("P") == "4.25 bar"
    assert widget.cursor_table.status_text("P") == "HIGH"
    assert widget.cursor_table.swatch_color("P") == widget._series[
        "P"
    ].opts["pen"].color().name()
    tooltip = widget.cursor_table.measurement_tooltip("P")
    assert tooltip is not None
    assert "Value: 4.25 bar" in tooltip
    assert "Status: HIGH" in tooltip
    assert "Cursor: 1.80 s" in tooltip
    assert "Measurement: 2.00 s" in tooltip
    widget.close()
    application.processEvents()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5.0, "LOW-LOW"),
        (15.0, "LOW"),
        (50.0, "NORMAL"),
        (85.0, "HIGH"),
        (95.0, "HIGH-HIGH"),
    ],
)
def test_cursor_table_displays_existing_alarm_states(
    value: float,
    expected: str,
) -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget(clock=lambda: 10.0)
    widget.update_channels(ChannelUpdate(("A",), (value,)))
    widget.set_channel_selected("A", True)
    metadata = ChannelMetadataRegistry()
    metadata.set(
        "A",
        alarms=AlarmLimits(low_low=10, low=20, high=80, high_high=90),
    )
    widget.set_channel_metadata(metadata)

    widget._update_cursor_values(0.0)

    assert widget.cursor_table.status_text("A") == expected
    badge = widget.cursor_table._status_labels["A"]
    assert badge.objectName() == "graphCursorStatus"
    assert badge.property("alarmKind") == expected
    widget.close()
    application.processEvents()


def test_cursor_table_clears_stale_values_when_measurements_disappear() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget(clock=lambda: 10.0)
    widget.update_channels(ChannelUpdate(("A",), (83.002932,)))
    widget.set_channel_selected("A", True)
    widget._update_cursor_values(0.0)
    assert widget.cursor_table.value_text("A") == "83.00"

    widget.clear_history()

    assert widget.cursor_table.source_names == ("A",)
    assert widget.cursor_table.value_text("A") == "—"
    assert widget.cursor_table.status_text("A") == "—"
    assert widget.cursor_time_label.text() == "Cursor: —"
    widget.close()
    application.processEvents()


def test_cursor_table_uses_placeholders_for_non_finite_measurements() -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget(clock=lambda: 10.0)
    widget.update_channels(ChannelUpdate(("A",), (1.0,)))
    widget.set_channel_selected("A", True)

    widget.cursor_table.set_cursor_values(
        (widget._cursor_row("A", 0.0, float("nan"), cursor_time=0.0),)
    )

    assert widget.cursor_table.value_text("A") == "—"
    assert widget.cursor_table.status_text("A") == "—"
    widget.close()
    application.processEvents()


def test_cursor_table_expands_with_rows_and_does_not_scroll_internally() -> None:
    application = QApplication.instance() or QApplication([])
    names = tuple(f"Channel {index}" for index in range(1, 10))
    widget = GraphsWidget(clock=lambda: 10.0)
    widget.update_channels(ChannelUpdate(names, tuple(range(1, 10))))
    for name in names:
        widget.set_channel_selected(name, True)
    widget._update_cursor_values(0.0)
    widget.resize(900, 800)
    widget.show()
    application.processEvents()

    expected_height = (
        max(widget.cursor_table.horizontalHeader().sizeHint().height(), 28)
        + 9 * widget.cursor_table.verticalHeader().defaultSectionSize()
        + widget.cursor_table.frameWidth() * 2
    )
    assert widget.cursor_table.rowCount() == 9
    assert widget.cursor_table.height() == expected_height
    assert widget.cursor_table.verticalScrollBarPolicy() == (
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert widget.cursor_table.verticalScrollBar().maximum() == 0
    assert widget.cursor_table.horizontalScrollBar().maximum() == 0
    assert widget.page_scroll.verticalScrollBar().maximum() > 0
    widget.close()
    application.processEvents()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_cursor_table_status_badges_fit_vertically(theme: str) -> None:
    application = QApplication.instance() or QApplication([])
    apply_application_theme(application, theme)
    names = ("A", "B", "C")
    widget = GraphsWidget(clock=lambda: 10.0)
    widget.update_channels(ChannelUpdate(names, (1.0, 2.0, 3.0)))
    for name in names:
        widget.set_channel_selected(name, True)
    widget._update_cursor_values(0.0)
    widget.show()
    application.processEvents()

    table = widget.cursor_table
    last = table.rowCount() - 1
    for row in (0, last // 2, last):
        cell = table.cellWidget(row, 2)
        badge = cell.findChild(QLabel, "graphCursorStatus")
        assert badge is not None
        in_cell = badge.mapTo(cell, QPoint(0, 0))
        assert in_cell.y() >= 1
        assert in_cell.y() + badge.height() <= cell.height()
        assert table.rowHeight(row) >= badge.height() + 8
    widget.close()
    application.processEvents()


def test_multi_source_cursor_tables_remain_isolated() -> None:
    application = QApplication.instance() or QApplication([])
    widget = MultiSourceGraphsWidget()
    pico = widget.ensure_source("pico", "Pico")
    arduino = widget.ensure_source("arduino", "Arduino")
    pico.update_channels(ChannelUpdate(("TEMP",), (25.0,)))
    arduino.update_channels(ChannelUpdate(("RPM",), (1_500,)))
    pico.set_channel_selected("TEMP", True)
    arduino.set_channel_selected("RPM", True)
    pico._update_cursor_values(0.0)
    arduino._update_cursor_values(0.0)

    assert pico.cursor_table.source_names == ("TEMP",)
    assert pico.cursor_table.value_text("TEMP") == "25.00"
    assert pico.cursor_table.value_text("RPM") is None
    assert arduino.cursor_table.source_names == ("RPM",)
    assert arduino.cursor_table.value_text("RPM") == "1500.00"
    assert arduino.cursor_table.value_text("TEMP") is None
    widget.close()
    application.processEvents()
