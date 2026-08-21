#!/usr/bin/env python3
"""Development-only Modbus RTU slave for virtual serial ports.

This is not part of the MCUDesk application UI or packaged releases.
It lets developers exercise MCUDesk's read-only Modbus polling path over
Linux PTYs without USB-RS485 hardware.

Protocol addresses are 0-based, matching the MCUDesk Address field.
32-bit integers and floats use big-endian bytes and high-word-first
order (MCUDesk defaults: Byte order=Big, Word order=High first).
"""

from __future__ import annotations

import argparse
import os
import signal
import sys

from pymodbus.server import StartSerialServer
from pymodbus.simulator import DataType, SimData, SimDevice

HOLDING_TEMPERATURE = 0
HOLDING_PRESSURE = 1
HOLDING_SIGNED = 2
HOLDING_RPM = 10
HOLDING_FLOW = 20
INPUT_TEMPERATURE = 0

STATIC_TEMPERATURE_RAW = 253
STATIC_PRESSURE_RAW = 1013
STATIC_SIGNED = -123
STATIC_RPM = 123456
STATIC_FLOW = 12.34
STATIC_INPUT_TEMPERATURE_RAW = 321

_dynamic = False
_tick = 0


def _build_device(slave_id: int) -> SimDevice:
    holding = [
        SimData(
            address=HOLDING_TEMPERATURE,
            values=STATIC_TEMPERATURE_RAW,
            datatype=DataType.UINT16,
            readonly=True,
        ),
        SimData(
            address=HOLDING_PRESSURE,
            values=STATIC_PRESSURE_RAW,
            datatype=DataType.UINT16,
            readonly=True,
        ),
        SimData(
            address=HOLDING_SIGNED,
            values=STATIC_SIGNED,
            datatype=DataType.INT16,
            readonly=True,
        ),
        SimData(
            address=HOLDING_RPM,
            values=STATIC_RPM,
            datatype=DataType.UINT32,
            readonly=True,
        ),
        SimData(
            address=HOLDING_FLOW,
            values=STATIC_FLOW,
            datatype=DataType.FLOAT32,
            readonly=True,
        ),
    ]
    inputs = [
        SimData(
            address=INPUT_TEMPERATURE,
            values=STATIC_INPUT_TEMPERATURE_RAW,
            datatype=DataType.UINT16,
            readonly=True,
        ),
    ]
    unused_bits = [
        SimData(address=0, values=False, datatype=DataType.BITS, readonly=True)
    ]
    unused_discrete = [
        SimData(address=0, values=False, datatype=DataType.BITS, readonly=True)
    ]
    return SimDevice(
        id=slave_id,
        simdata=(unused_bits, unused_discrete, holding, inputs),
        action=_on_access,
    )


async def _on_access(
    function_code: int,
    start_address: int,
    address: int,
    count: int,
    current_registers: list[int],
    set_values: list[int] | list[bool] | None,
) -> None:
    """Optionally mutate holding-register words before the response is sent."""
    del address, count, set_values
    global _tick
    if not _dynamic or function_code != 3:
        return None
    _tick += 1
    for offset, _word in enumerate(current_registers):
        register_address = start_address + offset
        if register_address == HOLDING_TEMPERATURE:
            current_registers[offset] = 250 + (_tick % 11)
        elif register_address == HOLDING_PRESSURE:
            current_registers[offset] = 990 + (_tick % 21)
    return None


def _toggle_dynamic(_signum: int, _frame: object) -> None:
    global _dynamic, _tick
    _dynamic = not _dynamic
    _tick = 0
    print(f"dynamic values: {'ON' if _dynamic else 'OFF'}", flush=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Development-only Modbus RTU slave for MCUDesk virtual-serial tests. "
            "Not a physical RS-485 validation tool."
        )
    )
    parser.add_argument(
        "--port",
        required=True,
        help="Serial port or PTY path for the slave (for example /tmp/mcudesk-modbus-sim)",
    )
    parser.add_argument("--baud", type=int, default=9600, help="Baud rate (default: 9600)")
    parser.add_argument(
        "--slave-id",
        type=int,
        default=1,
        metavar="ID",
        help="Modbus slave / unit ID (default: 1)",
    )
    parser.add_argument(
        "--dynamic",
        action="store_true",
        help="Start with changing Temperature and Pressure values",
    )
    return parser.parse_args()


def _print_banner(args: argparse.Namespace) -> None:
    print("MCUDesk development Modbus RTU simulator", flush=True)
    print("  This is a software test tool, not a physical RS-485 validator.", flush=True)
    print(f"  pid:        {os.getpid()}", flush=True)
    print(f"  port:       {args.port}", flush=True)
    print(f"  slave id:   {args.slave_id}", flush=True)
    print(f"  serial:     {args.baud} 8N1 RTU", flush=True)
    print("  addressing: protocol 0-based (MCUDesk Address field)", flush=True)
    print("  32-bit/float encoding: big-endian bytes, high word first", flush=True)
    print("  holding[0]  UINT16  253     → 25.3 °C @ scale 0.1", flush=True)
    print("  holding[1]  UINT16  1013    → 101.3 @ scale 0.1", flush=True)
    print("  holding[2]  INT16   -123", flush=True)
    print("  holding[10] UINT32  123456  (words 0x0001, 0xE240)", flush=True)
    print("  holding[20] FLOAT32 12.34", flush=True)
    print("  input[0]    UINT16  321     → 32.1 @ scale 0.1", flush=True)
    if hasattr(signal, "SIGUSR1"):
        print("  SIGUSR1 toggles dynamic Temperature/Pressure", flush=True)
    print(f"  dynamic:    {'ON' if _dynamic else 'OFF'}", flush=True)
    print("waiting for MCUDesk...", flush=True)


def main() -> None:
    global _dynamic
    args = _parse_args()
    if not 1 <= args.slave_id <= 247:
        raise SystemExit("error: --slave-id must be between 1 and 247")
    _dynamic = args.dynamic
    if hasattr(signal, "SIGUSR1"):
        signal.signal(signal.SIGUSR1, _toggle_dynamic)
    _print_banner(args)
    StartSerialServer(
        _build_device(args.slave_id),
        port=args.port,
        baudrate=args.baud,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=1,
        reconnect_delay=0.5,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
