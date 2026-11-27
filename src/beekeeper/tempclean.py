"""Empty the temp folder (F7.2): `beekeeper temp-clean`.

Run by the systemd user timer `beekeeper-temp-clean.timer` every Monday 07:00 Berlin,
independent of the factory process. The folder itself stays; everything inside goes.
"""

import shutil
from pathlib import Path

TEMP = Path.home() / "Desktop" / "temp"


def entries(folder: Path) -> list[Path]:
    """What a clean would delete, sorted; empty if the folder is missing."""
    if not folder.is_dir():
        return []
    return sorted(folder.iterdir())


def clean(folder: Path = TEMP, dry_run: bool = False) -> list[Path]:
    """Delete every entry in `folder` (files, links, subfolders); return what went."""
    found = entries(folder)
    if dry_run:
        return found
    for path in found:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    return found
