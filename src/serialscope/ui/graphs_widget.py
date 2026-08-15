"""Selectable live plotting of structured numeric channels."""

from collections.abc import Callable
import math
import time

import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QLabel,
    QLayout,
    QLayoutItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

from serialscope.data import (
    ChannelHistory,
    ChannelMetadataRegistry,
    EventMarker,
    calculate_statistics,
    nearest_measurement,
    process_display_points,
    evaluate_alarm,
)
from serialscope.parsing import ChannelUpdate
from serialscope.replay import ReplaySession
from serialscope.ui.elapsed_time_axis import ElapsedTimeAxis
from serialscope.ui.graph_cursor_table import GraphCursorRow, GraphCursorTable
from serialscope.ui.graph_display import format_cursor_time
from serialscope.ui.graph_statistics_table import (
    GraphStatisticsRow,
    GraphStatisticsTable,
)
from serialscope.ui.channel_selector import ChannelSelector, ChannelToggle
from serialscope.ui.channel_colors import series_color_for_channel
from serialscope.ui.theme import DARK_GRAPH_PALETTE, GraphPalette


TIME_WINDOWS = {
    "10 s": 10.0,
    "30 s": 30.0,
    "60 s": 60.0,
    "5 min": 300.0,
    "10 min": 600.0,
    "30 min": 1_800.0,
    "1 hour": 3_600.0,
}


def _compact_graph_combo(combo: QComboBox, contents: int) -> None:
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setMinimumContentsLength(contents)
    combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)


def _settings_group(object_name: str, heading: str) -> tuple[QFrame, QLayout]:
    group = QFrame()
    group.setObjectName(object_name)
    group.setProperty("graphSettingsGroup", True)
    group.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
    outer = QVBoxLayout(group)
    outer.setContentsMargins(10, 8, 10, 8)
    outer.setSpacing(6)
    title = QLabel(heading)
    title.setObjectName("graphSettingsHeading")
    outer.addWidget(title)
    row_host = QWidget()
    row_host.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
    row = _FlowLayout(row_host, spacing=6)
    outer.addWidget(row_host)
    return group, row


