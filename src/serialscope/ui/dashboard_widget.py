"""Responsive HMI-style dashboard for selected structured channels."""

from collections.abc import Callable

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
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from serialscope.parsing import ChannelUpdate
from serialscope.settings import (
    DEFAULT_DASHBOARD_TREND_WINDOW_SECONDS,
    normalize_dashboard_trend_window,
)
from serialscope.data import (
    AlarmState,
    ChannelHistory,
    ChannelKey,
    ChannelMetadataRegistry,
    DashboardLayout,
    GridPosition,
    evaluate_alarm,
)
from serialscope.ui.channel_tile import SPARKLINE_MAX_SAMPLES, ChannelTile
from serialscope.ui.fonts import (
    NumericDisplayStyle,
    normalize_numeric_display_style,
)
from serialscope.replay import ReplaySample, ReplaySession
from serialscope.ui.channel_colors import sparkline_color_for_channel
from serialscope.ui.channel_selector import ChannelSelector, ChannelToggle


DASHBOARD_TREND_RETENTION_SECONDS = 3_600.0
DASHBOARD_TREND_MAX_POINTS_PER_CHANNEL = 200_000
DASHBOARD_SPARKLINE_REFRESH_SECONDS = 0.25


def visible_trend_values(
    timestamps: tuple[float, ...],
    values: tuple[int | float, ...],
    window_seconds: float,
    max_samples: int = SPARKLINE_MAX_SAMPLES,
) -> tuple[int | float, ...]:
    """Filter by elapsed time, then visually thin without changing history."""
    if not timestamps or not values or max_samples < 1:
        return ()
    cutoff = timestamps[-1] - float(window_seconds)
    start = next(
        (index for index, timestamp in enumerate(timestamps) if timestamp >= cutoff),
        len(timestamps),
    )
    recent = values[start:]
    if len(recent) <= max_samples:
        return recent
    if max_samples == 1:
        return (recent[-1],)
    last = len(recent) - 1
    return tuple(
        recent[round(index * last / (max_samples - 1))]
        for index in range(max_samples)
    )


