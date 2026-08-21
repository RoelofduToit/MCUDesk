import csv
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, call

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QTabWidget,
)

from serial import SerialException

from serialscope.logging import (
    RecordingSession,
    RecordingSessionError,
    SessionConfig,
    is_interrupted_recording,
)
from serialscope.logging.recovery import IN_PROGRESS_NAME
from serialscope.settings import ApplicationSettings
from serialscope.serial import SerialConnection, SerialPortInfo
from serialscope.ui.main_window import MainWindow, format_byte_count
from serialscope.data import AlarmLimits, GridPosition


class FakeSignal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback

    def emit(self, value) -> None:
        assert self.callback is not None
        self.callback(value)


class FakeReader:
    def __init__(self, _connection: SerialConnection) -> None:
        self.bytes_received = FakeSignal()
        self.failed = FakeSignal()
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def test_main_window_has_application_title() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])

    assert window.windowTitle() == "MCUDesk"

    window.close()
    application.processEvents()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_connection_status_is_prominent_and_explicit_in_both_themes(
    theme: str,
) -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])
    window.apply_theme(theme)

    assert window.connection_bar.status_label.text() == "DISCONNECTED"
    assert (
        window.connection_bar.status_indicator.property("connectionState")
        == "disconnected"
    )
    assert "disconnected" in window.connection_bar.status_indicator.toolTip().lower()
    assert (
        window.connection_bar.status_label.minimumWidth()
        >= window.connection_bar.status_label.fontMetrics().horizontalAdvance(
            "CONNECTION ERROR"
        )
    )
    window.connection_bar.set_connection_state("connected")
    assert window.connection_bar.status_label.text() == "CONNECTED"
    assert (
        window.connection_bar.status_indicator.property("connectionState")
        == "connected"
    )
    window.connection_bar.set_connection_state("error")
    assert window.connection_bar.status_label.text() == "CONNECTION ERROR"
    assert window.connection_bar.status_indicator.property("connectionState") == "error"

    window.close()
    application.processEvents()


def test_connection_bar_does_not_clip_controls_at_normal_widths() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])
    bar = window.connection_bar
    window.resize(960, 640)
    window.show()
    application.processEvents()

    required = (
        bar.status_label,
        bar.connect_button,
        bar.port_label,
        bar.port_combo,
        bar.profile_label,
        bar.profile_combo,
        bar.baud_label,
        bar.baud_combo,
        bar.refresh_button,
    )
    bounds = bar.rect()
    for widget in required:
        assert widget.isVisibleTo(bar)
        geometry = QRect(widget.mapTo(bar, QPoint(0, 0)), widget.size())
        assert bounds.contains(geometry)
        assert geometry.width() > 8
        assert geometry.height() > 8
    assert bar.profile_status_label.isHidden()
    assert bar.status_label.text() == "DISCONNECTED"
    assert bar.connect_button.text() == "Connect"
    assert "PORT" in bar.port_label.text()
    window.resize(800, 600)
    application.processEvents()
    bounds = bar.rect()
    for widget in required:
        geometry = QRect(widget.mapTo(bar, QPoint(0, 0)), widget.size())
        assert bounds.contains(geometry)
    window.close()
    application.processEvents()


def test_main_window_restores_and_persists_delimiter_preference(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    settings_path = tmp_path / "settings.ini"
    settings = ApplicationSettings(
        QSettings(str(settings_path), QSettings.Format.IniFormat)
    )
    settings.set_structured_data_delimiter(";")
    window = MainWindow(port_scanner=lambda: [], application_settings=settings)

    assert window.side_panel.data_delimiter_combo.currentData() == ";"
    window.side_panel.data_delimiter_combo.setCurrentText("Tab")

    restored = ApplicationSettings(
        QSettings(str(settings_path), QSettings.Format.IniFormat)
    )
    assert restored.structured_data_delimiter == "\t"
    window.close()
    application.processEvents()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_theme_applies_without_resetting_live_application_state(
    tmp_path: Path,
    theme: str,
) -> None:
    application = QApplication.instance() or QApplication([])
    settings = ApplicationSettings(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    window = MainWindow(port_scanner=lambda: [], application_settings=settings)
    raw_data = b'{"A":1,"B":2}\n'
    window._handle_received_bytes(raw_data)
    window.graphs_widget.set_channel_selected("A", True)
    window.dashboard_widget.set_channel_selected("A", True)
    window.dashboard_widget.move_tile("A", GridPosition(2, 3))
    window._channel_metadata.set("A", "Signal A", "V", AlarmLimits(high=0.5))
    window._apply_channel_metadata()
    history_before = window.graphs_widget.history.points("A")
    dashboard_value_before = window.dashboard_widget.tile_value_text("A")

    window.apply_theme(theme)

    assert window.selected_theme == theme
    assert window.graphs_widget.history.points("A") == history_before
    assert window.graphs_widget.selected_channels == ("A",)
    assert window.dashboard_widget.selected_channels == ("A",)
    assert window.dashboard_widget.tile_value_text("A") == dashboard_value_before
    assert window._channel_metadata.get("A").alarms == AlarmLimits(high=0.5)
    assert window.dashboard_widget._tiles["A"].status_label.text() == "HIGH"
    assert window.dashboard_widget.tile_position("A") == GridPosition(2, 3)
    assert window.data_widget.value_text("A") == "1"
    assert window.side_panel.channels_widget.value_text("A") == "1"
    assert window.terminal.output.toPlainText() == raw_data.decode()
    assert application.styleSheet()

    window.close()
    application.processEvents()


def test_preferences_action_is_available() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])

    assert window.preferences_action.text() == "Preferences"
    assert window.parser_configuration_action.text() == "Parser Configuration..."
    assert window.modbus_devices_action.text() == "Modbus Devices..."
    assert window.diagnostics_action.text() == "Diagnostics..."
    assert window.configure_channels_action.text() == "Configure Channels..."
    assert window.check_updates_action.text() == "Check for Updates..."
    assert window.about_action.text() == "About MCUDesk"
    assert window.github_action.text() == "GitHub"

    window.close()
    application.processEvents()


