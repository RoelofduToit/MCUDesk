"""Detect and salvage recordings interrupted by a crash or power loss."""

from __future__ import annotations

import csv
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from serialscope.storage import atomic_write_json


IN_PROGRESS_NAME = "recording.inprogress"
_TERMINAL_STATUSES = {"completed", "discarded"}
_DELIMITERS = {",", ";", "\t"}
_INTEGER = re.compile(r"^[+-]?\d+$")


@dataclass(frozen=True, slots=True)
class InterruptedRecording:
    """Disk facts for one session that did not shut down cleanly."""

    directory: Path
    session_name: str
    started_local: str
    last_checkpoint: str
    duration_label: str
    logged_bytes: int
    sample_count: int
    session_id: str


class RecordingRecoveryError(Exception):
    """A recoverable session could not be finalized or inspected."""


def in_progress_path(directory: Path) -> Path:
    return Path(directory) / IN_PROGRESS_NAME


def write_in_progress_marker(directory: Path, payload: Mapping[str, object]) -> None:
    atomic_write_json(in_progress_path(directory), dict(payload))


def remove_in_progress_marker(directory: Path) -> None:
    in_progress_path(directory).unlink(missing_ok=True)


def is_interrupted_recording(directory: Path) -> bool:
    """Return True when the folder looks like a recording that never finalized."""
    directory = Path(directory)
    if not directory.is_dir():
        return False
    metadata = _read_json(directory / "session.json")
    status = str((metadata or {}).get("status") or "")
    if status in _TERMINAL_STATUSES:
        return False
    if metadata is not None and status == "recording":
        return True
    return in_progress_path(directory).is_file()


def inspect_interrupted_recording(directory: Path) -> InterruptedRecording | None:
    directory = Path(directory)
    if not is_interrupted_recording(directory):
        return None
    metadata = _read_json(directory / "session.json") or {}
    marker = _read_json(in_progress_path(directory)) or {}
    started = str(
        metadata.get("recording_start_local")
        or marker.get("started_local")
        or ""
    )
    checkpoint = str(
        metadata.get("last_checkpoint_utc")
        or marker.get("last_checkpoint_utc")
        or ""
    )
    name = str(metadata.get("session_name") or marker.get("session_name") or directory.name)
    session_id = str(metadata.get("session_id") or marker.get("session_id") or "")
    bytes_written, samples, last_elapsed = _summarize_payload(directory, metadata)
    return InterruptedRecording(
        directory=directory,
        session_name=name,
        started_local=started,
        last_checkpoint=checkpoint,
        duration_label=_duration_label(last_elapsed, metadata.get("elapsed_seconds")),
        logged_bytes=bytes_written,
        sample_count=samples,
        session_id=session_id,
    )


def find_interrupted_recordings(paths: tuple[Path, ...]) -> tuple[InterruptedRecording, ...]:
    """Inspect registered session folders; skip missing and already-finalized ones."""
    found: list[InterruptedRecording] = []
    seen: set[Path] = set()
    for raw in paths:
        directory = Path(raw)
        resolved = directory.resolve() if directory.exists() else directory
        if resolved in seen:
            continue
        seen.add(resolved)
        inspected = inspect_interrupted_recording(directory)
        if inspected is not None:
            found.append(inspected)
    return tuple(found)


