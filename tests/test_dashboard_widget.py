import json
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication

from serialscope.parsing import ChannelUpdate
from serialscope.replay import load_replay_session
from serialscope.ui.channel_tile import ChannelTile, format_dashboard_value
from serialscope.ui.style import DARK_STYLE, LIGHT_STYLE
from serialscope.ui.dashboard_widget import DashboardWidget
from serialscope.data import AlarmLimits, ChannelKey, ChannelMetadataRegistry, GridPosition


def test_dashboard_starts_empty_and_adds_channels_once_unselected() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()

    widget.update_channels(ChannelUpdate(("TC1", "RPM"), (101.42, 1500)))
    widget.update_channels(ChannelUpdate(("TC1", "RPM"), (102.0, 1510)))

    assert widget.channel_names == ("TC1", "RPM")
    assert widget.selected_channels == ()
    assert widget.tile_count == 0
    assert widget.empty_label.isVisibleTo(widget)
    widget.close()
    application.processEvents()


def test_selection_creates_updates_and_removes_one_tile() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    widget.update_channels(ChannelUpdate(("TC1", "RPM"), (101.42, 1500)))

    widget.set_channel_selected("TC1", True)
    widget.set_channel_selected("RPM", True)
    assert widget.selected_channels == ("TC1", "RPM")
    assert widget.tile_count == 2
    assert widget.tile_value_text("TC1") == "101.42"
    assert widget.tile_value_text("RPM") == "1500"
    widget.show()
    application.processEvents()
    assert widget._tiles["TC1"].parentWidget() is widget._tile_content
    assert widget._tiles["TC1"].isVisibleTo(widget._tile_content)
    assert widget._tiles["RPM"].isVisibleTo(widget._tile_content)

    widget.update_channels(ChannelUpdate(("TC1", "RPM"), (102.25, 1512)))
    assert widget.tile_value_text("TC1") == "102.25"
    assert widget.tile_value_text("RPM") == "1512"
    assert widget.tile_count == 2

    widget.set_channel_selected("TC1", False)
    assert widget.selected_channels == ("RPM",)
    assert widget.tile_count == 1
    widget.close()
    application.processEvents()


@pytest.mark.parametrize(
    ("value", "text"),
    [(101.420000, "101.42"), (2.51, "2.51"), (1500, "1500"), (0.0, "0")],
)
def test_dashboard_value_formatting(value: int | float, text: str) -> None:
    assert format_dashboard_value(value) == text


def test_partial_updates_preserve_existing_values_and_selection() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    widget.update_channels(ChannelUpdate(("A", "B"), (1, 2), False))
    widget.set_channel_selected("A", True)
    widget.set_channel_selected("B", True)

    widget.update_channels(ChannelUpdate(("A",), (3,), False))

    assert widget.tile_value_text("A") == "3"
    assert widget.tile_value_text("B") == "2"
    assert widget.selected_channels == ("A", "B")
    widget.close()
    application.processEvents()


def test_many_channels_use_vertical_scroll_without_horizontal_scroll() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    names = tuple(f"Channel {index}" for index in range(50))
    widget.update_channels(ChannelUpdate(names, tuple(range(50))))
    for name in names:
        widget.set_channel_selected(name, True)

    widget.resize(500, 400)
    widget.show()
    application.processEvents()

    assert widget.tile_count == 50
    assert widget.tile_scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert widget.tile_scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert widget._column_count >= 1
    widget.close()
    application.processEvents()


def test_window_resize_preserves_logical_positions_and_square_tiles() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    names = tuple(f"C{index}" for index in range(8))
    widget.update_channels(ChannelUpdate(names, tuple(range(8))))
    for name in names:
        widget.set_channel_selected(name, True)
    widget.move_tile("C3", GridPosition(2, 3))
    positions_before = widget.layout_model.snapshot()
    widget.show()

    widget.resize(980, 500)
    application.processEvents()
    assert all(tile.width() == tile.height() for tile in widget._tiles.values())
    widget.resize(430, 500)
    application.processEvents()

    assert widget.layout_model.snapshot() == positions_before
    assert all(tile.width() == tile.height() for tile in widget._tiles.values())
    assert widget.tile_count == 8
    widget.close()
    application.processEvents()

