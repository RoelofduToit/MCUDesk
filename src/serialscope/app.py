"""Application startup and lifecycle."""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from serialscope import __version__
from serialscope.settings import ApplicationSettings
from serialscope.ui.main_window import MainWindow


def main() -> int:
    """Start SerialScope and return the process exit code."""
    smoke_test = "--packaging-smoke-test" in sys.argv
    arguments = [
        argument for argument in sys.argv if argument != "--packaging-smoke-test"
    ]
    application = QApplication(arguments)
    application.setApplicationName("SerialScope")
    application.setApplicationVersion(__version__)
    application.setOrganizationName("SerialScope")
    settings = ApplicationSettings()
    window = MainWindow(application_settings=settings)
    window.show()
    if smoke_test:
        QTimer.singleShot(250, application.quit)
    return application.exec()
