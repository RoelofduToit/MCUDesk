# SerialScope

SerialScope is the foundation of a modern cross-platform serial terminal, data logger, and engineering data application for Windows and Linux.

Version 0.6.1 adds offline replay of completed SerialScope session folders. Use **File → Open Session...** to load `session.json` and `data.csv`; the Data and Graphs tabs then show the recorded structured values without requiring a serial connection. Use **File → Close Session** to return to the live workspace.

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
