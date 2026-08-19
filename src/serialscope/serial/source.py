"""Independent serial acquisition sources and their manager."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from serialscope.parsing import ChannelUpdate, ParserConfiguration, SerialStreamParser
from serialscope.serial.connection import SerialConnection, SerialConnectionError
from serialscope.serial.reader import SerialReader


def _source_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    return slug or "device"


@dataclass(slots=True)
class SerialSource:
    """Own all mutable acquisition state for one physical serial device."""

    source_id: str
    display_name: str
    port: str | None = None
    baud_rate: int = 115200
    line_ending: str = "LF"
    connection: SerialConnection = field(default_factory=SerialConnection)
    parser: SerialStreamParser = field(default_factory=SerialStreamParser)
    reader: SerialReader | None = None
    rx_bytes: int = 0
    tx_bytes: int = 0
    latest_values: dict[str, int | float] = field(default_factory=dict)

    @property
    def is_connected(self) -> bool:
        return self.connection.is_connected


class SerialSourceManager(QObject):
    """Coordinate independent sources and enforce exclusive port ownership."""

    source_added = Signal(str)
    source_removed = Signal(str)
    source_state_changed = Signal(str, str)
    bytes_received = Signal(str, bytes)
    structured_update = Signal(str, object)
    source_failed = Signal(str, str)

    def __init__(
        self,
        *,
        connection_factory: Callable[[], SerialConnection] = SerialConnection,
        reader_factory: Callable[[SerialConnection], SerialReader] = SerialReader,
        parser_factory: Callable[[], SerialStreamParser] = SerialStreamParser,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._connection_factory = connection_factory
        self._reader_factory = reader_factory
        self._parser_factory = parser_factory
        self._sources: dict[str, SerialSource] = {}

    @property
    def sources(self) -> tuple[SerialSource, ...]:
        return tuple(self._sources.values())

    @property
    def connected_sources(self) -> tuple[SerialSource, ...]:
        return tuple(source for source in self.sources if source.is_connected)

    def get(self, source_id: str) -> SerialSource:
        try:
            return self._sources[source_id]
        except KeyError as error:
            raise KeyError(f"Unknown serial source: {source_id}") from error

    def add_source(
        self,
        display_name: str | None = None,
        *,
        port: str | None = None,
        baud_rate: int = 115200,
        source_id: str | None = None,
        connection: SerialConnection | None = None,
    ) -> SerialSource:
        requested_name = (display_name or "").strip()
        if not requested_name:
            number = 1
            existing_names = {source.display_name.casefold() for source in self.sources}
            while f"device {number}" in existing_names:
                number += 1
            requested_name = f"Device {number}"
        existing_names = {source.display_name.casefold() for source in self.sources}
        resolved_name = requested_name
        suffix = 2
        while resolved_name.casefold() in existing_names:
            resolved_name = f"{requested_name} {suffix}"
            suffix += 1
        base = source_id or _source_slug(resolved_name)
        candidate = base
        suffix = 2
        while candidate in self._sources:
            candidate = f"{base}_{suffix}"
            suffix += 1
        source = SerialSource(
            source_id=candidate,
            display_name=resolved_name,
            port=port,
            baud_rate=baud_rate,
            connection=connection or self._connection_factory(),
            parser=self._parser_factory(),
        )
        self._sources[candidate] = source
        self.source_added.emit(candidate)
        return source

    def remove_source(self, source_id: str) -> None:
        source = self.get(source_id)
        self.disconnect(source_id)
        del self._sources[source_id]
        self.source_removed.emit(source_id)

    def rename_source(self, source_id: str, display_name: str) -> None:
        name = display_name.strip()
        if not name:
            raise ValueError("Device name must not be empty.")
        existing = {
            source.display_name.casefold()
            for source in self.sources
            if source.source_id != source_id
        }
        resolved = name
        suffix = 2
        while resolved.casefold() in existing:
            resolved = f"{name} {suffix}"
            suffix += 1
        self.get(source_id).display_name = resolved
        self.source_state_changed.emit(source_id, "connected" if self.get(source_id).is_connected else "disconnected")

    def connect(self, source_id: str, port: str, baud_rate: int) -> None:
        source = self.get(source_id)
        if source.is_connected or source.reader is not None:
            raise SerialConnectionError(
                f"{source.display_name} is already connected."
            )
        owner = next(
            (
                item
                for item in self.connected_sources
                if item.source_id != source_id and item.port == port
            ),
            None,
        )
        if owner is not None:
            raise SerialConnectionError(
                f"{port} is already connected as {owner.display_name}."
            )
        source.connection.connect(port, baud_rate)
        try:
            reader = self._reader_factory(source.connection)
            source.reader = reader
            reader.bytes_received.connect(
                lambda data, identity=source_id, owner=reader: self._receive(
                    identity, owner, data
                )
            )
            reader.failed.connect(
                lambda message, identity=source_id, owner=reader: self._reader_failed(
                    identity, owner, message
                )
            )
            reader.start()
        except Exception as error:
            source.reader = None
            try:
                source.connection.disconnect()
            except SerialConnectionError:
                pass
            if isinstance(error, SerialConnectionError):
                raise
            raise SerialConnectionError(
                f"Could not start the reader for {source.display_name}: {error}"
            ) from error

        source.port = port
        source.baud_rate = baud_rate
        source.rx_bytes = 0
        source.tx_bytes = 0
        source.latest_values.clear()
        source.parser.reset()
        self.source_state_changed.emit(source_id, "connected")

    def disconnect(self, source_id: str) -> None:
        source = self.get(source_id)
        reader, source.reader = source.reader, None
        if reader is not None:
            reader.stop()
        source.connection.disconnect()
        source.parser.reset()
        self.source_state_changed.emit(source_id, "disconnected")

    def disconnect_all(self) -> None:
        for source in tuple(self.sources):
            try:
                self.disconnect(source.source_id)
            except SerialConnectionError:
                self.source_state_changed.emit(source.source_id, "error")

    def apply_parser_configuration(
        self, source_id: str, configuration: ParserConfiguration
    ) -> None:
        source = self.get(source_id)
        source.parser.apply_configuration(configuration)
        self.source_state_changed.emit(
            source_id, "connected" if source.is_connected else "disconnected"
        )

    def write(self, source_id: str, data: bytes) -> int:
        source = self.get(source_id)
        written = source.connection.write(data)
        source.tx_bytes += written
        return written

    def _receive(self, source_id: str, reader: SerialReader, data: bytes) -> None:
        source = self.get(source_id)
        if source.reader is not reader or not source.is_connected:
            return
        source.rx_bytes += len(data)
        self.bytes_received.emit(source_id, data)
        for update in source.parser.feed(data):
            source.latest_values.update(zip(update.names, update.values, strict=True))
            self.structured_update.emit(source_id, update)

    def _reader_failed(
        self, source_id: str, reader: SerialReader, message: str
    ) -> None:
        source = self.get(source_id)
        if source.reader is not reader:
            return
        source.reader = None
        reader.stop()
        try:
            source.connection.disconnect()
        except SerialConnectionError:
            pass
        source.parser.reset()
        self.source_state_changed.emit(source_id, "error")
        self.source_failed.emit(source_id, message)
