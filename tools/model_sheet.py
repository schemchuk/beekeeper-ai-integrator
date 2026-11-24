"""Render a model sheet of all characters: neutral and talking/blinking poses.

Usage: python3 tools/model_sheet.py [out.png]
Each characters/*.svg uses group ids: eyes-open/eyes-closed, mouth-closed/-open/-wide.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORDER = ["pylyp", "bzynka", "medunko", "siryi", "koliuchka"]
NAMES = {
    "pylyp": "Пилип / Philipp",
    "bzynka": "Бзинька / Bsinka",
    "medunko": "Медунко",
    "siryi": "Сірий",
    "koliuchka": "Колючка",
}
POSES = [
    ("спокій", ""),
    ("говорить", "talk"),
    ("кричить", "shout"),
    ("кліпає", "blink"),
]

CSS = """
body{margin:0;background:#0f0b24;font-family:Inter,'Noto Sans',sans-serif;color:#f2f0f7}
h1{margin:24px 32px 8px;color:#ffc44d;font-size:34px}
.row{display:flex;align-items:flex-end;gap:8px;margin:8px 24px 0;padding:8px;border-bottom:1px solid #2f2457}
.label{width:190px;font-size:22px;font-weight:700;color:#ff4fa3;align-self:center}
.cell{width:230px;text-align:center;font-size:15px;color:#9c94c9}
.cell svg{width:230px;height:307px;background:radial-gradient(circle at 50% 70%,#221a52,#0f0b24 70%)}
.talk #mouth-closed,.shout #mouth-closed,.blink #eyes-open{display:none}
.talk #mouth-open,.shout #mouth-wide,.blink #eyes-closed{display:inline!important}
"""


def build_html() -> str:
    rows = []
    for name in ORDER:
        svg = (ROOT / "characters" / f"{name}.svg").read_text()
        cells = "".join(
            f'<div class="cell {cls}">{svg}<div>{title}</div></div>' for title, cls in POSES
        )
        rows.append(f'<div class="row"><div class="label">{NAMES[name]}</div>{cells}</div>')
    return f"<html><head><style>{CSS}</style></head><body><h1>Пасічник: герої, ескіз v1</h1>{''.join(rows)}</body></html>"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "model_sheet.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    height = 90 + 360 * len(ORDER)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(build_html())
    subprocess.run(
        ["chromium", "--headless", "--hide-scrollbars", f"--screenshot={out.resolve()}",
         f"--window-size=1180,{height}", f"file://{f.name}"],
        check=True, capture_output=True,
    )
    Path(f.name).unlink()
    print(out)


if __name__ == "__main__":
    main()
