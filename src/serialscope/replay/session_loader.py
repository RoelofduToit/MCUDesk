"""Qt-independent loading and validation of recorded SerialScope sessions."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping

from serialscope.data import EventMarker


class ReplaySessionError(RuntimeError):
    """Raised when a selected directory is not a usable recorded session."""


@dataclass(frozen=True)
class ReplaySample:
    """One structured sample at its original elapsed timestamp."""

    elapsed_s: float
    values: Mapping[str, int | float | None]


@dataclass(frozen=True)
class ReplaySession:
    """A fully loaded session, independent of serial transport and Qt."""

    directory: Path
    metadata: Mapping[str, object]
    channel_names: tuple[str, ...]
    samples: tuple[ReplaySample, ...]
    sources: tuple["ReplaySource", ...] = ()
    events: tuple[EventMarker, ...] = ()

    @property
    def name(self) -> str:
        value = self.metadata.get("session_name")
        return (
            str(value).strip()
            if value and str(value).strip()
            else self.directory.name
        )

    @property
    def latest_values(self) -> Mapping[str, int | float]:
        latest: dict[str, int | float] = {}
        for sample in self.samples:
            for name, value in sample.values.items():
                if value is not None:
                    latest[name] = value
        return MappingProxyType(latest)

    def points(self, name: str) -> tuple[tuple[float, ...], tuple[float, ...]]:
        points = [
            (sample.elapsed_s, float(sample.values[name]))
            for sample in self.samples
            if sample.values.get(name) is not None
        ]
        return tuple(point[0] for point in points), tuple(point[1] for point in points)

    def source(self, source_id: str) -> "ReplaySource":
        return next(source for source in self.sources if source.source_id == source_id)


@dataclass(frozen=True)
class ReplaySource:
    source_id: str
    display_name: str
    port: str | None
    baud_rate: int | None
    metadata: Mapping[str, object]
    channel_names: tuple[str, ...]
    samples: tuple[ReplaySample, ...]

    @property
    def latest_values(self) -> Mapping[str, int | float]:
        latest: dict[str, int | float] = {}
        for sample in self.samples:
            for name, value in sample.values.items():
                if value is not None:
                    latest[name] = value
        return MappingProxyType(latest)

    def points(self, name: str) -> tuple[tuple[float, ...], tuple[float, ...]]:
        points = [
            (sample.elapsed_s, float(sample.values[name]))
            for sample in self.samples
            if sample.values.get(name) is not None
        ]
        return tuple(item[0] for item in points), tuple(item[1] for item in points)


_INTEGER = re.compile(r"^[+-]?\d+$")
_DELIMITERS = {",", ";", "\t"}


def _session_file(directory: Path, relative_name: str) -> Path:
    """Resolve a metadata file reference without allowing session escape."""
    relative = Path(relative_name)
    if relative.is_absolute():
        raise ReplaySessionError("A recorded data file path is outside the session.")
    base = directory.resolve()
    candidate = (base / relative).resolve()
    if not candidate.is_relative_to(base):
        raise ReplaySessionError("A recorded data file path is outside the session.")
    return candidate


def _number(text: str, row_number: int, column: str) -> int | float | None:
    value = text.strip()
    if not value:
        return None
    try:
        parsed: int | float = int(value) if _INTEGER.fullmatch(value) else float(value)
    except ValueError as error:
        raise ReplaySessionError(
            f"Invalid numeric value in data.csv row {row_number}, column '{column}'."
        ) from error
    if isinstance(parsed, float) and not math.isfinite(parsed):
        raise ReplaySessionError(
            f"Invalid numeric value in data.csv row {row_number}, column '{column}'."
        )
    return parsed


def _load_data(data_path: Path, delimiter: str) -> tuple[tuple[str, ...], tuple[ReplaySample, ...]]:
    if not data_path.is_file():
        raise ReplaySessionError(f"The session does not contain {data_path.name}.")
    if delimiter not in _DELIMITERS:
        raise ReplaySessionError("session.json contains an unsupported data delimiter.")

    try:
        with data_path.open(encoding="utf-8-sig", newline="") as stream:
            rows = csv.reader(stream, delimiter=str(delimiter))
            header = next(rows, None)
            if not header:
                raise ReplaySessionError("data.csv is empty.")
            if header[0].strip() != "elapsed_s":
                raise ReplaySessionError("data.csv must begin with an elapsed_s column.")
            channels = tuple(value.strip() for value in header[1:])
            if (
                not channels
                or any(not name for name in channels)
                or len(set(channels)) != len(channels)
            ):
                raise ReplaySessionError("data.csv contains an invalid channel header.")

            samples: list[ReplaySample] = []
            previous_time = -1.0
            for row_number, row in enumerate(rows, start=2):
                if len(row) != len(header):
                    raise ReplaySessionError(
                        f"Malformed data.csv row {row_number}: expected {len(header)} columns."
                    )
                elapsed_value = _number(row[0], row_number, "elapsed_s")
                if elapsed_value is None:
                    raise ReplaySessionError(
                        f"Missing elapsed time in data.csv row {row_number}."
                    )
                elapsed = float(elapsed_value)
                if elapsed < 0 or elapsed < previous_time:
                    raise ReplaySessionError(
                        f"Invalid elapsed time in data.csv row {row_number}."
                    )
                previous_time = elapsed
                values = {
                    name: _number(text, row_number, name)
                    for name, text in zip(channels, row[1:], strict=True)
                }
                samples.append(ReplaySample(elapsed, MappingProxyType(values)))
    except ReplaySessionError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise ReplaySessionError("data.csv could not be read or is malformed.") from error

    if not samples:
        raise ReplaySessionError("data.csv contains no recorded samples.")
    return channels, tuple(samples)


def _load_events(directory: Path, metadata: Mapping[str, object]) -> tuple[EventMarker, ...]:
    path = _session_file(directory, str(metadata.get("events_file", "events.csv")))
    if not path.exists():
        return ()
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = csv.reader(stream)
            if next(rows, None) != ["elapsed_s", "event_id", "event"]:
                raise ReplaySessionError("events.csv contains an invalid header.")
            events: list[EventMarker] = []
            identifiers: set[str] = set()
            previous_time = -1.0
            for row in rows:
                if len(row) != 3:
                    raise ReplaySessionError("events.csv contains a malformed row.")
                marker = EventMarker(row[1], float(row[0]), row[2])
                if marker.elapsed_s < previous_time or marker.event_id in identifiers:
                    raise ReplaySessionError("events.csv contains invalid event data.")
                previous_time = marker.elapsed_s
                identifiers.add(marker.event_id)
                events.append(marker)
            return tuple(events)
    except ReplaySessionError:
        raise
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        raise ReplaySessionError("events.csv could not be read or is malformed.") from error


def load_replay_session(directory: Path) -> ReplaySession:
    """Load legacy or source-separated sessions into memory."""
    directory = Path(directory)
    metadata_path = directory / "session.json"
    if not metadata_path.is_file():
        raise ReplaySessionError("The selected folder does not contain session.json.")
    try:
        metadata_value = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReplaySessionError("session.json could not be read or is malformed.") from error
    if not isinstance(metadata_value, dict):
        raise ReplaySessionError("session.json must contain a JSON object.")
    metadata: dict[str, object] = metadata_value
    delimiter = metadata.get("structured_data_delimiter", ",")
    devices = metadata.get("devices")
    sources: list[ReplaySource] = []
    if isinstance(devices, list) and devices:
        source_ids: set[str] = set()
        for index, value in enumerate(devices, start=1):
            if not isinstance(value, dict):
                raise ReplaySessionError("session.json contains invalid device metadata.")
            source_id = str(value.get("source_id") or f"device_{index}")
            if source_id in source_ids:
                raise ReplaySessionError("session.json contains duplicate source IDs.")
            source_ids.add(source_id)
            data_file = str(value.get("data_file") or "")
            if not data_file:
                raise ReplaySessionError("A recorded device has no data_file.")
            source_delimiter = value.get("structured_data_delimiter", delimiter)
            channels, samples = _load_data(
                _session_file(directory, data_file), str(source_delimiter)
            )
            sources.append(
                ReplaySource(
                    source_id,
                    str(value.get("name") or source_id),
                    str(value["port"]) if value.get("port") is not None else None,
                    int(value["baudrate"]) if value.get("baudrate") is not None else None,
                    MappingProxyType(value),
                    channels,
                    samples,
                )
            )
    else:
        channels, samples = _load_data(directory / "data.csv", str(delimiter))
        serial_metadata = metadata.get("serial", {})
        if not isinstance(serial_metadata, dict):
            serial_metadata = {}
        sources.append(
            ReplaySource(
                "legacy_source",
                str(serial_metadata.get("device") or "Recorded Device"),
                str(serial_metadata["device"]) if serial_metadata.get("device") else None,
                int(serial_metadata["baud_rate"]) if serial_metadata.get("baud_rate") else None,
                MappingProxyType(metadata),
                channels,
                samples,
            )
        )
    primary = sources[0]
    events = _load_events(directory, metadata)
    return ReplaySession(
        directory=directory,
        metadata=MappingProxyType(metadata),
        channel_names=primary.channel_names,
        samples=primary.samples,
        sources=tuple(sources),
        events=events,
    )
