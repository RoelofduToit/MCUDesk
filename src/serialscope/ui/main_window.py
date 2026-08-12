"""The SerialScope main window and top-level UI composition."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from serialscope.serial import (
    SerialConnection,
    SerialConnectionError,
    SerialPortInfo,
    SerialReader,
    discover_recommended_serial_ports,
)
from serialscope.ui.connection_bar import ConnectionBar
from serialscope.ui.side_panel import SidePanel
from serialscope.ui.terminal_widget import TerminalWidget


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(
        self,
        port_scanner: Callable[[], list[SerialPortInfo]] | None = None,
        serial_connection: SerialConnection | None = None,
        reader_factory: Callable[[SerialConnection], SerialReader] | None = None,
    ) -> None:
        super().__init__()
        self._port_scanner = port_scanner or discover_recommended_serial_ports
        self._serial_connection = serial_connection or SerialConnection()
        self._reader_factory = reader_factory or SerialReader
        self._serial_reader: SerialReader | None = None
        self._rx_bytes = 0
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
        self.connection_bar.refresh_button.clicked.connect(self.refresh_ports)
        self.connection_bar.connect_button.clicked.connect(
            self.toggle_serial_connection
        )
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
        self.refresh_ports()

    def refresh_ports(self) -> None:
        """Refresh the connection bar with currently available ports."""
        self.connection_bar.set_ports(self._port_scanner())

    def toggle_serial_connection(self) -> None:
        """Connect or disconnect according to the current service state."""
        if self._serial_connection.is_connected:
            self._disconnect_serial_port()
        else:
            self._connect_serial_port()

    def _connect_serial_port(self) -> None:
        port = self.connection_bar.selected_port
        if port is None:
            self._show_connection_error("Select a serial port before connecting.")
            self.connection_bar.set_connected(False)
            return

        baud_rate = int(self.connection_bar.baud_combo.currentText())
        try:
            self._serial_connection.connect(port.device, baud_rate)
        except SerialConnectionError as error:
            self.connection_bar.set_connected(False)
            self._show_connection_error(str(error))
            return

        self.connection_bar.set_connected(True)
        self.terminal.reset_stream_decoder()
        self._start_serial_reader()

    def _start_serial_reader(self) -> None:
        self._serial_reader = self._reader_factory(self._serial_connection)
        self._serial_reader.bytes_received.connect(self._handle_received_bytes)
        self._serial_reader.failed.connect(self._handle_reader_failure)
        self._serial_reader.start()

    def _stop_serial_reader(self) -> None:
        reader = self._serial_reader
        self._serial_reader = None
        if reader is not None:
            reader.stop()

    def _handle_received_bytes(self, data: bytes) -> None:
        self._rx_bytes += len(data)
        self.rx_counter.setText(f"RX: {self._rx_bytes} B")
        self.terminal.append_bytes(data)

    def _handle_reader_failure(self, message: str) -> None:
        self._stop_serial_reader()
        try:
            self._serial_connection.disconnect()
        except SerialConnectionError:
            pass
        self.connection_bar.set_connected(False)
        self._show_connection_error(message)

    def _disconnect_serial_port(self) -> None:
        self._stop_serial_reader()
        try:
            self._serial_connection.disconnect()
        except SerialConnectionError as error:
            self._show_connection_error(str(error))
        finally:
            self.connection_bar.set_connected(False)

    def _show_connection_error(self, message: str) -> None:
        QMessageBox.critical(self, "Serial connection error", message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Release an open serial port before the window is destroyed."""
        self._stop_serial_reader()
        try:
            self._serial_connection.disconnect()
        except SerialConnectionError:
            pass
        event.accept()

    def _build_status_bar(self) -> None:
        status = self.statusBar()
        status.setObjectName("applicationStatusBar")

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
