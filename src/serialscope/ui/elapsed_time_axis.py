"""Human-readable elapsed-time axis for PyQtGraph."""

from dataclasses import dataclass
import math

import pyqtgraph as pg


@dataclass(frozen=True, slots=True)
class TimeTickStrategy:
    """Deterministic tick spacing for one elapsed-time window."""

    major_seconds: float
    minor_seconds: float


TIME_TICK_STRATEGIES = {
    10.0: TimeTickStrategy(2.0, 1.0),
    30.0: TimeTickStrategy(5.0, 1.0),
    60.0: TimeTickStrategy(10.0, 2.0),
    300.0: TimeTickStrategy(60.0, 20.0),
    600.0: TimeTickStrategy(120.0, 60.0),
    1_800.0: TimeTickStrategy(300.0, 60.0),
    3_600.0: TimeTickStrategy(600.0, 120.0),
}


def tick_strategy(window_seconds: float) -> TimeTickStrategy:
    """Return fixed preferred spacing, with a 1/2/5 fallback."""
    configured = TIME_TICK_STRATEGIES.get(float(window_seconds))
    if configured is not None:
        return configured

    target = max(float(window_seconds), 1e-9) / 6.0
    magnitude = 10.0 ** math.floor(math.log10(target))
    normalized = target / magnitude
    if normalized <= 1.0:
        multiplier = 1.0
    elif normalized <= 2.0:
        multiplier = 2.0
    elif normalized <= 5.0:
        multiplier = 5.0
    else:
        multiplier = 10.0
    major = multiplier * magnitude
    return TimeTickStrategy(major, major / 5.0)


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
        self._window_seconds = 60.0
        self._strategy = tick_strategy(self._window_seconds)
        self.enableAutoSIPrefix(False)
        self.setLabel("Elapsed Time")

    @property
    def window_seconds(self) -> float:
        return self._window_seconds

    @property
    def major_tick_spacing(self) -> float:
        return self._strategy.major_seconds

    def set_time_window(self, window_seconds: float) -> None:
        """Select deterministic spacing for the active visible window."""
        self._window_seconds = float(window_seconds)
        self._strategy = tick_strategy(self._window_seconds)
        self.picture = None
        self.update()

    def boundingRect(self):  # noqa: N802
        """Allow endpoint labels to extend slightly beyond the plot edges."""
        return super().boundingRect().adjusted(-24.0, 0.0, 24.0, 0.0)

    def tickValues(
        self,
        minVal: float,
        maxVal: float,
        size: float,
    ) -> list[tuple[float, list[float]]]:
        """Return globally aligned major and subordinate minor ticks."""
        del size
        lower = max(0.0, min(minVal, maxVal))
        upper = max(0.0, max(minVal, maxVal))
        major = _aligned_ticks(lower, upper, self._strategy.major_seconds)
        minor = [
            value
            for value in _aligned_ticks(lower, upper, self._strategy.minor_seconds)
            if not _is_multiple(value, self._strategy.major_seconds)
        ]
        return [
            (self._strategy.major_seconds, major),
            (self._strategy.minor_seconds, minor),
        ]

    def tickStrings(
        self,
        values: list[float],
        scale: float,
        spacing: float,
    ) -> list[str]:
        del scale
        if spacing < self._strategy.major_seconds and not math.isclose(
            spacing,
            self._strategy.major_seconds,
        ):
            return ["" for _value in values]
        return [self._format_window_tick(value) for value in values]

    def _format_window_tick(self, elapsed_seconds: float) -> str:
        seconds = max(0.0, elapsed_seconds)
        if self._window_seconds <= 60.0:
            return f"{_compact_number(seconds)} s"
        return f"{_compact_number(seconds / 60.0)} min"


def _aligned_ticks(lower: float, upper: float, spacing: float) -> list[float]:
    first = math.ceil((lower - spacing * 1e-9) / spacing)
    last = math.floor((upper + spacing * 1e-9) / spacing)
    if last < first or last - first > 2_000:
        return []
    return [index * spacing for index in range(first, last + 1)]


def _is_multiple(value: float, spacing: float) -> bool:
    return math.isclose(value / spacing, round(value / spacing), abs_tol=1e-9)
