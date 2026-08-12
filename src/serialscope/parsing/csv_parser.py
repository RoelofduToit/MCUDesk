"""Incremental parser for simple header-based CSV byte streams."""

import csv
from dataclasses import dataclass
import io
import math
import re


NumericValue = int | float
_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")


@dataclass(frozen=True, slots=True)
class ChannelUpdate:
    """The latest numeric values associated with a detected CSV header."""

    names: tuple[str, ...]
    values: tuple[NumericValue, ...]

    @property
    def channels(self) -> dict[str, NumericValue]:
        return dict(zip(self.names, self.values, strict=True))


class CsvChannelParser:
    """Parse complete CSV lines from arbitrarily chunked raw bytes."""

    def __init__(self, headerless_confirmation_rows: int = 3) -> None:
        if headerless_confirmation_rows < 1:
            raise ValueError("headerless confirmation rows must be positive")
        self._buffer = bytearray()
        self._header: tuple[str, ...] | None = None
        self._header_is_generic = False
        self._headerless_confirmation_rows = headerless_confirmation_rows
        self._candidate_width: int | None = None
        self._candidate_count = 0
        self._latest_values: tuple[NumericValue, ...] | None = None

    @property
    def header(self) -> tuple[str, ...] | None:
        return self._header

    def reset(self) -> None:
        """Discard buffered bytes and detected channel names."""
        self._buffer.clear()
        self._header = None
        self._header_is_generic = False
        self._reset_candidate()
        self._latest_values = None

    def feed(self, data: bytes) -> list[ChannelUpdate]:
        """Consume new bytes and return updates from complete valid rows."""
        self._buffer.extend(data)
        updates: list[ChannelUpdate] = []

        while True:
            newline_index = self._buffer.find(b"\n")
            if newline_index < 0:
                break
            raw_line = bytes(self._buffer[:newline_index])
            del self._buffer[: newline_index + 1]
            if raw_line.endswith(b"\r"):
                raw_line = raw_line[:-1]
            update = self._parse_line(raw_line)
            if update is not None:
                updates.append(update)

        return updates

    def _parse_line(self, raw_line: bytes) -> ChannelUpdate | None:
        try:
            line = raw_line.decode("utf-8")
            rows = list(csv.reader(io.StringIO(line), strict=True))
        except (UnicodeDecodeError, csv.Error):
            if self._header is None:
                self._reset_candidate()
            return None
        if len(rows) != 1:
            if self._header is None:
                self._reset_candidate()
            return None

        fields = tuple(field.strip() for field in rows[0])
        values = self._parse_values(fields)

        if self._header is not None:
            if (
                self._header_is_generic
                and len(fields) == len(self._header)
                and self._is_valid_header(fields)
            ):
                self._header = fields
                self._header_is_generic = False
                if self._latest_values is not None:
                    return ChannelUpdate(self._header, self._latest_values)
                return None

            if len(fields) != len(self._header) or values is None:
                return None
            self._latest_values = values
            return ChannelUpdate(self._header, values)

        if self._is_valid_header(fields):
            self._header = fields
            self._reset_candidate()
            return None

        if values is None or len(values) < 2:
            self._reset_candidate()
            return None

        width = len(values)
        if self._candidate_width == width:
            self._candidate_count += 1
        else:
            self._candidate_width = width
            self._candidate_count = 1

        self._latest_values = values
        if self._candidate_count < self._headerless_confirmation_rows:
            return None

        self._header = tuple(f"Channel {index}" for index in range(1, width + 1))
        self._header_is_generic = True
        self._reset_candidate()
        return ChannelUpdate(self._header, values)

    def _reset_candidate(self) -> None:
        self._candidate_width = None
        self._candidate_count = 0

    @classmethod
    def _is_valid_header(cls, fields: tuple[str, ...]) -> bool:
        return (
            len(fields) >= 2
            and all(fields)
            and len(set(fields)) == len(fields)
            and cls._parse_values(fields) is None
            and all(cls._parse_number(field) is None for field in fields)
        )

    @classmethod
    def _parse_values(
        cls,
        fields: tuple[str, ...],
    ) -> tuple[NumericValue, ...] | None:
        values: list[NumericValue] = []
        for field in fields:
            value = cls._parse_number(field)
            if value is None:
                return None
            values.append(value)
        return tuple(values)

    @staticmethod
    def _parse_number(field: str) -> NumericValue | None:
        if not field:
            return None
        if _INTEGER_PATTERN.fullmatch(field):
            return int(field)
        try:
            value = float(field)
        except ValueError:
            return None
        return value if math.isfinite(value) else None
