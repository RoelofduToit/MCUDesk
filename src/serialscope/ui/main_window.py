"""The SerialScope main window and top-level UI composition."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QApplication,
    QDialog,
)

from serialscope import __version__
from serialscope.logging import (
    MultiSourceRecordingSession,
    RawLogger,
    RecordingSession,
    RecordingSessionError,
    RecordingSourceConfig,
    SessionConfig,
)
from serialscope.parsing import ChannelUpdate, SerialStreamParser
from serialscope.data import ChannelMetadataRegistry
from serialscope.replay import ReplaySession, ReplaySessionError, load_replay_session
from serialscope.settings import ApplicationSettings
from serialscope.serial import (
    SerialConnection,
    SerialConnectionError,
    SerialPortInfo,
    SerialReader,
    SerialSourceManager,
    discover_recommended_serial_ports,
)
from serialscope.ui.connection_bar import ConnectionBar
from serialscope.ui.about_dialog import AboutDialog, APPLICATION_AUTHOR, GITHUB_URL
from serialscope.ui.channel_settings_dialog import ChannelSettingsDialog
from serialscope.ui.data_widget import DataWidget
from serialscope.ui.dashboard_widget import DashboardWidget
from serialscope.ui.event_dialogs import AddEventDialog, EventListDialog
from serialscope.ui.multi_graphs_widget import MultiSourceGraphsWidget
from serialscope.ui.preferences_dialog import PreferencesDialog
from serialscope.ui.side_panel import SidePanel
from serialscope.ui.terminal_widget import TerminalWidget
from serialscope.ui.theme import apply_application_theme


def format_byte_count(byte_count: int) -> str:
    """Format bytes using decimal SI units for status presentation."""
    if byte_count < 1_000:
        return f"{byte_count} B"
    if byte_count < 1_000_000:
        return f"{byte_count / 1_000:.1f} KB"
    return f"{byte_count / 1_000_000:.1f} MB"


def format_elapsed_time(elapsed_seconds: int) -> str:
    """Format elapsed seconds as hours, minutes, and seconds."""
    hours, remainder = divmod(elapsed_seconds, 3_600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(
        self,
        port_scanner: Callable[[], list[SerialPortInfo]] | None = None,
        serial_connection: SerialConnection | None = None,
        reader_factory: Callable[[SerialConnection], SerialReader] | None = None,
        raw_logger: RawLogger | None = None,
        recording_session: RecordingSession | None = None,
        stream_parser: SerialStreamParser | None = None,
        application_settings: ApplicationSettings | None = None,
        source_manager: SerialSourceManager | None = None,
    ) -> None:
        super().__init__()
        self._port_scanner = port_scanner or discover_recommended_serial_ports
        self._serial_connection = serial_connection or SerialConnection()
        self._reader_factory = reader_factory or SerialReader
        self._serial_reader: SerialReader | None = None
        self._recording_session = recording_session or MultiSourceRecordingSession()
        self._source_manager = source_manager or SerialSourceManager(
            connection_factory=SerialConnection,
            reader_factory=self._reader_factory,
            parser_factory=SerialStreamParser,
            parent=self,
        )
        if not self._source_manager.sources:
            default_source = self._source_manager.add_source(
                "Device 1", source_id="default", connection=self._serial_connection
            )
            if stream_parser is not None:
                default_source.parser = stream_parser
        else:
            default_source = self._source_manager.sources[0]
            self._serial_connection = default_source.connection
        self._stream_parser = default_source.parser
        self._source_metadata: dict[str, ChannelMetadataRegistry] = {
            default_source.source_id: ChannelMetadataRegistry()
        }
        self._application_settings = application_settings or ApplicationSettings()
        self._selected_theme = self._application_settings.theme
        self._rx_bytes = 0
        self._tx_bytes = 0
        self._replay_session: ReplaySession | None = None
        self._channel_metadata = self._source_metadata[default_source.source_id]
        self._live_channel_metadata: dict[str, dict[str, str]] | None = None
        self._recording_timer = QTimer(self)
        self._recording_timer.setInterval(1_000)
        self._recording_timer.timeout.connect(self._update_recording_presentation)
        self.setObjectName("mainWindow")
        self.setWindowTitle("SerialScope")
        self.setMinimumSize(800, 520)
        self.resize(1120, 720)

        central_widget = QWidget()
        central_widget.setObjectName("centralWorkspace")
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(14, 14, 14, 10)
        root_layout.setSpacing(12)

        self.connection_bar = ConnectionBar()
        self.connection_bar.refresh_button.clicked.connect(self.refresh_ports)
        self.connection_bar.connect_button.clicked.connect(
            self.toggle_serial_connection
        )
        self.connection_bar.add_source_button.clicked.connect(self._add_serial_source)
        self.connection_bar.remove_source_button.clicked.connect(self._remove_serial_source)
        self.connection_bar.source_combo.currentIndexChanged.connect(
            self._selected_source_changed
        )
        self.connection_bar.source_name_input.editingFinished.connect(
            self._rename_selected_source
        )
        root_layout.addWidget(self.connection_bar)

        self.replay_banner = QLabel()
        self.replay_banner.setObjectName("replayModeBanner")
        self.replay_banner.setWordWrap(True)
        self.replay_banner.hide()
        root_layout.addWidget(self.replay_banner)

        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter.setObjectName("workspaceSplitter")
        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.setObjectName("workspaceTabs")
        self.terminal = TerminalWidget()
        self.terminal.send_button.clicked.connect(self.send_command)
        self.terminal.command_input.returnPressed.connect(self.send_command)
        self.data_widget = DataWidget()
        self.dashboard_widget = DashboardWidget(lazy=True)
        self.graphs_widget = MultiSourceGraphsWidget()
        self.workspace_tabs.addTab(self.terminal, "Terminal")
        self.workspace_tabs.addTab(self.data_widget, "Data")
        self.workspace_tabs.addTab(self.dashboard_widget, "Dashboard")
        self.workspace_tabs.addTab(self.graphs_widget, "Graphs")
        self.workspace_tabs.tabBar().moveTab(2, 3)
        self.workspace_tabs.setCurrentWidget(self.terminal)
        self.side_panel = SidePanel()
        self.side_panel.logging_button.clicked.connect(self.toggle_logging)
        self.side_panel.add_event_button.clicked.connect(self.add_event)
        self.side_panel.view_events_button.clicked.connect(self.show_events)
        self.workspace_splitter.addWidget(self.workspace_tabs)
        self.workspace_splitter.addWidget(self.side_panel)
        self.workspace_splitter.setStretchFactor(0, 1)
        self.workspace_splitter.setStretchFactor(1, 0)
        self.workspace_splitter.setSizes([820, 260])
        root_layout.addWidget(self.workspace_splitter, 1)

        self.setCentralWidget(central_widget)
        self._build_menu_bar()
        self._build_status_bar()
        delimiter_index = self.side_panel.data_delimiter_combo.findData(
            self._application_settings.structured_data_delimiter
        )
        self.side_panel.data_delimiter_combo.setCurrentIndex(
            max(0, delimiter_index)
        )
        self.side_panel.data_delimiter_combo.currentIndexChanged.connect(
            self._save_delimiter_preference
        )
        self.apply_theme(self._selected_theme)
        self._source_manager.bytes_received.connect(self._handle_source_bytes)
        self._source_manager.structured_update.connect(self._handle_source_update)
        self._source_manager.source_state_changed.connect(self._source_state_changed)
        self._source_manager.source_failed.connect(self._handle_source_failure)
        self._refresh_source_selectors()
        self.refresh_ports()

    @property
    def selected_theme(self) -> str:
        return self._selected_theme

    def apply_theme(self, theme: str) -> None:
        """Apply a theme live without changing application state."""
        application = QApplication.instance()
        if application is None:
            return
        self._selected_theme = theme
        graph_palette = apply_application_theme(application, theme)
        self.graphs_widget.apply_theme(graph_palette)

    def _save_delimiter_preference(self) -> None:
        self._application_settings.set_structured_data_delimiter(
            self.side_panel.data_delimiter_combo.currentData()
        )

    def _show_preferences(self) -> None:
        dialog = PreferencesDialog(self._selected_theme, self)
        if dialog.exec() == PreferencesDialog.DialogCode.Accepted:
            self._application_settings.set_theme(dialog.selected_theme)
            self.apply_theme(dialog.selected_theme)

    def _build_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        self.open_session_action = file_menu.addAction("Open Session...")
        self.open_session_action.triggered.connect(self.open_session)
        self.close_session_action = file_menu.addAction("Close Session")
        self.close_session_action.triggered.connect(self.close_session)
        self.close_session_action.setEnabled(False)

        settings_menu = self.menuBar().addMenu("Settings")
        self.preferences_action = settings_menu.addAction("Preferences")
        self.preferences_action.triggered.connect(self._show_preferences)

        channels_menu = self.menuBar().addMenu("Channels")
        self.configure_channels_action = channels_menu.addAction(
            "Configure Channels..."
        )
        self.configure_channels_action.triggered.connect(
            self._show_channel_settings
        )

        help_menu = self.menuBar().addMenu("Help")
        self.about_action = help_menu.addAction("About SerialScope")
        self.about_action.triggered.connect(self._show_about_dialog)
        self._build_menu_information()

    def _build_menu_information(self) -> None:
        information = QWidget(self.menuBar())
        self.menu_information_widget = information
        information.setObjectName("menuApplicationInformation")
        layout = QHBoxLayout(information)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(7)

        self.menu_author_label = QLabel(APPLICATION_AUTHOR)
        self.menu_author_label.setObjectName("menuAuthorLabel")
        self.menu_author_label.setToolTip("SerialScope developer")
        layout.addWidget(self.menu_author_label)
        layout.addWidget(QLabel("|"))

        self.menu_version_label = QLabel(f"v{__version__}")
        self.menu_version_label.setObjectName("menuVersionLabel")
        self.menu_version_label.setToolTip("Installed SerialScope version")
        layout.addWidget(self.menu_version_label)
        layout.addWidget(QLabel("|"))

        self.github_updates_button = QToolButton()
        self.github_updates_button.setObjectName("githubUpdatesButton")
        self.github_updates_button.setText("GitHub / Updates")
        self.github_updates_button.setToolTip(
            "Open SerialScope on GitHub for releases and updates"
        )
        self.github_updates_button.clicked.connect(self._open_github)
        layout.addWidget(self.github_updates_button)
        self.menuBar().setCornerWidget(information, Qt.Corner.TopRightCorner)

    def _open_github(self) -> None:
        QDesktopServices.openUrl(QUrl(GITHUB_URL))

    def _show_about_dialog(self) -> None:
        AboutDialog(self).exec()

    def _show_channel_settings(self) -> None:
        dialog = ChannelSettingsDialog(self._channel_metadata, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.apply()
            self._apply_channel_metadata()

    def _apply_channel_metadata(self) -> None:
        if len(self._source_manager.sources) == 1:
            self.data_widget.set_channel_metadata(self._channel_metadata)
            self.graphs_widget.set_channel_metadata(self._channel_metadata)
            self.dashboard_widget.set_channel_metadata(self._channel_metadata)
            combined = self._channel_metadata
        else:
            combined = ChannelMetadataRegistry()
        for source_id, registry in self._source_metadata.items():
            for channel_name in registry.source_names:
                item = registry.get(channel_name)
                combined.set(
                    f"{source_id}\x1f{channel_name}",
                    item.alias or channel_name,
                    item.unit,
                    item.alarms,
                )
            if source_id in self.graphs_widget._widgets:
                self.graphs_widget.set_source_metadata(source_id, registry)
        if len(self._source_manager.sources) > 1:
            self.data_widget.set_channel_metadata(combined)
            self.dashboard_widget.set_channel_metadata(combined)
        if self._recording_session.is_recording:
            try:
                if hasattr(self._recording_session, "set_channel_metadata"):
                    self._recording_session.set_channel_metadata(
                        self._channel_metadata.snapshot()
                    )
            except RecordingSessionError as error:
                self._stop_recording("logging_error", show_error=False)
                self._show_logging_error(str(error))

    @property
    def is_replay_mode(self) -> bool:
        return self._replay_session is not None

    def open_session(self) -> None:
        """Choose and load a completed recording with explicit live-state safety."""
        if self._recording_session.is_recording:
            QMessageBox.warning(
                self,
                "Recording in progress",
                "Stop the active recording before opening a session.",
            )
            return
        if self._source_manager.connected_sources:
            response = QMessageBox.question(
                self,
                "Disconnect serial device?",
                "Opening a recorded session requires disconnecting the serial device. Disconnect now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response != QMessageBox.StandardButton.Yes:
                return
            self._source_manager.disconnect_all()

        selected = QFileDialog.getExistingDirectory(
            self, "Open recorded session"
        )
        if selected:
            self.load_session(Path(selected))

    def load_session(self, directory: Path) -> bool:
        """Load a selected directory and enter replay mode on success."""
        try:
            session = load_replay_session(directory)
        except ReplaySessionError as error:
            QMessageBox.critical(self, "Session replay error", str(error))
            return False
        self._enter_replay_mode(session)
        return True

    def close_session(self) -> None:
        """Leave replay mode and restore the disconnected live workspace."""
        if self._replay_session is None:
            return
        self._replay_session = None
        live_metadata = self._live_channel_metadata or {}
        self._live_channel_metadata = None
        self._channel_metadata.replace(live_metadata, tuple(live_metadata))
        self.replay_banner.clear()
        self.replay_banner.hide()
        self.connection_bar.setEnabled(True)
        self.close_session_action.setEnabled(False)
        for source_id in tuple(self.graphs_widget._widgets):
            if source_id not in {source.source_id for source in self._source_manager.sources}:
                self.graphs_widget.remove_source(source_id)
        self._refresh_source_selectors()
        self._reset_channels(reset_graphs=True)
        self.side_panel.set_events(())
        self.graphs_widget.set_events(())
        self._apply_channel_metadata()
        self.side_panel.set_connected(False)
        self.workspace_tabs.setCurrentWidget(self.terminal)

    def _enter_replay_mode(self, session: ReplaySession) -> None:
        self._live_channel_metadata = self._channel_metadata.snapshot()
        self._replay_session = session
        replay_metadata = session.metadata.get("channels", {})
        if not isinstance(replay_metadata, dict):
            replay_metadata = {}
        self._channel_metadata.replace(replay_metadata, session.channel_names)
        metadata = session.metadata
        details = [f"Replay Mode — {session.name}"]
        serial_metadata = metadata.get("serial", {})
        if not isinstance(serial_metadata, dict):
            serial_metadata = {}
        device = (
            serial_metadata.get("device")
            or metadata.get("serial_port")
            or metadata.get("device")
        )
        baud = serial_metadata.get("baud_rate") or metadata.get("baud_rate")
        if device:
            details.append(f"{device}{f' @ {baud}' if baud else ''}")
        duration = metadata.get("elapsed_seconds") or metadata.get(
            "elapsed_duration_seconds"
        )
        if duration is not None:
            details.append(f"Duration: {duration} s")
        self.replay_banner.setText("  |  ".join(details))
        self.replay_banner.setToolTip(self._replay_metadata_text(session))
        self.replay_banner.show()
        self.connection_bar.setEnabled(False)
        self.side_panel.set_connected(False)
        self.side_panel.channels_widget.load_replay(session)
        self.data_widget.reset()
        self.dashboard_widget.reset()
        legacy_replay = (
            len(session.sources) == 1
            and session.sources[0].source_id == "legacy_source"
        )
        if legacy_replay:
            self.data_widget.load_replay(session)
            self.dashboard_widget.load_replay(session)
            self.graphs_widget.load_replay(session)
        for source in (() if legacy_replay else session.sources):
            values = source.latest_values
            update = ChannelUpdate(
                source.channel_names,
                tuple(values.get(name, 0) for name in source.channel_names),
                False,
            )
            self.data_widget.update_source(source.source_id, source.display_name, update)
            self.dashboard_widget.update_source(source.source_id, source.display_name, update)
            metadata = source.metadata.get("channels", {})
            registry = ChannelMetadataRegistry()
            registry.replace(
                metadata if isinstance(metadata, dict) else {}, source.channel_names
            )
            self._source_metadata[source.source_id] = registry
        if not legacy_replay:
            self.graphs_widget.load_multi_replay(session)
        self.side_panel.set_events(session.events)
        self.graphs_widget.set_events(session.events)
        self._apply_channel_metadata()
        self.workspace_tabs.setCurrentWidget(self.data_widget)
        self.close_session_action.setEnabled(True)

    @staticmethod
    def _replay_metadata_text(session: ReplaySession) -> str:
        metadata = session.metadata
        serial_metadata = metadata.get("serial", {})
        if not isinstance(serial_metadata, dict):
            serial_metadata = {}
        fields = (
            ("Session", session.name),
            ("Started", metadata.get("recording_start_local")),
            ("Ended", metadata.get("recording_end_local")),
            (
                "Duration",
                metadata.get("elapsed_seconds")
                or metadata.get("elapsed_duration_seconds"),
            ),
            (
                "Port",
                serial_metadata.get("device")
                or metadata.get("serial_port")
                or metadata.get("device"),
            ),
            (
                "Baud",
                serial_metadata.get("baud_rate") or metadata.get("baud_rate"),
            ),
            ("SerialScope", metadata.get("serialscope_version")),
            ("Delimiter", repr(metadata.get("structured_data_delimiter", ","))),
            ("Rows", metadata.get("structured_row_count", len(session.samples))),
        )
        return "\n".join(f"{label}: {value}" for label, value in fields if value is not None)

    def refresh_ports(self) -> None:
        """Refresh the connection bar with currently available ports."""
        self.connection_bar.set_ports(self._port_scanner())

    @property
    def _selected_source_id(self) -> str:
        value = self.connection_bar.source_combo.currentData()
        return str(value) if value is not None else self._source_manager.sources[0].source_id

    @property
    def _selected_source(self):
        return self._source_manager.get(self._selected_source_id)

    def _refresh_source_selectors(self) -> None:
        selected = self._selected_source_id if self.connection_bar.source_combo.count() else None
        sources = tuple(
            (source.source_id, source.display_name) for source in self._source_manager.sources
        )
        combo = self.connection_bar.source_combo
        combo.blockSignals(True)
        combo.clear()
        for source_id, name in sources:
            combo.addItem(name, source_id)
        combo.setCurrentIndex(max(0, combo.findData(selected)))
        combo.blockSignals(False)
        self.terminal.set_sources(sources)
        for source_id, name in sources:
            self.graphs_widget.ensure_source(source_id, name)
            self._source_metadata.setdefault(source_id, ChannelMetadataRegistry())
        count = len(sources)
        self.connection_bar.set_source_count(count)
        self.data_widget.set_source_count(count)
        self.dashboard_widget.set_source_count(count)
        self._selected_source_changed()

    def _add_serial_source(self) -> None:
        if self._recording_session.is_recording:
            self._show_connection_error("Stop recording before adding another device.")
            return
        source = self._source_manager.add_source()
        self.connection_bar.source_name_input.clear()
        self._refresh_source_selectors()
        self.connection_bar.source_combo.setCurrentIndex(
            self.connection_bar.source_combo.findData(source.source_id)
        )

    def _remove_serial_source(self) -> None:
        if len(self._source_manager.sources) <= 1 or self._recording_session.is_recording:
            return
        source_id = self._selected_source_id
        try:
            self._source_manager.remove_source(source_id)
        except SerialConnectionError as error:
            self._show_connection_error(str(error))
            return
        self.graphs_widget.remove_source(source_id)
        self.data_widget.remove_source(source_id)
        self.dashboard_widget.remove_source(source_id)
        self._source_metadata.pop(source_id, None)
        self._refresh_source_selectors()

    def _rename_selected_source(self) -> None:
        name = self.connection_bar.source_name_input.text().strip()
        if not name or not self._source_manager.sources:
            return
        self._source_manager.rename_source(self._selected_source_id, name)
        self._refresh_source_selectors()

    def _selected_source_changed(self) -> None:
        if not self._source_manager.sources or self.connection_bar.source_combo.currentData() is None:
            return
        source = self._selected_source
        self.connection_bar.source_name_input.setText(source.display_name)
        self._serial_connection = source.connection
        self._serial_reader = source.reader
        self._stream_parser = source.parser
        self._channel_metadata = self._source_metadata[source.source_id]
        self.connection_bar.set_connected(source.is_connected)
        self.connection_bar.port_combo.setEnabled(not source.is_connected)
        if source.port:
            index = next(
                (
                    index
                    for index in range(self.connection_bar.port_combo.count())
                    if getattr(self.connection_bar.port_combo.itemData(index), "device", None)
                    == source.port
                ),
                -1,
            )
            if index >= 0:
                self.connection_bar.port_combo.setCurrentIndex(index)
        self.connection_bar.baud_combo.setCurrentText(str(source.baud_rate))
        self.terminal.source_combo.setCurrentIndex(
            self.terminal.source_combo.findData(source.source_id)
        )
        self.graphs_widget.source_combo.setCurrentIndex(
            self.graphs_widget.source_combo.findData(source.source_id)
        )
        self.terminal.set_connected(source.is_connected)
        self.side_panel.set_connected(bool(self._source_manager.connected_sources))
        self._rx_bytes, self._tx_bytes = source.rx_bytes, source.tx_bytes
        self._update_counter_labels()

    def toggle_serial_connection(self) -> None:
        """Connect or disconnect according to the current service state."""
        if self._selected_source.is_connected:
            self._disconnect_serial_port()
        else:
            self._connect_serial_port()

    def _connect_serial_port(self) -> None:
        if (
            self._recording_session.is_recording
            and isinstance(self._recording_session, MultiSourceRecordingSession)
        ):
            self._show_connection_error(
                "Stop recording before connecting another device."
            )
            return
        port = self.connection_bar.selected_port
        if port is None:
            self._show_connection_error("Select a serial port before connecting.")
            self.connection_bar.set_connection_state("error")
            return

        baud_rate = int(self.connection_bar.baud_combo.currentText())
        try:
            self._source_manager.connect(self._selected_source_id, port.device, baud_rate)
        except SerialConnectionError as error:
            self.connection_bar.set_connection_state("error")
            self._show_connection_error(str(error))
            return

        if (
            self._selected_source.display_name.startswith("Device ")
            and port.description
            and port.description not in {port.device, "n/a"}
        ):
            self._source_manager.rename_source(
                self._selected_source_id, port.description
            )
            self._refresh_source_selectors()

        self._reset_session_counters()
        self._reset_channels(reset_graphs=True)
        self.connection_bar.set_connected(True)
        self.terminal.set_connected(True)
        self.side_panel.set_connected(True)
        self.terminal.command_input.setFocus()
        self.terminal.reset_stream_decoder()
        self._serial_reader = self._selected_source.reader

    def _start_serial_reader(self) -> None:
        self._serial_reader = self._reader_factory(self._serial_connection)
        self._serial_reader.bytes_received.connect(self._handle_received_bytes)
        self._serial_reader.failed.connect(self._handle_reader_failure)
        self._serial_reader.start()

    def _stop_serial_reader(self) -> None:
        reader = self._serial_reader
        self._serial_reader = None
        if reader is not None:
            reader.stop()

    def _handle_received_bytes(self, data: bytes) -> None:
        self._handle_source_bytes(self._selected_source_id, data, parse_legacy=True)

    def _handle_source_bytes(
        self, source_id: str, data: bytes, *, parse_legacy: bool = False
    ) -> None:
        source = self._source_manager.get(source_id)
        if parse_legacy:
            source.rx_bytes += len(data)
        self._rx_bytes = source.rx_bytes
        self._update_counter_labels()
        if self._recording_session.is_recording:
            try:
                if isinstance(self._recording_session, MultiSourceRecordingSession):
                    self._recording_session.write(source_id, data)
                else:
                    self._recording_session.write(data)
            except RecordingSessionError as error:
                self._handle_recording_source_failure(source_id, error)
            else:
                self._update_recording_presentation()
        if parse_legacy:
            for update in source.parser.feed(data):
                self._handle_source_update(source_id, update)
        self.terminal.append_source_bytes(source_id, data)

    def _handle_source_update(self, source_id: str, update: object) -> None:
        if not hasattr(update, "names"):
            return
        source = self._source_manager.get(source_id)
        registry = self._source_metadata[source_id]
        known_channels = registry.source_names
        registry.ensure(update.names)
        if source_id == self._selected_source_id:
            self.side_panel.channels_widget.update_channels(update)
        single_source = len(self._source_manager.sources) == 1
        if single_source:
            self.data_widget.update_channels(update)
            self.graphs_widget.update_channels(update)
            self.dashboard_widget.update_channels(update)
        else:
            self.data_widget.update_source(source_id, source.display_name, update)
            self.graphs_widget.update_source(source_id, source.display_name, update)
            self.dashboard_widget.update_source(source_id, source.display_name, update)
        if registry.source_names != known_channels and source_id == self._selected_source_id:
            self._apply_channel_metadata()
        if self._recording_session.is_recording:
            try:
                if isinstance(self._recording_session, MultiSourceRecordingSession):
                    self._recording_session.write_structured(source_id, update)
                else:
                    self._recording_session.write_structured(update)
            except RecordingSessionError as error:
                self._handle_recording_source_failure(source_id, error)

    def _handle_recording_source_failure(
        self, source_id: str, error: RecordingSessionError
    ) -> None:
        """Stop only the logger that failed, preserving healthy peer sources."""
        if isinstance(self._recording_session, MultiSourceRecordingSession):
            try:
                self._recording_session.stop_source(source_id, "logging_error")
            except RecordingSessionError:
                # The original write error is the most actionable message; the
                # logger has already released its resources before this point.
                pass
            if not self._recording_session.active_source_ids:
                self._stop_recording("logging_error", show_error=False)
            else:
                self._update_recording_presentation()
        else:
            self._stop_recording("logging_error", show_error=False)
        self.side_panel.set_connected(bool(self._source_manager.connected_sources))
        self._show_logging_error(str(error))

    def _handle_reader_failure(self, message: str) -> None:
        self._handle_source_failure(self._selected_source_id, message)

    def _source_state_changed(self, source_id: str, state: str) -> None:
        if source_id == self._selected_source_id:
            self.connection_bar.set_connection_state(state)
            source = self._source_manager.get(source_id)
            self.terminal.set_connected(source.is_connected)
            self._rx_bytes, self._tx_bytes = source.rx_bytes, source.tx_bytes
            self._update_counter_labels()
        self.side_panel.set_connected(bool(self._source_manager.connected_sources))

    def _handle_source_failure(self, source_id: str, message: str) -> None:
        if self._recording_session.is_recording:
            if isinstance(self._recording_session, MultiSourceRecordingSession):
                try:
                    self._recording_session.stop_source(
                        source_id, "serial_disconnected"
                    )
                except RecordingSessionError as error:
                    self._show_logging_error(str(error))
                if not self._recording_session.active_source_ids:
                    self._stop_recording("serial_disconnected")
                else:
                    self._update_recording_presentation()
            else:
                self._stop_recording("serial_disconnected")
        if source_id == self._selected_source_id:
            self.connection_bar.set_connection_state("error")
            self.terminal.set_connected(False)
            if len(self._source_manager.sources) == 1:
                self._reset_channels()
        self.side_panel.set_connected(bool(self._source_manager.connected_sources))
        self._show_connection_error(message)

    def send_command(self) -> None:
        """Encode and transmit the current command through the serial layer."""
        source_id = self.terminal.selected_source_id or self._selected_source_id
        source = self._source_manager.get(source_id)
        if not source.is_connected:
            return

        data = self.terminal.command_bytes()
        try:
            written = self._source_manager.write(source_id, data)
        except SerialConnectionError as error:
            try:
                self._source_manager.disconnect(source_id)
            except SerialConnectionError:
                pass
            self.connection_bar.set_connection_state("error")
            self._show_connection_error(str(error))
            return

        self._tx_bytes = source.tx_bytes
        self._update_counter_labels()
        self.terminal.command_input.clear()
        self.terminal.command_input.setFocus()

    def _reset_session_counters(self) -> None:
        self._rx_bytes = 0
        self._tx_bytes = 0
        self._update_counter_labels()

    def _reset_channels(self, reset_graphs: bool = False) -> None:
        self._stream_parser.reset()
        self.side_panel.channels_widget.reset()
        self.data_widget.reset()
        if reset_graphs:
            self.graphs_widget.reset()
            self.dashboard_widget.reset()

    def _update_counter_labels(self) -> None:
        self.rx_counter.setText(f"RX: {format_byte_count(self._rx_bytes)}")
        self.tx_counter.setText(f"TX: {format_byte_count(self._tx_bytes)}")

    def toggle_logging(self) -> None:
        """Start or stop a raw RX recording session."""
        if self._recording_session.is_recording:
            self._stop_recording("normal")
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        connected_sources = self._source_manager.connected_sources
        if not connected_sources:
            return

        session_name = self.side_panel.session_name_input.text()
        if not session_name.strip():
            QMessageBox.warning(
                self,
                "Session name required",
                "Enter a session name before starting a recording.",
            )
            self.side_panel.session_name_input.setFocus()
            return

        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "Choose recording session location",
        )
        if not selected_directory:
            return

        try:
            if isinstance(self._recording_session, MultiSourceRecordingSession):
                configs = tuple(
                    RecordingSourceConfig(
                        source.source_id,
                        source.display_name,
                        source.port or "",
                        source.baud_rate,
                        self._source_metadata[source.source_id].snapshot(),
                    )
                    for source in connected_sources
                )
                self._recording_session.start(
                    Path(selected_directory),
                    session_name,
                    configs,
                    delimiter=self.side_panel.data_delimiter_combo.currentData(),
                    line_ending=self.terminal.line_ending_combo.currentText(),
                )
            else:
                source = self._selected_source
                config = SessionConfig(
                    session_name=session_name,
                    device=source.port or "",
                    baud_rate=source.baud_rate,
                    line_ending=self.terminal.line_ending_combo.currentText(),
                    structured_data_delimiter=(
                        self.side_panel.data_delimiter_combo.currentData()
                    ),
                    channels=self._channel_metadata.snapshot(),
                )
                self._recording_session.start(Path(selected_directory), config)
        except RecordingSessionError as error:
            self._update_recording_presentation()
            self._show_logging_error(str(error))
            return

        self._recording_timer.start()
        self.side_panel.set_events(())
        self.graphs_widget.set_events(())
        self._update_recording_presentation()
        self.side_panel.set_connected(True)

    def _stop_recording(self, end_reason: str, show_error: bool = True) -> None:
        try:
            if isinstance(self._recording_session, MultiSourceRecordingSession):
                self._recording_session.stop(
                    end_reason,
                    {
                        source.source_id: source.rx_bytes
                        for source in self._source_manager.sources
                    },
                )
            else:
                self._recording_session.stop(end_reason, self._rx_bytes)
        except RecordingSessionError as error:
            if show_error:
                self._show_logging_error(str(error))
        finally:
            self._recording_timer.stop()
            self._update_recording_presentation()
            self.side_panel.set_connected(bool(self._source_manager.connected_sources))

    def _update_recording_presentation(self) -> None:
        self.side_panel.set_logging_state(
            self._recording_session.is_recording,
            self._recording_session.display_name,
            format_byte_count(self._recording_session.bytes_written),
            format_elapsed_time(self._recording_session.elapsed_seconds),
            self._recording_session.event_logging_available,
        )
        self.side_panel.set_events(self._recording_session.events)

    def add_event(self) -> None:
        """Capture a parent-session timestamp before asking for annotation text."""
        if not self._recording_session.event_logging_available:
            return
        try:
            elapsed_s = self._recording_session.elapsed_now()
        except RecordingSessionError as error:
            self._show_event_error(str(error))
            return
        dialog = AddEventDialog(elapsed_s, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.event_text:
            return
        try:
            self._recording_session.add_event(elapsed_s, dialog.event_text)
        except RecordingSessionError as error:
            self._update_recording_presentation()
            self._show_event_error(str(error))
            return
        self.side_panel.set_events(self._recording_session.events)
        self.graphs_widget.set_events(self._recording_session.events)

    def show_events(self) -> None:
        if self.side_panel.events:
            EventListDialog(self.side_panel.events, self).exec()

    def _return_to_disconnected_state(self, end_reason: str) -> None:
        self._stop_recording(end_reason)
        self._stop_serial_reader()
        try:
            self._serial_connection.disconnect()
        except SerialConnectionError:
            pass
        self.connection_bar.set_connected(False)
        self.terminal.set_connected(False)
        self.side_panel.set_connected(False)
        self._reset_channels()

    def _disconnect_serial_port(self) -> None:
        source_id = self._selected_source_id
        if self._recording_session.is_recording:
            if isinstance(self._recording_session, MultiSourceRecordingSession):
                try:
                    self._recording_session.stop_source(
                        source_id, "serial_disconnected"
                    )
                except RecordingSessionError as error:
                    self._show_logging_error(str(error))
                if not self._recording_session.active_source_ids:
                    self._stop_recording("serial_disconnected")
            else:
                self._stop_recording("serial_disconnected")
        try:
            self._source_manager.disconnect(source_id)
        except SerialConnectionError as error:
            self.connection_bar.set_connection_state("error")
            self.terminal.set_connected(False)
            self.side_panel.set_connected(False)
            self._reset_channels()
            self._show_connection_error(str(error))
            return

        self.connection_bar.set_connected(False)
        self.terminal.set_connected(False)
        self.side_panel.set_connected(bool(self._source_manager.connected_sources))
        if len(self._source_manager.sources) == 1:
            self._reset_channels()

    def _show_connection_error(self, message: str) -> None:
        QMessageBox.critical(self, "Serial connection error", message)

    def _show_logging_error(self, message: str) -> None:
        QMessageBox.critical(self, "Recording error", message)

    def _show_event_error(self, message: str) -> None:
        QMessageBox.critical(self, "Event logging error", message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Release an open serial port before the window is destroyed."""
        if self._recording_session.is_recording:
            response = QMessageBox.question(
                self,
                "Recording in progress",
                "A recording is active. Stop recording and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._stop_recording("application_closed", show_error=False)
        self._source_manager.disconnect_all()
        for graph in self.graphs_widget._widgets.values():
            graph._refresh_timer.stop()
        event.accept()

    def _build_status_bar(self) -> None:
        status = self.statusBar()
        status.setObjectName("applicationStatusBar")

        counters = QWidget()
        counters.setObjectName("statusCounters")
        counter_layout = QHBoxLayout(counters)
        counter_layout.setContentsMargins(0, 0, 8, 0)
        counter_layout.setSpacing(18)

        self.rx_counter = QLabel("RX: 0 B")
        self.rx_counter.setObjectName("rxCounter")
        counter_layout.addWidget(self.rx_counter)

        self.tx_counter = QLabel("TX: 0 B")
        self.tx_counter.setObjectName("txCounter")
        counter_layout.addWidget(self.tx_counter)
        status.addPermanentWidget(counters)
