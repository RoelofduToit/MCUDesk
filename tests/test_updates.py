import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QApplication

from serialscope.settings import ApplicationSettings
from serialscope.updates import (
    LATEST_RELEASE_API_URL,
    LINUX_PACKAGE_ARCHITECTURE,
    ReleaseAsset,
    UpdateChecker,
    UpdateDownloader,
    UpdateMetadataError,
    automatic_check_due,
    compatible_asset_names,
    current_linux_package_architecture,
    is_update_available,
    parse_release_metadata,
    parse_sha256_digest,
)
from serialscope.updates.downloader import _is_supported_update_asset_name
from serialscope.updates.model import WINDOWS_PACKAGE_ARCHITECTURE


def _release_payload(version: str = "0.10.1", digest: str | None = None) -> dict:
    package = b"verified package bytes"
    return {
        "tag_name": f"v{version}",
        "name": f"SerialScope {version}",
        "body": "Release notes\n\n- Reliable updater",
        "html_url": f"https://github.com/RoelofduToit/MCUDesk/releases/tag/v{version}",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": f"serialscope_{version}_arm64.deb",
                "browser_download_url": "https://example.invalid/arm64.deb",
                "size": 10,
                "digest": "sha256:" + "1" * 64,
            },
            {
                "name": f"SerialScope-{version}.exe",
                "browser_download_url": "https://example.invalid/windows.exe",
                "size": 20,
            },
            {
                "name": f"serialscope_{version}_amd64.deb",
                "browser_download_url": "https://example.invalid/serialscope.deb",
                "size": len(package),
                "digest": digest or f"sha256:{hashlib.sha256(package).hexdigest()}",
            },
            {
                "name": "source.zip",
                "browser_download_url": "https://example.invalid/source.zip",
                "size": 30,
            },
        ],
    }


@pytest.mark.parametrize(
    ("installed", "latest", "expected"),
    [
        ("0.10.0", "v0.10.0", False),
        ("0.10.0", "v0.10.1", True),
        ("0.10.9", "v0.10.10", True),
        ("0.11.0", "v0.10.10", False),
    ],
)
def test_versions_are_compared_semantically(installed: str, latest: str, expected: bool) -> None:
    assert is_update_available(installed, latest) is expected


def test_invalid_release_tag_is_rejected() -> None:
    with pytest.raises(UpdateMetadataError):
        is_update_available("0.10.0", "not a version")


def test_missing_release_name_falls_back_to_mcudesk() -> None:
    payload = _release_payload()
    payload["name"] = ""
    info = parse_release_metadata(payload, "0.10.0")
    assert info.release_name == "MCUDesk 0.10.1"


def test_realistic_release_metadata_is_normalized_and_amd64_asset_is_exact() -> None:
    info = parse_release_metadata(_release_payload(), "0.10.0")

    assert info.installed_version == "0.10.0"
    assert info.latest_version == "0.10.1"
    assert info.release_name == "SerialScope 0.10.1"
    assert "Reliable updater" in info.release_notes
    assert info.release_url.endswith("/v0.10.1")
    assert info.update_available
    assert info.asset is not None
    assert info.asset.name == "serialscope_0.10.1_amd64.deb"
    assert info.asset.url == "https://example.invalid/serialscope.deb"
    assert info.asset.size == len(b"verified package bytes")
    assert info.asset.is_verifiable


def test_updater_prefers_mcudesk_linux_asset_and_keeps_legacy_fallback() -> None:
    payload = _release_payload()
    preferred = f"MCUDesk_0.10.1_Linux_amd64.deb"
    payload["assets"].insert(
        0,
        {
            "name": preferred,
            "browser_download_url": "https://example.invalid/mcudesk.deb",
            "size": 99,
            "digest": "sha256:" + "a" * 64,
        },
    )
    info = parse_release_metadata(payload, "0.10.0")
    assert info.asset is not None
    assert info.asset.name == preferred
    assert info.asset.url == "https://example.invalid/mcudesk.deb"

    legacy_only = _release_payload()
    legacy = parse_release_metadata(legacy_only, "0.10.0")
    assert legacy.asset is not None
    assert legacy.asset.name == "serialscope_0.10.1_amd64.deb"


def test_updater_accepts_mcudesk_and_legacy_windows_installers() -> None:
    digest = "sha256:" + "b" * 64
    payload = _release_payload()
    payload["assets"].extend(
        [
            {
                "name": "SerialScope_0.10.1_Windows_x64_Setup.exe",
                "browser_download_url": "https://example.invalid/legacy-setup.exe",
                "size": 11,
                "digest": digest,
            },
            {
                "name": "MCUDesk_0.10.1_Windows_x64_Setup.exe",
                "browser_download_url": "https://example.invalid/mcudesk-setup.exe",
                "size": 12,
                "digest": digest,
            },
        ]
    )
    preferred = parse_release_metadata(
        payload, "0.10.0", WINDOWS_PACKAGE_ARCHITECTURE
    )
    assert preferred.asset is not None
    assert preferred.asset.name == "MCUDesk_0.10.1_Windows_x64_Setup.exe"

    payload["assets"] = [
        asset
        for asset in payload["assets"]
        if asset["name"] != "MCUDesk_0.10.1_Windows_x64_Setup.exe"
    ]
    legacy = parse_release_metadata(payload, "0.10.0", WINDOWS_PACKAGE_ARCHITECTURE)
    assert legacy.asset is not None
    assert legacy.asset.name == "SerialScope_0.10.1_Windows_x64_Setup.exe"


