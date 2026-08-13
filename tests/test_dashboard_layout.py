import pytest

from serialscope.data import DashboardLayout, GridPosition


def test_new_channels_receive_first_free_cells() -> None:
    layout = DashboardLayout(columns=4)
    assert layout.add("A") == GridPosition(0, 0)
    assert layout.add("B") == GridPosition(0, 1)
    assert layout.add("C") == GridPosition(0, 2)


def test_move_to_empty_cell_preserves_gap_and_identity() -> None:
    layout = DashboardLayout(columns=4)
    layout.add("A")
    layout.add("B")
    layout.move("A", GridPosition(2, 3))

    assert layout.position("A") == GridPosition(2, 3)
    assert layout.position("B") == GridPosition(0, 1)
    assert GridPosition(0, 0) not in {
        layout.position(name) for name in layout.channel_names
    }


def test_drop_on_occupied_cell_swaps_without_overlap() -> None:
    layout = DashboardLayout(columns=4)
    layout.add("A")
    layout.add("B")
    layout.add("C")
    layout.move("A", GridPosition(0, 2))

    assert layout.position("A") == GridPosition(0, 2)
    assert layout.position("C") == GridPosition(0, 0)
    positions = [layout.position(name) for name in layout.channel_names]
    assert len(positions) == len(set(positions))


def test_removal_does_not_compact_other_positions() -> None:
    layout = DashboardLayout(columns=4)
    for name in ("A", "B", "C"):
        layout.add(name)
    layout.move("C", GridPosition(3, 1))
    before = layout.position("C")
    layout.remove("A")
    assert layout.position("C") == before


def test_invalid_grid_positions_are_rejected() -> None:
    with pytest.raises(ValueError):
        GridPosition(-1, 0)
