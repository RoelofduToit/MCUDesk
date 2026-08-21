# MCUDesk Architecture

## Purpose

MCUDesk is a professional cross-platform desktop application for Windows and Linux. It provides a modern serial terminal, data logging, intelligent parsing, device profiles, live engineering graphs, and later engineering and data-analysis features. The internal Python package remains `serialscope`.

Phase 0 through v0.2 established the terminal, serial, and raw recording foundations. Version 0.3 added deterministic structured channel detection, version 0.4 introduced a tabbed workspace and graphs, version 0.6 added replay, graph inspection, and Dashboard, version 0.7 added channel metadata and alarms, version 0.8 introduced independent multi-device acquisition, version 0.9 hardened lifecycle, packaging, and experiment events, version 0.10 added persistent per-device profiles, and version 0.11 adds verified application updates.

## Current structure

- `main.py` is a minimal source-checkout launcher.
- `src/serialscope/app.py` owns the Qt application lifecycle.
- `src/serialscope/settings.py` validates and persists small user preferences through `QSettings`.
- `src/serialscope/profiles/` owns Device Profile models, deterministic port matching, and versioned atomic JSON persistence.
- `src/serialscope/diagnostics/` observes source bytes, parser outcomes, and structured updates. The Tools menu opens a snapshot dialog; diagnostics never alter engineering channels.
- `src/serialscope/updates/` owns GitHub release parsing, version comparison, asynchronous checks, verified downloads, cancellation, and daily-check policy.
- `src/serialscope/serial/port_scanner.py` discovers ports through PySerial and returns Qt-independent structured metadata.
- `src/serialscope/serial/connection.py` owns the live PySerial object and its open/close lifecycle.
- `src/serialscope/serial/reader.py` runs bounded serial reads in a dedicated `QThread` and emits raw byte chunks.
- `src/serialscope/logging/raw_logger.py` owns a buffered binary log file and writes exact RX byte chunks.
- `src/serialscope/logging/structured_csv_logger.py` writes parser-produced numeric samples to rectangular UTF-8 CSV.
- `src/serialscope/logging/event_logger.py` writes sparse parent-session annotations to a dedicated UTF-8 CSV.
- `src/serialscope/logging/session.py` owns session directories, timing, metadata, and end-reason lifecycle around both loggers.
- `src/serialscope/parsing/csv_parser.py` incrementally detects simple CSV headers and emits numeric channel updates without Qt dependencies.
- `src/serialscope/parsing/key_value_parser.py` incrementally parses comma-separated numeric `key=value` lines.
- `src/serialscope/parsing/json_parser.py` incrementally parses top-level numeric values from one JSON object per line.
- `src/serialscope/parsing/stream_parser.py` deterministically selects and locks a parser for the current connection.
- `src/serialscope/data/channel_history.py` retains Qt-independent, monotonic, bounded numeric history for plotting.
- `src/serialscope/data/channel_metadata.py` retains optional aliases and units keyed by authoritative source channel names.
- `src/serialscope/data/event_marker.py` defines immutable session elapsed-time annotations with stable identities.
- `src/serialscope/data/dashboard_layout.py` owns non-overlapping source-keyed logical grid positions, free-cell assignment, moves, and swaps.
- `src/serialscope/data/engineering_units.py` defines the reusable categorized built-in unit catalogue without conversion behavior.
- `src/serialscope/data/alarm.py` validates optional limits and derives one current alarm state from a measured numeric value.
- `src/serialscope/data/graph_processing.py` performs pure display smoothing/interpolation and measured-data inspection/statistics without mutating graph history.
- `src/serialscope/replay/session_loader.py` validates and loads completed session metadata and structured CSV into immutable, Qt-independent replay data.
- `src/serialscope/ui/channels_widget.py` presents detected channel values in a compact scrollable view.
- `src/serialscope/ui/data_widget.py` presents the same channel updates in a larger, stable-order table.
- `src/serialscope/ui/dashboard_widget.py` owns Dashboard channel choices, latest values, scrolling, and responsive tile placement.
- `src/serialscope/ui/channel_tile.py` presents one channel name and formatted numeric value without owning data acquisition.
- `src/serialscope/ui/channel_settings_dialog.py` edits aliases and free-text units while keeping source names read-only.
- `src/serialscope/ui/unit_selector.py` presents nested unit-category menus, checked built-ins, No unit, and unrestricted custom-unit entry.
- `src/serialscope/ui/graphs_widget.py` owns graph-channel selection and PyQtGraph presentation.
- `src/serialscope/ui/elapsed_time_axis.py` formats seconds-valued graph ticks as human-readable elapsed time without SI prefixes.
- `src/serialscope/ui/preferences_dialog.py` provides the compact confirmed appearance settings UI.
- `src/serialscope/ui/update_controller.py` coordinates updater state and presentation without performing HTTP or package writes itself.
- `src/serialscope/ui/update_dialogs.py` presents release notes, byte progress, cancellation, and explicit installation handoff.
- `src/serialscope/ui/theme.py` applies consistent Light and Dark application/graph palettes centrally.
- `src/serialscope/ui/main_window.py` composes the top-level window and status bar.
- `src/serialscope/ui/connection_bar.py` contains the inert connection controls.
- `src/serialscope/ui/terminal_widget.py` contains the terminal display and command row.
- `src/serialscope/ui/side_panel.py` contains configuration placeholders.
- `src/serialscope/ui/event_dialogs.py` collects event text and presents the current/replayed event list.
- `src/serialscope/ui/style.py` contains the small application stylesheet.
- `tests/` contains automated tests.
- `docs/` contains project documentation and architectural decisions.

