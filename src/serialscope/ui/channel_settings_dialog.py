"""Compact editor for channel aliases and user-supplied engineering units."""

from collections.abc import Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from serialscope.data import (
    AlarmLimits,
    CalculatedChannel,
    ChannelMetadataRegistry,
)
from serialscope.ui.calculated_channel_dialog import CalculatedChannelDialog
from serialscope.ui.unit_selector import UnitSelector


class ChannelSettingsDialog(QDialog):
    def __init__(
        self,
        registry: ChannelMetadataRegistry,
        parent: QWidget | None = None,
        *,
        calculated_channels: tuple[CalculatedChannel, ...] = (),
        available_names: tuple[str, ...] = (),
        latest_values: Mapping[str, int | float] | None = None,
        calculated_errors: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._registry = registry
        self.calculated_channels = list(calculated_channels)
        self._available_names = available_names
        self._latest_values = dict(latest_values or {})
        self._calculated_errors = dict(calculated_errors or {})
        self.unit_selectors: dict[str, UnitSelector] = {}
        self.alias_editors: dict[str, QLineEdit] = {}
        self.alarm_editors: dict[str, tuple[QLineEdit, QLineEdit, QLineEdit, QLineEdit]] = {}
        self.setWindowTitle("Channel Settings")
        self.setObjectName("channelSettingsDialog")
        self.setMinimumSize(980, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(14)
        calculated_names = {channel.name for channel in self.calculated_channels}
        physical_names = tuple(
            name for name in registry.source_names if name not in calculated_names
        )

        physical_group = QGroupBox("Physical channels")
        physical_group.setObjectName("channelSettingsSection")
        physical_layout = QVBoxLayout(physical_group)
        physical_layout.setContentsMargins(10, 16, 10, 10)
        physical_layout.setSpacing(8)

        self.table = QTableWidget(len(physical_names), 7)
        self.table.setObjectName("channelSettingsTable")
        self.table.setHorizontalHeaderLabels(
            ["Original Name", "Alias", "Unit", "Low-Low", "Low", "High", "High-High"]
        )
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(72)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for column in range(3, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setWordWrap(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        for row, source_name in enumerate(physical_names):
            presentation = registry.get(source_name)
            source_item = QTableWidgetItem(source_name)
            source_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            source_item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            )
            self.table.setItem(row, 0, source_item)

            alias_edit = self._make_editor(
                presentation.alias, "channelSettingsAlias", "Alias"
            )
            self.alias_editors[source_name] = alias_edit
            self.table.setCellWidget(row, 1, alias_edit)

            unit_selector = UnitSelector(presentation.unit)
            self.table.setCellWidget(row, 2, unit_selector)
            self.unit_selectors[source_name] = unit_selector

            alarm_fields = []
            for column, value, placeholder in (
                (3, presentation.alarms.low_low, "Low-Low"),
                (4, presentation.alarms.low, "Low"),
                (5, presentation.alarms.high, "High"),
                (6, presentation.alarms.high_high, "High-High"),
            ):
                editor = self._make_editor(
                    "" if value is None else f"{value:g}",
                    "channelSettingsAlarm",
                    placeholder,
                )
                alarm_fields.append(editor)
                self.table.setCellWidget(row, column, editor)
            self.alarm_editors[source_name] = tuple(alarm_fields)
            self.table.setRowHeight(row, 42)
        for column in range(3, 7):
            self.table.setColumnWidth(column, 92)
        if self.table.rowCount():
            self.table.setCurrentCell(0, 1)
            self.table.scrollToTop()
        physical_layout.addWidget(self.table)
        layout.addWidget(physical_group, 1)

        calculated_group = QGroupBox("Calculated channels")
        calculated_group.setObjectName("channelSettingsSection")
        calculated_layout = QVBoxLayout(calculated_group)
        calculated_layout.setContentsMargins(10, 16, 10, 10)
        calculated_layout.setSpacing(8)

        self.calculated_empty_label = QLabel("No calculated channels configured")
        self.calculated_empty_label.setObjectName("calculatedChannelsEmpty")
        self.calculated_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        calculated_layout.addWidget(self.calculated_empty_label)

        self.calculated_table = QTableWidget(0, 4)
        self.calculated_table.setObjectName("calculatedChannelsTable")
        self.calculated_table.setHorizontalHeaderLabels(
            ["Name", "Expression", "Unit", "Status"]
        )
        calculated_header = self.calculated_table.horizontalHeader()
        calculated_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        calculated_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        calculated_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        calculated_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.calculated_table.verticalHeader().hide()
        self.calculated_table.verticalHeader().setDefaultSectionSize(32)
        self.calculated_table.setAlternatingRowColors(True)
        self.calculated_table.setShowGrid(False)
        self.calculated_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.calculated_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.calculated_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        calculated_layout.addWidget(self.calculated_table)

        calculated_buttons = QHBoxLayout()
        self.add_calculated_button = QPushButton("+ Add Calculated Channel")
        self.add_calculated_button.setObjectName("addCalculatedButton")
        self.edit_calculated_button = QPushButton("Edit")
        self.delete_calculated_button = QPushButton("Delete")
        self.delete_calculated_button.setObjectName("deleteCalculatedButton")
        self.add_calculated_button.clicked.connect(self._add_calculated)
        self.edit_calculated_button.clicked.connect(self._edit_calculated)
        self.delete_calculated_button.clicked.connect(self._delete_calculated)
        calculated_buttons.addWidget(self.add_calculated_button)
        calculated_buttons.addWidget(self.edit_calculated_button)
        calculated_buttons.addWidget(self.delete_calculated_button)
        calculated_buttons.addStretch()
        calculated_layout.addLayout(calculated_buttons)
        layout.addWidget(calculated_group, 1)
        self._refresh_calculated_table()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            ok_button.setObjectName("dialogPrimaryButton")
        if cancel_button is not None:
            cancel_button.setObjectName("dialogSecondaryButton")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _make_editor(text: str, object_name: str, placeholder: str) -> QLineEdit:
        editor = QLineEdit(text)
        editor.setObjectName(object_name)
        editor.setPlaceholderText(placeholder)
        editor.setClearButtonEnabled(False)
        return editor

    def apply(self) -> None:
        for row in range(self.table.rowCount()):
            source_name = self.table.item(row, 0).text()
            limits = AlarmLimits(
                *(self._optional_float(editor.text()) for editor in self.alarm_editors[source_name])
            )
            self._registry.set(
                source_name,
                self.alias_editors[source_name].text(),
                self.unit_selectors[source_name].unit,
                limits,
            )
        for channel in self.calculated_channels:
            current = self._registry.get(channel.name)
            self._registry.set(
                channel.name, current.alias, channel.unit, current.alarms
            )

    def _reserved_names(self, *, exclude: str | None = None) -> tuple[str, ...]:
        names = [
            *self._available_names,
            *(self._registry.source_names),
            *(channel.name for channel in self.calculated_channels),
        ]
        return tuple(
            name for name in dict.fromkeys(names) if name.casefold() != (exclude or "").casefold()
        )

    def _refresh_calculated_table(self) -> None:
        self.calculated_table.setRowCount(len(self.calculated_channels))
        for row, channel in enumerate(self.calculated_channels):
            error = self._calculated_errors.get(channel.name)
            status = error or "Valid"
            values = (channel.name, channel.expression, channel.unit, status)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, channel.channel_id)
                self.calculated_table.setItem(row, column, item)
        has_rows = bool(self.calculated_channels)
        self.calculated_empty_label.setVisible(not has_rows)
        self.calculated_table.setVisible(has_rows)
        self.edit_calculated_button.setEnabled(has_rows)
        self.delete_calculated_button.setEnabled(has_rows)

    def _selected_calculated_index(self) -> int:
        row = self.calculated_table.currentRow()
        return row if 0 <= row < len(self.calculated_channels) else -1

    def _add_calculated(self) -> None:
        dialog = CalculatedChannelDialog(
            available_names=self._available_names,
            latest_values=self._latest_values,
            reserved_names=self._reserved_names(),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.calculated_channels.append(dialog.calculated_channel)
        self._refresh_calculated_table()

    def _edit_calculated(self) -> None:
        index = self._selected_calculated_index()
        if index < 0:
            return
        current = self.calculated_channels[index]
        dialog = CalculatedChannelDialog(
            available_names=self._available_names,
            latest_values=self._latest_values,
            reserved_names=self._reserved_names(exclude=current.name),
            existing=current,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.calculated_channels[index] = dialog.calculated_channel
        self._refresh_calculated_table()

    def _delete_calculated(self) -> None:
        index = self._selected_calculated_index()
        if index < 0:
            return
        del self.calculated_channels[index]
        self._refresh_calculated_table()

    @staticmethod
    def _optional_float(text: str) -> float | None:
        return None if not text.strip() else float(text.strip())

    def _validate_and_accept(self) -> None:
        first_error: QLineEdit | None = None
        try:
            for source_name, editors in self.alarm_editors.items():
                for editor in editors:
                    editor.setProperty("validationState", "")
                    editor.style().unpolish(editor)
                    editor.style().polish(editor)
                AlarmLimits(*(self._optional_float(editor.text()) for editor in editors))
        except ValueError as error:
            for editors in self.alarm_editors.values():
                try:
                    AlarmLimits(*(self._optional_float(editor.text()) for editor in editors))
                except ValueError:
                    for editor in editors:
                        if editor.text().strip():
                            editor.setProperty("validationState", "error")
                            editor.style().unpolish(editor)
                            editor.style().polish(editor)
                            if first_error is None:
                                first_error = editor
            QMessageBox.warning(self, "Invalid alarm limits", str(error))
            if first_error is not None:
                first_error.setFocus()
            return
        self.accept()