def test_main_window_restores_persisted_theme(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    settings = ApplicationSettings(
        QSettings(
            str(tmp_path / "settings.ini"),
            QSettings.Format.IniFormat,
        )
    )
    settings.set_theme("dark")

    window = MainWindow(port_scanner=lambda: [], application_settings=settings)

    assert window.selected_theme == "dark"
    assert application.styleSheet()
    window.close()
    application.processEvents()


def test_light_dark_switch_preserves_typography_and_control_geometry(
    tmp_path: Path,
) -> None:
    application = QApplication.instance() or QApplication([])
    settings = ApplicationSettings(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    window = MainWindow(port_scanner=lambda: [], application_settings=settings)
    window.show()
    application.processEvents()
    controls = (
        window.connection_bar.connect_button,
        window.side_panel.session_name_input,
        window.side_panel.data_delimiter_combo,
    )

    window.apply_theme("dark")
    application.processEvents()
    dark_fonts = [control.font().toString() for control in controls]
    dark_sizes = [control.sizeHint() for control in controls]

    window.apply_theme("light")
    application.processEvents()

    assert [control.font().toString() for control in controls] == dark_fonts
    assert [control.sizeHint() for control in controls] == dark_sizes
    window.close()
    application.processEvents()


def test_main_window_constructs_ui_shell() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])

    assert window.minimumWidth() >= 800
    assert window.findChild(QComboBox, "portCombo") is not None
    assert window.findChild(QComboBox, "baudCombo").currentText() == "115200"
    assert window.findChild(QPlainTextEdit, "terminalOutput").isReadOnly()
    assert window.findChild(QLineEdit, "commandInput") is not None
    assert window.terminal.line_ending_combo.currentText() == "LF"
    assert not window.terminal.send_button.isEnabled()
    assert window.findChild(QGroupBox, "connectionSection") is not None
    assert window.findChild(QGroupBox, "channelsSection") is not None
    assert window.findChild(QGroupBox, "sessionSection") is not None
    assert window.side_panel.logging_status_dot.property("recordingState") == "inactive"
    assert window.side_panel.data_delimiter_combo.currentText() == "Comma (,)"
    assert window.side_panel.data_delimiter_combo.currentData() == ","
    assert window.rx_counter.text() == "RX: 0 B"
    assert window.tx_counter.text() == "TX: 0 B"

    window.close()
    application.processEvents()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_side_panel_has_usable_resizable_width_without_horizontal_clipping(
    theme: str,
) -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])
    window.apply_theme(theme)
    window.show()
    application.processEvents()

    panel = window.side_panel
    assert panel.minimumWidth() == 300
    initial_panel_width = window.workspace_splitter.sizes()[1]
    assert panel.minimumWidth() <= initial_panel_width <= 340
    assert window.workspace_tabs.width() > panel.width()
    assert not window.workspace_splitter.isCollapsible(1)
    assert (
        panel.scroll_area.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert (
        panel.channels_widget.scroll_area.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    for control in (
        panel.session_name_input,
        panel.data_delimiter_combo,
        panel.add_event_button,
        panel.view_events_button,
        panel.logging_button,
    ):
        assert control.width() >= control.minimumSizeHint().width()

    panel.session_name_input.setText(
        "Long-running reactor commissioning session with operator notes"
    )
    panel.set_logging_state(
        True,
        filename="Long-running reactor commissioning session with operator notes",
        byte_count="14.2 KB",
        elapsed="00:02:41",
    )
    window.resize(window.minimumSize())
    application.processEvents()

    assert panel.minimumWidth() <= panel.width() <= 340
    assert panel.scroll_area.horizontalScrollBar().maximum() == 0
    assert panel.scroll_area.verticalScrollBar().maximum() > 0
    assert panel.logging_filename_label.wordWrap()
    for control in (
        panel.session_name_input,
        panel.data_delimiter_combo,
        panel.add_event_button,
        panel.view_events_button,
        panel.logging_button,
    ):
        assert control.width() >= control.minimumSizeHint().width()

    window.resize(1120, 720)
    window.workspace_splitter.setSizes([650, 420])
    application.processEvents()
    assert panel.width() > panel.minimumWidth()

    window.close()
    application.processEvents()


def test_workspace_has_terminal_data_graphs_and_dashboard_tabs() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])

    assert isinstance(window.workspace_tabs, QTabWidget)
    assert [
        window.workspace_tabs.tabText(index)
        for index in range(window.workspace_tabs.count())
    ] == ["Terminal", "Data", "Graphs", "Dashboard"]
    assert window.workspace_tabs.currentWidget() is window.terminal
    assert window.workspace_tabs.indexOf(window.terminal) == 0
    assert window.workspace_tabs.indexOf(window.data_widget) == 1
    assert window.workspace_tabs.indexOf(window.graphs_widget) == 2
    assert window.workspace_tabs.indexOf(window.dashboard_widget) == 3

    window.close()
    application.processEvents()


def test_switching_workspace_tabs_preserves_live_channel_state() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()

    window.workspace_tabs.setCurrentWidget(window.graphs_widget)
    reader.bytes_received.emit(b"A,B\n1,2\n")
    window.dashboard_widget.set_channel_selected("A", True)
    window.workspace_tabs.setCurrentWidget(window.data_widget)

    assert window.data_widget.value_text("A") == "1"
    assert window.side_panel.channels_widget.value_text("A") == "1"
    assert window.connection_bar.status_label.text() == "CONNECTED"
    assert window.rx_counter.text() == "RX: 8 B"
    assert window.dashboard_widget.tile_value_text("A") == "1"

    reader.bytes_received.emit(b"3,4\n")
    window.workspace_tabs.setCurrentWidget(window.dashboard_widget)
    assert window.data_widget.value_text("A") == "3"
    assert window.dashboard_widget.tile_value_text("A") == "3"
    assert connection.is_connected

    window.close()
    application.processEvents()


