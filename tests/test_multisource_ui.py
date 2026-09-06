from unittest.mock import Mock
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton

from serialscope.parsing import ChannelUpdate
from serialscope.serial import SerialConnection, SerialPortInfo, SerialSourceManager
from serialscope.settings import ApplicationSettings
from serialscope.ui.main_window import MainWindow


def test_single_source_is_present_once_and_add_device_is_absent() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])

    assert len(window._source_manager.sources) == 1
    assert window.terminal.source_combo.count() == 1
    assert window.graphs_widget.source_combo.count() == 1
    assert window.terminal.source_combo.isHidden()
    assert window.graphs_widget.source_combo.isHidden()
    assert window.graphs_widget.source_label.isHidden()
    assert window.data_widget.table.isColumnHidden(4)
    assert window.connection_bar.findChild(QPushButton, "addSerialSourceButton") is None
    assert window.connection_bar.findChild(QPushButton, "removeSerialSourceButton") is None
    assert not hasattr(window.connection_bar, "add_source_button")
    assert not hasattr(window.connection_bar, "source_combo")
    window.close()
    application.processEvents()


def test_connect_disconnect_uses_the_single_source() -> None:
    application = QApplication.instance() or QApplication([])
    serial_ports = [Mock(is_open=True, port="COM4"), Mock(is_open=True, port="COM4")]
    connection = SerialConnection(serial_factory=Mock(side_effect=serial_ports))

    class Reader:
        def __init__(self, _connection):
            self.bytes_received = Mock()
            self.bytes_received.connect = Mock()
            self.failed = Mock()
            self.failed.connect = Mock()

        def start(self):
            pass

        def stop(self):
            pass

    window = MainWindow(
        port_scanner=lambda: [SerialPortInfo("COM4")],
        serial_connection=connection,
        reader_factory=Reader,
    )
    window.refresh_ports()
    assert len(window._source_manager.sources) == 1
    window.connection_bar.connect_button.click()
    assert window._source_manager.sources[0].is_connected
    assert window.connection_bar.status_label.text() == "CONNECTED"
    window.connection_bar.connect_button.click()
    assert not window._source_manager.sources[0].is_connected
    assert len(window._source_manager.sources) == 1
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
    window.close()
    application.processEvents()


def test_dashboard_source_labels_stay_hidden_for_the_single_device() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])
    window.dashboard_widget.update_source(
        "default", "Device 1", ChannelUpdate(("A",), (1,))
    )
    window.dashboard_widget.set_channel_selected("default\x1fA", True)
    assert window.dashboard_widget._tiles["default\x1fA"].source_label.isHidden()
    window.close()
    application.processEvents()


def test_legacy_multidevice_settings_do_not_crash_startup(tmp_path) -> None:
    application = QApplication.instance() or QApplication([])
    backend = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    backend.setValue("devices/count", 2)
    backend.setValue("devices/1/port", "/dev/ttyUSB0")
    backend.setValue("devices/2/port", "/dev/ttyUSB1")
    backend.setValue("sources/0/name", "Device 1")
    backend.setValue("sources/1/name", "Device 2")
    backend.sync()
    window = MainWindow(
        port_scanner=lambda: [],
        application_settings=ApplicationSettings(backend),
    )
    assert len(window._source_manager.sources) == 1
    assert window.connection_bar.findChild(QPushButton, "addSerialSourceButton") is None
    window.close()
    application.processEvents()


def test_injected_extra_sources_do_not_expose_add_device_controls() -> None:
    application = QApplication.instance() or QApplication([])
    manager = SerialSourceManager()
    manager.add_source("Reactor Pico", source_id="reactor")
    manager.add_source("Pressure Arduino", source_id="pressure")
    window = MainWindow(port_scanner=lambda: [], source_manager=manager)

    assert window.connection_bar.findChild(QPushButton, "addSerialSourceButton") is None
    assert not hasattr(window, "_add_serial_source")
    window.close()
    application.processEvents()
