import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from serialscope.parsing import ChannelUpdate
from serialscope.ui.data_widget import DataWidget
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
