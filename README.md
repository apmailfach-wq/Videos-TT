# Videos-TT

Automatisch generierte TikTok-Videos (1080×1920, 30 fps) – komplett per Code gerendert.

## notwehr-video.mp4

**Thema:** Strafe nach einer Schlägerei, wenn man selbst angegriffen wurde (Rechtslage in Deutschland)
Länge ca. 85 s · Voiceover: edge-tts `de-AT-JonasNeural` (+12 % Tempo)

| Abschnitt | Zeit | Inhalt |
|---|---|---|
| Hook | 0–7 s | Angegriffen, gewehrt – und selbst angezeigt? |
| § 32 StGB | 7–26 s | Notwehr: gegenwärtiger, rechtswidriger Angriff, mildestes sicheres Mittel, niemand muss weglaufen |
| § 33 StGB | 26–39 s | Notwehrexzess aus Furcht, Schrecken, Verwirrung |
| Die Grenze | 39–63 s | Angreifer am Boden/gibt auf → Schluss; § 223 (bis 5 J.), § 224 (6 Mon.–10 J.) |
| 3 Tipps | 63–75 s | Schweigen, Attest + Zeugen, Fachanwalt |
| Frage an die Zuschauer | 75–85 s | „Wurdet ihr schon mal angegriffen …? Schreibt eure Erfahrung in die Kommentare und speichert das Video!“ (groß eingeblendet) |

Keine Rechtsberatung.

## Neu erzeugen

```bash
pip install -r requirements.txt   # ffmpeg + Inter (für Fließtext) werden vorausgesetzt
cd src
python3 tts.py          # Voiceover je Szene + Wort-Timings -> build/
python3 render.py       # rendert ../notwehr-video.mp4
python3 render.py preview 5 30 60   # Standbilder zur Kontrolle -> build/stills/
```

- `src/script.py` – Sprechertext je Szene, Stimme, Tempo
- `src/tts.py` – edge-tts mit Wortgrenzen (Untertitel-Timing)
- `src/render.py` – Pillow-Frames im flachen Erklärfilm-Look → ffmpeg (H.264/AAC):
  hellgrauer Hintergrund, breite Headline (Unbounded) tippt sich oben ein, Kapitel-Badge,
  animierte Strichmännchen (türkis = du, dunkelblau = Angreifer), Gesetzesseiten, Polaroids
  mit Handschrift (Caveat), Umschläge, Stempel, dunkle Spotlight-Szenen für „Panik“.
- `fonts/` – Unbounded + Caveat (SIL Open Font License, via Google Fonts)

Die Szenendauern ergeben sich direkt aus der Länge der Tonspur; Key-Points werden auf das jeweils gesprochene Wort getimt.


## fuehrerschein-video.mp4 (Erklär-Format)

Gleiches Thema im klaren Erklär-Look wie das Notwehr-Video: eine Erzählstimme, getippte Headlines,
Kapitel 1 Party · 2 Morgen · 3 Kontrolle · 4 Strafen · 5 Fazit, Strichmännchen (Rafael türkis, Klaus orange,
Polizei blau), Promille-Kurve, Laborbefund, Stempel, Untertitel, Community-Frage. Ca. 81 s.
Quelle: `src/fuehrerschein2/` (`python3 tts.py && python3 render.py`). Stimme in `script.py` (VOICE);
Variante mit Conrad-Stimme: `fuehrerschein-video-conrad.mp4` (`VIDEO_OUT=fuehrerschein-video-conrad.mp4 python3 render.py`).

### Version mit eigener Stimme: `fuehrerschein-video-eigene-stimme.mp4`
Eigene Aufnahme → `align.py` (Text-zu-Pausen-Zuordnung ohne Spracherkennung) → `build_voice.py`
(entrauschen, Pausen kürzen, Tempo ×1,2) → `VOICE_DIR=… VIDEO_OUT=… python3 render.py`.

## fuehrerschein-video-neon.mp4 (Neon-Kurzfilm-Version)

**Thema:** „Gestern gewonnen, heute den Führerschein verloren?“ – Restalkohol & Cannabis am Morgen nach der Siegesfeier
Länge ca. 84 s · 1080×1920 · 30 fps · Neon-Look (Türkis/Magenta/Gelb) mit weichen 3D-Figuren und Bloom

