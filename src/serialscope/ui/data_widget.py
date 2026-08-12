"""Large tabular presentation of detected structured channels."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from serialscope.parsing import ChannelUpdate


class DataWidget(QWidget):
    """Display the latest channel values in stable insertion order."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dataWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self.empty_label = QLabel("No structured channels detected.")
        self.empty_label.setObjectName("dataEmptyLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label, 1)

        self.table = QTableWidget(0, 2)
        self.table.setObjectName("channelDataTable")
        self.table.setHorizontalHeaderLabels(["Channel", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.hide()
        layout.addWidget(self.table, 1)

        self._rows: dict[str, int] = {}

    def update_channels(self, update: ChannelUpdate) -> None:
        """Apply the same immutable channel update used by the compact view."""
        if update.replace_channels and tuple(self._rows) != update.names:
            self.reset()
        self._add_missing_channels(update.names)

        for name, value in zip(update.names, update.values, strict=True):
            self.table.item(self._rows[name], 1).setText(str(value))

    def reset(self) -> None:
        """Clear channel state and restore the empty presentation."""
        self.table.setRowCount(0)
        self._rows.clear()
        self.table.hide()
        self.empty_label.show()

    def value_text(self, name: str) -> str | None:
        row = self._rows.get(name)
        return self.table.item(row, 1).text() if row is not None else None

    @property
    def channel_names(self) -> tuple[str, ...]:
        return tuple(self._rows)

    def _add_missing_channels(self, names: tuple[str, ...]) -> None:
        for name in names:
            if name in self._rows:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem("—"))
            self._rows[name] = row
        if self._rows:
            self.empty_label.hide()
            self.table.show()
