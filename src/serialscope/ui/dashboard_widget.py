"""Responsive HMI-style dashboard for selected structured channels."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from serialscope.parsing import ChannelUpdate
from serialscope.data import ChannelMetadataRegistry
from serialscope.replay import ReplaySession
from serialscope.ui.channel_tile import ChannelTile


class DashboardWidget(QWidget):
    """Maintain channel choices and update existing tiles in place."""

    _TARGET_TILE_WIDTH = 220

    def __init__(
        self, parent: QWidget | None = None, *, lazy: bool = False
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardWidget")
        self._available_names: list[str] = []
        self._items: dict[str, QCheckBox] = {}
        self._latest_values: dict[str, int | float] = {}
        self._tiles: dict[str, ChannelTile] = {}
        self._column_count = 0
        self._metadata = ChannelMetadataRegistry()
        self._built = False
        if not lazy:
            self._build_ui()

    def _build_ui(self) -> None:
        if self._built:
            return
        self._built = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        selector_label = QLabel("Dashboard channels")
        selector_label.setObjectName("dashboardSelectorLabel")
        layout.addWidget(selector_label)

        self.channel_selector = QScrollArea()
        self.channel_selector.setObjectName("dashboardChannelSelector")
        self.channel_selector.setWidgetResizable(True)
        self.channel_selector.setFrameShape(QFrame.Shape.NoFrame)
        self.channel_selector.setMaximumHeight(112)
        self.channel_selector.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.channel_selector.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        selector_content = QWidget()
        selector_content.setObjectName("dashboardSelectorContent")
        self._selector_layout = QVBoxLayout(selector_content)
        self._selector_layout.setContentsMargins(5, 5, 5, 5)
        self._selector_layout.setSpacing(3)
        self._selector_layout.addStretch()
        self.channel_selector.setWidget(selector_content)
        layout.addWidget(self.channel_selector)

        self.tile_scroll = QScrollArea()
        self.tile_scroll.setObjectName("dashboardTileScroll")
        self.tile_scroll.setWidgetResizable(True)
        self.tile_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.tile_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.tile_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._tile_content = QWidget()
        self._tile_content.setObjectName("dashboardTileContent")
        self._grid = QGridLayout(self._tile_content)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(12)
        self.tile_scroll.setWidget(self._tile_content)
        layout.addWidget(self.tile_scroll, 1)

        self.empty_label = QLabel(
            "No dashboard channels selected.\nSelect channels to add live indicators.",
            self._tile_content,
        )
        self.empty_label.setObjectName("dashboardEmptyLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid.addWidget(self.empty_label, 0, 0)
        for name in self._available_names:
            self._add_checkbox(name)

    @property
    def channel_names(self) -> tuple[str, ...]:
        return tuple(self._available_names)

    @property
    def selected_channels(self) -> tuple[str, ...]:
        return tuple(name for name in self._items if name in self._tiles)

    @property
    def tile_count(self) -> int:
        return len(self._tiles)

    def update_channels(self, update: ChannelUpdate) -> None:
        """Consume one existing structured update without parsing raw input."""
        if update.replace_channels and self.channel_names != update.names:
            self.reset()
        self._add_channels(update.names)
        for name, value in zip(update.names, update.values, strict=True):
            self._latest_values[name] = value
            tile = self._tiles.get(name)
            if tile is not None:
                tile.set_value(value)

    def load_replay(self, session: ReplaySession) -> None:
        """Expose replay channels and their final recorded values."""
        self.reset()
        self._add_channels(session.channel_names)
        self._latest_values.update(session.latest_values)

    def reset(self) -> None:
        """Clear all availability, selections, values, and tiles."""
        if not self._built:
            self._available_names.clear()
            self._items.clear()
            self._latest_values.clear()
            self._tiles.clear()
            return
        for checkbox in self._items.values():
            self._selector_layout.removeWidget(checkbox)
            checkbox.setParent(None)
        self._items.clear()
        self._available_names.clear()
        self._latest_values.clear()
        for tile in self._tiles.values():
            self._grid.removeWidget(tile)
            tile.setParent(None)
        self._tiles.clear()
        self._column_count = 0
        self.empty_label.show()
        self._reflow(force=True)

    def set_channel_selected(self, name: str, selected: bool) -> None:
        self._build_ui()
        self._items[name].setChecked(selected)

    def tile_value_text(self, name: str) -> str | None:
        tile = self._tiles.get(name)
        return tile.value_label.text() if tile is not None else None

    def set_channel_metadata(self, registry: ChannelMetadataRegistry) -> None:
        self._metadata = registry
        for source_name, checkbox in self._items.items():
            presentation = registry.get(source_name)
            checkbox.setText(presentation.display_name)
            checkbox.setToolTip(f"Source: {source_name}")
        for source_name, tile in self._tiles.items():
            tile.set_presentation(registry.get(source_name))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._built:
            self._reflow()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        self._build_ui()
        super().showEvent(event)

    def _add_channels(self, names: tuple[str, ...]) -> None:
        for name in names:
            if name in self._available_names:
                continue
            self._available_names.append(name)
            if self._built:
                self._add_checkbox(name)

    def _add_checkbox(self, name: str) -> None:
        if name in self._items:
            return
        checkbox = QCheckBox(name)
        checkbox.setObjectName("dashboardChannelCheckBox")
        checkbox.setProperty("channelName", name)
        checkbox.toggled.connect(self._selection_changed_from_sender)
        self._selector_layout.insertWidget(
            self._selector_layout.count() - 1, checkbox
        )
        self._items[name] = checkbox
        presentation = self._metadata.get(name)
        checkbox.setText(presentation.display_name)
        checkbox.setToolTip(f"Source: {name}")

    def _selection_changed_from_sender(self, selected: bool) -> None:
        checkbox = self.sender()
        if isinstance(checkbox, QCheckBox):
            self._selection_changed(str(checkbox.property("channelName")), selected)

    def _selection_changed(self, name: str, selected: bool) -> None:
        if selected:
            if name not in self._tiles:
                tile = ChannelTile(name)
                tile.set_presentation(self._metadata.get(name))
                value = self._latest_values.get(name)
                if value is not None:
                    tile.set_value(value)
                self._tiles[name] = tile
        else:
            tile = self._tiles.pop(name, None)
            if tile is not None:
                self._grid.removeWidget(tile)
                tile.setParent(None)
        self.empty_label.setVisible(not self._tiles)
        self._reflow(force=True)

    def _reflow(self, force: bool = False) -> None:
        width = max(1, self.tile_scroll.viewport().width())
        columns = max(1, width // self._TARGET_TILE_WIDTH)
        if not force and columns == self._column_count:
            return
        self._column_count = columns
        for index, tile in enumerate(self._tiles.values()):
            self._grid.addWidget(tile, index // columns, index % columns)
        if not self._tiles:
            self._grid.addWidget(self.empty_label, 0, 0, 1, columns)
