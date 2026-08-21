"""Incremental parser for JSON objects sent one per serial line."""

import json
import math

from serialscope.parsing.csv_parser import ChannelUpdate, NumericValue
from serialscope.parsing.line_buffer import DEFAULT_MAX_LINE_BYTES, BoundedLineBuffer
from serialscope.parsing.observation import (
    PARSER_MALFORMED,
    PARSER_STRUCTURED,
    PARSER_UNRECOGNIZED,
    ParserObservation,
)


def _reject_nonstandard_number(value: str) -> None:
    raise ValueError(f"invalid JSON number: {value}")


class JsonChannelParser:
    """Expose top-level numeric JSON object values as channel updates."""

    def __init__(self, max_line_bytes: int = DEFAULT_MAX_LINE_BYTES) -> None:
        self._lines = BoundedLineBuffer(max_line_bytes)

    def reset(self) -> None:
        self._lines.reset()

    def feed(self, data: bytes) -> list[ChannelUpdate]:
        updates, _observation = self.observe(data)
        return updates

    def observe(self, data: bytes) -> tuple[list[ChannelUpdate], ParserObservation]:
        discarded = self._lines.discarded_line_count
        updates: list[ChannelUpdate] = []
        structured = unrecognized = 0
        lines = self._lines.feed(data)
        malformed = self._lines.discarded_line_count - discarded
        for raw_line in lines:
            kind, update = self._classify_line(raw_line)
            if kind == PARSER_STRUCTURED and update is not None:
                updates.append(update)
                structured += 1
            elif kind == PARSER_MALFORMED:
                malformed += 1
            else:
                unrecognized += 1
        return updates, ParserObservation(
            len(lines) + (self._lines.discarded_line_count - discarded),
            structured,
            unrecognized,
            malformed,
        )

    @staticmethod
    def _parse_line(raw_line: bytes) -> ChannelUpdate | None:
        _kind, update = JsonChannelParser._classify_line(raw_line)
        return update

    @staticmethod
    def _classify_line(raw_line: bytes) -> tuple[str, ChannelUpdate | None]:
        try:
            document = json.loads(
                raw_line.decode("utf-8"),
                parse_constant=_reject_nonstandard_number,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            stripped = raw_line.lstrip()
            if stripped.startswith(b"{") or stripped.startswith(b"["):
                return PARSER_MALFORMED, None
            return PARSER_UNRECOGNIZED, None

        if not isinstance(document, dict):
            return PARSER_UNRECOGNIZED, None

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
            return PARSER_UNRECOGNIZED, None
        return PARSER_STRUCTURED, ChannelUpdate(
            tuple(names), tuple(values), replace_channels=False
        )
