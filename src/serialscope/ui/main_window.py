"""The MCUDesk main window and top-level UI composition."""

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

from serialscope import PRODUCT_NAME, __version__
from serialscope.logging import (
    MultiSourceRecordingSession,
    RawLogger,
    RecordingSession,
    RecordingSessionError,
    RecordingSourceConfig,
    SessionConfig,
    find_interrupted_recordings,
    is_interrupted_recording,
)
from serialscope.diagnostics import DiagnosticsHub
from serialscope.modbus.model import (
    PROTOCOL_MODBUS_RTU,
    ModbusRtuConfigurationError,
)
from serialscope.parsing import ChannelUpdate, ParserConfiguration, SerialStreamParser
from serialscope.data import (
    CalculatedChannelStore,
    CalculatedChannelStoreError,
    ChannelMetadataRegistry,
    evaluate_calculated_channels,
)
from serialscope.profiles import (
    DeviceIdentity,
    DeviceMatchStatus,
    DeviceProfile,
    ProfileStore,
    ProfileStoreError,
    SerialSettings,
    match_device_profile,
)
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
from serialscope.ui.diagnostics_dialog import DiagnosticsDialog
from serialscope.ui.modbus_device_dialog import ModbusDeviceDialog
from serialscope.ui.parser_configuration_dialog import ParserConfigurationDialog
from serialscope.ui.preferences_dialog import PreferencesDialog
from serialscope.ui.export_data_dialog import ExportDataDialog
from serialscope.ui.graph_export import (
    GraphExportError,
    default_graph_export_filename,
    export_plot_item,
    resolve_graph_export_path,
)
from serialscope.export import (
    CURRENT_WINDOW,
    DataExportError,
    build_export_table,
    default_data_export_filename,
    write_export_csv,
)
from serialscope.ui.profile_dialogs import ProfileNameDialog
from serialscope.ui.recovery_dialog import InterruptedRecordingDialog
from serialscope.ui.side_panel import SidePanel
from serialscope.ui.terminal_widget import TerminalWidget
from serialscope.ui.theme import apply_application_theme
from serialscope.ui.update_controller import UpdateController


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
        profile_store: ProfileStore | None = None,
        calculated_store: CalculatedChannelStore | None = None,
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
        self._diagnostics = DiagnosticsHub(self._application_settings.diagnostics_settings)
        self._source_manager.set_diagnostics(self._diagnostics)
        self._diagnostics_dialog: DiagnosticsDialog | None = None
        self._replay_diagnostics: dict[str, object] | None = None
        self._update_controller = UpdateController(
            self,
            self._application_settings,
            lambda: self._recording_session.is_recording,
        )
        self._profile_store = profile_store or ProfileStore()
        self._calculated_store = calculated_store or CalculatedChannelStore()
        self._calculated_errors: dict[str, dict[str, str]] = {}
        for source in self._source_manager.sources:
            registry = self._source_metadata.setdefault(
                source.source_id, ChannelMetadataRegistry()
            )
            for channel in self._calculated_store.for_source(source.source_id):
                existing = registry.get(channel.name)
                registry.set(
                    channel.name, existing.alias, channel.unit or existing.unit, existing.alarms
                )
        self._source_profiles: dict[str, str | None] = {
            source.source_id: None for source in self._source_manager.sources
        }
        self._selected_theme = self._application_settings.theme
        self._rx_bytes = 0
        self._tx_bytes = 0
        self._replay_session: ReplaySession | None = None
        self._channel_metadata = self._source_metadata[default_source.source_id]
        self._live_channel_metadata: dict[str, dict[str, str]] | None = None
        self._recording_timer = QTimer(self)
        self._recording_timer.setInterval(1_000)
        self._recording_timer.timeout.connect(self._on_recording_timer)
        self._shutting_down = False
        self._manual_disconnect = False
        self._reconnect_source_id: str | None = None
        self._reconnect_attempts = 0
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._attempt_reconnect)
        self.setObjectName("mainWindow")
        self.setWindowTitle(PRODUCT_NAME)
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
        self.connection_bar.profile_combo.currentIndexChanged.connect(
            self._profile_selection_changed
        )
        self.connection_bar.save_profile_action.triggered.connect(
            self._save_current_profile
        )
        self.connection_bar.update_profile_action.triggered.connect(
            self._update_current_profile
        )
        self.connection_bar.rename_profile_action.triggered.connect(
            self._rename_current_profile
        )
        self.connection_bar.delete_profile_action.triggered.connect(
            self._delete_current_profile
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
        self.terminal.line_ending_combo.currentTextChanged.connect(
            self._line_ending_changed
        )
        self.terminal.source_combo.currentIndexChanged.connect(
            self._terminal_source_changed
        )
        self.data_widget = DataWidget()
        self.dashboard_widget = DashboardWidget(lazy=True)
        self.dashboard_widget.set_numeric_display_style(
            self._application_settings.dashboard_numeric_style
        )
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
        self.workspace_splitter.setCollapsible(1, False)
        self.workspace_splitter.setSizes([760, 320])
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
        QTimer.singleShot(0, self._offer_interrupted_recording_recovery)
        if self._profile_store.load_error:
            self.connection_bar.set_profile_controls_enabled(False)
            self.connection_bar.set_profile_status("Unavailable")
            QTimer.singleShot(
                0,
                lambda: QMessageBox.warning(
                    self,
                    "Device Profiles unavailable",
                    self._profile_store.load_error or "Device Profiles are unavailable.",
                ),
            )

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
        self.dashboard_widget.apply_theme(theme)

    def _save_delimiter_preference(self) -> None:
        self._application_settings.set_structured_data_delimiter(
            self.side_panel.data_delimiter_combo.currentData()
        )

    def _show_preferences(self) -> None:
        dialog = PreferencesDialog(
            self._selected_theme,
            self,
            automatically_check_for_updates=(
                self._application_settings.automatically_check_for_updates
            ),
            dashboard_numeric_style=self._application_settings.dashboard_numeric_style,
        )
        if dialog.exec() == PreferencesDialog.DialogCode.Accepted:
            self._application_settings.set_theme(dialog.selected_theme)
            self._application_settings.set_automatically_check_for_updates(
                dialog.automatically_check_for_updates
            )
            self._application_settings.set_dashboard_numeric_style(
                dialog.dashboard_numeric_style
            )
            self.dashboard_widget.set_numeric_display_style(
                dialog.dashboard_numeric_style
            )
            self.apply_theme(dialog.selected_theme)

    def _show_parser_configuration(self) -> None:
        source = self._selected_source
        if source.is_modbus:
            QMessageBox.information(
                self,
                "Parser Configuration",
                "Parser Configuration applies to serial-stream sources.\n"
                "Modbus RTU devices use register mapping instead.",
            )
            return
        recording = self._recording_session.is_recording
        dialog = ParserConfigurationDialog(
            source.parser.configuration,
            recent_sample=self.terminal.recent_lines(source.source_id),
            apply_enabled=not recording,
            apply_disabled_reason=(
                "Stop recording before changing parser configuration."
                if recording
                else ""
            ),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if self._recording_session.is_recording:
            QMessageBox.warning(
                self,
                "Parser Configuration",
                "Stop recording before changing parser configuration.",
            )
            return
        self._apply_parser_configuration(dialog.configuration())

    def _apply_parser_configuration(self, configuration: ParserConfiguration) -> None:
        source = self._selected_source
        self._source_manager.apply_parser_configuration(
            source.source_id, configuration
        )
        profile_id = self._source_profiles.get(source.source_id)
        if profile_id is None:
            return
        try:
            self._profile_store.update(profile_id, **self._current_profile_values())
        except ProfileStoreError as error:
            self._show_profile_error(str(error))

    def _show_diagnostics(self) -> None:
        if self._diagnostics_dialog is not None:
            self._diagnostics_dialog.reload_sources()
            self._diagnostics_dialog.show()
            self._diagnostics_dialog.raise_()
            return
        dialog = DiagnosticsDialog(
            self._diagnostics,
            lambda: tuple(
                (source.source_id, source.display_name)
                for source in self._source_manager.sources
            ),
            replay_diagnostics=self._replay_diagnostics,
            on_settings_changed=self._application_settings.set_diagnostics_settings,
            parent=self,
        )
        self._diagnostics_dialog = dialog
        dialog.finished.connect(lambda _result: self._timer_cleanup_diagnostics())
        dialog.show()

    def _timer_cleanup_diagnostics(self) -> None:
        self._diagnostics_dialog = None

    def _show_modbus_devices(self) -> None:
        source = self._selected_source
        occupied = {
            item.port: item.display_name
            for item in self._source_manager.connected_sources
            if item.port
        }
        dialog = ModbusDeviceDialog(
            profiles=self._profile_store.profiles,
            ports=self._available_ports(),
            configuration=source.modbus_config,
            selected_profile_id=self._source_profiles.get(source.source_id),
            selected_port=source.port or (
                self.connection_bar.selected_port.device
                if self.connection_bar.selected_port is not None
                else None
            ),
            occupied_ports=occupied,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            configuration = dialog.configuration()
        except ModbusRtuConfigurationError as error:
            self._show_profile_error(str(error))
            return
        if source.is_connected:
            self._show_connection_error(
                "Disconnect this device before applying Modbus configuration."
            )
            return
        try:
            self._source_manager.apply_modbus_configuration(
                source.source_id, configuration
            )
            self._apply_modbus_channel_units(source.source_id, configuration)
            profile_id = dialog.selected_profile_id()
            values = self._current_profile_values()
            values["protocol"] = PROTOCOL_MODBUS_RTU
            values["modbus"] = configuration
            values["serial"] = SerialSettings(
                baud_rate=configuration.connection.baud_rate,
                line_ending=source.line_ending,
            )
            values["last_port"] = dialog.selected_port() or source.port
            if profile_id is None:
                name_dialog = ProfileNameDialog("Save Modbus Profile", parent=self)
                if name_dialog.exec() != QDialog.DialogCode.Accepted:
                    self._refresh_source_selectors()
                    return
                profile = self._profile_store.create(
                    name_dialog.profile_name, **values
                )
                profile_id = profile.profile_id
            else:
                self._profile_store.update(profile_id, **values)
            self._source_profiles[source.source_id] = profile_id
            profile = self._profile_store.get(profile_id)
            if not source.display_name.startswith("Device "):
                pass
            else:
                self._source_manager.rename_source(source.source_id, profile.name)
            if dialog.connect_requested:
                port = dialog.selected_port()
                if port is None:
                    raise SerialConnectionError("Select a serial port before connecting.")
                self._source_manager.connect(
                    source.source_id, port, configuration.connection.baud_rate
                )
                self.connection_bar.set_connected(True)
                self.side_panel.set_connected(True)
        except (ProfileStoreError, SerialConnectionError, ModbusRtuConfigurationError) as error:
            self._show_connection_error(str(error))
        self._refresh_source_selectors()

    def _apply_modbus_channel_units(
        self, source_id: str, configuration
    ) -> None:
        registry = self._source_metadata[source_id]
        names = tuple(item.name for item in configuration.enabled_registers)
        registry.ensure(names)
        for register in configuration.enabled_registers:
            existing = registry.get(register.name)
            if register.unit and not existing.unit:
                registry.set(
                    register.name, existing.alias, register.unit, existing.alarms
                )
        self._channel_metadata = registry
        self._apply_channel_metadata()

    def _build_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        self.open_session_action = file_menu.addAction("Open Session...")
        self.open_session_action.triggered.connect(self.open_session)
        self.close_session_action = file_menu.addAction("Close Session")
        self.close_session_action.triggered.connect(self.close_session)
        self.close_session_action.setEnabled(False)
        file_menu.addSeparator()
        export_menu = file_menu.addMenu("Export")
        self.export_selected_data_action = export_menu.addAction("Selected Data...")
        self.export_selected_data_action.triggered.connect(self._export_selected_data)
        self.export_current_graph_action = export_menu.addAction("Current Graph...")
        self.export_current_graph_action.triggered.connect(self._export_current_graph)

        settings_menu = self.menuBar().addMenu("Settings")
        self.preferences_action = settings_menu.addAction("Preferences")
        self.preferences_action.triggered.connect(self._show_preferences)
        self.parser_configuration_action = settings_menu.addAction(
            "Parser Configuration..."
        )
        self.parser_configuration_action.triggered.connect(
            self._show_parser_configuration
        )
        self.modbus_devices_action = settings_menu.addAction("Modbus Devices...")
        self.modbus_devices_action.triggered.connect(self._show_modbus_devices)

        tools_menu = self.menuBar().addMenu("Tools")
        self.diagnostics_action = tools_menu.addAction("Diagnostics...")
        self.diagnostics_action.triggered.connect(self._show_diagnostics)

        channels_menu = self.menuBar().addMenu("Channels")
        self.configure_channels_action = channels_menu.addAction(
            "Configure Channels..."
        )
        self.configure_channels_action.triggered.connect(
            self._show_channel_settings
        )

        help_menu = self.menuBar().addMenu("Help")
        self.check_updates_action = help_menu.addAction("Check for Updates...")
        self.check_updates_action.triggered.connect(
            self._update_controller.check_manually
        )
        help_menu.addSeparator()
        self.about_action = help_menu.addAction(f"About {PRODUCT_NAME}")
        self.about_action.triggered.connect(self._show_about_dialog)
        self.github_action = help_menu.addAction("GitHub")
        self.github_action.triggered.connect(self._open_github)
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
        self.menu_author_label.setToolTip(f"{PRODUCT_NAME} developer")
        layout.addWidget(self.menu_author_label)
        layout.addWidget(QLabel("|"))

        self.menu_version_label = QLabel(f"v{__version__}")
        self.menu_version_label.setObjectName("menuVersionLabel")
        self.menu_version_label.setToolTip(f"Installed {PRODUCT_NAME} version")
        layout.addWidget(self.menu_version_label)
        layout.addWidget(QLabel("|"))

        self.github_updates_button = QToolButton()
        self.github_updates_button.setObjectName("githubUpdatesButton")
        self.github_updates_button.setText("GitHub / Updates")
        self.github_updates_button.setToolTip(
            f"Open {PRODUCT_NAME} on GitHub for releases and updates"
        )
        self.github_updates_button.clicked.connect(self._open_github)
        layout.addWidget(self.github_updates_button)
        self.menuBar().setCornerWidget(information, Qt.Corner.TopRightCorner)

    def _open_github(self) -> None:
        QDesktopServices.openUrl(QUrl(GITHUB_URL))

    def _show_about_dialog(self) -> None:
        AboutDialog(self).exec()

    def check_for_updates_automatically(self) -> bool:
        """Start the non-blocking daily check when application settings allow it."""
        return self._update_controller.check_automatically_if_due()

    def _show_channel_settings(self) -> None:
        self._sanitize_source_metadata()
        source_id = self._selected_source_id
        calculated_names = self._calculated_store.all_names(source_id)
        physical_names = tuple(
            name
            for name in (
                *self._selected_source.latest_values,
                *self._channel_metadata.source_names,
            )
            if name not in calculated_names
        )
        dialog = ChannelSettingsDialog(
            self._channel_metadata,
            self,
            calculated_channels=self._calculated_store.for_source(source_id),
            available_names=tuple(dict.fromkeys((*physical_names, *calculated_names))),
            latest_values=self._selected_source.latest_values,
            calculated_errors=self._calculated_errors.get(source_id, {}),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        dialog.apply()
        previous = set(self._calculated_store.all_names(source_id))
        try:
            self._calculated_store.replace_source(source_id, dialog.calculated_channels)
        except CalculatedChannelStoreError as error:
            QMessageBox.warning(self, "Calculated channels", str(error))
            return
        current = set(self._calculated_store.all_names(source_id))
        registry = self._source_metadata[source_id]
        self._remove_calculated_channels(source_id, previous - current)
        for channel in dialog.calculated_channels:
            existing = registry.get(channel.name)
            registry.set(channel.name, existing.alias, channel.unit, existing.alarms)
        self._apply_channel_metadata()
        self._refresh_calculated_channels(source_id)

    def _sanitize_source_metadata(self) -> None:
        """Keep per-source registries on parser names only."""
        for registry in self._source_metadata.values():
            registry.discard_composite_identities()

    def _apply_channel_metadata(self) -> None:
        self._sanitize_source_metadata()
        if len(self._source_manager.sources) == 1:
            self.data_widget.set_channel_metadata(self._channel_metadata)
            self.graphs_widget.set_channel_metadata(self._channel_metadata)
            self.dashboard_widget.set_channel_metadata(self._channel_metadata)
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
            self.data_widget.set_channel_metadata(combined)
            self.dashboard_widget.set_channel_metadata(combined)
        for source_id, registry in self._source_metadata.items():
            if source_id in self.graphs_widget._widgets:
                self.graphs_widget.set_source_metadata(source_id, registry)
        self._mark_calculated_selectors()
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
        self._replay_diagnostics = None
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
        self._update_profile_control_state()

    def _enter_replay_mode(self, session: ReplaySession) -> None:
        self._live_channel_metadata = self._channel_metadata.snapshot()
        self._replay_session = session
        diagnostics = session.metadata.get("diagnostics")
        self._replay_diagnostics = diagnostics if isinstance(diagnostics, dict) else None
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
        self._update_profile_control_state()

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
            (PRODUCT_NAME, metadata.get("serialscope_version")),
            ("Delimiter", repr(metadata.get("structured_data_delimiter", ","))),
            ("Rows", metadata.get("structured_row_count", len(session.samples))),
        )
        return "\n".join(f"{label}: {value}" for label, value in fields if value is not None)

    def refresh_ports(self) -> None:
        """Refresh the connection bar with currently available ports."""
        self.connection_bar.set_ports(self._port_scanner())
        self._update_profile_match()

    def _available_ports(self) -> tuple[SerialPortInfo, ...]:
        return tuple(
            port
            for index in range(self.connection_bar.port_combo.count())
            if isinstance(
                (port := self.connection_bar.port_combo.itemData(index)),
                SerialPortInfo,
            )
        )

    def _refresh_profile_selector(self) -> None:
        selected_id = self._source_profiles.get(self._selected_source_id)
        self.connection_bar.set_profiles(
            tuple(
                (profile.profile_id, profile.name)
                for profile in self._profile_store.profiles
            ),
            selected_id,
        )
        self._update_profile_match()
        self._update_profile_control_state()

    def _profile_selection_changed(self) -> None:
        profile_id = self.connection_bar.selected_profile_id
        if profile_id is None:
            self._source_profiles[self._selected_source_id] = None
            self.connection_bar.set_profile_status("")
            self.connection_bar.update_profile_action_state()
            return
        if not self._profile_change_is_safe():
            self._refresh_profile_selector()
            return
        try:
            profile = self._profile_store.get(profile_id)
        except ProfileStoreError as error:
            self._show_profile_error(str(error))
            self._refresh_profile_selector()
            return
        self._source_profiles[self._selected_source_id] = profile.profile_id
        self._apply_profile(profile)
        self._update_profile_match(profile)
        self.connection_bar.update_profile_action_state()

    def _profile_change_is_safe(self) -> bool:
        if self._recording_session.is_recording:
            self._show_profile_error("Stop recording before changing Device Profiles.")
            return False
        if self._selected_source.is_connected:
            self._show_profile_error(
                "Disconnect this device before changing its Device Profile."
            )
            return False
        return True

    def _apply_profile(self, profile: DeviceProfile) -> None:
        source = self._selected_source
        if profile.protocol == PROTOCOL_MODBUS_RTU and profile.modbus is not None:
            self._source_manager.apply_modbus_configuration(
                source.source_id, profile.modbus
            )
            source.baud_rate = profile.modbus.connection.baud_rate
            self.connection_bar.baud_combo.setCurrentText(str(source.baud_rate))
            self._apply_modbus_channel_units(source.source_id, profile.modbus)
        else:
            if source.is_modbus:
                self._source_manager.apply_serial_stream_protocol(source.source_id)
            source.baud_rate = profile.serial.baud_rate
            source.line_ending = profile.serial.line_ending
            source.parser.apply_configuration(profile.parser_config)
            self.connection_bar.baud_combo.setCurrentText(str(profile.serial.baud_rate))
            self.terminal.line_ending_combo.blockSignals(True)
            self.terminal.line_ending_combo.setCurrentText(profile.serial.line_ending)
            self.terminal.line_ending_combo.blockSignals(False)
        registry = self._source_metadata[source.source_id]
        registry.replace(
            profile.channels,
            registry.source_names,
            retain_missing=True,
        )
        self._channel_metadata = registry
        self._apply_channel_metadata()
        self.terminal.set_modbus_mode(source.is_modbus)

    def _update_profile_match(self, profile: DeviceProfile | None = None) -> None:
        profile_id = self._source_profiles.get(self._selected_source_id)
        if profile is None and profile_id is not None:
            try:
                profile = self._profile_store.get(profile_id)
            except ProfileStoreError:
                profile = None
        if profile is None:
            self.connection_bar.set_profile_status("")
            return
        match = match_device_profile(profile, self._available_ports())
        labels = {
            DeviceMatchStatus.EXACT: "Detected",
            DeviceMatchStatus.LIKELY: "Likely",
            DeviceMatchStatus.AMBIGUOUS: "Choose port",
            DeviceMatchStatus.NOT_FOUND: "Not detected",
        }
        tooltip = {
            DeviceMatchStatus.AMBIGUOUS: (
                "Multiple devices match this profile; select the intended port manually."
            ),
            DeviceMatchStatus.NOT_FOUND: "No matching serial device is currently available.",
        }.get(match.status, "Matching serial device detected.")
        self.connection_bar.set_profile_status(labels[match.status], tooltip)
        if match.status in {
            DeviceMatchStatus.AMBIGUOUS,
            DeviceMatchStatus.NOT_FOUND,
        }:
            self.connection_bar.port_combo.setCurrentIndex(-1)
            return
        if match.port is not None:
            index = next(
                (
                    index
                    for index in range(self.connection_bar.port_combo.count())
                    if getattr(
                        self.connection_bar.port_combo.itemData(index), "device", None
                    )
                    == match.port.device
                ),
                -1,
            )
            if index >= 0:
                self.connection_bar.port_combo.setCurrentIndex(index)

    def _current_profile_values(self) -> dict[str, object]:
        source = self._selected_source
        port = self.connection_bar.selected_port
        identity = DeviceIdentity(
            vid=port.vid if port else None,
            pid=port.pid if port else None,
            serial_number=port.serial_number if port else None,
            manufacturer=port.manufacturer if port else None,
            product=port.product if port else None,
            location=port.location if port else None,
            hwid=port.hwid if port else None,
        )
        return {
            "serial": SerialSettings(
                baud_rate=int(self.connection_bar.baud_combo.currentText()),
                line_ending=source.line_ending,
            ),
            "parser": source.parser.configuration.mode,
            "parser_config": source.parser.configuration,
            "device_identity": identity,
            "last_port": port.device if port else source.port,
            "channels": self._source_metadata[source.source_id].snapshot(),
            "protocol": source.protocol,
            "modbus": source.modbus_config,
        }

    def _profile_reference(self, source_id: str) -> tuple[str | None, str | None]:
        profile_id = self._source_profiles.get(source_id)
        if profile_id is None:
            return None, None
        try:
            return profile_id, self._profile_store.get(profile_id).name
        except ProfileStoreError:
            return None, None

    def _save_current_profile(self) -> None:
        if not self._profile_change_is_safe():
            return
        dialog = ProfileNameDialog("Save Device Profile", parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            profile = self._profile_store.create(
                dialog.profile_name, **self._current_profile_values()
            )
        except ProfileStoreError as error:
            self._show_profile_error(str(error))
            return
        self._source_profiles[self._selected_source_id] = profile.profile_id
        self._refresh_profile_selector()

    def _update_current_profile(self) -> None:
        profile_id = self._source_profiles.get(self._selected_source_id)
        if profile_id is None or not self._profile_change_is_safe():
            return
        profile = self._profile_store.get(profile_id)
        response = QMessageBox.question(
            self,
            "Update Device Profile",
            f'Update "{profile.name}" with the current device settings?',
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if response != QMessageBox.StandardButton.Ok:
            return
        try:
            self._profile_store.update(profile_id, **self._current_profile_values())
        except ProfileStoreError as error:
            self._show_profile_error(str(error))
            return
        self._refresh_profile_selector()

    def _rename_current_profile(self) -> None:
        profile_id = self._source_profiles.get(self._selected_source_id)
        if profile_id is None or not self._profile_change_is_safe():
            return
        profile = self._profile_store.get(profile_id)
        dialog = ProfileNameDialog(
            "Rename Device Profile", profile.name, "Rename", self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._profile_store.rename(profile_id, dialog.profile_name)
        except ProfileStoreError as error:
            self._show_profile_error(str(error))
            return
        self._refresh_profile_selector()

    def _delete_current_profile(self) -> None:
        profile_id = self._source_profiles.get(self._selected_source_id)
        if profile_id is None or not self._profile_change_is_safe():
            return
        profile = self._profile_store.get(profile_id)
        response = QMessageBox.question(
            self,
            "Delete Device Profile",
            f'Delete device profile "{profile.name}"?\n\n'
            "This removes the saved profile only. It does not delete recordings.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if response != QMessageBox.StandardButton.Ok:
            return
        try:
            self._profile_store.delete(profile_id)
        except ProfileStoreError as error:
            self._show_profile_error(str(error))
            return
        for source_id, active_id in tuple(self._source_profiles.items()):
            if active_id == profile_id:
                self._source_profiles[source_id] = None
        self._refresh_profile_selector()

    def _line_ending_changed(self, value: str) -> None:
        if not self._source_manager.sources:
            return
        source_id = self.terminal.selected_source_id or self._selected_source_id
        self._source_manager.get(source_id).line_ending = value

    def _update_profile_control_state(self) -> None:
        enabled = (
            self._profile_store.load_error is None
            and not self._recording_session.is_recording
            and not self._selected_source.is_connected
            and not self.is_replay_mode
        )
        self.connection_bar.set_profile_controls_enabled(enabled)

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
            self._source_profiles.setdefault(source_id, None)
        count = len(sources)
        self.connection_bar.set_source_count(count)
        self.data_widget.set_source_count(count)
        self.dashboard_widget.set_source_count(count)
        self._selected_source_changed()
        if self._diagnostics_dialog is not None:
            self._diagnostics_dialog.reload_sources()

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
        self._source_profiles.pop(source_id, None)
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
        self.terminal.set_modbus_mode(source.is_modbus)
        self.terminal.set_connected(source.is_connected and not source.is_modbus)
        self.side_panel.set_connected(bool(self._source_manager.connected_sources))
        self._rx_bytes, self._tx_bytes = source.rx_bytes, source.tx_bytes
        self._update_counter_labels()
        self._refresh_profile_selector()

    def _terminal_source_changed(self) -> None:
        source_id = self.terminal.selected_source_id
        if source_id is None:
            return
        self.terminal.line_ending_combo.blockSignals(True)
        self.terminal.line_ending_combo.setCurrentText(
            self._source_manager.get(source_id).line_ending
        )
        self.terminal.line_ending_combo.blockSignals(False)

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
        self._manual_disconnect = False
        self._cancel_reconnect()
        self.connection_bar.set_connection_state("connecting")
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
        self.terminal.set_modbus_mode(self._selected_source.is_modbus)
        self.terminal.set_connected(
            True if not self._selected_source.is_modbus else False
        )
        self.side_panel.set_connected(True)
        if not self._selected_source.is_modbus:
            self.terminal.command_input.setFocus()
            self.terminal.reset_stream_decoder()
        self._serial_reader = self._selected_source.reader
        self._update_profile_control_state()

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
        if self._shutting_down:
            return
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
            except Exception as error:
                self._handle_recording_source_failure(
                    source_id, RecordingSessionError(str(error))
                )
            else:
                self._update_recording_presentation()
        if parse_legacy:
            try:
                for update in source.parser.feed(data):
                    self._handle_source_update(source_id, update)
            except Exception:
                pass
        self.terminal.append_source_bytes(source_id, data)

    def _handle_source_update(self, source_id: str, update: object) -> None:
        if not hasattr(update, "names"):
            return
        source = self._source_manager.get(source_id)
        source.latest_values.update(
            zip(update.names, update.values, strict=True)
        )
        registry = self._source_metadata[source_id]
        known_channels = registry.source_names
        registry.ensure(update.names)
        if source.modbus_config is not None:
            for register in source.modbus_config.enabled_registers:
                existing = registry.get(register.name)
                if register.unit and not existing.unit:
                    registry.set(
                        register.name, existing.alias, register.unit, existing.alarms
                    )
        calculated = self._evaluate_calculated_channels(source_id)
        if calculated is not None:
            registry.ensure(calculated.names)
        presented = self._merge_calculated_update(source_id, update, calculated)
        self._present_structured_update(source_id, presented)
        self._apply_calculated_evaluation_status(source_id)
        if registry.source_names != known_channels:
            self._apply_channel_metadata()
        logged = presented
        if self._recording_session.is_recording:
            try:
                if isinstance(self._recording_session, MultiSourceRecordingSession):
                    self._recording_session.write_structured(source_id, logged)
                else:
                    self._recording_session.write_structured(logged)
            except RecordingSessionError as error:
                self._handle_recording_source_failure(source_id, error)
            except Exception as error:
                self._handle_recording_source_failure(
                    source_id, RecordingSessionError(str(error))
                )

    def _merge_calculated_update(
        self,
        source_id: str,
        physical: ChannelUpdate,
        calculated: ChannelUpdate | None,
    ) -> ChannelUpdate:
        """Keep calculated names in the live set instead of replacing it."""
        if not self._calculated_store.for_source(source_id):
            return physical
        if calculated is None:
            return ChannelUpdate(physical.names, physical.values, False)
        return ChannelUpdate(
            (*physical.names, *calculated.names),
            (*physical.values, *calculated.values),
            False,
        )

    def _view_channel_name(self, source_id: str, name: str) -> str:
        if len(self._source_manager.sources) == 1:
            return name
        return f"{source_id}\x1f{name}"

    def _apply_calculated_evaluation_status(self, source_id: str) -> None:
        """Show UNKNOWN when a calculated channel did not produce this sample."""
        for name in self._calculated_errors.get(source_id, {}):
            view_name = self._view_channel_name(source_id, name)
            self.dashboard_widget.mark_value_unavailable(view_name)
            self.data_widget.mark_value_unavailable(view_name)

    def _remove_calculated_channels(self, source_id: str, names: set[str]) -> None:
        """Drop deleted calculated definitions from live views and metadata."""
        registry = self._source_metadata[source_id]
        source = self._source_manager.get(source_id)
        for name in names:
            registry.discard(name)
            source.latest_values.pop(name, None)
            view_name = self._view_channel_name(source_id, name)
            self.dashboard_widget.remove_channel(view_name)
            self.data_widget.remove_channel(view_name)
            self.graphs_widget.remove_channel(view_name)

    def _evaluate_calculated_channels(self, source_id: str) -> ChannelUpdate | None:
        channels = self._calculated_store.for_source(source_id)
        if not channels:
            self._calculated_errors[source_id] = {}
            return None
        source = self._source_manager.get(source_id)
        result = evaluate_calculated_channels(channels, source.latest_values)
        self._calculated_errors[source_id] = dict(result.errors)
        if result.update is not None:
            source.latest_values.update(
                zip(result.update.names, result.update.values, strict=True)
            )
        return result.update

    def _refresh_calculated_channels(self, source_id: str) -> None:
        """Recompute calculated channels after definitions or metadata change."""
        update = self._evaluate_calculated_channels(source_id)
        if update is not None:
            self._source_metadata[source_id].ensure(update.names)
            self._present_structured_update(source_id, update)
        self._apply_calculated_evaluation_status(source_id)

    def _present_structured_update(self, source_id: str, update: ChannelUpdate) -> None:
        source = self._source_manager.get(source_id)
        if source_id == self._selected_source_id:
            self.side_panel.channels_widget.update_channels(update)
        if len(self._source_manager.sources) == 1:
            self.data_widget.update_channels(update)
            self.graphs_widget.update_channels(update)
            self.dashboard_widget.update_channels(update)
            return
        self.data_widget.update_source(source_id, source.display_name, update)
        self.graphs_widget.update_source(source_id, source.display_name, update)
        self.dashboard_widget.update_source(source_id, source.display_name, update)

    def _mark_calculated_selectors(self) -> None:
        calculated_by_source = {
            source.source_id: set(self._calculated_store.all_names(source.source_id))
            for source in self._source_manager.sources
        }
        for source_id, widget in getattr(self.graphs_widget, "_widgets", {}).items():
            names = calculated_by_source.get(source_id, set())
            for key in widget.channel_selector.toggles:
                widget.channel_selector.set_channel_calculated(key, key in names)
        if not getattr(self.dashboard_widget, "_built", False):
            return
        for key in self.dashboard_widget.channel_selector.toggles:
            if "\x1f" in key:
                source_id, _separator, channel_name = key.partition("\x1f")
                names = calculated_by_source.get(source_id, set())
                calculated = channel_name in names
            else:
                calculated = any(key in names for names in calculated_by_source.values())
            self.dashboard_widget.channel_selector.set_channel_calculated(
                key, calculated
            )

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
        self._update_profile_control_state()

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
            self.connection_bar.set_connection_state("lost")
            self.terminal.set_connected(False)
            if len(self._source_manager.sources) == 1:
                self._reset_channels()
        self.side_panel.set_connected(bool(self._source_manager.connected_sources))
        self._update_profile_control_state()
        self._show_connection_error(message)
        if not self._manual_disconnect and not self._shutting_down:
            self._schedule_reconnect(source_id)

    def send_command(self) -> None:
        """Encode and transmit the current command through the serial layer."""
        source_id = self.terminal.selected_source_id or self._selected_source_id
        source = self._source_manager.get(source_id)
        if not source.is_connected or source.is_modbus:
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
                        source_id=source.source_id,
                        display_name=source.display_name,
                        device=source.port or "",
                        baud_rate=source.baud_rate,
                        channels=self._source_metadata[source.source_id].snapshot(),
                        profile_id=self._profile_reference(source.source_id)[0],
                        profile_name=self._profile_reference(source.source_id)[1],
                        line_ending=source.line_ending,
                        parser_config=source.parser.configuration.to_dict(),
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
                profile_id, profile_name = self._profile_reference(source.source_id)
                config = SessionConfig(
                    session_name=session_name,
                    device=source.port or "",
                    baud_rate=source.baud_rate,
                    line_ending=self.terminal.line_ending_combo.currentText(),
                    structured_data_delimiter=(
                        self.side_panel.data_delimiter_combo.currentData()
                    ),
                    channels=self._channel_metadata.snapshot(),
                    profile_id=profile_id,
                    profile_name=profile_name,
                    parser_config=source.parser.configuration.to_dict(),
                )
                self._recording_session.start(Path(selected_directory), config)
        except RecordingSessionError as error:
            self._update_recording_presentation()
            self._show_logging_error(str(error))
            return

        self._diagnostics.begin_recording()
        self._recording_timer.start()
        self.side_panel.set_events(())
        self.graphs_widget.set_events(())
        if self._recording_session.directory is not None:
            self._application_settings.add_in_progress_session(
                self._recording_session.directory
            )
        self._update_recording_presentation()
        self.side_panel.set_connected(True)

    def _stop_recording(self, end_reason: str, show_error: bool = True) -> None:
        directory = self._recording_session.directory
        diagnostics = self._diagnostics.end_recording()
        try:
            if isinstance(self._recording_session, MultiSourceRecordingSession):
                self._recording_session.stop(
                    end_reason,
                    {
                        source.source_id: source.rx_bytes
                        for source in self._source_manager.sources
                    },
                    diagnostics=diagnostics,
                )
            else:
                self._recording_session.stop(
                    end_reason, self._rx_bytes, diagnostics=diagnostics
                )
        except RecordingSessionError as error:
            if show_error:
                self._show_logging_error(str(error))
        finally:
            if directory is not None:
                self._application_settings.remove_in_progress_session(directory)
            self._recording_timer.stop()
            self._update_recording_presentation()
            self.side_panel.set_connected(bool(self._source_manager.connected_sources))

    def _on_recording_timer(self) -> None:
        if self._recording_session.is_recording:
            try:
                self._recording_session.flush()
            except RecordingSessionError as error:
                source_id = self._selected_source_id
                self._handle_recording_source_failure(source_id, error)
                return
        self._update_recording_presentation()

    def _update_recording_presentation(self) -> None:
        self.side_panel.set_logging_state(
            self._recording_session.is_recording,
            self._recording_session.display_name,
            format_byte_count(self._recording_session.bytes_written),
            format_elapsed_time(self._recording_session.elapsed_seconds),
            self._recording_session.event_logging_available,
        )
        self.side_panel.set_events(self._recording_session.events)
        self._update_profile_control_state()

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
        self._update_profile_control_state()

    def _disconnect_serial_port(self) -> None:
        self._manual_disconnect = True
        self._cancel_reconnect()
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
            self._update_profile_control_state()
            return

        self.connection_bar.set_connected(False)
        self.terminal.set_connected(False)
        self.side_panel.set_connected(bool(self._source_manager.connected_sources))
        if len(self._source_manager.sources) == 1:
            self._reset_channels()
        self._update_profile_control_state()

    def _show_connection_error(self, message: str) -> None:
        QMessageBox.critical(self, "Serial connection error", message)

    def _show_logging_error(self, message: str) -> None:
        QMessageBox.critical(self, "Recording error", message)

    def _show_profile_error(self, message: str) -> None:
        QMessageBox.warning(self, "Device Profile", message)

    def _show_event_error(self, message: str) -> None:
        QMessageBox.critical(self, "Event logging error", message)

    def _export_selected_data(self) -> None:
        series = self.graphs_widget.selected_measurement_series()
        if not series:
            QMessageBox.information(
                self,
                "Export Selected Data",
                "Select at least one graph channel before exporting data.",
            )
            return
        dialog = ExportDataDialog(
            self,
            live_history_limited=self._replay_session is None,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        time_window = None
        if dialog.range_mode == CURRENT_WINDOW:
            if not self.graphs_widget._widgets:
                QMessageBox.information(
                    self,
                    "Export Selected Data",
                    "The current graph time window is not available.",
                )
                return
            time_window = self.graphs_widget.visible_time_range()
        selected, _filter = QFileDialog.getSaveFileName(
            self,
            "Export Selected Data",
            default_data_export_filename(),
            "CSV (*.csv)",
        )
        if not selected:
            return
        path = Path(selected)
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        try:
            table = build_export_table(
                series, range_mode=dialog.range_mode, time_window=time_window
            )
            write_export_csv(path, table)
        except DataExportError as error:
            QMessageBox.critical(self, "Export Selected Data", str(error))
            return
        self.statusBar().showMessage(
            f"Exported {table.channel_count} channels and {table.row_count:,} data rows.",
            8_000,
        )

    def _export_current_graph(self) -> None:
        if (
            not self.graphs_widget._widgets
            or not self.graphs_widget.selected_channels
        ):
            QMessageBox.information(
                self,
                "Export Current Graph",
                "No graph channels are currently selected.",
            )
            return
        selected, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Current Graph",
            default_graph_export_filename(".png"),
            "PNG (*.png);;SVG (*.svg)",
        )
        if not selected:
            return
        try:
            path = resolve_graph_export_path(Path(selected), selected_filter)
            export_plot_item(self.graphs_widget.plot_widget.plotItem, path)
        except GraphExportError as error:
            QMessageBox.critical(self, "Export Current Graph", str(error))
            return
        self.statusBar().showMessage(f"Exported graph to {path.name}.", 8_000)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Stop recording cleanly, then release serial workers and ports."""
        if self._recording_session.is_recording:
            response = QMessageBox.question(
                self,
                "Recording in progress",
                "Recording is currently active. Stop recording and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if response != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._shutting_down = True
        self._cancel_reconnect()
        for source in tuple(self._source_manager.sources):
            reader = source.reader
            if reader is not None:
                reader.stop()
                source.reader = None
        self._stop_recording("application_closed", show_error=False)
        self._update_controller.shutdown()
        if self._diagnostics_dialog is not None:
            self._diagnostics_dialog.close()
            self._diagnostics_dialog = None
        self._source_manager.disconnect_all()
        for graph in self.graphs_widget._widgets.values():
            graph._refresh_timer.stop()
        event.accept()

    def _offer_interrupted_recording_recovery(self) -> None:
        """Offer recovery for sessions that never finalized."""
        registered = tuple(
            Path(path) for path in self._application_settings.in_progress_sessions()
        )
        for path in registered:
            if not is_interrupted_recording(path):
                self._application_settings.remove_in_progress_session(path)
        found = find_interrupted_recordings(
            tuple(Path(path) for path in self._application_settings.in_progress_sessions())
        )
        if not found:
            return
        dialog = InterruptedRecordingDialog(found, self)
        dialog.exec()
        for path in tuple(self._application_settings.in_progress_sessions()):
            if not is_interrupted_recording(Path(path)):
                self._application_settings.remove_in_progress_session(Path(path))

    def _cancel_reconnect(self) -> None:
        self._reconnect_timer.stop()
        self._reconnect_attempts = 0
        self._reconnect_source_id = None

    def _schedule_reconnect(self, source_id: str) -> None:
        """Retry an unexpected disconnect; never auto-restart recording."""
        if self._shutting_down or self._manual_disconnect:
            return
        if self._reconnect_attempts >= 5:
            if source_id == self._selected_source_id:
                self.connection_bar.set_connection_state("error")
            return
        self._reconnect_source_id = source_id
        delay = min(800 * (2 ** self._reconnect_attempts), 8_000)
        if source_id == self._selected_source_id:
            self.connection_bar.set_connection_state("lost")
        self._reconnect_timer.start(delay)

    def _attempt_reconnect(self) -> None:
        source_id = self._reconnect_source_id
        if source_id is None or self._shutting_down or self._manual_disconnect:
            return
        source = self._source_manager.get(source_id)
        if source.is_connected or not source.port:
            self._cancel_reconnect()
            return
        if source_id == self._selected_source_id:
            self.connection_bar.set_connection_state("reconnecting")
        try:
            self._source_manager.connect(source_id, source.port, source.baud_rate)
        except SerialConnectionError:
            self._reconnect_attempts += 1
            self._schedule_reconnect(source_id)
            return
        self._cancel_reconnect()
        if source_id == self._selected_source_id:
            self.connection_bar.set_connected(True)
            self.terminal.set_modbus_mode(source.is_modbus)
            self.terminal.set_connected(source.is_connected and not source.is_modbus)
            if not source.is_modbus:
                self.terminal.reset_stream_decoder()
            self._serial_reader = source.reader
        self.side_panel.set_connected(True)
        self._update_profile_control_state()

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
