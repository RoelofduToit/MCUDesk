"""Presentation-only metadata keyed by authoritative source channel names."""

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ChannelPresentation:
    source_name: str
    alias: str = ""
    unit: str = ""

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

    def set(self, source_name: str, alias: str = "", unit: str = "") -> None:
        self._channels[source_name] = ChannelPresentation(
            source_name, alias.strip(), unit.strip()
        )

    def replace(self, metadata: Mapping[str, object], source_names: tuple[str, ...]) -> None:
        self._channels.clear()
        self.ensure(source_names)
        for source_name, value in metadata.items():
            if source_name not in self._channels or not isinstance(value, Mapping):
                continue
            self.set(
                source_name,
                str(value.get("alias", "")),
                str(value.get("unit", "")),
            )

    def snapshot(self) -> dict[str, dict[str, str]]:
        return {
            name: {"alias": item.alias, "unit": item.unit}
            for name, item in self._channels.items()
            if item.alias or item.unit
        }
