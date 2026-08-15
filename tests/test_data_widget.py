import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QLabel

from serialscope.parsing import ChannelUpdate
from serialscope.ui.data_widget import DataWidget
from serialscope.ui.theme import apply_application_theme
from serialscope.data import AlarmLimits, ChannelMetadataRegistry


def test_data_table_updates_existing_rows_without_duplicates() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DataWidget()

    widget.update_channels(ChannelUpdate(("TC1", "TC2"), (100.42, 98.71)))
    widget.update_channels(ChannelUpdate(("TC1", "TC2"), (101.2, 99.1)))

    assert widget.channel_names == ("TC1", "TC2")
    assert widget.table.rowCount() == 2
    assert widget.value_text("TC1") == "101.2"
    assert widget.value_text("TC2") == "99.1"
    application.processEvents()


def test_data_table_adds_channels_and_retains_omitted_values() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DataWidget()

    widget.update_channels(
        ChannelUpdate(("TEMP", "RPM"), (25.4, 1487), replace_channels=False)
    )
    widget.update_channels(
        ChannelUpdate(("TEMP", "FLOW"), (25.7, 0.42), replace_channels=False)
    )

    assert widget.channel_names == ("TEMP", "RPM", "FLOW")
    assert widget.value_text("TEMP") == "25.7"
    assert widget.value_text("RPM") == "1487"
    assert widget.value_text("FLOW") == "0.42"
    application.processEvents()


def test_data_table_reset_restores_empty_state() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DataWidget()
    widget.update_channels(ChannelUpdate(("A", "B"), (1, 2)))

    widget.reset()

    assert widget.channel_names == ()
    assert widget.table.isHidden()
    assert not widget.empty_label.isHidden()
    application.processEvents()


def test_data_table_displays_alias_unit_and_preserves_source_key() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DataWidget()
    widget.update_channels(ChannelUpdate(("TC1",), (101.42,)))
    registry = ChannelMetadataRegistry()
    registry.set("TC1", "Reactor Temperature", "°C")

    widget.set_channel_metadata(registry)

    assert widget.channel_names == ("TC1",)
    assert widget.table.item(0, 0).text() == "Reactor Temperature"
    assert widget.table.item(0, 0).toolTip() == "Source: TC1"
    assert widget.table.item(0, 2).text() == "°C"
    assert widget.value_text("TC1") == "101.42"
    widget.close()
    application.processEvents()


def test_data_status_updates_from_latest_measured_value() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DataWidget()
    registry = ChannelMetadataRegistry()
    registry.set("TC1", "Temperature", "°C", AlarmLimits(high=110, high_high=120))
    widget.set_channel_metadata(registry)

    widget.update_channels(ChannelUpdate(("TC1",), (99,)))
    assert widget.status_text("TC1") == "NORMAL"
    widget.update_channels(ChannelUpdate(("TC1",), (112,)))
    assert widget.status_text("TC1") == "HIGH"
    widget.update_channels(ChannelUpdate(("TC1",), (125,)))
    assert widget.status_text("TC1") == "HIGH-HIGH"
    widget.update_channels(ChannelUpdate(("TC1",), (108,)))
    assert widget.status_text("TC1") == "NORMAL"
    assert widget.channel_names == ("TC1",)
    widget.close()
    application.processEvents()


def test_changing_unit_does_not_change_numeric_measurement() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DataWidget()
    widget.update_channels(ChannelUpdate(("P",), (2.51,)))
    registry = ChannelMetadataRegistry()
    registry.set("P", "Pressure", "bar")
    widget.set_channel_metadata(registry)
    registry.set("P", "Pressure", "kPa")
    widget.set_channel_metadata(registry)

    assert widget.value_text("P") == "2.51"
    assert widget.table.item(0, 2).text() == "kPa"
    widget.close()
    application.processEvents()


