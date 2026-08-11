import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QGroupBox, QLineEdit, QPlainTextEdit

from serialscope.ui.main_window import MainWindow


def test_main_window_has_application_title() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.windowTitle() == "SerialScope"

    window.close()
    application.processEvents()


def test_main_window_constructs_ui_shell() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow()

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
