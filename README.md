# MCUDesk

MCUDesk is a serial terminal and engineering data
workspace for Windows and Linux. It helps connect to
microcontrollers and serial devices, inspect terminal traffic, detect structured
data, monitor live graphs and dashboards, record experiments, and replay saved
sessions.

Key capabilities include:

- independent multi-device serial connections
- raw terminal RX/TX with configurable line endings
- automatic CSV, key/value, and JSON-line channel detection
- live engineering graphs, cursor inspection, statistics, and event markers
- configurable dashboards, channel aliases, units, and alarm limits
- exact raw logging plus structured session data and metadata
- offline session replay and data export
- reusable device profiles and read-only Modbus RTU monitoring
- built-in Light and Dark themes and application update checks

## Download

Ready-to-install packages are published on the
[GitHub Releases page](https://github.com/RoelofduToit/MCUDesk/releases/latest).
Open the latest release, expand **Assets**, and download the package for your
operating system. You do not need Python to run these packaged builds.

### Linux (Debian/Ubuntu/Linux Mint, 64-bit)

Download:

```text
MCUDesk_<version>_Linux_amd64.deb
```

Then install it from a terminal, replacing `<version>` with the downloaded
release version:

```bash
cd ~/Downloads
sudo apt install ./MCUDesk_<version>_Linux_amd64.deb
```

Launch **MCUDesk** from the desktop application menu or run:

```bash
mcudesk
```

The Linux package requires a compatible 64-bit Debian-family distribution with
glibc 2.38 or newer.

### Windows (64-bit)

Download:

```text
MCUDesk_<version>_Windows_x64_Setup.exe
```

Double-click the downloaded installer and follow the setup wizard. The current
installer is not code-signed, so Windows may show a Microsoft Defender
SmartScreen warning; verify that the file came from this repository's official
GitHub release before continuing.

MCUDesk can check for stable updates from **GitHub / Updates** inside the
application. Package installation always remains an explicit user action.

## Recording format

Recordings use one parent experiment directory with `session.json` and
`events.csv`, plus separate `raw.log` and `data.csv` files beneath each
participating device directory. Operator events and structured device files
share the same host-side monotonic session origin. Existing sessions without
`events.csv` remain replayable.

## Requirements

- Python 3.10 or newer
- A Python virtual environment is recommended

## Development setup

From the repository root:

```bash
python -m venv .venv
```

Activate the environment:

```bash
# Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install the application and development dependencies:

```bash
python -m pip install -e ".[dev]"
```

## Run

```bash
python main.py
```

The package-safe module launcher works independently of the repository entry file:

```bash
python -m serialscope
```

After installation, the package entry points are also available:

```bash
mcudesk
serialscope
```

`serialscope` remains as a compatibility command. The internal Python package name is still `serialscope`.

## Test

```bash
python -m pytest
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the project boundaries and architectural rules.
See [docs/LONG_RUN_TEST.md](docs/LONG_RUN_TEST.md) for the overnight reliability checklist.
See [docs/PACKAGING_LINUX.md](docs/PACKAGING_LINUX.md) for standalone Linux build instructions.
See [docs/MODBUS.md](docs/MODBUS.md) for read-only Modbus RTU over USB/RS-485.
See [docs/MODBUS_SIMULATOR.md](docs/MODBUS_SIMULATOR.md) for the development PTY slave.
See [docs/DIAGNOSTICS.md](docs/DIAGNOSTICS.md) for live data-quality diagnostics.
