"""Settings dialog for one read-only Modbus RTU device."""

from collections.abc import Callable, Sequence

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from serialscope.modbus.client import (
    ModbusClientError,
    create_serial_transport,
    probe_modbus_connection,
)
from serialscope.modbus.model import (
    DEFAULT_INTERVAL_MS,
    MAX_INTERVAL_MS,
    MIN_INTERVAL_MS,
    MODBUS_PARITIES,
    STOP_BITS_OPTIONS,
    ModbusConnectionSettings,
    ModbusRegister,
    ModbusRtuConfiguration,
    ModbusRtuConfigurationError,
)
from serialscope.profiles import DeviceProfile
from serialscope.serial import SerialPortInfo
from serialscope.ui.modbus_register_dialog import ModbusRegisterDialog


_KIND_LABELS = {"holding": "Holding", "input": "Input"}
_TYPE_LABELS = {
    "uint16": "UInt16",
    "int16": "Int16",
    "uint32": "UInt32",
    "int32": "Int32",
    "float32": "Float32",
    "float64": "Float64",
}
_PARITY_LABELS = (("none", "None"), ("even", "Even"), ("odd", "Odd"))
_BAUD_RATES = ("9600", "19200", "38400", "57600", "115200", "230400")


class _TestConnectionWorker(QObject):
    succeeded = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        port: str,
        configuration: ModbusRtuConfiguration,
        transport_factory: Callable[..., object],
    ) -> None:
        super().__init__()
        self._port = port
        self._configuration = configuration
        self._transport_factory = transport_factory

    @Slot()
    def run(self) -> None:
        try:
            transport = self._transport_factory(self._port, self._configuration.connection)
            message = probe_modbus_connection(transport, self._configuration)
        except ModbusClientError as error:
            self.failed.emit(str(error))
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.succeeded.emit(message)
        self.finished.emit()


