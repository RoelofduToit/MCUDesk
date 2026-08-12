import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from serialscope.ui.elapsed_time_axis import ElapsedTimeAxis, format_elapsed_tick


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

    assert axis.tickStrings([0, 600, 3_600], 1.0, 600.0) == [
        "0 s",
        "10 min",
        "1 h",
    ]
    assert axis.labelText == "Elapsed Time"
    assert axis.autoSIPrefix is False
    application.processEvents()
