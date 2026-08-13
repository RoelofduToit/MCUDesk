"""Small, packaging-safe persistence helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path


def atomic_write_json(path: Path, value: object) -> None:
    """Durably replace a small JSON file without exposing a partial document."""
    path = Path(path)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    except (OSError, TypeError, ValueError):
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
