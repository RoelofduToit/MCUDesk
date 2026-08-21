"""Independent serial acquisition sources and their manager."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from serialscope.modbus import (
    ModbusPoller,
    ModbusRtuConfiguration,
    PROTOCOL_MODBUS_RTU,
    PROTOCOL_SERIAL_STREAM,
    create_serial_transport,
)
from serialscope.diagnostics.collector import DiagnosticsHub
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
    protocol: str = PROTOCOL_SERIAL_STREAM
    modbus_config: ModbusRtuConfiguration | None = None
    poller: ModbusPoller | None = None
    rx_bytes: int = 0
    tx_bytes: int = 0
    latest_values: dict[str, int | float] = field(default_factory=dict)

    @property
    def is_modbus(self) -> bool:
        return self.protocol == PROTOCOL_MODBUS_RTU

    @property
    def is_connected(self) -> bool:
        if self.is_modbus:
            return self.poller is not None and self.poller.is_running
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
        poller_factory: Callable[..., ModbusPoller] | None = None,
        modbus_transport_factory: Callable[..., object] | None = None,
        diagnostics: DiagnosticsHub | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._connection_factory = connection_factory
        self._reader_factory = reader_factory
        self._parser_factory = parser_factory
        self._poller_factory = poller_factory or ModbusPoller
        self._modbus_transport_factory = modbus_transport_factory or (
            lambda port, settings: create_serial_transport(port, settings)
        )
        self._diagnostics = diagnostics
        self._sources: dict[str, SerialSource] = {}

    def set_diagnostics(self, diagnostics: DiagnosticsHub | None) -> None:
        self._diagnostics = diagnostics

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
        if self._diagnostics is not None:
            self._diagnostics.note_removed(source_id)
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

    def apply_modbus_configuration(
        self, source_id: str, configuration: ModbusRtuConfiguration
    ) -> None:
        source = self.get(source_id)
        if source.is_connected:
            raise SerialConnectionError(
                "Disconnect this device before changing Modbus configuration."
            )
        source.protocol = PROTOCOL_MODBUS_RTU
        source.modbus_config = configuration
        source.baud_rate = configuration.connection.baud_rate
        self.source_state_changed.emit(source_id, "disconnected")

    def apply_serial_stream_protocol(self, source_id: str) -> None:
        source = self.get(source_id)
        if source.is_connected:
            raise SerialConnectionError(
                "Disconnect this device before changing the data source type."
            )
        source.protocol = PROTOCOL_SERIAL_STREAM
        source.modbus_config = None
        self.source_state_changed.emit(source_id, "disconnected")

    def occupied_port_owner(self, port: str, *, excluding: str | None = None) -> SerialSource | None:
        return next(
            (
                item
                for item in self.connected_sources
                if item.port == port and item.source_id != excluding
            ),
            None,
        )

    def connect(self, source_id: str, port: str, baud_rate: int) -> None:
        source = self.get(source_id)
        if source.is_connected or source.reader is not None or source.poller is not None:
            raise SerialConnectionError(
                f"{source.display_name} is already connected."
            )
        owner = self.occupied_port_owner(port, excluding=source_id)
        if owner is not None:
            raise SerialConnectionError(
                f"{port} is already connected as {owner.display_name}."
            )
        if source.is_modbus:
            self._connect_modbus(source, port, baud_rate)
            return
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
        if self._diagnostics is not None:
            self._diagnostics.note_connected(source_id)
        self.source_state_changed.emit(source_id, "connected")

    def _connect_modbus(self, source: SerialSource, port: str, baud_rate: int) -> None:
        configuration = source.modbus_config
        if configuration is None or not configuration.enabled_registers:
            raise SerialConnectionError(
                "Configure at least one enabled Modbus register before connecting."
            )
        if baud_rate != configuration.connection.baud_rate:
            configuration = replace(
                configuration,
                connection=replace(configuration.connection, baud_rate=baud_rate),
            )
            source.modbus_config = configuration
        try:
            poller = self._poller_factory(
                configuration,
                lambda: self._modbus_transport_factory(port, configuration.connection),
            )
            source.poller = poller
            poller.values_ready.connect(
                lambda update, identity=source.source_id, owner=poller: self._modbus_update(
                    identity, owner, update
                )
            )
            poller.failed.connect(
                lambda message, identity=source.source_id, owner=poller: self._poller_failed(
                    identity, owner, message
                )
            )
            poller.start()
        except Exception as error:
            source.poller = None
            raise SerialConnectionError(
                f"Could not start Modbus polling for {source.display_name}: {error}"
            ) from error
        source.port = port
        source.baud_rate = baud_rate
        source.rx_bytes = 0
        source.tx_bytes = 0
        source.latest_values.clear()
        if self._diagnostics is not None:
            self._diagnostics.note_connected(source.source_id)
        self.source_state_changed.emit(source.source_id, "connected")

    def disconnect(self, source_id: str) -> None:
        source = self.get(source_id)
        reader, source.reader = source.reader, None
        if reader is not None:
            reader.stop()
        poller, source.poller = source.poller, None
        if poller is not None:
            poller.stop()
        if not source.is_modbus:
            source.connection.disconnect()
        source.parser.reset()
        if self._diagnostics is not None:
            self._diagnostics.note_disconnected(source_id)
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
        if source.is_modbus:
            raise SerialConnectionError(
                "Terminal transmit is not available for Modbus RTU sources."
            )
        written = source.connection.write(data)
        source.tx_bytes += written
        return written

    def _modbus_update(
        self, source_id: str, poller: ModbusPoller, update: ChannelUpdate
    ) -> None:
        source = self.get(source_id)
        if source.poller is not poller or not source.is_connected:
            return
        source.latest_values.update(zip(update.names, update.values, strict=True))
        if self._diagnostics is not None:
            self._diagnostics.note_structured_update(source_id, update.names)
        self.structured_update.emit(source_id, update)

    def _poller_failed(
        self, source_id: str, poller: ModbusPoller, message: str
    ) -> None:
        source = self.get(source_id)
        if source.poller is not poller:
            return
        source.poller = None
        poller.stop()
        if self._diagnostics is not None:
            self._diagnostics.note_disconnected(source_id)
        self.source_state_changed.emit(source_id, "error")
        self.source_failed.emit(source_id, message)

    def _receive(self, source_id: str, reader: SerialReader, data: bytes) -> None:
        source = self.get(source_id)
        if source.reader is not reader or not source.is_connected:
            return
        source.rx_bytes += len(data)
        self.bytes_received.emit(source_id, data)
        if self._diagnostics is not None:
            self._diagnostics.note_bytes(source_id, len(data))
        updates, observation = source.parser.observe(data)
        if self._diagnostics is not None:
            self._diagnostics.note_parser_observation(source_id, observation)
        for update in updates:
            source.latest_values.update(zip(update.names, update.values, strict=True))
            if self._diagnostics is not None:
                self._diagnostics.note_structured_update(source_id, update.names)
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
        if self._diagnostics is not None:
            self._diagnostics.note_disconnected(source_id)
        self.source_state_changed.emit(source_id, "error")
        self.source_failed.emit(source_id, message)
