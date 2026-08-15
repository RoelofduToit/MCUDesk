"""Startup prompt for recordings that did not shut down cleanly."""

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from serialscope.logging.recovery import (
    InterruptedRecording,
    RecordingRecoveryError,
    discard_interrupted_recording,
    recover_interrupted_recording,
)


class InterruptedRecordingDialog(QDialog):
    """Let the operator recover, discard, or defer each interrupted session."""

    def __init__(
        self,
        sessions: tuple[InterruptedRecording, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Interrupted recording")
        self.setObjectName("interruptedRecordingDialog")
        self._sessions = {str(item.directory): item for item in sessions}
        layout = QVBoxLayout(self)
        heading = QLabel("An interrupted recording was found.")
        heading.setObjectName("interruptedRecordingHeading")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        self.list = QListWidget()
        self.list.setObjectName("interruptedRecordingList")
        for session in sessions:
            item = QListWidgetItem(f"{session.session_name}  —  {session.started_local}")
            item.setData(Qt.ItemDataRole.UserRole, str(session.directory))
            self.list.addItem(item)
        layout.addWidget(self.list)
        self.details = QLabel()
        self.details.setObjectName("interruptedRecordingDetails")
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        buttons = QHBoxLayout()
        self.recover_button = QPushButton("Recover")
        self.discard_button = QPushButton("Discard")
        self.folder_button = QPushButton("Open Folder")
        self.later_button = QPushButton("Decide Later")
        buttons.addWidget(self.recover_button)
        buttons.addWidget(self.discard_button)
        buttons.addWidget(self.folder_button)
        buttons.addStretch()
        buttons.addWidget(self.later_button)
        layout.addLayout(buttons)
        self.list.currentItemChanged.connect(self._show_details)
        self.recover_button.clicked.connect(self._recover_selected)
        self.discard_button.clicked.connect(self._discard_selected)
        self.folder_button.clicked.connect(self._open_selected_folder)
        self.later_button.clicked.connect(self.reject)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _selected(self) -> InterruptedRecording | None:
        item = self.list.currentItem()
        if item is None:
            return None
        return self._sessions.get(str(item.data(Qt.ItemDataRole.UserRole)))

    def _show_details(self) -> None:
        session = self._selected()
        if session is None:
            self.details.setText("")
            return
        self.details.setText(
            f"Session: {session.session_name}\n"
            f"Started: {session.started_local or '—'}\n"
            f"Last checkpoint: {session.last_checkpoint or '—'}\n"
            f"Approximate duration: {session.duration_label}\n"
            f"Samples: {session.sample_count}\n"
            f"Logged bytes: {session.logged_bytes}\n"
            f"Location: {session.directory}"
        )

    def _recover_selected(self) -> None:
        session = self._selected()
        if session is None:
            return
        try:
            recover_interrupted_recording(session.directory)
        except RecordingRecoveryError as error:
            QMessageBox.warning(self, "Recovery failed", str(error))
            return
        self._remove_current(f"Recovered {session.session_name}.")

    def _discard_selected(self) -> None:
        session = self._selected()
        if session is None:
            return
        discard_interrupted_recording(session.directory)
        self._remove_current(f"Discarded recovery for {session.session_name}.")

    def _open_selected_folder(self) -> None:
        session = self._selected()
        if session is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(session.directory))))

    def _remove_current(self, message: str) -> None:
        row = self.list.currentRow()
        item = self.list.takeItem(row)
        if item is not None:
            self._sessions.pop(str(item.data(Qt.ItemDataRole.UserRole)), None)
        if self.list.count() == 0:
            QMessageBox.information(self, "Interrupted recording", message)
            self.accept()
            return
        self.list.setCurrentRow(min(row, self.list.count() - 1))
        self._show_details()
