"""Incremental parser for numeric key/value streams."""

import math
import re

from serialscope.parsing.csv_parser import ChannelUpdate, NumericValue
from serialscope.parsing.line_buffer import DEFAULT_MAX_LINE_BYTES, BoundedLineBuffer
from serialscope.parsing.observation import (
    PARSER_MALFORMED,
    PARSER_STRUCTURED,
    PARSER_UNRECOGNIZED,
    ParserObservation,
)


_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")


class KeyValueChannelParser:
    """Parse complete key/value lines from arbitrarily chunked bytes."""

    def __init__(
        self,
        max_line_bytes: int = DEFAULT_MAX_LINE_BYTES,
        pair_separator: str = ",",
        name_value_separator: str = "=",
        min_pairs: int = 2,
    ) -> None:
        if not pair_separator or not name_value_separator:
            raise ValueError("key/value separators must not be empty")
        if pair_separator == name_value_separator:
            raise ValueError("key/value separators must be different")
        if min_pairs < 1:
            raise ValueError("minimum pair count must be positive")
        self._lines = BoundedLineBuffer(max_line_bytes)
        self._pair_separator = pair_separator
        self._name_value_separator = name_value_separator
        self._min_pairs = min_pairs

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

    def _parse_line(self, raw_line: bytes) -> ChannelUpdate | None:
        _kind, update = self._classify_line(raw_line)
        return update

    def _classify_line(self, raw_line: bytes) -> tuple[str, ChannelUpdate | None]:
        try:
            line = raw_line.decode("utf-8")
        except UnicodeDecodeError:
            return PARSER_MALFORMED, None

        names: list[str] = []
        values: list[NumericValue] = []
        seen: set[str] = set()
        for item in self._split_pairs(line):
            separator = self._name_value_separator
            if separator not in item:
                continue
            key, raw_value = (part.strip() for part in item.split(separator, 1))
            value = self._parse_number(raw_value)
            if not key or key in seen or value is None:
                continue
            seen.add(key)
            names.append(key)
            values.append(value)

        if len(names) < self._min_pairs:
            return PARSER_UNRECOGNIZED, None
        return PARSER_STRUCTURED, ChannelUpdate(
            tuple(names), tuple(values), replace_channels=False
        )

    def _split_pairs(self, line: str) -> list[str]:
        return line.split(self._pair_separator)

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
