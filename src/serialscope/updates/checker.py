"""Asynchronous stable-release checks through QtNetwork."""

import json

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from serialscope import PRODUCT_NAME, __version__
from serialscope.updates.model import (
    LATEST_RELEASE_API_URL,
    UpdateMetadataError,
    current_update_architecture,
    parse_release_metadata,
)


class UpdateChecker(QObject):
    """Fetch and validate the latest public GitHub release without blocking Qt."""

    succeeded = Signal(object)
    failed = Signal(str)
    checking_changed = Signal(bool)

    def __init__(
        self,
        network_manager: QNetworkAccessManager | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._network_manager = network_manager or QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None
        self._canceling = False

    @property
    def is_checking(self) -> bool:
        return self._reply is not None

    def check(self) -> bool:
        """Start one latest-release request; return false if one is already active."""
        if self._reply is not None:
            return False
        request = QNetworkRequest(QUrl(LATEST_RELEASE_API_URL))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"X-GitHub-Api-Version", b"2022-11-28")
        request.setRawHeader(b"User-Agent", f"{PRODUCT_NAME}/{__version__}".encode())
        request.setTransferTimeout(15_000)
        self._canceling = False
        self._reply = self._network_manager.get(request)
        self._reply.finished.connect(self._finished)
        self.checking_changed.emit(True)
        return True

    def cancel(self) -> None:
        """Abort an outstanding request without reporting an error to the user."""
        if self._reply is not None:
            self._canceling = True
            self._reply.abort()

    def _finished(self) -> None:
        reply = self._reply
        if reply is None:
            return
        self._reply = None
        self.checking_changed.emit(False)
        try:
            if self._canceling:
                return
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if reply.error() != QNetworkReply.NetworkError.NoError:
                if status == 403:
                    raise UpdateMetadataError(
                        "GitHub's anonymous API rate limit was reached. Try again later."
                    )
                raise UpdateMetadataError(reply.errorString() or "Network request failed.")
            if status != 200:
                raise UpdateMetadataError(f"GitHub returned HTTP {status or 'unknown'}.")
            try:
                payload = json.loads(bytes(reply.readAll()))
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise UpdateMetadataError("GitHub returned invalid JSON.") from error
            self.succeeded.emit(
                parse_release_metadata(
                    payload,
                    __version__,
                    current_update_architecture(),
                )
            )
        except UpdateMetadataError as error:
            self.failed.emit(str(error))
        finally:
            reply.deleteLater()
            self._canceling = False