def test_compatible_asset_names_list_mcudesk_before_legacy() -> None:
    linux = compatible_asset_names("0.14.0", LINUX_PACKAGE_ARCHITECTURE)
    windows = compatible_asset_names("0.14.0", WINDOWS_PACKAGE_ARCHITECTURE)
    assert linux[0].startswith("MCUDesk_")
    assert linux[-1].startswith("serialscope_")
    assert windows[0].startswith("MCUDesk_")
    assert windows[-1].startswith("SerialScope_")
    assert _is_supported_update_asset_name(linux[0])
    assert _is_supported_update_asset_name(linux[-1])
    assert _is_supported_update_asset_name(windows[0])
    assert _is_supported_update_asset_name(windows[-1])
    assert not _is_supported_update_asset_name("../evil.deb")
    assert not _is_supported_update_asset_name("MCUDesk_0.14.0.exe")


def test_missing_compatible_asset_never_falls_back_to_first_asset() -> None:
    payload = _release_payload()
    payload["assets"] = payload["assets"][:2]

    assert parse_release_metadata(payload, "0.10.0").asset is None


def test_non_linux_platform_never_selects_debian_asset(monkeypatch) -> None:
    monkeypatch.setattr("serialscope.updates.model.sys.platform", "win32")
    monkeypatch.setattr("serialscope.updates.model.platform.machine", lambda: "AMD64")

    assert current_linux_package_architecture() is None
    assert parse_release_metadata(_release_payload(), "0.10.0", None).asset is None


@pytest.mark.parametrize("flag", ["draft", "prerelease"])
def test_non_stable_release_is_rejected(flag: str) -> None:
    payload = _release_payload()
    payload[flag] = True
    with pytest.raises(UpdateMetadataError):
        parse_release_metadata(payload, "0.10.0")


def test_sha256_digest_parsing_is_strict() -> None:
    valid = "a" * 64
    assert parse_sha256_digest(f"sha256:{valid}") == (valid, None)
    assert parse_sha256_digest(None)[0] is None
    assert "malformed" in (parse_sha256_digest("sha256:bad")[1] or "").lower()
    assert "unsupported" in (parse_sha256_digest(f"sha512:{valid}")[1] or "").lower()


def test_automatic_check_policy_is_daily_and_optional() -> None:
    now = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)
    assert automatic_check_due(True, None, now)
    assert not automatic_check_due(False, None, now)
    assert not automatic_check_due(True, now - timedelta(hours=23), now)
    assert automatic_check_due(True, now - timedelta(hours=25), now)


class FakeReply(QObject):
    readyRead = Signal()
    downloadProgress = Signal(int, int)
    finished = Signal()

    def __init__(self, status: int = 200) -> None:
        super().__init__()
        self._buffer = b""
        self._status = status
        self._error = QNetworkReply.NetworkError.NoError
        self._error_string = ""
        self.aborted = False

    def supply(self, data: bytes, total: int | None = None) -> None:
        self._buffer += data
        self.readyRead.emit()
        self.downloadProgress.emit(len(data), total if total is not None else len(data))

    def readAll(self) -> bytes:
        data, self._buffer = self._buffer, b""
        return data

    def attribute(self, attribute):
        if attribute == QNetworkRequest.Attribute.HttpStatusCodeAttribute:
            return self._status
        return None

    def error(self):
        return self._error

    def errorString(self) -> str:
        return self._error_string

    def set_error(self, error, message: str) -> None:
        self._error = error
        self._error_string = message

    def abort(self) -> None:
        self.aborted = True
        self._error = QNetworkReply.NetworkError.OperationCanceledError
        self._error_string = "canceled"


class FakeNetworkManager(QObject):
    def __init__(self, reply: FakeReply) -> None:
        super().__init__()
        self.reply = reply
        self.requests = []

    def get(self, request):
        self.requests.append(request)
        return self.reply


def test_update_checker_uses_public_latest_endpoint_and_parses_offline_fixture() -> None:
    QApplication.instance() or QApplication([])
    reply = FakeReply()
    manager = FakeNetworkManager(reply)
    checker = UpdateChecker(manager)
    results = []
    checker.succeeded.connect(results.append)

    assert checker.check()
    assert manager.requests[0].url().toString() == LATEST_RELEASE_API_URL
    reply.supply(json.dumps(_release_payload("0.11.1")).encode())
    reply.finished.emit()

    assert results[0].latest_version == "0.11.1"


