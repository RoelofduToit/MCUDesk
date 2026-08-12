import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from serialscope.parsing import ChannelUpdate
from serialscope.ui.data_widget import DataWidget


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
