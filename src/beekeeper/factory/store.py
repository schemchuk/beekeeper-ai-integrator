"""Reading and writing the factory's YAML state files (ADR 007).

Writes are atomic: a temp file in the same folder, then a rename, so a crash never leaves
half a file behind.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

import yaml


class StateError(ValueError):
    """A refused operation or a broken state file."""


def read_yaml(path: Path) -> dict:
    """The file's top-level mapping, or {} if the file does not exist yet."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise StateError(f"{path}: expected a mapping at the top")
    return data


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def dump_time(moment: datetime) -> str:
    require_aware(moment)
    return moment.isoformat()


def load_time(value: object, where: str) -> datetime:
    """An aware datetime from an ISO string (or a YAML timestamp a human left unquoted)."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as e:
            raise StateError(f"{where}: not a date-time: {value!r}") from e
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise StateError(f"{where}: expected a date-time with a UTC offset, got {value!r}")
    return value


def require_aware(moment: datetime) -> None:
    if moment.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