def test_update_checker_reports_invalid_json_and_http_failures() -> None:
    QApplication.instance() or QApplication([])
    for reply in (FakeReply(), FakeReply(status=500)):
        manager = FakeNetworkManager(reply)
        checker = UpdateChecker(manager)
        errors = []
        checker.failed.connect(errors.append)
        checker.check()
        if reply._status == 200:
            reply.supply(b"not json")
        reply.finished.emit()
        assert errors

    timeout_reply = FakeReply()
    timeout_reply.set_error(QNetworkReply.NetworkError.TimeoutError, "timed out")
    timeout_checker = UpdateChecker(FakeNetworkManager(timeout_reply))
    timeout_errors = []
    timeout_checker.failed.connect(timeout_errors.append)
    timeout_checker.check()
    timeout_reply.finished.emit()
    assert timeout_errors == ["timed out"]


def test_verified_download_uses_part_file_reports_progress_and_renames(tmp_path: Path) -> None:
    QApplication.instance() or QApplication([])
    data = b"verified package bytes"
    asset = ReleaseAsset(
        "MCUDesk_0.14.0_Linux_amd64.deb",
        "https://example.invalid/update.deb",
        len(data),
        hashlib.sha256(data).hexdigest(),
    )
    reply = FakeReply()
    downloader = UpdateDownloader(FakeNetworkManager(reply), tmp_path)
    completed = []
    progress = []
    downloader.completed.connect(completed.append)
    downloader.progress.connect(lambda received, total: progress.append((received, total)))

    assert downloader.download(asset)
    assert (tmp_path / f"{asset.name}.part").exists()
    reply.supply(data, len(data))
    reply.finished.emit()

    assert completed == [tmp_path / asset.name]
    assert completed[0].read_bytes() == data
    assert not (tmp_path / f"{asset.name}.part").exists()
    assert progress[-1] == (len(data), len(data))


def test_bad_digest_is_rejected_and_partial_file_removed(tmp_path: Path) -> None:
    QApplication.instance() or QApplication([])
    data = b"tampered"
    asset = ReleaseAsset(
        "serialscope_0.11.1_amd64.deb",
        "https://example.invalid/update.deb",
        len(data),
        "0" * 64,
    )
    reply = FakeReply()
    downloader = UpdateDownloader(FakeNetworkManager(reply), tmp_path)
    errors = []
    downloader.failed.connect(errors.append)
    downloader.download(asset)
    reply.supply(data)
    reply.finished.emit()

    assert "verification failed" in errors[0].lower()
    assert not list(tmp_path.iterdir())


def test_download_cancel_and_http_failure_remove_partial_files(tmp_path: Path) -> None:
    QApplication.instance() or QApplication([])
    data = b"partial"
    asset = ReleaseAsset(
        "serialscope_0.11.1_amd64.deb",
        "https://example.invalid/update.deb",
        100,
        hashlib.sha256(data).hexdigest(),
    )
    reply = FakeReply()
    downloader = UpdateDownloader(FakeNetworkManager(reply), tmp_path)
    canceled = []
    downloader.canceled.connect(lambda: canceled.append(True))
    downloader.download(asset)
    reply.supply(data, 100)
    downloader.cancel()
    reply.finished.emit()
    assert canceled == [True]
    assert not list(tmp_path.iterdir())

    failed_reply = FakeReply(status=500)
    failed = UpdateDownloader(FakeNetworkManager(failed_reply), tmp_path)
    errors = []
    failed.failed.connect(errors.append)
    failed.download(asset)
    failed_reply.finished.emit()
    assert errors
    assert not list(tmp_path.iterdir())

    timeout_reply = FakeReply()
    timeout_reply.set_error(QNetworkReply.NetworkError.TimeoutError, "timed out")
    timed_out = UpdateDownloader(FakeNetworkManager(timeout_reply), tmp_path)
    timeout_errors = []
    timed_out.failed.connect(timeout_errors.append)
    timed_out.download(asset)
    timeout_reply.finished.emit()
    assert "timed out" in timeout_errors[0]
    assert not list(tmp_path.iterdir())


def test_download_without_trusted_digest_is_never_started(tmp_path: Path) -> None:
    QApplication.instance() or QApplication([])
    reply = FakeReply()
    manager = FakeNetworkManager(reply)
    downloader = UpdateDownloader(manager, tmp_path)
    errors = []
    downloader.failed.connect(errors.append)

    assert not downloader.download(
        ReleaseAsset(
            "serialscope_0.11.1_amd64.deb",
            "https://example.invalid/update.deb",
            10,
            None,
            "Digest unavailable",
        )
    )
    assert manager.requests == []
    assert errors == ["Digest unavailable"]
