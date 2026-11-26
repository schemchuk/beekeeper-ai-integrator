from beekeeper.episode import load_episode
from beekeeper.post import post_path, post_text, write_post
from blocks import COVER_POST

EPISODE = (
    'id: "900"\nslug: test\ntitle: {ua: "Тест", de: "Test"}\n'
    + COVER_POST
    + 'lines:\n  - who: pylyp\n    ua: "Привіт"\n    de: "Hallo"\n'
)


def test_post_text_order_hook_first_hashtags_last(tmp_path):
    (tmp_path / "episode.yaml").write_text(EPISODE, encoding="utf-8")
    ep = load_episode(tmp_path, {"pylyp"})
    text = post_text(ep, "de")
    blocks = text.strip().split("\n\n")
    assert blocks == [
        "Wie viele Mails könnte ein Bot schreiben?",
        "Autoantwort: 20 Zeilen Python.",
        "Was automatisieren Sie zuerst?",
        "Routine im Team? Schreiben Sie mir.",
        "#Automatisierung #KI #Python",
    ]
    out = tmp_path / "out"
    assert write_post(ep, out, "ua") == post_path(out, "ua")
    assert post_path(out, "ua").read_text(encoding="utf-8").startswith("Скільки листів")
