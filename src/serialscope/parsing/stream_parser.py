"""Deterministic selection between supported serial line formats."""

from typing import Literal

from serialscope.parsing.csv_parser import ChannelUpdate, CsvChannelParser
from serialscope.parsing.json_parser import JsonChannelParser
from serialscope.parsing.key_value_parser import KeyValueChannelParser
from serialscope.parsing.observation import ParserObservation
from serialscope.parsing.parser_config import ParserConfiguration


ParserFormat = Literal["csv", "json", "key_value"]


class SerialStreamParser:
    """Lock onto the first parser that produces a structured update."""

    def __init__(self, configuration: ParserConfiguration | None = None) -> None:
        self._configuration = configuration or ParserConfiguration()
        self._csv = CsvChannelParser()
        self._json = JsonChannelParser()
        self._key_value = KeyValueChannelParser()
        self._active_format: ParserFormat | None = None
        self._forced_format: ParserFormat | None = None
        self._rebuild_parsers()

    @property
    def configuration(self) -> ParserConfiguration:
        return self._configuration

    @property
    def active_format(self) -> ParserFormat | None:
        return self._active_format

    def apply_configuration(self, configuration: ParserConfiguration) -> None:
        """Replace parser settings and discard buffered detection state."""
        self._configuration = configuration
        self._rebuild_parsers()
        self.reset()

    def reset(self) -> None:
        self._csv.reset()
        self._json.reset()
        self._key_value.reset()
        self._active_format = self._forced_format

    def feed(self, data: bytes) -> list[ChannelUpdate]:
        updates, _observation = self.observe(data)
        return updates

    def observe(self, data: bytes) -> tuple[list[ChannelUpdate], ParserObservation]:
        if self._active_format == "csv":
            return self._csv.observe(data)
        if self._active_format == "json":
            return self._json.observe(data)
        if self._active_format == "key_value":
            return self._key_value.observe(data)

        json_updates = self._json.feed(data)
        key_value_updates = self._key_value.feed(data)
        csv_updates = self._csv.feed(data)
        lines = data.count(b"\n")
        if json_updates:
            self._active_format = "json"
            return json_updates, ParserObservation(lines, len(json_updates), max(0, lines - len(json_updates)), 0)
        if key_value_updates:
            self._active_format = "key_value"
            return key_value_updates, ParserObservation(
                lines, len(key_value_updates), max(0, lines - len(key_value_updates)), 0
            )
        if csv_updates:
            self._active_format = "csv"
            return csv_updates, ParserObservation(lines, len(csv_updates), max(0, lines - len(csv_updates)), 0)
        return [], ParserObservation(lines, 0, lines, 0)

    def _rebuild_parsers(self) -> None:
        configuration = self._configuration
        mode = configuration.mode
        if mode == "delimited":
            self._csv = CsvChannelParser(
                delimiter=configuration.delimiter,
                header_mode=configuration.header_mode,
                columns=configuration.columns,
            )
            self._json = JsonChannelParser()
            self._key_value = KeyValueChannelParser()
            self._forced_format = "csv"
        elif mode == "key_value":
            self._csv = CsvChannelParser()
            self._json = JsonChannelParser()
            self._key_value = KeyValueChannelParser(
                pair_separator=configuration.pair_separator,
                name_value_separator=configuration.name_value_separator,
                min_pairs=1,
            )
            self._forced_format = "key_value"
        elif mode == "json":
            self._csv = CsvChannelParser()
            self._json = JsonChannelParser()
            self._key_value = KeyValueChannelParser()
            self._forced_format = "json"
        else:
            self._csv = CsvChannelParser()
            self._json = JsonChannelParser()
            self._key_value = KeyValueChannelParser()
            self._forced_format = None
        self._active_format = self._forced_format
