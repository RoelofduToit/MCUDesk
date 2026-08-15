"""Shared display-only formatting for graph detail tables."""

import math


def format_graph_value(value: int | float | None) -> str:
    """Format a measurement without changing its stored precision."""
    if value is None or not math.isfinite(float(value)):
        return "—"
    return f"{float(value):.2f}"


def format_cursor_time(elapsed_seconds: float, *, precise: bool = False) -> str:
    """Format elapsed cursor time as seconds, MM:SS, or HH:MM:SS."""
    seconds = float(elapsed_seconds)
    if not math.isfinite(seconds):
        return "—"
    seconds = max(0.0, seconds)

    if precise:
        if seconds < 60.0:
            return f"{seconds:.2f} s"
        minutes, remainder = divmod(seconds, 60.0)
        if minutes < 60:
            return f"{int(minutes)}:{remainder:05.2f}"
        hours, minutes = divmod(int(minutes), 60)
        return f"{hours:02d}:{minutes:02d}:{remainder:05.2f}"

    rounded_tenths = round(seconds, 1)
    if rounded_tenths < 60.0:
        return f"{rounded_tenths:.1f} s"
    total_seconds = round(seconds)
    minutes, second = divmod(total_seconds, 60)
    if minutes < 60:
        return f"{minutes}:{second:02d}"
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{second:02d}"