def test_graph_history_survives_tab_changes_and_disconnect_then_resets_on_reconnect() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    readers: list[FakeReader] = []

    def reader_factory(active_connection: SerialConnection) -> FakeReader:
        reader = FakeReader(active_connection)
        readers.append(reader)
        return reader

    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=reader_factory,
    )
    window.connection_bar.connect_button.click()
    readers[0].bytes_received.emit(b"A,B\n1,2\n3,4\n")
    window.graphs_widget.set_channel_selected("A", True)
    window.dashboard_widget.set_channel_selected("A", True)

    window.workspace_tabs.setCurrentWidget(window.terminal)
    assert window.graphs_widget.history.points("A")[1] == (1, 3)

    window.connection_bar.connect_button.click()
    assert window.graphs_widget.history.points("A")[1] == (1, 3)
    assert window.graphs_widget.has_series("A")
    assert window.dashboard_widget.tile_value_text("A") == "3"

    window.connection_bar.connect_button.click()
    assert window.graphs_widget.channel_names == ()
    assert window.graphs_widget.history.points("A") == ((), ())
    assert not window.graphs_widget.has_series("A")
    assert window.dashboard_widget.channel_names == ()
    assert window.dashboard_widget.tile_count == 0

    window.close()
    application.processEvents()


def test_graph_clear_preserves_data_values_and_serial_state() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()
    reader.bytes_received.emit(b"A,B\n1,2\n")
    window.graphs_widget.set_channel_selected("A", True)

    window.graphs_widget.clear_button.click()

    assert window.graphs_widget.history.points("A") == ((), ())
    assert window.graphs_widget.selected_channels == ("A",)
    assert window.data_widget.value_text("A") == "1"
    assert window.side_panel.channels_widget.value_text("A") == "1"
    assert connection.is_connected
    assert window.rx_counter.text() == "RX: 8 B"

    window.close()
    application.processEvents()


def test_disconnect_while_graph_paused_is_safe_and_reconnect_resets_pause() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=FakeReader,
    )
    window.connection_bar.connect_button.click()
    window._handle_received_bytes(b"A,B\n1,2\n")
    window.graphs_widget.toggle_pause()

    window.connection_bar.connect_button.click()

    assert window.graphs_widget.is_paused
    assert window.graphs_widget.history.points("A")[1] == (1,)
    assert not connection.is_connected

    window.connection_bar.connect_button.click()
    assert not window.graphs_widget.is_paused
    assert window.graphs_widget.history.points("A") == ((), ())
    assert window.graphs_widget.plot_widget.viewRange()[0] == pytest.approx(
        [0.0, 60.0]
    )

    window.close()
    application.processEvents()


def test_port_dropdown_shows_empty_state() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])

    assert window.connection_bar.port_combo.currentText() == "No serial ports found"
    assert window.connection_bar.selected_port is None

    window.close()
    application.processEvents()


def test_start_logging_enablement_follows_connection_state() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=FakeReader,
    )

    assert not window.side_panel.logging_button.isEnabled()
    window.side_panel.session_name_input.setText("Disconnected test")
    assert not window.side_panel.logging_button.isEnabled()

    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.clear()
    assert window.side_panel.logging_button.isEnabled()
    window.side_panel.session_name_input.setText("   ")
    assert window.side_panel.logging_button.isEnabled()
    window.side_panel.session_name_input.setText("Connected test")
    assert window.side_panel.logging_button.isEnabled()

    window.connection_bar.connect_button.click()
    assert not window.side_panel.logging_button.isEnabled()

    window.close()
    application.processEvents()


@pytest.mark.parametrize("session_name", ["", "   "])
def test_blank_recording_name_warns_without_creating_files(
    monkeypatch,
    tmp_path: Path,
    session_name: str,
) -> None:
    application = QApplication.instance() or QApplication([])
    warnings: list[tuple[str, str]] = []
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=FakeReader,
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *_args: pytest.fail("directory chooser must not open"),
    )
    window.show()
    application.processEvents()
    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.setText(session_name)

    window.side_panel.logging_button.click()
    application.processEvents()

    assert warnings == [
        (
            "Session name required",
            "Enter a session name before starting a recording.",
        )
    ]
    assert not window._recording_session.is_recording
    assert not window._recording_timer.isActive()
    assert window.side_panel.logging_status_dot.property("recordingState") == "inactive"
    assert list(tmp_path.iterdir()) == []
    assert window.side_panel.session_name_input.hasFocus()

    window.close()
    application.processEvents()


def test_port_dropdown_refreshes_and_preserves_selection() -> None:
    application = QApplication.instance() or QApplication([])
    scans = iter(
        [
            [SerialPortInfo("COM3"), SerialPortInfo("COM4", "USB Serial Device")],
            [SerialPortInfo("COM4", "USB Serial Device"), SerialPortInfo("COM5")],
        ]
    )
    window = MainWindow(port_scanner=lambda: next(scans))
    window.connection_bar.port_combo.setCurrentIndex(1)

    window.connection_bar.refresh_button.click()

    assert window.connection_bar.port_combo.count() == 2
    assert window.connection_bar.port_combo.currentText() == "COM4 — USB Serial Device"
    assert window.connection_bar.selected_device == "COM4"
    assert window.connection_bar.port_combo.currentData().device == "COM4"

    window.close()
    application.processEvents()


def test_ui_controls_follow_connection_lifecycle() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    readers: list[FakeReader] = []

    def reader_factory(active_connection: SerialConnection) -> FakeReader:
        reader = FakeReader(active_connection)
        readers.append(reader)
        return reader

    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=reader_factory,
    )

    window.connection_bar.connect_button.click()

    assert window.connection_bar.status_label.text() == "CONNECTED"
    assert window.connection_bar.connect_button.text() == "Disconnect"
    assert not window.connection_bar.port_combo.isEnabled()
    assert not window.connection_bar.baud_combo.isEnabled()
    assert not window.connection_bar.refresh_button.isEnabled()
    assert readers[0].started

    window.connection_bar.connect_button.click()

    assert window.connection_bar.status_label.text() == "DISCONNECTED"
    assert window.connection_bar.connect_button.text() == "Connect"
    assert window.connection_bar.port_combo.isEnabled()
    assert window.connection_bar.baud_combo.isEnabled()
    assert window.connection_bar.refresh_button.isEnabled()
    assert readers[0].stopped
    serial_port.close.assert_called_once_with()

    window.close()
    application.processEvents()


