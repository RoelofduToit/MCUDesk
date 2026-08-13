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


_INTEGER = re.compile(r"^[+-]?\d+$")
_DELIMITERS = {",", ";", "\t"}


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


def load_replay_session(directory: Path) -> ReplaySession:
    """Load one complete session directory into memory."""
    directory = Path(directory)
    metadata_path = directory / "session.json"
    data_path = directory / "data.csv"
    if not metadata_path.is_file():
        raise ReplaySessionError("The selected folder does not contain session.json.")
    if not data_path.is_file():
        raise ReplaySessionError("The selected folder does not contain data.csv.")

    try:
        metadata_value = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReplaySessionError(
            "session.json could not be read or is malformed."
        ) from error
    if not isinstance(metadata_value, dict):
        raise ReplaySessionError("session.json must contain a JSON object.")
    metadata: dict[str, object] = metadata_value
    delimiter = metadata.get("structured_data_delimiter", ",")
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
    return ReplaySession(
        directory=directory,
        metadata=MappingProxyType(metadata),
        channel_names=channels,
        samples=tuple(samples),
    )
