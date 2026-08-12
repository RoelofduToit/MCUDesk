"""Terminal output and command controls."""

import codecs

from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


LINE_ENDINGS = {
    "None": b"",
    "LF": b"\n",
    "CR": b"\r",
    "CRLF": b"\r\n",
}
DEFAULT_MAXIMUM_BLOCKS = 10_000
ESCAPE = "\x1b"
STRING_TERMINATOR = "\\"


class TerminalWidget(QFrame):
    """Display terminal content and an inert command entry row."""

    def __init__(
        self,
        parent: QWidget | None = None,
        maximum_blocks: int = DEFAULT_MAXIMUM_BLOCKS,
    ) -> None:
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

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("clearTerminalButton")
        self.clear_button.setToolTip("Clear visible terminal output")
        self.clear_button.clicked.connect(self.output_clear)
        header_layout.addWidget(self.clear_button)
        layout.addWidget(header)

        self.output = QPlainTextEdit()
        self.output.setObjectName("terminalOutput")
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Serial data will appear here when connected.")
        self.output.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.output.document().setMaximumBlockCount(maximum_blocks)
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

        self.line_ending_combo = QComboBox()
        self.line_ending_combo.setObjectName("lineEndingCombo")
        self.line_ending_combo.addItems(LINE_ENDINGS)
        self.line_ending_combo.setCurrentText("LF")
        self.line_ending_combo.setToolTip("Line ending appended to transmitted text")
        command_layout.addWidget(self.line_ending_combo)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("sendButton")
        command_layout.addWidget(self.send_button)
        layout.addWidget(command_area)

        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._control_sequence_state = "text"
        self.set_connected(False)

    def command_bytes(self) -> bytes:
        """Encode the current command and selected line ending as raw bytes."""
        line_ending = LINE_ENDINGS[self.line_ending_combo.currentText()]
        return self.command_input.text().encode("utf-8") + line_ending

    def set_connected(self, connected: bool) -> None:
        """Enable transmit controls only while a serial port is connected."""
        self.command_input.setEnabled(connected)
        self.line_ending_combo.setEnabled(connected)
        self.send_button.setEnabled(connected)

    def append_bytes(self, data: bytes) -> None:
        """Decode and append a raw stream chunk without altering line breaks."""
        text = self._filter_control_sequences(self._decoder.decode(data))
        if not text:
            return

        scroll_bar = self.output.verticalScrollBar()
        previous_value = scroll_bar.value()
        should_follow = previous_value >= scroll_bar.maximum()

        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        if should_follow:
            scroll_bar.setValue(scroll_bar.maximum())
        else:
            scroll_bar.setValue(previous_value)

    def output_clear(self) -> None:
        """Clear only the visible terminal history."""
        self.output.clear()

    def reset_stream_decoder(self) -> None:
        """Reset decoding state for a newly connected byte stream."""
        self._decoder.reset()
        self._control_sequence_state = "text"

    def _filter_control_sequences(self, text: str) -> str:
        """Remove common terminal controls from display text incrementally."""
        visible: list[str] = []

        for character in text:
            state = self._control_sequence_state
            if state == "text":
                if character == ESCAPE:
                    self._control_sequence_state = "escape"
                else:
                    visible.append(character)
            elif state == "escape":
                if character == "]":
                    self._control_sequence_state = "osc"
                elif character == "[":
                    self._control_sequence_state = "csi"
                elif character == ESCAPE:
                    self._control_sequence_state = "escape"
                else:
                    self._control_sequence_state = "text"
            elif state == "csi":
                if "@" <= character <= "~":
                    self._control_sequence_state = "text"
            elif state == "osc":
                if character == "\x07":
                    self._control_sequence_state = "text"
                elif character == ESCAPE:
                    self._control_sequence_state = "osc_escape"
            elif state == "osc_escape":
                if character == STRING_TERMINATOR:
                    self._control_sequence_state = "text"
                elif character != ESCAPE:
                    self._control_sequence_state = "osc"

        return "".join(visible)
