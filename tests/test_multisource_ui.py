from unittest.mock import Mock

from PySide6.QtWidgets import QApplication

from serialscope.parsing import ChannelUpdate
from serialscope.serial import SerialConnection, SerialPortInfo
from serialscope.ui.main_window import MainWindow


def test_single_source_is_present_once_and_advanced_selectors_are_hidden() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])

    assert len(window._source_manager.sources) == 1
    assert window.connection_bar.source_combo.count() == 1
    assert window.terminal.source_combo.count() == 1
    assert window.graphs_widget.source_combo.count() == 1
    assert window.connection_bar.source_combo.itemText(0) == "Device 1"
    assert window.connection_bar.source_combo.isHidden()
    assert window.terminal.source_combo.isHidden()
    assert window.graphs_widget.source_combo.isHidden()
    assert window.graphs_widget.source_label.isHidden()
    assert window.data_widget.table.isColumnHidden(4)
    window.close()
    application.processEvents()


def test_add_and_remove_device_progressively_reveals_source_controls() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])

    window.connection_bar.add_source_button.click()
    names = [source.display_name for source in window._source_manager.sources]
    assert names == ["Device 1", "Device 2"]
    assert window.connection_bar.source_combo.count() == 2
    assert window.terminal.source_combo.count() == 2
    assert window.graphs_widget.source_combo.count() == 2
    assert not window.connection_bar.source_combo.isHidden()
    assert not window.terminal.source_combo.isHidden()
    assert not window.graphs_widget.source_combo.isHidden()
    assert not window.data_widget.table.isColumnHidden(4)

    window.connection_bar.remove_source_button.click()
    assert [source.display_name for source in window._source_manager.sources] == ["Device 1"]
    assert window.connection_bar.source_combo.count() == 1
    assert window.terminal.source_combo.count() == 1
    assert window.graphs_widget.source_combo.count() == 1
    assert window.connection_bar.source_combo.isHidden()
    assert window.terminal.source_combo.isHidden()
    assert window.graphs_widget.source_combo.isHidden()
    assert window.data_widget.table.isColumnHidden(4)
    window.close()
    application.processEvents()


def test_port_refresh_and_reconnect_do_not_create_sources() -> None:
    application = QApplication.instance() or QApplication([])
    serial_ports = [Mock(is_open=True, port="COM4"), Mock(is_open=True, port="COM4")]
    connection = SerialConnection(serial_factory=Mock(side_effect=serial_ports))

    class Reader:
        def __init__(self, _connection):
            self.bytes_received = Mock()
            self.bytes_received.connect = Mock()
            self.failed = Mock()
            self.failed.connect = Mock()
        def start(self): pass
        def stop(self): pass

    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=Reader,
    )
    window.refresh_ports()
    window.refresh_ports()
    assert len(window._source_manager.sources) == 1
    window.connection_bar.connect_button.click()
    window.connection_bar.connect_button.click()
    window.connection_bar.connect_button.click()
    assert len(window._source_manager.sources) == 1
    assert window.connection_bar.source_combo.count() == 1
    window.close()
    application.processEvents()


def test_dashboard_source_labels_follow_configured_source_count() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])
    window.dashboard_widget.update_source(
        "default", "Device 1", ChannelUpdate(("A",), (1,))
    )
    window.dashboard_widget.set_channel_selected("default\x1fA", True)
    assert window.dashboard_widget._tiles["default\x1fA"].source_label.isHidden()

    window.connection_bar.add_source_button.click()
    assert not window.dashboard_widget._tiles["default\x1fA"].source_label.isHidden()
    window.connection_bar.remove_source_button.click()
    assert window.dashboard_widget._tiles["default\x1fA"].source_label.isHidden()
    window.close()
    application.processEvents()
