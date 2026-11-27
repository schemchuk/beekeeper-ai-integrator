# Beekeeper AI Integrator

[English](README.md)

Eine Episodenfabrik für kurze Zeichentrick-Reels über Pylyp, einen ukrainischen Imker, der
heute in Deutschland IT automatisiert. Eine Idee geht in einen Telegram-Chat; heraus kommt
ein fertiges deutsches Reel mit Stimmen und Untertiteln, zweimal pro Woche veröffentlicht,
ohne Handschnitt.

Die Serie ist das Schaufenster, die Pipeline ist die Arbeit. Die Bienen erledigen die
Routine, der Imker pflegt die blühende Wiese. Genau das biete ich an: Ich nehme Menschen
und Firmen die Routinearbeit ab, damit ihnen Raum für ihre Ideen bleibt.

## Anschauen

| Folge | Wo |
| --- | --- |
| 003 „Abend mit Isegrim“ | [LinkedIn](https://www.linkedin.com/feed/update/urn:li:ugcPost:7532010812069249025) · [YouTube Shorts](https://youtube.com/shorts/qD0Wu-QN9Bw) · [Release-Dateien](https://github.com/schemchuk/beekeeper-ai-integrator/releases/tag/reel/003-vechir-z-sirym) |
| 002 „Medunko im Winterschlaf“ | LinkedIn, Instagram, Facebook, Threads (das erste Reel, 25.11.2026) |

Neue Folgen: dienstags und donnerstags um 8:00 Uhr (Berlin).

## So funktioniert es

1. **Idee**: Ich schicke dem Fabrik-Bot eine Idee oder eine Imkergeschichte, getippt oder
   gesprochen. Sprache wird lokal transkribiert (whisper), die Idee kommt in die Warteschlange.
2. **Drehbuch**: Drei Tage vor dem Termin schreibt die Fabrik nachts `episode.yaml`, Ukrainisch
   und Deutsch nebeneinander, mit Cover und Posttext.
3. **Freigabe**: Morgens kommt das Drehbuch in den Chat. Ich antworte mit Änderungen auf
   Ukrainisch, die Fabrik passt das Deutsche an. Schweigen gilt als Zustimmung.
4. **Produktion**: lokale Stimmen (die Hauptfigur spricht mit meiner geklonten Stimme),
   Timing, Untertitel, Animation in Remotion, dann die Prüfung gegen den Ausgabevertrag.
5. **Übergabe**: ein öffentliches GitHub-Release; mein Posting-Bot
   [postpilot](https://github.com/schemchuk/postpilot) holt es ab und veröffentlicht es
   pünktlich.

## Der Vertrag mit postpilot

Die Fabrik fasst weder Code noch Warteschlange noch Zugangsdaten von postpilot an. Sie
übergibt pro Folge ein Release `reel/<folge>` mit `manifest.json`
(`{"v": 2, "kind": "reel", "id": …, "release_at": …, "ai": true}`), `video.mp4`, `cover.png`
und `post_de.txt` und prüft alle Grenzen vorher. postpilot hält dafür vier Regeln ein:

| Regel | postpilot |
| --- | --- |
| R1 Text wie geschrieben | postet `post_de.txt` unverändert, ohne KI-Umschreiben, plus KI-Hinweis |
| R2 Unser Cover | nimmt `cover.png` als Vorschaubild, wo das Netzwerk es erlaubt |
| R3 Pünktlich | veröffentlicht zu `release_at`, binnen etwa 15 Minuten |
| R4 Nur einmal | übernimmt das Release maschinell; eine Folge wird nie doppelt veröffentlicht |

Details auf Englisch: [README](README.md), [Architektur](docs/architecture.md),
[ADR 011](docs/adr/011-handoff-release-contract-v2.md).

## Lizenz

Code: [MIT](LICENSE). Figuren, Folgen, Drehbücher und die Serienbibel:
[CC BY-NC 4.0](LICENSE-CONTENT.md).

© 2026 Volodymyr Shemchuk
