import json

import pytest

from serialscope.profiles import (
    DeviceIdentity,
    DeviceMatchStatus,
    ProfileStore,
    ProfileStoreError,
    SerialSettings,
    match_device_profile,
)
from serialscope.serial import SerialPortInfo


def profile_values(**overrides):
    values = {
        "serial": SerialSettings(baud_rate=115200, line_ending="CRLF"),
        "parser": "auto",
        "device_identity": DeviceIdentity(
            vid=0x2E8A,
            pid=0x000A,
            serial_number="PICO-001",
            manufacturer="Raspberry Pi",
            product="Pico",
        ),
        "last_port": "/dev/ttyACM0",
        "channels": {
            "TC1": {
                "alias": "Reactor Temperature",
                "unit": "°C",
                "alarms": {"low": 350, "high": 500},
            }
        },
    }
    values.update(overrides)
    return values


def test_profile_crud_round_trip_preserves_stable_id_and_metadata(tmp_path) -> None:
    path = tmp_path / "device_profiles.json"
    store = ProfileStore(path)
    profile = store.create("  Reactor Pico  ", **profile_values())
    profile_id = profile.profile_id

    reloaded = ProfileStore(path)
    restored = reloaded.get(profile_id)
    assert restored.name == "Reactor Pico"
    assert restored.serial == SerialSettings(baud_rate=115200, line_ending="CRLF")
    assert restored.parser == "auto"
    assert restored.channels["TC1"]["alias"] == "Reactor Temperature"
    assert restored.channels["TC1"]["unit"] == "°C"
    assert restored.channels["TC1"]["alarms"] == {"low": 350.0, "high": 500.0}

    renamed = reloaded.rename(profile_id, "反应器 Pico")
    assert renamed.profile_id == profile_id
    assert ProfileStore(path).get(profile_id).name == "反应器 Pico"
    reloaded.delete(profile_id)
    assert ProfileStore(path).profiles == ()


def test_empty_and_duplicate_profile_names_are_rejected(tmp_path) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    with pytest.raises(ProfileStoreError, match="empty"):
        store.create("   ", **profile_values())
    store.create("Reactor Pico", **profile_values())
    with pytest.raises(ProfileStoreError, match="name already exists"):
        store.create("reactor pico", **profile_values())


def test_store_uses_schema_version_and_tolerates_unknown_fields(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    store = ProfileStore(path)
    profile = store.create("Pico", **profile_values())
    document = json.loads(path.read_text("utf-8"))
    assert document["schema_version"] == 1
    document["future_root"] = True
    document["profiles"][0]["future_profile_field"] = {"value": 1}
    path.write_text(json.dumps(document), encoding="utf-8")
    assert ProfileStore(path).get(profile.profile_id).name == "Pico"


def test_corrupt_store_does_not_crash_or_overwrite_original(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    original = "{broken profile data"
    path.write_text(original, encoding="utf-8")
    store = ProfileStore(path)

    assert store.profiles == ()
    assert store.load_error is not None
    with pytest.raises(ProfileStoreError, match="unavailable"):
        store.create("New", **profile_values())
    assert path.read_text("utf-8") == original


def test_future_schema_is_not_silently_misinterpreted(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    original = json.dumps({"schema_version": 99, "profiles": []})
    path.write_text(original, encoding="utf-8")
    store = ProfileStore(path)
    assert store.profiles == ()
    assert "unsupported profile schema" in (store.load_error or "")
    assert path.read_text("utf-8") == original


def test_atomic_save_failure_rolls_back_in_memory(tmp_path, monkeypatch) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    monkeypatch.setattr(
        "serialscope.profiles.store.atomic_write_json",
        lambda *_args: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(ProfileStoreError, match="disk full"):
        store.create("Pico", **profile_values())
    assert store.profiles == ()


def _profile(store: ProfileStore, **identity_overrides):
    identity_values = {
        "vid": 0x2E8A,
        "pid": 0x000A,
        "serial_number": "PICO-001",
        "manufacturer": "Raspberry Pi",
        "product": "Pico",
    }
    identity_values.update(identity_overrides)
    return store.create(
        "Pico",
        **profile_values(device_identity=DeviceIdentity(**identity_values)),
    )


def test_serial_identity_wins_when_linux_port_changes(tmp_path) -> None:
    profile = _profile(ProfileStore(tmp_path / "profiles.json"))
    port = SerialPortInfo(
        "/dev/ttyACM1", vid=0x2E8A, pid=0x000A, serial_number="PICO-001"
    )
    result = match_device_profile(profile, [port])
    assert result.status is DeviceMatchStatus.EXACT
    assert result.port == port


def test_serial_number_alone_is_an_exact_identity(tmp_path) -> None:
    profile = _profile(ProfileStore(tmp_path / "profiles.json"))
    port = SerialPortInfo("COM7", serial_number="PICO-001")
    assert match_device_profile(profile, [port]).status is DeviceMatchStatus.EXACT


def test_no_serial_number_has_deterministic_likely_and_ambiguous_states(tmp_path) -> None:
    profile = _profile(
        ProfileStore(tmp_path / "profiles.json"), serial_number=None
    )
    first = SerialPortInfo(
        "/dev/ttyUSB0",
        vid=0x2E8A,
        pid=0x000A,
        manufacturer="Raspberry Pi",
        product="Pico",
    )
    second = SerialPortInfo(
        "/dev/ttyUSB1",
        vid=0x2E8A,
        pid=0x000A,
        manufacturer="Raspberry Pi",
        product="Pico",
    )
    assert match_device_profile(profile, [first]).status is DeviceMatchStatus.LIKELY
    result = match_device_profile(profile, [first, second])
    assert result.status is DeviceMatchStatus.AMBIGUOUS
    assert result.port is None


def test_absent_device_remains_a_profile_and_stale_port_does_not_beat_identity(
    tmp_path,
) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    profile = _profile(store)
    wrong = SerialPortInfo(
        "/dev/ttyACM0", vid=0x2E8A, pid=0x000A, serial_number="OTHER"
    )
    result = match_device_profile(profile, [wrong])
    assert result.status is DeviceMatchStatus.NOT_FOUND
    assert store.get(profile.profile_id) == profile


def test_last_port_is_used_only_when_no_stable_identity_exists(tmp_path) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    profile = store.create(
        "Legacy adapter",
        **profile_values(device_identity=DeviceIdentity(), last_port="COM4"),
    )
    port = SerialPortInfo("COM4")
    result = match_device_profile(profile, [port])
    assert result.status is DeviceMatchStatus.LIKELY
    assert result.port == port
