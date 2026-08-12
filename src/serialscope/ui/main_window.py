"""The SerialScope main window and top-level UI composition."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from serialscope.logging import RawLogger, RawLoggerError
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


def format_byte_count(byte_count: int) -> str:
    """Format bytes using decimal SI units for status presentation."""
    if byte_count < 1_000:
        return f"{byte_count} B"
    if byte_count < 1_000_000:
        return f"{byte_count / 1_000:.1f} KB"
    return f"{byte_count / 1_000_000:.1f} MB"


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(
        self,
        port_scanner: Callable[[], list[SerialPortInfo]] | None = None,
        serial_connection: SerialConnection | None = None,
        reader_factory: Callable[[SerialConnection], SerialReader] | None = None,
        raw_logger: RawLogger | None = None,
    ) -> None:
        super().__init__()
        self._port_scanner = port_scanner or discover_recommended_serial_ports
        self._serial_connection = serial_connection or SerialConnection()
        self._reader_factory = reader_factory or SerialReader
        self._serial_reader: SerialReader | None = None
        self._raw_logger = raw_logger or RawLogger()
        self._rx_bytes = 0
        self._tx_bytes = 0
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
        self.terminal.send_button.clicked.connect(self.send_command)
        self.terminal.command_input.returnPressed.connect(self.send_command)
        self.side_panel = SidePanel()
        self.side_panel.logging_button.clicked.connect(self.toggle_logging)
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
            self.connection_bar.set_connection_state("error")
            return

        baud_rate = int(self.connection_bar.baud_combo.currentText())
        try:
            self._serial_connection.connect(port.device, baud_rate)
        except SerialConnectionError as error:
            self.connection_bar.set_connection_state("error")
            self._show_connection_error(str(error))
            return

        self._reset_session_counters()
        self.connection_bar.set_connected(True)
        self.terminal.set_connected(True)
        self.side_panel.set_connected(True)
        self.terminal.command_input.setFocus()
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
        self._update_counter_labels()
        if self._raw_logger.is_recording:
            try:
                self._raw_logger.write(data)
            except RawLoggerError as error:
                self._update_logging_presentation()
                self.side_panel.set_connected(self._serial_connection.is_connected)
                self._show_logging_error(str(error))
            else:
                self._update_logging_presentation()
        self.terminal.append_bytes(data)

    def _handle_reader_failure(self, message: str) -> None:
        self._return_to_disconnected_state()
        self.connection_bar.set_connection_state("error")
        self._show_connection_error(message)

    def send_command(self) -> None:
        """Encode and transmit the current command through the serial layer."""
        if not self._serial_connection.is_connected:
            return

        data = self.terminal.command_bytes()
        try:
            written = self._serial_connection.write(data)
        except SerialConnectionError as error:
            self._return_to_disconnected_state()
            self.connection_bar.set_connection_state("error")
            self._show_connection_error(str(error))
            return

        self._tx_bytes += written
        self._update_counter_labels()
        self.terminal.command_input.clear()
        self.terminal.command_input.setFocus()

    def _reset_session_counters(self) -> None:
        self._rx_bytes = 0
        self._tx_bytes = 0
        self._update_counter_labels()

    def _update_counter_labels(self) -> None:
        self.rx_counter.setText(f"RX: {format_byte_count(self._rx_bytes)}")
        self.tx_counter.setText(f"TX: {format_byte_count(self._tx_bytes)}")

    def toggle_logging(self) -> None:
        """Start or stop raw RX logging."""
        if self._raw_logger.is_recording:
            self._stop_logging()
        else:
            self._start_logging()

    def _start_logging(self) -> None:
        if not self._serial_connection.is_connected:
            return

        suggested_name = datetime.now().strftime("serial_%Y-%m-%d_%H%M.log")
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save raw serial log",
            suggested_name,
            "Raw serial logs (*.log);;All files (*)",
        )
        if not selected_path:
            return

        try:
            self._raw_logger.start(Path(selected_path))
        except RawLoggerError as error:
            self._update_logging_presentation()
            self._show_logging_error(str(error))
            return

        self._update_logging_presentation()
        self.side_panel.set_connected(True)

    def _stop_logging(self, show_error: bool = True) -> None:
        try:
            self._raw_logger.stop()
        except RawLoggerError as error:
            if show_error:
                self._show_logging_error(str(error))
        finally:
            self._update_logging_presentation()
            self.side_panel.set_connected(self._serial_connection.is_connected)

    def _update_logging_presentation(self) -> None:
        path = self._raw_logger.path
        self.side_panel.set_logging_state(
            self._raw_logger.is_recording,
            path.name if path is not None else "",
            format_byte_count(self._raw_logger.bytes_written),
        )

    def _return_to_disconnected_state(self) -> None:
        self._stop_logging()
        self._stop_serial_reader()
        try:
            self._serial_connection.disconnect()
        except SerialConnectionError:
            pass
        self.connection_bar.set_connected(False)
        self.terminal.set_connected(False)
        self.side_panel.set_connected(False)

    def _disconnect_serial_port(self) -> None:
        self._stop_logging()
        self._stop_serial_reader()
        try:
            self._serial_connection.disconnect()
        except SerialConnectionError as error:
            self.connection_bar.set_connection_state("error")
            self.terminal.set_connected(False)
            self.side_panel.set_connected(False)
            self._show_connection_error(str(error))
            return

        self.connection_bar.set_connected(False)
        self.terminal.set_connected(False)
        self.side_panel.set_connected(False)

    def _show_connection_error(self, message: str) -> None:
        QMessageBox.critical(self, "Serial connection error", message)

    def _show_logging_error(self, message: str) -> None:
        QMessageBox.critical(self, "Raw logging error", message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Release an open serial port before the window is destroyed."""
        self._stop_logging(show_error=False)
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
