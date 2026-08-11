# SerialScope Architecture

## Purpose

SerialScope is intended to become a professional cross-platform desktop application for Windows and Linux. It will provide a modern serial terminal, data logging, intelligent parsing, device profiles, live engineering graphs, and later engineering and data-analysis features.

Phase 0 establishes only the project foundation. It does not implement product features.

## Current structure

- `main.py` is a minimal source-checkout launcher.
- `src/serialscope/app.py` owns the Qt application lifecycle.
- `src/serialscope/ui/` contains Qt widgets and other presentation code.
- `tests/` contains automated tests.
- `docs/` contains project documentation and architectural decisions.

Future modules should be introduced only when their responsibilities are needed. Business and domain logic must live outside the GUI so it can be tested without constructing Qt widgets.

## Architectural rules

- Keep `main.py` small; it only starts the application.
- Keep business logic out of Qt widgets and other GUI code.
- Keep modules cohesive and interfaces between layers explicit.
- Never perform blocking serial I/O on the GUI thread. A future serial subsystem must use an appropriate worker-thread or asynchronous boundary and communicate with the UI safely.
- Use `pathlib.Path` for filesystem paths.
- Preserve compatibility with Windows and Linux; do not rely on platform-specific paths or shell behavior.
- Add dependencies only when a current requirement justifies them.
- Keep serial transport, parsing, logging, profiles, plotting, and persistence as separate concerns when they are introduced.

## Phase 0 boundaries

The current application creates a `QApplication` and displays a blank `QMainWindow` titled **SerialScope**. Phase 0 intentionally includes no serial communication, graphs, database, logging pipeline, parsing, profiles, or other application features.

## Planned technology direction

- Python
- PySide6 / Qt 6 for the desktop GUI
- PySerial for future serial communication
- PyQtGraph for future live plotting
- pytest for automated tests

PySerial and PyQtGraph are not dependencies until their corresponding features are implemented.
