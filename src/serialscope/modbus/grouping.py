"""Deterministic grouping of adjacent compatible Modbus register reads."""

from __future__ import annotations

from dataclasses import dataclass

from serialscope.modbus.model import ModbusRegister

DEFAULT_MAX_BLOCK_REGISTERS = 32


@dataclass(frozen=True, slots=True)
class RegisterReadBlock:
    """One holding or input read covering one or more adjacent mappings."""

    kind: str
    address: int
    count: int
    items: tuple[tuple[ModbusRegister, int], ...]

    def slice_for(self, register: ModbusRegister, words: list[int] | tuple[int, ...]) -> list[int]:
        offset = next(index for item, index in self.items if item is register or item.name == register.name)
        return list(words[offset : offset + register.register_count])


def group_register_reads(
    registers: tuple[ModbusRegister, ...] | list[ModbusRegister],
    *,
    max_block_registers: int = DEFAULT_MAX_BLOCK_REGISTERS,
) -> tuple[RegisterReadBlock, ...]:
    """Group contiguous same-kind enabled registers; never span unused addresses."""
    if max_block_registers < 1:
        raise ValueError("max_block_registers must be positive")
    blocks: list[RegisterReadBlock] = []
    for kind in ("holding", "input"):
        items = sorted(
            (item for item in registers if item.enabled and item.kind == kind),
            key=lambda item: item.address,
        )
        current: list[tuple[ModbusRegister, int]] = []
        start = 0
        end = 0
        for register in items:
            if not current:
                current = [(register, 0)]
                start = register.address
                end = register.address + register.register_count
                continue
            if (
                register.address == end
                and (end - start + register.register_count) <= max_block_registers
            ):
                current.append((register, register.address - start))
                end = register.address + register.register_count
                continue
            blocks.append(
                RegisterReadBlock(kind, start, end - start, tuple(current))
            )
            current = [(register, 0)]
            start = register.address
            end = register.address + register.register_count
        if current:
            blocks.append(RegisterReadBlock(kind, start, end - start, tuple(current)))
    return tuple(blocks)
