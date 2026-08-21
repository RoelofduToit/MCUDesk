# MCUDesk

MCUDesk is a cross-platform serial terminal and engineering data tool for Windows and Linux.

Version 0.11.0 adds asynchronous stable-release checking and verified Linux
`.deb` downloads through the public GitHub Releases API. Installation remains
an explicit handoff to the operating system package installer.

Recordings use one parent experiment directory with `session.json` and `events.csv`, plus separate `raw.log` and `data.csv` files beneath each participating device directory. Operator events and structured device files share the same host-side monotonic session origin. Existing sessions without `events.csv` remain replayable.

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
See [docs/DIAGNOSTICS.md](docs/DIAGNOSTICS.md) for live data-quality diagnostics.
