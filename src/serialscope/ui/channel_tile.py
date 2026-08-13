"""A simple HMI-style presentation tile for one structured channel."""

import math

from PySide6.QtCore import QMimeData, QPoint, Qt
from PySide6.QtGui import QDrag, QMouseEvent, QPainter, QPixmap, QResizeEvent
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QWidget
from serialscope.data import AlarmState, ChannelPresentation


def format_dashboard_value(value: int | float) -> str:
    """Format a numeric measurement compactly without guessing units."""
    if isinstance(value, int):
        return str(value)
    numeric = float(value)
    if not math.isfinite(numeric):
        return "—"
    magnitude = abs(numeric)
    if numeric == 0 or 0.0001 <= magnitude < 1_000_000_000:
        return f"{numeric:.6f}".rstrip("0").rstrip(".")
    return f"{numeric:.6g}"


class ChannelTile(QFrame):
    """Display a channel name and its latest structured numeric value."""

    def __init__(self, channel_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.channel_name = channel_name
        self.setObjectName("dashboardChannelTile")
        self.setMinimumSize(150, 150)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_start: QPoint | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)

        self.name_label = ElidedLabel(channel_name)
        self.name_label.setObjectName("dashboardTileName")
        self.name_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.name_label)

        self.value_label = QLabel("—")
        self.value_label.setObjectName("dashboardTileValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.value_label, 1)

        self.unit_label = QLabel("")
        self.unit_label.setObjectName("dashboardTileUnit")
        self.unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.unit_label)

        self.status_label = QLabel("UNKNOWN")
        self.status_label.setObjectName("dashboardTileStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

    def set_value(self, value: int | float) -> None:
        self.value_label.setText(format_dashboard_value(value))

    def set_presentation(self, presentation: ChannelPresentation) -> None:
        self.name_label.setText(presentation.display_name)
        self.name_label.setToolTip(f"Source: {self.channel_name}")
        self.unit_label.setText(presentation.unit)

    def set_alarm_state(self, state: AlarmState) -> None:
        self.status_label.setText(state.value)
        self.setProperty("alarmState", state.style_state)
        self.status_label.setProperty("alarmState", state.style_state)
        self.style().unpolish(self)
        self.style().polish(self)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if (
            self._drag_start is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and self.drag_threshold_reached(event.position().toPoint())
        ):
            mime_data = QMimeData()
            mime_data.setData(
                "application/x-serialscope-dashboard-channel",
                self.channel_name.encode("utf-8"),
            )
            drag = QDrag(self)
            drag.setMimeData(mime_data)
            drag.setPixmap(self._drag_pixmap())
            drag.setHotSpot(self._drag_start)
            self.setProperty("dragState", "active")
            self.style().unpolish(self)
            self.style().polish(self)
            drag.exec(Qt.DropAction.MoveAction)
            self.setProperty("dragState", "inactive")
            self.style().unpolish(self)
            self.style().polish(self)
            self._drag_start = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_start = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def drag_threshold_reached(self, current: QPoint) -> bool:
        """Expose Qt's platform drag threshold for deterministic UI tests."""
        return bool(
            self._drag_start is not None
            and (current - self._drag_start).manhattanLength()
            >= QApplication.startDragDistance()
        )

    def _drag_pixmap(self) -> QPixmap:
        """Capture one stable, subtly translucent square drag visual."""
        source = self.grab()
        visual = QPixmap(source.size())
        visual.fill(Qt.GlobalColor.transparent)
        painter = QPainter(visual)
        painter.setOpacity(0.88)
        painter.drawPixmap(0, 0, source)
        painter.end()
        return visual


class ElidedLabel(QLabel):
    """Single-line label that preserves its full text while fitting a tile."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = text
        super().setText(text)

    def setText(self, text: str) -> None:  # noqa: N802
        self._full_text = text
        self._update_elision()

    def full_text(self) -> str:
        return self._full_text

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_elision()

    def _update_elision(self) -> None:
        available = max(1, self.contentsRect().width())
        super().setText(
            self.fontMetrics().elidedText(
                self._full_text, Qt.TextElideMode.ElideRight, available
            )
        )
