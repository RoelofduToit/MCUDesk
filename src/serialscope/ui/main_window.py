"""The SerialScope main window and top-level UI composition."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QApplication,
)

from serialscope.logging import (
    RawLogger,
    RecordingSession,
    RecordingSessionError,
    SessionConfig,
)
from serialscope.parsing import SerialStreamParser
from serialscope.replay import ReplaySession, ReplaySessionError, load_replay_session
from serialscope.settings import ApplicationSettings
from serialscope.serial import (
    SerialConnection,
    SerialConnectionError,
    SerialPortInfo,
    SerialReader,
    discover_recommended_serial_ports,
)
from serialscope.ui.connection_bar import ConnectionBar
from serialscope.ui.data_widget import DataWidget
from serialscope.ui.dashboard_widget import DashboardWidget
from serialscope.ui.graphs_widget import GraphsWidget
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
    ) -> None:
        super().__init__()
        self._port_scanner = port_scanner or discover_recommended_serial_ports
        self._serial_connection = serial_connection or SerialConnection()
        self._reader_factory = reader_factory or SerialReader
        self._serial_reader: SerialReader | None = None
        self._recording_session = recording_session or RecordingSession(raw_logger)
        self._stream_parser = stream_parser or SerialStreamParser()
        self._application_settings = application_settings or ApplicationSettings()
        self._selected_theme = self._application_settings.theme
        self._rx_bytes = 0
        self._tx_bytes = 0
        self._replay_session: ReplaySession | None = None
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
        self.graphs_widget = GraphsWidget()
        self.workspace_tabs.addTab(self.terminal, "Terminal")
        self.workspace_tabs.addTab(self.data_widget, "Data")
        self.workspace_tabs.addTab(self.dashboard_widget, "Dashboard")
        self.workspace_tabs.addTab(self.graphs_widget, "Graphs")
        self.workspace_tabs.tabBar().moveTab(2, 3)
        self.workspace_tabs.setCurrentWidget(self.terminal)
        self.side_panel = SidePanel()
        self.side_panel.logging_button.clicked.connect(self.toggle_logging)
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
        if self._serial_connection.is_connected:
            response = QMessageBox.question(
                self,
                "Disconnect serial device?",
                "Opening a recorded session requires disconnecting the serial device. Disconnect now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response != QMessageBox.StandardButton.Yes:
                return
            self._disconnect_serial_port()
            if self._serial_connection.is_connected:
                return

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
        self.replay_banner.clear()
        self.replay_banner.hide()
        self.connection_bar.setEnabled(True)
        self.close_session_action.setEnabled(False)
        self._reset_channels(reset_graphs=True)
        self.side_panel.set_connected(False)
        self.workspace_tabs.setCurrentWidget(self.terminal)

    def _enter_replay_mode(self, session: ReplaySession) -> None:
        self._replay_session = session
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
        self.data_widget.load_replay(session)
        self.graphs_widget.load_replay(session)
        self.dashboard_widget.load_replay(session)
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

    def toggle_serial_connection(self) -> None:
        """Connect or disconnect according to the current service state."""
        if self._serial_connection.is_connected:
            self._disconnect_serial_port()
        else:
            self._connect_serial_port()

    def _connect_serial_port(self) -> None:
        port = self.connection_bar.selected_port
        if port is None:
            self._show_connection_error("Select a serial port before connecting.")
            self.connection_bar.set_connection_state("error")
            return

        baud_rate = int(self.connection_bar.baud_combo.currentText())
        try:
            self._serial_connection.connect(port.device, baud_rate)
        except SerialConnectionError as error:
            self.connection_bar.set_connection_state("error")
            self._show_connection_error(str(error))
            return

        self._reset_session_counters()
        self._reset_channels(reset_graphs=True)
        self.connection_bar.set_connected(True)
        self.terminal.set_connected(True)
        self.side_panel.set_connected(True)
        self.terminal.command_input.setFocus()
        self.terminal.reset_stream_decoder()
        self._start_serial_reader()

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
        self._rx_bytes += len(data)
        self._update_counter_labels()
        if self._recording_session.is_recording:
            try:
                self._recording_session.write(data)
            except RecordingSessionError as error:
                self._stop_recording("logging_error", show_error=False)
                self.side_panel.set_connected(self._serial_connection.is_connected)
                self._show_logging_error(str(error))
            else:
                self._update_recording_presentation()
        for update in self._stream_parser.feed(data):
            self.side_panel.channels_widget.update_channels(update)
            self.data_widget.update_channels(update)
            self.graphs_widget.update_channels(update)
            self.dashboard_widget.update_channels(update)
            if self._recording_session.is_recording:
                try:
                    self._recording_session.write_structured(update)
                except RecordingSessionError as error:
                    self._stop_recording("logging_error", show_error=False)
                    self.side_panel.set_connected(
                        self._serial_connection.is_connected
                    )
                    self._show_logging_error(str(error))
        self.terminal.append_bytes(data)

    def _handle_reader_failure(self, message: str) -> None:
        self._return_to_disconnected_state("serial_disconnected")
        self.connection_bar.set_connection_state("error")
        self._show_connection_error(message)

    def send_command(self) -> None:
        """Encode and transmit the current command through the serial layer."""
        if not self._serial_connection.is_connected:
            return

        data = self.terminal.command_bytes()
        try:
            written = self._serial_connection.write(data)
        except SerialConnectionError as error:
            self._return_to_disconnected_state("serial_disconnected")
            self.connection_bar.set_connection_state("error")
            self._show_connection_error(str(error))
            return

        self._tx_bytes += written
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
        if not self._serial_connection.is_connected:
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

        port = self.connection_bar.selected_port
        if port is None:
            return
        config = SessionConfig(
            session_name=session_name,
            device=port.device,
            baud_rate=int(self.connection_bar.baud_combo.currentText()),
            line_ending=self.terminal.line_ending_combo.currentText(),
            structured_data_delimiter=(
                self.side_panel.data_delimiter_combo.currentData()
            ),
        )
        try:
            self._recording_session.start(Path(selected_directory), config)
        except RecordingSessionError as error:
            self._update_recording_presentation()
            self._show_logging_error(str(error))
            return

        self._recording_timer.start()
        self._update_recording_presentation()
        self.side_panel.set_connected(True)

    def _stop_recording(self, end_reason: str, show_error: bool = True) -> None:
        try:
            self._recording_session.stop(end_reason, self._rx_bytes)
        except RecordingSessionError as error:
            if show_error:
                self._show_logging_error(str(error))
        finally:
            self._recording_timer.stop()
            self._update_recording_presentation()
            self.side_panel.set_connected(self._serial_connection.is_connected)

    def _update_recording_presentation(self) -> None:
        self.side_panel.set_logging_state(
            self._recording_session.is_recording,
            self._recording_session.display_name,
            format_byte_count(self._recording_session.bytes_written),
            format_elapsed_time(self._recording_session.elapsed_seconds),
        )

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
        self._stop_recording("serial_disconnected")
        self._stop_serial_reader()
        try:
            self._serial_connection.disconnect()
        except SerialConnectionError as error:
            self.connection_bar.set_connection_state("error")
            self.terminal.set_connected(False)
            self.side_panel.set_connected(False)
            self._reset_channels()
            self._show_connection_error(str(error))
            return

        self.connection_bar.set_connected(False)
        self.terminal.set_connected(False)
        self.side_panel.set_connected(False)
        self._reset_channels()

    def _show_connection_error(self, message: str) -> None:
        QMessageBox.critical(self, "Serial connection error", message)

    def _show_logging_error(self, message: str) -> None:
        QMessageBox.critical(self, "Raw logging error", message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Release an open serial port before the window is destroyed."""
        self._stop_recording("application_closed", show_error=False)
        self._stop_serial_reader()
        try:
            self._serial_connection.disconnect()
        except SerialConnectionError:
            pass
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
