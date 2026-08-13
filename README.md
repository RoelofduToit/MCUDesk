# SerialScope

SerialScope is the foundation of a modern cross-platform serial terminal, data logger, and engineering data application for Windows and Linux.

Version 0.9.2 adds the first reproducible standalone Linux development build while retaining the v0.9.1 long-run reliability foundation. Each device owns its connection, reader, parser, counters, terminal stream, graph workspace, and recording files. The Data and Dashboard presentations can show source-aware channels from several devices together.

Recordings use one parent experiment directory and separate `raw.log` and `data.csv` files beneath each participating device directory. All structured files share the same host-side monotonic session origin. Existing single-device sessions remain replayable.

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

After installation, the package entry point is also available:

```bash
serialscope
```

## Test

```bash
python -m pytest
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the project boundaries and architectural rules.
See [docs/LONG_RUN_TEST.md](docs/LONG_RUN_TEST.md) for the overnight reliability checklist.
See [docs/PACKAGING_LINUX.md](docs/PACKAGING_LINUX.md) for standalone Linux build instructions.
