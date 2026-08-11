"""Application startup and lifecycle."""

import sys

from PySide6.QtWidgets import QApplication

from serialscope.ui.main_window import MainWindow


def main() -> int:
    """Start SerialScope and return the process exit code."""
    application = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return application.exec()
