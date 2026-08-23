import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog

from serialscope.parsing import ChannelUpdate
from serialscope.replay import ReplaySample, ReplaySession, ReplaySource
from serialscope.settings import ApplicationSettings
from serialscope.ui.channel_tile import SPARKLINE_MAX_SAMPLES
from serialscope.ui.dashboard_widget import (
    DASHBOARD_TREND_MAX_POINTS_PER_CHANNEL,
    DASHBOARD_TREND_RETENTION_SECONDS,
    DashboardWidget,
    visible_trend_values,
)
from serialscope.ui.graphs_widget import GraphsWidget
from serialscope.ui.main_window import MainWindow


class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.mark.parametrize(
    ("window_seconds", "expected"),
    [
        (30, (3_570, 3_600)),
        (60, (3_540, 3_570, 3_600)),
        (300, (3_300, 3_540, 3_570, 3_600)),
        (600, (3_000, 3_300, 3_540, 3_570, 3_600)),
        (1_800, (1_800, 3_000, 3_300, 3_540, 3_570, 3_600)),
        (3_600, (0, 1_800, 3_000, 3_300, 3_540, 3_570, 3_600)),
    ],
)
def test_each_trend_duration_filters_by_elapsed_timestamp(
    window_seconds: int,
    expected: tuple[int, ...],
) -> None:
    timestamps = (0.0, 1_800.0, 3_000.0, 3_300.0, 3_540.0, 3_570.0, 3_600.0)
    values = tuple(int(timestamp) for timestamp in timestamps)

    assert visible_trend_values(timestamps, values, window_seconds) == expected


@pytest.mark.parametrize("rate_hz", [1, 5, 10])
def test_one_minute_window_is_time_based_at_multiple_sample_rates(
    rate_hz: int,
) -> None:
    timestamps = tuple(index / rate_hz for index in range(120 * rate_hz + 1))
    values = timestamps

    visible = visible_trend_values(timestamps, values, 60)

    assert visible[0] == pytest.approx(60.0)
    assert visible[-1] == pytest.approx(120.0)
    assert len(visible) <= SPARKLINE_MAX_SAMPLES


def test_irregular_timestamps_are_filtered_without_synthetic_points() -> None:
    timestamps = (0.0, 1.0, 2.1, 4.5, 5.0, 12.0, 13.2)
    values = (0, 1, 2, 4, 5, 12, 13)

    assert visible_trend_values(timestamps, values, 10) == (4, 5, 12, 13)


def test_default_is_one_minute_with_separate_one_hour_retention() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()

    assert widget.trend_window_seconds == 60
    assert widget._trend.window_seconds == DASHBOARD_TREND_RETENTION_SECONDS
    assert (
        widget._trend.max_points_per_channel
        == DASHBOARD_TREND_MAX_POINTS_PER_CHANNEL
    )
    widget.close()
    application.processEvents()


def test_shorter_and_longer_windows_redraw_from_retained_history() -> None:
    application = QApplication.instance() or QApplication([])
    clock = ManualClock()
    widget = DashboardWidget(clock=clock)
    for timestamp, value in ((0, 1), (120, 2), (600, 3)):
        clock.now = timestamp
        widget.update_channels(ChannelUpdate(("A",), (value,)))
    widget.set_channel_selected("A", True)
    tile = widget._tiles["A"]
    geometry = tile.geometry()

    assert tile.sparkline.values == (3.0,)
    widget.set_trend_window_seconds(600)
    assert tile.sparkline.values == (1.0, 2.0, 3.0)
    widget.set_trend_window_seconds(300)
    assert tile.sparkline.values == (3.0,)
    assert widget._trend.points("A")[1] == (1, 2, 3)
    assert tile.geometry() == geometry
    widget.close()
    application.processEvents()