def test_connection_failure_restores_safe_ui_state(monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    connection = SerialConnection(
        serial_factory=Mock(side_effect=SerialException("Permission denied"))
    )
    errors: list[str] = []
    monkeypatch.setattr(
        MainWindow,
        "_show_connection_error",
        lambda _window, message: errors.append(message),
    )
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("/dev/ttyACM0")],
        serial_connection=connection,
    )

    window.connection_bar.connect_button.click()

    assert not connection.is_connected
    assert window.connection_bar.status_label.text() == "CONNECTION ERROR"
    assert window.connection_bar.connect_button.text() == "Connect"
    assert window.connection_bar.port_combo.isEnabled()
    assert window.connection_bar.baud_combo.isEnabled()
    assert window.connection_bar.refresh_button.isEnabled()
    assert errors == ["Could not open /dev/ttyACM0: Permission denied"]

    window.close()
    application.processEvents()


def test_closing_window_closes_serial_connection() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    readers: list[FakeReader] = []

    def reader_factory(active_connection: SerialConnection) -> FakeReader:
        reader = FakeReader(active_connection)
        readers.append(reader)
        return reader

    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=reader_factory,
    )
    window.connection_bar.connect_button.click()

    window.close()
    application.processEvents()

    serial_port.close.assert_called_once_with()
    assert not connection.is_connected
    assert readers[0].stopped


def test_received_chunks_append_and_increment_raw_byte_count() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    readers: list[FakeReader] = []

    def reader_factory(active_connection: SerialConnection) -> FakeReader:
        reader = FakeReader(active_connection)
        readers.append(reader)
        return reader

    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=reader_factory,
    )
    window.connection_bar.connect_button.click()

    readers[0].bytes_received.emit(b"RPM: 1435\n")
    readers[0].bytes_received.emit(b"Pressure: 2.31\n")

    assert window.terminal.output.toPlainText() == "RPM: 1435\nPressure: 2.31\n"
    assert window.rx_counter.text() == "RX: 25 B"
    assert window.tx_counter.text() == "TX: 0 B"

    window.close()
    application.processEvents()


def test_invalid_utf8_is_displayed_without_crashing() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])

    window._handle_received_bytes(b"value: \xff\n")

    assert window.terminal.output.toPlainText() == "value: �\n"
    assert window.rx_counter.text() == "RX: 9 B"

    window.close()
    application.processEvents()


def test_reader_failure_safely_disconnects_and_reports_error(monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    readers: list[FakeReader] = []
    errors: list[str] = []

    def reader_factory(active_connection: SerialConnection) -> FakeReader:
        reader = FakeReader(active_connection)
        readers.append(reader)
        return reader

    monkeypatch.setattr(
        MainWindow,
        "_show_connection_error",
        lambda _window, message: errors.append(message),
    )
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=reader_factory,
    )
    window.connection_bar.connect_button.click()

    readers[0].failed.emit("Serial connection to COM4 was lost: device removed")

    assert readers[0].stopped
    assert not connection.is_connected
    assert window.connection_bar.status_label.text() == "CONNECTION LOST"
    assert window.connection_bar.connect_button.text() == "Connect"
    assert errors == ["Serial connection to COM4 was lost: device removed"]

    window.close()
    application.processEvents()


@pytest.mark.parametrize(
    ("byte_count", "formatted"),
    [
        (0, "0 B"),
        (842, "842 B"),
        (12_400, "12.4 KB"),
        (3_800_000, "3.8 MB"),
    ],
)
def test_byte_count_formatting(byte_count: int, formatted: str) -> None:
    assert format_byte_count(byte_count) == formatted


def test_new_successful_connection_resets_session_counters() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=FakeReader,
    )
    window._rx_bytes = 12_400
    window._tx_bytes = 2_000
    window._update_counter_labels()

    window.connection_bar.connect_button.click()

    assert window._rx_bytes == 0
    assert window._tx_bytes == 0
    assert window.rx_counter.text() == "RX: 0 B"
    assert window.tx_counter.text() == "TX: 0 B"

    window.close()
    application.processEvents()


def test_clear_terminal_does_not_reset_counters_or_disconnect() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=FakeReader,
    )
    window.connection_bar.connect_button.click()
    window._handle_received_bytes(b"data\n")
    window._tx_bytes = 1_200
    window._update_counter_labels()

    window.terminal.clear_button.click()

    assert window.terminal.output.toPlainText() == ""
    assert window.rx_counter.text() == "RX: 5 B"
    assert window.tx_counter.text() == "TX: 1.2 KB"
    assert connection.is_connected

    window.close()
    application.processEvents()


@pytest.mark.parametrize(
    ("line_ending", "expected"),
    [
        ("None", b"STATUS"),
        ("LF", b"STATUS\n"),
        ("CR", b"STATUS\r"),
        ("CRLF", b"STATUS\r\n"),
    ],
)
def test_command_text_encodes_as_utf8_with_selected_line_ending(
    line_ending: str,
    expected: bytes,
) -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])
    window.terminal.command_input.setText("STATUS")
    window.terminal.line_ending_combo.setCurrentText(line_ending)

    assert window.terminal.command_bytes() == expected

    window.close()
    application.processEvents()


def test_send_button_writes_bytes_accumulates_tx_and_clears_input() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    serial_port.write.side_effect = lambda data: len(data)
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=FakeReader,
    )
    window.show()
    window.activateWindow()
    application.processEvents()
    window.connection_bar.connect_button.click()

    window.terminal.command_input.setText("STATUS")
    window.terminal.send_button.click()
    window.terminal.command_input.setText("µ")
    window.terminal.send_button.click()
    application.processEvents()

    assert serial_port.write.call_args_list == [call(b"STATUS\n"), call("µ\n".encode())]
    assert window.tx_counter.text() == "TX: 10 B"
    assert window.terminal.command_input.text() == ""
    assert window.terminal.command_input.hasFocus()
    assert window.terminal.output.toPlainText() == ""

    window.close()
    application.processEvents()


def test_enter_key_sends_command() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    serial_port.write.side_effect = lambda data: len(data)
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=FakeReader,
    )
    window.show()
    window.connection_bar.connect_button.click()
    window.terminal.command_input.setText("PING")

    QTest.keyClick(window.terminal.command_input, Qt.Key.Key_Return)

    serial_port.write.assert_called_once_with(b"PING\n")
    assert window.terminal.command_input.text() == ""

    window.close()
    application.processEvents()


