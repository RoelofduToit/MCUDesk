import math

import pytest

from serialscope.data import AlarmLimits, AlarmState, evaluate_alarm


def test_no_limits_is_normal() -> None:
    assert evaluate_alarm(10, AlarmLimits()) is AlarmState.NORMAL


@pytest.mark.parametrize(
    ("value", "state"),
    [
        (79, AlarmState.LOW_LOW),
        (80, AlarmState.LOW_LOW),
        (81, AlarmState.LOW),
        (90, AlarmState.LOW),
        (91, AlarmState.NORMAL),
        (109, AlarmState.NORMAL),
        (110, AlarmState.HIGH),
        (119, AlarmState.HIGH),
        (120, AlarmState.HIGH_HIGH),
        (121, AlarmState.HIGH_HIGH),
    ],
)
def test_alarm_states_and_inclusive_boundaries(value: float, state: AlarmState) -> None:
    limits = AlarmLimits(low_low=80, low=90, high=110, high_high=120)
    assert evaluate_alarm(value, limits) is state


def test_partial_limits_work() -> None:
    limits = AlarmLimits(low=10, high=20)
    assert evaluate_alarm(9, limits) is AlarmState.LOW
    assert evaluate_alarm(15, limits) is AlarmState.NORMAL
    assert evaluate_alarm(21, limits) is AlarmState.HIGH


@pytest.mark.parametrize(
    "limits",
    [
        {"low": 20, "high": 10},
        {"low_low": 10, "low": 10},
        {"high": 120, "high_high": 110},
    ],
)
def test_invalid_limit_order_is_rejected(limits: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="must increase"):
        AlarmLimits(**limits)


@pytest.mark.parametrize("value", [None, math.nan, math.inf, -math.inf])
def test_missing_or_nonfinite_measurement_is_unknown(value: float | None) -> None:
    assert evaluate_alarm(value, AlarmLimits(high=10)) is AlarmState.UNKNOWN
