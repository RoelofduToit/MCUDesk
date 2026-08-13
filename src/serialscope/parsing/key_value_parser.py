"""Incremental parser for comma-separated numeric key/value streams."""

import math
import re

from serialscope.parsing.csv_parser import ChannelUpdate, NumericValue
from serialscope.parsing.line_buffer import DEFAULT_MAX_LINE_BYTES, BoundedLineBuffer


_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")


class KeyValueChannelParser:
    """Parse complete key/value lines from arbitrarily chunked bytes."""

    def __init__(self, max_line_bytes: int = DEFAULT_MAX_LINE_BYTES) -> None:
        self._lines = BoundedLineBuffer(max_line_bytes)

    def reset(self) -> None:
        self._lines.reset()

    def feed(self, data: bytes) -> list[ChannelUpdate]:
        updates: list[ChannelUpdate] = []
        for raw_line in self._lines.feed(data):
            update = self._parse_line(raw_line)
            if update is not None:
                updates.append(update)

        return updates

    def _parse_line(self, raw_line: bytes) -> ChannelUpdate | None:
        try:
            line = raw_line.decode("utf-8")
        except UnicodeDecodeError:
            return None

        names: list[str] = []
        values: list[NumericValue] = []
        seen: set[str] = set()
        for item in line.split(","):
            if item.count("=") != 1:
                continue
            key, raw_value = (part.strip() for part in item.split("=", 1))
            value = self._parse_number(raw_value)
            if not key or key in seen or value is None:
                continue
            seen.add(key)
            names.append(key)
            values.append(value)

        if len(names) < 2:
            return None
        return ChannelUpdate(tuple(names), tuple(values), replace_channels=False)

    @staticmethod
    def _parse_number(value: str) -> NumericValue | None:
        if not value:
            return None
        if _INTEGER_PATTERN.fullmatch(value):
            return int(value)
        try:
            parsed = float(value)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
