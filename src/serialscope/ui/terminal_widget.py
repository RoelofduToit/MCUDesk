"""Terminal output and command controls."""

import codecs

from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class TerminalWidget(QFrame):
    """Display terminal content and an inert command entry row."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("terminalPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("panelHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 11, 16, 11)

        title = QLabel("TERMINAL")
        title.setObjectName("panelTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        hint = QLabel("Serial output")
        hint.setObjectName("mutedLabel")
        header_layout.addWidget(hint)
        layout.addWidget(header)

        self.output = QPlainTextEdit()
        self.output.setObjectName("terminalOutput")
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Serial data will appear here when connected.")
        self.output.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        layout.addWidget(self.output, 1)

        command_area = QWidget()
        command_area.setObjectName("commandArea")
        command_layout = QHBoxLayout(command_area)
        command_layout.setContentsMargins(12, 12, 12, 12)
        command_layout.setSpacing(10)

        self.command_input = QLineEdit()
        self.command_input.setObjectName("commandInput")
        self.command_input.setPlaceholderText("Enter a command to send…")
        self.command_input.setClearButtonEnabled(True)
        self.command_input.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        command_layout.addWidget(self.command_input, 1)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        command_layout.addWidget(self.send_button)
        layout.addWidget(command_area)

        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def append_bytes(self, data: bytes) -> None:
        """Decode and append a raw stream chunk without altering line breaks."""
        text = self._decoder.decode(data)
        if not text:
            return

        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def reset_stream_decoder(self) -> None:
        """Reset decoding state for a newly connected byte stream."""
        self._decoder.reset()
