"""Responsive HMI-style dashboard for selected structured channels."""

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from serialscope.parsing import ChannelUpdate
from serialscope.data import (
    ChannelMetadataRegistry,
    DashboardLayout,
    GridPosition,
    evaluate_alarm,
)
from serialscope.replay import ReplaySession
from serialscope.ui.channel_tile import ChannelTile


class DashboardWidget(QWidget):
    """Maintain channel choices and update existing tiles in place."""

    _PREFERRED_TILE_SIZE = 210
    _MINIMUM_TILE_SIZE = 150
    _GRID_SPACING = 12
    _MIME_TYPE = "application/x-serialscope-dashboard-channel"

    def __init__(
        self, parent: QWidget | None = None, *, lazy: bool = False
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardWidget")
        self._available_names: list[str] = []
        self._items: dict[str, QCheckBox] = {}
        self._latest_values: dict[str, int | float] = {}
        self._tiles: dict[str, ChannelTile] = {}
        self.layout_model = DashboardLayout(columns=4)
        self._column_count = 1
        self._tile_size = self._PREFERRED_TILE_SIZE
        self._metadata = ChannelMetadataRegistry()
        self._drop_candidate: GridPosition | None = None
        self._built = False
        self.setAcceptDrops(True)
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
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.tile_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.tile_scroll.viewport().installEventFilter(self)
        self._tile_content = QWidget()
        self._tile_content.setObjectName("dashboardTileContent")
        self._drop_indicator = QFrame(self._tile_content)
        self._drop_indicator.setObjectName("dashboardDropIndicator")
        self._drop_indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._drop_indicator.hide()
        self.tile_scroll.setWidget(self._tile_content)
        layout.addWidget(self.tile_scroll, 1)

        self.empty_label = QLabel(
            "No dashboard channels selected.\nSelect channels to add live indicators.",
            self._tile_content,
        )
        self.empty_label.setObjectName("dashboardEmptyLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
                tile.set_alarm_state(
                    evaluate_alarm(value, self._metadata.get(name).alarms)
                )

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
            self.layout_model.reset()
            return
        for checkbox in self._items.values():
            self._selector_layout.removeWidget(checkbox)
            checkbox.setParent(None)
        self._items.clear()
        self._available_names.clear()
        self._latest_values.clear()
        for tile in self._tiles.values():
            tile.setParent(None)
        self._tiles.clear()
        self.layout_model.reset()
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
            tile.set_alarm_state(
                evaluate_alarm(
                    self._latest_values.get(source_name),
                    registry.get(source_name).alarms,
                )
            )

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._built:
            self._reflow()

    def eventFilter(self, watched: object, event: QEvent) -> bool:  # noqa: N802
        if (
            self._built
            and watched is self.tile_scroll.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self._reflow()
        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasFormat(self._MIME_TYPE):
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if not event.mimeData().hasFormat(self._MIME_TYPE):
            return
        self._auto_scroll(event.position().toPoint())
        destination = self._calculate_target_cell(event.position().toPoint())
        self._set_drop_candidate(destination)
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        if event.mimeData().hasFormat(self._MIME_TYPE):
            source_name = bytes(event.mimeData().data(self._MIME_TYPE)).decode("utf-8")
            if self._commit_drop(source_name):
                event.acceptProposedAction()
        self._clear_drop_state()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        self._clear_drop_state()
        super().dragLeaveEvent(event)

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
                tile = ChannelTile(name, self._tile_content)
                tile.set_presentation(self._metadata.get(name))
                value = self._latest_values.get(name)
                if value is not None:
                    tile.set_value(value)
                tile.set_alarm_state(
                    evaluate_alarm(value, self._metadata.get(name).alarms)
                )
                self._tiles[name] = tile
                self.layout_model.add(name)
                tile.show()
        else:
            tile = self._tiles.pop(name, None)
            if tile is not None:
                tile.setParent(None)
            self.layout_model.remove(name)
        self.empty_label.setVisible(not self._tiles)
        self._reflow(force=True)

    def _reflow(self, force: bool = False) -> None:
        width = max(1, self.tile_scroll.viewport().width())
        tile_size = (
            self._PREFERRED_TILE_SIZE
            if width >= self._PREFERRED_TILE_SIZE
            else self._MINIMUM_TILE_SIZE
        )
        column_count = self._columns_for_width(width, tile_size)
        if (
            not force
            and tile_size == self._tile_size
            and column_count == self._column_count
        ):
            return
        self._tile_size = tile_size
        self._column_count = column_count
        self.layout_model.columns = column_count
        self._render_grid()

    def _columns_for_width(self, width: int, tile_size: int | None = None) -> int:
        size = self._tile_size if tile_size is None else tile_size
        return max(1, (max(1, width) + self._GRID_SPACING) // (size + self._GRID_SPACING))

    def move_tile(self, source_name: str, destination: GridPosition) -> None:
        """Snap one source-keyed tile into a cell, swapping any occupant."""
        self.layout_model.move(source_name, destination)
        self._render_grid()

    def tile_position(self, source_name: str) -> GridPosition | None:
        return self.layout_model.position(source_name)

    def _render_grid(self) -> None:
        for source_name, tile in self._tiles.items():
            position = self.layout_model.position(source_name)
            if position is None:
                continue
            tile.setFixedSize(self._tile_size, self._tile_size)
            tile.setGeometry(self.cell_rect(position))
        self._update_canvas_extent()

    def _calculate_target_cell(self, point: QPoint) -> GridPosition:
        """Map one Dashboard-local cursor point into grid-content coordinates."""
        content_point = self._tile_content.mapFrom(self, point)
        return self._position_from_content_point(content_point)

    def _position_from_content_point(self, point: QPoint) -> GridPosition:
        """Map a canvas point with the same pitch used by :meth:`cell_rect`."""
        pitch = self._tile_size + self._GRID_SPACING
        return GridPosition(
            max(0, point.y()) // pitch,
            min(self._column_count - 1, max(0, point.x()) // pitch),
        )

    def cell_rect(self, position: GridPosition) -> QRect:
        """Return the one authoritative square rectangle for a logical cell."""
        pitch = self._tile_size + self._GRID_SPACING
        return QRect(position.column * pitch, position.row * pitch, self._tile_size, self._tile_size)

    def _cell_geometry(self, position: GridPosition) -> QRect:
        return self.cell_rect(position)

    def _set_drop_candidate(self, destination: GridPosition) -> None:
        """Move only the lightweight preview when the candidate cell changes."""
        if destination == self._drop_candidate:
            return
        self._drop_candidate = destination
        self._drop_indicator.setFixedSize(self._tile_size, self._tile_size)
        self._drop_indicator.setGeometry(self.cell_rect(destination))
        self._drop_indicator.setToolTip(
            f"Drop at row {destination.row + 1}, column {destination.column + 1}"
        )
        self._drop_indicator.show()
        self._update_canvas_extent()
        self._drop_indicator.raise_()

    def _commit_drop(self, source_name: str) -> bool:
        """Commit exactly the cell represented by the current outline."""
        if self._drop_candidate is None or source_name not in self._tiles:
            return False
        self.move_tile(source_name, self._drop_candidate)
        return True

    def _clear_drop_state(self) -> None:
        self._drop_candidate = None
        self._drop_indicator.hide()
        self._update_canvas_extent()

    def _update_canvas_extent(self) -> None:
        viewport = self.tile_scroll.viewport().size()
        positions = [
            position
            for name in self._tiles
            if (position := self.layout_model.position(name)) is not None
        ]
        if self._drop_candidate is not None:
            positions.append(self._drop_candidate)
        maximum_column = max((position.column for position in positions), default=-1)
        maximum_row = max((position.row for position in positions), default=-1)
        visible_rows = max(
            1,
            (max(1, viewport.height()) + self._GRID_SPACING)
            // (self._tile_size + self._GRID_SPACING),
        )
        rows = max(visible_rows, maximum_row + 2)
        columns = max(self._column_count, maximum_column + 1)
        width = max(
            viewport.width(),
            columns * self._tile_size + max(0, columns - 1) * self._GRID_SPACING,
        )
        height = max(
            viewport.height(),
            rows * self._tile_size + max(0, rows - 1) * self._GRID_SPACING,
        )
        self._tile_content.setMinimumSize(QSize(width, height))
        self._tile_content.resize(width, height)
        self.empty_label.setGeometry(0, 0, width, min(height, viewport.height()))

    def _auto_scroll(self, point: object) -> None:
        """Scroll gently near viewport edges without touching tile layout."""
        viewport = self.tile_scroll.viewport()
        viewport_point = viewport.mapFrom(self, point)
        bar = self.tile_scroll.verticalScrollBar()
        edge = 28
        step = 12
        if 0 <= viewport_point.y() < edge:
            bar.setValue(bar.value() - step)
        elif viewport.height() - edge < viewport_point.y() <= viewport.height():
            bar.setValue(bar.value() + step)