def test_live_tile_and_new_tile_use_current_window_and_latest_value() -> None:
    application = QApplication.instance() or QApplication([])
    clock = ManualClock()
    widget = DashboardWidget(clock=clock)
    widget.set_trend_window_seconds(300)
    for timestamp, values in ((0, (1, 10)), (250, (2, 20)), (400, (3, 30))):
        clock.now = timestamp
        widget.update_channels(ChannelUpdate(("A", "B"), values))
    widget.set_channel_selected("A", True)
    widget.set_channel_selected("B", True)

    assert widget._tiles["A"].sparkline.values == (2.0, 3.0)
    assert widget._tiles["B"].sparkline.values == (20.0, 30.0)
    clock.now = 450
    widget.update_channels(ChannelUpdate(("A",), (4,)))
    assert widget._tiles["A"].sparkline.values == (2.0, 3.0, 4.0)
    assert widget.tile_value_text("A") == "4"
    widget.close()
    application.processEvents()


def test_multi_source_histories_with_same_channel_name_remain_isolated() -> None:
    application = QApplication.instance() or QApplication([])
    clock = ManualClock()
    widget = DashboardWidget(clock=clock)
    widget.update_source("serial", "Serial", ChannelUpdate(("TEMP",), (10,)))
    clock.now = 10
    widget.update_source("modbus", "Modbus", ChannelUpdate(("TEMP",), (100,)))
    clock.now = 20
    widget.update_source("serial", "Serial", ChannelUpdate(("TEMP",), (20,)))
    widget.set_channel_selected("serial\x1fTEMP", True)
    widget.set_channel_selected("modbus\x1fTEMP", True)

    assert widget._tiles["serial\x1fTEMP"].sparkline.values == (10.0, 20.0)
    assert widget._tiles["modbus\x1fTEMP"].sparkline.values == (100.0,)
    widget.close()
    application.processEvents()


def test_multi_source_replay_uses_recorded_times_and_isolated_keys() -> None:
    application = QApplication.instance() or QApplication([])
    samples = (
        ReplaySample(0.0, {"A": 1}),
        ReplaySample(50.0, {"A": 2}),
        ReplaySample(100.0, {"A": 3}),
    )
    source_a = ReplaySource("a", "Serial", None, None, {}, ("A",), samples)
    source_b = ReplaySource(
        "b",
        "Modbus",
        None,
        None,
        {},
        ("A",),
        (ReplaySample(0.0, {"A": 10}), ReplaySample(90.0, {"A": 20})),
    )
    session = ReplaySession(
        Path("session"),
        {},
        source_a.channel_names,
        source_a.samples,
        (source_a, source_b),
    )
    widget = DashboardWidget()
    widget.load_replay(session)
    widget.set_channel_selected("a\x1fA", True)
    widget.set_channel_selected("b\x1fA", True)

    assert widget._tiles["a\x1fA"].sparkline.values == (2.0, 3.0)
    assert widget._tiles["b\x1fA"].sparkline.values == (20.0,)
    widget.close()
    application.processEvents()


def test_legacy_replay_uses_recorded_elapsed_time() -> None:
    application = QApplication.instance() or QApplication([])
    samples = (
        ReplaySample(0.0, {"A": 1}),
        ReplaySample(50.0, {"A": 2}),
        ReplaySample(100.0, {"A": 3}),
    )
    session = ReplaySession(Path("session"), {}, ("A",), samples)
    widget = DashboardWidget()

    widget.load_replay(session)
    widget.set_channel_selected("A", True)

    assert widget._tiles["A"].sparkline.values == (2.0, 3.0)
    widget.close()
    application.processEvents()


def test_calculated_channels_use_the_same_trend_path() -> None:
    application = QApplication.instance() or QApplication([])
    clock = ManualClock()
    widget = DashboardWidget(clock=clock)
    widget.update_channels(ChannelUpdate(("A", "SUM"), (1, 3)))
    clock.now = 20
    widget.update_channels(ChannelUpdate(("A", "SUM"), (2, 5), False))
    widget.set_channel_selected("SUM", True)

    assert widget._tiles["SUM"].sparkline.values == (3.0, 5.0)
    widget.close()
    application.processEvents()