class DashboardWidget(QWidget):
    """Maintain channel choices and update existing tiles in place."""

    _PREFERRED_TILE_SIZE = 210
    _MINIMUM_TILE_SIZE = 150
    _GRID_SPACING = 12
    _MIME_TYPE = "application/x-serialscope-dashboard-channel"
    TILE_SIZE_PRESETS: tuple[tuple[str, int | None], ...] = (
        ("Auto", None),
        ("Compact", 150),
        ("Normal", 210),
        ("Large", 260),
        ("Extra large", 320),
    )

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        lazy: bool = False,
        clock: Callable[[], float] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardWidget")
        self._available_names: list[str] = []
        self._items: dict[str, ChannelToggle] = {}
        self._latest_values: dict[str, int | float] = {}
        history_options = {
            "window_seconds": DASHBOARD_TREND_RETENTION_SECONDS,
            "max_points_per_channel": DASHBOARD_TREND_MAX_POINTS_PER_CHANNEL,
        }
        if clock is not None:
            history_options["clock"] = clock
        self._trend = ChannelHistory(**history_options)
        self._trend_window_seconds = DEFAULT_DASHBOARD_TREND_WINDOW_SECONDS
        self._last_sparkline_refresh: dict[str, float] = {}
        self._tiles: dict[str, ChannelTile] = {}
        self.layout_model = DashboardLayout(columns=4)
        self._column_count = 1
        self._tile_size = self._PREFERRED_TILE_SIZE
        self._custom_tile_size: int | None = None
        self._metadata = ChannelMetadataRegistry()
        self._source_names: dict[str, str] = {}
        self._show_source_labels = False
        self._drop_candidate: GridPosition | None = None
        self._light_theme = False
        self._numeric_display_style = NumericDisplayStyle.DEFAULT
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

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        selector_label = QLabel("Dashboard channels")
        selector_label.setObjectName("dashboardSelectorLabel")
        selector_label.setMinimumWidth(0)
        selector_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        header_row.addWidget(selector_label, 1)
        tile_size_label = QLabel("Tile size")
        tile_size_label.setObjectName("dashboardTileSizeLabel")
        tile_size_label.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        header_row.addWidget(tile_size_label)
        self.tile_size_combo = QComboBox()
        self.tile_size_combo.setObjectName("dashboardTileSizeCombo")
        for label, pixels in self.TILE_SIZE_PRESETS:
            self.tile_size_combo.addItem(label, pixels)
        self.tile_size_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self.tile_size_combo.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        self.tile_size_combo.currentIndexChanged.connect(self._tile_size_changed)
        header_row.addWidget(self.tile_size_combo)
        layout.addLayout(header_row)

        self.channel_selector = ChannelSelector()
        self.channel_selector.selection_changed.connect(self._selection_changed)
        self._items = self.channel_selector.toggles
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
    def selected_channel_keys(self) -> tuple[ChannelKey, ...]:
        return tuple(
            ChannelKey.from_storage_key(name)
            for name in self.selected_channels
            if "\x1f" in name
        )

    @property
    def tile_count(self) -> int:
        return len(self._tiles)

    @property
    def custom_tile_size(self) -> int | None:
        """Return the user-selected tile edge length, or ``None`` for Auto."""
        return self._custom_tile_size

    @property
    def tile_size_preset(self) -> str:
        """Return the label of the active tile-size preset."""
        self._build_ui()
        return self.tile_size_combo.currentText()

    def set_tile_size_preset(self, label: str) -> None:
        """Select one named tile-size preset and reflow the grid."""
        self._build_ui()
        index = self.tile_size_combo.findText(label)
        if index < 0:
            raise ValueError(f"Unknown dashboard tile size preset: {label}")
        self.tile_size_combo.setCurrentIndex(index)

    def _tile_size_changed(self) -> None:
        self._custom_tile_size = self.tile_size_combo.currentData()
        self._reflow(force=True)

    def update_channels(self, update: ChannelUpdate) -> None:
        """Consume one existing structured update without parsing raw input."""
        # Parser replace updates list only the physical header. Calculated
        # channels are appended afterwards, so treating that header as the
        # complete dashboard set would destroy selected tiles on the next
        # sample. Availability is additive; tiles leave only on deselect or
        # an explicit remove_channel() when a definition is deleted.
        self._add_channels(update.names)
        self._trend.add_update(update)
        for name, value in zip(update.names, update.values, strict=True):
            self._latest_values[name] = value
            tile = self._tiles.get(name)
            if tile is not None:
                tile.set_value(value, record=False)
                tile.set_alarm_state(
                    evaluate_alarm(value, self._metadata.get(name).alarms)
                )
                self._refresh_tile_sparkline(name)

    def update_source(
        self, source_id: str, display_name: str, update: ChannelUpdate
    ) -> None:
        names = tuple(f"{source_id}\x1f{name}" for name in update.names)
        self._source_names.update({name: display_name for name in names})
        self.update_channels(ChannelUpdate(names, update.values, False))

    def set_source_count(self, count: int) -> None:
        self._show_source_labels = count >= 2
        for tile in self._tiles.values():
            tile.source_label.setVisible(self._show_source_labels)

    def remove_source(self, source_id: str) -> None:
        prefix = f"{source_id}\x1f"
        for name in tuple(self._items):
            if not name.startswith(prefix):
                continue
            self.channel_selector.remove_channel(name)
            self._available_names.remove(name)
            tile = self._tiles.pop(name, None)
            if tile is not None:
                tile.setParent(None)
            self.layout_model.remove(name)
            self._latest_values.pop(name, None)
            self._source_names.pop(name, None)
            self._last_sparkline_refresh.pop(name, None)
        if self._built:
            self.empty_label.setVisible(not self._tiles)
            self._apply_sparkline_colors()
            self._reflow(force=True)

    def apply_theme(self, theme: str) -> None:
        """Keep sparkline contrast aligned with the active tile background."""
        self._light_theme = theme == "light"
        self._apply_sparkline_colors()

    @property
    def numeric_display_style(self) -> str:
        return self._numeric_display_style.value

    def set_numeric_display_style(self, style: NumericDisplayStyle | str) -> None:
        """Apply a global numeric typeface to existing and future tiles."""
        self._numeric_display_style = normalize_numeric_display_style(style)
        for tile in self._tiles.values():
            tile.set_numeric_display_style(self._numeric_display_style)

    @property
    def trend_window_seconds(self) -> int:
        return self._trend_window_seconds

    def set_trend_window_seconds(self, seconds: int) -> None:
        """Apply one global visible sparkline duration without pruning history."""
        normalized = normalize_dashboard_trend_window(seconds)
        if normalized == self._trend_window_seconds:
            return
        self._trend_window_seconds = normalized
        self._refresh_all_sparklines()

    def _apply_sparkline_colors(self) -> None:
        names = tuple(self._available_names)
        for name, tile in self._tiles.items():
            tile.set_sparkline_color(
                sparkline_color_for_channel(
                    name, names, light_theme=self._light_theme
                )
            )

    def load_replay(self, session: ReplaySession) -> None:
        """Expose replay channels and preserve their recorded elapsed times."""
        self.reset()
        multi_source = bool(session.sources) and not (
            len(session.sources) == 1
            and session.sources[0].source_id == "legacy_source"
        )
        if not multi_source:
            self._add_channels(session.channel_names)
            self._latest_values.update(session.latest_values)
            self._load_replay_samples(session.samples)
            return
        for source in session.sources:
            names = tuple(
                f"{source.source_id}\x1f{name}" for name in source.channel_names
            )
            self._add_channels(names)
            self._source_names.update(
                {name: source.display_name for name in names}
            )
            self._latest_values.update(
                {
                    f"{source.source_id}\x1f{name}": value
                    for name, value in source.latest_values.items()
                }
            )
            self._load_replay_samples(
                source.samples,
                prefix=f"{source.source_id}\x1f",
            )
        self.set_source_count(len(session.sources))

    def reset(self) -> None:
        """Clear all availability, selections, values, and tiles."""
        if not self._built:
            self._available_names.clear()
            self._items.clear()
            self._latest_values.clear()
            self._source_names.clear()
            self._show_source_labels = False
            self._trend.reset()
            self._last_sparkline_refresh.clear()
            self._tiles.clear()
            self.layout_model.reset()
            return
        self.channel_selector.clear_channels()
        self._available_names.clear()
        self._latest_values.clear()
        self._source_names.clear()
        self._show_source_labels = False
        self._trend.reset()
        self._last_sparkline_refresh.clear()
        for tile in self._tiles.values():
            tile.setParent(None)
        self._tiles.clear()
        self.layout_model.reset()
        self.empty_label.show()
        self._reflow(force=True)

    def set_channel_selected(self, name: str | ChannelKey, selected: bool) -> None:
        self._build_ui()
        key = name.storage_key if isinstance(name, ChannelKey) else name
        self.channel_selector.set_channel_checked(key, selected)

    def remove_channel(self, name: str | ChannelKey) -> None:
        """Drop one channel after its definition is deleted, including its tile."""
        key = name.storage_key if isinstance(name, ChannelKey) else name
        if key not in self._available_names:
            return
        if self._built and key in self._items and self._items[key].isChecked():
            self.channel_selector.set_channel_checked(key, False)
        if self._built:
            self.channel_selector.remove_channel(key)
        self._available_names.remove(key)
        tile = self._tiles.pop(key, None)
        if tile is not None:
            tile.setParent(None)
        self.layout_model.remove(key)
        self._latest_values.pop(key, None)
        self._source_names.pop(key, None)
        self._last_sparkline_refresh.pop(key, None)
        if self._built:
            self.empty_label.setVisible(not self._tiles)
            self._apply_sparkline_colors()
            self._reflow(force=True)

    def tile_value_text(self, name: str) -> str | None:
        tile = self._tiles.get(name)
        return tile.value_label.text() if tile is not None else None

    def tile_status_text(self, name: str) -> str | None:
        tile = self._tiles.get(name)
        return tile.status_label.text() if tile is not None else None

    def mark_value_unavailable(self, name: str) -> None:
        """Keep the last number but show it is not a current measurement."""
        tile = self._tiles.get(name)
        if tile is not None:
            tile.set_alarm_state(AlarmState.UNKNOWN)

    def set_channel_metadata(self, registry: ChannelMetadataRegistry) -> None:
        self._metadata = registry
        for source_name, checkbox in self._items.items():
            presentation = registry.get(source_name)
            self.channel_selector.set_channel_text(
                source_name,
                presentation.display_name,
                tooltip=f"Source: {source_name}",
            )
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
        if self._tiles:
            self._apply_sparkline_colors()

    def _add_checkbox(self, name: str) -> None:
        if name in self._items:
            return
        presentation = self._metadata.get(name)
        self.channel_selector.add_channel(
            name,
            presentation.display_name,
            tooltip=f"Source: {name}",
        )

    def _selection_changed(self, name: str, selected: bool) -> None:
        if selected:
            if name not in self._tiles:
                tile = ChannelTile(
                    name,
                    self._tile_content,
                    source_name=self._source_names.get(name, ""),
                )
                tile.set_presentation(self._metadata.get(name))
                self._refresh_tile_sparkline(name, tile=tile, force=True)
                value = self._latest_values.get(name)
                if value is not None:
                    tile.set_value(value, record=False)
                tile.set_alarm_state(
                    evaluate_alarm(value, self._metadata.get(name).alarms)
                )
                tile.set_numeric_display_style(self._numeric_display_style)
                self._tiles[name] = tile
                self.layout_model.add(name)
                tile.show()
                tile.source_label.setVisible(self._show_source_labels)
                self._apply_sparkline_colors()
        else:
            tile = self._tiles.pop(name, None)
            if tile is not None:
                tile.setParent(None)
            self._last_sparkline_refresh.pop(name, None)
            self.layout_model.remove(name)
        self.empty_label.setVisible(not self._tiles)
        self._reflow(force=True)

    def _load_replay_samples(
        self,
        samples: tuple[ReplaySample, ...],
        *,
        prefix: str = "",
    ) -> None:
        for sample in samples:
            pairs = tuple(
                (f"{prefix}{name}", value)
                for name, value in sample.values.items()
                if value is not None
            )
            if not pairs:
                continue
            self._trend.add_update_at(
                ChannelUpdate(
                    tuple(name for name, _value in pairs),
                    tuple(value for _name, value in pairs),
                    False,
                ),
                sample.elapsed_s,
            )

    def _refresh_tile_sparkline(
        self,
        name: str,
        *,
        tile: ChannelTile | None = None,
        force: bool = False,
    ) -> None:
        target = tile if tile is not None else self._tiles.get(name)
        if target is None:
            return
        latest = self._trend.latest_elapsed(name)
        if latest is None:
            target.set_sparkline_samples(())
            return
        previous = self._last_sparkline_refresh.get(name)
        if (
            not force
            and self._trend.sample_count(name) > SPARKLINE_MAX_SAMPLES
            and previous is not None
            and latest - previous < DASHBOARD_SPARKLINE_REFRESH_SECONDS
        ):
            return
        timestamps, values = self._trend.points(name)
        target.set_sparkline_samples(
            visible_trend_values(
                timestamps,
                values,
                self._trend_window_seconds,
            )
        )
        self._last_sparkline_refresh[name] = latest

    def _refresh_all_sparklines(self) -> None:
        for name in self._tiles:
            self._refresh_tile_sparkline(name, force=True)

    def _effective_tile_size(self, width: int) -> int:
        if self._custom_tile_size is not None:
            return self._custom_tile_size
        return (
            self._PREFERRED_TILE_SIZE
            if width >= self._PREFERRED_TILE_SIZE
            else self._MINIMUM_TILE_SIZE
        )

    def _reflow(self, force: bool = False) -> None:
        width = max(1, self.tile_scroll.viewport().width())
        tile_size = self._effective_tile_size(width)
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

    def move_tile(self, source_name: str | ChannelKey, destination: GridPosition) -> None:
        """Snap one source-keyed tile into a cell, swapping any occupant."""
        key = source_name.storage_key if isinstance(source_name, ChannelKey) else source_name
        self.layout_model.move(key, destination)
        self._render_grid()

    def tile_position(self, source_name: str | ChannelKey) -> GridPosition | None:
        key = source_name.storage_key if isinstance(source_name, ChannelKey) else source_name
        return self.layout_model.position(key)

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
