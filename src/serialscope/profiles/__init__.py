"""Persistent per-device configuration profiles."""

from serialscope.profiles.matching import (
    DeviceMatch,
    DeviceMatchStatus,
    match_device_profile,
)
from serialscope.profiles.model import (
    DeviceIdentity,
    DeviceProfile,
    SerialSettings,
)
from serialscope.profiles.store import ProfileStore, ProfileStoreError

__all__ = [
    "DeviceIdentity",
    "DeviceMatch",
    "DeviceMatchStatus",
    "DeviceProfile",
    "ProfileStore",
    "ProfileStoreError",
    "SerialSettings",
    "match_device_profile",
]
