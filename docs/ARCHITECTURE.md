# SerialScope Architecture

## Purpose

SerialScope is intended to become a professional cross-platform desktop application for Windows and Linux. It will provide a modern serial terminal, data logging, intelligent parsing, device profiles, live engineering graphs, and later engineering and data-analysis features.

Phase 0 through v0.2 established the terminal, serial, and raw recording foundations. Version 0.3 adds deterministic CSV and key/value channel detection as an optional RX branch.

## Current structure

- `main.py` is a minimal source-checkout launcher.
- `src/serialscope/app.py` owns the Qt application lifecycle.
- `src/serialscope/serial/port_scanner.py` discovers ports through PySerial and returns Qt-independent structured metadata.
- `src/serialscope/serial/connection.py` owns the live PySerial object and its open/close lifecycle.
- `src/serialscope/serial/reader.py` runs bounded serial reads in a dedicated `QThread` and emits raw byte chunks.
- `src/serialscope/logging/raw_logger.py` owns a buffered binary log file and writes exact RX byte chunks.
- `src/serialscope/logging/session.py` owns session directories, timing, metadata, and end-reason lifecycle around `RawLogger`.
- `src/serialscope/parsing/csv_parser.py` incrementally detects simple CSV headers and emits numeric channel updates without Qt dependencies.
- `src/serialscope/parsing/key_value_parser.py` incrementally parses comma-separated numeric `key=value` lines.
- `src/serialscope/parsing/stream_parser.py` deterministically selects and locks a parser for the current connection.
- `src/serialscope/ui/channels_widget.py` presents detected channel values in a compact scrollable view.
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

## Version 0.3.2 boundaries

The application performs a synchronous serial-port enumeration at startup and when Refresh is clicked. `SerialPortInfo` values cross the discovery/UI boundary, and the actual device identifier is stored as combo-box item data rather than recovered from display text. Enumeration is kept synchronous because normal port discovery is brief; this decision can be revisited if measurements demonstrate a need.

`SerialConnection` remains the sole owner of the live `serial.Serial` instance. The UI requests synchronous connect and disconnect operations and presents their state; PySerial exceptions are translated at the serial-layer boundary before reaching the UI. Opening and closing remain on the GUI thread because they are short lifecycle operations.

After connection, a `SerialReaderWorker` performs bounded reads in a dedicated `QThread`. It emits the original `bytes` chunks and never accesses widgets. `MainWindow` wires those signals to the terminal and RX counter. `TerminalWidget` uses incremental UTF-8 decoding with replacement for invalid sequences, preserving partial multibyte characters across chunks. Disconnect and window shutdown request reader termination, wait for its short-timeout read to finish, and then close the port.

For transmit, `TerminalWidget` converts command text and the selected line ending to UTF-8 `bytes`. `MainWindow` requests the write and updates the TX counter from the actual count returned. `SerialConnection` exclusively accesses PySerial and accepts raw bytes, preserving a path for future binary transmission without coupling the serial layer to text.

`TerminalWidget` caps its Qt document at 10,000 text blocks, allowing Qt to discard old display content without full-document rewrites. It follows incoming output only while the user is already at the bottom. Clearing affects visible content only. RX and TX totals remain integer bytes in `MainWindow`; status labels format them with decimal units (`1 KB = 1,000 B`, `1 MB = 1,000,000 B`). Totals reset only after a new connection opens successfully.

When raw logging is active, `MainWindow` fans each received `bytes` chunk into two independent consumers: `TerminalWidget` decodes it for display, while `RawLogger` writes it directly to a buffered binary file. The logger never receives decoded text and adds no timestamps, delimiters, or metadata. It owns the file handle and logged-byte count. Manual stop, connection loss, and application shutdown flush and close it before serial teardown.

Each `RecordingSession` creates a collision-safe directory containing `raw.log` and `session.json`. It records the application version, optional session name, local and UTC times, serial configuration, platform, elapsed duration, logged and connection RX totals, and a lifecycle end reason. Metadata is human-readable JSON and is replaced atomically. `RawLogger` remains concerned only with exact raw bytes.

The UI timer updates elapsed-time presentation approximately once per second. It neither writes metadata nor touches the raw stream. Normal stop, serial disconnect/error, logging failure, and application shutdown finalize metadata with distinct end reasons.

Incoming RX bytes fan out independently to terminal display, raw session logging, and `CsvChannelParser`. The parser keeps only an incomplete-line buffer and processes each newly completed LF or CRLF line. A header requires at least two unique, non-empty, non-numeric comma-separated names. Once detected, rows must have the same field count and every value must be a finite integer or floating-point number. Invalid lines produce no update and do not clear existing channels or affect the other RX branches.

`ChannelUpdate` carries immutable name and numeric-value tuples. `MainWindow` forwards updates to `ChannelsWidget`, which reuses value labels while the header is unchanged and provides a bounded-width scrollable view. Parser and channel state reset for a new connection and on disconnect.

Key/value lines require at least two unique, non-empty keys with finite numeric values. Whitespace around keys, values, commas, and equals signs is ignored. Integer, floating-point, negative, and scientific-notation values are supported. Updates may add channels or omit existing channels; omitted values remain visible until updated later.

`SerialStreamParser` feeds both deterministic parsers only until one produces a structured update, then locks that format until connection reset. Key/value lines cannot qualify as CSV headers because CSV channel names containing `=` are rejected. Explicit or confirmed headerless CSV therefore coexists without delimiter guessing.

Version 0.3.2 intentionally includes no delimiter inference, JSON parsing, unit inference, calibration, statistics, structured export, databases, graphs, profiles, or protocol features.

## Planned technology direction

- Python
- PySide6 / Qt 6 for the desktop GUI
- PySerial for serial-port discovery and future serial communication
- PyQtGraph for future live plotting
- pytest for automated tests

PyQtGraph is not a dependency until plotting is implemented.
