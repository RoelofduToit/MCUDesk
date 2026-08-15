"""Compact, readable status pills for live data tables."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QTableWidget, QWidget

from serialscope.data import AlarmState

_LONGEST_STATUS = "HIGH-HIGH"
_HORIZONTAL_PAD = 24
_MINIMUM_HEIGHT = 22
_CELL_LEFT = 10
_CELL_RIGHT = 14
_CELL_TOP = 2
_CELL_BOTTOM = 2
_TABLE_ITEM_PAD_X = 12
_TABLE_ITEM_PAD_Y = 6
_COLUMN_SLACK = 16
_ROW_SLACK = 4


def table_value_font() -> QFont:
    font = QFont()
    font.setPointSizeF(10.5)
    font.setWeight(QFont.Weight.Medium)
    return font


def status_presentation(
    state: AlarmState | None, text: str | None = None
) -> tuple[str, str, str]:
    """Return display text, semantic style, and specific kind without changing logic."""
    if state is None:
        label = text if text else "—"
        if label == "ERROR":
            return label, "alarm", "ERROR"
        return "—" if not label else label, "unknown", "unknown"
    label = state.value
    if state is AlarmState.UNKNOWN:
        return label, "unknown", "UNKNOWN"
    return label, state.style_state, state.value


def apply_status_badge_metrics(badge: QLabel) -> None:
    """Keep pill text readable; Qt often ignores QLabel padding alone."""
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    badge.setMinimumHeight(_MINIMUM_HEIGHT)
    badge.ensurePolished()
    metrics = badge.fontMetrics()
    text_width = max(
        metrics.horizontalAdvance(badge.text() or ""),
        metrics.horizontalAdvance(_LONGEST_STATUS),
        metrics.horizontalAdvance("NORMAL"),
    )
    badge.setMinimumWidth(text_width + _HORIZONTAL_PAD)


def status_column_width(reference: QWidget) -> int:
    """Width that fits HIGH-HIGH after pill, cell, and QTableWidget item padding."""
    reference.ensurePolished()
    probe = QLabel(_LONGEST_STATUS)
    probe.setObjectName("channelDataStatusBadge")
    apply_status_badge_metrics(probe)
    badge_width = max(probe.minimumWidth(), probe.sizeHint().width())
    probe.deleteLater()
    return (
        badge_width
        + _CELL_LEFT
        + _CELL_RIGHT
        + _TABLE_ITEM_PAD_X * 2
        + _COLUMN_SLACK
    )


def status_row_height(reference: QWidget) -> int:
    """Row height that keeps the pill inside item padding and cell margins."""
    reference.ensurePolished()
    probe = QLabel(_LONGEST_STATUS)
    probe.setObjectName("channelDataStatusBadge")
    apply_status_badge_metrics(probe)
    badge_height = max(probe.minimumHeight(), probe.sizeHint().height())
    probe.deleteLater()
    return (
        badge_height
        + _CELL_TOP
        + _CELL_BOTTOM
        + _TABLE_ITEM_PAD_Y * 2
        + _ROW_SLACK
    )


def apply_status_row_height(table: QTableWidget) -> int:
    """Size every row so the shared status pill fits with a little vertical air."""
    height = status_row_height(table)
    header = table.verticalHeader()
    header.setDefaultSectionSize(height)
    header.setMinimumSectionSize(height)
    for row in range(table.rowCount()):
        table.setRowHeight(row, height)
    return height


def make_status_badge(
    text: str,
    style_state: str,
    kind: str,
    *,
    object_name: str,
    cell_name: str,
) -> tuple[QWidget, QLabel]:
    cell = QWidget()
    cell.setObjectName(cell_name)
    row = QHBoxLayout(cell)
    row.setContentsMargins(_CELL_LEFT, _CELL_TOP, _CELL_RIGHT, _CELL_BOTTOM)
    row.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge = QLabel(text)
    badge.setObjectName(object_name)
    apply_status_style(badge, style_state, kind)
    apply_status_badge_metrics(badge)
    row.addWidget(badge, 0, Qt.AlignmentFlag.AlignCenter)
    return cell, badge


def apply_status_style(badge: QLabel, style_state: str, kind: str) -> None:
    badge.setProperty("alarmState", style_state)
    badge.setProperty("alarmKind", kind)
    badge.style().unpolish(badge)
    badge.style().polish(badge)
    apply_status_badge_metrics(badge)