Future modules should be introduced only when their responsibilities are needed. Business and domain logic must live outside the GUI so it can be tested without constructing Qt widgets.

## Version 0.11.0 application updates

`serialscope.updates.model` is the single authority for the public
`RoelofduToit/MCUDesk` release location and package convention.
`UpdateChecker` requests only GitHub's latest stable release endpoint through
QtNetwork, normalizes leading `v` tags with `packaging.version.Version`, rejects
draft/prerelease metadata, and prefers MCUDesk-branded assets while still
accepting legacy SerialScope/`serialscope` asset names. Requests contain only
normal HTTP headers and the MCUDesk version; there are no credentials,
telemetry, or experiment/device data.

`UpdateDownloader` streams the selected asset asynchronously into Qt's
per-user cache beneath `updates/`. The incomplete filename ends in `.part` and
is removed on cancellation, HTTP/write failure, incomplete transfer, or digest
mismatch. MCUDesk requires GitHub's valid `sha256:<hex>` metadata: only a
fully flushed, size-checked, SHA-256-matching download is atomically renamed to
its final package name and offered for installation. Missing, malformed, and
unsupported digests have no bypass.

The UI controller allows checks and downloads during acquisition/recording but
blocks installation while recording remains active. It never stops logging or
disconnects hardware. Installation opens the verified package through the
desktop's default package installer; MCUDesk never invokes `sudo`, stores a
password, overwrites `/opt`, or forcibly restarts itself. Automatic checks are
enabled by default, persisted through `QSettings`, scheduled after the main
window appears, and rate-limited to approximately once per 24 hours. Automatic
failures and current-version results remain silent, while manual checks always
report a result. Closing the application aborts updater replies and cleans
partial data without unmanaged worker threads.

## Architectural rules

- Keep `main.py` small; it only starts the application.
- Keep business logic out of Qt widgets and other GUI code.
- Keep modules cohesive and interfaces between layers explicit.
- Never perform blocking serial reads on the GUI thread. Serial reader workers use a bounded read timeout and communicate with the UI using Qt signals.
- Use `pathlib.Path` for filesystem paths.
- Preserve compatibility with Windows and Linux; do not rely on platform-specific paths or shell behavior.
- Add dependencies only when a current requirement justifies them.
- Keep serial transport, parsing, logging, profiles, plotting, and persistence as separate concerns when they are introduced.

## Version 0.8.0 multi-device architecture

`SerialSourceManager` owns the runtime source collection and enforces exclusive ownership of physical port identifiers. Every `SerialSource` has a unique stable runtime `source_id`, editable display name, port and baud configuration, `SerialConnection`, `SerialReader`, `SerialStreamParser`, byte counters, and latest values. Reader signals cross the Qt thread boundary; workers never access widgets. A failure or disconnect stops only the affected source and leaves other source readers, parsers, and presentation state intact.

`ChannelKey(source_id, channel_name)` is the domain identity for a structured channel. Raw names such as `TC1` are meaningful only within their source. Metadata registries remain independent per source, so aliases, units, and alarm limits for two identically named channels cannot collide. JSON-friendly storage keys are reversible and presentation layers always retain the original source and channel components.

