import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from serialscope.data import ChannelHistory
from serialscope.logging import StructuredCsvLogger
from serialscope.modbus import ModbusRegister, ModbusRtuConfiguration
from serialscope.parsing import ChannelUpdate
from serialscope.serial import SerialSourceManager
from serialscope.ui.dashboard_widget import DashboardWidget
from serialscope.ui.data_widget import DataWidget
from serialscope.ui.main_window import MainWindow
from tests.test_modbus_sources import ImmediatePoller, FakeModbusTransport


def test_modbus_values_feed_data_graphs_dashboard_and_logger(tmp_path) -> None:
    QApplication.instance() or QApplication([])
    update = ChannelUpdate(("Motor Speed", "Current"), (1450, 12.3), False)
    data = DataWidget()
    dashboard = DashboardWidget(lazy=False)
    history = ChannelHistory()
    logger = StructuredCsvLogger()
    logger.start(tmp_path / "data.csv")
    data.update_channels(update)
    dashboard.update_channels(update)
    history.add_update(update)
    logger.write(update)
    logger.stop()
    assert data.value_text("Motor Speed") == "1450"
    assert "Motor Speed" in dashboard.channel_selector.toggles
    times, values = history.points("Current")
    assert values[-1] == 12.3
    contents = (tmp_path / "data.csv").read_text("utf-8")
    assert "Motor Speed" in contents
    assert "12.3" in contents


def test_main_window_consumes_modbus_structured_updates() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(
        port_scanner=lambda: [],
        source_manager=SerialSourceManager(
            poller_factory=ImmediatePoller,
            modbus_transport_factory=lambda port, settings: FakeModbusTransport(
                holding={0: 88}
            ),
        ),
    )
    source = window._selected_source
    window._source_manager.apply_modbus_configuration(
        source.source_id,
        ModbusRtuConfiguration(
            registers=(ModbusRegister(name="Temp", unit="°C"),)
        ),
    )
    window._source_manager.connect(source.source_id, "/dev/ttyUSB0", 9600)
    application.processEvents()
    assert window.data_widget.value_text("Temp") == "11"
    assert window._source_metadata[source.source_id].get("Temp").unit == "°C"
    window._source_manager.disconnect(source.source_id)
    window.close()
    application.processEvents()
