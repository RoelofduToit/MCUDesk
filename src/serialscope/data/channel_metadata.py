"""Presentation-only metadata keyed by authoritative source channel names."""

from dataclasses import dataclass
from typing import Mapping

from serialscope.data.alarm import AlarmLimits
from serialscope.data.channel_key import ChannelKey


@dataclass(frozen=True, slots=True)
class ChannelPresentation:
    source_name: str
    alias: str = ""
    unit: str = ""
    alarms: AlarmLimits = AlarmLimits()

    @property
    def display_name(self) -> str:
        return self.alias or self.source_name


class ChannelMetadataRegistry:
    """Retain aliases and units without changing source channel identity."""

    def __init__(self) -> None:
        self._channels: dict[str, ChannelPresentation] = {}

    @property
    def source_names(self) -> tuple[str, ...]:
        return tuple(self._channels)

    def ensure(self, source_names: tuple[str, ...]) -> None:
        for source_name in source_names:
            self._channels.setdefault(source_name, ChannelPresentation(source_name))

    def get(self, source_name: str) -> ChannelPresentation:
        return self._channels.get(source_name, ChannelPresentation(source_name))

    def set(
        self,
        source_name: str,
        alias: str = "",
        unit: str = "",
        alarms: AlarmLimits | None = None,
    ) -> None:
        self._channels[source_name] = ChannelPresentation(
            source_name, alias.strip(), unit.strip(), alarms or AlarmLimits()
        )

    def discard(self, source_name: str) -> None:
        self._channels.pop(source_name, None)

    def discard_composite_identities(self) -> None:
        """Drop leaked source-aware storage keys from a per-source registry."""
        leaked: list[tuple[str, str]] = []
        for name in self._channels:
            parser_name = self._parser_name(name)
            if parser_name != name:
                leaked.append((name, parser_name))
        for storage_name, parser_name in leaked:
            item = self._channels.pop(storage_name)
            existing = self._channels.get(parser_name)
            if existing is None:
                self._channels[parser_name] = ChannelPresentation(
                    parser_name, item.alias, item.unit, item.alarms
                )
            elif not (
                existing.alias or existing.unit or existing.alarms.is_configured
            ) and (item.alias or item.unit or item.alarms.is_configured):
                self._channels[parser_name] = ChannelPresentation(
                    parser_name, item.alias, item.unit, item.alarms
                )

    def replace(
        self,
        metadata: Mapping[str, object],
        source_names: tuple[str, ...],
        *,
        retain_missing: bool = False,
    ) -> None:
        normalized_metadata = self._normalize_metadata_keys(metadata)
        parser_names = tuple(
            dict.fromkeys(self._parser_name(name) for name in source_names)
        )
        retained = tuple(normalized_metadata) if retain_missing else ()
        self._channels.clear()
        self.ensure(tuple(dict.fromkeys((*parser_names, *retained))))
        for source_name, value in normalized_metadata.items():
            if source_name not in self._channels or not isinstance(value, Mapping):
                continue
            try:
                alarms = AlarmLimits.from_mapping(value.get("alarms"))
            except (TypeError, ValueError):
                alarms = AlarmLimits()
            self.set(
                source_name,
                str(value.get("alias", "")),
                str(value.get("unit", "")),
                alarms,
            )

    @staticmethod
    def _parser_name(source_name: str) -> str:
        if "\x1f" not in source_name:
            return source_name
        try:
            return ChannelKey.from_storage_key(source_name).channel_name
        except ValueError:
            return source_name

    @classmethod
    def _normalize_metadata_keys(
        cls, metadata: Mapping[str, object]
    ) -> dict[str, object]:
        """Prefer parser names; ignore composite keys when the real name exists."""
        normalized: dict[str, object] = {}
        for key, value in metadata.items():
            parser_name = cls._parser_name(key)
            if parser_name == key or parser_name not in normalized:
                normalized[parser_name] = value
        for key, value in metadata.items():
            if "\x1f" in key:
                continue
            normalized[key] = value
        return normalized

    def snapshot(self) -> dict[str, dict[str, str]]:
        return {
            name: {
                "alias": item.alias,
                "unit": item.unit,
                **({"alarms": item.alarms.to_dict()} if item.alarms.is_configured else {}),
            }
            for name, item in self._channels.items()
            if item.alias or item.unit or item.alarms.is_configured
        }