Parser state is never shared. Bytes from a source enter only that source's stream parser. The resulting source-aware event fans out to its terminal stream, source graph workspace, combined Data view, and combined Dashboard. Terminal RX and TX are selected by device and TX is never broadcast. Graphs uses a complete independent `GraphsWidget` per source, retaining separate history, selections, pause/clear state, processing settings, and replay data. Cross-device plotting is intentionally not implemented.

Data and Dashboard combine source-aware values for operational visibility. Dashboard layout positions are keyed by the reversible source-aware identity, allowing two `TC1` tiles from different devices. Tiles include a secondary device label and retain square geometry, alarms, aliases, engineering units, and the logical canvas drag model.

`MultiSourceRecordingSession` establishes one parent experiment directory and one common host monotonic origin. It snapshots the connected participants when recording starts; adding another source is blocked until recording stops. Each participant receives an independent raw logger and structured logger:

```text
Experiment_2026-08-13_2030/
├── session.json
├── events.csv
├── Pi_Pico/
│   ├── raw.log
│   └── data.csv
└── Arduino_Uno/
    ├── raw.log
    └── data.csv
```

Raw bytes never cross source boundaries. Structured rows use each device's actual asynchronous arrival time relative to the shared session origin; files are not synchronized or combined. `session.json` lists source IDs, names, ports, baud rates, relative file paths, channel metadata, byte totals, row counts, and lifecycle state.

Replay recognizes the `devices` list and loads each referenced structured file into an independent `ReplaySource`. Graph workspaces remain separated while Data and Dashboard can present all sources. The loader treats the earlier root-level `data.csv` format as one conceptual `legacy_source`, preserving backward compatibility without feeding replay through live parsers or serial transport.

Version 0.8.0 intentionally excludes combined graphs/CSV, device-clock synchronization, mid-recording participants, broadcast TX, automatic device matching, network sources, and protocol-specific transports.

## Version 0.9.3 experiment events

`EventMarker(event_id, elapsed_s, text)` is immutable annotation data and is never inserted into raw bytes, parser output, `ChannelUpdate`, device `data.csv`, or measured graph history. The parent recording session owns one event collection and one `EventLogger`, regardless of device count. The logger opens a header-only parent-level `events.csv` at recording start and writes UTF-8 CSV rows with the schema `elapsed_s,event_id,event`. The ID distinguishes repeated descriptions; the full-precision elapsed value is authoritative for graph placement.

The Add Event handler calls the recording session's monotonic `elapsed_now()` before constructing or opening the modal text dialog. Confirmation writes the original captured value, so typing or correction time cannot move the marker. Cancelled and empty descriptions produce no model object or CSV row. Events remain available if one device participant fails; only final parent-session stop or application shutdown closes the event logger. An event-file write failure disables further event entry and reports an error without stopping serial acquisition or device measurement logging.

All device graphs receive the same tuple of parent `EventMarker` objects and render thin theme-aware PyQtGraph vertical lines with elapsed-time/description tooltips. This presentation is rebuilt only when the event collection, replay, source workspace, or theme changes. Graph Clear does not delete session events. Replay loads the root `events.csv` without snapping its timestamps to samples; an absent file means zero events, while malformed event data follows the existing concise replay-error path.

Graph and Dashboard selection retain native `QCheckBox` multi-selection, keyboard, and accessibility behavior. Centralized Light/Dark QSS gives their indicators a compact circular filled/empty appearance with explicit hover, selected, disabled, and focus states. The selectors remain source-aware and do not alter graph or Dashboard data models.

## Version 0.10.0 Device Profiles

`DeviceProfile` is persistent reusable configuration for exactly one device, while `SerialSource` remains a runtime acquisition object and `SerialPortInfo` remains one currently discoverable operating-system endpoint. A profile has a UUID independent of its unique, trimmed display name. It stores the currently supported 8-N-1/no-flow-control serial format, baud rate, per-source TX line ending, the current `auto` parser mode, optional hardware identity hints, a last-port fallback, and channel alias/unit/alarm metadata keyed by authoritative source channel names.

`ProfileStore` keeps schema version 1 in `device_profiles.json` beneath Qt's cross-platform `AppConfigLocation`. It creates the configuration directory when needed and uses the same temporary-file, flush, `fsync`, and atomic-replace helper as session metadata. Unknown optional fields are tolerated. An invalid document or unsupported schema starts MCUDesk with zero available profiles, reports a concise warning, preserves the original file, and disables profile mutation rather than overwriting recoverable user data. Global theme/delimiter `QSettings` remain a separate responsibility.

