"""Pure release parsing and update policy for GitHub Releases."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import platform
import re
import sys

from packaging.version import InvalidVersion, Version


GITHUB_OWNER = "RoelofduToit"
GITHUB_REPOSITORY = "MCUDesk"
REPOSITORY_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPOSITORY}"
LATEST_RELEASE_API_URL = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/releases/latest"
)
LINUX_PACKAGE_ARCHITECTURE = "amd64"
WINDOWS_PACKAGE_ARCHITECTURE = "win64"
AUTOMATIC_CHECK_INTERVAL = timedelta(hours=24)
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


class UpdateMetadataError(ValueError):
    """Raised when release metadata is invalid or unsafe to use."""


@dataclass(frozen=True)
class ReleaseAsset:
    """A deterministic platform package selected from a GitHub release."""

    name: str
    url: str
    size: int
    sha256_digest: str | None
    verification_error: str | None = None

    @property
    def is_verifiable(self) -> bool:
        return self.sha256_digest is not None


@dataclass(frozen=True)
class UpdateInfo:
    """Normalized stable-release information consumed by the UI."""

    installed_version: str
    latest_version: str
    release_name: str
    release_notes: str
    release_url: str
    asset: ReleaseAsset | None

    @property
    def update_available(self) -> bool:
        return Version(self.latest_version) > Version(self.installed_version)


def normalize_version(value: str) -> Version:
    """Normalize a GitHub tag and return a comparable PEP 440 version."""
    normalized = value.strip()
    if normalized[:1].lower() == "v":
        normalized = normalized[1:]
    try:
        return Version(normalized)
    except InvalidVersion as error:
        raise UpdateMetadataError(f"Invalid release version: {value!r}") from error


def is_update_available(installed_version: str, latest_tag: str) -> bool:
    """Return true only when the stable release is newer than the application."""
    return normalize_version(latest_tag) > normalize_version(installed_version)


def parse_sha256_digest(value: object) -> tuple[str | None, str | None]:
    """Parse GitHub's ``sha256:<hex>`` digest without accepting weaker data."""
    if value is None or value == "":
        return None, "A trusted SHA-256 digest is unavailable for this asset."
    if not isinstance(value, str) or ":" not in value:
        return None, "The release asset digest is malformed."
    algorithm, digest = value.split(":", 1)
    if algorithm.lower() != "sha256":
        return None, f"Unsupported release digest algorithm: {algorithm or 'unknown'}."
    if not _SHA256_PATTERN.fullmatch(digest):
        return None, "The release SHA-256 digest is malformed."
    return digest.lower(), None


def compatible_asset_names(version: str, architecture: str | None) -> tuple[str, ...]:
    """Return preferred then legacy package names for one platform."""
    if architecture == LINUX_PACKAGE_ARCHITECTURE:
        return (
            f"MCUDesk_{version}_Linux_{architecture}.deb",
            f"serialscope_{version}_{architecture}.deb",
        )
    if architecture == WINDOWS_PACKAGE_ARCHITECTURE:
        return (
            f"MCUDesk_{version}_Windows_x64_Setup.exe",
            f"SerialScope_{version}_Windows_x64_Setup.exe",
        )
    return ()


def _compatible_asset(
    assets: object,
    latest_version: str,
    architecture: str | None,
) -> ReleaseAsset | None:
    if architecture is None:
        return None
    if not isinstance(assets, list):
        return None
    by_name: dict[str, dict] = {}
    for raw_asset in assets:
        if isinstance(raw_asset, dict) and isinstance(raw_asset.get("name"), str):
            by_name[raw_asset["name"]] = raw_asset
    for expected_name in compatible_asset_names(latest_version, architecture):
        raw_asset = by_name.get(expected_name)
        if raw_asset is None:
            continue
        url = raw_asset.get("browser_download_url")
        size = raw_asset.get("size", 0)
        if not isinstance(url, str) or not url.startswith("https://"):
            raise UpdateMetadataError("The compatible release asset URL is invalid.")
        if not isinstance(size, int) or size < 0:
            raise UpdateMetadataError("The compatible release asset size is invalid.")
        digest, digest_error = parse_sha256_digest(raw_asset.get("digest"))
        return ReleaseAsset(expected_name, url, size, digest, digest_error)
    return None


def parse_release_metadata(
    payload: object,
    installed_version: str,
    architecture: str | None = LINUX_PACKAGE_ARCHITECTURE,
) -> UpdateInfo:
    """Validate a stable GitHub release response and select its Linux package."""
    if not isinstance(payload, dict):
        raise UpdateMetadataError("GitHub returned malformed release metadata.")
    if payload.get("draft") or payload.get("prerelease"):
        raise UpdateMetadataError("GitHub returned a non-stable release.")

    tag = payload.get("tag_name")
    if not isinstance(tag, str):
        raise UpdateMetadataError("The GitHub release has no valid version tag.")
    latest = str(normalize_version(tag))
    installed = str(normalize_version(installed_version))
    release_url = payload.get("html_url")
    if not isinstance(release_url, str) or not release_url.startswith("https://"):
        raise UpdateMetadataError("The GitHub release URL is invalid.")

    name = payload.get("name")
    notes = payload.get("body")
    return UpdateInfo(
        installed_version=installed,
        latest_version=latest,
        release_name=name if isinstance(name, str) and name else f"MCUDesk {latest}",
        release_notes=notes if isinstance(notes, str) else "",
        release_url=release_url,
        asset=_compatible_asset(payload.get("assets"), latest, architecture),
    )


def current_linux_package_architecture() -> str | None:
    """Return the supported package architecture only on Linux x86-64."""
    machine = platform.machine().lower()
    if sys.platform.startswith("linux") and machine in {"x86_64", "amd64"}:
        return LINUX_PACKAGE_ARCHITECTURE
    return None


def current_update_architecture() -> str | None:
    """Return the updater package selector for this host, if supported."""
    linux = current_linux_package_architecture()
    if linux is not None:
        return linux
    machine = platform.machine().lower()
    if sys.platform.startswith("win") and machine in {"amd64", "x86_64"}:
        return WINDOWS_PACKAGE_ARCHITECTURE
    return None


def automatic_check_due(
    enabled: bool,
    last_check: datetime | None,
    now: datetime | None = None,
) -> bool:
    """Rate-limit automatic checks to no more than approximately once per day."""
    if not enabled:
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if last_check is None:
        return True
    if last_check.tzinfo is None:
        last_check = last_check.replace(tzinfo=timezone.utc)
    return current - last_check >= AUTOMATIC_CHECK_INTERVAL
