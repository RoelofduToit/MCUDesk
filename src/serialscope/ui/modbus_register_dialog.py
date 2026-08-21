"""Compact editor for one Modbus register mapping."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from serialscope.modbus.model import (
    BYTE_ORDERS,
    DATA_TYPES,
    REGISTER_KINDS,
    WORD_ORDERS,
    ModbusRegister,
    ModbusRtuConfigurationError,
)


_KIND_LABELS = (("holding", "Holding Register"), ("input", "Input Register"))
_TYPE_LABELS = (
    ("uint16", "UInt16"),
    ("int16", "Int16"),
    ("uint32", "UInt32"),
    ("int32", "Int32"),
    ("float32", "Float32"),
    ("float64", "Float64"),
)
_BYTE_LABELS = (("big", "Big"), ("little", "Little"))
_WORD_LABELS = (("high_first", "High first"), ("low_first", "Low first"))


class ModbusRegisterDialog(QDialog):
    """Edit one register without owning serial or polling state."""

    def __init__(
        self,
        register: ModbusRegister | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("modbusRegisterDialog")
        self.setWindowTitle("Edit Register" if register else "Add Register")
        self.setModal(True)
        self.setMinimumWidth(400)
        current = register or ModbusRegister(name="Channel")
        layout = QFormLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)

        self.enabled_checkbox = QCheckBox("Enabled")
        self.enabled_checkbox.setChecked(current.enabled)
        layout.addRow("", self.enabled_checkbox)

        self.name_input = QLineEdit(current.name)
        self.name_input.setObjectName("modbusRegisterName")
        layout.addRow("Name", self.name_input)

        self.kind_combo = QComboBox()
        for value, label in _KIND_LABELS:
            self.kind_combo.addItem(label, value)
        self.kind_combo.setCurrentIndex(max(0, self.kind_combo.findData(current.kind)))
        layout.addRow("Register type", self.kind_combo)

        self.address_spin = QSpinBox()
        self.address_spin.setRange(0, 65535)
        self.address_spin.setValue(current.address)
        self.address_spin.setToolTip(
            "0-based protocol address. Some manuals display Holding Register 0 as 40001."
        )
        layout.addRow("Address (0-based)", self.address_spin)

        self.data_type_combo = QComboBox()
        for value, label in _TYPE_LABELS:
            self.data_type_combo.addItem(label, value)
        self.data_type_combo.setCurrentIndex(
            max(0, self.data_type_combo.findData(current.data_type))
        )
        self.data_type_combo.currentIndexChanged.connect(self._update_word_order_enabled)
        layout.addRow("Data type", self.data_type_combo)

        self.byte_order_combo = QComboBox()
        for value, label in _BYTE_LABELS:
            self.byte_order_combo.addItem(label, value)
        self.byte_order_combo.setCurrentIndex(
            max(0, self.byte_order_combo.findData(current.byte_order))
        )
        layout.addRow("Byte order", self.byte_order_combo)

        self.word_order_combo = QComboBox()
        for value, label in _WORD_LABELS:
            self.word_order_combo.addItem(label, value)
        self.word_order_combo.setCurrentIndex(
            max(0, self.word_order_combo.findData(current.word_order))
        )
        layout.addRow("Word order", self.word_order_combo)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setDecimals(4)
        self.scale_spin.setRange(-1_000_000, 1_000_000)
        self.scale_spin.setValue(current.scale)
        layout.addRow("Scale", self.scale_spin)

        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setDecimals(4)
        self.offset_spin.setRange(-1_000_000, 1_000_000)
        self.offset_spin.setValue(current.offset)
        layout.addRow("Offset", self.offset_spin)

        self.unit_input = QLineEdit(current.unit)
        self.unit_input.setPlaceholderText("Optional initial unit")
        layout.addRow("Unit", self.unit_input)

        self.description_input = QLineEdit(current.description)
        layout.addRow("Description", self.description_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self._update_word_order_enabled()

    def _update_word_order_enabled(self) -> None:
        data_type = self.data_type_combo.currentData()
        multi_word = data_type not in {"uint16", "int16"}
        self.word_order_combo.setEnabled(multi_word)

    def register(self) -> ModbusRegister:
        try:
            return ModbusRegister(
                name=self.name_input.text(),
                kind=str(self.kind_combo.currentData()),
                address=self.address_spin.value(),
                data_type=str(self.data_type_combo.currentData()),
                scale=self.scale_spin.value(),
                offset=self.offset_spin.value(),
                unit=self.unit_input.text(),
                enabled=self.enabled_checkbox.isChecked(),
                byte_order=str(self.byte_order_combo.currentData()),
                word_order=str(self.word_order_combo.currentData()),
                description=self.description_input.text(),
            )
        except ModbusRtuConfigurationError:
            raise
        except ValueError as error:
            raise ModbusRtuConfigurationError(str(error)) from error