def test_replay_exposes_latest_values_and_reset_clears_them(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    directory = tmp_path / "session"
    directory.mkdir()
    (directory / "session.json").write_text(
        json.dumps({"structured_data_delimiter": ","}), encoding="utf-8"
    )
    (directory / "data.csv").write_text(
        "elapsed_s,A,B\n0,1,\n1.5,2,9\n", encoding="utf-8"
    )
    widget = DashboardWidget()

    widget.load_replay(load_replay_session(directory))
    widget.set_channel_selected("A", True)
    widget.set_channel_selected("B", True)

    assert widget.tile_value_text("A") == "2"
    assert widget.tile_value_text("B") == "9"
    widget.reset()
    assert widget.channel_names == ()
    assert widget.tile_count == 0
    widget.close()
    application.processEvents()


def test_dashboard_alias_and_unit_change_preserve_source_selection() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    widget.update_channels(ChannelUpdate(("TC1",), (101.42,)))
    widget.set_channel_selected("TC1", True)
    registry = ChannelMetadataRegistry()
    registry.set("TC1", "Reactor Temperature", "°C")

    widget.set_channel_metadata(registry)

    tile = widget._tiles["TC1"]
    assert widget.selected_channels == ("TC1",)
    assert widget.tile_count == 1
    assert tile.name_label.text() == "Reactor Temperature"
    assert tile.name_label.toolTip() == "Source: TC1"
    assert tile.unit_label.text() == "°C"
    assert tile.value_label.text() == "101.42"
    widget.close()
    application.processEvents()


def test_dashboard_shows_text_and_semantic_alarm_state() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    registry = ChannelMetadataRegistry()
    registry.set("TC1", "Temperature", "°C", AlarmLimits(high=110, high_high=120))
    widget.set_channel_metadata(registry)
    widget.update_channels(ChannelUpdate(("TC1",), (118.4,)))
    widget.set_channel_selected("TC1", True)
    tile = widget._tiles["TC1"]

    assert tile.status_label.text() == "HIGH"
    assert tile.property("alarmState") == "warning"
    widget.update_channels(ChannelUpdate(("TC1",), (125.2,)))
    assert tile.status_label.text() == "HIGH-HIGH"
    assert tile.property("alarmState") == "alarm"
    widget.update_channels(ChannelUpdate(("TC1",), (108,)))
    assert tile.status_label.text() == "NORMAL"
    assert tile.property("alarmState") == "normal"
    widget.close()
    application.processEvents()


def test_move_and_swap_preserve_value_metadata_alarm_and_updates() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    registry = ChannelMetadataRegistry()
    registry.set("A", "Temperature", "°C", AlarmLimits(high=10))
    registry.set("B", "Pressure", "bar")
    widget.set_channel_metadata(registry)
    widget.update_channels(ChannelUpdate(("A", "B"), (12, 2.5)))
    widget.set_channel_selected("A", True)
    widget.set_channel_selected("B", True)
    a_before = widget.tile_position("A")
    b_before = widget.tile_position("B")

    widget.move_tile("A", b_before)

    assert widget.tile_position("A") == b_before
    assert widget.tile_position("B") == a_before
    assert widget._tiles["A"].name_label.text() == "Temperature"
    assert widget._tiles["A"].unit_label.text() == "°C"
    assert widget._tiles["A"].status_label.text() == "HIGH"
    widget.update_channels(ChannelUpdate(("A",), (8,), False))
    assert widget.tile_value_text("A") == "8"
    assert widget._tiles["A"].status_label.text() == "NORMAL"
    widget.close()
    application.processEvents()


def test_deselect_leaves_other_explicit_positions_unchanged() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    widget.update_channels(ChannelUpdate(("A", "B", "C"), (1, 2, 3)))
    for name in ("A", "B", "C"):
        widget.set_channel_selected(name, True)
    widget.move_tile("C", GridPosition(3, 2))

    widget.set_channel_selected("A", False)

    assert widget.tile_position("C") == GridPosition(3, 2)
    assert widget.tile_position("B") == GridPosition(0, 1)
    widget.close()
    application.processEvents()


def test_drag_uses_platform_threshold_and_preserves_pickup_point() -> None:
    application = QApplication.instance() or QApplication([])
    tile = ChannelTile("A")
    pickup = QPoint(121, 17)
    tile._drag_start = pickup
    threshold = QApplication.startDragDistance()

    assert not tile.drag_threshold_reached(pickup + QPoint(threshold - 1, 0))
    assert tile.drag_threshold_reached(pickup + QPoint(threshold, 0))
    assert tile._drag_start == pickup
    tile.close()
    application.processEvents()


def test_drop_candidate_preview_does_not_commit_or_recreate_tiles() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    widget.update_channels(ChannelUpdate(("A", "B"), (1, 2)))
    widget.set_channel_selected("A", True)
    widget.set_channel_selected("B", True)
    positions = widget.layout_model.snapshot()
    tile_ids = {name: id(tile) for name, tile in widget._tiles.items()}

    candidate = widget._position_from_content_point(
        QPoint(widget._tile_size + widget._GRID_SPACING + 2, 2)
    )
    widget._set_drop_candidate(candidate)
    widget.update_channels(ChannelUpdate(("A",), (3,), False))

    assert candidate == GridPosition(0, 1)
    assert widget._drop_candidate == candidate
    assert widget.layout_model.snapshot() == positions
    assert {name: id(tile) for name, tile in widget._tiles.items()} == tile_ids
    assert widget.tile_value_text("A") == "3"
    assert widget._drop_indicator.width() == widget._drop_indicator.height()
    widget._clear_drop_state()
    assert widget._drop_candidate is None
    assert widget.layout_model.snapshot() == positions
    widget.close()
    application.processEvents()


def test_target_mapping_and_geometry_use_the_same_canvas_pitch() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    widget._column_count = 6
    pitch = widget._tile_size + widget._GRID_SPACING

    assert widget._position_from_content_point(QPoint(0, 0)) == GridPosition(0, 0)
    assert widget._position_from_content_point(
        QPoint(4 * pitch + 5, 2)
    ) == GridPosition(0, 4)
    assert widget._position_from_content_point(
        QPoint(2, 3 * pitch + 5)
    ) == GridPosition(3, 0)
    target = GridPosition(3, 4)
    assert widget.cell_rect(target) == QRect(
        4 * pitch, 3 * pitch, widget._tile_size, widget._tile_size
    )
    widget._set_drop_candidate(target)
    assert widget.cell_rect(target) == widget._drop_indicator.geometry()
    widget.close()
    application.processEvents()


def test_wide_viewport_exposes_far_right_empty_columns() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    widget.resize(1450, 500)
    widget.show()
    application.processEvents()

    assert widget._column_count > 4
    far_right = GridPosition(0, widget._column_count - 1)
    assert widget._position_from_content_point(widget.cell_rect(far_right).center()) == far_right
    widget.close()
    application.processEvents()


def test_resize_changes_available_cells_without_moving_existing_positions() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    widget.resize(1400, 500)
    widget.show()
    widget.update_channels(ChannelUpdate(("A",), (1,)))
    widget.set_channel_selected("A", True)
    application.processEvents()
    wide_columns = widget._column_count
    far_right = GridPosition(0, wide_columns - 1)
    widget.move_tile("A", far_right)

    widget.resize(500, 500)
    application.processEvents()
    assert widget._column_count < wide_columns
    assert widget.tile_position("A") == far_right
    assert widget.tile_scroll.horizontalScrollBar().maximum() > 0
    widget.resize(1500, 500)
    application.processEvents()
    assert widget.tile_position("A") == far_right
    widget.close()
    application.processEvents()


def test_scrolled_target_mapping_uses_qt_content_transform() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    names = tuple(f"C{index}" for index in range(20))
    widget.update_channels(ChannelUpdate(names, tuple(range(20))))
    for name in names:
        widget.set_channel_selected(name, True)
    widget.resize(760, 360)
    widget.show()
    application.processEvents()
    widget.tile_scroll.verticalScrollBar().setValue(240)
    application.processEvents()

    content_point = QPoint(5, 3 * (widget._tile_size + widget._GRID_SPACING) + 5)
    dashboard_point = widget.mapFrom(widget._tile_content, content_point)
    assert widget._calculate_target_cell(dashboard_point) == GridPosition(3, 0)
    widget.close()
    application.processEvents()


def test_preview_cell_is_the_only_cell_committed_for_empty_move_and_swap() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    widget.update_channels(ChannelUpdate(("A", "B"), (1, 2)))
    widget.set_channel_selected("A", True)
    widget.set_channel_selected("B", True)

    empty_target = GridPosition(2, 3)
    widget._set_drop_candidate(empty_target)
    assert widget._commit_drop("A")
    assert widget.tile_position("A") == empty_target

    source_before = widget.tile_position("A")
    occupied_target = widget.tile_position("B")
    widget._set_drop_candidate(occupied_target)
    assert widget._commit_drop("A")
    assert widget.tile_position("A") == occupied_target
    assert widget.tile_position("B") == source_before
    widget.close()
    application.processEvents()


def test_drop_without_stored_preview_is_cancelled_without_recalculation() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    widget.update_channels(ChannelUpdate(("A",), (1,)))
    widget.set_channel_selected("A", True)
    original = widget.tile_position("A")

    assert not widget._commit_drop("A")
    assert widget.tile_position("A") == original
    widget.close()
    application.processEvents()


@pytest.mark.parametrize("width", [520, 1100])
def test_preview_and_committed_tile_share_qgridlayout_geometry(width: int) -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    names = tuple(f"C{index}" for index in range(9))
    widget.update_channels(ChannelUpdate(names, tuple(range(9))))
    for name in names:
        widget.set_channel_selected(name, True)
    widget.resize(width, 500)
    widget.show()
    application.processEvents()

    target = GridPosition(2, 0)
    widget._set_drop_candidate(target)
    application.processEvents()
    preview_geometry = widget._drop_indicator.geometry()
    assert preview_geometry == widget._cell_geometry(target)

    assert widget._commit_drop("C0")
    widget._clear_drop_state()
    application.processEvents()
    assert widget.tile_position("C0") == target
    assert widget._tiles["C0"].geometry() == preview_geometry
    assert widget._tiles["C0"].width() == widget._tiles["C0"].height()
    widget.close()
    application.processEvents()


def test_empty_future_row_is_created_by_indicator_and_matches_committed_tile() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    widget.update_channels(ChannelUpdate(("A",), (1,)))
    widget.set_channel_selected("A", True)
    widget.show()
    application.processEvents()

    target = GridPosition(4, 3)
    widget._set_drop_candidate(target)
    application.processEvents()
    preview_geometry = widget._cell_geometry(target)
    assert preview_geometry == widget._drop_indicator.geometry()

    assert widget._commit_drop("A")
    widget._clear_drop_state()
    application.processEvents()
    assert widget.tile_position("A") == target
    assert widget._tiles["A"].geometry() == preview_geometry
    widget.close()
    application.processEvents()


def test_dashboard_label_typography_is_centralized_for_both_themes() -> None:
    for stylesheet in (DARK_STYLE, LIGHT_STYLE):
        rule = stylesheet.split("QLabel#dashboardTileName {", 1)[1].split("}", 1)[0]
        assert "font-size: 11pt" in rule
        assert "font-weight: 500" in rule


def test_long_dashboard_alias_is_elided_without_changing_square_tile() -> None:
    application = QApplication.instance() or QApplication([])
    tile = ChannelTile("source")
    alias = "Reactor vessel north wall temperature sensor with a very long alias"
    registry = ChannelMetadataRegistry()
    registry.set("source", alias, "°C")
    tile.setFixedSize(150, 150)
    tile.set_presentation(registry.get("source"))
    tile.show()
    application.processEvents()

    assert tile.name_label.full_text() == alias
    assert tile.name_label.text().endswith("…")
    assert tile.width() == tile.height() == 150
    assert tile.value_label.isVisibleTo(tile)
    tile.close()
    application.processEvents()


def test_identical_channel_names_from_two_sources_have_independent_tiles() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    widget.update_source("pico", "Pi Pico", ChannelUpdate(("TC1",), (10,)))
    widget.update_source("arduino", "Arduino Uno", ChannelUpdate(("TC1",), (20,)))
    pico = ChannelKey("pico", "TC1")
    arduino = ChannelKey("arduino", "TC1")
    widget.set_channel_selected(pico, True)
    widget.set_channel_selected(arduino, True)
    arduino_position = widget.tile_position(arduino)

    widget.move_tile(pico, GridPosition(3, 4))

    assert widget.tile_count == 2
    assert widget.tile_position(pico) == GridPosition(3, 4)
    assert widget.tile_position(arduino) == arduino_position
    assert widget._tiles[pico.storage_key].source_label.text() == "Pi Pico"
    assert widget._tiles[arduino.storage_key].source_label.text() == "Arduino Uno"
    assert widget.tile_value_text(pico.storage_key) == "10"
    assert widget.tile_value_text(arduino.storage_key) == "20"
    widget.close()
    application.processEvents()
