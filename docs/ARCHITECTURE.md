# SerialScope Architecture

## Purpose

SerialScope is intended to become a professional cross-platform desktop application for Windows and Linux. It will provide a modern serial terminal, data logging, intelligent parsing, device profiles, live engineering graphs, and later engineering and data-analysis features.

Phase 0 established the project foundation. Version 0.1.1 added the initial desktop UI shell, version 0.1.2 added serial-port discovery, version 0.1.3 added connection lifecycle management, version 0.1.4 added serial receive, and version 0.1.5 adds serial transmit. It does not interpret serial data.

## Current structure

- `main.py` is a minimal source-checkout launcher.
- `src/serialscope/app.py` owns the Qt application lifecycle.
- `src/serialscope/serial/port_scanner.py` discovers ports through PySerial and returns Qt-independent structured metadata.
- `src/serialscope/serial/connection.py` owns the live PySerial object and its open/close lifecycle.
- `src/serialscope/serial/reader.py` runs bounded serial reads in a dedicated `QThread` and emits raw byte chunks.
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

## Version 0.1.5 boundaries

The application performs a synchronous serial-port enumeration at startup and when Refresh is clicked. `SerialPortInfo` values cross the discovery/UI boundary, and the actual device identifier is stored as combo-box item data rather than recovered from display text. Enumeration is kept synchronous because normal port discovery is brief; this decision can be revisited if measurements demonstrate a need.

`SerialConnection` remains the sole owner of the live `serial.Serial` instance. The UI requests synchronous connect and disconnect operations and presents their state; PySerial exceptions are translated at the serial-layer boundary before reaching the UI. Opening and closing remain on the GUI thread because they are short lifecycle operations.

After connection, a `SerialReaderWorker` performs bounded reads in a dedicated `QThread`. It emits the original `bytes` chunks and never accesses widgets. `MainWindow` wires those signals to the terminal and RX counter. `TerminalWidget` uses incremental UTF-8 decoding with replacement for invalid sequences, preserving partial multibyte characters across chunks. Disconnect and window shutdown request reader termination, wait for its short-timeout read to finish, and then close the port.

For transmit, `TerminalWidget` converts command text and the selected line ending to UTF-8 `bytes`. `MainWindow` requests the write and updates the TX counter from the actual count returned. `SerialConnection` exclusively accesses PySerial and accepts raw bytes, preserving a path for future binary transmission without coupling the serial layer to text.

Version 0.1.5 intentionally includes no local transmit echo, history, macros, binary/HEX entry, or serial-data interpretation. It also includes no graphs, database, logging pipeline, parsing, profiles, reconnect behavior, or other protocol features.

## Planned technology direction

- Python
- PySide6 / Qt 6 for the desktop GUI
- PySerial for serial-port discovery and future serial communication
- PyQtGraph for future live plotting
- pytest for automated tests

PyQtGraph is not a dependency until plotting is implemented.
