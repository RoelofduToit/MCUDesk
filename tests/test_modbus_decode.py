import struct

import pytest

from serialscope.modbus.decode import decode_registers, decode_words
from serialscope.modbus.model import ModbusRegister


def test_uint16_and_int16_with_scale_and_offset() -> None:
    assert decode_words([5025], "uint16", scale=0.01) == pytest.approx(50.25)
    assert decode_words([0xFFFE], "int16") == -2
    assert decode_words([100], "uint16", scale=1, offset=5) == pytest.approx(105)


def test_32bit_integers_and_float32_word_order() -> None:
    assert decode_words([0x0001, 0x0002], "uint32") == 0x00010002
    assert decode_words([0x0002, 0x0001], "uint32", word_order="low_first") == 0x00010002
    assert decode_words([0xFFFF, 0xFFFE], "int32") == -2
    payload = struct.pack(">f", 123.4)
    high, low = struct.unpack(">HH", payload)
    assert decode_words([high, low], "float32") == pytest.approx(123.4, rel=1e-6)
    assert decode_words([low, high], "float32", word_order="low_first") == pytest.approx(
        123.4, rel=1e-6
    )


def test_little_byte_order_swaps_bytes_in_each_word() -> None:
    assert decode_words([0x3412], "uint16", byte_order="little") == 0x1234
    payload = struct.pack(">f", 1.5)
    high, low = struct.unpack(">HH", payload)
    swapped = [
        struct.unpack("<H", struct.pack(">H", high))[0],
        struct.unpack("<H", struct.pack(">H", low))[0],
    ]
    assert decode_words(swapped, "float32", byte_order="little") == pytest.approx(1.5)


def test_float64_uses_four_registers() -> None:
    payload = struct.pack(">d", 12.5)
    words = struct.unpack(">HHHH", payload)
    assert decode_words(words, "float64") == pytest.approx(12.5)


def test_register_decode_uses_mapping_fields() -> None:
    register = ModbusRegister(name="Temp", data_type="uint16", scale=0.1, offset=2)
    assert decode_registers([250], register) == pytest.approx(27.0)
