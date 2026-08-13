import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from serialscope.parsing import ChannelUpdate
from serialscope.replay import load_replay_session
from serialscope.ui.channel_tile import format_dashboard_value
from serialscope.ui.dashboard_widget import DashboardWidget


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
    assert widget.tile_scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert widget.tile_scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert widget._column_count >= 1
    widget.close()
    application.processEvents()


def test_grid_reflows_only_when_available_column_count_changes() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DashboardWidget()
    names = tuple(f"C{index}" for index in range(8))
    widget.update_channels(ChannelUpdate(names, tuple(range(8))))
    for name in names:
        widget.set_channel_selected(name, True)
    widget.show()

    widget.resize(980, 500)
    application.processEvents()
    wide_columns = widget._column_count
    widget.resize(430, 500)
    application.processEvents()
    narrow_columns = widget._column_count

    assert wide_columns >= 4
    assert 1 <= narrow_columns <= 2
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