def test_disconnected_send_is_disabled_and_safe() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=False, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    window = MainWindow(port_scanner=lambda: [], serial_connection=connection)

    window.send_command()

    serial_port.write.assert_not_called()
    assert not window.terminal.command_input.isEnabled()
    assert not window.terminal.send_button.isEnabled()
    assert window.tx_counter.text() == "TX: 0 B"

    window.close()
    application.processEvents()


def test_write_failure_preserves_command_and_safely_disconnects(monkeypatch) -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    serial_port.write.side_effect = SerialException("device removed")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    errors: list[str] = []
    monkeypatch.setattr(
        MainWindow,
        "_show_connection_error",
        lambda _window, message: errors.append(message),
    )
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()
    window.terminal.command_input.setText("STATUS")

    window.terminal.send_button.click()

    assert window.terminal.command_input.text() == "STATUS"
    assert window.tx_counter.text() == "TX: 0 B"
    assert reader.stopped
    assert not connection.is_connected
    assert window.connection_bar.status_label.text() == "CONNECTION ERROR"
    assert not window.terminal.send_button.isEnabled()
    assert errors == ["Could not write to COM4: device removed"]

    window.close()
    application.processEvents()


def test_raw_logging_writes_exact_rx_and_stops_without_disconnect(
    monkeypatch,
    tmp_path: Path,
) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *_args: str(tmp_path),
    )
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    readers: list[FakeReader] = []

    def reader_factory(active_connection: SerialConnection) -> FakeReader:
        reader = FakeReader(active_connection)
        readers.append(reader)
        return reader

    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=reader_factory,
    )
    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.setText("Test run")
    window.side_panel.logging_button.click()
    assert not window.side_panel.data_delimiter_combo.isEnabled()

    readers[0].bytes_received.emit(b"valid\n")
    readers[0].bytes_received.emit(b"\xff\x00binary")

    assert window.side_panel.logging_status_label.text() == "RECORDING"
    assert window.side_panel.logging_status_dot.property("recordingState") == "active"
    assert window.side_panel.logging_filename_label.text() == "Test run"
    assert window.side_panel.logged_bytes_label.text() == "Logged: 14 B"
    assert window.terminal.output.toPlainText() == "valid\n�\x00binary"

    window.side_panel.logging_button.click()

    session_directory = next(tmp_path.iterdir())
    assert (session_directory / "raw.log").read_bytes() == b"valid\n\xff\x00binary"
    assert window.side_panel.logging_status_label.text() == "Not recording"
    assert window.side_panel.logging_status_dot.property("recordingState") == "inactive"
    assert window.side_panel.session_name_input.text() == "Test run"
    assert window.side_panel.data_delimiter_combo.isEnabled()
    assert connection.is_connected

    window.close()
    application.processEvents()


def test_recording_delimiter_is_captured_and_cannot_change_active_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *_args: str(tmp_path),
    )
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.setText("Semicolon test")
    window.side_panel.data_delimiter_combo.setCurrentText("Semicolon (;)")
    window.side_panel.logging_button.click()

    assert not window.side_panel.data_delimiter_combo.isEnabled()
    window.side_panel.data_delimiter_combo.setCurrentText("Tab")
    reader.bytes_received.emit(b"A,B\n1,2\n")
    window.side_panel.logging_button.click()

    session_directory = next(tmp_path.iterdir())
    with (session_directory / "data.csv").open(
        encoding="utf-8", newline=""
    ) as file:
        rows = list(csv.reader(file, delimiter=";"))
    metadata = json.loads((session_directory / "session.json").read_text("utf-8"))
    assert rows[0] == ["elapsed_s", "A", "B"]
    assert rows[1][1:] == ["1", "2"]
    assert metadata["structured_data_delimiter"] == ";"
    assert (session_directory / "raw.log").read_bytes() == b"A,B\n1,2\n"
    assert window.side_panel.data_delimiter_combo.isEnabled()

    window.close()
    application.processEvents()


