"""Serial-device discovery interfaces."""

from serialscope.serial.port_scanner import (
    SerialPortInfo,
    discover_recommended_serial_ports,
    discover_serial_ports,
    is_likely_useful_port,
    recommended_serial_ports,
)

__all__ = [
    "SerialPortInfo",
    "discover_recommended_serial_ports",
    "discover_serial_ports",
    "is_likely_useful_port",
    "recommended_serial_ports",
]
