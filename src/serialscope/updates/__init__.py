"""Application update checking, downloading, and policy."""

from serialscope.updates.checker import UpdateChecker
from serialscope.updates.downloader import UpdateDownloader
from serialscope.updates.model import (
    AUTOMATIC_CHECK_INTERVAL,
    GITHUB_OWNER,
    GITHUB_REPOSITORY,
    LATEST_RELEASE_API_URL,
    LINUX_PACKAGE_ARCHITECTURE,
    REPOSITORY_URL,
    ReleaseAsset,
    UpdateInfo,
    UpdateMetadataError,
    automatic_check_due,
    compatible_asset_names,
    current_linux_package_architecture,
    current_update_architecture,
    is_update_available,
    normalize_version,
    parse_release_metadata,
    parse_sha256_digest,
)

__all__ = [
    "AUTOMATIC_CHECK_INTERVAL",
    "GITHUB_OWNER",
    "GITHUB_REPOSITORY",
    "LATEST_RELEASE_API_URL",
    "LINUX_PACKAGE_ARCHITECTURE",
    "REPOSITORY_URL",
    "ReleaseAsset",
    "UpdateChecker",
    "UpdateDownloader",
    "UpdateInfo",
    "UpdateMetadataError",
    "automatic_check_due",
    "compatible_asset_names",
    "current_linux_package_architecture",
    "current_update_architecture",
    "is_update_available",
    "normalize_version",
    "parse_release_metadata",
    "parse_sha256_digest",
]
