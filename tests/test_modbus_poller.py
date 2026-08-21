import os
from threading import Event
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from serialscope.modbus import (
    FakeModbusTransport,
    ModbusClientError,
    ModbusPoller,
    ModbusRegister,
    ModbusRtuConfiguration,
    probe_modbus_connection,
)
from serialscope.modbus.model import ModbusConnectionSettings
from serialscope.modbus.poller import ModbusPollerWorker
from serialscope.serial import SerialSourceManager


def _wait_until(condition, timeout_s: float = 2.0) -> bool:
    application = QApplication.instance() or QApplication([])
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        application.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def test_successful_poll_emits_channel_update() -> None:
    QApplication.instance() or QApplication([])
    transport = FakeModbusTransport(holding={0: 1500, 1: 237})
    configuration = ModbusRtuConfiguration(
        interval_ms=50,
        registers=(
            ModbusRegister(name="RPM", address=0),
            ModbusRegister(name="Current", address=1, scale=0.1),
        ),
    )
    poller = ModbusPoller(configuration, lambda: transport)
    updates = []
    poller.values_ready.connect(updates.append)
    poller.start()
    assert _wait_until(lambda: bool(updates))
    poller.stop()
    assert updates[0].names == ("RPM", "Current")
    assert updates[0].values[0] == 1500
    assert updates[0].values[1] == pytest.approx(23.7)
    assert transport.closed


def test_timeout_does_not_crash_and_one_failed_block_is_skipped() -> None:
    QApplication.instance() or QApplication([])
    transport = FakeModbusTransport(holding={0: 9})

    def flaky_read(address, count, slave_id):
        if address == 10:
            raise ModbusClientError("timed out", "timeout")
        return FakeModbusTransport.read_holding_registers(
            transport, address, count, slave_id
        )

    transport.read_holding_registers = flaky_read  # type: ignore[method-assign]
    configuration = ModbusRtuConfiguration(
        interval_ms=50,
        registers=(
            ModbusRegister(name="OK", address=0),
            ModbusRegister(name="Missing", address=10),
        ),
    )
    statuses = []
    updates = []
    poller = ModbusPoller(configuration, lambda: transport)
    poller.status_changed.connect(statuses.append)
    poller.values_ready.connect(updates.append)
    poller.start()
    assert _wait_until(lambda: bool(updates) and "timeout" in statuses)
    poller.stop()
    assert updates[0].names == ("OK",)


def test_disconnect_failure_stops_worker() -> None:
    QApplication.instance() or QApplication([])
    transport = FakeModbusTransport()
    transport.connect_error = "adapter unplugged"
    failed = []
    poller = ModbusPoller(
        ModbusRtuConfiguration(registers=(ModbusRegister(name="A"),)),
        lambda: transport,
    )
    poller.failed.connect(failed.append)
    poller.start()
    assert _wait_until(lambda: bool(failed))
    poller.stop()
    assert "unplugged" in failed[0]


def test_worker_stop_is_honoured_before_loop() -> None:
    transport = FakeModbusTransport(holding={0: 1})
    worker = ModbusPollerWorker(
        ModbusRtuConfiguration(registers=(ModbusRegister(name="A"),)),
        lambda: transport,
    )
    worker.request_stop()
    worker.run()
    assert transport.closed


def test_connection_test_reads_first_register() -> None:
    transport = FakeModbusTransport(holding={0: 42})
    message = probe_modbus_connection(
        transport,
        ModbusRtuConfiguration(registers=(ModbusRegister(name="Speed"),)),
    )
    assert "Device responding" in message
    assert "42" in message
    assert transport.closed


class _BlockingModbusTransport:
    """Model a pymodbus read that is blocked until a timeout or gate opens."""

    def __init__(self, *, block_s: float = 0.3, holding: dict[int, int] | None = None) -> None:
        self.holding = dict(holding or {0: 1})
        self.block_s = block_s
        self.connected = False
        self.closed = False
        self.in_read = Event()
        self.release = Event()
        self.reads = 0

    def connect(self) -> None:
        self.connected = True
        self.closed = False

    def close(self) -> None:
        self.connected = False
        self.closed = True
        self.release.set()

    def read_holding_registers(self, address: int, count: int, slave_id: int) -> list[int]:
        self.reads += 1
        self.in_read.set()
        self.release.wait(self.block_s)
        if self.closed:
            raise ModbusClientError("The Modbus connection is closed.", "disconnected")
        raise ModbusClientError("timed out", "timeout")

    def read_input_registers(self, address: int, count: int, slave_id: int) -> list[int]:
        return self.read_holding_registers(address, count, slave_id)


def _capture_qt_messages() -> list[str]:
    messages: list[str] = []

    def handler(_mode, _context, message: str) -> None:
        messages.append(message)

    qInstallMessageHandler(handler)
    return messages


def _scattered_registers() -> tuple[ModbusRegister, ...]:
    return tuple(ModbusRegister(name=f"R{index}", address=index * 10) for index in range(4))


