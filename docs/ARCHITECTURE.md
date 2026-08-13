# SerialScope Architecture

## Purpose

SerialScope is intended to become a professional cross-platform desktop application for Windows and Linux. It will provide a modern serial terminal, data logging, intelligent parsing, device profiles, live engineering graphs, and later engineering and data-analysis features.

Phase 0 through v0.2 established the terminal, serial, and raw recording foundations. Version 0.3 added deterministic structured channel detection, version 0.4 introduced a tabbed workspace and graphs, and version 0.6 adds offline session replay while preserving the independent live data paths.

## Current structure

- `main.py` is a minimal source-checkout launcher.
- `src/serialscope/app.py` owns the Qt application lifecycle.
- `src/serialscope/settings.py` validates and persists small user preferences through `QSettings`.
- `src/serialscope/serial/port_scanner.py` discovers ports through PySerial and returns Qt-independent structured metadata.
- `src/serialscope/serial/connection.py` owns the live PySerial object and its open/close lifecycle.
- `src/serialscope/serial/reader.py` runs bounded serial reads in a dedicated `QThread` and emits raw byte chunks.
- `src/serialscope/logging/raw_logger.py` owns a buffered binary log file and writes exact RX byte chunks.
- `src/serialscope/logging/structured_csv_logger.py` writes parser-produced numeric samples to rectangular UTF-8 CSV.
- `src/serialscope/logging/session.py` owns session directories, timing, metadata, and end-reason lifecycle around both loggers.
- `src/serialscope/parsing/csv_parser.py` incrementally detects simple CSV headers and emits numeric channel updates without Qt dependencies.
- `src/serialscope/parsing/key_value_parser.py` incrementally parses comma-separated numeric `key=value` lines.
- `src/serialscope/parsing/json_parser.py` incrementally parses top-level numeric values from one JSON object per line.
- `src/serialscope/parsing/stream_parser.py` deterministically selects and locks a parser for the current connection.
- `src/serialscope/data/channel_history.py` retains Qt-independent, monotonic, bounded numeric history for plotting.
- `src/serialscope/data/graph_processing.py` performs pure display smoothing/interpolation and measured-data inspection/statistics without mutating graph history.
- `src/serialscope/replay/session_loader.py` validates and loads completed session metadata and structured CSV into immutable, Qt-independent replay data.
- `src/serialscope/ui/channels_widget.py` presents detected channel values in a compact scrollable view.
- `src/serialscope/ui/data_widget.py` presents the same channel updates in a larger, stable-order table.
- `src/serialscope/ui/graphs_widget.py` owns graph-channel selection and PyQtGraph presentation.
- `src/serialscope/ui/elapsed_time_axis.py` formats seconds-valued graph ticks as human-readable elapsed time without SI prefixes.
- `src/serialscope/ui/preferences_dialog.py` provides the compact confirmed appearance settings UI.
- `src/serialscope/ui/theme.py` applies consistent Light and Dark application/graph palettes centrally.
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

## Version 0.6.2 boundaries

The application performs a synchronous serial-port enumeration at startup and when Refresh is clicked. `SerialPortInfo` values cross the discovery/UI boundary, and the actual device identifier is stored as combo-box item data rather than recovered from display text. Enumeration is kept synchronous because normal port discovery is brief; this decision can be revisited if measurements demonstrate a need.

`SerialConnection` remains the sole owner of the live `serial.Serial` instance. The UI requests synchronous connect and disconnect operations and presents their state; PySerial exceptions are translated at the serial-layer boundary before reaching the UI. Opening and closing remain on the GUI thread because they are short lifecycle operations.

After connection, a `SerialReaderWorker` performs bounded reads in a dedicated `QThread`. It emits the original `bytes` chunks and never accesses widgets. `MainWindow` wires those signals to the terminal and RX counter. `TerminalWidget` uses incremental UTF-8 decoding with replacement for invalid sequences, preserving partial multibyte characters across chunks. Disconnect and window shutdown request reader termination, wait for its short-timeout read to finish, and then close the port.

For transmit, `TerminalWidget` converts command text and the selected line ending to UTF-8 `bytes`. `MainWindow` requests the write and updates the TX counter from the actual count returned. `SerialConnection` exclusively accesses PySerial and accepts raw bytes, preserving a path for future binary transmission without coupling the serial layer to text.

