import pytest

from serialscope.parsing.csv_parser import CsvChannelParser
from serialscope.parsing.json_parser import JsonChannelParser
from serialscope.parsing.key_value_parser import KeyValueChannelParser
from serialscope.parsing.line_buffer import BoundedLineBuffer


def test_incomplete_line_buffer_is_bounded_and_recovers_after_newline() -> None:
    buffer = BoundedLineBuffer(max_line_bytes=16)

    assert buffer.feed(b"x" * 10) == ()
    assert buffer.feed(b"y" * 10) == ()
    assert buffer.buffered_bytes == 0
    assert buffer.feed(b"discarded\nvalid\r\n") == (b"valid",)


@pytest.mark.parametrize(
    ("parser", "valid_data", "expected_names"),
    [
        (CsvChannelParser(max_line_bytes=32), b"A,B\n1,2\n", ("A", "B")),
        (JsonChannelParser(max_line_bytes=32), b'{"A":1,"B":2}\n', ("A", "B")),
        (
            KeyValueChannelParser(max_line_bytes=32),
            b"A=1,B=2\n",
            ("A", "B"),
        ),
    ],
)
def test_line_parsers_discard_oversized_binary_input_and_recover(
    parser, valid_data: bytes, expected_names: tuple[str, ...]
) -> None:
    assert parser.feed(b"\xff" * 40) == []
    updates = parser.feed(b"\n" + valid_data)

    assert updates[-1].names == expected_names
