"""The SerialScope main window."""

from PySide6.QtWidgets import QMainWindow


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SerialScope")
