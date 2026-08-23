"""Bounded, Qt-independent history for live numeric channels."""

from collections import deque
from collections.abc import Callable
import math
import time

from serialscope.parsing import ChannelUpdate


class ChannelHistory:
    """Retain numeric channel samples within a monotonic time window."""

    def __init__(
        self,
        window_seconds: float = 3_600.0,
        clock: Callable[[], float] = time.monotonic,
        max_points_per_channel: int = 200_000,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("History window must be positive.")
        if max_points_per_channel < 1:
            raise ValueError("History point limit must be positive.")
        self._window_seconds = window_seconds
        self._max_points_per_channel = max_points_per_channel
        self._clock = clock
        self._origin: float | None = None
        self._samples: dict[str, deque[tuple[float, int | float]]] = {}

    @property
    def channel_names(self) -> tuple[str, ...]:
        return tuple(self._samples)

    @property
    def window_seconds(self) -> float:
        return self._window_seconds

    @property
    def max_points_per_channel(self) -> int:
        return self._max_points_per_channel

    def add_update(self, update: ChannelUpdate) -> None:
        """Record one structured update at its shared receive time."""
        self.add_update_at(update, self._clock())

    def add_update_at(self, update: ChannelUpdate, timestamp: float) -> None:
        """Record an update at an explicit monotonic/elapsed timestamp."""
        timestamp = float(timestamp)
        if not math.isfinite(timestamp):
            raise ValueError("History timestamp must be finite.")
        if self._origin is None:
            self._origin = timestamp
        for name, value in zip(update.names, update.values, strict=True):
            self._samples.setdefault(
                name, deque(maxlen=self._max_points_per_channel)
            ).append((timestamp, value))
        self._prune(timestamp)

    def points(self, name: str) -> tuple[tuple[float, ...], tuple[int | float, ...]]:
        """Return elapsed seconds and values for one channel."""
        samples = self._samples.get(name, ())
        origin = self._origin
        if origin is None:
            return (), ()
        return (
            tuple(timestamp - origin for timestamp, _value in samples),
            tuple(value for _timestamp, value in samples),
        )

    def sample_count(self, name: str) -> int:
        return len(self._samples.get(name, ()))

    def latest_elapsed(self, name: str) -> float | None:
        samples = self._samples.get(name)
        if not samples or self._origin is None:
            return None
        return samples[-1][0] - self._origin

    def reset(self) -> None:
        """Clear all samples and reset the elapsed-time origin."""
        self._origin = None
        self._samples.clear()

    def _prune(self, latest_timestamp: float) -> None:
        cutoff = latest_timestamp - self._window_seconds
        for samples in self._samples.values():
            while samples and samples[0][0] < cutoff:
                samples.popleft()
