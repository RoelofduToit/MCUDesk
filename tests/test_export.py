import csv
import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from serialscope.export import (
    ALL_AVAILABLE,
    CURRENT_WINDOW,
    DataExportError,
    MeasurementSeries,
    build_export_table,
    default_data_export_filename,
    format_csv_number,
    write_export_csv,
)
from serialscope.parsing import ChannelUpdate
from serialscope.replay import ReplaySample, ReplaySession
from serialscope.ui.export_data_dialog import ExportDataDialog
from serialscope.ui.graph_export import (
    GraphExportError,
    default_graph_export_filename,
    export_plot_item,
    resolve_graph_export_path,
)
from serialscope.ui.graphs_widget import GraphsWidget
from serialscope.ui.multi_graphs_widget import MultiSourceGraphsWidget


def _series(
    name: str,
    elapsed: tuple[float, ...],
    values: tuple[int | float, ...],
    *,
    source_id: str = "src",
    source_display_name: str = "Device",
    display_name: str = "",
    unit: str = "",
) -> MeasurementSeries:
    return MeasurementSeries(
        source_id=source_id,
        source_display_name=source_display_name,
        channel_name=name,
        display_name=display_name or name,
        unit=unit,
        elapsed=elapsed,
        values=values,
    )


def test_default_filenames_are_windows_safe() -> None:
    when = datetime(2026, 8, 22, 15, 4, 5)
    data_name = default_data_export_filename(when)
    graph_name = default_graph_export_filename(".png", when)
    for name in (data_name, graph_name):
        assert ":" not in name
        assert "*" not in name
        assert "?" not in name
        assert "<" not in name
        assert ">" not in name
        assert "|" not in name
        assert '"' not in name
    assert data_name == "MCUDesk_Data_2026-08-22_15-04-05.csv"
    assert graph_name == "MCUDesk_Graph_2026-08-22_15-04-05.png"


def test_csv_uses_period_decimal_and_preserves_integers() -> None:
    assert format_csv_number(25) == "25"
    assert format_csv_number(25.0) == "25"
    assert format_csv_number(25.3) == "25.3"
    assert "," not in format_csv_number(25.3)
    assert format_csv_number(float("nan")) == ""


def test_build_export_table_requires_selected_channels() -> None:
    with pytest.raises(DataExportError, match="Select at least one graph channel"):
        build_export_table(())


def test_export_includes_only_selected_channels_and_actual_values() -> None:
    table = build_export_table(
        (
            _series("TC1", (0.0, 1.0, 2.0), (25.0, 25.1, 25.2), unit="°C"),
            _series("PRESSURE", (0.0, 1.0, 2.0), (1.00, 1.01, 1.02), unit="bar"),
        )
    )
    assert table.headers == (
        "Elapsed Time (s)",
        "TC1 (°C)",
        "PRESSURE (bar)",
    )
    assert table.rows == (
        ("0.000000", "25", "1"),
        ("1.000000", "25.1", "1.01"),
        ("2.000000", "25.2", "1.02"),
    )
    assert table.channel_count == 2
    assert table.row_count == 3


def test_missing_values_stay_empty_and_are_not_zero_filled() -> None:
    table = build_export_table(
        (
            _series("TC1", (0.0, 1.0, 2.0), (25.0, 25.1, 25.2)),
            _series("PRESSURE", (0.0, 2.0), (1.00, 1.02)),
        )
    )
    assert table.rows[1] == ("1.000000", "25.1", "")
    assert "0" not in table.rows[1][2]


def test_event_rows_do_not_interpolate_or_smooth() -> None:
    table = build_export_table(
        (_series("TC1", (0.0, 2.0), (10.0, 20.0)),)
    )
    assert table.rows == (("0.000000", "10"), ("2.000000", "20"))
    assert all("15" not in "".join(row) for row in table.rows)


def test_current_window_filters_actual_samples_only() -> None:
    series = (
        _series("TC1", (0.0, 1.0, 2.0, 3.0), (1, 2, 3, 4)),
        _series("TC2", (0.0, 1.0, 2.0, 3.0), (10, 20, 30, 40)),
    )
    table = build_export_table(
        series, range_mode=CURRENT_WINDOW, time_window=(1.0, 2.0)
    )
    assert table.rows == (("1.000000", "2", "20"), ("2.000000", "3", "30"))
    all_table = build_export_table(series, range_mode=ALL_AVAILABLE)
    assert all_table.row_count == 4


def test_empty_window_raises_instead_of_writing_blank_csv() -> None:
    with pytest.raises(DataExportError, match="No measured samples"):
        build_export_table(
            (_series("TC1", (0.0, 1.0), (1, 2)),),
            range_mode=CURRENT_WINDOW,
            time_window=(10.0, 12.0),
        )


def test_multi_source_duplicate_display_names_keep_source_identity() -> None:
    table = build_export_table(
        (
            _series(
                "Temperature",
                (0.0,),
                (24.8,),
                source_id="a",
                source_display_name="Reactor A",
                unit="°C",
            ),
            _series(
                "Temperature",
                (0.0,),
                (31.2,),
                source_id="b",
                source_display_name="Reactor B",
                unit="°C",
            ),
        )
    )
    assert table.headers == (
        "Elapsed Time (s)",
        "Reactor A / Temperature (°C)",
        "Reactor B / Temperature (°C)",
    )
    assert table.rows == (("0.000000", "24.8", "31.2"),)


