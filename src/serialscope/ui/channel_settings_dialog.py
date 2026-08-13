"""Compact editor for channel aliases and user-supplied engineering units."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from serialscope.data import ChannelMetadataRegistry


class ChannelSettingsDialog(QDialog):
    def __init__(
        self, registry: ChannelMetadataRegistry, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._registry = registry
        self.setWindowTitle("Channel Settings")
        self.setMinimumSize(620, 340)

        layout = QVBoxLayout(self)
        self.table = QTableWidget(len(registry.source_names), 3)
        self.table.setObjectName("channelSettingsTable")
        self.table.setHorizontalHeaderLabels(["Original Name", "Alias", "Unit"])
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
            self.table.setItem(row, 2, QTableWidgetItem(presentation.unit))
        layout.addWidget(self.table)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply(self) -> None:
        for row in range(self.table.rowCount()):
            self._registry.set(
                self.table.item(row, 0).text(),
                self.table.item(row, 1).text(),
                self.table.item(row, 2).text(),
            )
