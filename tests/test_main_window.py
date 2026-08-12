import os
from pathlib import Path
from unittest.mock import Mock, call

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QGroupBox, QLineEdit, QPlainTextEdit

from serial import SerialException

from serialscope.logging import RawLogger, RawLoggerError
from serialscope.serial import SerialConnection, SerialPortInfo
from serialscope.ui.main_window import MainWindow, format_byte_count


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

    assert window.windowTitle() == "SerialScope"

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
    assert window.rx_counter.text() == "RX: 0 B"
    assert window.tx_counter.text() == "TX: 0 B"

    window.close()
    application.processEvents()


def test_port_dropdown_shows_empty_state() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])

    assert window.connection_bar.port_combo.currentText() == "No serial ports found"
    assert window.connection_bar.selected_port is None

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

    assert window.connection_bar.status_label.text() == "Connected"
    assert window.connection_bar.connect_button.text() == "Disconnect"
    assert not window.connection_bar.port_combo.isEnabled()
    assert not window.connection_bar.baud_combo.isEnabled()
    assert not window.connection_bar.refresh_button.isEnabled()
    assert readers[0].started

    window.connection_bar.connect_button.click()

    assert window.connection_bar.status_label.text() == "Disconnected"
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
    assert window.connection_bar.status_label.text() == "Connection error"
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
    assert window.connection_bar.status_label.text() == "Connection error"
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
    assert window.connection_bar.status_label.text() == "Connection error"
    assert not window.terminal.send_button.isEnabled()
    assert errors == ["Could not write to COM4: device removed"]

    window.close()
    application.processEvents()


def test_raw_logging_writes_exact_rx_and_stops_without_disconnect(
    monkeypatch,
    tmp_path: Path,
) -> None:
    application = QApplication.instance() or QApplication([])
    path = tmp_path / "session.log"
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getSaveFileName",
        lambda *_args: (str(path), ""),
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
    window.side_panel.logging_button.click()

    readers[0].bytes_received.emit(b"valid\n")
    readers[0].bytes_received.emit(b"\xff\x00binary")

    assert window.side_panel.logging_status_label.text() == "Recording"
    assert window.side_panel.logging_status_dot.property("recordingState") == "active"
    assert window.side_panel.logging_filename_label.text() == "session.log"
    assert window.side_panel.logged_bytes_label.text() == "Logged: 14 B"
    assert window.terminal.output.toPlainText() == "valid\n�\x00binary"

    window.side_panel.logging_button.click()

    assert path.read_bytes() == b"valid\n\xff\x00binary"
    assert window.side_panel.logging_status_label.text() == "Not recording"
    assert window.side_panel.logging_status_dot.property("recordingState") == "inactive"
    assert connection.is_connected

    window.close()
    application.processEvents()


def test_connection_loss_stops_and_preserves_log(monkeypatch, tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    path = tmp_path / "lost-device.log"
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getSaveFileName",
        lambda *_args: (str(path), ""),
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
    window.side_panel.logging_button.click()
    readers[0].bytes_received.emit(b"preserved")

    readers[0].failed.emit("device removed")

    assert path.read_bytes() == b"preserved"
    assert window.side_panel.logging_status_label.text() == "Not recording"
    assert window.side_panel.logging_status_dot.property("recordingState") == "inactive"
    assert not window.side_panel.logging_button.isEnabled()
    assert not connection.is_connected

    window.close()
    application.processEvents()


def test_application_shutdown_closes_active_log(monkeypatch, tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    path = tmp_path / "shutdown.log"
    monkeypatch.setattr(
        "serialscope.ui.main_window.QFileDialog.getSaveFileName",
        lambda *_args: (str(path), ""),
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
    window.side_panel.logging_button.click()
    reader.bytes_received.emit(b"before close")

    window.close()
    application.processEvents()

    assert path.read_bytes() == b"before close"
    assert window.side_panel.logging_status_dot.property("recordingState") == "inactive"
    assert reader.stopped
    assert not connection.is_connected


def test_logging_write_failure_keeps_serial_and_terminal_usable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    application = QApplication.instance() or QApplication([])
    path = tmp_path / "failure.log"
    logger = RawLogger()
    logger.start(path)
    errors: list[str] = []

    def fail_write(_data: bytes) -> int:
        logger._close_after_failure()
        raise RawLoggerError("Could not write log file: disk unavailable")

    monkeypatch.setattr(logger, "write", fail_write)
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
        raw_logger=logger,
    )
    window.connection_bar.connect_button.click()

    window._handle_received_bytes(b"still displayed\n")

    assert window.terminal.output.toPlainText() == "still displayed\n"
    assert connection.is_connected
    assert window.side_panel.logging_status_label.text() == "Not recording"
    assert window.side_panel.logging_status_dot.property("recordingState") == "inactive"
    assert errors == ["Could not write log file: disk unavailable"]

    window.close()
    application.processEvents()