Device matching is deterministic. A stored USB serial number, constrained by VID/PID when present, is exact even if the Linux device path changes. Without a serial number, one matching VID/PID plus available product/manufacturer hints is likely; multiple equal matches are ambiguous and leave the port unselected until the operator chooses. The remembered port is considered only when no stable hardware identity exists. Selecting a profile may select one deterministic match and restore configuration, but it never opens the port. Manual port override never rewrites identity unless the user explicitly updates the profile.

The connection bar exposes a compact `Custom`/profile selector and one actions menu. Custom preserves the original profile-free workflow. Runtime profile association is stored independently for each source and is hidden behind the existing single-device progressive disclosure. Applying or modifying profiles is disabled for an open selected source, during recording, and in replay mode. Profile application restores saved metadata, retains entries for temporarily missing firmware channels without creating live values, and gives newly observed channels default metadata.

At recording start, `session.json` may snapshot informational profile ID/name values per participating source along with the effective serial and channel configuration. Replay never reads the mutable profile store and remains fully governed by its session snapshot if a profile is renamed, changed, deleted, corrupt, or unavailable. Device Profiles never own session events and do not alter `events.csv`, `raw.log`, parser keys, or authoritative `data.csv` channel names.

## Version 0.9.1 reliability boundaries

Reader callbacks carry the identity of the exact `SerialReader` that emitted them. `SerialSourceManager` ignores queued bytes or failures from an obsolete reader after disconnect/reconnect, preventing an old worker from disconnecting a new session or duplicating updates. Connect rolls back the open serial port if reader construction or startup fails. Disconnect and read failure reset the affected parser; last displayed engineering values remain available, while a reconnect starts with a clean partial-line/parser state. One failed source does not stop peer workers.

CSV, JSON-line, and key/value parsers share a bounded incomplete-line buffer. A line larger than 1 MiB is discarded through its next newline, after which normal parsing resumes. Raw bytes are still counted, displayed through the terminal presentation path, and written unchanged when that source is recording. This protects parser memory from binary garbage or devices that never terminate a line.

Live `ChannelHistory` remains pruned to approximately one hour by monotonic time and also applies a 200,000-point per-channel emergency ceiling. The secondary ceiling prevents pathological input rates or a stalled clock from growing RAM indefinitely. It does not change timestamps or discard recording data. Replay continues to use immutable complete loaded samples and is not subject to the live-history ceiling.

Raw and structured loggers stream directly to buffered files and retain only counters, schema, and small metadata in memory. Multi-device logger startup is transactional with respect to open handles: any source startup or initial metadata failure closes every logger already opened. A fatal write failure finalizes only the affected device logger; healthy devices continue their parent experiment. Final metadata records the individual end reason. For a single v0.8-format source, legacy root-level files are hard links where supported, avoiding a second full copy of an overnight log.

Small session metadata documents are written to a sibling temporary file, flushed and `fsync`-ed, then atomically replaced. Finalization clears active lifecycle state even if metadata replacement itself fails. A confirmed application close finalizes recording with `application_closed`, stops all readers, closes serial ports, and stops graph refresh timers. The user may cancel close while a recording is active.

Replay file references are resolved beneath the selected session directory. Absolute paths, parent traversal, symlink escape, and duplicate source identifiers are rejected with a concise replay error. Large replay recordings remain loaded in memory for complete inspection; they are intentionally separate from rolling live history. Extremely large replay files may therefore still require a future indexed/on-disk model.

`serialscope.__version__` is the sole application-version value. Setuptools reads it dynamically for package metadata, while Qt application metadata, the menu bar, About dialog, and session files import the same value. The installed GUI entry point and `python -m serialscope` do not depend on the current working directory. Qt `QSettings` supplies platform-native user-writable preference storage. `serialscope.resources` resolves the authoritative application icon from either the source checkout or PyInstaller's runtime bundle without depending on the process working directory.

Acquisition and logging are never throttled for display. Graph rendering is timer-driven and presentation controls are only created for newly discovered channels. Data and Dashboard currently update numeric labels for every structured update; a future UI coalescing layer may reduce presentation work at very high rates without dropping logged samples.

## Version 0.9.2 Linux packaging

The maintained PyInstaller spec packages `src/serialscope/__main__.py`; both the bundle and `python -m serialscope` therefore converge on `serialscope.app.main()`. The one-folder output keeps Qt plugins and Python libraries inspectable under `dist/MCUDesk/`. PyInstaller's analysis and PySide6 hooks collect Qt libraries and platform plugins; normal import analysis includes MCUDesk's PyQtGraph and PySerial usage without importing optional PyQtGraph OpenGL/examples modules. The packaged
executable is named MCUDesk.

