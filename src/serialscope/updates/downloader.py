"""Asynchronous, cancellable, SHA-256-verified update downloads."""

import hashlib
import hmac
import os
from pathlib import Path

from PySide6.QtCore import QObject, QStandardPaths, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from serialscope import PRODUCT_NAME, __version__
from serialscope.updates.model import ReleaseAsset


_LINUX_PACKAGE_SUFFIXES = ("_Linux_amd64.deb", "_amd64.deb")
_WINDOWS_PACKAGE_SUFFIX = "_Windows_x64_Setup.exe"


def _is_supported_update_asset_name(name: str) -> bool:
    """Accept MCUDesk and legacy SerialScope package names, never path components."""
    if Path(name).name != name:
        return False
    return name.endswith(_LINUX_PACKAGE_SUFFIXES) or name.endswith(
        _WINDOWS_PACKAGE_SUFFIX
    )


class UpdateDownloader(QObject):
    """Own one package transfer and publish only a fully verified installer."""

    progress = Signal(int, int)
    completed = Signal(object)
    failed = Signal(str)
    canceled = Signal()
    active_changed = Signal(bool)

    def __init__(
        self,
        network_manager: QNetworkAccessManager | None = None,
        cache_directory: Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._network_manager = network_manager or QNetworkAccessManager(self)
        cache_location = QStandardPaths.writableLocation(QStandardPaths.CacheLocation)
        if not cache_location:
            cache_location = str(
                Path(QStandardPaths.writableLocation(QStandardPaths.TempLocation))
                / "SerialScope"  # keep historical cache identity under STORAGE_APP_NAME
            )
        default_cache = Path(cache_location)
        self._cache_directory = cache_directory or default_cache / "updates"
        self._reply: QNetworkReply | None = None
        self._asset: ReleaseAsset | None = None
        self._file = None
        self._part_path: Path | None = None
        self._final_path: Path | None = None
        self._hasher = hashlib.sha256()
        self._received = 0
        self._canceling = False
        self._write_error: str | None = None

    @property
    def is_downloading(self) -> bool:
        return self._reply is not None

    @property
    def cache_directory(self) -> Path:
        return self._cache_directory

    def download(self, asset: ReleaseAsset) -> bool:
        """Start downloading a compatible asset that has trusted SHA-256 metadata."""
        if self._reply is not None:
            return False
        if not asset.is_verifiable:
            self.failed.emit(asset.verification_error or "SHA-256 verification unavailable.")
            return False
        if not _is_supported_update_asset_name(asset.name):
            self.failed.emit("The selected update package name is unsafe or incompatible.")
            return False

        try:
            self._cache_directory.mkdir(parents=True, exist_ok=True)
            self._final_path = self._cache_directory / asset.name
            self._part_path = self._cache_directory / f"{asset.name}.part"
            self._part_path.unlink(missing_ok=True)
            self._file = self._part_path.open("wb")
        except OSError as error:
            self._cleanup_partial()
            self.failed.emit(f"Unable to create the update download: {error}")
            return False

        self._asset = asset
        self._hasher = hashlib.sha256()
        self._received = 0
        self._canceling = False
        self._write_error = None
        request = QNetworkRequest(QUrl(asset.url))
        request.setRawHeader(b"User-Agent", f"{PRODUCT_NAME}/{__version__}".encode())
        request.setTransferTimeout(30_000)
        self._reply = self._network_manager.get(request)
        self._reply.readyRead.connect(self._read_available)
        self._reply.downloadProgress.connect(self.progress.emit)
        self._reply.finished.connect(self._finished)
        self.active_changed.emit(True)
        return True

    def cancel(self) -> None:
        """Abort the transfer and ensure its `.part` file is never installable."""
        if self._reply is not None:
            self._canceling = True
            self._reply.abort()
            self._cleanup_partial()

    def _read_available(self) -> None:
        if self._reply is None or self._file is None or self._write_error:
            return
        data = bytes(self._reply.readAll())
        if not data:
            return
        try:
            written = self._file.write(data)
            if written != len(data):
                raise OSError("incomplete file write")
            self._hasher.update(data)
            self._received += len(data)
        except OSError as error:
            self._write_error = str(error)
            self._reply.abort()

    def _finished(self) -> None:
        reply = self._reply
        asset = self._asset
        if reply is None or asset is None:
            return
        self._read_available()
        self._reply = None
        self.active_changed.emit(False)
        try:
            if self._file is not None:
                self._file.flush()
                os.fsync(self._file.fileno())
                self._file.close()
                self._file = None
            if self._canceling:
                self._cleanup_partial()
                self.canceled.emit()
                return
            if self._write_error:
                raise OSError(self._write_error)
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if reply.error() != QNetworkReply.NetworkError.NoError or status != 200:
                raise OSError(reply.errorString() or f"HTTP {status or 'unknown'}")
            if asset.size and self._received != asset.size:
                raise OSError(
                    f"Incomplete download: received {self._received} of {asset.size} bytes."
                )
            actual_digest = self._hasher.hexdigest()
            if not hmac.compare_digest(actual_digest, asset.sha256_digest or ""):
                self._cleanup_partial()
                self.failed.emit(
                    "Update verification failed. The downloaded package does not "
                    "match the release checksum and will not be installed."
                )
                return
            assert self._part_path is not None and self._final_path is not None
            self._final_path.unlink(missing_ok=True)
            self._part_path.replace(self._final_path)
            self.completed.emit(self._final_path)
        except OSError as error:
            self._cleanup_partial()
            self.failed.emit(f"Unable to download the update: {error}")
        finally:
            reply.deleteLater()
            self._asset = None
            self._canceling = False
            self._write_error = None

    def _cleanup_partial(self) -> None:
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None
        if self._part_path is not None:
            try:
                self._part_path.unlink(missing_ok=True)
            except OSError:
                pass