def recover_interrupted_recording(directory: Path) -> InterruptedRecording:
    """Preserve valid on-disk samples and mark the session completed/recovered."""
    directory = Path(directory)
    if not directory.is_dir():
        raise RecordingRecoveryError("The interrupted recording folder is missing.")
    metadata = _read_json(directory / "session.json") or {}
    if str(metadata.get("status") or "") == "completed":
        raise RecordingRecoveryError("That recording is already complete.")
    delimiter = str(metadata.get("structured_data_delimiter") or ",")
    devices = metadata.get("devices")
    total_bytes = 0
    total_samples = 0
    last_elapsed = 0.0
    if isinstance(devices, list) and devices:
        repaired_devices: list[dict[str, object]] = []
        for device in devices:
            if not isinstance(device, dict):
                continue
            data_rel = str(device.get("data_file") or "")
            raw_rel = str(device.get("raw_file") or "")
            data_path = directory / data_rel if data_rel else None
            raw_path = directory / raw_rel if raw_rel else None
            columns, samples, elapsed = _salvage_csv(
                data_path, str(device.get("structured_data_delimiter") or delimiter)
            )
            size = raw_path.stat().st_size if raw_path is not None and raw_path.is_file() else 0
            total_bytes += size
            total_samples += samples
            last_elapsed = max(last_elapsed, elapsed)
            updated = dict(device)
            updated["structured_columns"] = list(columns)
            updated["structured_row_count"] = samples
            updated["logged_byte_count"] = size
            updated["recording_state"] = "completed"
            updated["end_reason"] = "recovered"
            repaired_devices.append(updated)
        metadata["devices"] = repaired_devices
    else:
        columns, samples, elapsed = _salvage_csv(directory / "data.csv", delimiter)
        raw = directory / "raw.log"
        total_bytes = raw.stat().st_size if raw.is_file() else 0
        total_samples = samples
        last_elapsed = elapsed
        metadata["structured_columns"] = list(columns)
        metadata["structured_row_count"] = samples
        metadata["logged_byte_count"] = total_bytes
    events_rel = str(metadata.get("events_file") or "events.csv")
    event_count = _salvage_events(directory / events_rel)
    ended = datetime.now().astimezone()
    metadata.update(
        {
            "status": "completed",
            "end_reason": "recovered",
            "recovered": True,
            "event_count": event_count,
            "elapsed_seconds": last_elapsed,
            "recording_end_local": ended.isoformat(),
            "recording_end_utc": ended.astimezone(timezone.utc).isoformat(),
            "logged_byte_count": metadata.get("logged_byte_count", total_bytes),
        }
    )
    atomic_write_json(directory / "session.json", metadata)
    remove_in_progress_marker(directory)
    inspected = inspect_interrupted_recording(directory)
    if inspected is not None:
        raise RecordingRecoveryError("The session is still marked interrupted after recovery.")
    return InterruptedRecording(
        directory=directory,
        session_name=str(metadata.get("session_name") or directory.name),
        started_local=str(metadata.get("recording_start_local") or ""),
        last_checkpoint=str(metadata.get("last_checkpoint_utc") or ""),
        duration_label=_duration_label(last_elapsed, last_elapsed),
        logged_bytes=int(metadata.get("logged_byte_count") or total_bytes or 0),
        sample_count=int(metadata.get("structured_row_count") or total_samples or 0),
        session_id=str(metadata.get("session_id") or ""),
    )


def discard_interrupted_recording(directory: Path) -> None:
    """Stop offering recovery without deleting preserved experiment files."""
    directory = Path(directory)
    if not directory.is_dir():
        remove_in_progress_marker(directory)
        return
    metadata = _read_json(directory / "session.json")
    if metadata is not None and str(metadata.get("status") or "") == "completed":
        remove_in_progress_marker(directory)
        return
    if metadata is None:
        metadata = {"session_name": directory.name}
    metadata["status"] = "discarded"
    metadata["end_reason"] = "discarded"
    atomic_write_json(directory / "session.json", metadata)
    remove_in_progress_marker(directory)


def _salvage_csv(path: Path | None, delimiter: str) -> tuple[tuple[str, ...], int, float]:
    if path is None or not path.is_file():
        return (), 0, 0.0
    if delimiter not in _DELIMITERS:
        delimiter = ","
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    rows = _read_csv_rows(text, delimiter)
    if not rows:
        return (), 0, 0.0
    header = [cell.strip() for cell in rows[0]]
    if not header or header[0] != "elapsed_s":
        return (), 0, 0.0
    kept = [header]
    last_elapsed = 0.0
    previous = -1.0
    for row in rows[1:]:
        if len(row) != len(header):
            continue
        elapsed = _parse_number(row[0])
        if elapsed is None or elapsed < 0 or elapsed < previous:
            continue
        if any(_parse_number(cell) is None and cell.strip() for cell in row[1:]):
            continue
        kept.append(row)
        previous = float(elapsed)
        last_elapsed = float(elapsed)
    rewritten = _join_csv(kept, delimiter)
    if rewritten != text.replace("\r\n", "\n").replace("\r", "\n"):
        atomic_replace_text(path, rewritten)
    return tuple(header[1:]), max(0, len(kept) - 1), last_elapsed


