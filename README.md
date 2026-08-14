# SerialScope

SerialScope is the foundation of a modern cross-platform serial terminal, data logger, and engineering data application for Windows and Linux.

Version 0.9.3 adds parent-session operator event markers and clearer circular multi-select channel controls while retaining the standalone Linux build and long-run reliability foundation. Each device owns its connection, reader, parser, counters, terminal stream, graph workspace, and recording files. Annotation events use the experiment's shared clock and remain separate from measurement data.

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
