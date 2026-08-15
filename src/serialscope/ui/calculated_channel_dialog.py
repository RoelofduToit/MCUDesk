"""Editor for one calculated / virtual channel."""

from collections.abc import Mapping

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from serialscope.data import (
    CalculatedChannel,
    CalculatedChannelError,
    ExpressionError,
    bindings_for_expression,
    evaluate_expression,
    expression_names,
)
from serialscope.ui.unit_selector import UnitSelector


class CalculatedChannelDialog(QDialog):
    """Collect a name, expression, and unit with live validation."""

    def __init__(
        self,
        *,
        available_names: tuple[str, ...] = (),
        latest_values: Mapping[str, int | float] | None = None,
        reserved_names: tuple[str, ...] = (),
        existing: CalculatedChannel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._available_names = available_names
        self._latest_values = dict(latest_values or {})
        self._reserved = {
            name.casefold()
            for name in reserved_names
            if existing is None or name.casefold() != existing.name.casefold()
        }
        self._existing_id = existing.channel_id if existing is not None else None
        self.setWindowTitle(
            "Edit Calculated Channel" if existing is not None else "Add Calculated Channel"
        )
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        form = QFormLayout()
        self.name_input = QLineEdit(existing.name if existing is not None else "")
        self.name_input.setPlaceholderText("Pressure Drop")
        form.addRow("Name", self.name_input)

        self.expression_input = QLineEdit(
            existing.expression if existing is not None else ""
        )
        self.expression_input.setPlaceholderText("Pressure_In - Pressure_Out")
        form.addRow("Expression", self.expression_input)

        insert_row = QHBoxLayout()
        self.channel_combo = QComboBox()
        for name in available_names:
            self.channel_combo.addItem(name, name)
        self.insert_button = QPushButton("Insert channel")
        self.insert_button.clicked.connect(self._insert_channel)
        self.insert_button.setEnabled(bool(available_names))
        insert_row.addWidget(self.channel_combo, 1)
        insert_row.addWidget(self.insert_button)
        form.addRow("", insert_row)

        self.unit_selector = UnitSelector(existing.unit if existing is not None else "")
        form.addRow("Unit", self.unit_selector)
        layout.addLayout(form)

        self.status_label = QLabel()
        self.status_label.setObjectName("calculatedChannelStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.preview_label = QLabel()
        self.preview_label.setObjectName("calculatedChannelPreview")
        self.preview_label.setWordWrap(True)
        layout.addWidget(self.preview_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.name_input.textChanged.connect(self._refresh_status)
        self.expression_input.textChanged.connect(self._refresh_status)
        self._refresh_status()

    @property
    def calculated_channel(self) -> CalculatedChannel:
        return CalculatedChannel.create(
            self.name_input.text(),
            self.expression_input.text(),
            unit=self.unit_selector.unit,
            available_names=self._available_names,
            channel_id=self._existing_id,
        )

    def _insert_channel(self) -> None:
        name = self.channel_combo.currentData()
        if not name:
            return
        from serialscope.data import identifier_for

        identifier = identifier_for(str(name))
        cursor = self.expression_input.cursorPosition()
        current = self.expression_input.text()
        self.expression_input.setText(current[:cursor] + identifier + current[cursor:])
        self.expression_input.setCursorPosition(cursor + len(identifier))
        self.expression_input.setFocus()

    def _refresh_status(self) -> None:
        name = self.name_input.text().strip()
        expression = self.expression_input.text().strip()
        if not name:
            self.status_label.setText("Enter a unique calculated channel name.")
            self.preview_label.setText("Current value: —")
            return
        if name.casefold() in self._reserved:
            self.status_label.setText("A channel with this name already exists.")
            self.preview_label.setText("Current value: —")
            return
        if not expression:
            self.status_label.setText("Enter an expression that uses existing channels.")
            self.preview_label.setText("Current value: —")
            return
        try:
            bindings = bindings_for_expression(expression, self._available_names)
            variables: dict[str, int | float] = {}
            missing: list[str] = []
            for identifier in expression_names(expression):
                source = bindings.get(identifier, identifier)
                if source in self._latest_values:
                    variables[identifier] = self._latest_values[source]
                else:
                    missing.append(source)
            if missing:
                self.status_label.setText(
                    "Expression is valid. Waiting for: " + ", ".join(missing) + "."
                )
                self.preview_label.setText("Current value: —")
                return
            value = evaluate_expression(expression, variables)
        except (ExpressionError, CalculatedChannelError) as error:
            self.status_label.setText(str(error))
            self.preview_label.setText("Current value: —")
            return
        unit = self.unit_selector.unit
        formatted = f"{value:g}"
        self.status_label.setText("Expression is valid.")
        self.preview_label.setText(
            f"Current value: {formatted}{f' {unit}' if unit else ''}"
        )

    def _validate_and_accept(self) -> None:
        try:
            self.calculated_channel
        except (ExpressionError, CalculatedChannelError) as error:
            self.status_label.setText(str(error))
            return
        name = self.name_input.text().strip()
        if name.casefold() in self._reserved:
            self.status_label.setText("A channel with this name already exists.")
            return
        self.accept()