def test_normal_polling_shutdown_joins_thread() -> None:
    QApplication.instance() or QApplication([])
    warnings = _capture_qt_messages()
    transport = FakeModbusTransport(holding={0: 9})
    poller = ModbusPoller(
        ModbusRtuConfiguration(interval_ms=50, registers=(ModbusRegister(name="A"),)),
        lambda: transport,
    )
    poller.start()
    assert _wait_until(lambda: transport.reads)
    poller.stop()
    assert not poller.is_running
    assert transport.closed
    assert not any("QThread: Destroyed" in message for message in warnings)


def test_shutdown_while_read_is_timing_out_joins_thread() -> None:
    QApplication.instance() or QApplication([])
    warnings = _capture_qt_messages()
    transport = _BlockingModbusTransport(block_s=0.4)
    configuration = ModbusRtuConfiguration(
        connection=ModbusConnectionSettings(timeout_s=0.2, parity="none"),
        interval_ms=50,
        registers=_scattered_registers(),
    )
    poller = ModbusPoller(configuration, lambda: transport)
    poller.start()
    assert _wait_until(lambda: transport.in_read.is_set())
    poller.stop()
    assert not poller.is_running
    assert transport.closed
    assert transport.reads == 1
    del poller
    assert not any("QThread: Destroyed" in message for message in warnings)


def test_disconnect_while_polling_joins_thread() -> None:
    application = QApplication.instance() or QApplication([])
    warnings = _capture_qt_messages()
    transport = FakeModbusTransport(holding={0: 4})
    manager = SerialSourceManager(
        modbus_transport_factory=lambda port, settings: transport,
    )
    source = manager.add_source("VSD")
    manager.apply_modbus_configuration(
        source.source_id,
        ModbusRtuConfiguration(interval_ms=50, registers=(ModbusRegister(name="RPM"),)),
    )
    manager.connect(source.source_id, "COM4", 9600)
    poller = source.poller
    assert poller is not None
    assert _wait_until(lambda: bool(transport.reads))
    manager.disconnect(source.source_id)
    application.processEvents()
    assert not poller.is_running
    assert not source.is_connected
    assert not any("QThread: Destroyed" in message for message in warnings)


def test_repeated_connect_disconnect_joins_each_thread() -> None:
    QApplication.instance() or QApplication([])
    warnings = _capture_qt_messages()
    transports: list[FakeModbusTransport] = []

    def factory(port, settings):
        transport = FakeModbusTransport(holding={0: 8})
        transports.append(transport)
        return transport

    manager = SerialSourceManager(modbus_transport_factory=factory)
    source = manager.add_source("VSD")
    configuration = ModbusRtuConfiguration(
        interval_ms=50, registers=(ModbusRegister(name="RPM"),)
    )
    manager.apply_modbus_configuration(source.source_id, configuration)
    pollers = []
    for _ in range(3):
        manager.connect(source.source_id, "COM4", 9600)
        poller = source.poller
        assert poller is not None
        pollers.append(poller)
        assert _wait_until(lambda owner=poller: owner.is_running)
        manager.disconnect(source.source_id)
        assert not poller.is_running
    assert all(not item.is_running for item in pollers)
    assert all(item.closed for item in transports)
    assert not any("QThread: Destroyed" in message for message in warnings)


def test_source_removal_while_polling_joins_thread() -> None:
    QApplication.instance() or QApplication([])
    warnings = _capture_qt_messages()
    transport = FakeModbusTransport(holding={0: 3})
    manager = SerialSourceManager(
        modbus_transport_factory=lambda port, settings: transport,
    )
    source = manager.add_source("VSD")
    source_id = source.source_id
    manager.apply_modbus_configuration(
        source_id,
        ModbusRtuConfiguration(interval_ms=50, registers=(ModbusRegister(name="RPM"),)),
    )
    manager.connect(source_id, "COM4", 9600)
    poller = source.poller
    assert poller is not None
    assert _wait_until(lambda: poller.is_running)
    manager.remove_source(source_id)
    assert not poller.is_running
    assert not any("QThread: Destroyed" in message for message in warnings)


def test_disconnect_all_stops_active_modbus_poller() -> None:
    QApplication.instance() or QApplication([])
    warnings = _capture_qt_messages()
    transport = FakeModbusTransport(holding={0: 5})
    manager = SerialSourceManager(
        modbus_transport_factory=lambda port, settings: transport,
    )
    source = manager.add_source("VSD")
    manager.apply_modbus_configuration(
        source.source_id,
        ModbusRtuConfiguration(interval_ms=50, registers=(ModbusRegister(name="RPM"),)),
    )
    manager.connect(source.source_id, "COM4", 9600)
    poller = source.poller
    assert poller is not None
    assert _wait_until(lambda: poller.is_running)
    manager.disconnect_all()
    assert not poller.is_running
    assert not any("QThread: Destroyed" in message for message in warnings)
