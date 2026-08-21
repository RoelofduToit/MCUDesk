"""Injectable Modbus RTU transport. Production uses pymodbus; tests inject fakes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from serialscope.modbus.decode import decode_registers
from serialscope.modbus.model import ModbusConnectionSettings, ModbusRtuConfiguration


class ModbusClientError(Exception):
    """A user-presentable Modbus transport or protocol failure."""

    def __init__(self, message: str, kind: str = "error") -> None:
        super().__init__(message)
        self.kind = kind


class ModbusTransport(Protocol):
    """Minimal read-only serial Modbus client used by the poller."""

    def connect(self) -> None: ...

    def close(self) -> None: ...

    def read_holding_registers(self, address: int, count: int, slave_id: int) -> list[int]: ...

    def read_input_registers(self, address: int, count: int, slave_id: int) -> list[int]: ...


_PARITY_CODES = {"none": "N", "even": "E", "odd": "O"}


class FakeModbusTransport:
    """Deterministic in-memory Modbus slave for offline tests."""

    def __init__(
        self,
        *,
        holding: dict[int, int] | None = None,
        input_registers: dict[int, int] | None = None,
    ) -> None:
        self.holding = dict(holding or {})
        self.input_registers = dict(input_registers or {})
        self.connected = False
        self.closed = False
        self.connect_error: str | None = None
        self.read_error: ModbusClientError | None = None
        self.reads: list[tuple[str, int, int, int]] = []
        self.connect_count = 0

    def connect(self) -> None:
        self.connect_count += 1
        if self.connect_error:
            raise ModbusClientError(self.connect_error, "disconnected")
        self.connected = True
        self.closed = False

    def close(self) -> None:
        self.connected = False
        self.closed = True

    def read_holding_registers(self, address: int, count: int, slave_id: int) -> list[int]:
        return self._read("holding", self.holding, address, count, slave_id)

    def read_input_registers(self, address: int, count: int, slave_id: int) -> list[int]:
        return self._read("input", self.input_registers, address, count, slave_id)

    def _read(
        self,
        kind: str,
        table: dict[int, int],
        address: int,
        count: int,
        slave_id: int,
    ) -> list[int]:
        self.reads.append((kind, address, count, slave_id))
        if not self.connected:
            raise ModbusClientError("The Modbus connection is closed.", "disconnected")
        if self.read_error is not None:
            raise self.read_error
        values = []
        for offset in range(count):
            if address + offset not in table:
                raise ModbusClientError(
                    f"No {kind} register at address {address + offset}.",
                    "exception",
                )
            values.append(int(table[address + offset]) & 0xFFFF)
        return values


class PymodbusSerialTransport:
    """Thin pymodbus adapter that never exposes write operations."""

    def __init__(self, client: object) -> None:
        self._client = client

    def connect(self) -> None:
        connected = self._client.connect()
        if connected is False:
            raise ModbusClientError("Could not open the Modbus serial port.", "disconnected")

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            close()

    def read_holding_registers(self, address: int, count: int, slave_id: int) -> list[int]:
        return self._read("read_holding_registers", address, count, slave_id)

    def read_input_registers(self, address: int, count: int, slave_id: int) -> list[int]:
        return self._read("read_input_registers", address, count, slave_id)

    def _read(self, method_name: str, address: int, count: int, slave_id: int) -> list[int]:
        method = getattr(self._client, method_name)
        try:
            result = method(address, count=count, device_id=slave_id)
        except TypeError:
            result = method(address, count=count, slave=slave_id)
        except Exception as error:
            raise _translate_pymodbus_error(error) from error
        return _registers_from_result(result)


def _registers_from_result(result: object) -> list[int]:
    if result is None:
        raise ModbusClientError("The Modbus device did not respond.", "no_response")
    is_error = getattr(result, "isError", None)
    if callable(is_error) and is_error():
        message = str(result) or "The Modbus device returned an exception."
        raise ModbusClientError(message, "exception")
    registers = getattr(result, "registers", None)
    if not isinstance(registers, list):
        raise ModbusClientError("The Modbus response did not contain registers.", "protocol")
    return [int(value) & 0xFFFF for value in registers]


def _translate_pymodbus_error(error: Exception) -> ModbusClientError:
    name = type(error).__name__
    text = str(error) or name
    lowered = text.lower()
    if "timeout" in name.lower() or "timeout" in lowered:
        return ModbusClientError("Modbus request timed out.", "timeout")
    if "crc" in lowered or "check" in lowered:
        return ModbusClientError("Modbus CRC or protocol error.", "protocol")
    if "connect" in name.lower() or "connect" in lowered:
        return ModbusClientError(text, "disconnected")
    if "no response" in lowered or "noreply" in lowered:
        return ModbusClientError("The Modbus device did not respond.", "no_response")
    return ModbusClientError(text, "error")


def create_serial_transport(
    port: str,
    settings: ModbusConnectionSettings,
    *,
    client_factory: Callable[..., object] | None = None,
) -> PymodbusSerialTransport:
    """Create a pymodbus serial client with auto-reconnect disabled."""
    if client_factory is None:
        from pymodbus.client import ModbusSerialClient

        client_factory = ModbusSerialClient
    client = client_factory(
        port,
        baudrate=settings.baud_rate,
        bytesize=settings.data_bits,
        parity=_PARITY_CODES[settings.parity],
        stopbits=settings.stop_bits,
        timeout=settings.timeout_s,
        retries=0,
        reconnect_delay=0,
        reconnect_delay_max=0,
    )
    return PymodbusSerialTransport(client)


def probe_modbus_connection(
    transport: ModbusTransport,
    configuration: ModbusRtuConfiguration,
) -> str:
    """Open briefly, read the first enabled register, then release the port."""
    transport.connect()
    try:
        registers = configuration.enabled_registers
        if not registers:
            return "Port opened. Add an enabled register to verify the slave."
        first = registers[0]
        if first.kind == "holding":
            words = transport.read_holding_registers(
                first.address, first.register_count, configuration.connection.slave_id
            )
        else:
            words = transport.read_input_registers(
                first.address, first.register_count, configuration.connection.slave_id
            )
        value = decode_registers(words, first)
        return f"Device responding. {first.name} = {value}"
    finally:
        transport.close()
