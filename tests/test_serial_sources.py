from unittest.mock import Mock

import pytest

from serialscope.data import ChannelKey
from serialscope.serial import SerialConnection, SerialConnectionError, SerialSourceManager


class Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, value):
        for callback in self.callbacks:
            callback(value)


class Reader:
    def __init__(self, _connection):
        self.bytes_received = Signal()
        self.failed = Signal()
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


def connection(port: str) -> SerialConnection:
    serial_port = Mock(is_open=True, port=port, in_waiting=0)
    return SerialConnection(serial_factory=Mock(return_value=serial_port))


def test_channel_keys_separate_identical_raw_names() -> None:
    pico = ChannelKey("pico", "TC1")
    arduino = ChannelKey("arduino", "TC1")
    assert pico != arduino
    assert ChannelKey.from_storage_key(pico.storage_key) == pico


def test_sources_are_unique_and_cannot_share_an_open_port() -> None:
    connections = iter((connection("COM4"), connection("COM4")))
    manager = SerialSourceManager(
        connection_factory=lambda: next(connections), reader_factory=Reader
    )
    pico = manager.add_source("Pico")
    arduino = manager.add_source("Pico")
    assert pico.source_id == "pico"
    assert arduino.source_id == "pico_2"
    manager.connect(pico.source_id, "COM4", 115200)
    with pytest.raises(SerialConnectionError, match="already connected as Pico"):
        manager.connect(arduino.source_id, "COM4", 9600)


def test_parsers_and_disconnects_are_independent() -> None:
    connections = iter((connection("COM4"), connection("COM5")))
    manager = SerialSourceManager(
        connection_factory=lambda: next(connections), reader_factory=Reader
    )
    pico = manager.add_source("Pico")
    arduino = manager.add_source("Arduino")
    updates = []
    manager.structured_update.connect(lambda source_id, update: updates.append((source_id, update)))
    manager.connect(pico.source_id, "COM4", 115200)
    manager.connect(arduino.source_id, "COM5", 9600)

    pico.reader.bytes_received.emit(b"A,B\n1,2\n")
    arduino.reader.bytes_received.emit(b'{"A":9,"RPM":1500}\n')
    assert [(source_id, update.names) for source_id, update in updates] == [
        (pico.source_id, ("A", "B")),
        (arduino.source_id, ("A", "RPM")),
    ]

    manager.disconnect(pico.source_id)
    assert not pico.is_connected
    assert arduino.is_connected
    arduino.reader.bytes_received.emit(b'{"A":10}\n')
    assert updates[-1][0] == arduino.source_id
