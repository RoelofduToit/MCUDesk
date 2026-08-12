"""Application startup and lifecycle."""

import sys

from PySide6.QtWidgets import QApplication

from serialscope import __version__
from serialscope.settings import ApplicationSettings
from serialscope.ui.main_window import MainWindow


def main() -> int:
    """Start SerialScope and return the process exit code."""
    application = QApplication(sys.argv)
    application.setApplicationName("SerialScope")
    application.setApplicationVersion(__version__)
    application.setOrganizationName("SerialScope")
    settings = ApplicationSettings()
    window = MainWindow(application_settings=settings)
    window.show()
    return application.exec()
