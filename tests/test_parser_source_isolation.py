import json
from pathlib import Path
from unittest.mock import Mock

from serialscope.logging import (
    MultiSourceRecordingSession,
    RecordingSourceConfig,
)
from serialscope.parsing import (
    ChannelUpdate,
    ColumnMapping,
    ParserConfiguration,
)
from serialscope.profiles import DeviceIdentity, ProfileStore, SerialSettings
from serialscope.serial import SerialConnection, SerialSourceManager


class Signal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)

    def emit(self, value) -> None:
        for callback in self.callbacks:
            callback(value)


class Reader:
    def __init__(self, _connection) -> None:
        self.bytes_received = Signal()
        self.failed = Signal()

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def connection(port: str) -> SerialConnection:
    serial_port = Mock(is_open=True, port=port, in_waiting=0)
    return SerialConnection(serial_factory=Mock(return_value=serial_port))


def test_source_a_configuration_does_not_affect_source_b() -> None:
    connections = iter((connection("COM4"), connection("COM5")))
    manager = SerialSourceManager(
        connection_factory=lambda: next(connections), reader_factory=Reader
    )
    left = manager.add_source("Arduino A")
    right = manager.add_source("Arduino B")
    manager.apply_parser_configuration(
        left.source_id,
        ParserConfiguration(
            mode="delimited",
            delimiter="|",
            header_mode="none",
            columns=(
                ColumnMapping(0, "TC1"),
                ColumnMapping(1, "TC2"),
                ColumnMapping(2, "RPM"),
            ),
        ),
    )
    manager.apply_parser_configuration(
        right.source_id,
        ParserConfiguration(
            mode="key_value",
            pair_separator=";",
            name_value_separator=":",
        ),
    )
    updates = []
    manager.structured_update.connect(
        lambda source_id, update: updates.append((source_id, update.channels))
    )
    manager.connect(left.source_id, "COM4", 115200)
    manager.connect(right.source_id, "COM5", 9600)
    left.reader.bytes_received.emit(b"23.4|25.1|1450\n")
    right.reader.bytes_received.emit(b"TEMP:23.4;PRESS:101.3;RPM:1450\n")
    assert updates == [
        (left.source_id, {"TC1": 23.4, "TC2": 25.1, "RPM": 1450}),
        (
            right.source_id,
            {"TEMP": 23.4, "PRESS": 101.3, "RPM": 1450},
        ),
    ]
    assert left.parser.configuration.mode == "delimited"
    assert right.parser.configuration.mode == "key_value"


def test_parser_configuration_does_not_alter_raw_logging(tmp_path: Path) -> None:
    payload = b"23.4|25.1|101.3|1450\n"
    session = MultiSourceRecordingSession()
    directory = session.start(
        tmp_path,
        "Parser Raw",
        (
            RecordingSourceConfig(
                "pico",
                "Pico",
                "COM4",
                115200,
                parser_config=ParserConfiguration(
                    mode="delimited",
                    delimiter="|",
                    header_mode="none",
                    columns=(
                        ColumnMapping(0, "TC1"),
                        ColumnMapping(1, "TC2"),
                        ColumnMapping(2, "PRESSURE"),
                        ColumnMapping(3, "RPM"),
                    ),
                ).to_dict(),
            ),
        ),
    )
    session.write("pico", payload)
    session.write_structured(
        "pico",
        ChannelUpdate(("TC1", "TC2", "PRESSURE", "RPM"), (23.4, 25.1, 101.3, 1450)),
    )
    session.stop("normal", {"pico": len(payload)})
    assert (directory / "Pico" / "raw.log").read_bytes() == payload
    data = (directory / "Pico" / "data.csv").read_text(encoding="utf-8")
    assert "TC1,TC2,PRESSURE,RPM" in data
    metadata = json.loads((directory / "session.json").read_text(encoding="utf-8"))
    assert metadata["devices"][0]["parser"]["delimiter"] == "|"


def test_old_profiles_load_without_parser_config(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    store = ProfileStore(path)
    profile = store.create(
        "Legacy Pico",
        serial=SerialSettings(),
        parser="auto",
        device_identity=DeviceIdentity(),
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    document["profiles"][0].pop("parser_config", None)
    path.write_text(json.dumps(document), encoding="utf-8")
    restored = ProfileStore(path).get(profile.profile_id)
    assert restored.parser == "auto"
    assert restored.parser_config == ParserConfiguration()


def test_parser_config_persists_in_device_profile(tmp_path: Path) -> None:
    store = ProfileStore(tmp_path / "profiles.json")
    configuration = ParserConfiguration(
        mode="delimited",
        delimiter="|",
        header_mode="none",
        columns=(ColumnMapping(0, "TC1"), ColumnMapping(1, "TC2")),
    )
    profile = store.create(
        "Mapped Pico",
        serial=SerialSettings(),
        parser=configuration.mode,
        parser_config=configuration,
        device_identity=DeviceIdentity(),
    )
    restored = ProfileStore(tmp_path / "profiles.json").get(profile.profile_id)
    assert restored.parser == "delimited"
    assert restored.parser_config == configuration
