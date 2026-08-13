import math

import pytest

from serialscope.data import (
    calculate_statistics,
    interpolate_points,
    nearest_measurement,
    process_display_points,
    smooth_values,
)


def test_interpolation_off_preserves_points_and_source() -> None:
    x_values = (0.0, 2.0, 5.0)
    y_values = (1, 4, 2)
    original = x_values, y_values

    assert interpolate_points(x_values, y_values) == (
        x_values,
        (1.0, 4.0, 2.0),
    )
    assert (x_values, y_values) == original


def test_linear_interpolation_and_density() -> None:
    low_x, low_y = interpolate_points((0.0, 2.0), (0, 4), "linear", density=2)
    high_x, high_y = interpolate_points((0.0, 2.0), (0, 4), "linear", density=10)

    assert low_x == (0.0, 1.0, 2.0)
    assert low_y == (0.0, 2.0, 4.0)
    assert len(high_x) == 11
    assert high_y[5] == pytest.approx(2.0)


def test_pchip_is_shape_preserving_and_hits_measurements() -> None:
    x_values, y_values = interpolate_points(
        (0.0, 1.0, 2.0, 3.0),
        (0, 2, 2, 3),
        "pchip",
        density=5,
        max_gap=None,
    )

    assert x_values[::5] == (0.0, 1.0, 2.0, 3.0)
    assert y_values[::5] == pytest.approx((0.0, 2.0, 2.0, 3.0))
    assert min(y_values) >= 0.0
    assert max(y_values) <= 3.0


def test_maximum_gap_inserts_visible_break() -> None:
    x_values, y_values = interpolate_points(
        (0.0, 1.0, 30.0), (0, 1, 2), "linear", density=5, max_gap=5.0
    )

    assert math.isnan(x_values[-2])
    assert math.isnan(y_values[-2])
    assert x_values[-1] == 30.0
    assert y_values[-1] == 2.0


def test_display_output_is_bounded_for_large_sources() -> None:
    x_values = tuple(float(value) for value in range(20_001))
    y_values = tuple(range(20_001))
    display_x, _display_y = interpolate_points(
        x_values, y_values, "linear", density=10, max_gap=None
    )
    assert len(display_x) <= 100_000


def test_moving_average_and_window_size() -> None:
    source = (1, 3, 9, 15)
    assert smooth_values(source, "moving_average", window=2) == pytest.approx(
        (1, 2, 6, 12)
    )
    assert smooth_values(source, "moving_average", window=3) == pytest.approx(
        (1, 2, 13 / 3, 9)
    )
    assert source == (1, 3, 9, 15)


def test_ema_and_alpha_change_response() -> None:
    source = (0, 10, 10)
    slow = smooth_values(source, "ema", alpha=0.2)
    fast = smooth_values(source, "ema", alpha=0.8)
    assert slow == pytest.approx((0, 2, 3.6))
    assert fast == pytest.approx((0, 8, 9.6))


def test_processing_order_is_smoothing_then_interpolation() -> None:
    x_values, y_values = process_display_points(
        (0.0, 1.0, 2.0),
        (0, 10, 10),
        smoothing="ema",
        ema_alpha=0.5,
        interpolation="linear",
        density=2,
        max_gap=None,
    )
    assert x_values == pytest.approx((0, 0.5, 1, 1.5, 2))
    assert y_values == pytest.approx((0, 2.5, 5, 6.25, 7.5))


def test_statistics_use_only_measured_values_and_range() -> None:
    statistics = calculate_statistics(
        (0.0, 1.0, 2.0, 3.0), (1, 100, 3, 5), 1.5, 3.0
    )
    assert statistics is not None
    assert statistics.minimum == 3
    assert statistics.maximum == 5
    assert statistics.average == 4
    assert statistics.count == 2


def test_cursor_lookup_returns_nearest_actual_measurement() -> None:
    assert nearest_measurement((0.0, 4.0, 9.0), (10, 20, 30), 6.0) == (4.0, 20)
    assert nearest_measurement((0.0, 4.0, 9.0), (10, 20, 30), 8.0) == (9.0, 30)
