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

## handy-weg-motivation.mp4 (Motivation-Short)

**Thema:** „Handy weg – leg los“: Motivation für Jugendliche, weniger zu scrollen und eine Stunde am Tag etwas für sich zu tun.
Länge ca. 46 s · 1080×1920 · 30 fps · Stimme `de-DE-FlorianMultilingualNeural` (+8 %)

Flat-Illustration auf knalligen Verlaufs-/Sunburst-Hintergründen, Cartoon-Kid im blauen Hoodie,
ein großes Wort pro Moment (Schlüsselwörter gelb), selbst synthetisierte Musik: düsterer Herzschlag-Teil,
Riser und Beat-Drop bei „Aber weißt du was?“. Szenen: Bildschirmzeit-Zähler · Endlos-Feed · andere trainieren/lernen/bauen ·
24-h-Uhr mit „App-Monster“ · Aufstehen, Handy fliegt weg · Handy in die Kiste, 60-Min-Timer, Sport/Lernen/Malen/Rausgehen ·
Jubel auf dem Hügel · Handy „OFF“ + Kommentar-Aufforderung.

```bash
cd src/motivation
pip install piper-tts
python3 tts_piper.py                # Thorsten-Stimme (lädt Modell nach build/voices) + Wort-Timings
# python3 tts.py                    # alternative: edge-tts
python3 render.py                   # rendert ../../handy-weg-motivation.mp4
python3 render.py preview 3 20 40   # Standbilder
```

## handy-redet-mit-dir.mp4 („Dein Handy redet mit dir“, Humor-Version)

**Konzept:** Das Handy ist ein klammernder Ex: Es spricht dich direkt an (quengelige, hochgepitchte Stimme, als Chat-Bubble),
ein trockener Erzähler kontert mit Punchlines („Dein Handy hat 100 % Akku. Du hast zwei.“, „Das ist kein Leben.
Das ist ein Ladebildschirm.“, „Die Likes warten. Deine Träume nicht.“). Schluss: Teilen-Aufforderung
„Schick das dem Freund mit der höchsten Bildschirmzeit“ + Bildschirmzeit-Ranking.

Länge ca. 50 s · Hook: schwarzer Screen, Stoppschild knallt rein, Bildschirm wackelt, Bass-Boom, „STOPP! Leg das Handy weg!“ · eigener Look: Neo-Brutalismus/Sticker-Stil (knallige Flächen mit Punktraster, dicke schwarze Outlines
und harte Schatten an allen Illustrationen, schräge Slam-Caption-Sticker, Emoji-Gags), Marimba-Beat mit
„Record-Stop“ bei den Pointen. Stimmen: `de-DE-AmalaNeural` (Handy, +22 Hz) und `de-DE-ConradNeural` (Erzähler).

```bash
cd src/handy2
python3 tts.py            # beide Stimmen + Wort-Timings -> build/handy2/
python3 render.py         # rendert ../../handy-redet-mit-dir.mp4
python3 render.py times   # Szenen-Zeitplan
```

## boss-fight-handy.mp4 – Serienformat „BOSS FIGHT #1: Du vs. dein Handy“

Wiedererkennbares Format im Stil eines Arcade-Prügelspiels (ca. 50 s): Neon-Arena, HP-Balken „DU vs. HANDY · BOSS“,
Ansager-Stimme („Runde eins. Kämpft!“), das Handy aus `handy2` als Boss, Projektile (🔔📱🌙🪫), Schadenszahlen,
Combo-Zähler, „LOW HP“, Spezialattacke (Schublade, Training, Lernen, Bauen), „K.O.“, „LEVEL UP +1 Disziplin“,
Teaser „Nächster Boss: ???“ + Folgen-Button. Chiptune-Beat mit Treffer-Sounds.
Nächste Folgen: einfach `src/bossfight/lines.py` (Texte) und `HITS` in `render.py` anpassen.

```bash
cd src/bossfight && python3 tts.py && python3 render.py
```

## drei-handys.mp4 – „Um 22 Uhr leuchtete bei allen dreien das Handy.“

Eigener Look „Midnight & Gold“ (Mitternachtsblau, Figurenfarben Violett/Türkis/Gold, goldener Jahresbalken, Sonnenaufgang im Fenster, warmes Türlicht; drei Zimmer übereinander, weiße Strichfiguren): AUSREDE hängt jede Nacht im Sitzsack (in Figurenfarbe) und scrollt mit beiden Händen, Knie angezogen (Handy mit laufendem Feed + Daumen, blaues Licht),
MOTIVATION hält zwei Tage durch, DISZIPLIN legt das Handy jeden Abend weg und steht jeden Morgen auf – Tageszähler
TAG 1 → 365, Fenster Nacht/Morgen, Tür ins Licht. Ende: „SEI DER EINE.“ + Kommentar-Frage „1, 2 oder 3?“.
Keine Stimme, nur Text + selbst erzeugter Ambient-Score (Drone, Klavier, Ticken, Wecker, Herzschlag). Ca. 42 s.
Sofort verständlich: Hook-Karte „3 TEENS. 1 HANDY. NUR EINER SCHAFFT'S.“, Sprechblasen („Nur noch 5 Minuten…“,
„Ab morgen wirklich!“, „Snooze…“), Zoom + „HANDY WEG.“ wenn Disziplin das Handy in die Schublade legt,
Aktivität hinter der Tür (⚽🏋️📚🏃…), Status-Emojis im Zeitraffer (😴 / 😩 / wachsendes 💪).

```bash
cd src/drei && python3 render.py
```
