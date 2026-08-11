"""Application startup and lifecycle."""

import sys

from PySide6.QtWidgets import QApplication

from serialscope import __version__
from serialscope.ui.main_window import MainWindow
from serialscope.ui.style import APPLICATION_STYLE


def main() -> int:
    """Start SerialScope and return the process exit code."""
    application = QApplication(sys.argv)
    application.setApplicationName("SerialScope")
    application.setApplicationVersion(__version__)
    application.setOrganizationName("SerialScope")
    application.setStyleSheet(APPLICATION_STYLE)
    window = MainWindow()
    window.show()
    return application.exec()
