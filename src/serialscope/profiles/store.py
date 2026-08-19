"""Versioned, atomic persistence for user Device Profiles."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import json
from pathlib import Path
import uuid

from PySide6.QtCore import QStandardPaths

from serialscope.parsing.parser_config import ParserConfiguration
from serialscope.profiles.model import (
    DeviceIdentity,
    DeviceProfile,
    SerialSettings,
)
from serialscope.storage import atomic_write_json


PROFILE_SCHEMA_VERSION = 1


class ProfileStoreError(RuntimeError):
    """A concise profile persistence or validation failure."""


def default_profile_path() -> Path:
    root = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    return Path(root) / "device_profiles.json"


class ProfileStore:
    """Own profile CRUD and one versioned JSON document."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_profile_path()
        self._profiles: dict[str, DeviceProfile] = {}
        self.load_error: str | None = None
        self._load()

    @property
    def profiles(self) -> tuple[DeviceProfile, ...]:
        return tuple(sorted(self._profiles.values(), key=lambda item: item.name.casefold()))

    def get(self, profile_id: str) -> DeviceProfile:
        try:
            return self._profiles[profile_id]
        except KeyError as error:
            raise ProfileStoreError("The selected Device Profile no longer exists.") from error

    def create(
        self,
        name: str,
        *,
        serial: SerialSettings,
        parser: str = "auto",
        device_identity: DeviceIdentity = DeviceIdentity(),
        last_port: str | None = None,
        channels: Mapping[str, Mapping[str, object]] | None = None,
        profile_id: str | None = None,
        parser_config: ParserConfiguration | Mapping[str, object] | None = None,
    ) -> DeviceProfile:
        self._ensure_writable()
        try:
            profile = DeviceProfile(
                profile_id or uuid.uuid4().hex,
                name,
                serial,
                parser,
                device_identity,
                last_port,
                channels or {},
                parser_config=parser_config
                if isinstance(parser_config, ParserConfiguration)
                else ParserConfiguration.from_mapping(
                    parser_config, default_mode=parser
                ),
            )
        except (TypeError, ValueError) as error:
            raise ProfileStoreError(str(error)) from error
        self._ensure_unique_name(profile.name)
        if profile.profile_id in self._profiles:
            raise ProfileStoreError("A Device Profile with that ID already exists.")
        self._profiles[profile.profile_id] = profile
        self._save_or_rollback(lambda: self._profiles.pop(profile.profile_id))
        return profile

    def update(
        self,
        profile_id: str,
        *,
        serial: SerialSettings,
        parser: str,
        device_identity: DeviceIdentity,
        last_port: str | None,
        channels: Mapping[str, Mapping[str, object]],
        parser_config: ParserConfiguration | Mapping[str, object] | None = None,
    ) -> DeviceProfile:
        self._ensure_writable()
        previous = self.get(profile_id)
        try:
            resolved_config = (
                parser_config
                if isinstance(parser_config, ParserConfiguration)
                else ParserConfiguration.from_mapping(
                    parser_config, default_mode=parser
                )
                if parser_config is not None
                else ParserConfiguration(mode=parser)
            )
            updated = replace(
                previous,
                serial=serial,
                parser=parser,
                device_identity=device_identity,
                last_port=last_port,
                channels=channels,
                parser_config=resolved_config,
            )
        except (TypeError, ValueError) as error:
            raise ProfileStoreError(str(error)) from error
        self._profiles[profile_id] = updated
        self._save_or_rollback(lambda: self._profiles.__setitem__(profile_id, previous))
        return updated

    def rename(self, profile_id: str, name: str) -> DeviceProfile:
        self._ensure_writable()
        previous = self.get(profile_id)
        trimmed = name.strip()
        self._ensure_unique_name(trimmed, excluding=profile_id)
        updated = replace(previous, name=trimmed)
        self._profiles[profile_id] = updated
        self._save_or_rollback(lambda: self._profiles.__setitem__(profile_id, previous))
        return updated

    def delete(self, profile_id: str) -> None:
        self._ensure_writable()
        previous = self.get(profile_id)
        del self._profiles[profile_id]
        self._save_or_rollback(lambda: self._profiles.__setitem__(profile_id, previous))

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("root must be an object")
            if value.get("schema_version") != PROFILE_SCHEMA_VERSION:
                raise ValueError("unsupported profile schema version")
            raw_profiles = value.get("profiles", [])
            if not isinstance(raw_profiles, list):
                raise ValueError("profiles must be a list")
            profiles = [
                DeviceProfile.from_mapping(item)
                for item in raw_profiles
                if isinstance(item, Mapping)
            ]
            if len(profiles) != len(raw_profiles):
                raise ValueError("profile entries must be objects")
            identifiers = {item.profile_id for item in profiles}
            names = {item.name.casefold() for item in profiles}
            if len(identifiers) != len(profiles) or len(names) != len(profiles):
                raise ValueError("profile IDs and names must be unique")
            self._profiles = {item.profile_id: item for item in profiles}
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            self._profiles = {}
            self.load_error = (
                f"Device Profiles could not be loaded from {self.path}: {error}. "
                "The original file was left unchanged."
            )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            atomic_write_json(
                self.path,
                {
                    "schema_version": PROFILE_SCHEMA_VERSION,
                    "profiles": [profile.to_dict() for profile in self.profiles],
                },
            )
        except (OSError, TypeError, ValueError) as error:
            raise ProfileStoreError(f"Could not save Device Profiles: {error}") from error

    def _save_or_rollback(self, rollback) -> None:
        try:
            self._save()
        except ProfileStoreError:
            rollback()
            raise

    def _ensure_writable(self) -> None:
        if self.load_error is not None:
            raise ProfileStoreError(
                "Device Profiles are unavailable because the profile file is invalid."
            )

    def _ensure_unique_name(self, name: str, excluding: str | None = None) -> None:
        if not name.strip():
            raise ProfileStoreError("Profile name must not be empty.")
        if any(
            item.profile_id != excluding and item.name.casefold() == name.casefold()
            for item in self._profiles.values()
        ):
            raise ProfileStoreError("A Device Profile with that name already exists.")
