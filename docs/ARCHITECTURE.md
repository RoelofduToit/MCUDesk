# SerialScope Architecture

## Purpose

SerialScope is intended to become a professional cross-platform desktop application for Windows and Linux. It will provide a modern serial terminal, data logging, intelligent parsing, device profiles, live engineering graphs, and later engineering and data-analysis features.

Phase 0 established the project foundation. Version 0.1.1 added the initial desktop UI shell. Version 0.1.2 adds serial-port discovery only; it does not open ports or implement data processing.

## Current structure

- `main.py` is a minimal source-checkout launcher.
- `src/serialscope/app.py` owns the Qt application lifecycle.
- `src/serialscope/serial/port_scanner.py` discovers ports through PySerial and returns Qt-independent structured metadata.
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

## Version 0.1.2 boundaries

The application performs a synchronous serial-port enumeration at startup and when Refresh is clicked. `SerialPortInfo` values cross the discovery/UI boundary, and the actual device identifier is stored as combo-box item data rather than recovered from display text. Enumeration is kept synchronous because normal port discovery is brief; this decision can be revisited if measurements demonstrate a need.

Version 0.1.2 intentionally does not open, configure, read, or write serial ports. Connect and Send remain inert. It also includes no graphs, database, logging pipeline, parsing, profiles, background workers, or reconnect behavior.

## Planned technology direction

- Python
- PySide6 / Qt 6 for the desktop GUI
- PySerial for serial-port discovery and future serial communication
- PyQtGraph for future live plotting
- pytest for automated tests

PyQtGraph is not a dependency until plotting is implemented.
