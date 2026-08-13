"""Logical, source-keyed grid positions for Dashboard tiles."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class GridPosition:
    row: int
    column: int

    def __post_init__(self) -> None:
        if self.row < 0 or self.column < 0:
            raise ValueError("Grid positions cannot be negative.")


class DashboardLayout:
    """Own non-overlapping logical positions independently of Qt geometry."""

    def __init__(self, columns: int = 4) -> None:
        if columns < 1:
            raise ValueError("Dashboard grid must have at least one column.")
        self.columns = columns
        self._positions: dict[str, GridPosition] = {}

    @property
    def channel_names(self) -> tuple[str, ...]:
        return tuple(self._positions)

    def position(self, source_name: str) -> GridPosition | None:
        return self._positions.get(source_name)

    def add(self, source_name: str) -> GridPosition:
        existing = self.position(source_name)
        if existing is not None:
            return existing
        occupied = set(self._positions.values())
        index = 0
        while GridPosition(index // self.columns, index % self.columns) in occupied:
            index += 1
        position = GridPosition(index // self.columns, index % self.columns)
        self._positions[source_name] = position
        return position

    def remove(self, source_name: str) -> None:
        self._positions.pop(source_name, None)

    def move(self, source_name: str, destination: GridPosition) -> None:
        if source_name not in self._positions:
            raise KeyError(source_name)
        occupant = next(
            (
                name
                for name, position in self._positions.items()
                if name != source_name and position == destination
            ),
            None,
        )
        previous = self._positions[source_name]
        self._positions[source_name] = destination
        if occupant is not None:
            self._positions[occupant] = previous

    def reset(self) -> None:
        self._positions.clear()

    def snapshot(self) -> dict[str, dict[str, int]]:
        return {
            name: {"row": position.row, "column": position.column}
            for name, position in self._positions.items()
        }
