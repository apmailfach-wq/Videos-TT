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

## unfall-video.mp4 (ALLTAG KLAR – Fahrrad vs. Auto: Wer zahlt?)

Satirischer Kurzfilm im Soft-3D-Look · ca. 83 s · 1080×1920 · 30 fps · 4 Stimmen (Erzähler, Autofahrer, Radfahrer, Polizist)

| Abschnitt | Inhalt |
|---|---|
| Cold Open | Zeitlupen-Standbild „WER ZAHLT DAS ALLES?“ → Zurückspulen |
| Unfall | Fahrt zum Bäcker, Radfahrer, KRACH, Stirn aufs Lenkrad (HUUUP!), Flug über die Motorhaube in Zeitlupe, Aktenzeichen-Stempel |
| Schadensbilanz | Harte Schnitte pro Wort: zersprungenes Handy, Vorderrad mit Achter (eiert beim Drehen), Schulter, Totalschaden, Delle, Stirn, Brötchen; Schadensmuseum |
| Streit + Rangelei | Gegenseitiges Zeigen, Haftpflicht-Politur, Slapstick-Staubwolke, Kosten-O-Meter, „Strafverfahren?!“ |
| Polizei | Ankunft mit Blaulicht, genervter Beamter, beide zeigen aufeinander, Urlaubsantrag genehmigt |
| Rechtslage | § 7 StVG (Halterhaftung), Umstände/Mitverschulden, Schadensersatz, Schmerzensgeld ggf. für beide, § 223 StGB – vorsichtig formuliert, keine Pauschalschuld |
| Pointe + Frage | Parkbank mit Kühlpack, „brauche ich drei“, Papierstapel mit Brautpaar, WER ZAHLT? WER HAFTET? WER IST SCHULD? + Abstimmung in den Kommentaren |

```bash
cd src/unfall
python3 tts.py               # Stimmen (script.py: VOICES / LINES), Pausen straffen -> build/unfall/
python3 render.py            # rendert ../../unfall-video.mp4
python3 render.py preview 5 30   # Standbilder
```
Keine Rechtsberatung.

### unfall-video-erklaer.mp4 (gleiches Thema im Erklär-Format des Top-Videos)
Heller Erklär-Look wie Notwehr/Führerschein: getippte Headlines, Kapitel 1 Unfall · 2 Schäden · 3 Streit ·
4 Polizei · 5 Rechtslage · 6 3 goldene Tipps · 7 Fazit, Strichmännchen (Radfahrer türkis, Autofahrer orange, Polizei blau),
Gesetzes-Inhaltsverzeichnis, Polaroids mit Handschrift, animiertes Vorderrad mit Achter, Paragrafen-Seiten, Stempel,
Karaoke-Untertitel, Abstimmung Auto vs. Rad + „Speichern für den Ernstfall“ (wie Notwehr-Video). Ca. 75 s.
Quelle: `src/unfall2/` (`python3 tts.py && python3 render.py`).
