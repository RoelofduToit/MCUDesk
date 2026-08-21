"""Incremental parser for simple header-based CSV byte streams."""

import csv
from dataclasses import dataclass
import io
import math
import re

from serialscope.parsing.line_buffer import (
    DEFAULT_MAX_LINE_BYTES,
    BoundedLineBuffer,
)
from serialscope.parsing.observation import (
    PARSER_MALFORMED,
    PARSER_STRUCTURED,
    PARSER_UNRECOGNIZED,
    ParserObservation,
)
from serialscope.parsing.parser_config import (
    ColumnMapping,
    HEADER_MODES,
    generic_channel_name,
)


NumericValue = int | float
_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")


@dataclass(frozen=True, slots=True)
class ChannelUpdate:
    """The latest numeric values associated with a detected CSV header."""

    names: tuple[str, ...]
    values: tuple[NumericValue, ...]
    replace_channels: bool = True

    @property
    def channels(self) -> dict[str, NumericValue]:
        return dict(zip(self.names, self.values, strict=True))


class CsvChannelParser:
    """Parse complete CSV lines from arbitrarily chunked raw bytes."""

    def __init__(
        self,
        headerless_confirmation_rows: int = 3,
        max_line_bytes: int = DEFAULT_MAX_LINE_BYTES,
        delimiter: str = ",",
        header_mode: str = "auto",
        columns: tuple[ColumnMapping, ...] = (),
    ) -> None:
        if headerless_confirmation_rows < 1:
            raise ValueError("headerless confirmation rows must be positive")
        if not delimiter or "\n" in delimiter or "\r" in delimiter:
            raise ValueError("delimiter must be a non-empty single-line separator")
        if header_mode not in HEADER_MODES:
            raise ValueError("unsupported header mode")
        self._lines = BoundedLineBuffer(max_line_bytes)
        self._delimiter = delimiter
        self._header_mode = header_mode
        self._columns = tuple(sorted(columns, key=lambda item: item.index))
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
        self._lines.reset()
        self._header = None
        self._header_is_generic = False
        self._reset_candidate()
        self._latest_values = None

    def feed(self, data: bytes) -> list[ChannelUpdate]:
        """Consume new bytes and return updates from complete valid rows."""
        updates, _observation = self.observe(data)
        return updates

    def observe(self, data: bytes) -> tuple[list[ChannelUpdate], ParserObservation]:
        """Parse bytes and classify each complete line for diagnostics."""
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
        return updates, ParserObservation(len(lines) + malformed, structured, unrecognized, malformed)

    def _parse_line(self, raw_line: bytes) -> ChannelUpdate | None:
        _kind, update = self._classify_line(raw_line)
        return update

    def _classify_line(self, raw_line: bytes) -> tuple[str, ChannelUpdate | None]:
        try:
            line = raw_line.decode("utf-8")
            fields = self._read_fields(line)
        except (UnicodeDecodeError, csv.Error, ValueError):
            if self._header is None:
                self._reset_candidate()
            return PARSER_MALFORMED, None
        if fields is None:
            if self._header is None:
                self._reset_candidate()
            return PARSER_UNRECOGNIZED, None

        if self._header_mode == "none" and self._columns:
            update = self._parse_mapped_row(fields)
            return (PARSER_STRUCTURED, update) if update else (PARSER_UNRECOGNIZED, None)

        values = self._parse_values(fields)

        if self._header is not None:
            if (
                self._header_mode == "auto"
                and self._header_is_generic
                and len(fields) == len(self._header)
                and self._is_valid_header(fields)
            ):
                self._header = fields
                self._header_is_generic = False
                if self._latest_values is not None:
                    return PARSER_STRUCTURED, ChannelUpdate(self._header, self._latest_values)
                return PARSER_UNRECOGNIZED, None

            if len(fields) != len(self._header) or values is None:
                return PARSER_UNRECOGNIZED, None
            self._latest_values = values
            return PARSER_STRUCTURED, ChannelUpdate(self._header, values)

        if self._header_mode == "present":
            if self._is_explicit_header(fields):
                self._header = fields
                self._header_is_generic = False
                self._reset_candidate()
            return PARSER_UNRECOGNIZED, None

        if self._header_mode == "none":
            if values is None or not values:
                return PARSER_UNRECOGNIZED, None
            self._header = tuple(
                generic_channel_name(index) for index in range(len(values))
            )
            self._header_is_generic = True
            self._latest_values = values
            return PARSER_STRUCTURED, ChannelUpdate(self._header, values)

        if self._is_valid_header(fields):
            self._header = fields
            self._reset_candidate()
            return PARSER_UNRECOGNIZED, None

        if values is None or len(values) < 2:
            self._reset_candidate()
            return PARSER_UNRECOGNIZED, None

        width = len(values)
        if self._candidate_width == width:
            self._candidate_count += 1
        else:
            self._candidate_width = width
            self._candidate_count = 1

        self._latest_values = values
        if self._candidate_count < self._headerless_confirmation_rows:
            return PARSER_UNRECOGNIZED, None

        self._header = tuple(generic_channel_name(index) for index in range(width))
        self._header_is_generic = True
        self._reset_candidate()
        return PARSER_STRUCTURED, ChannelUpdate(self._header, values)

    def _parse_mapped_row(self, fields: tuple[str, ...]) -> ChannelUpdate | None:
        names: list[str] = []
        values: list[NumericValue] = []
        for column in self._columns:
            if not column.enabled:
                continue
            if column.index >= len(fields):
                continue
            value = self._parse_number(fields[column.index])
            if value is None:
                continue
            names.append(column.name)
            values.append(value)
        if not names:
            return None
        return ChannelUpdate(tuple(names), tuple(values), replace_channels=False)

    def _read_fields(self, line: str) -> tuple[str, ...] | None:
        delimiter = self._delimiter
        if len(delimiter) == 1:
            rows = list(
                csv.reader(io.StringIO(line), delimiter=delimiter, strict=True)
            )
            if len(rows) != 1:
                return None
            return tuple(field.strip() for field in rows[0])
        return tuple(part.strip() for part in line.split(delimiter))

    def _reset_candidate(self) -> None:
        self._candidate_width = None
        self._candidate_count = 0

    @classmethod
    def _is_valid_header(cls, fields: tuple[str, ...]) -> bool:
        return (
            len(fields) >= 2
            and all(fields)
            and len(set(fields)) == len(fields)
            and all("=" not in field for field in fields)
            and cls._parse_values(fields) is None
            and all(cls._parse_number(field) is None for field in fields)
        )

    @staticmethod
    def _is_explicit_header(fields: tuple[str, ...]) -> bool:
        return bool(fields) and all(fields) and len(set(fields)) == len(fields)

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
