# SerialScope

SerialScope is the foundation of a modern cross-platform serial terminal, data logger, and engineering data application for Windows and Linux.

Version 0.1.3 discovers serial ports on Windows and Linux and supports opening and closing a selected port with standard 8-N-1 settings. Receiving and transmitting serial data, plotting, parsing, profiles, logging, and persistence are intentionally not implemented.

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
