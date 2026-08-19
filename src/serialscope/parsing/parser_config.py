"""User-defined parser configuration, validation, and sample preview."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


PARSER_MODES = ("auto", "delimited", "key_value", "json")
HEADER_MODES = ("auto", "present", "none")

DELIMITER_PRESETS: tuple[tuple[str, str, str], ...] = (
    ("comma", ",", "Comma"),
    ("semicolon", ";", "Semicolon"),
    ("tab", "\t", "Tab"),
    ("pipe", "|", "Pipe"),
    ("space", " ", "Space"),
)
PAIR_SEPARATOR_PRESETS: tuple[tuple[str, str, str], ...] = (
    ("comma", ",", "Comma"),
    ("semicolon", ";", "Semicolon"),
    ("space", " ", "Space"),
)
NAME_VALUE_SEPARATOR_PRESETS: tuple[tuple[str, str, str], ...] = (
    ("equals", "=", "="),
    ("colon", ":", ":"),
)

_MAX_SEPARATOR_LENGTH = 8


class ParserConfigurationError(ValueError):
    """A deterministic, user-presentable parser configuration error."""


def generic_channel_name(index: int) -> str:
    """Return the existing headerless name for a zero-based column index."""
    return f"Channel {index + 1}"


def _require_separator(value: object, label: str) -> str:
    text = str(value)
    if not text:
        raise ParserConfigurationError(f"{label} must not be empty.")
    if "\n" in text or "\r" in text:
        raise ParserConfigurationError(f"{label} must not contain a newline.")
    if len(text) > _MAX_SEPARATOR_LENGTH:
        raise ParserConfigurationError(
            f"{label} must be at most {_MAX_SEPARATOR_LENGTH} characters."
        )
    return text


@dataclass(frozen=True, slots=True)
class ColumnMapping:
    """One explicitly named delimited-input column."""

    index: int
    name: str = ""
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.index, int) or isinstance(self.index, bool):
            raise ParserConfigurationError("Column index must be an integer.")
        if self.index < 0:
            raise ParserConfigurationError("Column index must not be negative.")
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "enabled", bool(self.enabled))

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "name": self.name,
            "enabled": self.enabled,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ColumnMapping":
        return cls(
            index=int(value.get("index", 0)),
            name=str(value.get("name", "")),
            enabled=bool(value.get("enabled", True)),
        )


def _normalize_columns(
    columns: tuple[ColumnMapping, ...] | list[ColumnMapping] | tuple[object, ...] | list[object],
) -> tuple[ColumnMapping, ...]:
    normalized: list[ColumnMapping] = []
    seen_indices: set[int] = set()
    enabled_names: list[str] = []
    for item in columns:
        if isinstance(item, ColumnMapping):
            column = item
        elif isinstance(item, Mapping):
            column = ColumnMapping.from_mapping(item)
        else:
            raise ParserConfigurationError("Column mappings must be objects.")
        if column.index in seen_indices:
            raise ParserConfigurationError("Column indices must be unique.")
        seen_indices.add(column.index)
        if column.enabled:
            if not column.name:
                raise ParserConfigurationError(
                    "Enabled columns must have a channel name."
                )
            if column.name in enabled_names:
                raise ParserConfigurationError(
                    "Enabled channel names must be unique."
                )
            enabled_names.append(column.name)
        normalized.append(column)
    return tuple(sorted(normalized, key=lambda item: item.index))


@dataclass(frozen=True, slots=True)
class ParserConfiguration:
    """Describe how one serial source should interpret incoming lines."""

    mode: str = "auto"
    delimiter: str = ","
    header_mode: str = "auto"
    columns: tuple[ColumnMapping, ...] = ()
    pair_separator: str = ","
    name_value_separator: str = "="

    def __post_init__(self) -> None:
        mode = str(self.mode).strip()
        if mode not in PARSER_MODES:
            raise ParserConfigurationError("Unsupported parser mode.")
        header_mode = str(self.header_mode).strip()
        if header_mode not in HEADER_MODES:
            raise ParserConfigurationError("Unsupported header setting.")
        delimiter = _require_separator(self.delimiter, "Delimiter")
        pair_separator = _require_separator(self.pair_separator, "Pair separator")
        name_value_separator = _require_separator(
            self.name_value_separator, "Name/value separator"
        )
        if pair_separator == name_value_separator:
            raise ParserConfigurationError(
                "Pair separator and name/value separator must be different."
            )
        columns = _normalize_columns(self.columns)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "header_mode", header_mode)
        object.__setattr__(self, "delimiter", delimiter)
        object.__setattr__(self, "pair_separator", pair_separator)
        object.__setattr__(self, "name_value_separator", name_value_separator)
        object.__setattr__(self, "columns", columns)

    @property
    def is_default(self) -> bool:
        return self == ParserConfiguration()

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "delimiter": self.delimiter,
            "header_mode": self.header_mode,
            "columns": [column.to_dict() for column in self.columns],
            "pair_separator": self.pair_separator,
            "name_value_separator": self.name_value_separator,
        }

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, object] | None,
        *,
        default_mode: str = "auto",
    ) -> "ParserConfiguration":
        if value is None:
            return cls(mode=default_mode)
        if not isinstance(value, Mapping):
            raise ParserConfigurationError("Parser configuration must be an object.")
        raw_columns = value.get("columns", ())
        if raw_columns in (None, ""):
            raw_columns = ()
        if not isinstance(raw_columns, (list, tuple)):
            raise ParserConfigurationError("Column mappings must be a list.")
        mode = str(value.get("mode", default_mode) or default_mode)
        return cls(
            mode=mode,
            delimiter=str(value.get("delimiter", ",")),
            header_mode=str(value.get("header_mode", "auto")),
            columns=tuple(
                ColumnMapping.from_mapping(item)
                if isinstance(item, Mapping)
                else item
                for item in raw_columns
            ),
            pair_separator=str(value.get("pair_separator", ",")),
            name_value_separator=str(value.get("name_value_separator", "=")),
        )


@dataclass(frozen=True, slots=True)
class PreviewEntry:
    """One preview row for a parsed sample field."""

    channel: str
    value: str
    state: str


@dataclass(frozen=True, slots=True)
class ParserPreview:
    """Deterministic preview of a configuration against sample text."""

    entries: tuple[PreviewEntry, ...]
    message: str
    configuration_error: str | None = None


def split_delimited_fields(line: str, delimiter: str) -> tuple[str, ...]:
    """Split one visual sample line without requiring numeric values."""
    import csv
    import io

    if not delimiter:
        return (line.strip(),) if line.strip() else ()
    if len(delimiter) == 1:
        try:
            rows = list(csv.reader(io.StringIO(line), delimiter=delimiter, strict=True))
        except csv.Error:
            return ()
        if len(rows) != 1:
            return ()
        return tuple(field.strip() for field in rows[0])
    return tuple(part.strip() for part in line.split(delimiter))


def last_sample_line(sample: str) -> str:
    lines = [line.strip() for line in sample.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    for line in reversed(lines):
        if line:
            return line
    return ""


def preview_sample(configuration: ParserConfiguration, sample: str) -> ParserPreview:
    """Parse sample text with a throwaway parser instance."""
    from serialscope.parsing.stream_parser import SerialStreamParser

    try:
        ParserConfiguration(
            mode=configuration.mode,
            delimiter=configuration.delimiter,
            header_mode=configuration.header_mode,
            columns=configuration.columns,
            pair_separator=configuration.pair_separator,
            name_value_separator=configuration.name_value_separator,
        )
    except ParserConfigurationError as error:
        return ParserPreview((), str(error), str(error))

    text = sample.replace("\r\n", "\n").replace("\r", "\n")
    if text and not text.endswith("\n"):
        text += "\n"
    parser = SerialStreamParser(configuration)
    try:
        updates = parser.feed(text.encode("utf-8"))
    except Exception:
        return ParserPreview((), "Invalid row")

    if updates:
        update = updates[-1]
        entries = tuple(
            PreviewEntry(name, _format_preview_value(value), "OK")
            for name, value in zip(update.names, update.values, strict=True)
        )
        return ParserPreview(entries, "OK")

    line = last_sample_line(sample)
    if not line:
        return ParserPreview((), "No matching fields")
    if configuration.mode == "delimited":
        return _preview_delimited_failure(configuration, line)
    if configuration.mode == "json":
        return ParserPreview((), "Invalid row")
    if configuration.mode == "key_value":
        return _preview_key_value_failure(configuration, line)
    return ParserPreview((), "No matching fields")


def _format_preview_value(value: int | float) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    text = f"{value:.12g}"
    return text


def _preview_delimited_failure(
    configuration: ParserConfiguration, line: str
) -> ParserPreview:
    from serialscope.parsing.csv_parser import CsvChannelParser

    fields = split_delimited_fields(line, configuration.delimiter)
    if not fields:
        return ParserPreview((), "Invalid row")
    if configuration.header_mode == "none" and configuration.columns:
        entries: list[PreviewEntry] = []
        for column in configuration.columns:
            if not column.enabled:
                continue
            if column.index >= len(fields):
                entries.append(PreviewEntry(column.name, "", "Missing"))
                continue
            raw = fields[column.index]
            if CsvChannelParser._parse_number(raw) is None:
                entries.append(
                    PreviewEntry(
                        column.name,
                        raw,
                        "Invalid number" if raw else "Missing",
                    )
                )
                continue
            entries.append(
                PreviewEntry(
                    column.name,
                    raw,
                    "OK",
                )
            )
        if not entries:
            return ParserPreview((), "No matching fields")
        if all(entry.state != "OK" for entry in entries):
            message = entries[0].state if len(entries) == 1 else "Invalid row"
            return ParserPreview(tuple(entries), message)
        return ParserPreview(tuple(entries), "OK")
    return ParserPreview((), "Invalid row")


def _preview_key_value_failure(
    configuration: ParserConfiguration, line: str
) -> ParserPreview:
    if configuration.name_value_separator not in line:
        return ParserPreview((), "No matching fields")
    return ParserPreview((), "No matching fields")
