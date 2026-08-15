"""UI coordination for manual/automatic checks and installation handoff."""

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QMessageBox, QProgressDialog, QWidget

from serialscope.settings import ApplicationSettings
from serialscope.updates import UpdateChecker, UpdateDownloader, UpdateInfo, automatic_check_due
from serialscope.ui.update_dialogs import (
    DownloadProgressDialog,
    UpdateAvailableDialog,
    UpdateReadyDialog,
)


class UpdateController(QObject):
    """Keep updater networking and dialogs outside MainWindow business logic."""

    def __init__(
        self,
        parent: QWidget,
        settings: ApplicationSettings,
        recording_active: Callable[[], bool],
        checker: UpdateChecker | None = None,
        downloader: UpdateDownloader | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = parent
        self._settings = settings
        self._recording_active = recording_active
        self.checker = checker or UpdateChecker(parent=self)
        self.downloader = downloader or UpdateDownloader(parent=self)
        self._manual_check = False
        self._notified_this_session = False
        self._checking_dialog: QProgressDialog | None = None
        self._update_dialog: UpdateAvailableDialog | None = None
        self._download_dialog: DownloadProgressDialog | None = None
        self._ready_dialog: UpdateReadyDialog | None = None
        self._current_info: UpdateInfo | None = None
        self._downloaded_package: Path | None = None

        self.checker.succeeded.connect(self._check_succeeded)
        self.checker.failed.connect(self._check_failed)
        self.downloader.progress.connect(self._download_progress)
        self.downloader.completed.connect(self._download_completed)
        self.downloader.failed.connect(self._download_failed)
        self.downloader.canceled.connect(self._download_canceled)

    def check_manually(self) -> None:
        """Start or join a check that must always produce visible feedback."""
        self._manual_check = True
        self._show_checking_dialog()
        self.checker.check()

    def check_automatically_if_due(self, now: datetime | None = None) -> bool:
        """Quietly start one rate-limited background check after startup."""
        current = now or datetime.now(timezone.utc)
        if not automatic_check_due(
            self._settings.automatically_check_for_updates,
            self._settings.last_automatic_update_check,
            current,
        ):
            return False
        self._settings.set_last_automatic_update_check(current)
        self._manual_check = False
        return self.checker.check()

    def shutdown(self) -> None:
        """Abort owned replies and remove incomplete transfer state on exit."""
        self.checker.cancel()
        self.downloader.cancel()
        for dialog in (
            self._checking_dialog,
            self._update_dialog,
            self._download_dialog,
            self._ready_dialog,
        ):
            if dialog is not None:
                dialog.close()

    def install_downloaded_update(self, package_path: Path | None = None) -> bool:
        """Hand a verified package to Linux without acquiring privileges ourselves."""
        package = package_path or self._downloaded_package
        if package is None or not package.is_file():
            QMessageBox.warning(self._window, "Update unavailable", "The update package is missing.")
            return False
        if self._recording_active():
            QMessageBox.warning(
                self._window,
                "Recording in progress",
                "Stop the active recording before installing the update.",
            )
            return False
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(package))):
            QMessageBox.critical(
                self._window,
                "Unable to open update",
                "The system package installer could not be opened.",
            )
            return False
        QMessageBox.information(
            self._window,
            "Finish installing the update",
            "Complete installation in the system package installer, then restart SerialScope.",
        )
        return True

    def _show_checking_dialog(self) -> None:
        if self._checking_dialog is not None:
            return
        dialog = QProgressDialog("Checking for updates...", "", 0, 0, self._window)
        dialog.setObjectName("updateCheckingDialog")
        dialog.setWindowTitle("SerialScope Update")
        dialog.setCancelButton(None)
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        dialog.setMinimumDuration(0)
        dialog.show()
        self._checking_dialog = dialog

    def _close_checking_dialog(self) -> None:
        if self._checking_dialog is not None:
            self._checking_dialog.close()
            self._checking_dialog.deleteLater()
            self._checking_dialog = None

    def _check_succeeded(self, info: UpdateInfo) -> None:
        manual = self._manual_check
        self._manual_check = False
        self._close_checking_dialog()
        self._current_info = info
        if not info.update_available:
            if manual:
                QMessageBox.information(
                    self._window,
                    "SerialScope Update",
                    "SerialScope is up to date.\n\n"
                    f"Installed version: {info.installed_version}\n"
                    f"Latest version: {info.latest_version}",
                )
            return
        if not manual and self._notified_this_session:
            return
        self._notified_this_session = True
        dialog = UpdateAvailableDialog(info, self._window)
        dialog.view_release_requested.connect(
            lambda: QDesktopServices.openUrl(QUrl(info.release_url))
        )
        dialog.download_requested.connect(self._start_download)
        dialog.show()
        self._update_dialog = dialog

    def _check_failed(self, _details: str) -> None:
        manual = self._manual_check
        self._manual_check = False
        self._close_checking_dialog()
        if manual:
            QMessageBox.warning(
                self._window,
                "Unable to check for updates",
                "Unable to check for updates.\n\n"
                "Check your internet connection and try again.",
            )

    def _start_download(self) -> None:
        info = self._current_info
        if info is None or info.asset is None:
            return
        if self._update_dialog is not None:
            self._update_dialog.accept()
        dialog = DownloadProgressDialog(info.latest_version, info.asset.size, self._window)
        dialog.cancel_requested.connect(self.downloader.cancel)
        dialog.show()
        self._download_dialog = dialog
        if not self.downloader.download(info.asset):
            dialog.close()

    def _download_progress(self, received: int, total: int) -> None:
        if self._download_dialog is not None:
            self._download_dialog.set_progress(received, total)

    def _download_completed(self, package_path: Path) -> None:
        if self._download_dialog is not None:
            self._download_dialog.close()
            self._download_dialog = None
        self._downloaded_package = package_path
        dialog = UpdateReadyDialog(self._window)
        dialog.install_requested.connect(self.install_downloaded_update)
        dialog.show()
        self._ready_dialog = dialog

    def _download_failed(self, message: str) -> None:
        if self._download_dialog is not None:
            self._download_dialog.close()
            self._download_dialog = None
        QMessageBox.critical(self._window, "Update download failed", message)

    def _download_canceled(self) -> None:
        if self._download_dialog is not None:
            self._download_dialog.close()
            self._download_dialog = None