def _salvage_events(path: Path) -> int:
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        return 0
    header = rows[0]
    kept = [header]
    if header != ["elapsed_s", "event_id", "event"]:
        return 0
    previous = -1.0
    seen: set[str] = set()
    for row in rows[1:]:
        if len(row) != 3:
            continue
        try:
            elapsed = float(row[0])
        except ValueError:
            continue
        event_id = row[1]
        if elapsed < previous or event_id in seen:
            continue
        kept.append(row)
        previous = elapsed
        seen.add(event_id)
    rewritten = _join_csv(kept, ",")
    if rewritten != text.replace("\r\n", "\n").replace("\r", "\n"):
        if rewritten.strip() != text.replace("\r\n", "\n").replace("\r", "\n").strip():
            atomic_replace_text(path, rewritten)
    return max(0, len(kept) - 1)


def _join_csv(rows: list[list[str]], delimiter: str) -> str:
    from io import StringIO

    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n")
    writer.writerows(rows)
    return buffer.getvalue()


def atomic_replace_text(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _read_csv_rows(text: str, delimiter: str) -> list[list[str]]:
    """Parse as much CSV as possible; a corrupt tail must not discard earlier rows."""
    try:
        return list(csv.reader(text.splitlines(), delimiter=delimiter))
    except csv.Error:
        kept: list[list[str]] = []
        for line in text.splitlines():
            try:
                parsed = list(csv.reader([line], delimiter=delimiter))
            except csv.Error:
                continue
            if parsed:
                kept.append(parsed[0])
        return kept


def _parse_number(text: str) -> int | float | None:
    value = text.strip()
    if not value:
        return None
    try:
        parsed: int | float = int(value) if _INTEGER.fullmatch(value) else float(value)
    except ValueError:
        return None
    if isinstance(parsed, float) and not math.isfinite(parsed):
        return None
    return parsed


def _summarize_payload(
    directory: Path, metadata: Mapping[str, object]
) -> tuple[int, int, float]:
    devices = metadata.get("devices")
    if isinstance(devices, list) and devices:
        total_bytes = 0
        total_samples = 0
        last_elapsed = 0.0
        delimiter = str(metadata.get("structured_data_delimiter") or ",")
        for device in devices:
            if not isinstance(device, dict):
                continue
            raw_rel = str(device.get("raw_file") or "")
            data_rel = str(device.get("data_file") or "")
            raw = directory / raw_rel
            if raw.is_file():
                total_bytes += raw.stat().st_size
            _columns, samples, elapsed = _peek_csv(
                directory / data_rel if data_rel else None,
                str(device.get("structured_data_delimiter") or delimiter),
            )
            total_samples += samples
            last_elapsed = max(last_elapsed, elapsed)
        return total_bytes, total_samples, last_elapsed
    raw = directory / "raw.log"
    size = raw.stat().st_size if raw.is_file() else int(metadata.get("logged_byte_count") or 0)
    _columns, samples, elapsed = _peek_csv(
        directory / "data.csv", str(metadata.get("structured_data_delimiter") or ",")
    )
    return size, samples, elapsed


def _peek_csv(path: Path | None, delimiter: str) -> tuple[tuple[str, ...], int, float]:
    if path is None or not path.is_file():
        return (), 0, 0.0
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = csv.reader(stream, delimiter=delimiter)
            header = next(rows, None)
            if not header:
                return (), 0, 0.0
            count = 0
            last = 0.0
            for row in rows:
                if len(row) != len(header):
                    continue
                try:
                    last = float(row[0])
                except ValueError:
                    continue
                count += 1
            return tuple(header[1:]), count, last
    except (OSError, UnicodeError, csv.Error):
        return (), 0, 0.0


def _duration_label(last_elapsed: float, metadata_elapsed: object) -> str:
    seconds = last_elapsed
    if seconds <= 0 and metadata_elapsed is not None:
        try:
            seconds = float(metadata_elapsed)
        except (TypeError, ValueError):
            seconds = 0.0
    seconds = max(0.0, seconds)
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