`TerminalWidget` caps its Qt document at 10,000 text blocks, allowing Qt to discard old display content without full-document rewrites. It follows incoming output only while the user is already at the bottom. Clearing affects visible content only. RX and TX totals remain integer bytes in `MainWindow`; status labels format them with decimal units (`1 KB = 1,000 B`, `1 MB = 1,000,000 B`). Totals reset only after a new connection opens successfully.

When raw logging is active, `MainWindow` fans each received `bytes` chunk into two independent consumers: `TerminalWidget` decodes it for display, while `RawLogger` writes it directly to a buffered binary file. The logger never receives decoded text and adds no timestamps, delimiters, or metadata. It owns the file handle and logged-byte count. Manual stop, connection loss, and application shutdown flush and close it before serial teardown.

Each `RecordingSession` creates a collision-safe directory containing `raw.log`, `data.csv`, and `session.json`. It records the application version, required user-supplied session name, local and UTC times, serial configuration, platform, elapsed duration, logged and connection RX totals, structured row count/schema details, and a lifecycle end reason. Metadata is human-readable JSON and is replaced atomically. `RawLogger` remains concerned only with exact raw bytes.

`StructuredCsvLogger` receives the same immutable `ChannelUpdate` objects already sent to the channel presentations; it never parses raw input. Its monotonic clock starts with the recording, and each accepted parser sample becomes one row with an `elapsed_s` value formatted to milliseconds. The session captures one comma, semicolon, or tab delimiter at start, records it in metadata, and keeps it fixed until close. This output choice has no relationship to input parser selection. The file starts with an `elapsed_s`-only header; before any rows exist, the first structured sample safely establishes the complete stable channel header. Missing known channels produce empty cells. Later unknown channels are omitted to keep the live file rectangular and are listed in final session metadata rather than triggering fragile in-place header rewrites. If no structured sample arrives, `data.csv` remains a valid header-only file.

The UI timer updates elapsed-time presentation approximately once per second. It neither writes metadata nor touches the raw stream. Normal stop, serial disconnect/error, logging failure, and application shutdown finalize metadata with distinct end reasons.

Incoming RX bytes fan out independently to terminal display, raw session logging, and `CsvChannelParser`. The parser keeps only an incomplete-line buffer and processes each newly completed LF or CRLF line. A header requires at least two unique, non-empty, non-numeric comma-separated names. Once detected, rows must have the same field count and every value must be a finite integer or floating-point number. Invalid lines produce no update and do not clear existing channels or affect the other RX branches.

`ChannelUpdate` carries immutable name and numeric-value tuples. `MainWindow` forwards updates to `ChannelsWidget`, which reuses value labels while the header is unchanged and provides a bounded-width scrollable view. Parser and channel state reset for a new connection and on disconnect.

Key/value lines require at least two unique, non-empty keys with finite numeric values. Whitespace around keys, values, commas, and equals signs is ignored. Integer, floating-point, negative, and scientific-notation values are supported. Updates may add channels or omit existing channels; omitted values remain visible until updated later.

JSON lines must decode as complete JSON objects before they can claim the stream. Only finite top-level integer and floating-point values become channels; strings, booleans, nulls, arrays, and nested objects are ignored. JSON updates add newly observed keys and retain omitted channels in the UI. Malformed or unsupported JSON produces no update and cannot alter terminal or raw-log data.

`SerialStreamParser` feeds all deterministic parsers only until one produces a structured update, then locks that format until connection reset. JSON is tested first because successful object decoding is conservative and prevents its comma-separated members from being mistaken for a CSV header. Key/value lines cannot qualify as CSV headers because CSV channel names containing `=` are rejected. Explicit or confirmed headerless CSV therefore coexists without delimiter guessing.

The central horizontal splitter contains a `QTabWidget` and the unchanged compact sidebar. The existing `TerminalWidget` is hosted directly in the default Terminal tab, so switching tabs does not affect RX, TX, parsing, recording, counters, or connection lifecycle. `MainWindow` forwards each parser-produced `ChannelUpdate` to the compact sidebar, larger Data table, and Graphs presentation; none owns parsing logic.

`ChannelHistory` timestamps structured updates with a monotonic clock and prunes samples older than approximately one hour. History collection continues regardless of the visible tab or paused graph presentation. `GraphsWidget` exposes each detected numeric channel once and leaves it unselected until the user opts in. Selected channels share one elapsed-seconds X axis and Y axis, use deterministic PyQtGraph colors, and appear in a legend. A 100 ms UI timer refreshes selected curves rather than redrawing for every incoming byte or structured update.

