"""Compact, non-blocking presentation for application updates."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from serialscope import PRODUCT_NAME
from serialscope.updates import UpdateInfo


class UpdateAvailableDialog(QDialog):
    """Present release details without rendering untrusted HTML."""

    view_release_requested = Signal()
    download_requested = Signal()

    def __init__(self, info: UpdateInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("updateAvailableDialog")
        self.setWindowTitle(f"{PRODUCT_NAME} Update")
        self.setMinimumSize(520, 360)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel(f"{PRODUCT_NAME} {info.latest_version} is available")
        title.setObjectName("updateAvailableTitle")
        layout.addWidget(title)
        versions = QLabel(
            f"Installed version: {info.installed_version}\n"
            f"Latest version: {info.latest_version}"
        )
        versions.setObjectName("updateVersionDetails")
        layout.addWidget(versions)
        layout.addWidget(QLabel("Release notes:"))
        self.release_notes = QPlainTextEdit(info.release_notes or "No release notes provided.")
        self.release_notes.setObjectName("updateReleaseNotes")
        self.release_notes.setReadOnly(True)
        layout.addWidget(self.release_notes, 1)

        self.package_status = QLabel()
        self.package_status.setObjectName("updatePackageStatus")
        self.package_status.setWordWrap(True)
        layout.addWidget(self.package_status)

        buttons = QDialogButtonBox()
        later = buttons.addButton("Later", QDialogButtonBox.ButtonRole.RejectRole)
        self.view_release_button = buttons.addButton(
            "View Release", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.download_button = buttons.addButton(
            "Download Update", QDialogButtonBox.ButtonRole.AcceptRole
        )
        later.clicked.connect(self.reject)
        self.view_release_button.clicked.connect(self.view_release_requested.emit)
        self.download_button.clicked.connect(self.download_requested.emit)
        layout.addWidget(buttons)

        if info.asset is None:
            self.package_status.setText(
                f"A newer {PRODUCT_NAME} version is available, but no compatible "
                "package was found for this system."
            )
            self.download_button.setEnabled(False)
        elif not info.asset.is_verifiable:
            self.package_status.setText(info.asset.verification_error or "Verification unavailable.")
            self.download_button.setEnabled(False)
        else:
            self.package_status.setText(f"Package: {info.asset.name} — SHA-256 available")


class DownloadProgressDialog(QDialog):
    """Display byte progress and expose explicit cancellation."""

    cancel_requested = Signal()

    def __init__(self, version: str, total_bytes: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("updateDownloadProgressDialog")
        self.setWindowTitle("Downloading Update")
        self.setModal(False)
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        self.status_label = QLabel(f"Downloading {PRODUCT_NAME} {version}")
        layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, max(0, total_bytes))
        if total_bytes <= 0:
            self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)
        self.byte_label = QLabel("0 B")
        layout.addWidget(self.byte_label)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(cancel)

    def set_progress(self, received: int, total: int) -> None:
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(min(received, total))
            self.byte_label.setText(f"{_format_bytes(received)} / {_format_bytes(total)}")
        else:
            self.progress_bar.setRange(0, 0)
            self.byte_label.setText(_format_bytes(received))


class UpdateReadyDialog(QDialog):
    """Require an explicit installation handoff after verification."""

    install_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("updateReadyDialog")
        self.setWindowTitle("Update Ready")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Update downloaded and verified."))
        buttons = QDialogButtonBox()
        later = buttons.addButton("Later", QDialogButtonBox.ButtonRole.RejectRole)
        self.install_button = buttons.addButton(
            "Install Update", QDialogButtonBox.ButtonRole.AcceptRole
        )
        later.clicked.connect(self.reject)
        self.install_button.clicked.connect(self.install_requested.emit)
        layout.addWidget(buttons)


def _format_bytes(byte_count: int) -> str:
    if byte_count < 1_000_000:
        return f"{byte_count / 1_000:.1f} KB" if byte_count >= 1_000 else f"{byte_count} B"
    return f"{byte_count / 1_000_000:.1f} MB"
