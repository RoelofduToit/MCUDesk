import csv
from pathlib import Path

import pytest

from serialscope.logging import StructuredCsvLogger
from serialscope.parsing import ChannelUpdate


class MutableClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


def _rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return list(csv.reader(csv_file))


def test_logger_writes_elapsed_header_and_one_row_per_sample(tmp_path: Path) -> None:
    clock = MutableClock()
    logger = StructuredCsvLogger(clock=clock)
    path = tmp_path / "data.csv"
    logger.start(path)

    logger.write(ChannelUpdate(("TC1", "PRESSURE"), (100.41, 2.501)))
    clock.value += 1.003
    logger.write(ChannelUpdate(("TC1", "PRESSURE"), (100.52, 2.497)))
    logger.stop()

    assert _rows(path) == [
        ["elapsed_s", "TC1", "PRESSURE"],
        ["0.000", "100.41", "2.501"],
        ["1.003", "100.52", "2.497"],
    ]
    assert logger.row_count == 2
    assert not logger.is_recording


def test_missing_values_are_empty_and_later_unknown_channels_are_ignored(
    tmp_path: Path,
) -> None:
    clock = MutableClock()
    logger = StructuredCsvLogger(clock=clock)
    path = tmp_path / "data.csv"
    logger.start(path)
    logger.write(ChannelUpdate(("TC1", "TC2"), (100.1, 98.2), False))
    clock.value += 1.0

    logger.write(ChannelUpdate(("TC1", "TC3"), (100.3, 105.2), False))
    logger.stop()

    assert logger.columns == ("TC1", "TC2")
    assert logger.ignored_channels == ("TC3",)
    assert _rows(path) == [
        ["elapsed_s", "TC1", "TC2"],
        ["0.000", "100.1", "98.2"],
        ["1.000", "100.3", ""],
    ]


def test_start_creates_elapsed_header_and_stop_flushes_without_samples(
    tmp_path: Path,
) -> None:
    path = tmp_path / "data.csv"
    logger = StructuredCsvLogger()

    logger.start(path)
    logger.stop()

    assert path.exists()
    assert _rows(path) == [["elapsed_s"]]


@pytest.mark.parametrize(
    ("delimiter", "expected"),
    [
        (",", "elapsed_s,A,B\r\n0.000,1,2\r\n"),
        (";", "elapsed_s;A;B\r\n0.000;1;2\r\n"),
        ("\t", "elapsed_s\tA\tB\r\n0.000\t1\t2\r\n"),
    ],
)
def test_selected_delimiter_is_used_for_entire_file(
    tmp_path: Path,
    delimiter: str,
    expected: str,
) -> None:
    clock = MutableClock()
    logger = StructuredCsvLogger(clock=clock)
    path = tmp_path / "data.csv"

    logger.start(path, delimiter=delimiter)
    logger.write(ChannelUpdate(("A", "B"), (1, 2)))
    logger.stop()

    assert logger.delimiter == delimiter
    assert path.read_bytes().decode("utf-8") == expected
