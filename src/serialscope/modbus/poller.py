"""Background Modbus RTU polling using the existing Qt thread pattern."""

from __future__ import annotations

from collections.abc import Callable
import struct
from threading import Event
import time

from PySide6.QtCore import QObject, QThread, Signal, Slot

from serialscope.modbus.client import ModbusClientError, ModbusTransport
from serialscope.modbus.decode import decode_registers
from serialscope.modbus.grouping import group_register_reads
from serialscope.modbus.model import ModbusRtuConfiguration
from serialscope.parsing import ChannelUpdate

FATAL_KINDS = {"disconnected"}
ERROR_EMIT_INTERVAL_S = 2.0


class ModbusPollerWorker(QObject):
    """Poll one slave on a dedicated thread without touching widgets."""

    values_ready = Signal(object)
    status_changed = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        configuration: ModbusRtuConfiguration,
        transport_factory: Callable[[], ModbusTransport],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__()
        self._configuration = configuration
        self._transport_factory = transport_factory
        self._clock = clock
        self._stop_requested = Event()
        self._last_error_kind: str | None = None
        self._last_error_at = 0.0

    def request_stop(self) -> None:
        self._stop_requested.set()

    @Slot()
    def run(self) -> None:
        transport: ModbusTransport | None = None
        try:
            transport = self._transport_factory()
            transport.connect()
            if self._stop_requested.is_set():
                return
            self.status_changed.emit("connected")
            blocks = group_register_reads(self._configuration.enabled_registers)
            interval = max(self._configuration.interval_ms / 1000.0, 0.05)
            slave_id = self._configuration.connection.slave_id
            while not self._stop_requested.is_set():
                started = self._clock()
                try:
                    update = self._poll_once(transport, blocks, slave_id)
                except ModbusClientError as error:
                    if error.kind in FATAL_KINDS:
                        self.failed.emit(str(error))
                        return
                    self._emit_soft_error(error)
                else:
                    if update is not None:
                        self.values_ready.emit(update)
                    if self._last_error_kind is not None:
                        self._last_error_kind = None
                        self.status_changed.emit("polling")
                remaining = interval - (self._clock() - started)
                self._wait(remaining)
        except ModbusClientError as error:
            if not self._stop_requested.is_set():
                self.failed.emit(str(error))
        except Exception as error:
            if not self._stop_requested.is_set():
                self.failed.emit(f"Modbus polling failed: {error}")
        finally:
            if transport is not None:
                try:
                    transport.close()
                except Exception:
                    pass
            self.finished.emit()

    def _poll_once(
        self,
        transport: ModbusTransport,
        blocks,
        slave_id: int,
    ) -> ChannelUpdate | None:
        names: list[str] = []
        values: list[int | float] = []
        for block in blocks:
            try:
                if block.kind == "holding":
                    words = transport.read_holding_registers(block.address, block.count, slave_id)
                else:
                    words = transport.read_input_registers(block.address, block.count, slave_id)
            except ModbusClientError as error:
                if error.kind in FATAL_KINDS:
                    raise
                self._emit_soft_error(error)
                continue
            for register, offset in block.items:
                slice_words = words[offset : offset + register.register_count]
                try:
                    value = decode_registers(slice_words, register)
                except (ValueError, struct.error) as error:
                    self._emit_soft_error(
                        ModbusClientError(f"{register.name}: {error}", "protocol")
                    )
                    continue
                names.append(register.name)
                values.append(value)
        if not names:
            return None
        return ChannelUpdate(tuple(names), tuple(values), replace_channels=False)

    def _emit_soft_error(self, error: ModbusClientError) -> None:
        now = self._clock()
        if (
            error.kind == self._last_error_kind
            and now - self._last_error_at < ERROR_EMIT_INTERVAL_S
        ):
            return
        self._last_error_kind = error.kind
        self._last_error_at = now
        self.status_changed.emit(error.kind)

    def _wait(self, seconds: float) -> None:
        deadline = self._clock() + max(0.0, seconds)
        while not self._stop_requested.is_set() and self._clock() < deadline:
            remaining = deadline - self._clock()
            self._stop_requested.wait(min(0.05, remaining))


class ModbusPoller(QObject):
    """Own one Modbus worker thread for a single source."""

    values_ready = Signal(object)
    status_changed = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        configuration: ModbusRtuConfiguration,
        transport_factory: Callable[[], ModbusTransport],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__()
        self._thread = QThread()
        self._worker = ModbusPollerWorker(configuration, transport_factory, clock)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.values_ready.connect(self.values_ready)
        self._worker.status_changed.connect(self.status_changed)
        self._worker.failed.connect(self.failed)
        self._worker.finished.connect(self._thread.quit)

    @property
    def is_running(self) -> bool:
        return self._thread.isRunning()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._worker.request_stop()
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3_000)
