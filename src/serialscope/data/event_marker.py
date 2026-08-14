"""Session-level experiment annotation model."""

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class EventMarker:
    """One operator annotation positioned on the parent session timeline."""

    event_id: str
    elapsed_s: float
    text: str

    def __post_init__(self) -> None:
        event_id = self.event_id.strip()
        text = self.text.strip()
        if not event_id:
            raise ValueError("Event identity must not be empty.")
        if not math.isfinite(self.elapsed_s) or self.elapsed_s < 0:
            raise ValueError("Event elapsed time must be finite and non-negative.")
        if not text:
            raise ValueError("Event text must not be empty.")
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "text", text)
