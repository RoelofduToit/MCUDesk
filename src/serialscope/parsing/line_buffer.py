"""Bounded byte buffering for newline-delimited serial formats."""

from __future__ import annotations


DEFAULT_MAX_LINE_BYTES = 1_048_576


class BoundedLineBuffer:
    """Collect complete LF-delimited lines while discarding oversized input."""

    def __init__(self, max_line_bytes: int = DEFAULT_MAX_LINE_BYTES) -> None:
        if max_line_bytes < 1:
            raise ValueError("Maximum line length must be positive.")
        self._maximum = max_line_bytes
        self._buffer = bytearray()
        self._discarding_oversized_line = False
        self.discarded_line_count = 0

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def reset(self) -> None:
        self._buffer.clear()
        self._discarding_oversized_line = False
        self.discarded_line_count = 0

    def feed(self, data: bytes) -> tuple[bytes, ...]:
        lines: list[bytes] = []
        offset = 0
        while offset < len(data):
            newline = data.find(b"\n", offset)
            if self._discarding_oversized_line:
                if newline < 0:
                    break
                self._discarding_oversized_line = False
                self.discarded_line_count += 1
                offset = newline + 1
                continue

            if newline < 0:
                tail = data[offset:]
                if len(self._buffer) + len(tail) > self._maximum:
                    self._buffer.clear()
                    self._discarding_oversized_line = True
                else:
                    self._buffer.extend(tail)
                break

            segment = data[offset:newline]
            if len(self._buffer) + len(segment) <= self._maximum:
                self._buffer.extend(segment)
                line = bytes(self._buffer)
                lines.append(line[:-1] if line.endswith(b"\r") else line)
            else:
                self.discarded_line_count += 1
            self._buffer.clear()
            offset = newline + 1
        return tuple(lines)
