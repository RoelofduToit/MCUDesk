# SerialScope Architecture

## Purpose

SerialScope is intended to become a professional cross-platform desktop application for Windows and Linux. It will provide a modern serial terminal, data logging, intelligent parsing, device profiles, live engineering graphs, and later engineering and data-analysis features.

Phase 0 established the project foundation. Version 0.1.1 adds only the initial desktop UI shell; it does not implement serial or data-processing features.

## Current structure

- `main.py` is a minimal source-checkout launcher.
- `src/serialscope/app.py` owns the Qt application lifecycle.
- `src/serialscope/ui/main_window.py` composes the top-level window and status bar.
- `src/serialscope/ui/connection_bar.py` contains the inert connection controls.
- `src/serialscope/ui/terminal_widget.py` contains the terminal display and command row.
- `src/serialscope/ui/side_panel.py` contains configuration placeholders.
- `src/serialscope/ui/style.py` contains the small application stylesheet.
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

## Version 0.1.1 boundaries

The current application creates a `QApplication` and displays a resizable `QMainWindow` titled **SerialScope**. The window contains connection controls, a terminal placeholder, command entry, side-panel sections, and status counters. These widgets have no feature behavior. Version 0.1.1 intentionally includes no serial communication, graphs, database, logging pipeline, parsing, profiles, background workers, or reconnect behavior.

## Planned technology direction

- Python
- PySide6 / Qt 6 for the desktop GUI
- PySerial for future serial communication
- PyQtGraph for future live plotting
- pytest for automated tests

PySerial and PyQtGraph are not dependencies until their corresponding features are implemented.
