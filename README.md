# SerialScope

SerialScope is the foundation of a modern cross-platform serial terminal, data logger, and engineering data application for Windows and Linux.

Version 0.8.0 supports multiple independent serial devices. Each device owns its connection, reader, parser, counters, terminal stream, graph workspace, and recording files. The Data and Dashboard presentations can show source-aware channels from several devices together.

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

After installation, the package entry point is also available:

```bash
serialscope
```

## Test

```bash
python -m pytest
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the project boundaries and architectural rules.
