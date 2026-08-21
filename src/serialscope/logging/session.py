"""Recording-session directory and metadata lifecycle."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import platform
import re
import time
from typing import Mapping
import uuid

from serialscope import __version__
from serialscope.data import EventMarker
from serialscope.logging.event_logger import EventLogger, EventLoggerError
from serialscope.logging.raw_logger import RawLogger, RawLoggerError
from serialscope.logging.structured_csv_logger import (
    StructuredCsvLogger,
    StructuredCsvLoggerError,
)
from serialscope.parsing import ChannelUpdate
from serialscope.logging.recovery import (
    remove_in_progress_marker,
    write_in_progress_marker,
)
from serialscope.storage import atomic_write_json


class RecordingSessionError(Exception):
    """A user-presentable recording-session failure."""


@dataclass(frozen=True, slots=True)
class SessionConfig:
    """Connection metadata captured when a recording begins."""

    session_name: str
    device: str
    baud_rate: int
    line_ending: str
    data_bits: int = 8
    parity: str = "none"
    stop_bits: int = 1
    structured_data_delimiter: str = ","
    channels: Mapping[str, Mapping[str, object]] | None = None
    profile_id: str | None = None
    profile_name: str | None = None
    parser_config: Mapping[str, object] | None = None


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def sanitize_session_name(name: str) -> str:
    """Return a compact cross-platform-safe folder-name component."""
    sanitized = _INVALID_FILENAME_CHARS.sub("_", name.strip())
    sanitized = re.sub(r"\s+", "_", sanitized)
    sanitized = re.sub(r"_+", "_", sanitized).strip(" ._")
    sanitized = sanitized[:80].rstrip(" ._")
    if sanitized.upper() in _WINDOWS_RESERVED_NAMES:
        sanitized = f"Session_{sanitized}"
    return sanitized


class RecordingSession:
    """Coordinate a raw logger with a session directory and JSON metadata."""

    def __init__(
        self,
        raw_logger: RawLogger | None = None,
        structured_logger: StructuredCsvLogger | None = None,
        clock: Callable[[], datetime] | None = None,
        event_logger: EventLogger | None = None,
        monotonic_clock: Callable[[], float] = time.monotonic,
        event_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._monotonic_clock = monotonic_clock
        self._raw_logger = raw_logger or RawLogger()
        self._owns_structured_logger = structured_logger is None
        self._structured_logger = structured_logger or StructuredCsvLogger(
            monotonic_clock
        )
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._event_logger = event_logger or EventLogger()
        self._event_id_factory = event_id_factory or (lambda: uuid.uuid4().hex)
        self._directory: Path | None = None
        self._config: SessionConfig | None = None
        self._started_at: datetime | None = None
        self._started_monotonic: float | None = None
        self._events: list[EventMarker] = []
        self._metadata: dict[str, object] = {}

    @property
    def is_recording(self) -> bool:
        return self._started_at is not None

    @property
    def directory(self) -> Path | None:
        return self._directory

    @property
    def bytes_written(self) -> int:
        return self._raw_logger.bytes_written

    @property
    def display_name(self) -> str:
        if self._config is None:
            return ""
        return self._config.session_name or (
            self._directory.name if self._directory is not None else ""
        )

    @property
    def elapsed_seconds(self) -> int:
        if self._started_at is None:
            return 0
        return max(0, int((self._now() - self._started_at).total_seconds()))

    @property
    def events(self) -> tuple[EventMarker, ...]:
        return tuple(self._events)

    @property
    def event_logging_available(self) -> bool:
        return self.is_recording and self._event_logger.is_recording

    def elapsed_now(self) -> float:
        if self._started_monotonic is None:
            raise RecordingSessionError("No recording session is active.")
        return max(0.0, self._monotonic_clock() - self._started_monotonic)

    def add_event(self, elapsed_s: float, text: str) -> EventMarker:
        if not self.is_recording:
            raise RecordingSessionError("No recording session is active.")
        try:
            marker = EventMarker(self._event_id_factory(), elapsed_s, text)
            self._event_logger.write(marker)
        except (EventLoggerError, ValueError) as error:
            raise RecordingSessionError(f"Could not record event: {error}") from error
        self._events.append(marker)
        return marker

    def start(self, parent_directory: Path, config: SessionConfig) -> Path:
        """Create a collision-safe session directory and begin raw logging."""
        if self.is_recording:
            raise RecordingSessionError("A recording session is already active.")
        if not config.session_name.strip():
            raise RecordingSessionError(
                "Enter a session name before starting a recording."
            )

        started_at = self._now()
        started_monotonic = self._monotonic_clock()
        folder_base = sanitize_session_name(config.session_name)
        timestamp = started_at.strftime("%Y-%m-%d_%H%M")
        try:
            directory = self._create_unique_directory(
                parent_directory,
                f"{folder_base}_{timestamp}",
            )
            self._raw_logger.start(directory / "raw.log")
            structured_options = (
                {"started_at": started_monotonic}
                if self._owns_structured_logger
                else {}
            )
            self._structured_logger.start(
                directory / "data.csv",
                delimiter=config.structured_data_delimiter,
                **structured_options,
            )
            self._event_logger.start(directory / "events.csv")
        except (OSError, RawLoggerError, StructuredCsvLoggerError, EventLoggerError) as error:
            try:
                self._raw_logger.stop()
            except RawLoggerError:
                pass
            try:
                self._structured_logger.stop()
            except StructuredCsvLoggerError:
                pass
            try:
                self._event_logger.stop()
            except EventLoggerError:
                pass
            raise RecordingSessionError(f"Could not start recording session: {error}") from error

        self._directory = directory
        self._config = config
        self._started_at = started_at
        self._started_monotonic = started_monotonic
        self._events = []
        self._session_id = uuid.uuid4().hex
        self._metadata = {
            "serialscope_version": __version__,
            "session_id": self._session_id,
            "session_name": config.session_name,
            "recording_start_local": started_at.isoformat(),
            "recording_start_utc": started_at.astimezone(timezone.utc).isoformat(),
            "serial": {
                "device": config.device,
                "baud_rate": config.baud_rate,
                "data_bits": config.data_bits,
                "parity": config.parity,
                "stop_bits": config.stop_bits,
                "line_ending": config.line_ending,
            },
            "platform": platform.system(),
            "structured_data_file": "data.csv",
            "structured_data_delimiter": config.structured_data_delimiter,
            "structured_row_count": 0,
            "structured_columns": [],
            "structured_ignored_channels": [],
            "events_file": "events.csv",
            "event_count": 0,
            "channels": self._normalize_channel_metadata(config.channels or {}),
            "status": "recording",
            "recording_end_local": None,
            "recording_end_utc": None,
            "elapsed_seconds": None,
            "logged_byte_count": 0,
            "total_rx_byte_count": None,
            "end_reason": None,
        }
        if config.profile_id:
            self._metadata["device_profile"] = {
                "profile_id": config.profile_id,
                "profile_name": config.profile_name,
            }
        if config.parser_config:
            self._metadata["parser"] = dict(config.parser_config)
        try:
            self._write_metadata()
            self._write_in_progress_marker()
        except RecordingSessionError:
            try:
                self._raw_logger.stop()
            except RawLoggerError:
                pass
            try:
                self._structured_logger.stop()
            except StructuredCsvLoggerError:
                pass
            try:
                self._event_logger.stop()
            except EventLoggerError:
                pass
            self._clear_active_state()
            raise
        return directory

    def set_channel_metadata(
        self, channels: Mapping[str, Mapping[str, object]]
    ) -> None:
        """Update presentation metadata without touching structured source data."""
        if not self.is_recording:
            return
        self._metadata["channels"] = self._normalize_channel_metadata(channels)
        self._write_metadata()

    @staticmethod
    def _normalize_channel_metadata(
        channels: Mapping[str, Mapping[str, object]],
    ) -> dict[str, dict[str, object]]:
        normalized: dict[str, dict[str, object]] = {}
        for name, values in channels.items():
            channel: dict[str, object] = {
                "alias": str(values.get("alias", "")).strip(),
                "unit": str(values.get("unit", "")).strip(),
            }
            alarms = values.get("alarms")
            if isinstance(alarms, Mapping):
                channel["alarms"] = {
                    key: float(value)
                    for key, value in alarms.items()
                    if key in {"low_low", "low", "high", "high_high"}
                    and value is not None
                }
            normalized[name] = channel
        return normalized

    def write(self, data: bytes) -> int:
        """Forward an exact byte chunk to the raw-only logger."""
        if not self.is_recording:
            raise RecordingSessionError("No recording session is active.")
        try:
            return self._raw_logger.write(data)
        except RawLoggerError as error:
            raise RecordingSessionError(str(error)) from error

    def write_structured(self, update: ChannelUpdate) -> None:
        """Write one parser-produced structured sample to data.csv."""
        if not self.is_recording:
            raise RecordingSessionError("No recording session is active.")
        try:
            self._structured_logger.write(update)
        except StructuredCsvLoggerError as error:
            raise RecordingSessionError(str(error)) from error

    def flush(self) -> None:
        """Flush raw and structured logs so a crash loses at most one timer interval."""
        if not self.is_recording:
            return
        try:
            self._raw_logger.flush()
            self._structured_logger.flush()
            self._checkpoint_metadata()
        except (RawLoggerError, StructuredCsvLoggerError) as error:
            raise RecordingSessionError(str(error)) from error

    def stop(
        self,
        end_reason: str,
        total_rx_bytes: int,
        diagnostics: dict[str, object] | None = None,
    ) -> None:
        """Close raw data and finalize metadata for the active session."""
        if not self.is_recording:
            return

        ended_at = self._now()
        started_at = self._started_at
        raw_error: RawLoggerError | None = None
        structured_error: StructuredCsvLoggerError | None = None
        event_error: EventLoggerError | None = None
        try:
            self._raw_logger.stop()
        except RawLoggerError as error:
            raw_error = error
        try:
            self._structured_logger.stop()
        except StructuredCsvLoggerError as error:
            structured_error = error
        try:
            self._event_logger.stop()
        except EventLoggerError as error:
            event_error = error

        if diagnostics is not None:
            self._metadata["diagnostics"] = diagnostics
        self._metadata.update(
            {
                "status": "completed",
                "recording_end_local": ended_at.isoformat(),
                "recording_end_utc": ended_at.astimezone(timezone.utc).isoformat(),
                "elapsed_seconds": max(
                    0,
                    (ended_at - started_at).total_seconds(),
                ),
                "logged_byte_count": self.bytes_written,
                "structured_row_count": self._structured_logger.row_count,
                "structured_columns": list(self._structured_logger.columns),
                "structured_ignored_channels": list(
                    self._structured_logger.ignored_channels
                ),
                "event_count": len(self._events),
                "total_rx_byte_count": total_rx_bytes,
                "end_reason": end_reason,
            }
        )
        metadata_error: RecordingSessionError | None = None
        try:
            self._write_metadata()
        except RecordingSessionError as error:
            metadata_error = error
        finally:
            if self._directory is not None:
                remove_in_progress_marker(self._directory)
            self._clear_active_state()

        if metadata_error is not None:
            raise metadata_error
        if raw_error is not None:
            raise RecordingSessionError(str(raw_error)) from raw_error
        if structured_error is not None:
            raise RecordingSessionError(str(structured_error)) from structured_error
        if event_error is not None:
            raise RecordingSessionError(str(event_error)) from event_error

    def _now(self) -> datetime:
        value = self._clock()
        return value.astimezone() if value.tzinfo is None else value

    @staticmethod
    def _create_unique_directory(parent: Path, base_name: str) -> Path:
        parent.mkdir(parents=True, exist_ok=True)
        candidate = parent / base_name
        suffix = 2
        while True:
            try:
                candidate.mkdir()
                return candidate
            except FileExistsError:
                candidate = parent / f"{base_name}_{suffix}"
                suffix += 1

    def _checkpoint_metadata(self) -> None:
        if not self.is_recording:
            return
        self._metadata["logged_byte_count"] = self.bytes_written
        self._metadata["structured_row_count"] = self._structured_logger.row_count
        self._metadata["structured_columns"] = list(self._structured_logger.columns)
        self._metadata["last_checkpoint_utc"] = (
            self._now().astimezone(timezone.utc).isoformat()
        )
        self._write_metadata()
        self._write_in_progress_marker()

    def _write_in_progress_marker(self) -> None:
        if self._directory is None:
            return
        write_in_progress_marker(
            self._directory,
            {
                "schema": 1,
                "session_id": self._metadata.get("session_id", ""),
                "session_name": self._metadata.get("session_name", ""),
                "started_local": self._metadata.get("recording_start_local", ""),
                "last_checkpoint_utc": self._metadata.get("last_checkpoint_utc", ""),
            },
        )

    def _write_metadata(self) -> None:
        if self._directory is None:
            raise RecordingSessionError("The session directory is unavailable.")
        try:
            atomic_write_json(self._directory / "session.json", self._metadata)
        except (OSError, ValueError, TypeError) as error:
            raise RecordingSessionError(
                f"Could not write session metadata: {error}"
            ) from error

    def _clear_active_state(self) -> None:
        self._started_at = None
        self._started_monotonic = None