| Abschnitt | Inhalt |
|---|---|
| Hook | Tor in Zeitlupe → Konfetti → harter Schnitt auf Blaulicht, Glitch-Text, Führerschein reißt |
| Siegesparty | Drohnenflug, Rafael (Joint, Popcorn, Rauch-Fußball), Klaus (Bierzähler mit Ka-Ching), Splitscreen |
| Die Nacht | Zeitraffer 23:00 → 06:30, Röntgenblick mit THC-Partikeln/Alkohol-Blasen, Tacho im roten Bereich |
| Der Morgen | Wecker, Spiegel-Dialoge, Türen knallen, „Wirklich?“, Zündschlüssel |
| Die Fahrt | Verfolgerkamera, Cockpit, Drohne, Ampel – Bremse quietscht |
| Kontrolle | Blaulicht, Polizist, Comic-Freeze, 0,5 ‰ am Pustegerät, 3D-Fakten-Stempel |
| Pointe & Frage | „Deutschland hat gewonnen … und wir haben verloren.“, Bus-Szene, Community-Frage, Loop zurück zum Ball |

Fakten (Stand 2026, ohne Gewähr): THC-Grenzwert 3,5 ng/ml Blutserum (§ 24a StVG); ab 0,5 ‰ bzw. 3,5 ng/ml beim
ersten Verstoß 500 €, 2 Punkte, 1 Monat Fahrverbot; ab 0,3 ‰ mit Fahrfehler/Ausfallerscheinungen Straftat (§ 316 StGB);
Mischkonsum Cannabis + Alkohol 1.000 €; Probezeit/unter 21: 0,0 ‰ und Cannabisverbot (§ 24c StVG).

```bash
cd src/fuehrerschein
python3 tts.py                 # Stimmen je Figur (script.py: VOICES / LINES) -> build/fuehrerschein/
python3 render.py              # rendert ../../fuehrerschein-video-neon.mp4
python3 render.py shots        # Schnittliste
python3 render.py preview 5 30 # Standbilder
```

## zarplata-video.mp4 – Physik-Simulator „Доживёт ли зарплата до отпуска?“

**Format:** 2D-Physik (Pymunk) zum Zuschauen und Mitfiebern, 1080×1920, **60 fps**, ca. 34 s, keine Stimme –
nur Sound-Effekte (Aufprall, „Geld weg“-Bonk, Ka-Ching, Trommelwirbel, Fanfare). Trend-Sound in TikTok drüberlegen.
Deutsche Version: `zarplata-video-de.mp4` („Schafft es mein Gehalt bis zum Urlaub?“).

Der grüne Ball **ЗАРПЛАТА** (mit Gesicht, wird mit sinkendem Kontostand kleiner und roter) fällt durch das Level:

| Abschnitt | Hindernisse (Kosten) |
|---|---|
| Hook | „ДОЖИВЁТ ЛИ МОЯ ЗАРПЛАТА ДО ОТПУСКА?“, Kontostand 85 000 ₽ + Fortschrittsbalken zum 🏖 |
| Rotoren | АРЕНДА −30 000, 2× КОММУНАЛКА −7 500 (danach „ОПЛАЧЕНО“) |
| Plinko | НАЛОГИ-Pins je −1 300, grüner КЭШБЭК +47 ₽ |
| Kammer | wütende Bälle: ДОСТАВКА ЕДЫ, ВНЕЗАПНЫЙ ЗУБНОЙ (−18 000), ПОДПИСКИ, ДР ДРУГА |
| Kolben | КРЕДИТ, ШТРАФ, Bonus-Bumper ПРЕМИЯ +15 000 |
| Finale | Zeitlupe „НУ ЖЕ… НУ ЖЕ…“, Schieber ЦЕНЫ ВЫРОСЛИ, Taschen МИКРОЗАЙМ / **ОТПУСК** / ДОШИРАК ДО ЗП |
| Ende | „ДОЛЕТЕЛА!“ → „Осталось на отпуск: 1 651 ₽“ → „Отпуск: шашлык на балконе“ → Kommentar-Frage 👇 |