def test_connection_loss_stops_and_preserves_log(monkeypatch, tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *_args: str(tmp_path),
    )
    monkeypatch.setattr(MainWindow, "_show_connection_error", lambda *_args: None)
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    readers: list[FakeReader] = []

    def reader_factory(active_connection: SerialConnection) -> FakeReader:
        reader = FakeReader(active_connection)
        readers.append(reader)
        return reader

    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=reader_factory,
    )
    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.setText("Disconnect test")
    window.side_panel.data_delimiter_combo.setCurrentText("Comma (,)")
    window.side_panel.logging_button.click()
    raw_data = b"A,B\n1,2\n"
    readers[0].bytes_received.emit(raw_data)

    readers[0].failed.emit("device removed")

    session_directory = next(tmp_path.iterdir())
    assert (session_directory / "raw.log").read_bytes() == raw_data
    with (session_directory / "data.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))
    assert rows[0] == ["elapsed_s", "A", "B"]
    assert rows[1][1:] == ["1", "2"]
    metadata = json.loads((session_directory / "session.json").read_text("utf-8"))
    assert metadata["end_reason"] == "serial_disconnected"
    assert window.side_panel.logging_status_label.text() == "Not recording"
    assert window.side_panel.logging_status_dot.property("recordingState") == "inactive"
    assert not window.side_panel.logging_button.isEnabled()
    assert not connection.is_connected

    window.close()
    application.processEvents()


def test_application_shutdown_closes_active_log(monkeypatch, tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *_args: str(tmp_path),
    )
    monkeypatch.setattr(
        "serialscope.ui.main_window.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.setText("Shutdown test")
    window.side_panel.data_delimiter_combo.setCurrentText("Comma (,)")
    window.side_panel.logging_button.click()
    raw_data = b'{"A":1,"B":2}\n'
    reader.bytes_received.emit(raw_data)

    window.close()
    application.processEvents()

    session_directory = next(tmp_path.iterdir())
    assert (session_directory / "raw.log").read_bytes() == raw_data
    with (session_directory / "data.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))
    assert rows[0] == ["elapsed_s", "A", "B"]
    assert rows[1][1:] == ["1", "2"]
    metadata = json.loads((session_directory / "session.json").read_text("utf-8"))
    assert metadata["end_reason"] == "application_closed"
    assert window.side_panel.logging_status_dot.property("recordingState") == "inactive"
    assert reader.stopped
    assert not connection.is_connected


def test_unexpected_disconnect_reconnects_without_restarting_recording(
    monkeypatch, tmp_path: Path
) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(MainWindow, "_show_connection_error", lambda *_args: None)
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    readers: list[FakeReader] = []

    def reader_factory(active_connection: SerialConnection) -> FakeReader:
        reader = FakeReader(active_connection)
        readers.append(reader)
        return reader

    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=reader_factory,
    )
    window.connection_bar.connect_button.click()
    readers[0].failed.emit("device unplugged")

    assert window.connection_bar.status_label.text() == "CONNECTION LOST"
    assert not connection.is_connected
    assert window._reconnect_timer.isActive()
    assert window.side_panel.logging_status_label.text() == "Not recording"

    window._reconnect_timer.stop()
    window._attempt_reconnect()

    assert connection.is_connected
    assert window.connection_bar.status_label.text() == "CONNECTED"
    assert len(readers) == 2
    assert readers[1].started
    assert window.side_panel.logging_status_dot.property("recordingState") == "inactive"
    window.close()
    application.processEvents()


def test_malformed_serial_bytes_do_not_crash_or_stop_connection(
    monkeypatch,
) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(MainWindow, "_show_connection_error", lambda *_args: None)
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()

    window._handle_received_bytes(b"\xff\x00\x01garbage\n")
    window._handle_received_bytes(b"A,B\n1,2\n")

    assert connection.is_connected
    assert window.terminal.output.toPlainText()
    assert window.data_widget.channel_names == ("A", "B")
    window.close()
    application.processEvents()


def test_recorder_exception_clears_recording_indicator(
    monkeypatch, tmp_path: Path
) -> None:
    application = QApplication.instance() or QApplication([])
    session = RecordingSession()
    session.start(tmp_path, SessionConfig("Boom", "COM4", 115200, "LF"))
    monkeypatch.setattr(
        session, "write", lambda *_args: (_ for _ in ()).throw(RuntimeError("disk vanished"))
    )
    errors: list[str] = []
    monkeypatch.setattr(
        MainWindow, "_show_logging_error", lambda _window, message: errors.append(message)
    )
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=FakeReader,
        recording_session=session,
    )
    window.connection_bar.connect_button.click()
    window._handle_received_bytes(b"still-ok\n")

    assert "disk vanished" in errors[0]
    assert not session.is_recording
    assert window.side_panel.logging_status_label.text() == "Not recording"
    assert window.side_panel.logging_status_dot.property("recordingState") == "inactive"
    assert connection.is_connected
    window.close()
    application.processEvents()


def test_application_close_can_be_cancelled_while_recording(
    monkeypatch, tmp_path: Path
) -> None:
    application = QApplication.instance() or QApplication([])
    session = RecordingSession()
    session.start(
        tmp_path,
        SessionConfig("Keep running", "COM4", 115200, "LF"),
    )
    responses = iter(
        (QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
    )
    monkeypatch.setattr(
        "serialscope.ui.main_window.QMessageBox.question",
        lambda *_args, **_kwargs: next(responses),
    )
    window = MainWindow(port_scanner=lambda: [], recording_session=session)
    window.show()

    assert not window.close()
    assert session.is_recording
    assert window.isVisible()

    assert window.close()
    application.processEvents()
    assert not session.is_recording
    metadata = json.loads((session.directory / "session.json").read_text("utf-8"))
    assert metadata["end_reason"] == "application_closed"


def test_logging_write_failure_keeps_serial_and_terminal_usable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    application = QApplication.instance() or QApplication([])
    session = RecordingSession()
    session.start(
        tmp_path,
        SessionConfig("Failure", "COM4", 115200, "LF"),
    )
    errors: list[str] = []

    def fail_write(_data: bytes) -> int:
        raise RecordingSessionError("Could not write log file: disk unavailable")

    monkeypatch.setattr(session, "write", fail_write)
    monkeypatch.setattr(
        MainWindow,
        "_show_logging_error",
        lambda _window, message: errors.append(message),
    )
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=FakeReader,
        recording_session=session,
    )
    window.connection_bar.connect_button.click()

    window._handle_received_bytes(b"still displayed\n")

    assert window.terminal.output.toPlainText() == "still displayed\n"
    assert connection.is_connected
    assert window.side_panel.logging_status_label.text() == "Not recording"
    assert window.side_panel.logging_status_dot.property("recordingState") == "inactive"
    assert errors == ["Could not write log file: disk unavailable"]
    metadata = json.loads(
        (session.directory / "session.json").read_text("utf-8")
    )
    assert metadata["end_reason"] == "logging_error"

    window.close()
    application.processEvents()


def test_recording_elapsed_timer_updates_ui(monkeypatch, tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    current_time = datetime(2026, 8, 12, 18, 15, tzinfo=timezone.utc)

    def clock() -> datetime:
        return current_time

    session = RecordingSession(clock=clock)
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *_args: str(tmp_path),
    )
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=FakeReader,
        recording_session=session,
    )
    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.setText("Timed test")
    window.side_panel.logging_button.click()

    assert window._recording_timer.isActive()
    assert window.side_panel.recording_elapsed_label.text() == "00:00:00"
    current_time += timedelta(seconds=161)
    window._recording_timer.timeout.emit()

    assert window.side_panel.recording_elapsed_label.text() == "00:02:41"
    assert window.side_panel.logging_status_dot.property("recordingState") == "active"

    window.side_panel.logging_button.click()
    assert not window._recording_timer.isActive()
    assert window.side_panel.logging_status_dot.property("recordingState") == "inactive"

    window.close()
    application.processEvents()


def test_csv_rx_updates_channels_without_changing_terminal() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    readers: list[FakeReader] = []

    def reader_factory(active_connection: SerialConnection) -> FakeReader:
        reader = FakeReader(active_connection)
        readers.append(reader)
        return reader

    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=reader_factory,
    )
    window.connection_bar.connect_button.click()
    raw_data = b"Count,Temperature_C\n1,24.72\n2,25.08\n"

    readers[0].bytes_received.emit(raw_data[:13])
    readers[0].bytes_received.emit(raw_data[13:])

    assert window.terminal.output.toPlainText() == raw_data.decode()
    assert window.rx_counter.text() == f"RX: {len(raw_data)} B"
    assert window.side_panel.channels_widget.value_text("Count") == "2"
    assert window.side_panel.channels_widget.value_text("Temperature_C") == "25.08"

    window.close()
    application.processEvents()


