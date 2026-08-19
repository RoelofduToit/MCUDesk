"""Application startup and lifecycle."""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from serialscope import PRODUCT_NAME, STORAGE_APP_NAME, __version__
from serialscope.resources import apply_application_icon
from serialscope.settings import ApplicationSettings
from serialscope.ui.main_window import MainWindow


def main() -> int:
    """Start MCUDesk and return the process exit code."""
    smoke_test = "--packaging-smoke-test" in sys.argv
    arguments = [
        argument for argument in sys.argv if argument != "--packaging-smoke-test"
    ]
    application = QApplication(arguments)
    application.setApplicationName(STORAGE_APP_NAME)
    application.setApplicationDisplayName(PRODUCT_NAME)
    application.setApplicationVersion(__version__)
    application.setOrganizationName(STORAGE_APP_NAME)
    apply_application_icon(application)
    settings = ApplicationSettings()
    window = MainWindow(application_settings=settings)
    window.show()
    if smoke_test:
        QTimer.singleShot(250, application.quit)
    else:
        QTimer.singleShot(0, window.check_for_updates_automatically)
    return application.exec()
