"""The SerialScope main window and top-level UI composition."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from serialscope.ui.connection_bar import ConnectionBar
from serialscope.ui.side_panel import SidePanel
from serialscope.ui.terminal_widget import TerminalWidget


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("mainWindow")
        self.setWindowTitle("SerialScope")
        self.setMinimumSize(800, 520)
        self.resize(1120, 720)

        central_widget = QWidget()
        central_widget.setObjectName("centralWorkspace")
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(14, 14, 14, 10)
        root_layout.setSpacing(12)

        self.connection_bar = ConnectionBar()
        root_layout.addWidget(self.connection_bar)

        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter.setObjectName("workspaceSplitter")
        self.terminal = TerminalWidget()
        self.side_panel = SidePanel()
        self.workspace_splitter.addWidget(self.terminal)
        self.workspace_splitter.addWidget(self.side_panel)
        self.workspace_splitter.setStretchFactor(0, 1)
        self.workspace_splitter.setStretchFactor(1, 0)
        self.workspace_splitter.setSizes([820, 260])
        root_layout.addWidget(self.workspace_splitter, 1)

        self.setCentralWidget(central_widget)
        self._build_status_bar()

    def _build_status_bar(self) -> None:
        status = self.statusBar()
        status.setObjectName("applicationStatusBar")

        self.connection_state = QLabel("Disconnected")
        self.connection_state.setObjectName("statusConnectionState")
        status.addWidget(self.connection_state)

        counters = QWidget()
        counters.setObjectName("statusCounters")
        counter_layout = QHBoxLayout(counters)
        counter_layout.setContentsMargins(0, 0, 8, 0)
        counter_layout.setSpacing(18)

        self.rx_counter = QLabel("RX: 0 B")
        self.rx_counter.setObjectName("rxCounter")
        counter_layout.addWidget(self.rx_counter)

        self.tx_counter = QLabel("TX: 0 B")
        self.tx_counter.setObjectName("txCounter")
        counter_layout.addWidget(self.tx_counter)
        status.addPermanentWidget(counters)