def test_channels_reset_on_disconnect_and_new_connection() -> None:
    application = QApplication.instance() or QApplication([])
    first_port = Mock(is_open=True, port="COM4")
    second_port = Mock(is_open=True, port="COM4")
    serial_factory = Mock(side_effect=[first_port, second_port])
    connection = SerialConnection(serial_factory=serial_factory)
    readers: list[FakeReader] = []

    def reader_factory(active_connection: SerialConnection) -> FakeReader:
        reader = FakeReader(active_connection)
        readers.append(reader)
        return reader

    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=reader_factory,
    )
    window.connection_bar.connect_button.click()
    readers[0].bytes_received.emit(b"Old,Value\n1,2\n")
    assert window.side_panel.channels_widget.value_text("Old") == "1"

    window.connection_bar.connect_button.click()
    assert window.side_panel.channels_widget.value_text("Old") is None

    window.connection_bar.connect_button.click()
    readers[1].bytes_received.emit(b"New,Value\n3,4\n")
    assert window.side_panel.channels_widget.value_text("Old") is None
    assert window.side_panel.channels_widget.value_text("New") == "3"

    window.close()
    application.processEvents()


def test_csv_parsing_does_not_modify_recorded_raw_bytes(
    monkeypatch,
    tmp_path: Path,
) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *_args: str(tmp_path),
    )
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.setText("CSV raw test")
    window.side_panel.logging_button.click()
    raw_data = b"A,B\r\n1,2.5\r\n\xffbinary\n"

    reader.bytes_received.emit(raw_data)
    window.side_panel.logging_button.click()

    session_directory = next(tmp_path.iterdir())
    assert (session_directory / "raw.log").read_bytes() == raw_data
    expected_display = raw_data.decode(errors="replace").replace("\r\n", "\n")
    assert window.terminal.output.toPlainText() == expected_display
    assert window.side_panel.channels_widget.value_text("B") == "2.5"

    window.close()
    application.processEvents()


def test_key_value_rx_updates_and_extends_channels() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()

    reader.bytes_received.emit(b"TEMP=25.")
    reader.bytes_received.emit(b"4,PRESSURE=2.51,RPM=1487\r\n")
    reader.bytes_received.emit(b"TEMP=25.7,PRESSURE=2.48,FLOW=0.42\n")

    assert window.side_panel.channels_widget.value_text("TEMP") == "25.7"
    assert window.side_panel.channels_widget.value_text("PRESSURE") == "2.48"
    assert window.side_panel.channels_widget.value_text("RPM") == "1487"
    assert window.side_panel.channels_widget.value_text("FLOW") == "0.42"

    window.close()
    application.processEvents()


def test_key_value_parsing_leaves_terminal_and_raw_log_exact(
    monkeypatch,
    tmp_path: Path,
) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *_args: str(tmp_path),
    )
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.setText("Key value raw test")
    window.side_panel.logging_button.click()
    raw_data = b"TEMP=-12.4,FLOW=1.25e-3\r\n"

    reader.bytes_received.emit(raw_data)
    window.side_panel.logging_button.click()

    session_directory = next(tmp_path.iterdir())
    assert (session_directory / "raw.log").read_bytes() == raw_data
    assert window.terminal.output.toPlainText() == raw_data.decode().replace("\r\n", "\n")
    assert window.side_panel.channels_widget.value_text("TEMP") == "-12.4"
    assert window.side_panel.channels_widget.value_text("FLOW") == "0.00125"

    window.close()
    application.processEvents()


def test_json_rx_updates_adds_and_retains_channels() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()

    reader.bytes_received.emit(b'{"TC1":10')
    reader.bytes_received.emit(b'0.4,"TC2":98.7}\r\n')
    reader.bytes_received.emit(b'{"TC1":101.2,"TC3":105.7}\n')

    channels = window.side_panel.channels_widget
    assert channels.value_text("TC1") == "101.2"
    assert channels.value_text("TC2") == "98.7"
    assert channels.value_text("TC3") == "105.7"

    window.close()
    application.processEvents()


def test_json_parser_state_resets_for_new_connection() -> None:
    application = QApplication.instance() or QApplication([])
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    readers: list[FakeReader] = []

    def reader_factory(active_connection: SerialConnection) -> FakeReader:
        reader = FakeReader(active_connection)
        readers.append(reader)
        return reader

    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=reader_factory,
    )
    window.connection_bar.connect_button.click()
    readers[0].bytes_received.emit(b'{"old":1')
    window.connection_bar.connect_button.click()

    window.connection_bar.connect_button.click()
    readers[1].bytes_received.emit(b'{"new":2}\n')

    assert window.side_panel.channels_widget.value_text("old") is None
    assert window.side_panel.channels_widget.value_text("new") == "2"

    window.close()
    application.processEvents()


def test_json_parsing_leaves_terminal_and_raw_log_exact(
    monkeypatch,
    tmp_path: Path,
) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *_args: str(tmp_path),
    )
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.setText("JSON raw test")
    window.side_panel.logging_button.click()
    raw_data = b'{"TEMP":-12.4,"FLOW":0.00125}\r\n'

    reader.bytes_received.emit(raw_data)
    window.side_panel.logging_button.click()

    session_directory = next(tmp_path.iterdir())
    assert (session_directory / "raw.log").read_bytes() == raw_data
    assert window.terminal.output.toPlainText() == raw_data.decode().replace("\r\n", "\n")
    assert window.side_panel.channels_widget.value_text("TEMP") == "-12.4"
    assert window.rx_counter.text() == f"RX: {len(raw_data)} B"

    window.close()
    application.processEvents()