Die Simulation ist deterministisch: `render.py` testet hunderte Seeds und nimmt den dramatischsten Lauf
(landet im Urlaub, fast pleite, viele verschiedene Treffer, ~30 s). Andere Seeds = neue Videos mit gleichem Level.

```bash
cd src/zarplata
python3 render.py                    # besten Seed suchen + ../../zarplata-video.mp4 rendern (~1 min)
python3 render.py seed 314           # bestimmten Seed rendern
python3 sim.py 300                   # Seeds durchprobieren: Ergebnis, Restgeld, Dauer, Treffer
SEED=314 python3 render.py preview 2 15 end   # Standbilder -> build/zarplata/stills/
LANG_VIDEO=de python3 render.py seed 314      # deutsche Texte/€ -> ../../zarplata-video-de.mp4
```

- `src/zarplata/sim.py` – Level, Hindernisse, Kosten, Kollisionen, Zeitlupe, Anti-Hängenbleiben
- `src/zarplata/render.py` – Cairo-Grafik (Kantenglättung), Kamera-Follow, Partikel, Münzen, Konfetti, Screen-Shake, HUD
- `src/zarplata/sfx.py` – synthetisierte Sounds passend zu den Physik-Events
- `src/zarplata/texts.py` – alle Texte (ru/de) – hier eigene Ausgaben/Pointen eintragen

## gehalt-video.mp4 – „Schafft es mein Gehalt bis zum Urlaub?“ (deutsches Leben)

Physik-Video (Pymunk), 1080×1920, 60 fps, ca. 43 s, nur Soundeffekte (Trend-Sound in TikTok drüberlegen).
Ein Monat mit **3.350 € brutto** (StKl. I, keine Kinder, ohne Kirchensteuer, Werte 2026 gerundet, ohne Gewähr):

| Kapitel | Was passiert |
|---|---|
| 1 · Lohnabzüge | Schacht mit 5 Schranken: Lohnsteuer −392,00 · Rente 9,3 % −311,55 · Kranken 8,75 % −293,13 · Pflege 2,4 % −80,40 · Arbeitslosen 1,3 % −43,55 → Stempel **NETTO 2.229,37 €** |
| 2 · Fixkosten | Rotoren: Warmmiete −1.150 · Strom −89 · Handy + WLAN −64,98 (danach „BEZAHLT“) |
| 3 · Alltag | Plinko mit Emoji-Pins: Kaffee to go, Butterbrezel, Döner, Pizza, Feierabendbier, Online-Bestellung; grüner Pfand-Bumper +3,25 |
| 4 · Überraschungen | Kugeln mit Gesicht: Wocheneinkauf, Zahnreinigung, Rundfunkbeitrag 18,36, Fitnessstudio, Streaming, Lieferdienst |
| 5 · Monatsende | Kolben Kfz-Versicherung, Deutschlandticket 63 €, Knöllchen; Steuererstattung-Bumper; Rotor NK-Nachzahlung −240; Taschen Dispo / **Urlaub (Mallorca)** / Nudeln bis zum 1. |
| Ende | „GESCHAFFT!“ → Monatsabrechnung (Brutto, Abgaben, Fixkosten, Alltag, Überraschungen, Rückflüsse, Rest) → „Mallorca? Eher Balkonien.“ → „Wie viel bleibt dir am Monatsende?“ |

HUD: Kontostand (Brutto → Netto, mit Cent), live **Kontoauszug** der letzten 3 Buchungen, Monatsfortschritt „1.–31. Mai“.

```bash
cd src/gehalt
python3 render.py                         # besten Seed suchen + ../../gehalt-video.mp4 (~2 min)
python3 render.py seed 451                # diesen Lauf rendern (218,27 € übrig)
SEED=451 python3 render.py preview 3 15 L4 end   # Standbilder (L4 = 4 s nach Landung)
python3 sim.py 200                        # Seeds testen
```
Beträge/Texte: `src/gehalt/daten.py` · Level: `src/gehalt/sim.py` · Grafik: `src/gehalt/render.py`.
