from unittest.mock import Mock

import pytest
from serial import SerialException

from serialscope.serial import SerialConnection, SerialConnectionError


def test_successful_connection_uses_standard_serial_settings() -> None:
    serial_port = Mock(is_open=True, port="COM4")
    serial_factory = Mock(return_value=serial_port)
    connection = SerialConnection(serial_factory=serial_factory)

    connection.connect("COM4", 115200)

    assert connection.is_connected
    assert connection.device == "COM4"
    serial_factory.assert_called_once_with(
        port="COM4",
        baudrate=115200,
        bytesize=8,
        parity="N",
        stopbits=1,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
        timeout=0.1,
    )


def test_disconnect_closes_and_releases_serial_port() -> None:
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    connection.connect("COM4", 9600)

    connection.disconnect()

    serial_port.close.assert_called_once_with()
    assert not connection.is_connected
    assert connection.device is None


def test_read_returns_raw_bytes_from_open_connection() -> None:
    serial_port = Mock(is_open=True, port="COM4", in_waiting=3)
    serial_port.read.return_value = b"\xff\x00A"
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    connection.connect("COM4", 115200)

    data = connection.read()

    assert data == b"\xff\x00A"
    serial_port.read.assert_called_once_with(3)


def test_connection_failure_is_translated_and_state_remains_disconnected() -> None:
    serial_factory = Mock(side_effect=SerialException("Permission denied"))
    connection = SerialConnection(serial_factory=serial_factory)

    with pytest.raises(SerialConnectionError, match="Permission denied"):
        connection.connect("/dev/ttyACM0", 115200)

    assert not connection.is_connected
    assert connection.device is None
