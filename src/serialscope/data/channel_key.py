"""Source-aware identity for structured channels."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class ChannelKey:
    """Identify one parser channel within one acquisition source."""

    source_id: str
    channel_name: str

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.channel_name.strip():
            raise ValueError("Channel source and name must not be empty.")

    @property
    def storage_key(self) -> str:
        """Return a reversible, JSON-friendly metadata key."""
        return f"{self.source_id}\x1f{self.channel_name}"

    @classmethod
    def from_storage_key(cls, value: str) -> "ChannelKey":
        source_id, separator, channel_name = value.partition("\x1f")
        if not separator:
            raise ValueError("Not a source-aware channel key.")
        return cls(source_id, channel_name)
