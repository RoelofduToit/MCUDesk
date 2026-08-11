"""Serial connection lifecycle management."""

from collections.abc import Callable

import serial
from serial import SerialException
from serial.serialutil import SerialBase


class SerialConnectionError(Exception):
    """A user-presentable failure to open or close a serial connection."""


class SerialConnection:
    """Own a single PySerial connection without reading or writing data."""

    def __init__(
        self,
        serial_factory: Callable[..., SerialBase] = serial.Serial,
    ) -> None:
        self._serial_factory = serial_factory
        self._serial_port: SerialBase | None = None

    @property
    def is_connected(self) -> bool:
        """Return whether the owned serial port is open."""
        return self._serial_port is not None and self._serial_port.is_open

    @property
    def device(self) -> str | None:
        """Return the connected device identifier, if connected."""
        if self._serial_port is None:
            return None
        return self._serial_port.port

    def connect(self, device: str, baud_rate: int) -> None:
        """Open a serial port using SerialScope's standard settings."""
        if self._serial_port is not None:
            raise SerialConnectionError("A serial port is already connected.")

        try:
            self._serial_port = self._serial_factory(
                port=device,
                baudrate=baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
        except (SerialException, OSError) as error:
            self._serial_port = None
            raise SerialConnectionError(
                f"Could not open {device}: {error}"
            ) from error

    def disconnect(self) -> None:
        """Close and release the owned serial port."""
        if self._serial_port is None:
            return

        serial_port = self._serial_port
        self._serial_port = None
        try:
            serial_port.close()
        except (SerialException, OSError) as error:
            raise SerialConnectionError(
                f"Could not close {serial_port.port}: {error}"
            ) from error
