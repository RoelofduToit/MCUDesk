"""Large tabular presentation of detected structured channels."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from serialscope.parsing import ChannelUpdate
from serialscope.replay import ReplaySession
from serialscope.data import (
    AlarmState,
    ChannelKey,
    ChannelMetadataRegistry,
    evaluate_alarm,
)
from serialscope.ui.status_badge import (
    apply_status_row_height,
    make_status_badge,
    status_column_width,
    status_presentation,
    table_value_font,
)

_VALUE_COLUMN_WIDTH = 120
_UNIT_COLUMN_WIDTH = 88


def _status_badge(text: str, style_state: str, kind: str) -> QWidget:
    cell, _badge = make_status_badge(
        text,
        style_state,
        kind,
        object_name="channelDataStatusBadge",
        cell_name="channelDataStatusCell",
    )
    return cell


class DataWidget(QWidget):
    """Display the latest channel values in stable insertion order."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dataWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        self.empty_label = QLabel("No structured channels detected.")
        self.empty_label.setObjectName("dataEmptyLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label, 1)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("channelDataTable")
        self.table.setHorizontalHeaderLabels(["Channel", "Value", "Unit", "Status", "Source"])
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._syncing_columns = False
        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        header.setStretchLastSection(False)
        header.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        header.setMinimumSectionSize(48)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._status_min_width = 0
        self.table.verticalHeader().hide()
        apply_status_row_height(self.table)
        self.table.installEventFilter(self)
        self.table.horizontalHeader().installEventFilter(self)
        self.table.viewport().installEventFilter(self)
        self._sync_column_widths()
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setMouseTracking(True)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.hide()
        layout.addWidget(self.table, 1)

        self._rows: dict[str, int] = {}
        self._metadata = ChannelMetadataRegistry()
        self._latest_values: dict[str, int | float] = {}
        self._source_names: dict[str, str] = {}
        self._syncing_columns = False
        self.set_source_count(1)

    def set_source_count(self, count: int) -> None:
        """Show source identity only when it disambiguates multiple devices."""
        hidden = count < 2
        self.table.setColumnHidden(4, hidden)
        if hidden:
            self.table.setColumnWidth(4, 0)
        self._sync_column_widths()

    def remove_source(self, source_id: str) -> None:
        prefix = f"{source_id}\x1f"
        retained = [name for name in self._rows if not name.startswith(prefix)]
        values = {name: self._latest_values[name] for name in retained if name in self._latest_values}
        sources = {name: self._source_names.get(name, "") for name in retained}
        self.reset()
        self._source_names = sources
        if retained:
            self._add_missing_channels(tuple(retained))
            for name, value in values.items():
                self._latest_values[name] = value
                self.table.item(self._rows[name], 1).setText(str(value))
                self._update_status(name)

    def update_channels(self, update: ChannelUpdate) -> None:
        """Apply the same immutable channel update used by the compact view."""
        if update.replace_channels and tuple(self._rows) != update.names:
            self.reset()
        self._add_missing_channels(update.names)

        for name, value in zip(update.names, update.values, strict=True):
            self._latest_values[name] = value
            self.table.item(self._rows[name], 1).setText(str(value))
            self._update_status(name)

    def update_source(
        self, source_id: str, display_name: str, update: ChannelUpdate
    ) -> None:
        names = tuple(f"{source_id}\x1f{name}" for name in update.names)
        self._source_names.update({name: display_name for name in names})
        self.update_channels(ChannelUpdate(names, update.values, False))

    def reset(self) -> None:
        """Clear channel state and restore the empty presentation."""
        self.table.setRowCount(0)
        self._rows.clear()
        self._latest_values.clear()
        self.table.hide()
        self.empty_label.show()

    def remove_channel(self, name: str | ChannelKey) -> None:
        if isinstance(name, ChannelKey):
            name = name.storage_key
        row = self._rows.pop(name, None)
        if row is None:
            return
        self.table.removeRow(row)
        self._latest_values.pop(name, None)
        self._source_names.pop(name, None)
        self._rows = {
            existing: (index if index < row else index - 1)
            for existing, index in self._rows.items()
        }
        if not self._rows:
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

    def value_text(self, name: str | ChannelKey) -> str | None:
        if isinstance(name, ChannelKey):
            name = name.storage_key
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
            self.table.setItem(row, 1, self._value_item("—"))
            unit_item = QTableWidgetItem("")
            unit_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row, 2, unit_item)
            status_item = QTableWidgetItem("UNKNOWN")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setData(Qt.ItemDataRole.UserRole, "unknown")
            self.table.setItem(row, 3, status_item)
            self.table.setCellWidget(
                row, 3, _status_badge("UNKNOWN", "unknown", "UNKNOWN")
            )
            self.table.setItem(row, 4, QTableWidgetItem(self._source_names.get(name, "")))
            self._rows[name] = row
        self.set_channel_metadata(self._metadata)
        apply_status_row_height(self.table)
        if self._rows:
            self.empty_label.hide()
            self.table.show()

    def _value_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        item.setFont(table_value_font())
        return item

    def eventFilter(self, watched: QWidget, event: QEvent) -> bool:  # noqa: N802
        if event.type() in {QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest}:
            if watched in {self.table, self.table.viewport(), self.table.horizontalHeader()}:
                self._sync_column_widths()
        return super().eventFilter(watched, event)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._status_min_width = status_column_width(self.table)
        self._sync_column_widths()
        apply_status_row_height(self.table)

    def _sync_column_widths(self) -> None:
        """Keep Value/Unit/Status fully visible; Channel absorbs leftover width."""
        if self._syncing_columns:
            return
        self._syncing_columns = True
        try:
            header = self.table.horizontalHeader()
            if self._status_min_width <= 0:
                self._status_min_width = status_column_width(self.table)
            header.resizeSection(1, _VALUE_COLUMN_WIDTH)
            header.resizeSection(2, _UNIT_COLUMN_WIDTH)
            header.resizeSection(3, self._status_min_width)
            if self.table.isColumnHidden(4):
                header.resizeSection(4, 0)
        finally:
            self._syncing_columns = False

    def status_text(self, name: str) -> str | None:
        row = self._rows.get(name)
        return self.table.item(row, 3).text() if row is not None else None

    def mark_value_unavailable(self, name: str | ChannelKey) -> None:
        """Keep the last number but mark the row as not currently measured."""
        if isinstance(name, ChannelKey):
            name = name.storage_key
        if name not in self._rows:
            return
        label, style_state, kind = status_presentation(AlarmState.UNKNOWN)
        item = self.table.item(self._rows[name], 3)
        item.setText(label)
        item.setData(Qt.ItemDataRole.UserRole, style_state)
        self.table.setCellWidget(
            self._rows[name], 3, _status_badge(label, style_state, kind)
        )

    def _update_status(self, source_name: str) -> None:
        row = self._rows.get(source_name)
        if row is None:
            return
        state = evaluate_alarm(
            self._latest_values.get(source_name),
            self._metadata.get(source_name).alarms,
        )
        label, style_state, kind = status_presentation(state)
        item = self.table.item(row, 3)
        item.setText(label)
        item.setData(Qt.ItemDataRole.UserRole, style_state)
        self.table.setCellWidget(row, 3, _status_badge(label, style_state, kind))
