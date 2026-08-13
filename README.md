# SerialScope

SerialScope is the foundation of a modern cross-platform serial terminal, data logger, and engineering data application for Windows and Linux.

Version 0.6.2 adds measured-value cursor inspection, visible-range statistics, Reset Zoom, and optional display-only smoothing and Linear/PCHIP interpolation to live and replay graphs. Recorded measurements, parser output, raw logs, and structured session CSV remain unchanged. Use **File → Open Session...** to inspect a completed session without a serial connection.

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
