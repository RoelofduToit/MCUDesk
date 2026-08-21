"""Deterministic decoding of Modbus register words into engineering values."""

from __future__ import annotations

import struct

from serialscope.modbus.model import ModbusRegister, register_count_for_type


def register_count(data_type: str) -> int:
    return register_count_for_type(data_type)


def _word_bytes(word: int, byte_order: str) -> bytes:
    value = word & 0xFFFF
    if byte_order == "little":
        return struct.pack("<H", value)
    return struct.pack(">H", value)


def decode_words(
    words: tuple[int, ...] | list[int],
    data_type: str,
    *,
    byte_order: str = "big",
    word_order: str = "high_first",
    scale: float = 1.0,
    offset: float = 0.0,
) -> int | float:
    """Decode one configured value from the exact register words it occupies."""
    needed = register_count_for_type(data_type)
    if len(words) != needed:
        raise ValueError(f"{data_type} requires {needed} register(s), not {len(words)}.")
    ordered = tuple(words) if word_order == "high_first" else tuple(reversed(words))
    payload = b"".join(_word_bytes(word, byte_order) for word in ordered)
    if data_type == "uint16":
        raw: int | float = struct.unpack(">H", payload)[0]
    elif data_type == "int16":
        raw = struct.unpack(">h", payload)[0]
    elif data_type == "uint32":
        raw = struct.unpack(">I", payload)[0]
    elif data_type == "int32":
        raw = struct.unpack(">i", payload)[0]
    elif data_type == "float32":
        raw = struct.unpack(">f", payload)[0]
    elif data_type == "float64":
        raw = struct.unpack(">d", payload)[0]
    else:
        raise ValueError(f"Unsupported Modbus data type: {data_type}.")
    if scale == 1 and offset == 0 and isinstance(raw, int):
        return raw
    return float(raw) * float(scale) + float(offset)


def decode_registers(words: tuple[int, ...] | list[int], register: ModbusRegister) -> int | float:
    """Decode one mapped register from a contiguous read block slice."""
    return decode_words(
        words,
        register.data_type,
        byte_order=register.byte_order,
        word_order=register.word_order,
        scale=register.scale,
        offset=register.offset,
    )
