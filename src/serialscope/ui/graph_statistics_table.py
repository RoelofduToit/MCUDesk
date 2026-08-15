"""Compact presentation of measured graph statistics."""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from serialscope.ui.graph_display import format_graph_value


MAX_VISIBLE_STATISTIC_ROWS = 6


@dataclass(frozen=True, slots=True)
class GraphStatisticsRow:
    source_name: str
    display_name: str
    unit: str
    color: str
    minimum: float
    average: float
    maximum: float


class GraphStatisticsTable(QTableWidget):
    """Reuse table rows while measured values refresh."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 4, parent)
        self.setObjectName("graphStatisticsTable")
        self.setHorizontalHeaderLabels(("Channel", "Min", "Avg", "Max"))
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(26)
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self._source_names: tuple[str, ...] = ()
        self._channel_labels: dict[str, QLabel] = {}
        self._swatches: dict[str, QLabel] = {}
        self._value_items: dict[str, tuple[QTableWidgetItem, ...]] = {}
        self._resize_to_rows()

    @property
    def source_names(self) -> tuple[str, ...]:
        return self._source_names

    def set_statistics(self, rows: tuple[GraphStatisticsRow, ...]) -> None:
        """Update values in place, rebuilding only when selected channels change."""
        source_names = tuple(row.source_name for row in rows)
        if source_names != self._source_names:
            self._rebuild(source_names)

        for row_index, row in enumerate(rows):
            self._set_presentation(row.source_name, row.display_name, row.unit, row.color)
            values = (row.minimum, row.average, row.maximum)
            for item, value in zip(self._value_items[row.source_name], values, strict=True):
                item.setText(format_graph_value(value))
            self.setRowHeight(row_index, self.verticalHeader().defaultSectionSize())

    def clear_statistics(self) -> None:
        self._rebuild(())

    def update_presentation(
        self,
        source_name: str,
        display_name: str,
        unit: str,
    ) -> None:
        """Refresh alias/unit text without recalculating frozen statistics."""
        swatch = self._swatches.get(source_name)
        if swatch is None:
            return
        self._set_presentation(
            source_name,
            display_name,
            unit,
            swatch.property("graphColor"),
        )

    def channel_text(self, source_name: str) -> str | None:
        label = self._channel_labels.get(source_name)
        return label.text() if label is not None else None

    def value_text(self, source_name: str, column: str) -> str | None:
        items = self._value_items.get(source_name)
        if items is None:
            return None
        return items[{"min": 0, "avg": 1, "max": 2}[column]].text()

    def swatch_color(self, source_name: str) -> str | None:
        swatch = self._swatches.get(source_name)
        return str(swatch.property("graphColor")) if swatch is not None else None

    def _rebuild(self, source_names: tuple[str, ...]) -> None:
        self.clearContents()
        self.setRowCount(len(source_names))
        self._source_names = source_names
        self._channel_labels.clear()
        self._swatches.clear()
        self._value_items.clear()
        for row, source_name in enumerate(source_names):
            channel_widget = QWidget()
            channel_widget.setObjectName("graphStatisticsChannel")
            layout = QHBoxLayout(channel_widget)
            layout.setContentsMargins(6, 0, 4, 0)
            layout.setSpacing(6)
            swatch = QLabel("●")
            swatch.setObjectName("graphStatisticsSwatch")
            layout.addWidget(swatch)
            label = QLabel(source_name)
            label.setObjectName("graphStatisticsChannelLabel")
            layout.addWidget(label, 1)
            self.setCellWidget(row, 0, channel_widget)
            self._swatches[source_name] = swatch
            self._channel_labels[source_name] = label

            items = []
            for column in range(1, 4):
                item = QTableWidgetItem("—")
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.setItem(row, column, item)
                items.append(item)
            self._value_items[source_name] = tuple(items)
        self._resize_to_rows()

    def _set_presentation(
        self,
        source_name: str,
        display_name: str,
        unit: str,
        color: object,
    ) -> None:
        label = self._channel_labels[source_name]
        label.setText(f"{display_name} ({unit})" if unit else display_name)
        label.setToolTip(f"Source: {source_name}")
        swatch = self._swatches[source_name]
        color_text = str(color)
        swatch.setProperty("graphColor", color_text)
        swatch.setStyleSheet(
            f"color: {color_text}; background-color: transparent; border: none;"
        )

    def _resize_to_rows(self) -> None:
        visible_rows = min(max(self.rowCount(), 1), MAX_VISIBLE_STATISTIC_ROWS)
        header_height = max(self.horizontalHeader().sizeHint().height(), 28)
        frame = self.frameWidth() * 2
        self.setFixedHeight(
            header_height + visible_rows * self.verticalHeader().defaultSectionSize() + frame
        )
