"""Selectable live plotting of structured numeric channels."""

from collections.abc import Callable
import time

import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from serialscope.data import ChannelHistory
from serialscope.parsing import ChannelUpdate
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
        self._paused = False
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

        self.elapsed_time_axis = ElapsedTimeAxis()
        self.plot_widget = pg.PlotWidget(
            axisItems={"bottom": self.elapsed_time_axis}
        )
        self.plot_widget.setObjectName("livePlot")
        self.plot_widget.setBackground("#0a1016")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.18)
        self.plot_widget.setLabel("left", "Value")
        self.plot_widget.addLegend()
        layout.addWidget(self.plot_widget, 1)
        self.apply_theme(DARK_GRAPH_PALETTE)
        self._apply_x_range(0.0)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(100)
        self._refresh_timer.timeout.connect(self.refresh_plot)
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
            if name in self._selectors:
                continue
            checkbox = QCheckBox(name)
            checkbox.setObjectName("graphChannelCheckBox")
            checkbox.toggled.connect(
                lambda selected, channel=name: self._set_channel_selected(
                    channel, selected
                )
            )
            self._selector_layout.insertWidget(self._selector_layout.count() - 1, checkbox)
            self._selectors[name] = checkbox

    def set_channel_selected(self, name: str, selected: bool) -> None:
        self._selectors[name].setChecked(selected)

    def has_series(self, name: str) -> bool:
        return name in self._series

    def refresh_plot(self) -> None:
        if self._paused:
            return

        points = {
            name: self.history.points(name) for name in self._series
        }
        latest_time = max(
            (x_values[-1] for x_values, _y_values in points.values() if x_values),
            default=None,
        )
        cutoff = (
            latest_time - self.time_window_seconds
            if latest_time is not None
            else None
        )
        for name, series in self._series.items():
            x_values, y_values = points[name]
            if x_values and cutoff is not None:
                visible = next(
                    (index for index, timestamp in enumerate(x_values) if timestamp >= cutoff),
                    len(x_values),
                )
                series.setData(x_values[visible:], y_values[visible:])
            else:
                series.setData([], [])
        self._apply_x_range(latest_time or 0.0)

    def toggle_pause(self) -> None:
        """Freeze or resume plot presentation without stopping acquisition."""
        self._paused = not self._paused
        self.pause_button.setText("Resume" if self._paused else "Pause")
        if not self._paused:
            self.refresh_plot()

    def clear_history(self) -> None:
        """Clear active-connection history while preserving channel choices."""
        self.history.reset()
        for series in self._series.values():
            series.setData([], [])
        self._apply_x_range(0.0)

    def apply_theme(self, palette: GraphPalette) -> None:
        """Update graph surfaces without altering history or selections."""
        self._graph_palette = palette
        self.plot_widget.setBackground(palette.background)
        for orientation in ("bottom", "left"):
            axis = self.plot_widget.getAxis(orientation)
            axis.setPen(palette.foreground)
            axis.setTextPen(palette.foreground)
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
        self.history.reset()
        self._paused = False
        self.pause_button.setText("Pause")
        self._apply_x_range(0.0)

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
            self.apply_theme(self._graph_palette)
            self.refresh_plot()
        else:
            series = self._series.pop(name, None)
            if series is not None:
                self.plot_widget.removeItem(series)
