import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from serialscope.modbus import (
    FakeModbusTransport,
    ModbusClientError,
    ModbusPoller,
    ModbusRegister,
    ModbusRtuConfiguration,
    probe_modbus_connection,
)
from serialscope.modbus.poller import ModbusPollerWorker


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
