import pytest

from serialscope.modbus.model import (
    ModbusConnectionSettings,
    ModbusRegister,
    ModbusRtuConfiguration,
    ModbusRtuConfigurationError,
)
from serialscope.profiles import DeviceProfile, ProfileStore, SerialSettings


def test_modbus_defaults_and_round_trip() -> None:
    configuration = ModbusRtuConfiguration(
        registers=(
            ModbusRegister(name="Motor Speed", address=0, unit="rpm"),
            ModbusRegister(
                name="Current",
                address=1,
                data_type="uint16",
                scale=0.1,
                unit="A",
            ),
        )
    )
    restored = ModbusRtuConfiguration.from_mapping(configuration.to_dict())
    assert restored.connection.slave_id == 1
    assert restored.connection.parity == "even"
    assert restored.connection.baud_rate == 9600
    assert restored.interval_ms == 500
    assert restored.registers[1].scale == pytest.approx(0.1)
    assert restored.enabled_registers[0].name == "Motor Speed"


@pytest.mark.parametrize("slave_id", [0, 248, -1])
def test_invalid_slave_ids_are_rejected(slave_id: int) -> None:
    with pytest.raises(ModbusRtuConfigurationError, match="Slave ID"):
        ModbusConnectionSettings(slave_id=slave_id)


@pytest.mark.parametrize("interval", [0, 49, 60_001])
def test_invalid_poll_interval_is_rejected(interval: int) -> None:
    with pytest.raises(ModbusRtuConfigurationError, match="Poll interval"):
        ModbusRtuConfiguration(interval_ms=interval)


def test_register_validation_and_overlap() -> None:
    with pytest.raises(ModbusRtuConfigurationError, match="empty"):
        ModbusRegister(name="  ")
    with pytest.raises(ModbusRtuConfigurationError, match="address"):
        ModbusRegister(name="X", address=-1)
    with pytest.raises(ModbusRtuConfigurationError, match="overlap"):
        ModbusRtuConfiguration(
            registers=(
                ModbusRegister(name="A", address=10, data_type="float32"),
                ModbusRegister(name="B", address=11),
            )
        )
    with pytest.raises(ModbusRtuConfigurationError, match="Duplicate"):
        ModbusRtuConfiguration(
            registers=(
                ModbusRegister(name="Speed"),
                ModbusRegister(name="speed", address=2),
            )
        )


def test_disabled_registers_do_not_overlap_enabled_ones() -> None:
    configuration = ModbusRtuConfiguration(
        registers=(
            ModbusRegister(name="Live", address=10, data_type="float32"),
            ModbusRegister(name="Unused", address=11, enabled=False),
        )
    )
    assert [item.name for item in configuration.enabled_registers] == ["Live"]


def test_old_device_profiles_default_to_serial_stream(tmp_path) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    profile = store.create(
        "Reactor Pico",
        serial=SerialSettings(baud_rate=115200),
        last_port="/dev/ttyACM0",
    )
    assert profile.protocol == "serial_stream"
    assert profile.modbus is None
    document = profile.to_dict()
    document.pop("protocol", None)
    restored = DeviceProfile.from_mapping(document)
    assert restored.protocol == "serial_stream"
    assert ProfileStore(tmp_path / "profiles.json").get(profile.profile_id).name == "Reactor Pico"


def test_modbus_profile_persists_without_breaking_serial_profiles(tmp_path) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    serial_profile = store.create("Arduino", serial=SerialSettings())
    configuration = ModbusRtuConfiguration(
        connection=ModbusConnectionSettings(baud_rate=19200, parity="none", slave_id=3),
        interval_ms=250,
        registers=(ModbusRegister(name="Temp", kind="input", address=10, unit="°C"),),
    )
    modbus_profile = store.create(
        "VSD",
        serial=SerialSettings(baud_rate=19200),
        protocol="modbus_rtu",
        modbus=configuration,
        last_port="/dev/ttyUSB0",
    )
    reloaded = ProfileStore(tmp_path / "profiles.json")
    assert reloaded.get(serial_profile.profile_id).protocol == "serial_stream"
    restored = reloaded.get(modbus_profile.profile_id)
    assert restored.protocol == "modbus_rtu"
    assert restored.modbus is not None
    assert restored.modbus.connection.slave_id == 3
    assert restored.modbus.registers[0].kind == "input"
