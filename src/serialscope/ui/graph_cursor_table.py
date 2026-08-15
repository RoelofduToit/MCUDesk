"""Structured presentation of values nearest the graph inspection cursor."""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from serialscope.data import AlarmState
from serialscope.ui.graph_display import format_cursor_time, format_graph_value


@dataclass(frozen=True, slots=True)
class GraphCursorRow:
    source_name: str
    display_name: str
    unit: str
    color: str
    cursor_time: float | None
    measurement_time: float | None
    value: int | float | None
    status: AlarmState | None


class GraphCursorTable(QTableWidget):
    """Reuse selected-channel rows while cursor values change rapidly."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 3, parent)
        self.setObjectName("graphCursorTable")
        self.setHorizontalHeaderLabels(("Channel", "Value", "Status"))
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(26)
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._source_names: tuple[str, ...] = ()
        self._channel_widgets: dict[str, QWidget] = {}
        self._channel_labels: dict[str, QLabel] = {}
        self._swatches: dict[str, QLabel] = {}
        self._value_items: dict[str, QTableWidgetItem] = {}
        self._status_labels: dict[str, QLabel] = {}
        self._resize_to_rows()

    @property
    def source_names(self) -> tuple[str, ...]:
        return self._source_names

    def set_cursor_values(self, rows: tuple[GraphCursorRow, ...]) -> None:
        """Update persistent rows, rebuilding only when selection changes."""
        source_names = tuple(row.source_name for row in rows)
        if source_names != self._source_names:
            self._rebuild(source_names)

        for row_index, row in enumerate(rows):
            self._set_row(row)
            self.setRowHeight(row_index, self.verticalHeader().defaultSectionSize())

    def clear_values(self) -> None:
        self._rebuild(())

    def update_presentation(
        self,
        source_name: str,
        display_name: str,
        unit: str,
    ) -> None:
        """Refresh an existing alias/unit without replacing its row widgets."""
        label = self._channel_labels.get(source_name)
        if label is None:
            return
        label.setText(display_name)
        label.setToolTip(f"Source: {source_name}")
        value_item = self._value_items[source_name]
        current_value = value_item.data(Qt.ItemDataRole.UserRole)
        value_item.setText(_value_with_unit(current_value, unit))

    def channel_text(self, source_name: str) -> str | None:
        label = self._channel_labels.get(source_name)
        return label.text() if label is not None else None

    def value_text(self, source_name: str) -> str | None:
        item = self._value_items.get(source_name)
        return item.text() if item is not None else None

    def status_text(self, source_name: str) -> str | None:
        label = self._status_labels.get(source_name)
        return label.text() if label is not None else None

    def measurement_tooltip(self, source_name: str) -> str | None:
        widget = self._channel_widgets.get(source_name)
        return widget.toolTip() if widget is not None else None

    def row_widget(self, source_name: str) -> QWidget | None:
        return self._channel_widgets.get(source_name)

    def swatch_color(self, source_name: str) -> str | None:
        swatch = self._swatches.get(source_name)
        return str(swatch.property("graphColor")) if swatch is not None else None

    def _rebuild(self, source_names: tuple[str, ...]) -> None:
        self.clearContents()
        self.setRowCount(len(source_names))
        self._source_names = source_names
        self._channel_widgets.clear()
        self._channel_labels.clear()
        self._swatches.clear()
        self._value_items.clear()
        self._status_labels.clear()
        for row, source_name in enumerate(source_names):
            channel_widget = QWidget()
            channel_widget.setObjectName("graphCursorChannel")
            layout = QHBoxLayout(channel_widget)
            layout.setContentsMargins(6, 0, 4, 0)
            layout.setSpacing(6)
            swatch = QLabel("●")
            swatch.setObjectName("graphCursorSwatch")
            layout.addWidget(swatch)
            label = QLabel(source_name)
            label.setObjectName("graphCursorChannelLabel")
            layout.addWidget(label, 1)
            self.setCellWidget(row, 0, channel_widget)

            value_item = QTableWidgetItem("—")
            value_item.setData(Qt.ItemDataRole.UserRole, None)
            value_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.setItem(row, 1, value_item)

            status_label = QLabel("—")
            status_label.setObjectName("graphCursorStatus")
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_label.setProperty("alarmState", "unknown")
            self.setCellWidget(row, 2, status_label)

            self._channel_widgets[source_name] = channel_widget
            self._channel_labels[source_name] = label
            self._swatches[source_name] = swatch
            self._value_items[source_name] = value_item
            self._status_labels[source_name] = status_label
        self._resize_to_rows()

    def _set_row(self, row: GraphCursorRow) -> None:
        label = self._channel_labels[row.source_name]
        label.setText(row.display_name)
        label.setToolTip(f"Source: {row.source_name}")

        swatch = self._swatches[row.source_name]
        swatch.setProperty("graphColor", row.color)
        swatch.setStyleSheet(
            f"color: {row.color}; background-color: transparent; border: none;"
        )

        value_item = self._value_items[row.source_name]
        value_item.setData(Qt.ItemDataRole.UserRole, row.value)
        value_text = _value_with_unit(row.value, row.unit)
        value_item.setText(value_text)

        status_label = self._status_labels[row.source_name]
        status_text = row.status.value if row.status is not None else "—"
        status_label.setText(status_text)
        status_label.setProperty(
            "alarmState",
            row.status.style_state if row.status is not None else "unknown",
        )
        status_label.style().unpolish(status_label)
        status_label.style().polish(status_label)

        tooltip = _measurement_tooltip(row, value_text, status_text)
        self._channel_widgets[row.source_name].setToolTip(tooltip)
        value_item.setToolTip(tooltip)
        status_label.setToolTip(tooltip)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Let the Graphs page scroll; this table never owns a vertical viewport."""
        event.ignore()

    def _resize_to_rows(self) -> None:
        visible_rows = max(self.rowCount(), 1)
        header_height = max(self.horizontalHeader().sizeHint().height(), 28)
        frame = self.frameWidth() * 2
        self.setFixedHeight(
            header_height + visible_rows * self.verticalHeader().defaultSectionSize() + frame
        )


def _value_with_unit(value: int | float | None, unit: str) -> str:
    formatted = format_graph_value(value)
    if formatted == "—" or not unit:
        return formatted
    return f"{formatted} {unit}"


def _measurement_tooltip(
    row: GraphCursorRow,
    value_text: str,
    status_text: str,
) -> str:
    measurement = (
        format_cursor_time(row.measurement_time, precise=True)
        if row.measurement_time is not None
        else "—"
    )
    cursor = (
        format_cursor_time(row.cursor_time, precise=True)
        if row.cursor_time is not None
        else "—"
    )
    return (
        f"{row.display_name}\n\n"
        f"Value: {value_text}\n"
        f"Status: {status_text}\n"
        f"Cursor: {cursor}\n"
        f"Measurement: {measurement}"
    )
