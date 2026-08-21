"""Incremental, bounded diagnostics from observed source events."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
import time
from collections.abc import Callable

from serialscope.diagnostics.model import (
    ChannelDiagnosticsSnapshot,
    DiagnosticsSettings,
    GapEventSnapshot,
    SourceDiagnosticsSnapshot,
)
from serialscope.parsing.observation import ParserObservation


def _finite(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return value


def _mean_stdev(values: deque[float]) -> tuple[float | None, float | None]:
    count = len(values)
    if count < 1:
        return None, None
    mean = sum(values) / count
    if count < 2:
        return mean, None
    variance = sum((item - mean) ** 2 for item in values) / (count - 1)
    return mean, math.sqrt(max(0.0, variance))


def _median(values: deque[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


@dataclass
class _ChannelState:
    name: str
    updates: int = 0
    last_time: float | None = None
    first_time: float | None = None
    intervals: deque[float] = field(default_factory=deque)
    max_interval: float = 0.0


@dataclass
class _ByteSample:
    time: float
    bytes: int
    lines: int


@dataclass
class _SourceState:
    source_id: str
    connected: bool = False
    ever_connected: bool = False
    connected_since: float | None = None
    last_uptime_s: float | None = None
    bytes_received: int = 0
    lines_received: int = 0
    structured_updates: int = 0
    parser_errors: int = 0
    unrecognized_lines: int = 0
    reconnects: int = 0
    last_rx: float | None = None
    last_structured: float | None = None
    last_activity: float | None = None
    longest_gap_s: float = 0.0
    channels: dict[str, _ChannelState] = field(default_factory=dict)
    gaps: deque[GapEventSnapshot] = field(default_factory=deque)
    rx_samples: deque[_ByteSample] = field(default_factory=deque)


class DiagnosticsCollector:
    """Observe per-source activity using an injectable monotonic clock."""

    def __init__(
        self,
        settings: DiagnosticsSettings | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings or DiagnosticsSettings()
        self._clock = clock
        self._sources: dict[str, _SourceState] = {}

    def _source(self, source_id: str) -> _SourceState:
        current = self._sources.get(source_id)
        if current is None:
            current = _SourceState(
                source_id,
                gaps=deque(maxlen=self.settings.gap_history),
                rx_samples=deque(maxlen=200),
            )
            self._sources[source_id] = current
        return current

    def _now(self, now: float | None) -> float:
        return self._clock() if now is None else now

    def _baseline_interval(self, channel: _ChannelState) -> float | None:
        if self.settings.expected_interval_s:
            return self.settings.expected_interval_s
        return _median(channel.intervals)

    def source_ids(self) -> tuple[str, ...]:
        return tuple(self._sources)

    def apply_settings(self, settings: DiagnosticsSettings) -> None:
        self.settings = settings
        for source in self._sources.values():
            source.gaps = deque(source.gaps, maxlen=settings.gap_history)
            for channel in source.channels.values():
                channel.intervals = deque(channel.intervals, maxlen=settings.interval_window)

    def note_connected(self, source_id: str, now: float | None = None) -> None:
        source = self._source(source_id)
        current = self._now(now)
        if source.ever_connected:
            source.reconnects += 1
        source.ever_connected = True
        source.connected = True
        source.connected_since = current

    def note_disconnected(self, source_id: str, now: float | None = None) -> None:
        source = self._source(source_id)
        current = self._now(now)
        if source.connected and source.connected_since is not None:
            source.last_uptime_s = max(0.0, current - source.connected_since)
        source.connected = False
        source.connected_since = None

    def note_removed(self, source_id: str) -> None:
        self._sources.pop(source_id, None)

    def reset_live(self, source_id: str | None = None) -> None:
        """Reset counters/timing only; does not touch acquisition or recordings."""
        if source_id is None:
            ids = tuple(self._sources)
        else:
            ids = (source_id,)
        connected = {
            identity: self._sources[identity].connected
            for identity in ids
            if identity in self._sources
        }
        for identity in ids:
            self._sources.pop(identity, None)
            if connected.get(identity):
                self.note_connected(identity)

    def note_bytes(self, source_id: str, byte_count: int, now: float | None = None) -> None:
        if byte_count <= 0:
            return
        source = self._source(source_id)
        current = self._now(now)
        source.bytes_received += byte_count
        source.last_rx = current
        self._note_activity(source, current)
        source.rx_samples.append(_ByteSample(current, byte_count, 0))

    def note_parser_observation(
        self,
        source_id: str,
        observation: ParserObservation,
        now: float | None = None,
    ) -> None:
        if observation.lines <= 0 and observation.malformed <= 0:
            return
        source = self._source(source_id)
        current = self._now(now)
        source.lines_received += observation.lines
        source.parser_errors += observation.malformed
        source.unrecognized_lines += observation.unrecognized
        if observation.lines:
            source.rx_samples.append(_ByteSample(current, 0, observation.lines))

    def note_structured_update(
        self,
        source_id: str,
        names: tuple[str, ...],
        now: float | None = None,
    ) -> None:
        source = self._source(source_id)
        current = self._now(now)
        source.structured_updates += 1
        source.last_structured = current
        self._note_activity(source, current)
        for name in names:
            self._note_channel(source, name, current)

    def snapshot(self, source_id: str, now: float | None = None) -> SourceDiagnosticsSnapshot:
        source = self._source(source_id)
        current = self._now(now)
        classified = observation_rate(source.structured_updates, source.parser_errors)
        uptime = source.last_uptime_s
        if source.connected and source.connected_since is not None:
            uptime = max(0.0, current - source.connected_since)
        channels = tuple(
            self._channel_snapshot(channel, current)
            for channel in sorted(source.channels.values(), key=lambda item: item.name.casefold())
        )
        return SourceDiagnosticsSnapshot(
            source_id=source.source_id,
            connected=source.connected,
            uptime_s=_finite(uptime),
            bytes_received=source.bytes_received,
            lines_received=source.lines_received,
            structured_updates=source.structured_updates,
            parser_errors=source.parser_errors,
            unrecognized_lines=source.unrecognized_lines,
            parser_success_rate=classified,
            reconnects=source.reconnects,
            last_rx_age_s=_age(source.last_rx, current),
            last_structured_age_s=_age(source.last_structured, current),
            rx_bytes_per_s=self._window_rate(source, current, "bytes"),
            lines_per_s=self._window_rate(source, current, "lines"),
            data_age_s=_age(source.last_activity, current),
            longest_gap_s=source.longest_gap_s or None,
            channels=channels,
            gaps=tuple(source.gaps),
        )

    def session_summary(self, source_id: str, now: float | None = None) -> dict[str, object]:
        snap = self.snapshot(source_id, now)
        channels = {
            channel.name: {
                "updates": channel.updates,
                "longest_gap_s": channel.max_interval_s,
                "average_interval_s": channel.average_interval_s,
                "measured_rate_hz": channel.measured_rate_hz,
            }
            for channel in snap.channels
        }
        return {
            "source_id": snap.source_id,
            "reconnects": snap.reconnects,
            "longest_gap_s": snap.longest_gap_s,
            "structured_updates": snap.structured_updates,
            "parser_errors": snap.parser_errors,
            "bytes_received": snap.bytes_received,
            "lines_received": snap.lines_received,
            "channels": channels,
        }

    def _note_activity(self, source: _SourceState, current: float) -> None:
        previous = source.last_activity
        source.last_activity = current
        if previous is None:
            return
        duration = current - previous
        if duration > source.longest_gap_s:
            source.longest_gap_s = duration
        threshold = self._source_gap_threshold(source)
        if threshold is not None and duration >= threshold:
            source.gaps.append(
                GapEventSnapshot(previous, current, duration, None)
            )

    def _source_gap_threshold(self, source: _SourceState) -> float | None:
        if self.settings.expected_interval_s:
            return self.settings.expected_interval_s * self.settings.gap_multiplier
        intervals = [
            interval
            for channel in source.channels.values()
            for interval in channel.intervals
        ]
        if len(intervals) < self.settings.min_samples:
            return None
        baseline = _median(deque(intervals))
        if baseline is None:
            return None
        return baseline * self.settings.gap_multiplier

    def _note_channel(self, source: _SourceState, name: str, current: float) -> None:
        channel = source.channels.get(name)
        if channel is None:
            channel = _ChannelState(
                name, intervals=deque(maxlen=self.settings.interval_window)
            )
            source.channels[name] = channel
        if channel.first_time is None:
            channel.first_time = current
        if channel.last_time is not None:
            interval = current - channel.last_time
            if interval >= 0:
                channel.intervals.append(interval)
                channel.max_interval = max(channel.max_interval, interval)
                threshold = self._channel_gap_threshold(channel)
                if threshold is not None and interval >= threshold:
                    source.gaps.append(
                        GapEventSnapshot(channel.last_time, current, interval, name)
                    )
        channel.updates += 1
        channel.last_time = current

    def _channel_gap_threshold(self, channel: _ChannelState) -> float | None:
        baseline = self._baseline_interval(channel)
        if baseline is None or len(channel.intervals) < self.settings.min_samples:
            if self.settings.expected_interval_s and channel.updates >= 1:
                return self.settings.expected_interval_s * self.settings.gap_multiplier
            return None
        return baseline * self.settings.gap_multiplier

    def _channel_snapshot(
        self, channel: _ChannelState, current: float
    ) -> ChannelDiagnosticsSnapshot:
        mean, stdev = _mean_stdev(channel.intervals)
        rate = None if not mean else 1.0 / mean
        age = _age(channel.last_time, current)
        stale = self._is_stale(channel, age)
        state = "—" if channel.updates == 0 else ("STALE" if stale else "OK")
        return ChannelDiagnosticsSnapshot(
            name=channel.name,
            updates=channel.updates,
            last_update_age_s=age,
            measured_rate_hz=_finite(rate),
            average_interval_s=_finite(mean),
            max_interval_s=channel.max_interval or None,
            jitter_s=_finite(stdev),
            state=state,
            stale=stale,
        )

    def _is_stale(self, channel: _ChannelState, age: float | None) -> bool:
        if age is None or channel.updates < 1:
            return False
        baseline = self._baseline_interval(channel)
        if self.settings.expected_interval_s:
            return age >= self.settings.expected_interval_s * self.settings.stale_multiplier
        if baseline is None or len(channel.intervals) < self.settings.min_samples:
            return False
        return age >= baseline * self.settings.stale_multiplier

    def _window_rate(self, source: _SourceState, current: float, field: str) -> float | None:
        window = self.settings.rate_window_s
        total = 0
        oldest = None
        for sample in source.rx_samples:
            if current - sample.time > window:
                continue
            oldest = sample.time if oldest is None else oldest
            total += sample.bytes if field == "bytes" else sample.lines
        if total <= 0 or oldest is None:
            return None
        span = max(current - oldest, 1e-6)
        return total / span


def observation_rate(structured: int, errors: int) -> float | None:
    total = structured + errors
    if total <= 0:
        return None
    return structured / total


def _age(moment: float | None, now: float) -> float | None:
    if moment is None:
        return None
    return max(0.0, now - moment)


class DiagnosticsHub:
    """Fan out live events to live and optional recording collectors."""

    def __init__(
        self,
        settings: DiagnosticsSettings | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clock = clock
        self.live = DiagnosticsCollector(settings, clock)
        self.session: DiagnosticsCollector | None = None

    @property
    def settings(self) -> DiagnosticsSettings:
        return self.live.settings

    def apply_settings(self, settings: DiagnosticsSettings) -> None:
        self.live.apply_settings(settings)
        if self.session is not None:
            self.session.apply_settings(settings)

    def begin_recording(self) -> None:
        self.session = DiagnosticsCollector(self.live.settings, self._clock)

    def end_recording(self) -> dict[str, object] | None:
        collector = self.session
        self.session = None
        if collector is None:
            return None
        return {
            "sources": [
                collector.session_summary(source_id)
                for source_id in collector.source_ids()
            ]
        }

    def _each(self) -> tuple[DiagnosticsCollector, ...]:
        if self.session is None:
            return (self.live,)
        return (self.live, self.session)

    def note_connected(self, source_id: str, now: float | None = None) -> None:
        for collector in self._each():
            collector.note_connected(source_id, now)

    def note_disconnected(self, source_id: str, now: float | None = None) -> None:
        for collector in self._each():
            collector.note_disconnected(source_id, now)

    def note_removed(self, source_id: str) -> None:
        for collector in self._each():
            collector.note_removed(source_id)

    def note_bytes(self, source_id: str, byte_count: int, now: float | None = None) -> None:
        for collector in self._each():
            collector.note_bytes(source_id, byte_count, now)

    def note_parser_observation(
        self, source_id: str, observation: ParserObservation, now: float | None = None
    ) -> None:
        for collector in self._each():
            collector.note_parser_observation(source_id, observation, now)

    def note_structured_update(
        self, source_id: str, names: tuple[str, ...], now: float | None = None
    ) -> None:
        for collector in self._each():
            collector.note_structured_update(source_id, names, now)
