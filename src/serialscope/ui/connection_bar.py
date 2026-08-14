"""Connection controls displayed above the main workspace."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QMenu,
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

        self.source_label = QLabel("DEVICE")
        self.source_label.setObjectName("fieldLabel")
        layout.addWidget(self.source_label)
        self.source_combo = QComboBox()
        self.source_combo.setObjectName("serialSourceCombo")
        self.source_combo.setMinimumContentsLength(10)
        layout.addWidget(self.source_combo)
        self.source_name_input = QLineEdit()
        self.source_name_input.setObjectName("serialSourceName")
        self.source_name_input.setPlaceholderText("Device name")
        self.source_name_input.setMaximumWidth(150)
        layout.addWidget(self.source_name_input)
        self.add_source_button = QPushButton("Add Device")
        self.add_source_button.setObjectName("addSerialSourceButton")
        layout.addWidget(self.add_source_button)
        self.remove_source_button = QPushButton("Remove")
        self.remove_source_button.setObjectName("removeSerialSourceButton")
        layout.addWidget(self.remove_source_button)

        self.profile_label = QLabel("PROFILE")
        self.profile_label.setObjectName("fieldLabel")
        layout.addWidget(self.profile_label)
        self.profile_combo = QComboBox()
        self.profile_combo.setObjectName("deviceProfileCombo")
        self.profile_combo.setMinimumContentsLength(11)
        self.profile_combo.setMaximumWidth(180)
        self.profile_combo.addItem("Custom", None)
        layout.addWidget(self.profile_combo)
        self.profile_menu_button = QToolButton()
        self.profile_menu_button.setObjectName("deviceProfileMenuButton")
        self.profile_menu_button.setText("⋮")
        self.profile_menu_button.setToolTip("Device Profile actions")
        self.profile_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.profile_menu = QMenu(self.profile_menu_button)
        self.save_profile_action = self.profile_menu.addAction(
            "Save Current as Profile..."
        )
        self.update_profile_action = self.profile_menu.addAction("Update Profile")
        self.rename_profile_action = self.profile_menu.addAction("Rename Profile...")
        self.delete_profile_action = self.profile_menu.addAction("Delete Profile...")
        self.profile_menu_button.setMenu(self.profile_menu)
        layout.addWidget(self.profile_menu_button)
        self.profile_status_label = QLabel("")
        self.profile_status_label.setObjectName("profileStatusLabel")
        self.profile_status_label.setMaximumWidth(115)
        layout.addWidget(self.profile_status_label)

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
            [
                "9600",
                "19200",
                "38400",
                "57600",
                "115200",
                "230400",
                "460800",
                "921600",
            ]
        )
        self.baud_combo.setCurrentText("115200")
        layout.addWidget(self.baud_combo)

        self.status_indicator = QFrame()
        self.status_indicator.setObjectName("connectionStatusIndicator")
        status_layout = QHBoxLayout(self.status_indicator)
        status_layout.setContentsMargins(9, 0, 10, 0)
        status_layout.setSpacing(6)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("connectionStatusDot")
        self.status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_dot)

        self.status_label = QLabel("DISCONNECTED")
        self.status_label.setObjectName("connectionStatusLabel")
        self.status_label.ensurePolished()
        self.status_label.setMinimumWidth(
            self.status_label.fontMetrics().horizontalAdvance("CONNECTION ERROR")
        )
        status_layout.addWidget(self.status_label)
        layout.addWidget(self.status_indicator)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("connectButton")
        layout.addWidget(self.connect_button)

        layout.addStretch()

        self.set_connection_state("disconnected")
        self.set_source_count(1)
        self.set_profile_controls_enabled(True)

    def set_source_count(self, count: int) -> None:
        """Reveal source management only when it distinguishes devices."""
        multiple = count >= 2
        self.source_label.setVisible(multiple)
        self.source_combo.setVisible(multiple)
        self.source_name_input.setVisible(multiple)
        self.remove_source_button.setVisible(multiple)
        self.add_source_button.setText("+ Add Device" if not multiple else "+ Add")

    def set_connected(self, connected: bool) -> None:
        """Present the current connection state without owning its logic."""
        self.set_connection_state("connected" if connected else "disconnected")

    def set_connection_state(self, state: str) -> None:
        """Present connected, disconnected, or error state."""
        connected = state == "connected"
        self.connect_button.setText("Disconnect" if connected else "Connect")
        labels = {
            "connected": "CONNECTED",
            "disconnected": "DISCONNECTED",
            "error": "CONNECTION ERROR",
        }
        self.status_label.setText(labels[state])
        tooltips = {
            "connected": "Serial device is connected",
            "disconnected": "Serial device is disconnected",
            "error": "The serial connection failed",
        }
        self.status_indicator.setToolTip(tooltips[state])
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        self.refresh_button.setEnabled(not connected)

        for widget in (self.status_indicator, self.status_dot, self.status_label):
            widget.setProperty("connectionState", state)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

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

    def set_profiles(
        self, profiles: tuple[tuple[str, str], ...], selected_id: str | None
    ) -> None:
        """Populate persistent profiles without conflating names and IDs."""
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("Custom", None)
        for profile_id, name in profiles:
            self.profile_combo.addItem(name, profile_id)
        index = self.profile_combo.findData(selected_id)
        self.profile_combo.setCurrentIndex(index if index >= 0 else 0)
        self.profile_combo.blockSignals(False)
        self.update_profile_action_state()

    @property
    def selected_profile_id(self) -> str | None:
        value = self.profile_combo.currentData()
        return str(value) if value is not None else None

    def set_profile_status(self, text: str, tooltip: str = "") -> None:
        self.profile_status_label.setText(text)
        self.profile_status_label.setToolTip(tooltip or text)

    def set_profile_controls_enabled(self, enabled: bool) -> None:
        self.profile_combo.setEnabled(enabled)
        self.profile_menu_button.setEnabled(enabled)
        self.update_profile_action_state()

    def update_profile_action_state(self) -> None:
        selected = self.selected_profile_id is not None
        enabled = self.profile_menu_button.isEnabled()
        self.save_profile_action.setEnabled(enabled)
        self.update_profile_action.setEnabled(enabled and selected)
        self.rename_profile_action.setEnabled(enabled and selected)
        self.delete_profile_action.setEnabled(enabled and selected)

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
