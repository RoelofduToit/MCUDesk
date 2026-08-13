"""Compact editor for channel aliases and user-supplied engineering units."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from serialscope.data import AlarmLimits, ChannelMetadataRegistry
from serialscope.ui.unit_selector import UnitSelector


class ChannelSettingsDialog(QDialog):
    def __init__(
        self, registry: ChannelMetadataRegistry, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._registry = registry
        self.unit_selectors: dict[str, UnitSelector] = {}
        self.setWindowTitle("Channel Settings")
        self.setMinimumSize(980, 380)

        layout = QVBoxLayout(self)
        self.table = QTableWidget(len(registry.source_names), 7)
        self.table.setObjectName("channelSettingsTable")
        self.table.setHorizontalHeaderLabels(
            ["Original Name", "Alias", "Unit", "Low-Low", "Low", "High", "High-High"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.verticalHeader().hide()
        for row, source_name in enumerate(registry.source_names):
            presentation = registry.get(source_name)
            source_item = QTableWidgetItem(source_name)
            source_item.setFlags(source_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, source_item)
            self.table.setItem(row, 1, QTableWidgetItem(presentation.alias))
            unit_selector = UnitSelector(presentation.unit)
            self.table.setCellWidget(row, 2, unit_selector)
            self.unit_selectors[source_name] = unit_selector
            for column, value in enumerate(
                (
                    presentation.alarms.low_low,
                    presentation.alarms.low,
                    presentation.alarms.high,
                    presentation.alarms.high_high,
                ),
                start=3,
            ):
                self.table.setItem(
                    row, column, QTableWidgetItem("" if value is None else f"{value:g}")
                )
        layout.addWidget(self.table)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply(self) -> None:
        for row in range(self.table.rowCount()):
            limits = AlarmLimits(
                *(
                    self._optional_float(self.table.item(row, column).text())
                    for column in range(3, 7)
                )
            )
            self._registry.set(
                self.table.item(row, 0).text(),
                self.table.item(row, 1).text(),
                self.unit_selectors[self.table.item(row, 0).text()].unit,
                limits,
            )

    @staticmethod
    def _optional_float(text: str) -> float | None:
        return None if not text.strip() else float(text.strip())

    def _validate_and_accept(self) -> None:
        try:
            for row in range(self.table.rowCount()):
                AlarmLimits(
                    *(
                        self._optional_float(self.table.item(row, column).text())
                        for column in range(3, 7)
                    )
                )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid alarm limits", str(error))
            return
        self.accept()
