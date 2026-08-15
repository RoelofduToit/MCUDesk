"""Calculated/virtual channels derived from physical measurements."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import re
from typing import Mapping as MappingType
import uuid

from serialscope.data.expression import (
    ExpressionError,
    evaluate_expression,
    expression_names,
    parse_expression,
)
from serialscope.parsing import ChannelUpdate


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NON_IDENTIFIER = re.compile(r"[^A-Za-z0-9_]+")


class CalculatedChannelError(ValueError):
    """A user-presentable calculated-channel configuration problem."""


@dataclass(frozen=True, slots=True)
class CalculatedChannel:
    """One user-defined virtual channel and its restricted expression."""

    channel_id: str
    name: str
    expression: str
    unit: str = ""
    bindings: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        channel_id = self.channel_id.strip()
        name = self.name.strip()
        expression = self.expression.strip()
        if not channel_id:
            raise CalculatedChannelError("Calculated channel ID must not be empty.")
        if not name:
            raise CalculatedChannelError("Enter a calculated channel name.")
        if "\x1f" in name:
            raise CalculatedChannelError("Calculated channel name is invalid.")
        parse_expression(expression)
        object.__setattr__(self, "channel_id", channel_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "expression", expression)
        object.__setattr__(self, "unit", self.unit.strip())
        object.__setattr__(self, "bindings", tuple(self.bindings))

    @property
    def binding_map(self) -> dict[str, str]:
        return dict(self.bindings)

    def dependencies(self) -> tuple[str, ...]:
        """Return authoritative source names this expression depends on."""
        mapping = self.binding_map
        return tuple(mapping.get(name, name) for name in expression_names(self.expression))

    def to_dict(self) -> dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "name": self.name,
            "expression": self.expression,
            "unit": self.unit,
            "bindings": dict(self.bindings),
        }

    @classmethod
    def from_mapping(cls, value: MappingType[str, object]) -> "CalculatedChannel":
        bindings = value.get("bindings", {})
        pairs: tuple[tuple[str, str], ...] = ()
        if isinstance(bindings, Mapping):
            pairs = tuple(
                (str(identifier).strip(), str(source).strip())
                for identifier, source in bindings.items()
                if str(identifier).strip() and str(source).strip()
            )
        return cls(
            str(value.get("channel_id") or uuid.uuid4().hex),
            str(value.get("name", "")),
            str(value.get("expression", "")),
            str(value.get("unit", "")),
            pairs,
        )

    @classmethod
    def create(
        cls,
        name: str,
        expression: str,
        *,
        unit: str = "",
        available_names: Iterable[str] = (),
        channel_id: str | None = None,
    ) -> "CalculatedChannel":
        bindings = bindings_for_expression(expression, available_names)
        return cls(
            channel_id or uuid.uuid4().hex,
            name,
            expression,
            unit,
            tuple(bindings.items()),
        )


@dataclass(frozen=True, slots=True)
class CalculatedEvaluation:
    update: ChannelUpdate | None
    errors: Mapping[str, str]
    names: tuple[str, ...]


def identifier_for(name: str) -> str:
    """Return a stable expression identifier derived from a channel name."""
    text = name.strip()
    if _IDENTIFIER.fullmatch(text):
        return text
    compact = _NON_IDENTIFIER.sub("_", text).strip("_")
    if not compact:
        compact = "channel"
    if compact[0].isdigit():
        compact = f"ch_{compact}"
    return compact


def default_bindings(channel_names: Iterable[str]) -> dict[str, str]:
    """Map unique identifiers onto authoritative channel names."""
    bindings: dict[str, str] = {}
    used: set[str] = set()
    for name in channel_names:
        base = identifier_for(name)
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used.add(candidate)
        bindings[candidate] = name
    return bindings


def bindings_for_expression(
    expression: str, available_names: Iterable[str]
) -> dict[str, str]:
    """Bind expression identifiers to available authoritative channel names."""
    available = tuple(available_names)
    by_identifier = default_bindings(available)
    reverse = {name: ident for ident, name in by_identifier.items()}
    available_set = set(available)
    bindings: dict[str, str] = {}
    for identifier in expression_names(expression):
        if identifier in available_set:
            bindings[identifier] = identifier
        elif identifier in by_identifier:
            bindings[identifier] = by_identifier[identifier]
        elif identifier in reverse:
            bindings[identifier] = reverse[identifier]
        else:
            bindings[identifier] = identifier
    return bindings


def topological_order(
    names: tuple[str, ...],
    dependencies: Mapping[str, tuple[str, ...]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return a safe evaluation order and any names involved in a cycle."""
    name_set = set(names)
    remaining = {
        name: tuple(dep for dep in dependencies.get(name, ()) if dep in name_set)
        for name in names
    }
    ready = [name for name, deps in remaining.items() if not deps]
    ordered: list[str] = []
    while ready:
        name = ready.pop(0)
        ordered.append(name)
        for other, deps in remaining.items():
            if name in deps:
                remaining[other] = tuple(dep for dep in deps if dep != name)
                if not remaining[other] and other not in ordered and other not in ready:
                    ready.append(other)
    cyclic = tuple(name for name in names if name not in ordered)
    return tuple(ordered), cyclic


def evaluate_calculated_channels(
    channels: tuple[CalculatedChannel, ...],
    latest: Mapping[str, int | float],
) -> CalculatedEvaluation:
    """Evaluate calculated channels in dependency order without looping."""
    errors: dict[str, str] = {}
    dependencies: dict[str, tuple[str, ...]] = {}
    for channel in channels:
        try:
            dependencies[channel.name] = channel.dependencies()
        except ExpressionError as error:
            errors[channel.name] = str(error)
            dependencies[channel.name] = ()

    order, cyclic = topological_order(
        tuple(channel.name for channel in channels), dependencies
    )
    for name in cyclic:
        errors.setdefault(
            name,
            "This expression depends on itself through another calculated channel.",
        )

    by_name = {channel.name: channel for channel in channels}
    values = dict(latest)
    produced_names: list[str] = []
    produced_values: list[int | float] = []
    for name in order:
        if name in errors:
            continue
        channel = by_name[name]
        try:
            identifiers = expression_names(channel.expression)
        except ExpressionError as error:
            errors[name] = str(error)
            continue
        mapping = channel.binding_map
        variables: dict[str, int | float] = {}
        missing = False
        for identifier in identifiers:
            source = mapping.get(identifier, identifier)
            if source not in values:
                errors[name] = f"{source} is not available yet."
                missing = True
                break
            variables[identifier] = values[source]
        if missing:
            continue
        try:
            result = evaluate_expression(channel.expression, variables)
        except ExpressionError as error:
            errors[name] = str(error)
            continue
        values[name] = result
        produced_names.append(name)
        produced_values.append(result)

    update = (
        ChannelUpdate(tuple(produced_names), tuple(produced_values), False)
        if produced_names
        else None
    )
    return CalculatedEvaluation(
        update, errors, tuple(channel.name for channel in channels)
    )
