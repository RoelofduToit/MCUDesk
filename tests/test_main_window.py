import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from serialscope.ui.main_window import MainWindow


def test_main_window_has_application_title() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow()

    assert window.windowTitle() == "SerialScope"

    window.close()
    application.processEvents()
