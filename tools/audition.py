"""Voice audition: every candidate voice reads the same line per character, UA and DE.

Usage: .venv/bin/python tools/audition.py [--only piper|holos|chatterbox]
Writes out/audition/<character>/<lang>-<label>.wav and out/audition/index.html.
"""

import argparse
import html
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "audition"
TTS = Path.home() / "tts"
PIPER_PY = TTS / "bin" / "python"
UA_PIPER = TTS / "reel" / "uk_UA-ukrainian_tts-medium.onnx"
DE_DIR = TTS / "reel_de"
VOLODYMYR_REF = ROOT / "voice" / "samples" / "volodymyr_2.wav"

LINES = {
    "pylyp": {
        "ua": "Все. Пишу бота, який сам читатиме відмови. Хоч комусь у цій хаті буде робота.",
        "de": "Schluss. Ich schreibe einen Bot, der die Absagen selbst liest. Wenigstens einer in diesem Haus hat dann Arbeit.",
    },
    "bzynka": {
        "ua": "Реджект. І не дивись на мене так, я бачила код і гірший.",
        "de": "Abgelehnt. Und schau mich nicht so an, ich habe schon schlimmeren Code gesehen.",
    },
    "medunko": {
        "ua": "Добрий день. А медку не буде? Я тільки ложечку.",
        "de": "Guten Tag. Gibt es vielleicht ein bisschen Honig? Nur einen Löffel.",
    },
    "siryi": {
        "ua": "Пилипе, тобі лист з Німеччини. Двісті сорок перший. Я під них вже окрему сумку завів.",
        "de": "Philipp, Post vom Jobcenter. Der zweihunderteinundvierzigste. Ich habe dafür schon eine eigene Tasche.",
    },
    "koliuchka": {
        "ua": "Мишей нема. Розплід є? Тоді я пішов.",
        "de": "Keine Mäuse. Gibt es Drohnenbrut? Dann bin ich weg.",
    },
}

# (character, lang, label, engine, engine args, fx) ; fx = (pitch ratio, tempo ratio)
FX_BEAR = (0.78, 0.9)
FX_WOLF = (0.88, 0.95)
FX_BEE = (1.35, 1.1)
FX_HEDGEHOG = (1.12, 1.05)

PIPER = [
    ("bzynka", "ua", "piper-tetiana-bee", {"model": UA_PIPER, "speaker": 2}, FX_BEE),
    ("bzynka", "ua", "piper-lada-bee", {"model": UA_PIPER, "speaker": 0}, FX_BEE),
    ("medunko", "ua", "piper-mykyta-bear", {"model": UA_PIPER, "speaker": 1}, FX_BEAR),
    ("siryi", "ua", "piper-mykyta-wolf", {"model": UA_PIPER, "speaker": 1}, FX_WOLF),
    ("koliuchka", "ua", "piper-mykyta-hedgehog", {"model": UA_PIPER, "speaker": 1}, FX_HEDGEHOG),
    ("pylyp", "ua", "piper-mykyta (як в 001)", {"model": UA_PIPER, "speaker": 1}, None),
    ("pylyp", "de", "piper-thorsten (як в 001)", {"model": DE_DIR / "de_DE-thorsten-medium.onnx"}, None),
    ("bzynka", "de", "piper-ramona-bee", {"model": DE_DIR / "de_DE-ramona-low.onnx"}, FX_BEE),
    ("bzynka", "de", "piper-eva_k-bee", {"model": DE_DIR / "de_DE-eva_k-x_low.onnx"}, FX_BEE),
    ("bzynka", "de", "piper-kerstin-bee", {"model": DE_DIR / "de_DE-kerstin-low.onnx"}, FX_BEE),
    ("medunko", "de", "piper-thorsten-sleepy-bear", {"model": DE_DIR / "de_DE-thorsten_emotional-medium.onnx", "speaker": 5}, FX_BEAR),
    ("medunko", "de", "piper-karlsson-bear", {"model": DE_DIR / "de_DE-karlsson-low.onnx"}, FX_BEAR),
    ("medunko", "de", "piper-thorsten-amused-bear", {"model": DE_DIR / "de_DE-thorsten_emotional-medium.onnx", "speaker": 0}, FX_BEAR),
    ("siryi", "de", "piper-pavoque-wolf", {"model": DE_DIR / "de_DE-pavoque-low.onnx"}, FX_WOLF),
    ("siryi", "de", "piper-thorsten-drunk-wolf", {"model": DE_DIR / "de_DE-thorsten_emotional-medium.onnx", "speaker": 3}, FX_WOLF),
    ("siryi", "de", "piper-karlsson-wolf", {"model": DE_DIR / "de_DE-karlsson-low.onnx"}, FX_WOLF),
    ("koliuchka", "de", "piper-thorsten-disgusted-hedgehog", {"model": DE_DIR / "de_DE-thorsten_emotional-medium.onnx", "speaker": 2}, FX_HEDGEHOG),
    ("koliuchka", "de", "piper-pavoque-hedgehog", {"model": DE_DIR / "de_DE-pavoque-low.onnx"}, FX_HEDGEHOG),
]


