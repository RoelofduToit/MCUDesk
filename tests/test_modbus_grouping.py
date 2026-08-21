from serialscope.modbus.grouping import group_register_reads
from serialscope.modbus.model import ModbusRegister


def test_adjacent_same_kind_registers_are_grouped() -> None:
    blocks = group_register_reads(
        (
            ModbusRegister(name="A", address=0),
            ModbusRegister(name="B", address=1),
            ModbusRegister(name="C", address=2),
        )
    )
    assert len(blocks) == 1
    assert blocks[0].kind == "holding"
    assert blocks[0].address == 0
    assert blocks[0].count == 3
    assert [item.name for item, _offset in blocks[0].items] == ["A", "B", "C"]


def test_gaps_and_kinds_remain_separate() -> None:
    blocks = group_register_reads(
        (
            ModbusRegister(name="H0", address=0),
            ModbusRegister(name="H2", address=2),
            ModbusRegister(name="I0", kind="input", address=0),
            ModbusRegister(name="Disabled", address=1, enabled=False),
        )
    )
    assert [(block.kind, block.address, block.count) for block in blocks] == [
        ("holding", 0, 1),
        ("holding", 2, 1),
        ("input", 0, 1),
    ]


def test_multi_register_types_extend_the_block() -> None:
    blocks = group_register_reads(
        (
            ModbusRegister(name="Float", address=10, data_type="float32"),
            ModbusRegister(name="Next", address=12),
        )
    )
    assert len(blocks) == 1
    assert blocks[0].count == 3
    assert blocks[0].items[1][1] == 2