def test_rendering_is_bounded_without_pruning_retained_measurements() -> None:
    application = QApplication.instance() or QApplication([])
    clock = ManualClock()
    widget = DashboardWidget(clock=clock)
    widget.set_trend_window_seconds(3_600)
    for index in range(100):
        clock.now = float(index)
        widget.update_channels(ChannelUpdate(("A",), (index,)))
    widget.set_channel_selected("A", True)

    assert widget._trend.sample_count("A") == 100
    assert len(widget._tiles["A"].sparkline.values) == SPARKLINE_MAX_SAMPLES
    assert widget._tiles["A"].sparkline.values[0] == 0.0
    assert widget._tiles["A"].sparkline.values[-1] == 99.0
    widget.close()
    application.processEvents()


@pytest.mark.parametrize("preset", ["Auto", "Compact", "Normal", "Large", "Extra large"])
def test_window_and_numeric_style_changes_preserve_tile_geometry(
    preset: str,
) -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    widget.update_channels(ChannelUpdate(("A",), (25.3,)))
    widget.set_channel_selected("A", True)
    widget.set_tile_size_preset(preset)
    widget.resize(900, 500)
    widget.show()
    application.processEvents()
    tile = widget._tiles["A"]
    geometry = tile.geometry()

    widget.set_numeric_display_style("technical_mono")
    widget.set_trend_window_seconds(1_800)
    application.processEvents()

    assert tile.geometry() == geometry
    assert tile.width() == tile.height()
    assert widget.numeric_display_style == "technical_mono"
    assert widget.trend_window_seconds == 1_800
    widget.close()
    application.processEvents()


def test_dashboard_window_does_not_change_graph_time_window_or_history() -> None:
    application = QApplication.instance() or QApplication([])
    dashboard = DashboardWidget()
    graphs = GraphsWidget()
    graphs.update_channels(ChannelUpdate(("A",), (1,)))
    history = graphs.history.points("A")

    dashboard.set_trend_window_seconds(1_800)

    assert graphs.time_window_seconds == 60
    assert graphs.history.points("A") == history
    dashboard.close()
    graphs.close()
    application.processEvents()


def test_main_window_loads_and_applies_trend_preference_live(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = QApplication.instance() or QApplication([])
    settings = ApplicationSettings(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    settings.set_dashboard_trend_window_seconds(600)
    window = MainWindow(port_scanner=lambda: [], application_settings=settings)
    window.dashboard_widget.update_channels(ChannelUpdate(("A",), (1,)))
    window.dashboard_widget.set_channel_selected("A", True)
    window.graphs_widget.update_channels(ChannelUpdate(("A",), (1,)))
    tile = window.dashboard_widget._tiles["A"]
    graph_history = window.graphs_widget.history.points("A")

    class AcceptedPreferences:
        DialogCode = QDialog.DialogCode
        selected_theme = window.selected_theme
        automatically_check_for_updates = True
        dashboard_numeric_style = window.dashboard_widget.numeric_display_style
        dashboard_trend_window_seconds = 1_800

        def __init__(self, *_args, **_kwargs) -> None:
            assert _kwargs["dashboard_trend_window_seconds"] == 600

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "serialscope.ui.main_window.PreferencesDialog",
        AcceptedPreferences,
    )

    assert window.dashboard_widget.trend_window_seconds == 600
    window._show_preferences()

    assert settings.dashboard_trend_window_seconds == 1_800
    assert window.dashboard_widget.trend_window_seconds == 1_800
    assert window.dashboard_widget._tiles["A"] is tile
    assert window.dashboard_widget.tile_value_text("A") == "1"
    assert window.graphs_widget.active_widget.time_window_seconds == 60
    assert window.graphs_widget.history.points("A") == graph_history
    window.close()
    application.processEvents()