def test_csv_escaping_and_write_roundtrip(tmp_path: Path) -> None:
    table = build_export_table(
        (
            _series(
                "A",
                (0.0,),
                (1.5,),
                display_name="Temp, core",
                unit="°C",
            ),
        )
    )
    path = tmp_path / "export.csv"
    write_export_csv(path, table)
    text = path.read_text(encoding="utf-8")
    assert "Elapsed Time (s)" in text
    assert '"Temp, core (°C)"' in text
    with path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0][1] == "Temp, core (°C)"
    assert rows[1] == ["0.000000", "1.5"]


def test_history_snapshot_is_independent_of_later_updates() -> None:
    QApplication.instance() or QApplication([])
    clock = iter((100.0, 101.0)).__next__
    widget = GraphsWidget(clock=clock)
    widget.update_channels(ChannelUpdate(("TC1",), (25.0,)))
    widget.set_channel_selected("TC1", True)
    snapshot = widget.selected_measurement_series()
    widget.update_channels(ChannelUpdate(("TC1",), (26.0,)))
    assert snapshot[0].values == (25.0,)
    assert widget.history.points("TC1")[1] == (25.0, 26.0)
    widget.close()


def test_graphs_widget_exports_selected_channels_only() -> None:
    QApplication.instance() or QApplication([])
    widget = GraphsWidget(clock=iter((1.0, 2.0)).__next__)
    widget.update_channels(ChannelUpdate(("TC1", "TC2", "PRESSURE"), (25.0, 26.0, 1.0)))
    widget.set_channel_selected("TC1", True)
    widget.set_channel_selected("PRESSURE", True)
    series = widget.selected_measurement_series()
    assert [item.channel_name for item in series] == ["TC1", "PRESSURE"]
    table = build_export_table(series)
    assert "TC2" not in "".join(table.headers)
    widget.smoothing_combo.setCurrentText("Moving Average")
    widget.interpolation_combo.setCurrentText("Linear")
    smoothed = build_export_table(widget.selected_measurement_series())
    assert smoothed.rows == table.rows
    widget.close()


def test_replay_export_uses_recorded_samples() -> None:
    QApplication.instance() or QApplication([])
    session = ReplaySession(
        Path("session"),
        {},
        ("TC1", "TC2"),
        (
            ReplaySample(0.0, {"TC1": 25.0, "TC2": 26.0}),
            ReplaySample(1.0, {"TC1": 25.1, "TC2": None}),
        ),
    )
    widget = GraphsWidget()
    widget.load_replay(session)
    widget.set_channel_selected("TC1", True)
    widget.set_channel_selected("TC2", True)
    table = build_export_table(widget.selected_measurement_series())
    assert table.rows[0] == ("0.000000", "25", "26")
    assert table.rows[1] == ("1.000000", "25.1", "")
    widget.close()


def test_multi_source_widget_keeps_separate_temperature_columns() -> None:
    QApplication.instance() or QApplication([])
    widget = MultiSourceGraphsWidget()
    first = widget.ensure_source("a", "Reactor A")
    second = widget.ensure_source("b", "Reactor B")
    first.update_channels(ChannelUpdate(("Temperature",), (24.8,)))
    second.update_channels(ChannelUpdate(("Temperature",), (31.2,)))
    first.set_channel_selected("Temperature", True)
    second.set_channel_selected("Temperature", True)
    table = build_export_table(widget.selected_measurement_series())
    assert table.headers[1] == "Reactor A / Temperature"
    assert table.headers[2] == "Reactor B / Temperature"
    assert table.rows[0][1] == "24.8"
    assert table.rows[0][2] == "31.2"
    widget.close()


def test_export_dialog_defaults_to_current_window() -> None:
    application = QApplication.instance() or QApplication([])
    dialog = ExportDataDialog(live_history_limited=True)
    assert dialog.window_radio.isChecked()
    assert dialog.range_mode == CURRENT_WINDOW
    dialog.all_radio.setChecked(True)
    assert dialog.range_mode == ALL_AVAILABLE
    dialog.close()
    application.processEvents()


def test_graph_export_extension_handling() -> None:
    assert resolve_graph_export_path(Path("plot.png")) == Path("plot.png")
    assert resolve_graph_export_path(Path("plot.svg")) == Path("plot.svg")
    assert resolve_graph_export_path(Path("plot"), "PNG (*.png)") == Path("plot.png")
    assert resolve_graph_export_path(Path("plot"), "SVG (*.svg)") == Path("plot.svg")
    with pytest.raises(GraphExportError, match="Unsupported"):
        resolve_graph_export_path(Path("plot.pdf"), "PDF (*.pdf)")


def test_png_and_svg_export_do_not_change_graph_state(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    widget = GraphsWidget(clock=iter((10.0, 11.0, 12.0)).__next__)
    widget.update_channels(ChannelUpdate(("TC1", "PRESSURE"), (25.0, 1.0)))
    widget.set_channel_selected("TC1", True)
    widget.set_channel_selected("PRESSURE", True)
    widget.resize(800, 700)
    widget.show()
    application.processEvents()
    widget.refresh_plot()
    application.processEvents()

    selected = widget.selected_channels
    paused = widget.is_paused
    view = widget.plot_widget.viewRange()
    smoothing = widget.smoothing_combo.currentIndex()

    png = tmp_path / "graph.png"
    svg = tmp_path / "graph.svg"
    export_plot_item(widget.plot_widget.plotItem, png)
    export_plot_item(widget.plot_widget.plotItem, svg)

    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    svg_text = svg.read_text(encoding="utf-8", errors="replace").lower()
    assert "<svg" in svg_text
    assert "<image" not in svg_text
    assert widget.selected_channels == selected
    assert widget.is_paused == paused
    assert widget.plot_widget.viewRange() == view
    assert widget.smoothing_combo.currentIndex() == smoothing
    widget.close()
    application.processEvents()