class _FlowLayout(QLayout):
    """Lay controls left-to-right and wrap only when width requires it."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 8) -> None:
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)
        self._items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        width = 0
        height = 0
        spacing = self.spacing()
        for index, item in enumerate(self._items):
            hint = item.sizeHint()
            width += hint.width()
            if index:
                width += spacing
            height = max(height, hint.height())
        left, top, right, bottom = self.getContentsMargins()
        return QSize(width + left + right, height + top + bottom)

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        return size + QSize(left + right, top + bottom)

    def _item_size(self, item: QLayoutItem, available_width: int) -> QSize:
        hint = item.sizeHint()
        width = hint.width() if hint.width() <= available_width else max(
            item.minimumSize().width(), available_width
        )
        if width < hint.width() and item.hasHeightForWidth():
            return QSize(width, item.heightForWidth(width))
        return QSize(width, hint.height())

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        x = effective.x()
        y = effective.y()
        line_height = 0
        spacing = self.spacing()
        available = max(0, effective.width())

        for item in self._items:
            size = self._item_size(item, available)
            next_x = x + size.width() + spacing
            if line_height and next_x - spacing > effective.right() + 1:
                x = effective.x()
                y += line_height + spacing
                size = self._item_size(item, available)
                next_x = x + size.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), size))
            x = next_x
            line_height = max(line_height, size.height())

        return y + line_height - rect.y() + bottom


def visible_x_range(latest_time: float, window_seconds: float) -> tuple[float, float]:
    """Return a non-negative elapsed-time viewport for the live graph."""
    latest_time = max(0.0, latest_time)
    if latest_time <= window_seconds:
        return 0.0, window_seconds
    return latest_time - window_seconds, latest_time


class GraphsWidget(QWidget):
    """Collect bounded history and plot only user-selected channels."""

    def __init__(
        self,
        parent: QWidget | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("graphsWidget")
        self.history = ChannelHistory(clock=clock)
        self._series: dict[str, pg.PlotDataItem] = {}
        self._measured_series: dict[str, pg.PlotDataItem] = {}
        self._paused = False
        self._replay_session: ReplaySession | None = None
        self._graph_palette = DARK_GRAPH_PALETTE
        self._metadata = ChannelMetadataRegistry()
        self._events: tuple[EventMarker, ...] = ()
        self._event_lines: list[pg.InfiniteLine] = []
        self._cursor_elapsed: float | None = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.page_scroll = QScrollArea()
        self.page_scroll.setObjectName("graphsPageScrollArea")
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.page_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.page_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.page_content = QWidget()
        self.page_content.setObjectName("graphsPageContent")
        self.page_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        layout = QVBoxLayout(self.page_content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        channel_label = QLabel("Channels")
        channel_label.setObjectName("graphChannelsLabel")
        layout.addWidget(channel_label)

        self.channel_selector = ChannelSelector()
        self.channel_selector.selection_changed.connect(self._set_channel_selected)
        self.selector_scroll = self.channel_selector
        self._selectors: dict[str, ChannelToggle] = self.channel_selector.toggles
        layout.addWidget(self.selector_scroll)

        settings = QFrame()
        settings.setObjectName("graphSettingsPanel")
        settings_layout = _FlowLayout(settings, spacing=8)

        view, view_row = _settings_group("graphControls", "View")
        self.pause_button = QPushButton("Pause")
        self.pause_button.setObjectName("graphPauseButton")
        self.pause_button.clicked.connect(self.toggle_pause)
        view_row.addWidget(self.pause_button)
        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("graphClearButton")
        self.clear_button.clicked.connect(self.clear_history)
        view_row.addWidget(self.clear_button)
        self.reset_zoom_button = QPushButton("Reset Zoom")
        self.reset_zoom_button.setObjectName("graphResetZoomButton")
        self.reset_zoom_button.clicked.connect(self.reset_zoom)
        view_row.addWidget(self.reset_zoom_button)
        window_label = QLabel("Time Window")
        window_label.setObjectName("graphTimeWindowLabel")
        view_row.addWidget(window_label)
        self.time_window_combo = QComboBox()
        self.time_window_combo.setObjectName("graphTimeWindowCombo")
        for label, seconds in TIME_WINDOWS.items():
            self.time_window_combo.addItem(label, seconds)
        self.time_window_combo.setCurrentText("60 s")
        self.time_window_combo.currentIndexChanged.connect(self.refresh_plot)
        _compact_graph_combo(self.time_window_combo, 5)
        view_row.addWidget(self.time_window_combo)
        settings_layout.addWidget(view)

        processing, processing_row = _settings_group(
            "graphProcessingControls", "Interpolation"
        )
        self.interpolation_combo = QComboBox()
        self.interpolation_combo.setObjectName("graphInterpolationCombo")
        self.interpolation_combo.addItem("Off", "off")
        self.interpolation_combo.addItem("Linear", "linear")
        self.interpolation_combo.addItem("PCHIP", "pchip")
        _compact_graph_combo(self.interpolation_combo, 6)
        processing_row.addWidget(self.interpolation_combo)
        self.density_label = QLabel("Density")
        self.density_label.setObjectName("graphDensityLabel")
        processing_row.addWidget(self.density_label)
        self.density_combo = QComboBox()
        self.density_combo.setObjectName("graphInterpolationDensityCombo")
        for density in (2, 5, 10):
            self.density_combo.addItem(f"{density}x", density)
        self.density_combo.setCurrentText("5x")
        _compact_graph_combo(self.density_combo, 3)
        processing_row.addWidget(self.density_combo)
        self.max_gap_label = QLabel("Max Gap")
        self.max_gap_label.setObjectName("graphMaxGapLabel")
        processing_row.addWidget(self.max_gap_label)
        self.max_gap_combo = QComboBox()
        self.max_gap_combo.setObjectName("graphMaxGapCombo")
        for label, seconds in (
            ("1 s", 1.0),
            ("2 s", 2.0),
            ("5 s", 5.0),
            ("10 s", 10.0),
            ("Unlimited", None),
        ):
            self.max_gap_combo.addItem(label, seconds)
        self.max_gap_combo.setCurrentText("5 s")
        _compact_graph_combo(self.max_gap_combo, 6)
        processing_row.addWidget(self.max_gap_combo)
        self.measured_points_checkbox = QCheckBox("Show measured points")
        self.measured_points_checkbox.setObjectName("graphMeasuredPointsCheckBox")
        processing_row.addWidget(self.measured_points_checkbox)
        settings_layout.addWidget(processing)

        smoothing, smoothing_row = _settings_group(
            "graphSmoothingControls", "Smoothing"
        )
        self.smoothing_combo = QComboBox()
        self.smoothing_combo.setObjectName("graphSmoothingCombo")
        self.smoothing_combo.addItem("Off", "off")
        self.smoothing_combo.addItem("Moving Average", "moving_average")
        self.smoothing_combo.addItem("EMA", "ema")
        _compact_graph_combo(self.smoothing_combo, 12)
        smoothing_row.addWidget(self.smoothing_combo)
        self.moving_average_label = QLabel("Window (samples)")
        self.moving_average_label.setObjectName("graphMovingAverageLabel")
        smoothing_row.addWidget(self.moving_average_label)
        self.moving_average_spin = QSpinBox()
        self.moving_average_spin.setObjectName("graphMovingAverageWindow")
        self.moving_average_spin.setRange(2, 100)
        self.moving_average_spin.setValue(5)
        smoothing_row.addWidget(self.moving_average_spin)
        self.ema_alpha_label = QLabel("Alpha")
        self.ema_alpha_label.setObjectName("graphEmaAlphaLabel")
        smoothing_row.addWidget(self.ema_alpha_label)
        self.ema_alpha_spin = QDoubleSpinBox()
        self.ema_alpha_spin.setObjectName("graphEmaAlpha")
        self.ema_alpha_spin.setRange(0.01, 1.0)
        self.ema_alpha_spin.setSingleStep(0.05)
        self.ema_alpha_spin.setDecimals(2)
        self.ema_alpha_spin.setValue(0.2)
        smoothing_row.addWidget(self.ema_alpha_spin)
        settings_layout.addWidget(smoothing)
        layout.addWidget(settings)
        self._update_processing_control_state()

        self.elapsed_time_axis = ElapsedTimeAxis()
        self.plot_widget = pg.PlotWidget(
            axisItems={"bottom": self.elapsed_time_axis}
        )
        self.plot_widget.plotItem.layout.setContentsMargins(0, 0, 24, 0)
        self.plot_widget.setObjectName("livePlot")
        self.plot_widget.setBackground("#0a1016")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.18)
        self.plot_widget.setLabel("left", "Value")
        self.plot_widget.addLegend()
        self.plot_widget.setMinimumHeight(500)
        self.plot_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._cursor_line: pg.InfiniteLine | None = None
        layout.addWidget(self.plot_widget, 1)

        self.cursor_panel = QFrame()
        self.cursor_panel.setObjectName("graphCursorPanel")
        cursor_panel_layout = QVBoxLayout(self.cursor_panel)
        cursor_panel_layout.setContentsMargins(12, 10, 12, 10)
        cursor_panel_layout.setSpacing(6)
        self.cursor_heading = QLabel("Cursor Values")
        self.cursor_heading.setObjectName("graphCursorHeading")
        cursor_panel_layout.addWidget(self.cursor_heading)
        self.cursor_time_label = QLabel("Cursor: —")
        self.cursor_time_label.setObjectName("graphCursorTimeLabel")
        cursor_panel_layout.addWidget(self.cursor_time_label)
        self.cursor_table = GraphCursorTable()
        cursor_panel_layout.addWidget(self.cursor_table)
        self.cursor_empty_label = QLabel("Select a channel and move over the graph.")
        self.cursor_empty_label.setObjectName("graphCursorEmptyLabel")
        self.cursor_empty_label.setWordWrap(True)
        cursor_panel_layout.addWidget(self.cursor_empty_label)
        layout.addWidget(self.cursor_panel)

        self.statistics_panel = QFrame()
        self.statistics_panel.setObjectName("graphStatisticsPanel")
        statistics_panel_layout = QVBoxLayout(self.statistics_panel)
        statistics_panel_layout.setContentsMargins(12, 10, 12, 10)
        statistics_panel_layout.setSpacing(6)
        self.statistics_heading = QLabel("Statistics")
        self.statistics_heading.setObjectName("graphStatisticsHeading")
        statistics_panel_layout.addWidget(self.statistics_heading)
        self.statistics_table = GraphStatisticsTable()
        statistics_panel_layout.addWidget(self.statistics_table)
        self.statistics_empty_label = QLabel("Select a channel to view statistics.")
        self.statistics_empty_label.setObjectName("graphStatisticsEmptyLabel")
        self.statistics_empty_label.setWordWrap(True)
        statistics_panel_layout.addWidget(self.statistics_empty_label)
        layout.addWidget(self.statistics_panel)
        self.page_scroll.setWidget(self.page_content)
        outer_layout.addWidget(self.page_scroll)
        self.apply_theme(DARK_GRAPH_PALETTE)
        self._apply_x_range(0.0)

        self.plot_widget.viewport().setMouseTracking(True)
        self.plot_widget.viewport().installEventFilter(self)
        for control in (
            self.interpolation_combo,
            self.density_combo,
            self.max_gap_combo,
            self.measured_points_checkbox,
            self.smoothing_combo,
            self.moving_average_spin,
            self.ema_alpha_spin,
        ):
            if isinstance(control, QCheckBox):
                control.toggled.connect(self._processing_changed)
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                control.valueChanged.connect(self._processing_changed)
            else:
                control.currentIndexChanged.connect(self._processing_changed)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(100)
        self._refresh_timer.timeout.connect(self._refresh_live_plot)
        self._refresh_timer.start()

    @property
    def channel_names(self) -> tuple[str, ...]:
        return tuple(self._selectors)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Expose content width while allowing the scroll area to absorb height."""
        hint = super().minimumSizeHint()
        return QSize(max(hint.width(), self.page_content.minimumSizeHint().width()), hint.height())

    @property
    def selected_channels(self) -> tuple[str, ...]:
        return tuple(name for name, box in self._selectors.items() if box.isChecked())

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def time_window_seconds(self) -> float:
        return float(self.time_window_combo.currentData())

    def update_channels(self, update: ChannelUpdate) -> None:
        """Collect a structured update and expose newly observed channels."""
        self.history.add_update(update)
        for name in update.names:
            self._add_channel(name)

    def load_replay(self, session: ReplaySession) -> None:
        """Present a completed session without feeding the live history model."""
        self.reset()
        self._replay_session = session
        for name in session.channel_names:
            self._add_channel(name)
        self.set_events(session.events)
        self.refresh_plot()

    @property
    def events(self) -> tuple[EventMarker, ...]:
        return self._events

    def set_events(self, events: tuple[EventMarker, ...]) -> None:
        """Replace sparse presentation markers without touching measurements."""
        events = tuple(events)
        if events == self._events:
            return
        for line in self._event_lines:
            self.plot_widget.removeItem(line)
        self._event_lines.clear()
        self._events = events
        for marker in events:
            line = pg.InfiniteLine(
                pos=marker.elapsed_s,
                angle=90,
                movable=False,
                pen=pg.mkPen(self._graph_palette.event_marker, width=1),
                hoverPen=pg.mkPen(self._graph_palette.event_marker_hover, width=2),
            )
            line.setObjectName("graphEventMarker")
            line.setToolTip(f"{marker.elapsed_s:.3f} s\n{marker.text}")
            line.setZValue(5)
            self.plot_widget.addItem(line, ignoreBounds=True)
            self._event_lines.append(line)

    def set_channel_selected(self, name: str, selected: bool) -> None:
        self.channel_selector.set_channel_checked(name, selected)

    def has_series(self, name: str) -> bool:
        return name in self._series

    def set_channel_metadata(self, registry: ChannelMetadataRegistry) -> None:
        """Refresh presentation labels without changing source-keyed graph state."""
        self._metadata = registry
        legend = self.plot_widget.plotItem.legend
        for source_name, checkbox in self._selectors.items():
            presentation = registry.get(source_name)
            self.channel_selector.set_channel_text(
                source_name,
                presentation.display_name,
                tooltip=f"Source: {source_name}",
            )
            self.statistics_table.update_presentation(
                source_name,
                presentation.display_name,
                presentation.unit,
            )
            self.cursor_table.update_presentation(
                source_name,
                presentation.display_name,
                presentation.unit,
            )
            series = self._series.get(source_name)
            if series is not None:
                series.opts["name"] = presentation.display_name
                if legend is not None:
                    label = legend.getLabel(series)
                    if label is not None:
                        label.setText(
                            presentation.display_name,
                            color=self._graph_palette.foreground,
                        )
        self._refresh_cursor_values()
        if not self._paused:
            self.refresh_plot()

    def refresh_plot(self) -> None:
        if self._paused:
            return

        points = {
            name: (
                self._replay_session.points(name)
                if self._replay_session is not None
                else self.history.points(name)
            )
            for name in self._series
        }
        latest_time = max(
            (x_values[-1] for x_values, _y_values in points.values() if x_values),
            default=None,
        )
        cutoff = (
            latest_time - self.time_window_seconds
            if latest_time is not None and self._replay_session is None
            else None
        )
        measured_for_statistics: dict[str, tuple[tuple[float, ...], tuple[int | float, ...]]] = {}
        for name, series in self._series.items():
            x_values, y_values = points[name]
            if x_values and cutoff is not None:
                visible = next(
                    (index for index, timestamp in enumerate(x_values) if timestamp >= cutoff),
                    len(x_values),
                )
                source_x, source_y = x_values[visible:], y_values[visible:]
            else:
                source_x, source_y = x_values, y_values
            measured_for_statistics[name] = source_x, source_y
            display_x, display_y = process_display_points(
                source_x,
                source_y,
                smoothing=self.smoothing_combo.currentData(),
                moving_average_window=self.moving_average_spin.value(),
                ema_alpha=self.ema_alpha_spin.value(),
                interpolation=self.interpolation_combo.currentData(),
                density=self.density_combo.currentData(),
                max_gap=self.max_gap_combo.currentData(),
            )
            series.setData(display_x, display_y)
            marker = self._measured_series.get(name)
            if marker is not None:
                marker.setData(source_x, source_y)
        self._apply_x_range(latest_time or 0.0)
        self._update_statistics(measured_for_statistics)

    def toggle_pause(self) -> None:
        """Freeze or resume plot presentation without stopping acquisition."""
        self._paused = not self._paused
        self.pause_button.setText("Resume" if self._paused else "Pause")
        if not self._paused:
            self.refresh_plot()

    def clear_history(self) -> None:
        """Clear active-connection history while preserving channel choices."""
        self.history.reset()
        self._replay_session = None
        for series in self._series.values():
            series.setData([], [])
        for series in self._measured_series.values():
            series.setData([], [])
        self.statistics_table.clear_statistics()
        self.statistics_empty_label.setText("No measured data in the visible range.")
        self.statistics_empty_label.show()
        self._clear_cursor_values()
        self._apply_x_range(0.0)

    def apply_theme(self, palette: GraphPalette) -> None:
        """Update graph surfaces without altering history or selections."""
        self._graph_palette = palette
        self.plot_widget.setBackground(palette.background)
        for orientation in ("bottom", "left"):
            axis = self.plot_widget.getAxis(orientation)
            axis.setPen(palette.foreground)
            axis.setTextPen(palette.foreground)
        if self._cursor_line is not None:
            self._cursor_line.setPen(pg.mkPen(palette.cursor, width=1))
        for line in self._event_lines:
            line.setPen(pg.mkPen(palette.event_marker, width=1))
            line.setHoverPen(pg.mkPen(palette.event_marker_hover, width=2))
        legend = self.plot_widget.plotItem.legend
        if legend is not None:
            legend.setBrush(palette.background)
            legend.setPen(palette.foreground)
            for _sample, label in legend.items:
                label.setText(label.text, color=palette.foreground)

    def reset(self) -> None:
        """Clear selector, series, and history for a new connection."""
        self.channel_selector.clear_channels()
        for series in tuple(self._series.values()):
            self.plot_widget.removeItem(series)
        self._series.clear()
        for series in tuple(self._measured_series.values()):
            self.plot_widget.removeItem(series)
        self._measured_series.clear()
        self.history.reset()
        self._replay_session = None
        self.set_events(())
        self._paused = False
        self.pause_button.setText("Pause")
        if self._cursor_line is not None:
            self._cursor_line.hide()
        self._cursor_elapsed = None
        self.cursor_time_label.setText("Cursor: —")
        self.cursor_table.clear_values()
        self.cursor_empty_label.setText("Select a channel and move over the graph.")
        self.cursor_empty_label.show()
        self.statistics_table.clear_statistics()
        self.statistics_empty_label.setText("Select a channel to view statistics.")
        self.statistics_empty_label.show()
        self.page_scroll.verticalScrollBar().setValue(0)
        self._apply_x_range(0.0)

    def reset_zoom(self) -> None:
        """Restore the current live/replay X range and automatic Y range."""
        latest = max(
            (points[0][-1] for points in self._source_points().values() if points[0]),
            default=0.0,
        )
        self._apply_x_range(latest)
        self.plot_widget.enableAutoRange(axis="y", enable=True)

    def _apply_x_range(self, latest_time: float) -> None:
        self.elapsed_time_axis.set_time_window(self.time_window_seconds)
        lower, upper = visible_x_range(latest_time, self.time_window_seconds)
        self.plot_widget.setXRange(lower, upper, padding=0)

    def _set_channel_selected(self, name: str, selected: bool) -> None:
        if selected:
            color = series_color_for_channel(name, tuple(self._selectors))
            self._series[name] = self.plot_widget.plot(
                name=self._metadata.get(name).display_name,
                pen=pg.mkPen(color, width=2),
            )
            self._measured_series[name] = self.plot_widget.plot(
                pen=None,
                symbol="o",
                symbolSize=5,
                symbolBrush=color,
                symbolPen=None,
                name=None,
            )
            self._measured_series[name].setVisible(self.measured_points_checkbox.isChecked())
            self.apply_theme(self._graph_palette)
            self.refresh_plot()
        else:
            series = self._series.pop(name, None)
            if series is not None:
                self.plot_widget.removeItem(series)
            marker = self._measured_series.pop(name, None)
            if marker is not None:
                self.plot_widget.removeItem(marker)
            self.refresh_plot()
        self._refresh_cursor_values()

    def _add_channel(self, name: str) -> None:
        if name in self._selectors:
            return
        presentation = self._metadata.get(name)
        self.channel_selector.add_channel(
            name,
            presentation.display_name,
            tooltip=f"Source: {name}",
        )

    def _refresh_live_plot(self) -> None:
        # Completed replay data is immutable; leaving it alone permits zoom and pan.
        if self._replay_session is None:
            self.refresh_plot()

    def _source_points(self) -> dict[str, tuple[tuple[float, ...], tuple[int | float, ...]]]:
        return {
            name: (
                self._replay_session.points(name)
                if self._replay_session is not None
                else self.history.points(name)
            )
            for name in self._series
        }

    def _processing_changed(self, *_args: object) -> None:
        self._update_processing_control_state()
        for marker in self._measured_series.values():
            marker.setVisible(self.measured_points_checkbox.isChecked())
        if not self._paused:
            self.refresh_plot()

    def _update_processing_control_state(self) -> None:
        interpolation_enabled = self.interpolation_combo.currentData() != "off"
        self.density_combo.setEnabled(interpolation_enabled)
        self.max_gap_combo.setEnabled(interpolation_enabled)
        self.density_label.setEnabled(interpolation_enabled)
        self.max_gap_label.setEnabled(interpolation_enabled)
        smoothing = self.smoothing_combo.currentData()
        moving_average = smoothing == "moving_average"
        ema = smoothing == "ema"
        self.moving_average_label.setVisible(moving_average)
        self.moving_average_spin.setVisible(moving_average)
        self.ema_alpha_label.setVisible(ema)
        self.ema_alpha_spin.setVisible(ema)

    def _handle_mouse_moved(self, event: object) -> None:
        position = event[0] if isinstance(event, tuple) else event
        if not self.plot_widget.sceneBoundingRect().contains(position):
            if self._cursor_line is not None:
                self._cursor_line.hide()
            self._clear_cursor_values()
            return
        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(position)
        target = max(0.0, mouse_point.x())
        self.cursor_line.setPos(target)
        self.cursor_line.show()
        self._cursor_elapsed = target
        self._update_cursor_values(target)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Inspect graph mouse motion without retaining scene-signal proxies."""
        if watched is self.plot_widget.viewport() and event.type() == QEvent.Type.MouseMove:
            scene_position = self.plot_widget.mapToScene(event.position().toPoint())
            self._handle_mouse_moved(scene_position)
        return super().eventFilter(watched, event)

    def inspect_at(self, elapsed_time: float) -> dict[str, tuple[float, int | float]]:
        """Return nearest actual samples for cursor inspection and tests."""
        return {
            name: nearest
            for name, points in self._source_points().items()
            if (nearest := nearest_measurement(*points, elapsed_time)) is not None
        }

    @property
    def cursor_line(self) -> pg.InfiniteLine:
        """Create the inspection cursor only when first needed."""
        if self._cursor_line is None:
            self._cursor_line = pg.InfiniteLine(angle=90, movable=False)
            self._cursor_line.setObjectName("graphInspectionCursor")
            self._cursor_line.setPen(pg.mkPen(self._graph_palette.cursor, width=1))
            self._cursor_line.hide()
            self.plot_widget.addItem(self._cursor_line, ignoreBounds=True)
        return self._cursor_line

    def _refresh_cursor_values(self) -> None:
        if self._cursor_elapsed is None:
            self._show_cursor_placeholders()
        else:
            self._update_cursor_values(self._cursor_elapsed)

    def _show_cursor_placeholders(self) -> None:
        rows = tuple(self._cursor_row(name, None, None) for name in self._series)
        self.cursor_table.set_cursor_values(rows)
        self.cursor_empty_label.setVisible(not rows)

    def _clear_cursor_values(self) -> None:
        self._cursor_elapsed = None
        self.cursor_time_label.setText("Cursor: —")
        self._show_cursor_placeholders()

    def _update_cursor_values(self, elapsed_time: float) -> None:
        inspected = self.inspect_at(elapsed_time)
        rows = []
        for name in self._series:
            measurement_time, value = inspected.get(name, (None, None))
            rows.append(
                self._cursor_row(
                    name,
                    measurement_time,
                    value,
                    cursor_time=elapsed_time,
                )
            )
        self.cursor_time_label.setText(f"Cursor: {format_cursor_time(elapsed_time)}")
        self.cursor_table.set_cursor_values(tuple(rows))
        self.cursor_empty_label.setVisible(not rows)

    def _cursor_row(
        self,
        name: str,
        measurement_time: float | None,
        value: int | float | None,
        *,
        cursor_time: float | None = None,
    ) -> GraphCursorRow:
        presentation = self._metadata.get(name)
        valid_value = (
            value
            if value is not None and math.isfinite(float(value))
            else None
        )
        state = (
            evaluate_alarm(valid_value, presentation.alarms)
            if valid_value is not None
            else None
        )
        pen = self._series[name].opts["pen"]
        return GraphCursorRow(
            source_name=name,
            display_name=presentation.display_name,
            unit=presentation.unit,
            color=pen.color().name(),
            cursor_time=cursor_time,
            measurement_time=measurement_time,
            value=valid_value,
            status=state,
        )

    def _update_statistics(
        self,
        points: dict[str, tuple[tuple[float, ...], tuple[int | float, ...]]],
    ) -> None:
        lower, upper = self.plot_widget.viewRange()[0]
        rows = []
        for name, (x_values, y_values) in points.items():
            statistics = calculate_statistics(x_values, y_values, lower, upper)
            if statistics is not None:
                presentation = self._metadata.get(name)
                pen = self._series[name].opts["pen"]
                rows.append(
                    GraphStatisticsRow(
                        source_name=name,
                        display_name=presentation.display_name,
                        unit=presentation.unit,
                        color=pen.color().name(),
                        minimum=statistics.minimum,
                        average=statistics.average,
                        maximum=statistics.maximum,
                    )
                )
        self.statistics_table.set_statistics(tuple(rows))
        self.statistics_empty_label.setVisible(not rows)
        if not rows:
            self.statistics_empty_label.setText(
                "No measured data in the visible range."
                if self._series
                else "Select a channel to view statistics."
            )
