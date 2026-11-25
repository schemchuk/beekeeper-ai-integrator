from pathlib import Path
from textwrap import dedent

import pytest

from beekeeper.cli import main
from beekeeper.episode import EpisodeError, load_cast, load_episode

ROOT = Path(__file__).resolve().parents[1]
CAST = {"pylyp", "medunko", "bzynka"}

GOOD = """\
id: "900"
slug: test
title: {ua: "Тест", de: "Test"}
scenes:
  hut: "a hut"
lines:
  - shot: {scene: hut}
    onscreen: {ua: ["раз", "два"], de: ["eins", "zwei"]}
    sfx: phone-buzz
  - who: pylyp
    ua: "Привіт"
    de: "Hallo"
    pause: 0.5
"""


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "episode.yaml"
    p.write_text(dedent(text), encoding="utf-8")
    return p


def problems(tmp_path: Path, text: str) -> list[str]:
    with pytest.raises(EpisodeError) as exc:
        load_episode(write(tmp_path, text), CAST)
    return exc.value.problems


def test_good_episode(tmp_path):
    ep = load_episode(write(tmp_path, GOOD), CAST)
    assert ep.id == "900"
    assert ep.lines[0].who is None
    assert ep.lines[0].onscreen == {"ua": ["раз", "два"], "de": ["eins", "zwei"]}
    assert ep.lines[1].text == {"ua": "Привіт", "de": "Hallo"}
    assert ep.lines[1].pause == 0.5


def test_folder_path_reads_episode_yaml(tmp_path):
    write(tmp_path, GOOD)
    assert load_episode(tmp_path, CAST).slug == "test"


def test_episode_002_is_valid():
    cast = load_cast(ROOT / "characters/cast.yaml")
    ep = load_episode(ROOT / "episodes/002-medunko-v-splyachtsi", cast)
    assert ep.slug == "medunko-v-splyachtsi"
    assert all(line.who in cast for line in ep.lines if line.who)


def test_missing_german_reports_its_line(tmp_path):
    text = GOOD.replace('    de: "Hallo"\n', "")
    [p] = problems(tmp_path, text)
    assert p.endswith(":10: lines[1].de: required text")


def test_unknown_speaker_and_scene(tmp_path):
    text = GOOD.replace("who: pylyp", "who: kolobok").replace("scene: hut", "scene: moon")
    ps = problems(tmp_path, text)
    assert any(":7: lines[0].shot.scene: 'moon' is not in scenes" in p for p in ps)
    assert any("lines[1].who: 'kolobok' is not in cast.yaml" in p for p in ps)


def test_typo_key_is_reported(tmp_path):
    ps = problems(tmp_path, GOOD.replace("sfx:", "sfxx:"))
    assert any("lines[0].sfxx: unknown key" in p for p in ps)


def test_speech_without_speaker(tmp_path):
    text = GOOD.replace("  - who: pylyp\n    ua:", "  - ua:")
    ps = problems(tmp_path, text)
    assert any("lines[1]: speech (ua/de) needs a speaker in 'who'" in p for p in ps)


def test_onscreen_counts_must_match(tmp_path):
    ps = problems(tmp_path, GOOD.replace('de: ["eins", "zwei"]', 'de: ["eins"]'))
    assert any("ua and de need the same number of texts" in p for p in ps)


def test_empty_line_and_bad_pause(tmp_path):
    text = GOOD.replace("pause: 0.5", "pause: -1") + "  - shot: {scene: hut}\n"
    ps = problems(tmp_path, text)
    assert any("lines[1].pause: must be seconds" in p for p in ps)
    assert any("lines[2]: needs speech" in p for p in ps)


def test_invalid_yaml_reports_line(tmp_path):
    [p] = problems(tmp_path, GOOD + "  - who: [unclosed\n")
    assert ": invalid YAML:" in p


def test_all_problems_reported_at_once(tmp_path):
    text = GOOD.replace("slug: test\n", "").replace('    de: "Hallo"\n', "")
    assert len(problems(tmp_path, text)) == 2


def test_cli_validate_ok(capsys):
    assert (
        main(
            [
                "validate",
                str(ROOT / "episodes/002-medunko-v-splyachtsi"),
                "--cast",
                str(ROOT / "characters/cast.yaml"),
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.startswith("ok: 002 medunko-v-splyachtsi")


def test_cli_validate_fails(tmp_path, capsys):
    p = write(tmp_path, GOOD.replace('    de: "Hallo"\n', ""))
    cast = tmp_path / "cast.yaml"
    cast.write_text("pylyp: {}\n", encoding="utf-8")
    assert main(["validate", str(p), "--cast", str(cast)]) == 1
    err = capsys.readouterr().err
    assert "lines[1].de: required text" in err and "1 problem(s)" in err


def test_cli_missing_cast(tmp_path, capsys):
    assert main(["validate", str(write(tmp_path, GOOD)), "--cast", str(tmp_path / "no.yaml")]) == 1
    assert "file not found" in capsys.readouterr().err


def test_shot_eyes_must_be_open_or_closed(tmp_path):
    ep = load_episode(
        write(tmp_path, GOOD.replace("{scene: hut}", "{scene: hut, eyes: closed}")), CAST
    )
    assert ep.lines[0].shot["eyes"] == "closed"
    [p] = problems(tmp_path, GOOD.replace("{scene: hut}", "{scene: hut, eyes: sleepy}"))
    assert p.endswith("lines[0].shot.eyes: must be open or closed")
