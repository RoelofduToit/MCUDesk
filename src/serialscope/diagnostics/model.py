"""Immutable diagnostics snapshots and user-facing settings."""

from __future__ import annotations

from dataclasses import dataclass


MIN_STALE_MULTIPLIER = 2.0
MAX_STALE_MULTIPLIER = 20.0
MIN_GAP_MULTIPLIER = 2.0
MAX_GAP_MULTIPLIER = 20.0
MIN_BASELINE_SAMPLES = 3
MAX_INTERVAL_WINDOW = 500
MAX_GAP_HISTORY = 100


@dataclass(frozen=True, slots=True)
class DiagnosticsSettings:
    """Conservative live-quality thresholds."""

    stale_multiplier: float = 5.0
    gap_multiplier: float = 5.0
    min_samples: int = 5
    interval_window: int = 120
    gap_history: int = 50
    expected_interval_s: float | None = None
    rate_window_s: float = 2.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "stale_multiplier",
            min(MAX_STALE_MULTIPLIER, max(MIN_STALE_MULTIPLIER, float(self.stale_multiplier))),
        )
        object.__setattr__(
            self,
            "gap_multiplier",
            min(MAX_GAP_MULTIPLIER, max(MIN_GAP_MULTIPLIER, float(self.gap_multiplier))),
        )
        object.__setattr__(
            self,
            "min_samples",
            min(50, max(MIN_BASELINE_SAMPLES, int(self.min_samples))),
        )
        object.__setattr__(
            self,
            "interval_window",
            min(MAX_INTERVAL_WINDOW, max(20, int(self.interval_window))),
        )
        object.__setattr__(
            self,
            "gap_history",
            min(MAX_GAP_HISTORY, max(10, int(self.gap_history))),
        )
        expected = self.expected_interval_s
        if expected is not None:
            expected = float(expected)
            object.__setattr__(self, "expected_interval_s", expected if expected > 0 else None)
        object.__setattr__(self, "rate_window_s", max(0.5, float(self.rate_window_s)))


@dataclass(frozen=True, slots=True)
class ChannelDiagnosticsSnapshot:
    name: str
    updates: int
    last_update_age_s: float | None
    measured_rate_hz: float | None
    average_interval_s: float | None
    max_interval_s: float | None
    jitter_s: float | None
    state: str
    stale: bool


@dataclass(frozen=True, slots=True)
class GapEventSnapshot:
    start_s: float
    end_s: float
    duration_s: float
    channel: str | None


@dataclass(frozen=True, slots=True)
class SourceDiagnosticsSnapshot:
    source_id: str
    connected: bool
    uptime_s: float | None
    bytes_received: int
    lines_received: int
    structured_updates: int
    parser_errors: int
    unrecognized_lines: int
    parser_success_rate: float | None
    reconnects: int
    last_rx_age_s: float | None
    last_structured_age_s: float | None
    rx_bytes_per_s: float | None
    lines_per_s: float | None
    data_age_s: float | None
    longest_gap_s: float | None
    channels: tuple[ChannelDiagnosticsSnapshot, ...]
    gaps: tuple[GapEventSnapshot, ...]
