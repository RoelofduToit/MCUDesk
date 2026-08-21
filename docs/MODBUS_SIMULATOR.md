# MCUDesk Modbus RTU development simulator

`tools/modbus_rtu_simulator.py` is a **development / software test tool**.
It is a deterministic Modbus RTU slave for Linux virtual serial ports. It is
not installed with the MCUDesk application bundle.

It does **not** validate physical RS-485:

- USB-RS485 adapter drivers
- A/B wiring or polarity
- termination
- biasing
- grounding
- electrical noise
- long cables
- vendor-specific Modbus behaviour

## Linux virtual serial pair

Use two terminals. `socat` creates a null-modem pair of PTYs.

**Terminal 1:**

```bash
socat -d -d \
  pty,raw,echo=0,link=/tmp/mcudesk-modbus-mcudesk \
  pty,raw,echo=0,link=/tmp/mcudesk-modbus-sim
```

**Terminal 2:**

```bash
python tools/modbus_rtu_simulator.py \
  --port /tmp/mcudesk-modbus-sim
```

The slave uses **9600 8N1**, slave ID **1**, and RTU framing.

| Role | Path |
| --- | --- |
| Simulator | `/tmp/mcudesk-modbus-sim` |
| MCUDesk | `/tmp/mcudesk-modbus-mcudesk` |

PySerial does not list `/dev/pts` devices. For a GUI session, select
`/tmp/mcudesk-modbus-mcudesk` if it is available, or inject that path as a
discovered port from a checkout. USB-RS485 adapters continue to appear in the
normal port list.

Stop the simulator with Ctrl+C. Leave `socat` running while MCUDesk is
connected.

## MCUDesk settings

Open **Settings → Modbus Devices...**.

| Field | Value |
| --- | --- |
| Port | `/tmp/mcudesk-modbus-mcudesk` |
| Baud | 9600 |
| Parity | None |
| Stop bits | 1 |
| Slave ID | 1 |
| Poll interval | 1000 ms |

Addresses are **0-based protocol addresses**. MCUDesk does not convert 40001.

## Simulated register map

Byte order is **big**. Word order is **high first**. MCUDesk scale/offset are
applied in the application, not in the slave.

| MCUDesk name | Kind | Address | Type | Slave raw | Scale | Expected |
| --- | --- | --- | --- | --- | --- | --- |
| Temperature | Holding | 0 | UInt16 | 253 | 0.1 | 25.3 |
| Pressure | Holding | 1 | UInt16 | 1013 | 0.1 | 101.3 |
| SignedValue | Holding | 2 | Int16 | −123 | 1 | −123 |
| RPM32 | Holding | 10 | UInt32 | 123456 | 1 | 123456 |
| FlowFloat | Holding | 20 | Float32 | 12.34 | 1 | ≈12.34 |
| InputTemperature | Input | 0 | UInt16 | 321 | 0.1 | 32.1 |

UInt32 123456 is stored as holding words `0x0001`, `0xE240`. Float32 12.34 is
IEEE-754 with the high word first.

Unmapped addresses return a Modbus exception. MCUDesk must not display a fake
zero for those registers.

## Changing values

Start with motion:

```bash
python tools/modbus_rtu_simulator.py --port /tmp/mcudesk-modbus-sim --dynamic
```

Or send `SIGUSR1` to a running simulator (Linux/macOS):

```bash
kill -USR1 <pid>
```

The pid is printed at startup. Dynamic mode only changes Temperature and
Pressure:

- Temperature raw: 250, 251, … 260, then wrap (25.0–26.0 at scale 0.1)
- Pressure raw: 990 + (tick % 21) (99.0–101.0 at scale 0.1)

Use this to confirm Graphs are following live polls, not one cached response.
