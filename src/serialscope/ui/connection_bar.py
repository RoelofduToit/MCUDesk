"""Connection controls displayed above the main workspace."""

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QMenu,
    QWidget,
)

from serialscope.serial import SerialPortInfo


class _WrapLayout(QLayout):
    """Keep control groups on one row when they fit, otherwise wrap."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 8) -> None:
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)
        self._items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        width = 0
        height = 0
        spacing = self.spacing()
        for index, item in enumerate(self._items):
            hint = item.sizeHint()
            width += hint.width()
            if index:
                width += spacing
            height = max(height, hint.height())
        left, top, right, bottom = self.getContentsMargins()
        return QSize(width + left + right, height + top + bottom)

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        return size + QSize(left + right, top + bottom)

    def _item_size(self, item: QLayoutItem, available_width: int) -> QSize:
        hint = item.sizeHint()
        width = hint.width() if hint.width() <= available_width else max(
            item.minimumSize().width(), available_width
        )
        if width < hint.width() and item.hasHeightForWidth():
            return QSize(width, item.heightForWidth(width))
        return QSize(width, hint.height())

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        x = effective.x()
        y = effective.y()
        line_height = 0
        spacing = self.spacing()
        available = max(0, effective.width())
        for item in self._items:
            size = self._item_size(item, available)
            next_x = x + size.width() + spacing
            if line_height and next_x - spacing > effective.right() + 1:
                x = effective.x()
                y += line_height + spacing
                size = self._item_size(item, available)
                next_x = x + size.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), size))
            x = next_x
            line_height = max(line_height, size.height())
        return y + line_height - rect.y() + bottom


def _compact_combo(combo: QComboBox, *, contents: int = 4) -> None:
    """Prefer a modest width and shrink before neighboring labels clip."""
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setMinimumContentsLength(contents)
    combo.setMinimumWidth(64)
    combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)


def _fixed_control(widget: QWidget) -> None:
    widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


def _cluster(*widgets: QWidget) -> QWidget:
    group = QWidget()
    group.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    row = QHBoxLayout(group)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    for widget in widgets:
        row.addWidget(widget)
    return group


class ConnectionBar(QFrame):
    """Present the connection controls without implementing their behavior."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("connectionBar")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)
        self._rows = QWidget()
        self._wrap = _WrapLayout(self._rows, spacing=8)
        layout.addWidget(self._rows, 1)

        self.source_label = QLabel("DEVICE")
        self.source_label.setObjectName("fieldLabel")
        _fixed_control(self.source_label)
        self.source_combo = QComboBox()
        self.source_combo.setObjectName("serialSourceCombo")
        _compact_combo(self.source_combo, contents=4)
        self.source_name_input = QLineEdit()
        self.source_name_input.setObjectName("serialSourceName")
        self.source_name_input.setPlaceholderText("Device name")
        self.source_name_input.setMinimumWidth(80)
        self.source_name_input.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.add_source_button = QPushButton("Add Device")
        self.add_source_button.setObjectName("addSerialSourceButton")
        _fixed_control(self.add_source_button)
        self.remove_source_button = QPushButton("Remove")
        self.remove_source_button.setObjectName("removeSerialSourceButton")
        _fixed_control(self.remove_source_button)
        self._wrap.addWidget(
            _cluster(
                self.source_label,
                self.source_combo,
                self.source_name_input,
                self.add_source_button,
                self.remove_source_button,
            )
        )

        self.profile_label = QLabel("PROFILE")
        self.profile_label.setObjectName("fieldLabel")
        _fixed_control(self.profile_label)
        self.profile_combo = QComboBox()
        self.profile_combo.setObjectName("deviceProfileCombo")
        _compact_combo(self.profile_combo, contents=5)
        self.profile_combo.addItem("Custom", None)
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
        _fixed_control(self.profile_menu_button)
        self.profile_status_label = QLabel("")
        self.profile_status_label.setObjectName("profileStatusLabel")
        self.profile_status_label.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred
        )
        self.profile_status_label.hide()
        self._wrap.addWidget(
            _cluster(
                self.profile_label,
                self.profile_combo,
                self.profile_menu_button,
                self.profile_status_label,
            )
        )

        self.port_label = QLabel("PORT")
        self.port_label.setObjectName("fieldLabel")
        _fixed_control(self.port_label)
        self.port_combo = QComboBox()
        self.port_combo.setObjectName("portCombo")
        _compact_combo(self.port_combo, contents=6)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.setToolTip("Refresh available serial ports")
        _fixed_control(self.refresh_button)
        self._wrap.addWidget(_cluster(self.port_label, self.port_combo, self.refresh_button))

        self.baud_label = QLabel("BAUD")
        self.baud_label.setObjectName("fieldLabel")
        _fixed_control(self.baud_label)
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
        _compact_combo(self.baud_combo, contents=4)
        self.baud_combo.setMinimumWidth(72)
        self._wrap.addWidget(_cluster(self.baud_label, self.baud_combo))

        self.status_indicator = QFrame()
        self.status_indicator.setObjectName("connectionStatusIndicator")
        self.status_indicator.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        status_layout = QHBoxLayout(self.status_indicator)
        status_layout.setContentsMargins(9, 0, 10, 0)
        status_layout.setSpacing(6)
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("connectionStatusDot")
        self.status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_dot)
        self.status_label = QLabel("DISCONNECTED")
        self.status_label.setObjectName("connectionStatusLabel")
        status_layout.addWidget(self.status_label)
        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("connectButton")
        _fixed_control(self.connect_button)
        self._wrap.addWidget(_cluster(self.status_indicator, self.connect_button))
        self._update_status_label_width()
        self._update_connect_button_width()

        self.set_connection_state("disconnected")
        self.set_source_count(1)
        self.set_profile_controls_enabled(True)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        margins = self.layout().contentsMargins()
        inner = max(1, width - margins.left() - margins.right())
        return self._wrap.heightForWidth(inner) + margins.top() + margins.bottom()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in {QEvent.Type.StyleChange, QEvent.Type.FontChange}:
            self._update_status_label_width()
            self._update_connect_button_width()

    def _update_status_label_width(self) -> None:
        self.status_label.ensurePolished()
        text_width = self.status_label.fontMetrics().horizontalAdvance(
            "CONNECTION ERROR"
        )
        self.status_label.setMinimumWidth(text_width)
        margins = self.status_indicator.layout().contentsMargins()
        self.status_indicator.setMinimumWidth(
            text_width
            + self.status_dot.sizeHint().width()
            + margins.left()
            + margins.right()
            + 6
        )

    def _update_connect_button_width(self) -> None:
        self.connect_button.ensurePolished()
        self.connect_button.setMinimumWidth(
            self.connect_button.fontMetrics().horizontalAdvance("Disconnect") + 24
        )

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
        self.profile_status_label.setVisible(bool(text))

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
