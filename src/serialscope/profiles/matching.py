"""Deterministic Device Profile matching against discovered serial ports."""

from dataclasses import dataclass
from enum import Enum

from serialscope.profiles.model import DeviceProfile
from serialscope.serial.port_scanner import SerialPortInfo


class DeviceMatchStatus(Enum):
    EXACT = "exact"
    LIKELY = "likely"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class DeviceMatch:
    status: DeviceMatchStatus
    candidates: tuple[SerialPortInfo, ...] = ()

    @property
    def port(self) -> SerialPortInfo | None:
        return self.candidates[0] if len(self.candidates) == 1 else None


def _same(value: str | None, other: str | None) -> bool:
    return bool(value and other and value.casefold() == other.casefold())


def match_device_profile(
    profile: DeviceProfile, ports: tuple[SerialPortInfo, ...] | list[SerialPortInfo]
) -> DeviceMatch:
    """Match stable USB identity first and use a remembered port only as fallback."""
    identity = profile.device_identity
    if identity.serial_number:
        serial_candidates = tuple(
            port
            for port in ports
            if _same(identity.serial_number, port.serial_number)
        )
        if len(serial_candidates) == 1:
            return DeviceMatch(DeviceMatchStatus.EXACT, serial_candidates)
        candidates = tuple(
            port
            for port in serial_candidates
            if (identity.vid is None or port.vid == identity.vid)
            and (identity.pid is None or port.pid == identity.pid)
        )
        if len(candidates) == 1:
            return DeviceMatch(DeviceMatchStatus.EXACT, candidates)
        if len(candidates) > 1:
            return DeviceMatch(DeviceMatchStatus.AMBIGUOUS, candidates)
        return DeviceMatch(DeviceMatchStatus.NOT_FOUND)

    if identity.vid is not None and identity.pid is not None:
        candidates = tuple(
            port
            for port in ports
            if port.vid == identity.vid
            and port.pid == identity.pid
            and (
                not identity.product
                or not port.product
                or _same(identity.product, port.product)
            )
            and (
                not identity.manufacturer
                or not port.manufacturer
                or _same(identity.manufacturer, port.manufacturer)
            )
        )
        if len(candidates) == 1:
            return DeviceMatch(DeviceMatchStatus.LIKELY, candidates)
        if len(candidates) > 1:
            return DeviceMatch(DeviceMatchStatus.AMBIGUOUS, candidates)

    fallback = tuple(port for port in ports if port.device == profile.last_port)
    if len(fallback) == 1:
        return DeviceMatch(DeviceMatchStatus.LIKELY, fallback)
    return DeviceMatch(DeviceMatchStatus.NOT_FOUND)
