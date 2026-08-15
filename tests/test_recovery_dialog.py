import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from serialscope.logging import (
    RecordingSession,
    SessionConfig,
    inspect_interrupted_recording,
    is_interrupted_recording,
)
from serialscope.parsing import ChannelUpdate
from serialscope.replay import load_replay_session
from serialscope.ui.recovery_dialog import InterruptedRecordingDialog


def _crash(session: RecordingSession) -> None:
    session._raw_logger.stop()
    session._structured_logger.stop()
    session._event_logger.stop()
    session._clear_active_state()


def test_recovery_dialog_recovers_and_discards_independently(
    monkeypatch, tmp_path: Path
) -> None:
    application = QApplication.instance() or QApplication([])
    first = RecordingSession()
    first_dir = first.start(tmp_path, SessionConfig("Alpha", "COM4", 115200, "LF"))
    first.write(b"a\n")
    first.write_structured(ChannelUpdate(("TC1",), (1.0,)))
    first.flush()
    _crash(first)
    second = RecordingSession()
    second_dir = second.start(tmp_path, SessionConfig("Beta", "COM5", 9600, "LF"))
    second.write(b"b\n")
    second.write_structured(ChannelUpdate(("TC1",), (2.0,)))
    second.flush()
    _crash(second)
    sessions = (
        inspect_interrupted_recording(first_dir),
        inspect_interrupted_recording(second_dir),
    )
    assert sessions[0] is not None and sessions[1] is not None
    monkeypatch.setattr(QMessageBox, "information", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args, **_kwargs: None)
    dialog = InterruptedRecordingDialog(sessions)
    heading = dialog.findChild(QLabel, "interruptedRecordingHeading")
    assert heading is not None
    assert heading.text() == "An interrupted recording was found."
    assert dialog.list.count() == 2
    dialog.list.setCurrentRow(0)
    dialog.recover_button.click()
    assert not is_interrupted_recording(first_dir)
    assert is_interrupted_recording(second_dir)
    assert load_replay_session(first_dir).samples[0].values["TC1"] == 1.0
    assert dialog.list.count() == 1
    dialog.discard_button.click()
    assert not is_interrupted_recording(second_dir)
    assert second_dir.is_dir()
    dialog.close()
    application.processEvents()


def test_recovery_dialog_open_folder_uses_selected_directory(
    monkeypatch, tmp_path: Path
) -> None:
    application = QApplication.instance() or QApplication([])
    session = RecordingSession()
    directory = session.start(tmp_path, SessionConfig("Folder", "COM4", 115200, "LF"))
    _crash(session)
    inspected = inspect_interrupted_recording(directory)
    assert inspected is not None
    opened: list[str] = []
    monkeypatch.setattr(
        "serialscope.ui.recovery_dialog.QDesktopServices.openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )
    dialog = InterruptedRecordingDialog((inspected,))
    dialog.folder_button.click()
    assert [Path(item) for item in opened] == [directory]
    dialog.close()
    application.processEvents()
