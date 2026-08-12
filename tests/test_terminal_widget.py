import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from serialscope.ui.terminal_widget import TerminalWidget


def test_clear_removes_only_visible_terminal_content() -> None:
    application = QApplication.instance() or QApplication([])
    terminal = TerminalWidget()
    terminal.append_bytes(b"Visible data\n")

    terminal.clear_button.click()

    assert terminal.output.toPlainText() == ""
    application.processEvents()


def test_terminal_history_is_limited_to_configured_block_count() -> None:
    application = QApplication.instance() or QApplication([])
    terminal = TerminalWidget(maximum_blocks=3)

    terminal.append_bytes(b"one\ntwo\nthree\nfour\nfive")

    assert terminal.output.document().blockCount() <= 3
    assert "one" not in terminal.output.toPlainText()
    assert "five" in terminal.output.toPlainText()
    application.processEvents()


def test_auto_scroll_pauses_above_bottom_and_resumes_at_bottom() -> None:
    application = QApplication.instance() or QApplication([])
    terminal = TerminalWidget()
    terminal.resize(500, 240)
    terminal.show()
    terminal.append_bytes(b"".join(f"line {index}\n".encode() for index in range(100)))
    application.processEvents()

    scroll_bar = terminal.output.verticalScrollBar()
    scroll_bar.setValue(0)
    terminal.append_bytes(b"new while reviewing\n")
    assert scroll_bar.value() == 0

    scroll_bar.setValue(scroll_bar.maximum())
    terminal.append_bytes(b"new while following\n")
    assert scroll_bar.value() == scroll_bar.maximum()

    terminal.close()
    application.processEvents()
