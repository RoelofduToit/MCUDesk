"""Validated Modbus RTU configuration persisted with Device Profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


PROTOCOL_SERIAL_STREAM = "serial_stream"
PROTOCOL_MODBUS_RTU = "modbus_rtu"
SOURCE_PROTOCOLS = (PROTOCOL_SERIAL_STREAM, PROTOCOL_MODBUS_RTU)

REGISTER_KINDS = ("holding", "input")
DATA_TYPES = ("uint16", "int16", "uint32", "int32", "float32", "float64")
BYTE_ORDERS = ("big", "little")
WORD_ORDERS = ("high_first", "low_first")
MODBUS_PARITIES = ("none", "even", "odd")
STOP_BITS_OPTIONS = (1, 2)

MIN_SLAVE_ID = 1
MAX_SLAVE_ID = 247
MIN_INTERVAL_MS = 50
MAX_INTERVAL_MS = 60_000
DEFAULT_INTERVAL_MS = 500
MAX_REGISTER_ADDRESS = 65_535
MIN_TIMEOUT_S = 0.2
MAX_TIMEOUT_S = 5.0

_REGISTER_WIDTH = {
    "uint16": 1,
    "int16": 1,
    "uint32": 2,
    "int32": 2,
    "float32": 2,
    "float64": 4,
}


class ModbusRtuConfigurationError(ValueError):
    """A user-presentable Modbus configuration problem."""


def register_count_for_type(data_type: str) -> int:
    try:
        return _REGISTER_WIDTH[data_type]
    except KeyError as error:
        raise ModbusRtuConfigurationError(
            f"Unsupported Modbus data type: {data_type}."
        ) from error


def _optional_text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _as_float(value: object, name: str, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ModbusRtuConfigurationError(f"{name} must be a number.") from error


def _as_int(value: object, name: str, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ModbusRtuConfigurationError(f"{name} must be an integer.") from error


@dataclass(frozen=True, slots=True)
class ModbusConnectionSettings:
    """Serial settings used only by a Modbus RTU source."""

    baud_rate: int = 9600
    data_bits: int = 8
    parity: str = "even"
    stop_bits: int = 1
    slave_id: int = 1
    timeout_s: float = 1.0

    def __post_init__(self) -> None:
        if self.baud_rate <= 0:
            raise ModbusRtuConfigurationError("Baud rate must be positive.")
        if self.data_bits != 8:
            raise ModbusRtuConfigurationError("Modbus RTU requires 8 data bits.")
        if self.parity not in MODBUS_PARITIES:
            raise ModbusRtuConfigurationError("Parity must be None, Even, or Odd.")
        if self.stop_bits not in STOP_BITS_OPTIONS:
            raise ModbusRtuConfigurationError("Stop bits must be 1 or 2.")
        if not MIN_SLAVE_ID <= self.slave_id <= MAX_SLAVE_ID:
            raise ModbusRtuConfigurationError(
                f"Slave ID must be between {MIN_SLAVE_ID} and {MAX_SLAVE_ID}."
            )
        if not MIN_TIMEOUT_S <= self.timeout_s <= MAX_TIMEOUT_S:
            raise ModbusRtuConfigurationError("Timeout must be between 0.2 and 5 seconds.")

    def to_dict(self) -> dict[str, object]:
        return {
            "baud_rate": self.baud_rate,
            "data_bits": self.data_bits,
            "parity": self.parity,
            "stop_bits": self.stop_bits,
            "slave_id": self.slave_id,
            "timeout_s": self.timeout_s,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object] | None) -> "ModbusConnectionSettings":
        raw = value or {}
        return cls(
            baud_rate=_as_int(raw.get("baud_rate"), "Baud rate", 9600),
            data_bits=_as_int(raw.get("data_bits"), "Data bits", 8),
            parity=str(raw.get("parity", "even")).strip().lower() or "even",
            stop_bits=_as_int(raw.get("stop_bits"), "Stop bits", 1),
            slave_id=_as_int(raw.get("slave_id"), "Slave ID", 1),
            timeout_s=_as_float(raw.get("timeout_s"), "Timeout", 1.0),
        )


@dataclass(frozen=True, slots=True)
class ModbusRegister:
    """One mapped holding or input register that becomes a MCUDesk channel."""

    name: str
    kind: str = "holding"
    address: int = 0
    data_type: str = "uint16"
    scale: float = 1.0
    offset: float = 0.0
    unit: str = ""
    enabled: bool = True
    byte_order: str = "big"
    word_order: str = "high_first"
    description: str = ""

    def __post_init__(self) -> None:
        name = self.name.strip()
        if not name:
            raise ModbusRtuConfigurationError("Register name must not be empty.")
        if self.kind not in REGISTER_KINDS:
            raise ModbusRtuConfigurationError(
                "Register type must be Holding or Input."
            )
        if self.data_type not in DATA_TYPES:
            raise ModbusRtuConfigurationError(
                f"Unsupported Modbus data type: {self.data_type}."
            )
        if not 0 <= self.address <= MAX_REGISTER_ADDRESS:
            raise ModbusRtuConfigurationError(
                "Register address must be between 0 and 65535."
            )
        last = self.address + self.register_count - 1
        if last > MAX_REGISTER_ADDRESS:
            raise ModbusRtuConfigurationError(
                f"{self.name} extends past register address 65535."
            )
        if self.byte_order not in BYTE_ORDERS:
            raise ModbusRtuConfigurationError("Byte order must be Big or Little.")
        if self.word_order not in WORD_ORDERS:
            raise ModbusRtuConfigurationError(
                "Word order must be High first or Low first."
            )
        if not isinstance(self.scale, (int, float)) or not isinstance(self.offset, (int, float)):
            raise ModbusRtuConfigurationError("Scale and offset must be numbers.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "unit", _optional_text(self.unit))
        object.__setattr__(self, "description", _optional_text(self.description))
        object.__setattr__(self, "kind", str(self.kind))
        object.__setattr__(self, "data_type", str(self.data_type))
        object.__setattr__(self, "byte_order", str(self.byte_order))
        object.__setattr__(self, "word_order", str(self.word_order))
        object.__setattr__(self, "scale", float(self.scale))
        object.__setattr__(self, "offset", float(self.offset))
        object.__setattr__(self, "enabled", bool(self.enabled))

    @property
    def register_count(self) -> int:
        return register_count_for_type(self.data_type)

    @property
    def uses_word_order(self) -> bool:
        return self.register_count > 1

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "kind": self.kind,
            "address": self.address,
            "data_type": self.data_type,
            "scale": self.scale,
            "offset": self.offset,
            "unit": self.unit,
            "enabled": self.enabled,
            "byte_order": self.byte_order,
            "word_order": self.word_order,
            "description": self.description,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ModbusRegister":
        return cls(
            name=str(value.get("name", "")),
            kind=str(value.get("kind", "holding")).strip().lower() or "holding",
            address=_as_int(value.get("address"), "Register address", 0),
            data_type=str(value.get("data_type", "uint16")).strip().lower() or "uint16",
            scale=_as_float(value.get("scale"), "Scale", 1.0),
            offset=_as_float(value.get("offset"), "Offset", 0.0),
            unit=_optional_text(value.get("unit")),
            enabled=bool(value.get("enabled", True)),
            byte_order=str(value.get("byte_order", "big")).strip().lower() or "big",
            word_order=str(value.get("word_order", "high_first")).strip().lower()
            or "high_first",
            description=_optional_text(value.get("description")),
        )


@dataclass(frozen=True, slots=True)
class ModbusRtuConfiguration:
    """Complete read-only Modbus RTU source configuration."""

    connection: ModbusConnectionSettings = field(default_factory=ModbusConnectionSettings)
    interval_ms: int = DEFAULT_INTERVAL_MS
    registers: tuple[ModbusRegister, ...] = ()

    def __post_init__(self) -> None:
        if not MIN_INTERVAL_MS <= self.interval_ms <= MAX_INTERVAL_MS:
            raise ModbusRtuConfigurationError(
                f"Poll interval must be between {MIN_INTERVAL_MS} and {MAX_INTERVAL_MS} ms."
            )
        object.__setattr__(self, "registers", tuple(self.registers))
        self._validate_unique_names()
        self._validate_overlaps()

    def _validate_unique_names(self) -> None:
        seen: set[str] = set()
        for register in self.registers:
            key = register.name.casefold()
            if key in seen:
                raise ModbusRtuConfigurationError(
                    f"Duplicate Modbus channel name: {register.name}."
                )
            seen.add(key)

    def _validate_overlaps(self) -> None:
        by_kind: dict[str, list[ModbusRegister]] = {"holding": [], "input": []}
        for register in self.registers:
            if register.enabled:
                by_kind[register.kind].append(register)
        for kind, items in by_kind.items():
            ordered = sorted(items, key=lambda item: item.address)
            for index, current in enumerate(ordered):
                current_end = current.address + current.register_count
                for other in ordered[index + 1 :]:
                    if other.address >= current_end:
                        break
                    raise ModbusRtuConfigurationError(
                        f"{kind.title()} registers {current.name!r} and {other.name!r} overlap."
                    )

    @property
    def enabled_registers(self) -> tuple[ModbusRegister, ...]:
        return tuple(item for item in self.registers if item.enabled)

    def to_dict(self) -> dict[str, object]:
        return {
            "connection": self.connection.to_dict(),
            "interval_ms": self.interval_ms,
            "registers": [item.to_dict() for item in self.registers],
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object] | None) -> "ModbusRtuConfiguration":
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise ModbusRtuConfigurationError("Modbus configuration must be a JSON object.")
        connection = value.get("connection", {})
        if connection is None:
            connection = {}
        if not isinstance(connection, Mapping):
            raise ModbusRtuConfigurationError("Modbus connection settings must be a JSON object.")
        registers = value.get("registers", ())
        if registers is None:
            registers = ()
        if not isinstance(registers, list | tuple):
            raise ModbusRtuConfigurationError("Modbus registers must be a list.")
        parsed: list[ModbusRegister] = []
        for raw in registers:
            if not isinstance(raw, Mapping):
                raise ModbusRtuConfigurationError("Each Modbus register must be a JSON object.")
            parsed.append(ModbusRegister.from_mapping(raw))
        return cls(
            connection=ModbusConnectionSettings.from_mapping(connection),
            interval_ms=_as_int(value.get("interval_ms"), "Poll interval", DEFAULT_INTERVAL_MS),
            registers=tuple(parsed),
        )