The bundle contains no README or docs. It includes `assets/icons/mcudesk.png` as runtime data beneath PyInstaller's `_internal` directory; Qt applies it at application level. User settings remain in Qt's platform-native `QSettings` location under the existing SerialScope storage identity, and session/replay locations are chosen through file dialogs. None depends on the executable directory or current working directory. The Linux spec leaves `EXE(icon=None)` because PyInstaller supports executable icon embedding only on Windows and macOS; desktop packaging installs the same PNG through a `.desktop` file and hicolor icon hierarchy.

PyInstaller is isolated in the `packaging` optional dependency group and is not a runtime dependency. Generated `build/` and `dist/` content remains ignored, while `packaging/serialscope.spec` is intentionally tracked. A private `--packaging-smoke-test` argument constructs the normal main window and exits automatically, enabling a non-interactive offscreen bundle check without creating a second startup path.

## Legacy single-device foundations through Version 0.7.2

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

The Preferences dialog exposes exactly Dark and Light. Confirmed changes apply live through the centralized theme layer without reconstructing widgets or mutating serial, parser, recording, Data, or graph state. Both themes use centralized restrained stylesheets and a shared typography definition, control dimensions, and spacing. MCUDesk does not derive its appearance from the operating-system theme, giving it consistent geometry and typography across desktop environments.

`GraphsWidget` receives a shared graph palette from the theme layer and updates its background, axes, legend, and text without clearing history or selections. Trace colors remain deterministic and independent of user customization.

Graph source measurements and display curves are deliberately separate. Every redraw starts again from the immutable live `ChannelHistory` or loaded `ReplaySession` points. The display pipeline is explicitly: measured data → optional smoothing → optional interpolation → PyQtGraph curve. Moving Average and EMA operate only on a temporary value tuple. Linear and shape-preserving PCHIP interpolation retain authoritative timestamps and measurements while generating bounded display points; the implementation adapts density to avoid expanding a curve beyond approximately 100,000 display points.

Interpolation honors the selected maximum gap. An interval larger than that threshold receives an explicit non-finite display separator, so PyQtGraph leaves a visible break rather than disguising missing acquisition time. The optional measured-point overlay plots only source samples and makes generated curves distinguishable from measurements.

Cursor inspection uses a nearest-timestamp lookup against each selected channel's actual source samples and labels the sample time explicitly. Minimum, maximum, and arithmetic average are likewise calculated only from measured samples in the visible X range, never from smoothed or interpolated points. Reset Zoom restores the current live/replay time-window range and automatic Y range without touching history, channel selection, serial state, or replay data. Pause continues freezing presentation while live source history accumulates; processing changes made while paused take effect on Resume.

Completed session replay is a separate offline data path. The loader reads `session.json` and `data.csv` once through `pathlib`, `json`, and `csv`, honors the session's fixed structured delimiter, validates elapsed timestamps and numeric values, and retains missing cells as missing samples. It does not feed recorded rows back through the live serial transport or parsers. Replay history is immutable and unbounded by the live one-hour acquisition buffer, so the complete loaded recording remains available for graph inspection. The Data view receives only the latest available value for each channel.

`MainWindow` owns the mutually exclusive live/replay presentation state and explicitly confirms before disconnecting an active serial device. An active recording blocks replay entry until the user stops it. File → Close Session clears replay-only values and histories before restoring disconnected live controls. Theme application updates presentation in place and does not reload or mutate replay data. The sidebar is vertically scrollable with no horizontal scrolling so compact-height windows retain access to session controls.

The central workspace now contains Terminal, Data, Graphs, and Dashboard tabs, with Terminal still selected initially. `MainWindow` forwards each existing immutable `ChannelUpdate` to Dashboard alongside the established Data and Graphs consumers. Dashboard owns no serial, parser, logger, or replay-loader behavior.

Dashboard channel availability is derived from structured channel names and remains unselected by default. Selection creates one reusable `ChannelTile`; subsequent samples update its value label in place. Deselection removes only that presentation and frees its logical cell without compacting other tiles. A scroll area supports large or deliberately sparse grids.

