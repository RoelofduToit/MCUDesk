"""Cross-platform serial-port discovery."""

from collections.abc import Iterable
from dataclasses import dataclass
import sys

from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo


@dataclass(frozen=True, slots=True)
class SerialPortInfo:
    """Structured metadata describing an available serial port."""

    device: str
    description: str | None = None
    manufacturer: str | None = None
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None
    product: str | None = None
    location: str | None = None
    hwid: str | None = None

    @property
    def display_name(self) -> str:
        """Return a concise label while preserving ``device`` separately."""
        if self.description and self.description not in {self.device, "n/a"}:
            return f"{self.device} — {self.description}"
        return self.device


def discover_serial_ports() -> list[SerialPortInfo]:
    """Return available serial ports in deterministic device-name order."""
    ports = (_to_port_info(port) for port in list_ports.comports())
    return sorted(ports, key=lambda port: port.device.casefold())


def discover_recommended_serial_ports() -> list[SerialPortInfo]:
    """Collect all ports and return those recommended for the normal UI."""
    all_ports = discover_serial_ports()
    return recommended_serial_ports(all_ports)


def recommended_serial_ports(
    ports: Iterable[SerialPortInfo],
    platform: str | None = None,
) -> list[SerialPortInfo]:
    """Return likely useful ports, applying filtering only on Linux."""
    current_platform = platform or sys.platform
    return [
        port
        for port in ports
        if is_likely_useful_port(port, platform=current_platform)
    ]


def is_likely_useful_port(
    port: SerialPortInfo,
    platform: str | None = None,
) -> bool:
    """Classify whether a port should appear in the normal dropdown."""
    current_platform = platform or sys.platform
    if not current_platform.startswith("linux"):
        return True

    has_hardware_metadata = any(
        (
            port.vid is not None,
            port.pid is not None,
            bool(port.manufacturer),
            bool(port.serial_number),
        )
    )
    useful_linux_prefixes = (
        "/dev/ttyUSB",
        "/dev/ttyACM",
        "/dev/ttyAMA",
        "/dev/rfcomm",
    )
    return has_hardware_metadata or port.device.startswith(useful_linux_prefixes)


def _to_port_info(port: ListPortInfo) -> SerialPortInfo:
    return SerialPortInfo(
        device=port.device,
        description=port.description,
        manufacturer=port.manufacturer,
        vid=port.vid,
        pid=port.pid,
        serial_number=port.serial_number,
        product=getattr(port, "product", None),
        location=getattr(port, "location", None),
        hwid=getattr(port, "hwid", None),
    )
