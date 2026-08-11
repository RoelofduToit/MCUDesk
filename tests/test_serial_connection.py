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
    )


def test_disconnect_closes_and_releases_serial_port() -> None:
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    connection.connect("COM4", 9600)

    connection.disconnect()

    serial_port.close.assert_called_once_with()
    assert not connection.is_connected
    assert connection.device is None


def test_connection_failure_is_translated_and_state_remains_disconnected() -> None:
    serial_factory = Mock(side_effect=SerialException("Permission denied"))
    connection = SerialConnection(serial_factory=serial_factory)

    with pytest.raises(SerialConnectionError, match="Permission denied"):
        connection.connect("/dev/ttyACM0", 115200)

    assert not connection.is_connected
    assert connection.device is None
