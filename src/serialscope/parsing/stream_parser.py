"""Deterministic selection between supported serial line formats."""

from typing import Literal

from serialscope.parsing.csv_parser import ChannelUpdate, CsvChannelParser
from serialscope.parsing.json_parser import JsonChannelParser
from serialscope.parsing.key_value_parser import KeyValueChannelParser


ParserFormat = Literal["csv", "json", "key_value"]


class SerialStreamParser:
    """Lock onto the first parser that produces a structured update."""

    def __init__(self) -> None:
        self._csv = CsvChannelParser()
        self._json = JsonChannelParser()
        self._key_value = KeyValueChannelParser()
        self._active_format: ParserFormat | None = None

    @property
    def active_format(self) -> ParserFormat | None:
        return self._active_format

    def reset(self) -> None:
        self._csv.reset()
        self._json.reset()
        self._key_value.reset()
        self._active_format = None

    def feed(self, data: bytes) -> list[ChannelUpdate]:
        if self._active_format == "csv":
            return self._csv.feed(data)
        if self._active_format == "json":
            return self._json.feed(data)
        if self._active_format == "key_value":
            return self._key_value.feed(data)

        json_updates = self._json.feed(data)
        key_value_updates = self._key_value.feed(data)
        csv_updates = self._csv.feed(data)
        if json_updates:
            self._active_format = "json"
            return json_updates
        if key_value_updates:
            self._active_format = "key_value"
            return key_value_updates
        if csv_updates:
            self._active_format = "csv"
            return csv_updates
        return []
