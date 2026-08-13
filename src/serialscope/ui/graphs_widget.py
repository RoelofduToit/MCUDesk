"""Selectable live plotting of structured numeric channels."""

from collections.abc import Callable
import time

import pyqtgraph as pg
from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

from serialscope.data import (
    ChannelHistory,
    calculate_statistics,
    nearest_measurement,
    process_display_points,
)
from serialscope.parsing import ChannelUpdate
from serialscope.replay import ReplaySession
from serialscope.ui.elapsed_time_axis import ElapsedTimeAxis
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
        self._selectors: dict[str, QCheckBox] = {}
        self._series: dict[str, pg.PlotDataItem] = {}
        self._measured_series: dict[str, pg.PlotDataItem] = {}
        self._paused = False
        self._replay_session: ReplaySession | None = None
        self._graph_palette = DARK_GRAPH_PALETTE

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        channel_label = QLabel("Channels")
        channel_label.setObjectName("graphChannelsLabel")
        layout.addWidget(channel_label)

        self.selector_scroll = QScrollArea()
        self.selector_scroll.setObjectName("graphChannelSelector")
        self.selector_scroll.setWidgetResizable(True)
        self.selector_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.selector_scroll.setMaximumHeight(84)
        selector_content = QWidget()
        self._selector_layout = QHBoxLayout(selector_content)
        self._selector_layout.setContentsMargins(0, 0, 0, 0)
        self._selector_layout.setSpacing(14)
        self._selector_layout.addStretch()
        self.selector_scroll.setWidget(selector_content)
        layout.addWidget(self.selector_scroll)

        controls = QWidget()
        controls.setObjectName("graphControls")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setObjectName("graphPauseButton")
        self.pause_button.clicked.connect(self.toggle_pause)
        controls_layout.addWidget(self.pause_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("graphClearButton")
        self.clear_button.clicked.connect(self.clear_history)
        controls_layout.addWidget(self.clear_button)

        self.reset_zoom_button = QPushButton("Reset Zoom")
        self.reset_zoom_button.setObjectName("graphResetZoomButton")
        self.reset_zoom_button.clicked.connect(self.reset_zoom)
        controls_layout.addWidget(self.reset_zoom_button)
        controls_layout.addStretch()

        window_label = QLabel("Time Window")
        window_label.setObjectName("graphTimeWindowLabel")
        controls_layout.addWidget(window_label)

        self.time_window_combo = QComboBox()
        self.time_window_combo.setObjectName("graphTimeWindowCombo")
        for label, seconds in TIME_WINDOWS.items():
            self.time_window_combo.addItem(label, seconds)
        self.time_window_combo.setCurrentText("60 s")
        self.time_window_combo.currentIndexChanged.connect(self.refresh_plot)
        controls_layout.addWidget(self.time_window_combo)
        layout.addWidget(controls)

        processing = QWidget()
        processing.setObjectName("graphProcessingControls")
        processing_layout = QHBoxLayout(processing)
        processing_layout.setContentsMargins(0, 0, 0, 0)
        processing_layout.setSpacing(8)

        processing_layout.addWidget(QLabel("Interpolation"))
        self.interpolation_combo = QComboBox()
        self.interpolation_combo.setObjectName("graphInterpolationCombo")
        self.interpolation_combo.addItem("Off", "off")
        self.interpolation_combo.addItem("Linear", "linear")
        self.interpolation_combo.addItem("PCHIP", "pchip")
        processing_layout.addWidget(self.interpolation_combo)

        processing_layout.addWidget(QLabel("Density"))
        self.density_combo = QComboBox()
        self.density_combo.setObjectName("graphInterpolationDensityCombo")
        for density in (2, 5, 10):
            self.density_combo.addItem(f"{density}x", density)
        self.density_combo.setCurrentText("5x")
        processing_layout.addWidget(self.density_combo)

        processing_layout.addWidget(QLabel("Max Gap"))
        self.max_gap_combo = QComboBox()
        self.max_gap_combo.setObjectName("graphMaxGapCombo")
        for label, seconds in (("1 s", 1.0), ("2 s", 2.0), ("5 s", 5.0), ("10 s", 10.0), ("Unlimited", None)):
            self.max_gap_combo.addItem(label, seconds)
        self.max_gap_combo.setCurrentText("5 s")
        processing_layout.addWidget(self.max_gap_combo)

        self.measured_points_checkbox = QCheckBox("Show measured points")
        self.measured_points_checkbox.setObjectName("graphMeasuredPointsCheckBox")
        processing_layout.addWidget(self.measured_points_checkbox)
        processing_layout.addStretch()
        layout.addWidget(processing)

        smoothing = QWidget()
        smoothing.setObjectName("graphSmoothingControls")
        smoothing_layout = QHBoxLayout(smoothing)
        smoothing_layout.setContentsMargins(0, 0, 0, 0)
        smoothing_layout.setSpacing(8)
        smoothing_layout.addWidget(QLabel("Smoothing"))
        self.smoothing_combo = QComboBox()
        self.smoothing_combo.setObjectName("graphSmoothingCombo")
        self.smoothing_combo.addItem("Off", "off")
        self.smoothing_combo.addItem("Moving Average", "moving_average")
        self.smoothing_combo.addItem("EMA", "ema")
        smoothing_layout.addWidget(self.smoothing_combo)
        self.moving_average_label = QLabel("Window (samples)")
        smoothing_layout.addWidget(self.moving_average_label)
        self.moving_average_spin = QSpinBox()
        self.moving_average_spin.setObjectName("graphMovingAverageWindow")
        self.moving_average_spin.setRange(2, 100)
        self.moving_average_spin.setValue(5)
        smoothing_layout.addWidget(self.moving_average_spin)
        self.ema_alpha_label = QLabel("Alpha")
        smoothing_layout.addWidget(self.ema_alpha_label)
        self.ema_alpha_spin = QDoubleSpinBox()
        self.ema_alpha_spin.setObjectName("graphEmaAlpha")
        self.ema_alpha_spin.setRange(0.01, 1.0)
        self.ema_alpha_spin.setSingleStep(0.05)
        self.ema_alpha_spin.setDecimals(2)
        self.ema_alpha_spin.setValue(0.2)
        smoothing_layout.addWidget(self.ema_alpha_spin)
        smoothing_layout.addStretch()
        layout.addWidget(smoothing)
        self._update_processing_control_state()

        self.elapsed_time_axis = ElapsedTimeAxis()
        self.plot_widget = pg.PlotWidget(
            axisItems={"bottom": self.elapsed_time_axis}
        )
        self.plot_widget.setObjectName("livePlot")
        self.plot_widget.setBackground("#0a1016")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.18)
        self.plot_widget.setLabel("left", "Value")
        self.plot_widget.addLegend()
        self._cursor_line: pg.InfiniteLine | None = None
        layout.addWidget(self.plot_widget, 1)

        self.cursor_readout = QLabel("Move over the graph to inspect measured values.")
        self.cursor_readout.setObjectName("graphCursorReadout")
        self.cursor_readout.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.cursor_readout)
        self.statistics_label = QLabel("Statistics: select a channel")
        self.statistics_label.setObjectName("graphStatisticsLabel")
        self.statistics_label.setWordWrap(True)
        layout.addWidget(self.statistics_label)
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
        self.refresh_plot()

    def set_channel_selected(self, name: str, selected: bool) -> None:
        self._selectors[name].setChecked(selected)

    def has_series(self, name: str) -> bool:
        return name in self._series

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
        self.statistics_label.setText("Statistics: no measured data")
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
        legend = self.plot_widget.plotItem.legend
        if legend is not None:
            legend.setBrush(palette.background)
            legend.setPen(palette.foreground)
            for _sample, label in legend.items:
                label.setText(label.text, color=palette.foreground)

    def reset(self) -> None:
        """Clear selector, series, and history for a new connection."""
        for checkbox in self._selectors.values():
            self._selector_layout.removeWidget(checkbox)
            checkbox.deleteLater()
        self._selectors.clear()
        for series in tuple(self._series.values()):
            self.plot_widget.removeItem(series)
        self._series.clear()
        for series in tuple(self._measured_series.values()):
            self.plot_widget.removeItem(series)
        self._measured_series.clear()
        self.history.reset()
        self._replay_session = None
        self._paused = False
        self.pause_button.setText("Pause")
        if self._cursor_line is not None:
            self._cursor_line.hide()
        self.cursor_readout.setText("Move over the graph to inspect measured values.")
        self.statistics_label.setText("Statistics: select a channel")
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
        lower, upper = visible_x_range(latest_time, self.time_window_seconds)
        self.plot_widget.setXRange(lower, upper, padding=0)

    def _set_channel_selected(self, name: str, selected: bool) -> None:
        if selected:
            color = pg.intColor(
                list(self._selectors).index(name),
                hues=12,
                minValue=180,
            )
            self._series[name] = self.plot_widget.plot(
                name=name,
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

    def _add_channel(self, name: str) -> None:
        if name in self._selectors:
            return
        checkbox = QCheckBox(name)
        checkbox.setObjectName("graphChannelCheckBox")
        checkbox.toggled.connect(
            lambda selected, channel=name: self._set_channel_selected(
                channel, selected
            )
        )
        self._selector_layout.insertWidget(self._selector_layout.count() - 1, checkbox)
        self._selectors[name] = checkbox

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
            return
        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(position)
        target = max(0.0, mouse_point.x())
        self.cursor_line.setPos(target)
        self.cursor_line.show()
        lines = [f"Time: {target:.2f} s"]
        for name, points in self._source_points().items():
            nearest = nearest_measurement(*points, target)
            if nearest is not None:
                timestamp, value = nearest
                lines.append(f"{name}: {value:g}  (measured at {timestamp:.2f} s)")
        self.cursor_readout.setText("   |   ".join(lines))

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

    def _update_statistics(
        self,
        points: dict[str, tuple[tuple[float, ...], tuple[int | float, ...]]],
    ) -> None:
        lower, upper = self.plot_widget.viewRange()[0]
        rows = []
        for name, (x_values, y_values) in points.items():
            statistics = calculate_statistics(x_values, y_values, lower, upper)
            if statistics is not None:
                rows.append(
                    f"{name}  Min {statistics.minimum:g}  Max {statistics.maximum:g}  Avg {statistics.average:g}"
                )
        self.statistics_label.setText("   |   ".join(rows) if rows else "Statistics: no measured data")
