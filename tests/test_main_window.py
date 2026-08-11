import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QGroupBox, QLineEdit, QPlainTextEdit

from serial import SerialException

from serialscope.serial import SerialConnection, SerialPortInfo
from serialscope.ui.main_window import MainWindow


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
    assert window.findChild(QGroupBox, "connectionSection") is not None
    assert window.findChild(QGroupBox, "channelsSection") is not None
    assert window.findChild(QGroupBox, "sessionSection") is not None
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
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
    )

    window.connection_bar.connect_button.click()

    assert window.connection_bar.status_label.text() == "Connected"
    assert window.connection_bar.connect_button.text() == "Disconnect"
    assert not window.connection_bar.port_combo.isEnabled()
    assert not window.connection_bar.baud_combo.isEnabled()
    assert not window.connection_bar.refresh_button.isEnabled()

    window.connection_bar.connect_button.click()

    assert window.connection_bar.status_label.text() == "Disconnected"
    assert window.connection_bar.connect_button.text() == "Connect"
    assert window.connection_bar.port_combo.isEnabled()
    assert window.connection_bar.baud_combo.isEnabled()
    assert window.connection_bar.refresh_button.isEnabled()
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
    assert window.connection_bar.status_label.text() == "Disconnected"
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
    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
    )
    window.connection_bar.connect_button.click()

    window.close()
    application.processEvents()

    serial_port.close.assert_called_once_with()
    assert not connection.is_connected
