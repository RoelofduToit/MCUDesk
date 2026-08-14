from types import SimpleNamespace

from serialscope.serial import port_scanner


def _port(device: str, **metadata: object) -> SimpleNamespace:
    values = {
        "device": device,
        "description": None,
        "manufacturer": None,
        "vid": None,
        "pid": None,
        "serial_number": None,
        "product": None,
        "location": None,
        "hwid": None,
    }
    values.update(metadata)
    return SimpleNamespace(**values)


def test_discover_serial_ports_when_none_are_available(monkeypatch) -> None:
    monkeypatch.setattr(port_scanner.list_ports, "comports", lambda: [])

    assert port_scanner.discover_serial_ports() == []


def test_discover_serial_ports_returns_one_port(monkeypatch) -> None:
    monkeypatch.setattr(
        port_scanner.list_ports,
        "comports",
        lambda: [_port("/dev/ttyACM0", description="Arduino Uno")],
    )

    ports = port_scanner.discover_serial_ports()

    assert len(ports) == 1
    assert ports[0].device == "/dev/ttyACM0"
    assert ports[0].display_name == "/dev/ttyACM0 — Arduino Uno"


def test_discover_serial_ports_returns_multiple_ports_sorted(monkeypatch) -> None:
    monkeypatch.setattr(
        port_scanner.list_ports,
        "comports",
        lambda: [_port("COM10"), _port("COM3"), _port("COM4")],
    )

    ports = port_scanner.discover_serial_ports()

    assert [port.device for port in ports] == ["COM10", "COM3", "COM4"]


def test_discover_serial_ports_preserves_available_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        port_scanner.list_ports,
        "comports",
        lambda: [
            _port(
                "COM4",
                description="USB Serial Device",
                manufacturer="Example Devices",
                vid=0x2341,
                pid=0x0043,
                serial_number="ABC123",
                product="USB Adapter",
                location="1-2.3",
                hwid="USB VID:PID=2341:0043",
            )
        ],
    )

    port = port_scanner.discover_serial_ports()[0]

    assert port.description == "USB Serial Device"
    assert port.manufacturer == "Example Devices"
    assert port.vid == 0x2341
    assert port.pid == 0x0043
    assert port.serial_number == "ABC123"
    assert port.product == "USB Adapter"
    assert port.location == "1-2.3"
    assert port.hwid == "USB VID:PID=2341:0043"


def test_anonymous_ttys_port_is_hidden_but_remains_discovered(monkeypatch) -> None:
    monkeypatch.setattr(
        port_scanner.list_ports,
        "comports",
        lambda: [_port("/dev/ttyS0")],
    )

    all_ports = port_scanner.discover_serial_ports()
    recommended = port_scanner.recommended_serial_ports(all_ports, platform="linux")

    assert [port.device for port in all_ports] == ["/dev/ttyS0"]
    assert recommended == []


def test_ttyacm_port_is_recommended_on_linux() -> None:
    port = port_scanner.SerialPortInfo("/dev/ttyACM0")

    assert port_scanner.is_likely_useful_port(port, platform="linux")


def test_ttyusb_port_is_recommended_on_linux() -> None:
    port = port_scanner.SerialPortInfo("/dev/ttyUSB0")

    assert port_scanner.is_likely_useful_port(port, platform="linux")


def test_ttys_port_with_hardware_metadata_is_recommended_on_linux() -> None:
    port = port_scanner.SerialPortInfo(
        "/dev/ttyS4",
        manufacturer="Example Devices",
    )

    assert port_scanner.is_likely_useful_port(port, platform="linux")


def test_windows_com_ports_are_not_filtered() -> None:
    ports = [
        port_scanner.SerialPortInfo("COM3"),
        port_scanner.SerialPortInfo("COM4"),
    ]

    assert port_scanner.recommended_serial_ports(ports, platform="win32") == ports