def piper_text(text: str, lang: str) -> str:
    # The Ukrainian Piper model drops capitals: feed lowercase.
    return text.lower() if lang == "ua" else text


def run_piper(text: str, lang: str, args: dict, dst: Path) -> None:
    cmd = [str(PIPER_PY), "-m", "piper", "-m", str(args["model"]), "-f", str(dst)]
    if "speaker" in args:
        cmd += ["-s", str(args["speaker"])]
    subprocess.run(cmd, input=piper_text(text, lang), text=True, check=True, capture_output=True)


def apply_fx(src: Path, fx) -> None:
    if not fx:
        return
    pitch, tempo = fx
    tmp = src.with_suffix(".fx.wav")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af",
         f"rubberband=pitch={pitch}:tempo={tempo}", str(tmp)],
        check=True,
    )
    tmp.replace(src)


def slug(label: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in label)


def render(char: str, lang: str, label: str, make, fx) -> None:
    dst = OUT / char / f"{lang}-{slug(label)}.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    make(LINES[char][lang], dst)
    apply_fx(dst, fx)
    print("ok", dst.relative_to(ROOT))


def build_index() -> None:
    sheet = ROOT / "out" / "model_sheet.png"
    parts = [
        "<html><head><meta charset='utf-8'><title>Прослуховування</title><style>",
        "body{background:#0f0b24;color:#f2f0f7;font-family:sans-serif;margin:24px}",
        "h1{color:#ffc44d}h2{color:#ff4fa3;margin-top:32px}.c{display:flex;align-items:center;gap:12px;margin:6px 0}",
        ".l{width:330px;font-family:monospace;color:#36e3d0}q{color:#9c94c9}",
        "</style></head><body><h1>Пасічник: прослуховування голосів</h1>",
        f"<p><a href='file://{sheet}'>Ескізи героїв</a></p>",
    ]
    for char, lines in LINES.items():
        parts.append(f"<h2>{char}</h2>")
        for lang in ("ua", "de"):
            parts.append(f"<p><q>{html.escape(lines[lang])}</q></p>")
            for wav in sorted((OUT / char).glob(f"{lang}-*.wav")):
                parts.append(
                    f"<div class='c'><span class='l'>{html.escape(wav.stem)}</span>"
                    f"<audio controls preload='none' src='{char}/{wav.name}'></audio></div>"
                )
    parts.append("</body></html>")
    (OUT / "index.html").write_text("\n".join(parts))
    print("index", (OUT / "index.html"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["piper", "holos", "chatterbox", "index"])
    a = ap.parse_args()
    if a.only in (None, "piper"):
        for char, lang, label, args, fx in PIPER:
            render(char, lang, label, lambda t, d, args=args, lang=lang: run_piper(t, lang, args, d), fx)
    if a.only in (None, "holos"):
        import holos_engine
        holos_engine.run(render, LINES, VOLODYMYR_REF, (FX_BEE, FX_BEAR, FX_WOLF, FX_HEDGEHOG))
    if a.only in (None, "chatterbox"):
        import chatterbox_engine
        chatterbox_engine.run(render, LINES, VOLODYMYR_REF)
    build_index()


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()
