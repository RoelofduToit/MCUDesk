"""Versioned persistence for calculated channel definitions."""

from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from serialscope.data.calculated import (
    CalculatedChannel,
    CalculatedChannelError,
)
from serialscope.data.expression import ExpressionError
from serialscope.storage import atomic_write_json


CALCULATED_SCHEMA_VERSION = 1


class CalculatedChannelStoreError(RuntimeError):
    """A concise calculated-channel persistence failure."""


def default_calculated_path() -> Path:
    root = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    return Path(root) / "calculated_channels.json"


class CalculatedChannelStore:
    """Own per-source calculated channel lists in one atomic JSON document."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_calculated_path()
        self._sources: dict[str, tuple[CalculatedChannel, ...]] = {}
        self.load_error: str | None = None
        self._load()

    def for_source(self, source_id: str) -> tuple[CalculatedChannel, ...]:
        return self._sources.get(source_id, ())

    def all_names(self, source_id: str) -> tuple[str, ...]:
        return tuple(channel.name for channel in self.for_source(source_id))

    def replace_source(
        self, source_id: str, channels: Iterable[CalculatedChannel]
    ) -> tuple[CalculatedChannel, ...]:
        resolved = tuple(channels)
        names = [channel.name.casefold() for channel in resolved]
        if len(names) != len(set(names)):
            raise CalculatedChannelStoreError(
                "Calculated channel names must be unique."
            )
        ids = [channel.channel_id for channel in resolved]
        if len(ids) != len(set(ids)):
            raise CalculatedChannelStoreError(
                "Calculated channel IDs must be unique."
            )
        self._sources[source_id] = resolved
        self._save()
        return resolved

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            self.load_error = f"Could not read calculated channels: {error}"
            return
        if not isinstance(payload, dict):
            self.load_error = "Calculated channel file is malformed."
            return
        version = payload.get("schema_version")
        if version not in {None, CALCULATED_SCHEMA_VERSION, 1}:
            self.load_error = (
                f"Unsupported calculated channel schema version: {version}."
            )
            return
        sources = payload.get("sources", {})
        if not isinstance(sources, dict):
            self.load_error = "Calculated channel file is malformed."
            return
        loaded: dict[str, tuple[CalculatedChannel, ...]] = {}
        try:
            for source_id, items in sources.items():
                if not isinstance(items, list):
                    continue
                loaded[str(source_id)] = tuple(
                    CalculatedChannel.from_mapping(item)
                    for item in items
                    if isinstance(item, dict)
                )
        except (TypeError, ValueError, CalculatedChannelError, ExpressionError) as error:
            self.load_error = f"Calculated channel file is invalid: {error}"
            return
        self._sources = loaded

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            atomic_write_json(
                self.path,
                {
                    "schema_version": CALCULATED_SCHEMA_VERSION,
                    "sources": {
                        source_id: [channel.to_dict() for channel in channels]
                        for source_id, channels in self._sources.items()
                    },
                },
            )
        except (OSError, TypeError, ValueError) as error:
            raise CalculatedChannelStoreError(
                f"Could not save calculated channels: {error}"
            ) from error
