"""Experiment-level recording with independent files for every source."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import time
from collections.abc import Callable, Mapping

from serialscope import __version__
from serialscope.logging.raw_logger import RawLogger, RawLoggerError
from serialscope.logging.session import RecordingSessionError, sanitize_session_name
from serialscope.logging.structured_csv_logger import (
    StructuredCsvLogger,
    StructuredCsvLoggerError,
)
from serialscope.parsing import ChannelUpdate


@dataclass(frozen=True, slots=True)
class RecordingSourceConfig:
    source_id: str
    display_name: str
    device: str
    baud_rate: int
    channels: Mapping[str, Mapping[str, object]] | None = None


@dataclass(slots=True)
class _SourceLoggers:
    config: RecordingSourceConfig
    directory_name: str
    raw: RawLogger
    structured: StructuredCsvLogger
    active: bool = True
    end_reason: str | None = None


class MultiSourceRecordingSession:
    """Own one parent session and isolated per-source raw/structured loggers."""

    def __init__(
        self,
        *,
        datetime_clock: Callable[[], datetime] | None = None,
        monotonic_clock: Callable[[], float] = time.monotonic,
        raw_logger_factory: Callable[[], RawLogger] = RawLogger,
        structured_logger_factory: Callable[[], StructuredCsvLogger] | None = None,
    ) -> None:
        self._datetime_clock = datetime_clock or (lambda: datetime.now().astimezone())
        self._monotonic_clock = monotonic_clock
        self._raw_factory = raw_logger_factory
        self._structured_factory = structured_logger_factory or (
            lambda: StructuredCsvLogger(monotonic_clock)
        )
        self._directory: Path | None = None
        self._session_name = ""
        self._started_local: datetime | None = None
        self._started_at: datetime | None = None
        self._started_monotonic: float | None = None
        self._delimiter = ","
        self._sources: dict[str, _SourceLoggers] = {}
        self._metadata: dict[str, object] = {}

    @property
    def is_recording(self) -> bool:
        return self._started_monotonic is not None or self._started_at is not None

    @property
    def directory(self) -> Path | None:
        return self._directory

    @property
    def display_name(self) -> str:
        return self._session_name

    @property
    def elapsed_seconds(self) -> int:
        if self._started_monotonic is None:
            return 0
        return max(0, int(self._monotonic_clock() - self._started_monotonic))

    @property
    def bytes_written(self) -> int:
        return sum(item.raw.bytes_written for item in self._sources.values())

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(self._sources)

    @property
    def active_source_ids(self) -> tuple[str, ...]:
        return tuple(key for key, item in self._sources.items() if item.active)

    def start(
        self,
        parent_directory: Path,
        session_name: str,
        sources: tuple[RecordingSourceConfig, ...],
        *,
        delimiter: str = ",",
        line_ending: str = "LF",
    ) -> Path:
        if self.is_recording:
            raise RecordingSessionError("A recording session is already active.")
        if not session_name.strip():
            raise RecordingSessionError("Enter a session name before starting a recording.")
        if not sources:
            raise RecordingSessionError("Connect at least one device before recording.")
        if len({item.source_id for item in sources}) != len(sources):
            raise RecordingSessionError("Recording source IDs must be unique.")

        started_local = self._now()
        started_monotonic = self._monotonic_clock()
        base = f"{sanitize_session_name(session_name)}_{started_local:%Y-%m-%d_%H%M}"
        directory = self._create_unique_directory(Path(parent_directory), base)
        used_names: set[str] = set()
        loggers: dict[str, _SourceLoggers] = {}
        try:
            for config in sources:
                folder = sanitize_session_name(config.display_name) or config.source_id
                candidate = folder
                suffix = 2
                while candidate.casefold() in used_names:
                    candidate = f"{folder}_{suffix}"
                    suffix += 1
                used_names.add(candidate.casefold())
                source_directory = directory / candidate
                source_directory.mkdir()
                raw = self._raw_factory()
                structured = self._structured_factory()
                raw.start(source_directory / "raw.log")
                structured.start(
                    source_directory / "data.csv",
                    delimiter=delimiter,
                    started_at=started_monotonic,
                )
                loggers[config.source_id] = _SourceLoggers(
                    config, candidate, raw, structured
                )
        except (OSError, RawLoggerError, StructuredCsvLoggerError) as error:
            for item in loggers.values():
                try:
                    item.raw.stop()
                    item.structured.stop()
                except (RawLoggerError, StructuredCsvLoggerError):
                    pass
            raise RecordingSessionError(f"Could not start recording session: {error}") from error

        self._directory = directory
        self._session_name = session_name
        self._started_local = started_local
        self._started_at = started_local
        self._started_monotonic = started_monotonic
        self._delimiter = delimiter
        self._sources = loggers
        self._metadata = {
            "serialscope_version": __version__,
            "session_name": session_name,
            "recording_start_local": started_local.isoformat(),
            "recording_start_utc": started_local.astimezone(timezone.utc).isoformat(),
            "platform": platform.system(),
            "structured_data_delimiter": delimiter,
            "common_time_origin": "host_monotonic_at_recording_start",
            "line_ending": line_ending,
            "status": "recording",
            "devices": [self._device_metadata(item) for item in loggers.values()],
            "recording_end_local": None,
            "recording_end_utc": None,
            "elapsed_seconds": None,
            "end_reason": None,
        }
        self._write_metadata()
        return directory

    def write(self, source_id: str, data: bytes) -> int:
        try:
            item = self._sources[source_id]
            if not item.active:
                return 0
            return item.raw.write(data)
        except KeyError as error:
            raise RecordingSessionError(
                f"Source {source_id} is not part of this recording."
            ) from error
        except RawLoggerError as error:
            raise RecordingSessionError(str(error)) from error

    def write_structured(self, source_id: str, update: ChannelUpdate) -> None:
        try:
            item = self._sources[source_id]
            if not item.active:
                return
            item.structured.write(update)
        except KeyError as error:
            raise RecordingSessionError(
                f"Source {source_id} is not part of this recording."
            ) from error
        except StructuredCsvLoggerError as error:
            raise RecordingSessionError(str(error)) from error

    def stop(
        self,
        end_reason: str,
        total_rx_bytes: Mapping[str, int] | None = None,
    ) -> None:
        if not self.is_recording:
            return
        ended = self._now()
        errors: list[Exception] = []
        for item in self._sources.values():
            if not item.active:
                continue
            try:
                item.raw.stop()
            except RawLoggerError as error:
                errors.append(error)
            try:
                item.structured.stop()
            except StructuredCsvLoggerError as error:
                errors.append(error)
            item.active = False
            item.end_reason = end_reason
        devices = [
            self._device_metadata(item, (total_rx_bytes or {}).get(item.config.source_id))
            for item in self._sources.values()
        ]
        self._metadata.update(
            {
                "status": "completed",
                "recording_end_local": ended.isoformat(),
                "recording_end_utc": ended.astimezone(timezone.utc).isoformat(),
                "elapsed_seconds": max(
                    0.0, self._monotonic_clock() - (self._started_monotonic or 0.0)
                ),
                "end_reason": end_reason,
                "devices": devices,
            }
        )
        # Transitional single-source mirrors keep pre-0.8 tooling usable. They
        # are never created for multi-device sessions and are not combined data.
        if len(self._sources) == 1 and self._directory is not None:
            item = next(iter(self._sources.values()))
            try:
                shutil.copyfile(
                    self._directory / item.directory_name / "raw.log",
                    self._directory / "raw.log",
                )
                shutil.copyfile(
                    self._directory / item.directory_name / "data.csv",
                    self._directory / "data.csv",
                )
                self._metadata["legacy_single_source_files"] = True
            except OSError as error:
                errors.append(error)
        self._write_metadata()
        self._started_monotonic = None
        self._started_local = None
        self._started_at = None
        if errors:
            raise RecordingSessionError(str(errors[0])) from errors[0]

    def stop_source(self, source_id: str, end_reason: str) -> None:
        """Finalize one failed/disconnected participant without stopping peers."""
        item = self._sources.get(source_id)
        if item is None or not item.active:
            return
        errors: list[Exception] = []
        try:
            item.raw.stop()
        except RawLoggerError as error:
            errors.append(error)
        try:
            item.structured.stop()
        except StructuredCsvLoggerError as error:
            errors.append(error)
        item.active = False
        item.end_reason = end_reason
        self._metadata["devices"] = [
            self._device_metadata(source) for source in self._sources.values()
        ]
        self._write_metadata()
        if errors:
            raise RecordingSessionError(str(errors[0])) from errors[0]

    def _device_metadata(
        self, item: _SourceLoggers, total_rx_bytes: int | None = None
    ) -> dict[str, object]:
        config = item.config
        result: dict[str, object] = {
            "source_id": config.source_id,
            "name": config.display_name,
            "port": config.device,
            "baudrate": config.baud_rate,
            "raw_file": f"{item.directory_name}/raw.log",
            "data_file": f"{item.directory_name}/data.csv",
            "structured_data_delimiter": self._delimiter,
            "logged_byte_count": item.raw.bytes_written,
            "structured_row_count": item.structured.row_count,
            "structured_columns": list(item.structured.columns),
            "channels": dict(config.channels or {}),
            "recording_state": "recording" if item.active else "completed",
            "end_reason": item.end_reason,
        }
        if total_rx_bytes is not None:
            result["total_rx_byte_count"] = total_rx_bytes
        return result

    def _now(self) -> datetime:
        value = self._datetime_clock()
        return value.astimezone() if value.tzinfo is None else value

    def _clear_active_state(self) -> None:
        """Clear lifecycle state after finalization (and for legacy test setup)."""
        self._started_monotonic = None
        self._started_local = None
        self._started_at = None

    @staticmethod
    def _create_unique_directory(parent: Path, base: str) -> Path:
        parent.mkdir(parents=True, exist_ok=True)
        candidate = parent / base
        suffix = 2
        while True:
            try:
                candidate.mkdir()
                return candidate
            except FileExistsError:
                candidate = parent / f"{base}_{suffix}"
                suffix += 1

    def _write_metadata(self) -> None:
        if self._directory is None:
            raise RecordingSessionError("The session directory is unavailable.")
        temporary = self._directory / ".session.json.tmp"
        try:
            temporary.write_text(
                json.dumps(self._metadata, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self._directory / "session.json")
        except (OSError, TypeError, ValueError) as error:
            raise RecordingSessionError(f"Could not write session metadata: {error}") from error
