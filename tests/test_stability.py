from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from serialscope.data import ChannelHistory, ChannelMetadataRegistry
from serialscope.logging import RawLogger, StructuredCsvLogger
from serialscope.parsing import ChannelUpdate
from serialscope.ui.dashboard_widget import DashboardWidget
from serialscope.ui.data_widget import DataWidget
from serialscope.ui.graphs_widget import GraphsWidget


class FixedClock:
    def __call__(self) -> float:
        return 100.0


def test_100000_updates_stream_to_disk_with_bounded_live_state(tmp_path: Path) -> None:
    clock = FixedClock()
    raw = RawLogger()
    structured = StructuredCsvLogger(clock)
    history = ChannelHistory(clock=clock, max_points_per_channel=10_000)
    metadata = ChannelMetadataRegistry()
    raw_path = tmp_path / "raw.log"
    data_path = tmp_path / "data.csv"
    raw.start(raw_path)
    structured.start(data_path)
    update = ChannelUpdate(("A", "B"), (1, 2))

    for _sample in range(100_000):
        raw.write(b"1,2\n")
        structured.write(update)
        history.add_update(update)
        metadata.ensure(update.names)

    raw.stop()
    structured.stop()

    assert raw.bytes_written == 400_000
    assert raw_path.stat().st_size == 400_000
    assert structured.row_count == 100_000
    assert sum(1 for _line in data_path.open("rb")) == 100_001
    assert len(history.points("A")[0]) == 10_000
    assert history.channel_names == ("A", "B")
    assert metadata.source_names == ("A", "B")
    assert not raw.is_recording
    assert not structured.is_recording


@pytest.mark.parametrize("channel_count", [9, 50, 100])
def test_large_channel_sets_do_not_duplicate_presentation_controls(
    channel_count: int,
) -> None:
    application = QApplication.instance() or QApplication([])
    names = tuple(f"CH{index}" for index in range(channel_count))
    values = tuple(range(channel_count))
    update = ChannelUpdate(names, values)
    data = DataWidget()
    dashboard = DashboardWidget(lazy=False)
    graphs = GraphsWidget()

    for _repeat in range(3):
        data.update_channels(update)
        dashboard.update_channels(update)
        graphs.update_channels(update)

    assert data.table.rowCount() == channel_count
    assert len(dashboard._items) == channel_count
    assert len(graphs._selectors) == channel_count
    assert tuple(data.channel_names) == names
    assert tuple(dashboard.channel_names) == names
    assert tuple(graphs.channel_names) == names

    graphs._refresh_timer.stop()
    data.close()
    dashboard.close()
    graphs.close()
    application.processEvents()
