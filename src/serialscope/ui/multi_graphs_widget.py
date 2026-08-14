"""Device-separated graph workspaces."""

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget

from serialscope.data import ChannelMetadataRegistry, EventMarker
from serialscope.parsing import ChannelUpdate
from serialscope.replay import ReplaySession, ReplaySource
from serialscope.ui.graphs_widget import GraphsWidget
from serialscope.ui.theme import DARK_GRAPH_PALETTE, GraphPalette


class MultiSourceGraphsWidget(QWidget):
    """Keep one complete GraphsWidget state per device."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        selector_row = QHBoxLayout()
        self.source_label = QLabel("Device")
        selector_row.addWidget(self.source_label)
        self.source_combo = QComboBox()
        self.source_combo.setObjectName("graphSourceCombo")
        selector_row.addWidget(self.source_combo)
        selector_row.addStretch()
        layout.addLayout(selector_row)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self._widgets: dict[str, GraphsWidget] = {}
        self._palette = DARK_GRAPH_PALETTE
        self._events: tuple[EventMarker, ...] = ()
        self.source_combo.currentIndexChanged.connect(self._select_current)
        self._update_selector_visibility()

    @property
    def active_widget(self) -> GraphsWidget:
        source_id = self.source_combo.currentData()
        return self._widgets[str(source_id)]

    def ensure_source(self, source_id: str, display_name: str) -> GraphsWidget:
        if source_id in self._widgets:
            index = self.source_combo.findData(source_id)
            if index >= 0:
                self.source_combo.setItemText(index, display_name)
            self._update_selector_visibility()
            return self._widgets[source_id]
        widget = GraphsWidget()
        widget.apply_theme(self._palette)
        widget.set_events(self._events)
        self._widgets[source_id] = widget
        self.stack.addWidget(widget)
        self.source_combo.addItem(display_name, source_id)
        self._update_selector_visibility()
        return widget

    def remove_source(self, source_id: str) -> None:
        widget = self._widgets.pop(source_id, None)
        if widget is None:
            return
        self.stack.removeWidget(widget)
        widget.deleteLater()
        index = self.source_combo.findData(source_id)
        if index >= 0:
            self.source_combo.removeItem(index)
        self._update_selector_visibility()

    def _update_selector_visibility(self) -> None:
        multiple = len(self._widgets) >= 2
        self.source_label.setVisible(multiple)
        self.source_combo.setVisible(multiple)

    def update_source(self, source_id: str, display_name: str, update: ChannelUpdate) -> None:
        self.ensure_source(source_id, display_name).update_channels(update)

    def load_multi_replay(self, session: ReplaySession) -> None:
        self._events = session.events
        for source_id in tuple(self._widgets):
            self.remove_source(source_id)
        for source in session.sources:
            widget = self.ensure_source(source.source_id, source.display_name)
            adapted = ReplaySession(
                session.directory,
                source.metadata,
                source.channel_names,
                source.samples,
                (source,),
                session.events,
            )
            widget.load_replay(adapted)

    @property
    def events(self) -> tuple[EventMarker, ...]:
        return self._events

    def set_events(self, events: tuple[EventMarker, ...]) -> None:
        self._events = tuple(events)
        for widget in self._widgets.values():
            widget.set_events(self._events)

    def set_source_metadata(self, source_id: str, registry: ChannelMetadataRegistry) -> None:
        self._widgets[source_id].set_channel_metadata(registry)

    def apply_theme(self, palette: GraphPalette) -> None:
        self._palette = palette
        for widget in self._widgets.values():
            widget.apply_theme(palette)

    def reset_source(self, source_id: str) -> None:
        if source_id in self._widgets:
            self._widgets[source_id].reset()

    def reset_all(self) -> None:
        self._events = ()
        for widget in self._widgets.values():
            widget.reset()

    def _select_current(self) -> None:
        source_id = self.source_combo.currentData()
        if source_id is not None:
            self.stack.setCurrentWidget(self._widgets[str(source_id)])

    # Compatibility facade for the original single-device MainWindow API.
    @property
    def history(self):
        return self.active_widget.history

    @property
    def channel_names(self):
        return self.active_widget.channel_names

    @property
    def selected_channels(self):
        return self.active_widget.selected_channels

    @property
    def is_paused(self):
        return self.active_widget.is_paused

    @property
    def plot_widget(self):
        return self.active_widget.plot_widget

    @property
    def clear_button(self):
        return self.active_widget.clear_button

    @property
    def _series(self):
        return self.active_widget._series

    @property
    def _refresh_timer(self):
        return self.active_widget._refresh_timer

    def update_channels(self, update: ChannelUpdate) -> None:
        self.active_widget.update_channels(update)

    def set_channel_selected(self, name: str, selected: bool) -> None:
        self.active_widget.set_channel_selected(name, selected)

    def has_series(self, name: str) -> bool:
        return self.active_widget.has_series(name)

    def toggle_pause(self) -> None:
        self.active_widget.toggle_pause()

    def clear_history(self) -> None:
        self.active_widget.clear_history()

    def reset(self) -> None:
        self._events = ()
        self.active_widget.reset()

    def load_replay(self, session: ReplaySession) -> None:
        self._events = session.events
        self.active_widget.load_replay(session)

    def set_channel_metadata(self, registry: ChannelMetadataRegistry) -> None:
        self.active_widget.set_channel_metadata(registry)
