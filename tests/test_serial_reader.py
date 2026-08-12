from unittest.mock import Mock

from serialscope.serial import SerialConnectionError, SerialReaderWorker


def test_reader_forwards_incoming_raw_bytes() -> None:
    connection = Mock()
    worker = SerialReaderWorker(connection)
    chunks: list[bytes] = []

    def read() -> bytes:
        worker.request_stop()
        return b"Temperature: 24.6\n"

    connection.read.side_effect = read
    worker.bytes_received.connect(chunks.append)

    worker.run()

    assert chunks == [b"Temperature: 24.6\n"]


def test_reader_stops_without_emitting_empty_chunks() -> None:
    connection = Mock()
    worker = SerialReaderWorker(connection)
    chunks: list[bytes] = []

    def read() -> bytes:
        worker.request_stop()
        return b""

    connection.read.side_effect = read
    worker.bytes_received.connect(chunks.append)

    worker.run()

    assert chunks == []


def test_reader_reports_serial_failure() -> None:
    connection = Mock()
    connection.read.side_effect = SerialConnectionError("Device disconnected")
    worker = SerialReaderWorker(connection)
    errors: list[str] = []
    worker.failed.connect(errors.append)

    worker.run()

    assert errors == ["Device disconnected"]