The visible X range can show the latest 10, 30, 60, 300, 600, 1,800, or 3,600 seconds without changing retained history or channel selections. Stored and plotted X values remain monotonic elapsed seconds, while a dedicated PyQtGraph axis formats ticks as seconds, minutes, or hours/minutes and disables SI prefixes. Pause freezes the displayed curves while structured updates continue entering history; Resume immediately redraws the latest window. Clear resets graph samples and elapsed origin, empties existing curves, and retains channel selectors and selections so subsequent updates begin a fresh graph. None of these controls affects serial transport, parsing, Data/sidebar values, counters, or logging.

Disconnect leaves graph history and visible series intact. A subsequent successful connection resets graph history, selectors, and curves before new data arrives, preventing data from separate devices or sessions from being mixed. Manual stop, disconnect/error, and application shutdown flush and close both session data files before metadata finalization. Malformed parser input continues into `raw.log` but produces no `data.csv` row.

`ApplicationSettings` uses Qt `QSettings`, relying on Qt's platform-native storage location, and persists only lowercase `dark` or `light` plus the structured-data delimiter. Dark is the default. Legacy `system` values and all unknown themes fall back to Dark; unknown delimiters fall back to comma. No connection or recording state is persisted. Delimiter changes are saved when the user changes that dedicated Session control; an active recording still captures and locks its delimiter at session start.

The Preferences dialog exposes exactly Dark and Light. Confirmed changes apply live through the centralized theme layer without reconstructing widgets or mutating serial, parser, recording, Data, or graph state. Both themes use centralized restrained stylesheets and a shared typography definition, control dimensions, and spacing. SerialScope does not derive its appearance from the operating-system theme, giving it consistent geometry and typography across desktop environments.

`GraphsWidget` receives a shared graph palette from the theme layer and updates its background, axes, legend, and text without clearing history or selections. Trace colors remain deterministic and independent of user customization.

Graph source measurements and display curves are deliberately separate. Every redraw starts again from the immutable live `ChannelHistory` or loaded `ReplaySession` points. The display pipeline is explicitly: measured data → optional smoothing → optional interpolation → PyQtGraph curve. Moving Average and EMA operate only on a temporary value tuple. Linear and shape-preserving PCHIP interpolation retain authoritative timestamps and measurements while generating bounded display points; the implementation adapts density to avoid expanding a curve beyond approximately 100,000 display points.

Interpolation honors the selected maximum gap. An interval larger than that threshold receives an explicit non-finite display separator, so PyQtGraph leaves a visible break rather than disguising missing acquisition time. The optional measured-point overlay plots only source samples and makes generated curves distinguishable from measurements.

Cursor inspection uses a nearest-timestamp lookup against each selected channel's actual source samples and labels the sample time explicitly. Minimum, maximum, and arithmetic average are likewise calculated only from measured samples in the visible X range, never from smoothed or interpolated points. Reset Zoom restores the current live/replay time-window range and automatic Y range without touching history, channel selection, serial state, or replay data. Pause continues freezing presentation while live source history accumulates; processing changes made while paused take effect on Resume.

Completed session replay is a separate offline data path. The loader reads `session.json` and `data.csv` once through `pathlib`, `json`, and `csv`, honors the session's fixed structured delimiter, validates elapsed timestamps and numeric values, and retains missing cells as missing samples. It does not feed recorded rows back through the live serial transport or parsers. Replay history is immutable and unbounded by the live one-hour acquisition buffer, so the complete loaded recording remains available for graph inspection. The Data view receives only the latest available value for each channel.

`MainWindow` owns the mutually exclusive live/replay presentation state and explicitly confirms before disconnecting an active serial device. An active recording blocks replay entry until the user stops it. File → Close Session clears replay-only values and histories before restoring disconnected live controls. Theme application updates presentation in place and does not reload or mutate replay data. The sidebar is vertically scrollable with no horizontal scrolling so compact-height windows retain access to session controls.

Version 0.6.2 intentionally includes no playback clock, speed controls, seeking, raw-terminal replay, session editing, export, comparison, annotations, full decimation, FFT, formulas, or database indexing.

## Planned technology direction

- Python
- PySide6 / Qt 6 for the desktop GUI
- PySerial for serial-port discovery and future serial communication
- PyQtGraph for live plotting
- pytest for automated tests
