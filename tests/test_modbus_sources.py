from unittest.mock import Mock

import pytest

from serialscope.modbus import (
    FakeModbusTransport,
    ModbusPoller,
    ModbusRegister,
    ModbusRtuConfiguration,
)
from serialscope.parsing import ChannelUpdate
from serialscope.serial import SerialConnection, SerialConnectionError, SerialSourceManager


class Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in self.callbacks:
            callback(*args)


class Reader:
    def __init__(self, _connection):
        self.bytes_received = Signal()
        self.failed = Signal()

    def start(self):
        pass

    def stop(self):
        pass


class ImmediatePoller:
    def __init__(self, configuration, factory):
        self.configuration = configuration
        self.transport = factory()
        self.values_ready = Signal()
        self.status_changed = Signal()
        self.failed = Signal()
        self.running = False

    @property
    def is_running(self) -> bool:
        return self.running

    def start(self) -> None:
        self.transport.connect()
        self.running = True
        register = self.configuration.enabled_registers[0]
        self.values_ready.emit(ChannelUpdate((register.name,), (11,), False))

    def stop(self) -> None:
        self.running = False
        self.transport.close()


def connection(port: str) -> SerialConnection:
    serial_port = Mock(is_open=True, port=port, in_waiting=0)
    return SerialConnection(serial_factory=Mock(return_value=serial_port))


def test_modbus_source_does_not_affect_serial_source() -> None:
    connections = iter((connection("COM3"), connection("COM4")))
    transports = []

    def transport_factory(port, settings):
        transport = FakeModbusTransport(holding={0: 7})
        transports.append((port, transport))
        return transport

    manager = SerialSourceManager(
        connection_factory=lambda: next(connections),
        reader_factory=Reader,
        poller_factory=ImmediatePoller,
        modbus_transport_factory=transport_factory,
    )
    arduino = manager.add_source("Arduino")
    vsd = manager.add_source("VSD")
    manager.apply_modbus_configuration(
        vsd.source_id,
        ModbusRtuConfiguration(registers=(ModbusRegister(name="RPM"),)),
    )
    updates = []
    manager.structured_update.connect(
        lambda source_id, update: updates.append((source_id, update.names))
    )
    manager.connect(arduino.source_id, "COM3", 115200)
    manager.connect(vsd.source_id, "COM4", 9600)
    arduino.reader.bytes_received.emit(b"A,B\n1,2\n")
    assert vsd.is_modbus
    assert vsd.is_connected
    assert not arduino.is_modbus
    assert (vsd.source_id, ("RPM",)) in updates
    assert (arduino.source_id, ("A", "B")) in updates
    manager.disconnect(vsd.source_id)
    assert arduino.is_connected
    assert not vsd.is_connected
    manager.disconnect(arduino.source_id)


def test_two_modbus_sources_are_isolated() -> None:
    transports = {}

    def transport_factory(port, settings):
        transport = FakeModbusTransport(holding={0: 1 if port == "COM4" else 2})
        transports[port] = transport
        return transport

    manager = SerialSourceManager(
        connection_factory=lambda: connection("unused"),
        reader_factory=Reader,
        poller_factory=ImmediatePoller,
        modbus_transport_factory=transport_factory,
    )
    a = manager.add_source("A")
    b = manager.add_source("B")
    config_a = ModbusRtuConfiguration(registers=(ModbusRegister(name="A1"),))
    config_b = ModbusRtuConfiguration(registers=(ModbusRegister(name="B1"),))
    manager.apply_modbus_configuration(a.source_id, config_a)
    manager.apply_modbus_configuration(b.source_id, config_b)
    manager.connect(a.source_id, "COM4", 9600)
    manager.connect(b.source_id, "COM5", 19200)
    assert transports["COM4"].connected
    assert transports["COM5"].connected
    manager.disconnect(a.source_id)
    assert transports["COM4"].closed
    assert not transports["COM5"].closed
    manager.disconnect(b.source_id)


def test_modbus_cannot_share_an_open_serial_port() -> None:
    manager = SerialSourceManager(
        connection_factory=lambda: connection("COM4"),
        reader_factory=Reader,
        poller_factory=ImmediatePoller,
        modbus_transport_factory=lambda port, settings: FakeModbusTransport(holding={0: 1}),
    )
    serial_source = manager.add_source("Arduino")
    modbus_source = manager.add_source("VSD")
    manager.apply_modbus_configuration(
        modbus_source.source_id,
        ModbusRtuConfiguration(registers=(ModbusRegister(name="RPM"),)),
    )
    manager.connect(serial_source.source_id, "COM4", 115200)
    with pytest.raises(SerialConnectionError, match="already connected"):
        manager.connect(modbus_source.source_id, "COM4", 9600)


def test_modbus_write_is_rejected() -> None:
    manager = SerialSourceManager(
        poller_factory=ImmediatePoller,
        modbus_transport_factory=lambda port, settings: FakeModbusTransport(holding={0: 1}),
    )
    source = manager.add_source("VSD")
    manager.apply_modbus_configuration(
        source.source_id,
        ModbusRtuConfiguration(registers=(ModbusRegister(name="RPM"),)),
    )
    manager.connect(source.source_id, "COM4", 9600)
    with pytest.raises(SerialConnectionError, match="not available"):
        manager.write(source.source_id, b"01 03")
    manager.disconnect(source.source_id)
