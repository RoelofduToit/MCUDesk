"""Application startup and lifecycle."""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from serialscope import __version__
from serialscope.resources import apply_application_icon
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
    apply_application_icon(application)
    settings = ApplicationSettings()
    window = MainWindow(application_settings=settings)
    window.show()
    if smoke_test:
        QTimer.singleShot(250, application.quit)
    else:
        QTimer.singleShot(0, window.check_for_updates_automatically)
    return application.exec()
