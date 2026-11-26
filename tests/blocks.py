"""Cover and post blocks every episode needs since the reach rules (2026-11-26).

Test fixtures put them right after `title`, so tests that append to `lines` still work.
"""

COVER_POST = """\
cover:
  who: [pylyp]
  monitor: {ua: "Ваш запит збережено.", de: "Ihre Anfrage wurde gespeichert."}
post:
  hook:
    ua: "Скільки листів на тиждень міг би писати бот?"
    de: "Wie viele Mails könnte ein Bot schreiben?"
  grain: {ua: "Автовідповідь: 20 рядків Python.", de: "Autoantwort: 20 Zeilen Python."}
  question: {ua: "Що автоматизуєте першим?", de: "Was automatisieren Sie zuerst?"}
  offer: {ua: "Рутина в команді? Пишіть.", de: "Routine im Team? Schreiben Sie mir."}
  hashtags: [Automatisierung, KI, Python]
"""

OFFSET = COVER_POST.count("\n")  # lines the blocks add before `scenes`/`lines`