class ModbusDeviceDialog(QDialog):
    """Configure a Modbus RTU source without adding main-window controls."""

    def __init__(
        self,
        *,
        profiles: Sequence[DeviceProfile] = (),
        ports: Sequence[SerialPortInfo] = (),
        configuration: ModbusRtuConfiguration | None = None,
        selected_profile_id: str | None = None,
        selected_port: str | None = None,
        occupied_ports: dict[str, str] | None = None,
        transport_factory: Callable[..., object] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("modbusDeviceDialog")
        self.setWindowTitle("Modbus RTU Device")
        self.setModal(True)
        self.setMinimumSize(640, 520)
        self.resize(720, 580)
        self._profiles = tuple(profiles)
        self._occupied_ports = dict(occupied_ports or {})
        self._transport_factory = transport_factory or create_serial_transport
        self._registers: list[ModbusRegister] = list(
            (configuration or ModbusRtuConfiguration()).registers
        )
        self._connect_requested = False
        self._test_thread: QThread | None = None
        self._test_worker: _TestConnectionWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(12)

        profile_group = QGroupBox("Device Profile")
        profile_form = QFormLayout(profile_group)
        self.profile_combo = QComboBox()
        self.profile_combo.setObjectName("modbusProfileCombo")
        self.profile_combo.addItem("New Modbus profile", None)
        for profile in self._profiles:
            self.profile_combo.addItem(profile.name, profile.profile_id)
        if selected_profile_id:
            index = self.profile_combo.findData(selected_profile_id)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
        self.profile_combo.currentIndexChanged.connect(self._load_selected_profile)
        profile_form.addRow("Profile", self.profile_combo)
        layout.addWidget(profile_group)

        connection = configuration.connection if configuration else ModbusConnectionSettings()
        connection_group = QGroupBox("Connection")
        form = QGridLayout(connection_group)
        form.setContentsMargins(10, 8, 10, 8)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        self.port_combo = QComboBox()
        self.port_combo.setObjectName("modbusPortCombo")
        for port in ports:
            label = port.device
            if port.description and port.description not in {port.device, "n/a"}:
                label = f"{port.device} — {port.description}"
            self.port_combo.addItem(label, port.device)
        if selected_port:
            index = self.port_combo.findData(selected_port)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
        form.addWidget(QLabel("Port"), 0, 0)
        form.addWidget(self.port_combo, 0, 1, 1, 3)

        self.baud_combo = QComboBox()
        for rate in _BAUD_RATES:
            self.baud_combo.addItem(rate, int(rate))
        baud_index = self.baud_combo.findData(connection.baud_rate)
        if baud_index < 0:
            self.baud_combo.addItem(str(connection.baud_rate), connection.baud_rate)
            baud_index = self.baud_combo.findData(connection.baud_rate)
        self.baud_combo.setCurrentIndex(max(0, baud_index))
        form.addWidget(QLabel("Baud"), 1, 0)
        form.addWidget(self.baud_combo, 1, 1)

        self.parity_combo = QComboBox()
        for value, label in _PARITY_LABELS:
            self.parity_combo.addItem(label, value)
        self.parity_combo.setCurrentIndex(
            max(0, self.parity_combo.findData(connection.parity))
        )
        form.addWidget(QLabel("Parity"), 1, 2)
        form.addWidget(self.parity_combo, 1, 3)

        self.stop_bits_combo = QComboBox()
        for value in STOP_BITS_OPTIONS:
            self.stop_bits_combo.addItem(str(value), value)
        self.stop_bits_combo.setCurrentIndex(
            max(0, self.stop_bits_combo.findData(connection.stop_bits))
        )
        form.addWidget(QLabel("Stop bits"), 2, 0)
        form.addWidget(self.stop_bits_combo, 2, 1)

        self.slave_spin = QSpinBox()
        self.slave_spin.setRange(1, 247)
        self.slave_spin.setValue(connection.slave_id)
        form.addWidget(QLabel("Slave ID"), 2, 2)
        form.addWidget(self.slave_spin, 2, 3)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(MIN_INTERVAL_MS, MAX_INTERVAL_MS)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.setValue(
            configuration.interval_ms if configuration else DEFAULT_INTERVAL_MS
        )
        form.addWidget(QLabel("Poll interval"), 3, 0)
        form.addWidget(self.interval_spin, 3, 1)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)
        layout.addWidget(connection_group)

        register_group = QGroupBox("Registers")
        register_layout = QVBoxLayout(register_group)
        self.register_empty = QLabel("No registers yet. Add the values this device should poll.")
        self.register_empty.setObjectName("mutedLabel")
        self.register_empty.setWordWrap(True)
        register_layout.addWidget(self.register_empty)
        self.register_table = QTableWidget(0, 5)
        self.register_table.setObjectName("modbusRegisterTable")
        self.register_table.setHorizontalHeaderLabels(
            ("Enabled", "Name", "Type", "Address", "Data Type")
        )
        self.register_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.register_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.register_table.verticalHeader().setVisible(False)
        self.register_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.register_table.setMinimumHeight(120)
        header = self.register_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.register_table.doubleClicked.connect(lambda _index: self._edit_register())
        register_layout.addWidget(self.register_table, 1)

        buttons_row = QHBoxLayout()
        add_button = QPushButton("Add Register")
        add_button.setObjectName("modbusAddRegisterButton")
        add_button.clicked.connect(self._add_register)
        remove_button = QPushButton("Remove")
        remove_button.setObjectName("modbusRemoveRegisterButton")
        remove_button.clicked.connect(self._remove_register)
        edit_button = QPushButton("Edit Register...")
        edit_button.setObjectName("modbusEditRegisterButton")
        edit_button.clicked.connect(self._edit_register)
        buttons_row.addWidget(add_button)
        buttons_row.addWidget(edit_button)
        buttons_row.addWidget(remove_button)
        buttons_row.addStretch()
        register_layout.addLayout(buttons_row)
        layout.addWidget(register_group, 1)

        test_row = QHBoxLayout()
        self.test_button = QPushButton("Test Connection")
        self.test_button.setObjectName("modbusTestConnectionButton")
        self.test_button.clicked.connect(self._test_connection)
        test_row.addWidget(self.test_button)
        self.status_label = QLabel("Not tested")
        self.status_label.setObjectName("modbusStatusLabel")
        self.status_label.setWordWrap(True)
        test_row.addWidget(self.status_label, 1)
        layout.addLayout(test_row)

        buttons = QDialogButtonBox()
        self.cancel_button = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.save_button = buttons.addButton(
            "Save", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.save_connect_button = buttons.addButton(
            "Save and Connect", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.save_button.setObjectName("modbusSaveButton")
        self.save_connect_button.setObjectName("modbusSaveConnectButton")
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._save)
        self.save_connect_button.clicked.connect(self._save_and_connect)
        layout.addWidget(buttons)
        self._refresh_register_table()

    @property
    def connect_requested(self) -> bool:
        return self._connect_requested

    def selected_profile_id(self) -> str | None:
        value = self.profile_combo.currentData()
        return str(value) if value else None

    def selected_port(self) -> str | None:
        value = self.port_combo.currentData()
        return str(value) if value else None

    def configuration(self) -> ModbusRtuConfiguration:
        return ModbusRtuConfiguration(
            connection=ModbusConnectionSettings(
                baud_rate=int(self.baud_combo.currentData()),
                parity=str(self.parity_combo.currentData()),
                stop_bits=int(self.stop_bits_combo.currentData()),
                slave_id=self.slave_spin.value(),
            ),
            interval_ms=self.interval_spin.value(),
            registers=tuple(self._registers),
        )

    def _refresh_register_table(self) -> None:
        self.register_table.setRowCount(len(self._registers))
        for row, register in enumerate(self._registers):
            enabled = QTableWidgetItem("Yes" if register.enabled else "No")
            enabled.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.register_table.setItem(row, 0, enabled)
            self.register_table.setItem(row, 1, QTableWidgetItem(register.name))
            self.register_table.setItem(
                row, 2, QTableWidgetItem(_KIND_LABELS.get(register.kind, register.kind))
            )
            address = QTableWidgetItem(str(register.address))
            address.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.register_table.setItem(row, 3, address)
            self.register_table.setItem(
                row, 4, QTableWidgetItem(_TYPE_LABELS.get(register.data_type, register.data_type))
            )
        self.register_empty.setVisible(not self._registers)
        if self._registers and self.register_table.currentRow() < 0:
            self.register_table.selectRow(0)

    def _selected_register_index(self) -> int:
        return self.register_table.currentRow()

    def _add_register(self) -> None:
        dialog = ModbusRegisterDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._registers.append(dialog.register())
            ModbusRtuConfiguration(
                connection=self.configuration().connection,
                interval_ms=self.interval_spin.value(),
                registers=tuple(self._registers),
            )
        except ModbusRtuConfigurationError as error:
            self._registers.pop()
            QMessageBox.warning(self, "Invalid register", str(error))
            return
        self._refresh_register_table()
        self.register_table.selectRow(len(self._registers) - 1)

    def _edit_register(self) -> None:
        index = self._selected_register_index()
        if index < 0 or index >= len(self._registers):
            return
        dialog = ModbusRegisterDialog(self._registers[index], parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        previous = self._registers[index]
        try:
            self._registers[index] = dialog.register()
            ModbusRtuConfiguration(
                connection=self.configuration().connection,
                interval_ms=self.interval_spin.value(),
                registers=tuple(self._registers),
            )
        except ModbusRtuConfigurationError as error:
            self._registers[index] = previous
            QMessageBox.warning(self, "Invalid register", str(error))
            return
        self._refresh_register_table()
        self.register_table.selectRow(index)

    def _remove_register(self) -> None:
        index = self._selected_register_index()
        if index < 0 or index >= len(self._registers):
            return
        del self._registers[index]
        self._refresh_register_table()

    def _load_selected_profile(self) -> None:
        profile_id = self.selected_profile_id()
        if profile_id is None:
            return
        profile = next(
            (item for item in self._profiles if item.profile_id == profile_id),
            None,
        )
        if profile is None or profile.modbus is None:
            return
        configuration = profile.modbus
        self._registers = list(configuration.registers)
        connection = configuration.connection
        baud_index = self.baud_combo.findData(connection.baud_rate)
        if baud_index < 0:
            self.baud_combo.addItem(str(connection.baud_rate), connection.baud_rate)
            baud_index = self.baud_combo.findData(connection.baud_rate)
        self.baud_combo.setCurrentIndex(max(0, baud_index))
        self.parity_combo.setCurrentIndex(
            max(0, self.parity_combo.findData(connection.parity))
        )
        self.stop_bits_combo.setCurrentIndex(
            max(0, self.stop_bits_combo.findData(connection.stop_bits))
        )
        self.slave_spin.setValue(connection.slave_id)
        self.interval_spin.setValue(configuration.interval_ms)
        if profile.last_port:
            port_index = self.port_combo.findData(profile.last_port)
            if port_index >= 0:
                self.port_combo.setCurrentIndex(port_index)
        self._refresh_register_table()

    def _test_connection(self) -> None:
        port = self.selected_port()
        if not port:
            self.status_label.setText("Select a serial port.")
            return
        owner = self._occupied_ports.get(port)
        if owner:
            self.status_label.setText(f"{port} is already connected as {owner}.")
            return
        try:
            configuration = self.configuration()
        except ModbusRtuConfigurationError as error:
            self.status_label.setText(str(error))
            return
        self.test_button.setEnabled(False)
        self.status_label.setText("Testing connection...")
        worker = _TestConnectionWorker(port, configuration, self._transport_factory)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._test_succeeded)
        worker.failed.connect(self._test_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self.test_button.setEnabled(True))
        self._test_thread = thread
        self._test_worker = worker
        thread.start()

    def _test_succeeded(self, message: str) -> None:
        self.status_label.setText(message)

    def _test_failed(self, message: str) -> None:
        self.status_label.setText(message)

    def _save(self) -> None:
        self._connect_requested = False
        if self._accept_if_valid():
            self.accept()

    def _save_and_connect(self) -> None:
        self._connect_requested = True
        if self._accept_if_valid():
            self.accept()

    def _accept_if_valid(self) -> bool:
        try:
            configuration = self.configuration()
        except ModbusRtuConfigurationError as error:
            QMessageBox.warning(self, "Invalid Modbus configuration", str(error))
            return False
        if self._connect_requested and not configuration.enabled_registers:
            QMessageBox.warning(
                self,
                "Invalid Modbus configuration",
                "Configure at least one enabled register before connecting.",
            )
            return False
        if self._connect_requested and not self.selected_port():
            QMessageBox.warning(
                self,
                "Invalid Modbus configuration",
                "Select a serial port before connecting.",
            )
            return False
        return True

    def closeEvent(self, event) -> None:  # noqa: N802
        thread = self._test_thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(1_000)
        super().closeEvent(event)
