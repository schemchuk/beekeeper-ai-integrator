from pathlib import Path

from beekeeper.cli import main
from beekeeper.tempclean import clean

DEPLOY = Path(__file__).parent.parent / "deploy"


def _fill(folder: Path) -> None:
    (folder / "sub").mkdir(parents=True)
    (folder / "003-script.md").write_text("x")
    (folder / "sub" / "deep.txt").write_text("y")


def test_clean_empties_but_keeps_folder(tmp_path):
    target = tmp_path / "temp"
    _fill(target)
    outside = tmp_path / "keep.txt"
    outside.write_text("k")
    (target / "link").symlink_to(outside)
    gone = clean(target)
    assert {p.name for p in gone} == {"003-script.md", "sub", "link"}
    assert target.is_dir() and not any(target.iterdir())
    assert outside.read_text() == "k"  # a link is removed, not followed


def test_dry_run_deletes_nothing(tmp_path, capsys):
    target = tmp_path / "temp"
    _fill(target)
    assert main(["temp-clean", "--dir", str(target), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "would delete" in out and "003-script.md" in out and "2 item(s)" in out
    assert (target / "sub" / "deep.txt").exists()


def test_missing_folder_is_fine(tmp_path, capsys):
    assert main(["temp-clean", "--dir", str(tmp_path / "nope")]) == 0
    assert "deleted 0 item(s)" in capsys.readouterr().out


def test_timer_is_monday_berlin_and_persistent():
    timer = (DEPLOY / "beekeeper-temp-clean.timer").read_text()
    assert "OnCalendar=Mon *-*-* 07:00:00 Europe/Berlin" in timer
    assert "Persistent=true" in timer
    service = (DEPLOY / "beekeeper-temp-clean.service").read_text()
    assert "beekeeper temp-clean" in service and "Type=oneshot" in service
