"""Selectable live plotting of structured numeric channels."""

from collections.abc import Callable
import time

import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from serialscope.data import ChannelHistory
from serialscope.parsing import ChannelUpdate


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

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setObjectName("livePlot")
        self.plot_widget.setBackground("#0a1016")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.18)
        self.plot_widget.setLabel("bottom", "Elapsed time", units="s")
        self.plot_widget.setLabel("left", "Value")
        self.plot_widget.addLegend()
        layout.addWidget(self.plot_widget, 1)

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
        for name, series in self._series.items():
            x_values, y_values = self.history.points(name)
            series.setData(x_values, y_values)

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
            self.refresh_plot()
        else:
            series = self._series.pop(name, None)
            if series is not None:
                self.plot_widget.removeItem(series)