Dashboard positioning is represented by `DashboardLayout` as source channel → `GridPosition(row, column)`, never as pixel coordinates. New selections receive the first free cell; deselection frees only that cell and does not compact other tiles. Drag MIME data carries the authoritative source name, and a drop is converted to a logical cell. Empty destinations preserve gaps; occupied destinations deterministically swap tiles. Qt geometry is regenerated from the model, keeping measurements, aliases, units, alarm status, and live updates independent of drag operations.

Tiles are constrained to a 1:1 aspect ratio. The logical canvas exposes as many square columns as fit the current viewport and never rewrites existing positions. Narrow viewports retain off-screen user positions through horizontal overflow, while sparse/tall arrangements remain vertically scrollable. The model exposes a serializable snapshot for future session/profile persistence, but v0.8.0 does not persist named Dashboard layouts.

Disconnect leaves the last live Dashboard values visible without generating updates. A successful new connection resets availability, selections, and tiles before accepting the new device's structured state. Replay entry similarly replaces Dashboard state with replay channel names and final recorded values; closing replay clears that state. Dark/Light styling remains centralized and theme changes do not reconstruct tiles or alter selection/value state. Dashboard construction is deferred until it receives structured data or becomes visible, keeping unopened application windows lightweight.

Every structured channel retains its parser/device-provided source name as its authoritative identity. `ChannelMetadataRegistry` stores only optional, trimmed presentation metadata (`alias` and user-supplied `unit`) under that source key. Empty aliases fall back to the source name and empty units remain blank. Duplicate aliases are valid and cannot merge histories, selections, tiles, CSV columns, or any other source-keyed state.

Channels → Configure Channels opens a table whose source-name column is read-only. Applying changes updates existing Data rows, graph selectors/legend/cursor/statistics text, and Dashboard selectors/tiles in place. Graph history and selected series, Dashboard selections, numeric values, serial state, parsing, and recording remain intact. Units are presentation text only: MCUDesk performs no inference, conversion, calibration, or scaling.

The Unit column uses one reusable categorized catalogue covering common temperature, pressure, flow, mass, rotation/frequency, electrical, length, velocity, time, concentration/fraction, and energy units. Menus store and return the actual displayed string rather than an index or category identifier. Other → Custom accepts arbitrary Unicode engineering notation, and unknown values restored from session metadata remain custom instead of being replaced. Selecting a different unit never converts or otherwise changes a measurement.

`RecordingSession` copies the registry's non-empty presentation metadata into the small `channels` object in `session.json`, and can refresh that object when metadata changes during an active recording. `StructuredCsvLogger` continues receiving unchanged `ChannelUpdate` objects, so `data.csv` headers always use original source names. Raw serial bytes and `raw.log` remain completely independent. Replay accepts older sessions without `channels`, and when metadata exists MainWindow applies it to Data, Graphs, and Dashboard while the replay model remains source-keyed.

`AlarmLimits` is immutable presentation/configuration metadata with optional Low-Low, Low, High, and High-High values. Configured values must be finite and strictly increase in that order, even when only a subset is present. Evaluation is a pure function of one measured value and its limits: inclusive outer limits produce LOW-LOW/HIGH-HIGH before inclusive inner limits produce LOW/HIGH; finite values outside configured limits are NORMAL, while missing or non-finite values are UNKNOWN. The evaluator is independent of widgets so future hysteresis can be added without rewriting presentation code.

Channel Settings extends the existing source-keyed row with the four optional limits. Data and Dashboard retain latest numeric values and ask the shared evaluator for status after either a measurement or metadata change. Dashboard tiles expose explicit status text plus centralized `normal`, `warning`, and `alarm` theme properties; color is supplementary rather than the only signal. Data adds a Status column. Graph cursor inspection evaluates its nearest actual measured sample, while trace colors, histories, statistics, interpolation, and smoothing remain unchanged.

Configured limits serialize beneath each channel's `alarms` object in `session.json`. Replay restores them and evaluates the final/latest displayed values; older sessions and malformed legacy alarm blocks safely fall back to no limits. Alarm state itself is derived and is not written as a measurement. Raw RX, `raw.log`, parser values/names, graph source history, and `data.csv` headers/numbers remain untouched.

Version 0.7.2 intentionally includes no hysteresis, acknowledgement, alarm history, sounds, notifications, control actions, graph alarm bands, calibration, or device profiles.

## Planned technology direction

- Python
- PySide6 / Qt 6 for the desktop GUI
- PySerial for serial-port discovery and future serial communication
- PyQtGraph for live plotting
- pytest for automated tests
