"""Build CSV tables from actual stored measurements.

Rows are the union of actual sample timestamps for the selected channels.
A cell is filled only when that channel has a stored observation at that
timestamp. Missing observations stay empty. Display processing such as
smoothing and interpolation is never applied.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
from datetime import datetime
import math
from pathlib import Path

CURRENT_WINDOW = "window"
ALL_AVAILABLE = "all"


class DataExportError(Exception):
    """A user-presentable data export failure."""


@dataclass(frozen=True, slots=True)
class MeasurementSeries:
    """One selected channel's actual stored samples."""

    source_id: str
    source_display_name: str
    channel_name: str
    display_name: str
    unit: str
    elapsed: tuple[float, ...]
    values: tuple[int | float, ...]


@dataclass(frozen=True, slots=True)
class ExportTable:
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    channel_count: int
    row_count: int


def default_data_export_filename(when: datetime | None = None) -> str:
    stamp = (when or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
    return f"MCUDesk_Data_{stamp}.csv"


def format_csv_number(value: int | float) -> str:
    """Format a stored number with a portable decimal point."""
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    number = float(value)
    if not math.isfinite(number):
        return ""
    if number.is_integer() and abs(number) < 1e15:
        return str(int(number))
    return format(number, ".15g")


def _heading(series: MeasurementSeries, *, include_source: bool) -> str:
    label = series.display_name.strip() or series.channel_name
    unit = f" ({series.unit})" if series.unit.strip() else ""
    if include_source and series.source_display_name.strip():
        return f"{series.source_display_name} / {label}{unit}"
    return f"{label}{unit}"


def _include_source_context(series: tuple[MeasurementSeries, ...]) -> bool:
    if len({item.source_id for item in series if item.source_id}) > 1:
        return True
    headings = [_heading(item, include_source=False) for item in series]
    return len(headings) != len(set(headings))


def build_export_table(
    series: tuple[MeasurementSeries, ...],
    *,
    range_mode: str = ALL_AVAILABLE,
    time_window: tuple[float, float] | None = None,
) -> ExportTable:
    """Assemble CSV headers and rows from actual stored samples."""
    if not series:
        raise DataExportError("Select at least one graph channel before exporting data.")
    if range_mode not in {CURRENT_WINDOW, ALL_AVAILABLE}:
        raise DataExportError("Unknown data export range.")
    if range_mode == CURRENT_WINDOW:
        if time_window is None:
            raise DataExportError("The current graph time window is not available.")
        lower, upper = time_window
        if not math.isfinite(lower) or not math.isfinite(upper) or upper < lower:
            raise DataExportError("The current graph time window is not available.")

    include_source = _include_source_context(series)
    headers = ("Elapsed Time (s)",) + tuple(
        _heading(item, include_source=include_source) for item in series
    )

    rows_by_time: dict[float, dict[int, int | float]] = {}
    for index, item in enumerate(series):
        if len(item.elapsed) != len(item.values):
            raise DataExportError("A selected channel has mismatched sample times and values.")
        for elapsed, value in zip(item.elapsed, item.values, strict=True):
            if range_mode == CURRENT_WINDOW and not (lower <= elapsed <= upper):
                continue
            rows_by_time.setdefault(elapsed, {})[index] = value

    ordered_times = sorted(rows_by_time)
    rows: list[tuple[str, ...]] = []
    channel_count = len(series)
    for elapsed in ordered_times:
        cells = [f"{elapsed:.6f}"]
        observed = rows_by_time[elapsed]
        for index in range(channel_count):
            if index not in observed:
                cells.append("")
            else:
                cells.append(format_csv_number(observed[index]))
        rows.append(tuple(cells))

    if not rows:
        raise DataExportError("No measured samples fall within the selected export range.")
    return ExportTable(headers, tuple(rows), channel_count, len(rows))


def write_export_csv(path: Path, table: ExportTable) -> None:
    """Write one UTF-8 CSV using a portable decimal point."""
    try:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(table.headers)
            writer.writerows(table.rows)
    except (OSError, ValueError, csv.Error) as error:
        raise DataExportError(f"Could not export data:\n\n{error}") from error
