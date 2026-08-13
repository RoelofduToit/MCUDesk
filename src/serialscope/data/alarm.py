"""Deterministic, UI-independent channel alarm limit evaluation."""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Mapping


class AlarmState(str, Enum):
    UNKNOWN = "UNKNOWN"
    NORMAL = "NORMAL"
    LOW = "LOW"
    LOW_LOW = "LOW-LOW"
    HIGH = "HIGH"
    HIGH_HIGH = "HIGH-HIGH"

    @property
    def style_state(self) -> str:
        if self in {AlarmState.LOW_LOW, AlarmState.HIGH_HIGH}:
            return "alarm"
        if self in {AlarmState.LOW, AlarmState.HIGH}:
            return "warning"
        return "normal"


@dataclass(frozen=True, slots=True)
class AlarmLimits:
    low_low: float | None = None
    low: float | None = None
    high: float | None = None
    high_high: float | None = None

    def __post_init__(self) -> None:
        configured = [
            value
            for value in (self.low_low, self.low, self.high, self.high_high)
            if value is not None
        ]
        if any(not math.isfinite(value) for value in configured):
            raise ValueError("Alarm limits must be finite numbers.")
        if any(left >= right for left, right in zip(configured, configured[1:])):
            raise ValueError(
                "Alarm limits must increase in the order Low-Low, Low, High, High-High."
            )

    @property
    def is_configured(self) -> bool:
        return any(
            value is not None
            for value in (self.low_low, self.low, self.high, self.high_high)
        )

    def to_dict(self) -> dict[str, float]:
        return {
            name: value
            for name, value in (
                ("low_low", self.low_low),
                ("low", self.low),
                ("high", self.high),
                ("high_high", self.high_high),
            )
            if value is not None
        }

    @classmethod
    def from_mapping(cls, values: object) -> "AlarmLimits":
        if not isinstance(values, Mapping):
            return cls()
        parsed: dict[str, float | None] = {}
        for name in ("low_low", "low", "high", "high_high"):
            value = values.get(name)
            parsed[name] = None if value is None or value == "" else float(value)
        return cls(**parsed)


def evaluate_alarm(value: int | float | None, limits: AlarmLimits) -> AlarmState:
    """Evaluate one measurement, prioritizing the most severe configured state."""
    if value is None:
        return AlarmState.UNKNOWN
    numeric = float(value)
    if not math.isfinite(numeric):
        return AlarmState.UNKNOWN
    if limits.low_low is not None and numeric <= limits.low_low:
        return AlarmState.LOW_LOW
    if limits.high_high is not None and numeric >= limits.high_high:
        return AlarmState.HIGH_HIGH
    if limits.low is not None and numeric <= limits.low:
        return AlarmState.LOW
    if limits.high is not None and numeric >= limits.high:
        return AlarmState.HIGH
    return AlarmState.NORMAL
