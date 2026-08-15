"""Background serial byte reader using Qt threading primitives."""

from threading import Event

from PySide6.QtCore import QObject, QThread, Signal, Slot

from serialscope.serial.connection import SerialConnection, SerialConnectionError


class SerialReaderWorker(QObject):
    """Continuously read byte chunks without accessing UI objects."""

    bytes_received = Signal(bytes)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, connection: SerialConnection) -> None:
        super().__init__()
        self._connection = connection
        self._stop_requested = Event()

    @Slot()
    def run(self) -> None:
        """Read until stopped or the connection fails."""
        try:
            while not self._stop_requested.is_set():
                data = self._connection.read()
                if data:
                    self.bytes_received.emit(data)
        except SerialConnectionError as error:
            if not self._stop_requested.is_set():
                self.failed.emit(str(error))
        except Exception as error:
            if not self._stop_requested.is_set():
                self.failed.emit(f"Serial reader failed: {error}")
        finally:
            self.finished.emit()

    def request_stop(self) -> None:
        """Request termination; the short serial timeout bounds shutdown."""
        self._stop_requested.set()


class SerialReader(QObject):
    """Manage a reader worker and its dedicated QThread."""

    bytes_received = Signal(bytes)
    failed = Signal(str)

    def __init__(self, connection: SerialConnection) -> None:
        super().__init__()
        self._thread = QThread()
        self._worker = SerialReaderWorker(connection)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.bytes_received.connect(self.bytes_received)
        self._worker.failed.connect(self.failed)
        self._worker.finished.connect(self._thread.quit)

    @property
    def is_running(self) -> bool:
        return self._thread.isRunning()

    def start(self) -> None:
        """Start the background reader."""
        self._thread.start()

    def stop(self) -> None:
        """Stop the reader and wait briefly for its thread to finish."""
        self._worker.request_stop()
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3_000)
