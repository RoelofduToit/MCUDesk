import pytest

from serialscope.diagnostics import DiagnosticsCollector, DiagnosticsHub, DiagnosticsSettings
from serialscope.logging.raw_logger import RawLogger
from serialscope.logging.session import RecordingSession, SessionConfig
from serialscope.logging.structured_csv_logger import StructuredCsvLogger
from serialscope.parsing import ChannelUpdate, SerialStreamParser
from serialscope.parsing.observation import ParserObservation
from serialscope.replay import load_replay_session
from serialscope.storage import atomic_write_json


class Clock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def test_source_metrics_and_reset_are_independent() -> None:
    clock = Clock()
    collector = DiagnosticsCollector(clock=clock)
    collector.note_connected("a", clock())
    collector.note_bytes("a", 100, clock())
    collector.note_parser_observation("a", ParserObservation(lines=2, structured=2), clock())
    collector.note_structured_update("a", ("TC1",), clock())
    clock.advance(1)
    collector.note_connected("b", clock())
    collector.note_structured_update("b", ("X",), clock())
    snap_a = collector.snapshot("a", clock())
    snap_b = collector.snapshot("b", clock())
    assert snap_a.bytes_received == 100
    assert snap_a.lines_received == 2
    assert snap_a.structured_updates == 1
    assert snap_a.reconnects == 0
    assert snap_b.structured_updates == 1
    collector.reset_live("a")
    assert collector.snapshot("a", clock()).structured_updates == 0
    assert collector.snapshot("b", clock()).structured_updates == 1


def test_reconnects_count_after_first_connection() -> None:
    clock = Clock()
    collector = DiagnosticsCollector(clock=clock)
    collector.note_connected("pico")
    collector.note_disconnected("pico")
    collector.note_connected("pico")
    assert collector.snapshot("pico", clock()).reconnects == 1


def test_channel_rate_age_stale_and_recovery() -> None:
    clock = Clock()
    collector = DiagnosticsCollector(DiagnosticsSettings(min_samples=3), clock=clock)
    collector.note_connected("pico")
    for _ in range(6):
        collector.note_structured_update("pico", ("TC1", "TC2"), clock())
        clock.advance(1.0)
    snap = collector.snapshot("pico", clock())
    tc1 = next(channel for channel in snap.channels if channel.name == "TC1")
    assert tc1.measured_rate_hz == pytest.approx(1.0, rel=0.05)
    assert tc1.average_interval_s == pytest.approx(1.0, rel=0.05)
    assert tc1.last_update_age_s == pytest.approx(1.0, abs=0.01)
    assert not tc1.stale
    clock.advance(6.0)
    stale = next(
        channel
        for channel in collector.snapshot("pico", clock()).channels
        if channel.name == "TC1"
    )
    assert stale.stale
    assert stale.state == "STALE"
    collector.note_structured_update("pico", ("TC1",), clock())
    healthy = next(
        channel
        for channel in collector.snapshot("pico", clock()).channels
        if channel.name == "TC1"
    )
    assert not healthy.stale
    assert healthy.state == "OK"


def test_first_sample_does_not_divide_by_zero() -> None:
    clock = Clock()
    collector = DiagnosticsCollector(clock=clock)
    collector.note_structured_update("pico", ("TC1",), clock())
    snap = collector.snapshot("pico", clock())
    tc1 = snap.channels[0]
    assert tc1.measured_rate_hz is None
    assert tc1.average_interval_s is None
    assert not tc1.stale


def test_gap_requires_significant_interval() -> None:
    clock = Clock()
    collector = DiagnosticsCollector(DiagnosticsSettings(min_samples=3, gap_multiplier=5), clock=clock)
    for _ in range(6):
        collector.note_structured_update("pico", ("TC1",), clock())
        clock.advance(1.0)
    collector.note_structured_update("pico", ("TC1",), clock())
    assert collector.snapshot("pico", clock()).gaps == ()
    clock.advance(6.0)
    collector.note_structured_update("pico", ("TC1",), clock())
    gaps = collector.snapshot("pico", clock()).gaps
    channel_gaps = [gap for gap in gaps if gap.channel == "TC1"]
    assert len(channel_gaps) == 1
    assert channel_gaps[0].duration_s == pytest.approx(6.0)


def test_interval_history_is_bounded() -> None:
    clock = Clock()
    collector = DiagnosticsCollector(DiagnosticsSettings(interval_window=20), clock=clock)
    for _ in range(80):
        collector.note_structured_update("pico", ("TC1",), clock())
        clock.advance(0.1)
    channel = collector.snapshot("pico", clock()).channels[0]
    assert channel.updates == 80
    internals = collector._sources["pico"].channels["TC1"].intervals
    assert len(internals) <= 20


def test_parser_observation_counts_malformed_not_debug_text() -> None:
    parser = SerialStreamParser()
    parser.apply_configuration(parser.configuration)
    # lock json
    from serialscope.parsing.parser_config import ParserConfiguration

    parser.apply_configuration(ParserConfiguration(mode="json"))
    _updates, good = parser.observe(b'{"TC1":1}\n')
    _updates, debug = parser.observe(b"hello world\n")
    _updates, bad = parser.observe(b'{"TC1":\n')
    assert good.structured == 1
    assert debug.unrecognized == 1
    assert debug.malformed == 0
    assert bad.malformed == 1


def test_session_summary_and_old_replay_remain_compatible(tmp_path) -> None:
    clock = Clock()
    hub = DiagnosticsHub(clock=clock)
    hub.begin_recording()
    hub.note_connected("default")
    hub.note_structured_update("default", ("TC1",))
    summary = hub.end_recording()
    assert summary is not None
    assert summary["sources"][0]["structured_updates"] == 1
    session = RecordingSession(RawLogger(), StructuredCsvLogger(clock))
    session.start(tmp_path, SessionConfig("soak", "COM3", 115200, "LF"))
    session.write_structured(ChannelUpdate(("TC1",), (1.0,)))
    recorded = session.directory
    session.stop("normal", 10, diagnostics=summary)
    loaded = load_replay_session(recorded)
    assert loaded.metadata.get("diagnostics")["sources"][0]["structured_updates"] == 1
    # old session without diagnostics
    old = tmp_path / "old"
    old.mkdir()
    (old / "data.csv").write_text("elapsed_s,TC1\n0.000,1\n", encoding="utf-8")
    atomic_write_json(
        old / "session.json",
        {
            "session_name": "legacy",
            "structured_data_delimiter": ",",
            "serial": {"device": "COM4", "baud_rate": 9600},
        },
    )
    legacy = load_replay_session(old)
    assert "diagnostics" not in legacy.metadata
    assert legacy.channel_names == ("TC1",)
