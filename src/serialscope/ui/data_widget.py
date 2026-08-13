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
from serialscope.replay import ReplaySession
from serialscope.data import ChannelMetadataRegistry, evaluate_alarm


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

        self.table = QTableWidget(0, 4)
        self.table.setObjectName("channelDataTable")
        self.table.setHorizontalHeaderLabels(["Channel", "Value", "Unit", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.hide()
        layout.addWidget(self.table, 1)

        self._rows: dict[str, int] = {}
        self._metadata = ChannelMetadataRegistry()
        self._latest_values: dict[str, int | float] = {}

    def update_channels(self, update: ChannelUpdate) -> None:
        """Apply the same immutable channel update used by the compact view."""
        if update.replace_channels and tuple(self._rows) != update.names:
            self.reset()
        self._add_missing_channels(update.names)

        for name, value in zip(update.names, update.values, strict=True):
            self._latest_values[name] = value
            self.table.item(self._rows[name], 1).setText(str(value))
            self._update_status(name)

    def reset(self) -> None:
        """Clear channel state and restore the empty presentation."""
        self.table.setRowCount(0)
        self._rows.clear()
        self._latest_values.clear()
        self.table.hide()
        self.empty_label.show()

    def load_replay(self, session: ReplaySession) -> None:
        """Show the latest available value for every recorded channel."""
        self.reset()
        self._add_missing_channels(session.channel_names)
        latest = session.latest_values
        for name in session.channel_names:
            value = latest.get(name)
            if value is not None:
                self.table.item(self._rows[name], 1).setText(str(value))
                self._latest_values[name] = value
                self._update_status(name)

    def value_text(self, name: str) -> str | None:
        row = self._rows.get(name)
        return self.table.item(row, 1).text() if row is not None else None

    def set_channel_metadata(self, registry: ChannelMetadataRegistry) -> None:
        self._metadata = registry
        for source_name, row in self._rows.items():
            presentation = registry.get(source_name)
            name_item = self.table.item(row, 0)
            name_item.setText(presentation.display_name)
            name_item.setToolTip(f"Source: {source_name}")
            self.table.item(row, 2).setText(presentation.unit)
            self._update_status(source_name)

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
            self.table.setItem(row, 2, QTableWidgetItem(""))
            self.table.setItem(row, 3, QTableWidgetItem("UNKNOWN"))
            self._rows[name] = row
        self.set_channel_metadata(self._metadata)
        if self._rows:
            self.empty_label.hide()
            self.table.show()

    def status_text(self, name: str) -> str | None:
        row = self._rows.get(name)
        return self.table.item(row, 3).text() if row is not None else None

    def _update_status(self, source_name: str) -> None:
        row = self._rows.get(source_name)
        if row is None:
            return
        state = evaluate_alarm(
            self._latest_values.get(source_name),
            self._metadata.get(source_name).alarms,
        )
        item = self.table.item(row, 3)
        item.setText(state.value)
        item.setData(Qt.ItemDataRole.UserRole, state.style_state)
