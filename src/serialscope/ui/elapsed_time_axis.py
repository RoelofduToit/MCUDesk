"""Human-readable elapsed-time axis for PyQtGraph."""

import math

import pyqtgraph as pg


def format_elapsed_tick(elapsed_seconds: float) -> str:
    """Format a seconds-valued graph tick without SI prefixes."""
    seconds = max(0.0, elapsed_seconds)
    if seconds < 60.0:
        return f"{_compact_number(seconds)} s"
    if seconds < 3_600.0:
        return f"{_compact_number(seconds / 60.0)} min"

    total_minutes = round(seconds / 60.0)
    hours, minutes = divmod(total_minutes, 60)
    if minutes == 0:
        return f"{hours} h"
    return f"{hours} h {minutes} min"


def _compact_number(value: float) -> str:
    if math.isclose(value, round(value), abs_tol=1e-9):
        return str(round(value))
    return f"{value:.1f}".rstrip("0").rstrip(".")


class ElapsedTimeAxis(pg.AxisItem):
    """Render seconds-valued ticks as readable elapsed durations."""

    def __init__(self, orientation: str = "bottom", **kwargs: object) -> None:
        super().__init__(orientation=orientation, **kwargs)
        self.enableAutoSIPrefix(False)
        self.setLabel("Elapsed Time")

    def tickStrings(
        self,
        values: list[float],
        scale: float,
        spacing: float,
    ) -> list[str]:
        del scale, spacing
        return [format_elapsed_tick(value) for value in values]
