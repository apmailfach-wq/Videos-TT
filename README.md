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

## bar-karte-handy-video.mp4 (Bezahlschmerz-Erklärfilm)

**Thema:** „Deine Bezahlart kostet dich fast 470 € im Jahr. Welche?“ (BAR vs KARTE vs HANDY) · genau 60 s · 1080×1920 · 30 fps
Flache 2D-Animation auf Dunkelblau mit wandernden Lichtern und Glow, drei Bahnen mit Strichfiguren mit Gesichtern
(BAR gelb, KARTE rot, HANDY türkis), dauerhafte Anzeige oben (Uhr „TAG 1–30“ + drei hochzählende Zähler mit
„▲ MEISTE AUSGABEN“-Marke), Kapitel-Banner, Spontankäufe fliegen in ein Raster, Push-Nachrichten („autsch!“),
Geldautomat + Kleingeld, Kamera-Wackler, Konfetti, Wort-für-Wort-Untertitel in Figurenfarben.
Voiceover: edge-tts `de-DE-ConradNeural`; Musik/Klicks/Ping werden synthetisch erzeugt.

| Zeit | Szene |
|---|---|
| 0–4 s | Hook: „DEINE BEZAHLART KOSTET DICH BIS ZU 468 € IM JAHR – WOMIT GIBST DU MEHR AUS?“ (ab Frame 0 voll im Bild) |
| 3–8 s | Wer zahlt wie · gleicher Einkaufszettel · 30 Tage · gleiches Budget |
| 8–16 s | Woche 1: Tag 1–8 → 142 / 163 / 171 € |
| 16–22 s | Falsche Auflösung: „HANDY = GRÖSSTE GELDFALLE?“ → „NOCH NICHT.“ |
| 22–30 s | Woche 2: Handy meldet jede Zahlung, kauft weniger |
| 30–38 s | Woche 3: Geldautomat, „Kleingeld fühlt sich wie Spielgeld an“ |
| 38–44 s | Woche 4: Karte – keine Nachricht, kein Gefühl |
| 44–50 s | Ergebnis: KARTE 668 € (meiste Ausgaben) · HANDY 641 € · BAR 629 € (am sparsamsten), +39 €/Monat → +468 €/Jahr |
| 50–56 s | „Wie sehr spürst du die Zahlung?“ + Tipp: Push-Nachricht für die Karte an |
| 56–60 s | „Wie zahlst du?“ → Kommentare, Abonnieren-Button mit Klick, „Teil 2 folgt“, Hinweis „Beispielrechnung“ |

Die Beträge sind eine Beispielrechnung (gleicher Einkaufszettel, Unterschiede nur durch Extras);
`timeline.py` prüft, dass die Zähler an Tag 8/15/22/30 exakt die Zielwerte treffen.

```bash
cd src/bezahlen
python3 tts.py                 # Sprecher je Szene + Wort-Timings (Tempo passt sich dem Zeitfenster an)
python3 timeline.py            # Kontrollwerte prüfen, Zeitplan anzeigen
python3 audio.py               # Mischung: Stimme, leise Musik, Klicks, Pings -> build/bezahlen/mix.wav
python3 render.py              # rendert ../../bar-karte-handy-video.mp4
python3 render.py still 18 47  # Standbilder -> build/bezahlen/stills/
```
