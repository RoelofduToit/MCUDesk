"""Parser line-classification used by diagnostics without changing feed results."""

from dataclasses import dataclass


PARSER_STRUCTURED = "structured"
PARSER_UNRECOGNIZED = "unrecognized"
PARSER_MALFORMED = "malformed"


@dataclass(frozen=True, slots=True)
class ParserObservation:
    """Counts for one observed byte chunk."""

    lines: int = 0
    structured: int = 0
    unrecognized: int = 0
    malformed: int = 0

    def combined(self, other: "ParserObservation") -> "ParserObservation":
        return ParserObservation(
            self.lines + other.lines,
            self.structured + other.structured,
            self.unrecognized + other.unrecognized,
            self.malformed + other.malformed,
        )
