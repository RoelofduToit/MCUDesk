import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from serialscope.ui.elapsed_time_axis import (
    ElapsedTimeAxis,
    format_elapsed_tick,
    tick_strategy,
)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0 s"),
        (10, "10 s"),
        (30, "30 s"),
        (60, "1 min"),
        (300, "5 min"),
        (600, "10 min"),
        (1_800, "30 min"),
        (3_600, "1 h"),
        (4_500, "1 h 15 min"),
        (5_400, "1 h 30 min"),
        (7_200, "2 h"),
    ],
)
def test_elapsed_tick_formatting(seconds: float, expected: str) -> None:
    label = format_elapsed_tick(seconds)

    assert label == expected
    assert "ks" not in label.lower()


def test_fractional_ticks_are_compact() -> None:
    assert format_elapsed_tick(12.25) == "12.2 s"
    assert format_elapsed_tick(90) == "1.5 min"


def test_axis_disables_si_prefix_and_formats_tick_values() -> None:
    application = QApplication.instance() or QApplication([])
    axis = ElapsedTimeAxis()
    axis.set_time_window(3_600.0)

    assert axis.tickStrings([0, 600, 3_600], 1.0, 600.0) == [
        "0 min",
        "10 min",
        "60 min",
    ]
    assert axis.labelText == "Elapsed Time"
    assert axis.autoSIPrefix is False
    application.processEvents()


@pytest.mark.parametrize(
    ("window", "major_spacing", "expected_ticks"),
    [
        (10.0, 2.0, [0, 2, 4, 6, 8, 10]),
        (30.0, 5.0, [0, 5, 10, 15, 20, 25, 30]),
        (60.0, 10.0, [0, 10, 20, 30, 40, 50, 60]),
        (300.0, 60.0, [0, 60, 120, 180, 240, 300]),
        (600.0, 120.0, [0, 120, 240, 360, 480, 600]),
        (1_800.0, 300.0, [0, 300, 600, 900, 1_200, 1_500, 1_800]),
        (3_600.0, 600.0, [0, 600, 1_200, 1_800, 2_400, 3_000, 3_600]),
    ],
)
def test_predefined_windows_use_deterministic_major_ticks(
    window: float,
    major_spacing: float,
    expected_ticks: list[float],
) -> None:
    application = QApplication.instance() or QApplication([])
    axis = ElapsedTimeAxis()
    axis.set_time_window(window)

    levels = axis.tickValues(0.0, window, 1_000.0)

    assert axis.window_seconds == window
    assert axis.major_tick_spacing == major_spacing
    assert levels[0] == (major_spacing, expected_ticks)
    labels = axis.tickStrings(expected_ticks, 1.0, major_spacing)
    expected_unit = "s" if window <= 60.0 else "min"
    assert all(label.endswith(expected_unit) for label in labels)
    assert all("." not in label for label in labels)
    assert not any(
        awkward in label
        for label in labels
        for awkward in ("3.3 min", "6.7 min", "13.3 min", "16.7 min")
    )
    application.processEvents()


def test_scrolling_ticks_stay_aligned_to_global_major_multiples() -> None:
    application = QApplication.instance() or QApplication([])
    axis = ElapsedTimeAxis()
    axis.set_time_window(1_800.0)

    major_spacing, ticks = axis.tickValues(720.0, 2_520.0, 1_000.0)[0]

    assert major_spacing == 300.0
    assert ticks == [900.0, 1_200.0, 1_500.0, 1_800.0, 2_100.0, 2_400.0]
    assert all(tick % major_spacing == 0 for tick in ticks)
    application.processEvents()


def test_additional_windows_use_one_two_five_tick_progression() -> None:
    strategy = tick_strategy(120.0)

    assert strategy.major_seconds == 20.0
    assert strategy.minor_seconds == 4.0
