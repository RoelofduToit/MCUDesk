"""Qt-independent Device Profile value models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from serialscope.data import AlarmLimits
from serialscope.parsing.parser_config import (
    ParserConfiguration,
    ParserConfigurationError,
)


LINE_ENDINGS = ("None", "LF", "CR", "CRLF")


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


@dataclass(frozen=True, slots=True)
class SerialSettings:
    """The serial and TX settings currently supported by MCUDesk."""

    baud_rate: int = 115200
    data_bits: int = 8
    parity: str = "none"
    stop_bits: int = 1
    flow_control: str = "none"
    line_ending: str = "LF"

    def __post_init__(self) -> None:
        if self.baud_rate <= 0:
            raise ValueError("Baud rate must be positive.")
        if self.data_bits != 8 or self.parity != "none":
            raise ValueError("Only the current 8-N-1 serial format is supported.")
        if self.stop_bits != 1 or self.flow_control != "none":
            raise ValueError("Only the current 8-N-1 serial format is supported.")
        if self.line_ending not in LINE_ENDINGS:
            raise ValueError("Unsupported TX line ending.")

    def to_dict(self) -> dict[str, object]:
        return {
            "baud_rate": self.baud_rate,
            "data_bits": self.data_bits,
            "parity": self.parity,
            "stop_bits": self.stop_bits,
            "flow_control": self.flow_control,
            "line_ending": self.line_ending,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "SerialSettings":
        return cls(
            baud_rate=int(value.get("baud_rate", 115200)),
            data_bits=int(value.get("data_bits", 8)),
            parity=str(value.get("parity", "none")),
            stop_bits=int(value.get("stop_bits", 1)),
            flow_control=str(value.get("flow_control", "none")),
            line_ending=str(value.get("line_ending", "LF")),
        )


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    """Optional hardware identity and descriptive matching hints."""

    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None
    manufacturer: str | None = None
    product: str | None = None
    location: str | None = None
    hwid: str | None = None

    def __post_init__(self) -> None:
        for name in ("serial_number", "manufacturer", "product", "location", "hwid"):
            object.__setattr__(self, name, _optional_text(getattr(self, name)))

    def to_dict(self) -> dict[str, object]:
        values = {
            "vid": self.vid,
            "pid": self.pid,
            "serial_number": self.serial_number,
            "manufacturer": self.manufacturer,
            "product": self.product,
            "location": self.location,
            "hwid": self.hwid,
        }
        return {key: value for key, value in values.items() if value is not None}

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "DeviceIdentity":
        return cls(
            vid=int(value["vid"]) if value.get("vid") is not None else None,
            pid=int(value["pid"]) if value.get("pid") is not None else None,
            serial_number=_optional_text(value.get("serial_number")),
            manufacturer=_optional_text(value.get("manufacturer")),
            product=_optional_text(value.get("product")),
            location=_optional_text(value.get("location")),
            hwid=_optional_text(value.get("hwid")),
        )


def _normalize_channels(
    channels: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    normalized: dict[str, dict[str, object]] = {}
    for raw_name, raw_values in channels.items():
        name = str(raw_name).strip()
        if not name or not isinstance(raw_values, Mapping):
            continue
        values: dict[str, object] = {
            "alias": str(raw_values.get("alias", "")).strip(),
            "unit": str(raw_values.get("unit", "")).strip(),
        }
        alarms = AlarmLimits.from_mapping(raw_values.get("alarms"))
        if alarms.is_configured:
            values["alarms"] = alarms.to_dict()
        normalized[name] = values
    return normalized


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    """One persistent configuration for one runtime device source."""

    profile_id: str
    name: str
    serial: SerialSettings = SerialSettings()
    parser: str = "auto"
    device_identity: DeviceIdentity = DeviceIdentity()
    last_port: str | None = None
    channels: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    parser_config: ParserConfiguration = field(default_factory=ParserConfiguration)

    def __post_init__(self) -> None:
        profile_id = self.profile_id.strip()
        name = self.name.strip()
        if not profile_id:
            raise ValueError("Profile ID must not be empty.")
        if not name:
            raise ValueError("Profile name must not be empty.")
        try:
            parser_config = self.parser_config
            if not isinstance(parser_config, ParserConfiguration):
                parser_config = ParserConfiguration.from_mapping(
                    parser_config,
                    default_mode=str(self.parser or "auto"),
                )
            elif parser_config.is_default and self.parser != "auto":
                parser_config = ParserConfiguration(mode=str(self.parser))
        except ParserConfigurationError as error:
            raise ValueError(str(error)) from error
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "parser_config", parser_config)
        object.__setattr__(self, "parser", parser_config.mode)
        object.__setattr__(self, "last_port", _optional_text(self.last_port))
        object.__setattr__(self, "channels", _normalize_channels(self.channels))

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "serial": self.serial.to_dict(),
            "parser": self.parser,
            "parser_config": self.parser_config.to_dict(),
            "device_identity": self.device_identity.to_dict(),
            "last_port": self.last_port,
            "channels": self.channels,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "DeviceProfile":
        serial = value.get("serial", {})
        identity = value.get("device_identity", {})
        channels = value.get("channels", {})
        parser_config = value.get("parser_config")
        if not isinstance(serial, Mapping) or not isinstance(identity, Mapping):
            raise ValueError("Profile configuration must contain JSON objects.")
        if not isinstance(channels, Mapping):
            raise ValueError("Profile channels must contain a JSON object.")
        if parser_config is not None and not isinstance(parser_config, Mapping):
            raise ValueError("Parser configuration must contain a JSON object.")
        return cls(
            profile_id=str(value.get("profile_id", "")),
            name=str(value.get("name", "")),
            serial=SerialSettings.from_mapping(serial),
            parser=str(value.get("parser", "auto")),
            device_identity=DeviceIdentity.from_mapping(identity),
            last_port=_optional_text(value.get("last_port")),
            channels=channels,
            parser_config=ParserConfiguration.from_mapping(
                parser_config,
                default_mode=str(value.get("parser", "auto")),
            ),
        )
