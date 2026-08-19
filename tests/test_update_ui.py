import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from serialscope.settings import ApplicationSettings
from serialscope.ui.update_controller import UpdateController
from serialscope.ui.update_dialogs import DownloadProgressDialog, UpdateAvailableDialog
from serialscope.updates import ReleaseAsset, UpdateInfo


class FakeChecker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    checking_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.check_count = 0
        self.canceled = False

    def check(self) -> bool:
        self.check_count += 1
        return True

    def cancel(self) -> None:
        self.canceled = True


class FakeDownloader(QObject):
    progress = Signal(int, int)
    completed = Signal(object)
    failed = Signal(str)
    canceled = Signal()
    active_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.asset = None
        self.was_canceled = False

    def download(self, asset) -> bool:
        self.asset = asset
        return True

    def cancel(self) -> None:
        self.was_canceled = True


def _settings(tmp_path: Path) -> ApplicationSettings:
    return ApplicationSettings(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )


def _info(latest: str = "0.11.1", asset: ReleaseAsset | None = None) -> UpdateInfo:
    return UpdateInfo(
        installed_version="0.11.0",
        latest_version=latest,
        release_name=f"MCUDesk {latest}",
        release_notes="Safe release notes",
        release_url=f"https://example.invalid/releases/{latest}",
        asset=asset,
    )


def test_update_dialog_displays_plain_release_notes_and_compatible_state() -> None:
    application = QApplication.instance() or QApplication([])
    asset = ReleaseAsset(
        "serialscope_0.11.1_amd64.deb",
        "https://example.invalid/update.deb",
        100,
        "a" * 64,
    )
    dialog = UpdateAvailableDialog(_info(asset=asset))

    assert dialog.release_notes.toPlainText() == "Safe release notes"
    assert dialog.download_button.isEnabled()
    assert "SHA-256" in dialog.package_status.text()
    dialog.close()
    application.processEvents()


def test_update_dialog_disables_download_without_package_or_digest() -> None:
    application = QApplication.instance() or QApplication([])
    missing = UpdateAvailableDialog(_info())
    untrusted = UpdateAvailableDialog(
        _info(
            asset=ReleaseAsset(
                "serialscope_0.11.1_amd64.deb",
                "https://example.invalid/update.deb",
                100,
                None,
                "Digest unavailable",
            )
        )
    )

    assert not missing.download_button.isEnabled()
    assert "no compatible" in missing.package_status.text().lower()
    assert not untrusted.download_button.isEnabled()
    assert untrusted.package_status.text() == "Digest unavailable"
    missing.close()
    untrusted.close()
    application.processEvents()


def test_download_progress_uses_actual_bytes() -> None:
    QApplication.instance() or QApplication([])
    dialog = DownloadProgressDialog("0.11.1", 1_000_000)
    dialog.set_progress(421_000, 1_000_000)

    assert dialog.progress_bar.value() == 421_000
    assert dialog.byte_label.text() == "421.0 KB / 1.0 MB"
    dialog.close()


def test_manual_current_check_always_reports_result(monkeypatch, tmp_path: Path) -> None:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    checker = FakeChecker()
    controller = UpdateController(parent, _settings(tmp_path), lambda: False, checker, FakeDownloader())
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[2]))

    controller.check_manually()
    assert controller._checking_dialog is not None
    checker.succeeded.emit(_info(latest="0.11.0"))

    assert "up to date" in messages[0].lower()
    assert "Installed version: 0.11.0" in messages[0]
    parent.close()


def test_automatic_checks_are_rate_limited_disabled_and_fail_quietly(
    monkeypatch, tmp_path: Path
) -> None:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    settings = _settings(tmp_path)
    checker = FakeChecker()
    controller = UpdateController(parent, settings, lambda: False, checker, FakeDownloader())
    now = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))

    assert controller.check_automatically_if_due(now)
    assert checker.check_count == 1
    checker.failed.emit("offline")
    assert warnings == []
    assert not controller.check_automatically_if_due(now + timedelta(hours=1))

    settings.set_automatically_check_for_updates(False)
    assert not controller.check_automatically_if_due(now + timedelta(days=2))
    assert checker.check_count == 1
    parent.close()