def test_terminal_control_filter_does_not_change_raw_log_or_rx_count(
    monkeypatch,
    tmp_path: Path,
) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *_args: str(tmp_path),
    )
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.setText("CircuitPython console")
    window.side_panel.logging_button.click()
    raw_data = (
        b"\x1b]0;CircuitPython | code.py\x1b\\"
        b"\x1b[32m"
        b'{"TC2":99.19,"TC3":106.16}\n'
        b"\x1b[0m"
    )

    reader.bytes_received.emit(raw_data[:12])
    reader.bytes_received.emit(raw_data[12:37])
    reader.bytes_received.emit(raw_data[37:])
    window.side_panel.logging_button.click()

    session_directory = next(tmp_path.iterdir())
    assert (session_directory / "raw.log").read_bytes() == raw_data
    assert window.rx_counter.text() == f"RX: {len(raw_data)} B"
    assert window.terminal.output.toPlainText() == (
        '{"TC2":99.19,"TC3":106.16}\n'
    )

    window.close()
    application.processEvents()


@pytest.mark.parametrize(
    ("raw_data", "expected_header", "expected_values"),
    [
        (
            b"A,B\n1,2.5\n3,4.5\n",
            ["elapsed_s", "A", "B"],
            [["1", "2.5"], ["3", "4.5"]],
        ),
        (
            b"TEMP=25.4,PRESSURE=2.51\nTEMP=25.7,PRESSURE=2.48\n",
            ["elapsed_s", "TEMP", "PRESSURE"],
            [["25.4", "2.51"], ["25.7", "2.48"]],
        ),
        (
            b'{"TC1":100.4,"TC2":98.7}\n{"TC1":101.2,"TC2":99.1}\n',
            ["elapsed_s", "TC1", "TC2"],
            [["100.4", "98.7"], ["101.2", "99.1"]],
        ),
    ],
)
def test_recording_writes_parser_updates_to_structured_csv(
    monkeypatch,
    tmp_path: Path,
    raw_data: bytes,
    expected_header: list[str],
    expected_values: list[list[str]],
) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *_args: str(tmp_path),
    )
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.setText("Structured parser test")
    window.side_panel.data_delimiter_combo.setCurrentText("Comma (,)")
    window.side_panel.logging_button.click()

    reader.bytes_received.emit(raw_data)
    window.side_panel.logging_button.click()

    session_directory = next(tmp_path.iterdir())
    with (session_directory / "data.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))
    assert rows[0] == expected_header
    assert [row[1:] for row in rows[1:]] == expected_values
    assert len(rows) == 3
    assert (session_directory / "raw.log").read_bytes() == raw_data

    window.close()
    application.processEvents()


def test_malformed_recorded_input_stays_raw_without_structured_rows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *_args: str(tmp_path),
    )
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    reader = FakeReader(connection)
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=lambda _connection: reader,
    )
    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.setText("Malformed input")
    window.side_panel.logging_button.click()
    raw_data = b'{"broken":1,\nnot,structured\n\xff\x00\n'

    reader.bytes_received.emit(raw_data)
    window.side_panel.logging_button.click()

    session_directory = next(tmp_path.iterdir())
    assert (session_directory / "raw.log").read_bytes() == raw_data
    with (session_directory / "data.csv").open(encoding="utf-8", newline="") as file:
        assert list(csv.reader(file)) == [["elapsed_s"]]

    window.close()
    application.processEvents()


def test_startup_offers_recovery_for_interrupted_recording(
    monkeypatch, tmp_path: Path
) -> None:
    application = QApplication.instance() or QApplication([])
    session = RecordingSession()
    directory = session.start(tmp_path, SessionConfig("Lost run", "COM4", 115200, "LF"))
    session.write(b"keep\n")
    session.flush()
    session._raw_logger.stop()
    session._structured_logger.stop()
    session._event_logger.stop()
    session._clear_active_state()
    settings = ApplicationSettings(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    settings.add_in_progress_session(directory)
    shown: list[tuple] = []

    class FakeDialog:
        def __init__(self, sessions, parent=None) -> None:
            shown.append(sessions)

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(
        "serialscope.ui.main_window.InterruptedRecordingDialog", FakeDialog
    )
    window = MainWindow(
        port_scanner=lambda: [],
        application_settings=settings,
    )
    application.processEvents()

    assert len(shown) == 1
    assert shown[0][0].directory == directory
    assert shown[0][0].session_name == "Lost run"
    assert is_interrupted_recording(directory)
    window.close()
    application.processEvents()


def test_startup_does_not_offer_recovery_for_completed_recording(
    monkeypatch, tmp_path: Path
) -> None:
    application = QApplication.instance() or QApplication([])
    session = RecordingSession()
    directory = session.start(tmp_path, SessionConfig("Finished", "COM4", 115200, "LF"))
    session.write(b"done\n")
    session.stop("normal", 5)
    settings = ApplicationSettings(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    settings.add_in_progress_session(directory)
    shown: list[object] = []

    class FakeDialog:
        def __init__(self, sessions, parent=None) -> None:
            shown.append(sessions)

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(
        "serialscope.ui.main_window.InterruptedRecordingDialog", FakeDialog
    )
    window = MainWindow(
        port_scanner=lambda: [],
        application_settings=settings,
    )
    application.processEvents()

    assert shown == []
    assert settings.in_progress_sessions() == ()
    assert not is_interrupted_recording(directory)
    window.close()
    application.processEvents()


def test_normal_stop_unregisters_in_progress_session(
    monkeypatch, tmp_path: Path
) -> None:
    application = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getExistingDirectory",
        lambda *_args: str(tmp_path),
    )
    settings = ApplicationSettings(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    serial_port = Mock(is_open=True, port="COM4")
    connection = SerialConnection(serial_factory=Mock(return_value=serial_port))
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=FakeReader,
        application_settings=settings,
    )
    application.processEvents()
    window.connection_bar.connect_button.click()
    window.side_panel.session_name_input.setText("Live run")
    window.side_panel.logging_button.click()

    session_directory = next(path for path in tmp_path.iterdir() if path.is_dir())
    assert tuple(Path(item) for item in settings.in_progress_sessions()) == (
        session_directory,
    )
    assert (session_directory / IN_PROGRESS_NAME).is_file()

    window.side_panel.logging_button.click()

    assert settings.in_progress_sessions() == ()
    assert not (session_directory / IN_PROGRESS_NAME).exists()
    metadata = json.loads((session_directory / "session.json").read_text("utf-8"))
    assert metadata["status"] == "completed"
    assert metadata["end_reason"] == "normal"
    window.close()
    application.processEvents()
