"""Connection controls displayed above the main workspace."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from serialscope.serial import SerialPortInfo


class ConnectionBar(QFrame):
    """Present the connection controls without implementing their behavior."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("connectionBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        port_label = QLabel("PORT")
        port_label.setObjectName("fieldLabel")
        layout.addWidget(port_label)

        self.port_combo = QComboBox()
        self.port_combo.setObjectName("portCombo")
        self.port_combo.setMinimumContentsLength(14)
        layout.addWidget(self.port_combo)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.setToolTip("Refresh available serial ports")
        layout.addWidget(self.refresh_button)

        baud_label = QLabel("BAUD")
        baud_label.setObjectName("fieldLabel")
        layout.addWidget(baud_label)

        self.baud_combo = QComboBox()
        self.baud_combo.setObjectName("baudCombo")
        self.baud_combo.addItems(
            ["9600", "19200", "38400", "57600", "115200", "230400", "460800"]
        )
        self.baud_combo.setCurrentText("115200")
        layout.addWidget(self.baud_combo)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("connectButton")
        layout.addWidget(self.connect_button)

        layout.addStretch()

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("connectionStatusDot")
        self.status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_dot)

        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("connectionStatusLabel")
        layout.addWidget(self.status_label)

    def set_ports(self, ports: list[SerialPortInfo]) -> None:
        """Replace displayed ports while retaining the selected device."""
        selected_device = self.selected_device
        self.port_combo.clear()

        if not ports:
            self.port_combo.addItem("No serial ports found", None)
            return

        for port in ports:
            self.port_combo.addItem(port.display_name, port)

        if selected_device is not None:
            for index in range(self.port_combo.count()):
                port = self.port_combo.itemData(index)
                if port.device == selected_device:
                    self.port_combo.setCurrentIndex(index)
                    break

    @property
    def selected_port(self) -> SerialPortInfo | None:
        """Return the selected structured port value, if one exists."""
        port = self.port_combo.currentData()
        return port if isinstance(port, SerialPortInfo) else None

    @property
    def selected_device(self) -> str | None:
        """Return the selected OS device identifier."""
        port = self.selected_port
        return port.device if port is not None else None
