"""Pure display processing and inspection helpers for graph measurements."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
import math
from statistics import fmean


MAX_DISPLAY_POINTS = 100_000


@dataclass(frozen=True, slots=True)
class ChannelStatistics:
    minimum: float
    maximum: float
    average: float
    count: int


def smooth_values(
    values: tuple[int | float, ...],
    method: str = "off",
    *,
    window: int = 5,
    alpha: float = 0.2,
) -> tuple[float, ...]:
    """Return display-smoothed values without changing the input measurements."""
    source = tuple(float(value) for value in values)
    if method == "off" or not source:
        return source
    if method == "moving_average":
        if not 2 <= window <= 100:
            raise ValueError("Moving-average window must be between 2 and 100.")
        result: list[float] = []
        running_sum = 0.0
        for index, value in enumerate(source):
            running_sum += value
            if index >= window:
                running_sum -= source[index - window]
            result.append(running_sum / min(index + 1, window))
        return tuple(result)
    if method == "ema":
        if not 0.01 <= alpha <= 1.0:
            raise ValueError("EMA alpha must be between 0.01 and 1.00.")
        result = [source[0]]
        for value in source[1:]:
            result.append(alpha * value + (1.0 - alpha) * result[-1])
        return tuple(result)
    raise ValueError(f"Unknown smoothing method: {method}")


def interpolate_points(
    x_values: tuple[float, ...],
    y_values: tuple[int | float, ...],
    method: str = "off",
    *,
    density: int = 5,
    max_gap: float | None = 5.0,
    max_points: int = MAX_DISPLAY_POINTS,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Create bounded display points, inserting NaN breaks across large gaps."""
    if len(x_values) != len(y_values):
        raise ValueError("X and Y values must have matching lengths.")
    source_x = tuple(float(value) for value in x_values)
    source_y = tuple(float(value) for value in y_values)
    if method == "off" or len(source_x) < 2:
        return source_x, source_y
    if method not in {"linear", "pchip"}:
        raise ValueError(f"Unknown interpolation method: {method}")
    if density not in {2, 5, 10}:
        raise ValueError("Interpolation density must be 2, 5, or 10.")
    if any(right <= left for left, right in zip(source_x, source_x[1:])):
        raise ValueError("Interpolation timestamps must be strictly increasing.")

    interval_count = len(source_x) - 1
    effective_density = max(1, min(density, (max_points - 1) // interval_count))
    slopes = _pchip_slopes(source_x, source_y) if method == "pchip" else ()
    output_x: list[float] = [source_x[0]]
    output_y: list[float] = [source_y[0]]
    for index in range(interval_count):
        left_x, right_x = source_x[index], source_x[index + 1]
        gap = right_x - left_x
        if max_gap is not None and gap > max_gap:
            output_x.extend((math.nan, right_x))
            output_y.extend((math.nan, source_y[index + 1]))
            continue
        for step in range(1, effective_density + 1):
            fraction = step / effective_density
            x_value = left_x + fraction * gap
            if method == "linear":
                y_value = source_y[index] + fraction * (
                    source_y[index + 1] - source_y[index]
                )
            else:
                y_value = _hermite_value(
                    source_y[index],
                    source_y[index + 1],
                    slopes[index],
                    slopes[index + 1],
                    gap,
                    fraction,
                )
            output_x.append(x_value)
            output_y.append(y_value)
    return tuple(output_x), tuple(output_y)


def process_display_points(
    x_values: tuple[float, ...],
    y_values: tuple[int | float, ...],
    *,
    smoothing: str = "off",
    moving_average_window: int = 5,
    ema_alpha: float = 0.2,
    interpolation: str = "off",
    density: int = 5,
    max_gap: float | None = 5.0,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Apply measured -> smoothing -> interpolation for display only."""
    smoothed = smooth_values(
        y_values,
        smoothing,
        window=moving_average_window,
        alpha=ema_alpha,
    )
    return interpolate_points(
        x_values,
        smoothed,
        interpolation,
        density=density,
        max_gap=max_gap,
    )


def calculate_statistics(
    x_values: tuple[float, ...],
    y_values: tuple[int | float, ...],
    lower: float | None = None,
    upper: float | None = None,
) -> ChannelStatistics | None:
    """Calculate statistics from measured samples inside an optional X range."""
    selected = [
        float(value)
        for timestamp, value in zip(x_values, y_values, strict=True)
        if (lower is None or timestamp >= lower) and (upper is None or timestamp <= upper)
    ]
    if not selected:
        return None
    return ChannelStatistics(min(selected), max(selected), fmean(selected), len(selected))


def nearest_measurement(
    x_values: tuple[float, ...],
    y_values: tuple[int | float, ...],
    target: float,
) -> tuple[float, int | float] | None:
    """Return the nearest actual measurement without interpolating a value."""
    if not x_values:
        return None
    index = bisect_left(x_values, target)
    if index == 0:
        nearest = 0
    elif index == len(x_values):
        nearest = len(x_values) - 1
    else:
        nearest = index - 1 if target - x_values[index - 1] <= x_values[index] - target else index
    return x_values[nearest], y_values[nearest]


def _pchip_slopes(x_values: tuple[float, ...], y_values: tuple[float, ...]) -> tuple[float, ...]:
    count = len(x_values)
    if count == 2:
        slope = (y_values[1] - y_values[0]) / (x_values[1] - x_values[0])
        return slope, slope
    intervals = tuple(right - left for left, right in zip(x_values, x_values[1:]))
    deltas = tuple(
        (right - left) / interval
        for left, right, interval in zip(
            y_values[:-1], y_values[1:], intervals, strict=True
        )
    )
    slopes = [0.0] * count
    slopes[0] = _endpoint_slope(intervals[0], intervals[1], deltas[0], deltas[1])
    slopes[-1] = _endpoint_slope(intervals[-1], intervals[-2], deltas[-1], deltas[-2])
    for index in range(1, count - 1):
        if deltas[index - 1] == 0 or deltas[index] == 0 or deltas[index - 1] * deltas[index] < 0:
            slopes[index] = 0.0
        else:
            first_weight = 2 * intervals[index] + intervals[index - 1]
            second_weight = intervals[index] + 2 * intervals[index - 1]
            slopes[index] = (first_weight + second_weight) / (
                first_weight / deltas[index - 1] + second_weight / deltas[index]
            )
    return tuple(slopes)


def _endpoint_slope(here: float, adjacent: float, delta: float, adjacent_delta: float) -> float:
    slope = ((2 * here + adjacent) * delta - here * adjacent_delta) / (here + adjacent)
    if slope * delta <= 0:
        return 0.0
    if delta * adjacent_delta < 0 and abs(slope) > abs(3 * delta):
        return 3 * delta
    return slope


def _hermite_value(y0: float, y1: float, m0: float, m1: float, width: float, t: float) -> float:
    return (
        (2 * t**3 - 3 * t**2 + 1) * y0
        + (t**3 - 2 * t**2 + t) * width * m0
        + (-2 * t**3 + 3 * t**2) * y1
        + (t**3 - t**2) * width * m1
    )
