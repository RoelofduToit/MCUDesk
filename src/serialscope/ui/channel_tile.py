"""A simple HMI-style presentation tile for one structured channel."""

from collections import deque
import math

from PySide6.QtCore import Property, QMimeData, QPoint, QPointF, Qt
from PySide6.QtGui import (
    QColor,
    QDrag,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget
from serialscope.data import AlarmState, ChannelPresentation
from serialscope.ui.fonts import (
    NumericDisplayStyle,
    font_supports_text,
    normalize_numeric_display_style,
    numeric_display_font,
    numeric_display_size_scale,
)


SPARKLINE_MAX_SAMPLES = 48


def mark_tile_display_widget(widget: QWidget) -> None:
    """Forward mouse input through decorative tile content to the parent tile.

    Interactive child controls should skip this so they keep receiving clicks.
    """
    widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    widget.setCursor(Qt.CursorShape.OpenHandCursor)


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


class SparklineWidget(QWidget):
    """Compact line of recent samples with no axes or labels."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        max_samples: int = SPARKLINE_MAX_SAMPLES,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardTileSparkline")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(28)
        self._values: deque[float] = deque(maxlen=max_samples)
        self._line_color = QColor("#4db3d9")

    def lineColor(self) -> QColor:  # noqa: N802
        return QColor(self._line_color)

    def setLineColor(self, color: QColor) -> None:  # noqa: N802
        self._line_color = QColor(color)
        self.update()

    lineColor = Property(QColor, lineColor, setLineColor)

    @property
    def values(self) -> tuple[float, ...]:
        return tuple(self._values)

    def add_sample(self, value: int | float) -> None:
        numeric = float(value)
        if not math.isfinite(numeric):
            return
        self._values.append(numeric)
        self.update()

    def set_samples(self, values: tuple[int | float, ...]) -> None:
        self._values.clear()
        for value in values:
            numeric = float(value)
            if math.isfinite(numeric):
                self._values.append(numeric)
        self.update()

    def clear(self) -> None:
        self._values.clear()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.contentsRect().adjusted(1, 4, -1, -4)
        if rect.width() < 2 or rect.height() < 2:
            return
        samples = self.values
        if not samples:
            return
        if len(samples) == 1:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._line_color)
            painter.drawEllipse(QPointF(rect.right() - 1, rect.center().y()), 2.0, 2.0)
            return
        lowest = min(samples)
        span = max(samples) - lowest
        last_index = len(samples) - 1
        points = []
        for index, value in enumerate(samples):
            x = rect.left() + (rect.width() * index / last_index)
            if span == 0:
                y = rect.center().y()
            else:
                y = rect.bottom() - ((value - lowest) / span) * rect.height()
            points.append(QPointF(x, y))
        pen = QPen(self._line_color, 1.6)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawPolyline(points)


class ChannelTile(QFrame):
    """Display a channel name and its latest structured numeric value."""

    def __init__(
        self,
        channel_name: str,
        parent: QWidget | None = None,
        *,
        source_name: str = "",
    ) -> None:
        super().__init__(parent)
        self.channel_name = channel_name
        self.setObjectName("dashboardChannelTile")
        self.setMinimumSize(150, 150)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_start: QPoint | None = None
        self._numeric_style = NumericDisplayStyle.DEFAULT
        self._numeric_font: QFont | None = None
        self._default_value_font = QFont()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)

        self.name_label = ElidedLabel(channel_name)
        self.name_label.setObjectName("dashboardTileName")
        layout.addWidget(self.name_label)

        self.value_label = QLabel("—")
        self.value_label.setObjectName("dashboardTileValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label, 1)

        self.unit_label = QLabel("")
        self.unit_label.setObjectName("dashboardTileUnit")
        self.unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.unit_label)

        self.status_label = QLabel("UNKNOWN")
        self.status_label.setObjectName("dashboardTileStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.source_label = QLabel(source_name)
        self.source_label.setObjectName("dashboardTileSource")
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.source_label)

        self.sparkline = SparklineWidget()
        layout.addWidget(self.sparkline)

        for child in (
            self.name_label,
            self.value_label,
            self.unit_label,
            self.status_label,
            self.source_label,
            self.sparkline,
        ):
            mark_tile_display_widget(child)
        self._default_value_font = QFont(self.value_label.font())

    def set_source_name(self, source_name: str) -> None:
        self.source_label.setText(source_name)

    def set_numeric_display_style(self, style: NumericDisplayStyle | str) -> None:
        """Apply a Dashboard numeric typeface without reading application settings."""
        self._numeric_style = normalize_numeric_display_style(style)
        self._numeric_font = numeric_display_font(self._numeric_style)
        self._apply_numeric_display_font()

    def _apply_numeric_display_font(self) -> None:
        requested = self._numeric_font
        text = self.value_label.text()
        if requested is None or not font_supports_text(requested, text):
            self.value_label.setProperty("numericFamily", "default")
            self.value_label.setStyleSheet("")
            self.value_label.setFont(self._default_value_font)
        else:
            applied = QFont(requested)
            point_size = 24.0 * numeric_display_size_scale(self._numeric_style)
            applied.setPointSizeF(point_size)
            applied = self._fit_bundled_value_font(applied, text)
            point_size = applied.pointSizeF()
            family = applied.family().replace("'", "\\'")
            style = "italic" if applied.italic() else "normal"
            # Widget stylesheet is required so QWidget { font-family } does not
            # replace the bundled typeface after polish.
            self.value_label.setProperty("numericFamily", "bundled")
            self.value_label.setStyleSheet(
                f"font-family: '{family}'; font-size: {point_size}pt; "
                f"font-weight: 400; font-style: {style};"
            )
            self.value_label.setFont(applied)
        self.value_label.style().unpolish(self.value_label)
        self.value_label.style().polish(self.value_label)

    def _fit_bundled_value_font(self, font: QFont, text: str) -> QFont:
        """Shrink a bundled value face just enough to stay inside the tile."""
        available = self.value_label.contentsRect()
        if available.width() < 12 or available.height() < 12 or not text:
            return font
        fitted = QFont(font)
        for _ in range(10):
            metrics = QFontMetrics(fitted)
            if (
                metrics.horizontalAdvance(text) <= available.width()
                and metrics.height() <= available.height()
            ):
                break
            next_size = fitted.pointSizeF() * 0.88
            if next_size < 11:
                break
            fitted.setPointSizeF(next_size)
        return fitted

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._numeric_font is not None:
            self._apply_numeric_display_font()

    def set_value(self, value: int | float, *, record: bool = True) -> None:
        self.value_label.setText(format_dashboard_value(value))
        self._apply_numeric_display_font()
        if record:
            self.sparkline.add_sample(value)

    def set_sparkline_samples(self, values: tuple[int | float, ...]) -> None:
        """Replace the visible trend without changing the current value label."""
        self.sparkline.set_samples(values)

    def set_sparkline_color(self, color: QColor | str) -> None:
        self.sparkline.setLineColor(QColor(color))

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

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._update_elision()

    def _update_elision(self) -> None:
        if not self.isVisible():
            super().setText(self._full_text)
            return
        available = max(1, self.contentsRect().width())
        super().setText(
            self.fontMetrics().elidedText(
                self._full_text, Qt.TextElideMode.ElideRight, available
            )
        )