def test_automatic_update_notifies_only_once_per_session(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    parent = QWidget()
    checker = FakeChecker()
    controller = UpdateController(parent, _settings(tmp_path), lambda: False, checker, FakeDownloader())
    checker.succeeded.emit(_info())
    first_dialog = controller._update_dialog
    checker.succeeded.emit(_info())

    assert first_dialog is not None
    assert controller._update_dialog is first_dialog
    controller.shutdown()
    parent.close()
    application.processEvents()


def test_update_dialog_view_and_download_actions_use_release_metadata(
    monkeypatch, tmp_path: Path
) -> None:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    checker = FakeChecker()
    downloader = FakeDownloader()
    controller = UpdateController(parent, _settings(tmp_path), lambda: False, checker, downloader)
    asset = ReleaseAsset(
        "serialscope_0.11.1_amd64.deb",
        "https://example.invalid/update.deb",
        100,
        "a" * 64,
    )
    info = _info(asset=asset)
    opened = []
    monkeypatch.setattr(
        "serialscope.ui.update_controller.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString()) or True,
    )

    checker.succeeded.emit(info)
    assert controller._update_dialog is not None
    controller._update_dialog.view_release_button.click()
    controller._update_dialog.download_button.click()

    assert opened == [info.release_url]
    assert downloader.asset == asset
    assert controller._download_dialog is not None
    controller.shutdown()
    parent.close()


def test_verified_download_creates_explicit_install_state(tmp_path: Path) -> None:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    downloader = FakeDownloader()
    controller = UpdateController(parent, _settings(tmp_path), lambda: False, FakeChecker(), downloader)
    package = tmp_path / "serialscope_0.11.1_amd64.deb"
    package.write_bytes(b"verified")

    downloader.completed.emit(package)

    assert controller._downloaded_package == package
    assert controller._ready_dialog is not None
    assert controller._ready_dialog.install_button.text() == "Install Update"
    controller.shutdown()
    parent.close()


def test_install_is_blocked_during_recording_without_stopping_it(
    monkeypatch, tmp_path: Path
) -> None:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    recording = {"active": True}
    controller = UpdateController(
        parent,
        _settings(tmp_path),
        lambda: recording["active"],
        FakeChecker(),
        FakeDownloader(),
    )
    package = tmp_path / "serialscope_0.11.1_amd64.deb"
    package.write_bytes(b"verified")
    warnings = []
    opened = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    monkeypatch.setattr(
        "serialscope.ui.update_controller.QDesktopServices.openUrl",
        lambda url: opened.append(url) or True,
    )

    assert not controller.install_downloaded_update(package)
    assert recording["active"]
    assert opened == []
    assert warnings == ["Stop the active recording before installing the update."]
    parent.close()


def test_install_handoff_opens_verified_deb_when_not_recording(
    monkeypatch, tmp_path: Path
) -> None:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    controller = UpdateController(parent, _settings(tmp_path), lambda: False, FakeChecker(), FakeDownloader())
    package = tmp_path / "serialscope_0.11.1_amd64.deb"
    package.write_bytes(b"verified")
    opened = []
    monkeypatch.setattr(
        "serialscope.ui.update_controller.QDesktopServices.openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)

    assert controller.install_downloaded_update(package)
    assert [Path(path) for path in opened] == [package]
    parent.close()


def test_controller_shutdown_cancels_check_and_download(tmp_path: Path) -> None:
    QApplication.instance() or QApplication([])
    checker = FakeChecker()
    downloader = FakeDownloader()
    parent = QWidget()
    controller = UpdateController(parent, _settings(tmp_path), lambda: False, checker, downloader)

    controller.shutdown()

    assert checker.canceled
    assert downloader.was_canceled
    parent.close()