def test_data_table_uses_live_engineering_presentation() -> None:
    application = QApplication.instance() or QApplication([])
    widget = DataWidget()
    registry = ChannelMetadataRegistry()
    registry.set("TC1", "Temperature", "°C", AlarmLimits(high=110, high_high=120))
    widget.set_channel_metadata(registry)
    widget.update_channels(ChannelUpdate(("TC1", "RPM"), (125.0, 1487)))
    widget.resize(720, 360)
    widget.show()
    application.processEvents()

    value_item = widget.table.item(0, 1)
    assert value_item.textAlignment() & Qt.AlignmentFlag.AlignRight
    assert widget.table.rowHeight(0) >= 36
    assert widget.table.columnWidth(3) >= widget.table.fontMetrics().horizontalAdvance(
        "HIGH-HIGH"
    ) + 40
    assert widget.table.width() >= 680
    badge = widget.table.cellWidget(0, 3).findChild(QLabel, "channelDataStatusBadge")
    assert badge is not None
    assert badge.text() == "HIGH-HIGH"
    assert badge.property("alarmState") == "alarm"
    assert badge.property("alarmKind") == "HIGH-HIGH"
    assert badge.minimumHeight() >= 22
    normal = widget.table.cellWidget(1, 3).findChild(QLabel, "channelDataStatusBadge")
    assert normal.text() == "NORMAL"
    assert normal.property("alarmState") == "normal"
    assert normal.minimumWidth() >= normal.fontMetrics().horizontalAdvance("HIGH-HIGH")
    assert normal.alignment() & Qt.AlignmentFlag.AlignHCenter
    widget.resize(420, 280)
    application.processEvents()
    assert widget.table.width() <= widget.width()
    assert widget.table.columnWidth(3) >= widget.table.fontMetrics().horizontalAdvance(
        "HIGH-HIGH"
    )
    assert widget.table.horizontalHeader().sectionResizeMode(0).name == "Stretch"
    assert widget.table.horizontalHeader().sectionResizeMode(1).name == "Fixed"
    assert widget.table.horizontalHeader().sectionResizeMode(2).name == "Fixed"
    assert widget.table.horizontalHeader().sectionResizeMode(3).name == "Fixed"
    widget.close()
    application.processEvents()


def test_data_table_status_badges_stay_inside_viewport_at_several_widths() -> None:
    application = QApplication.instance() or QApplication([])
    apply_application_theme(application, "dark")
    widget = DataWidget()
    registry = ChannelMetadataRegistry()
    registry.set("TC1", "Temperature", "°C", AlarmLimits(high=110, high_high=120))
    widget.set_channel_metadata(registry)
    widget.update_channels(ChannelUpdate(("TC1", "RPM"), (125.0, 1487)))
    widget.show()

    for width in (520, 720, 960, 1100):
        widget.resize(width, 360)
        application.processEvents()
        viewport = widget.table.viewport()
        assert widget.table.columnWidth(1) == 120
        assert widget.table.columnWidth(2) == 88
        assert widget.table.columnWidth(3) >= widget._status_min_width
        assert widget.table.horizontalScrollBar().maximum() == 0
        for row in range(widget.table.rowCount()):
            cell = widget.table.cellWidget(row, 3)
            badge = cell.findChild(QLabel, "channelDataStatusBadge")
            assert badge is not None
            top_left = badge.mapTo(viewport, QPoint(0, 0))
            right = top_left.x() + badge.width()
            assert top_left.x() >= 0
            assert right <= viewport.width()
            in_cell = badge.mapTo(cell, QPoint(0, 0))
            assert in_cell.x() >= 0
            assert in_cell.x() + badge.width() <= cell.width()
    widget.close()
    application.processEvents()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_data_table_status_badges_fit_vertically_in_every_row(theme: str) -> None:
    application = QApplication.instance() or QApplication([])
    apply_application_theme(application, theme)
    widget = DataWidget()
    names = tuple(f"CH{index}" for index in range(5))
    widget.update_channels(ChannelUpdate(names, (1, 2, 3, 4, 5)))
    widget.resize(800, 420)
    widget.show()
    application.processEvents()

    last = widget.table.rowCount() - 1
    for row in (0, last // 2, last):
        cell = widget.table.cellWidget(row, 3)
        badge = cell.findChild(QLabel, "channelDataStatusBadge")
        assert badge is not None
        in_cell = badge.mapTo(cell, QPoint(0, 0))
        assert in_cell.y() >= 1
        assert in_cell.y() + badge.height() <= cell.height()
        assert widget.table.rowHeight(row) >= badge.height() + 8
        assert widget.table.rowHeight(row) >= widget.table.verticalHeader().defaultSectionSize()
    widget.close()
    application.processEvents()
