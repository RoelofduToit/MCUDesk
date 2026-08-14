"""Presentation-only metadata keyed by authoritative source channel names."""

from dataclasses import dataclass
from typing import Mapping
from serialscope.data.alarm import AlarmLimits


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

    def replace(
        self,
        metadata: Mapping[str, object],
        source_names: tuple[str, ...],
        *,
        retain_missing: bool = False,
    ) -> None:
        self._channels.clear()
        self.ensure(
            tuple(dict.fromkeys((*source_names, *(metadata if retain_missing else ()))))
        )
        for source_name, value in metadata.items():
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
