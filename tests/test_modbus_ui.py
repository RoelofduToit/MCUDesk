import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from serialscope.modbus import (
    FakeModbusTransport,
    ModbusRegister,
    ModbusRtuConfiguration,
)
from serialscope.serial import SerialPortInfo
from serialscope.ui.main_window import MainWindow
from serialscope.ui.modbus_device_dialog import ModbusDeviceDialog
from serialscope.ui.modbus_register_dialog import ModbusRegisterDialog


def test_modbus_dialog_add_edit_remove_and_rejects_invalid_save() -> None:
    QApplication.instance() or QApplication([])
    dialog = ModbusDeviceDialog(ports=(SerialPortInfo(device="/dev/ttyUSB0"),))
    assert dialog.windowTitle() == "Modbus RTU Device"
    assert dialog.register_table.columnCount() == 5
    assert not dialog.register_empty.isHidden()
    register_dialog = ModbusRegisterDialog()
    assert register_dialog.windowTitle() == "Add Register"
    register_dialog.name_input.setText("RPM")
    register_dialog.address_spin.setValue(0)
    dialog._registers.append(register_dialog.register())
    dialog._refresh_register_table()
    assert dialog.register_table.rowCount() == 1
    dialog.register_table.selectRow(0)
    dialog._remove_register()
    assert dialog.register_table.rowCount() == 0
    assert dialog.configuration().enabled_registers == ()
    dialog.close()


def test_test_connection_uses_background_worker_and_occupied_port() -> None:
    application = QApplication.instance() or QApplication([])
    transport = FakeModbusTransport(holding={0: 9})
    dialog = ModbusDeviceDialog(
        ports=(SerialPortInfo(device="/dev/ttyUSB0"),),
        configuration=ModbusRtuConfiguration(registers=(ModbusRegister(name="RPM"),)),
        occupied_ports={"/dev/ttyUSB1": "Arduino"},
        transport_factory=lambda port, settings: transport,
        selected_port="/dev/ttyUSB0",
    )
    dialog._test_connection()
    deadline = 200
    while dialog.status_label.text() == "Testing connection..." and deadline:
        application.processEvents()
        deadline -= 1
    assert "Device responding" in dialog.status_label.text()
    dialog.port_combo.addItem("/dev/ttyUSB1", "/dev/ttyUSB1")
    dialog.port_combo.setCurrentIndex(dialog.port_combo.findData("/dev/ttyUSB1"))
    dialog._test_connection()
    assert "already connected as Arduino" in dialog.status_label.text()
    dialog.close()


def test_main_window_exposes_modbus_menu_without_cluttering_connection_bar() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [])
    window.show()
    application.processEvents()
    assert window.modbus_devices_action.text() == "Modbus Devices..."
    bar = window.connection_bar
    assert not hasattr(bar, "slave_spin")
    assert bar.port_combo.isVisibleTo(window)
    assert bar.baud_combo.isVisibleTo(window)
    assert window.workspace_tabs.count() == 4
    names = [window.workspace_tabs.tabText(index) for index in range(4)]
    assert "Modbus" not in names
    window.close()
    application.processEvents()


def test_modbus_menu_creates_dialog_and_serial_bar_size_is_unchanged() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(port_scanner=lambda: [SerialPortInfo(device="/dev/ttyUSB0")])
    window.resize(1200, 800)
    window.show()
    application.processEvents()
    height = window.connection_bar.height()
    dialog = ModbusDeviceDialog(parent=window, ports=(SerialPortInfo(device="/dev/ttyUSB0"),))
    dialog.show()
    application.processEvents()
    assert dialog.isVisible()
    dialog.close()
    application.processEvents()
    window.resize(900, 700)
    application.processEvents()
    assert window.connection_bar.height() < 220
    window.resize(1200, 800)
    application.processEvents()
    assert abs(window.connection_bar.height() - height) < 40
    window.close()
    application.processEvents()
