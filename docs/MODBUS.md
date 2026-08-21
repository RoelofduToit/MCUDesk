# MCUDesk Modbus RTU

MCUDesk can poll industrial devices that speak **Modbus RTU over RS-485** and
turn the register values into normal MCUDesk channels. Those channels use the
existing Data, Graphs, Dashboard, alarms, calculated channels, and structured
logging pipeline.

This milestone is **read-only**. MCUDesk does not write coils or registers.

## Physical setup

```text
Computer
   ↓ USB
USB-to-RS485 adapter
   ↓ A / B
Modbus RTU device (PLC, VSD, meter, controller, …)
```

A USB-to-RS485 adapter is required. MCUDesk does not speak Modbus TCP in this
version.

RS-485 A/B labelling is not consistent across manufacturers. If the port opens
but the slave never replies, swap A and B.

## Configuration

Open **Settings → Modbus Devices...**. The main window is unchanged for ordinary
serial-stream devices.

Match the device manual for:

- serial port
- baud rate
- parity (None / Even / Odd)
- stop bits
- slave / unit ID (1–247)

Then map registers:

- **Holding Register** uses Modbus function 03
- **Input Register** uses Modbus function 04

Addresses are **0-based protocol addresses**. Some manuals show Holding Register
0 as 40001, or Input Register 0 as 30001. MCUDesk does not subtract 40001
automatically.

## Data types and scaling

Supported types: UInt16, Int16, UInt32, Int32, Float32, Float64.

16-bit values occupy one register. 32-bit values occupy two. Float64 occupies
four. MCUDesk requests the required count automatically.

Engineering value:

```text
value = raw × scale + offset
```

Default scale is 1 and offset is 0.

32-bit and 64-bit values also have byte order (Big / Little) and word order
(High first / Low first). MCUDesk does not guess endianness.

An optional unit on the register is an initial Channel Settings unit. After the
channel exists, aliases and units continue to live in **Channels → Configure
Channels**.

## Polling and Terminal

Polling runs in a background thread per Modbus source. A timeout or missing
slave does not freeze the GUI. Unplugging the adapter reports a connection
error and uses the existing reconnect path.

The Terminal stays dedicated to serial-stream devices. Modbus sources show:

```text
Terminal is not available for Modbus RTU sources.
```

Data, Graphs, and Dashboard are the Modbus views. Recorded sessions write
engineering values to the existing per-source `data.csv`. Raw Modbus frames are
not treated as text serial data.

Device Profiles store the Modbus map. Existing serial-stream profiles continue
to load without choosing a protocol.

## Limitations

- No Modbus TCP
- No register or coil writes
- No automatic A/B or endianness detection
- Register maps must come from the manufacturer documentation

## Development simulator

A Linux PTY slave for software tests is documented in
[MODBUS_SIMULATOR.md](MODBUS_SIMULATOR.md). It is not a physical RS-485 test
and is not installed with the MCUDesk application.
