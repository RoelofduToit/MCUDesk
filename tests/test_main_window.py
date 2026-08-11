import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QGroupBox, QLineEdit, QPlainTextEdit

from serialscope.serial import SerialPortInfo
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
