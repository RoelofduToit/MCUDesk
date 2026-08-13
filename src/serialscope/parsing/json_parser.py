"""Incremental parser for JSON objects sent one per serial line."""

import json
import math

from serialscope.parsing.csv_parser import ChannelUpdate, NumericValue
from serialscope.parsing.line_buffer import DEFAULT_MAX_LINE_BYTES, BoundedLineBuffer


def _reject_nonstandard_number(value: str) -> None:
    raise ValueError(f"invalid JSON number: {value}")


class JsonChannelParser:
    """Expose top-level numeric JSON object values as channel updates."""

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

    @staticmethod
    def _parse_line(raw_line: bytes) -> ChannelUpdate | None:
        try:
            document = json.loads(
                raw_line.decode("utf-8"),
                parse_constant=_reject_nonstandard_number,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return None

        if not isinstance(document, dict):
            return None

        names: list[str] = []
        values: list[NumericValue] = []
        for name, value in document.items():
            if not name or isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if isinstance(value, float) and not math.isfinite(value):
                continue
            names.append(name)
            values.append(value)

        if not names:
            return None
        return ChannelUpdate(tuple(names), tuple(values), replace_channels=False)
