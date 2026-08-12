"""Bounded, Qt-independent history for live numeric channels."""

from collections import deque
from collections.abc import Callable
import time

from serialscope.parsing import ChannelUpdate


class ChannelHistory:
    """Retain numeric channel samples within a monotonic time window."""

    def __init__(
        self,
        window_seconds: float = 3_600.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("History window must be positive.")
        self._window_seconds = window_seconds
        self._clock = clock
        self._origin: float | None = None
        self._samples: dict[str, deque[tuple[float, int | float]]] = {}

    @property
    def channel_names(self) -> tuple[str, ...]:
        return tuple(self._samples)

    def add_update(self, update: ChannelUpdate) -> None:
        """Record one structured update at its shared receive time."""
        timestamp = self._clock()
        if self._origin is None:
            self._origin = timestamp
        for name, value in zip(update.names, update.values, strict=True):
            self._samples.setdefault(name, deque()).append((timestamp, value))
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

    def reset(self) -> None:
        """Clear all samples and reset the elapsed-time origin."""
        self._origin = None
        self._samples.clear()

    def _prune(self, latest_timestamp: float) -> None:
        cutoff = latest_timestamp - self._window_seconds
        for samples in self._samples.values():
            while samples and samples[0][0] < cutoff:
                samples.popleft()
