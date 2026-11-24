"""Cast page: each character with its chosen UA/DE voice. The mouth moves while it talks.

Usage: python3 tools/cast_page.py  ->  out/cast.html
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
NAMES = {
    "pylyp": ("Пилип", "Philipp"),
    "bzynka": ("Бзинька", "Bsinka"),
    "medunko": ("Медунко", "Medunko"),
    "siryi": ("Сірий", "Siryi"),
    "koliuchka": ("Колючка", "Koliuchka"),
}
# Audition files that won the casting (see characters/cast.yaml).
CHOSEN = {
    "pylyp": ("ua-holos-clone-sample2", "de-chatterbox-clone-sample2"),
    "bzynka": ("ua-holos-mix-high23-bee", "de-piper-kerstin-bee"),
    "medunko": ("ua-holos-mix-low01-bear", "de-piper-karlsson-bear"),
    "siryi": ("ua-holos-mix-low45-wolf", "de-piper-pavoque-wolf"),
    "koliuchka": ("ua-holos-mix-low67-hedgehog", "de-piper-thorsten-disgusted-hedgehog"),
}

CSS = """
body{margin:0;background:#0f0b24;color:#f2f0f7;font-family:Inter,'Noto Sans',sans-serif}
h1{color:#ffc44d;margin:24px 32px 4px}p.sub{color:#9c94c9;margin:0 32px 16px}
.grid{display:flex;flex-wrap:wrap;gap:16px;padding:0 24px 32px}
.card{width:300px;background:#17123a;border-radius:16px;padding:12px;text-align:center}
.card svg{width:276px;height:368px;background:radial-gradient(circle at 50% 70%,#2a2063,#0f0b24 72%);border-radius:12px}
.card h2{color:#ff4fa3;margin:8px 0 4px;font-size:22px}
.btn{display:block;width:100%;margin:6px 0;padding:10px;border:0;border-radius:10px;font-size:16px;cursor:pointer;background:#2f2457;color:#f2f0f7}
.btn:hover{background:#3b2f6b}.btn small{color:#36e3d0}
.talk [id=mouth-closed]{display:none}.talk [id=mouth-open]{display:inline!important}
.blink [id=eyes-open]{display:none}.blink [id=eyes-closed]{display:inline!important}
.bob{animation:bob 2.4s ease-in-out infinite}
@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
"""

JS = """
let cur=null;
function play(id, src){
  if(cur){cur.audio.pause();clearInterval(cur.t);cur.svg.classList.remove('talk');}
  const svg=document.querySelector('#'+id+' svg');
  const audio=new Audio(src);
  const t=setInterval(()=>svg.classList.toggle('talk',Math.random()>0.35),110);
  audio.onended=()=>{clearInterval(t);svg.classList.remove('talk');};
  cur={audio,t,svg};audio.play();
}
setInterval(()=>{document.querySelectorAll('.card svg').forEach(s=>{
  if(Math.random()<0.25){s.classList.add('blink');setTimeout(()=>s.classList.remove('blink'),140);}
});},900);
"""


def main() -> None:
    cast = yaml.safe_load((ROOT / "characters" / "cast.yaml").read_text())
    cards = []
    for char, (ua_name, de_name) in NAMES.items():
        svg = (ROOT / "characters" / f"{char}.svg").read_text()
        ua, de = CHOSEN[char]
        cards.append(
            f'<div class="card" id="c-{char}"><div class="bob">{svg}</div>'
            f"<h2>{ua_name} / {de_name}</h2>"
            f'<button class="btn" onclick="play(\'c-{char}\',\'audition/{char}/{ua}.wav\')">▶ українською '
            f'<small>{cast[char]["ua"]["engine"]}</small></button>'
            f'<button class="btn" onclick="play(\'c-{char}\',\'audition/{char}/{de}.wav\')">▶ deutsch '
            f'<small>{cast[char]["de"]["engine"]}</small></button></div>'
        )
    page = (
        f"<html><head><meta charset='utf-8'><title>Пасічник: каст</title><style>{CSS}</style></head>"
        f"<body><h1>Пасічник: герої і голоси</h1><p class='sub'>Натисни кнопку: герой заговорить.</p>"
        f"<div class='grid'>{''.join(cards)}</div><script>{JS}</script></body></html>"
    )
    out = ROOT / "out" / "cast.html"
    out.write_text(page)
    print(out)


if __name__ == "__main__":
    main()
