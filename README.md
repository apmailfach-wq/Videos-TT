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

## was-waere-wenn-teil1.mp4 (Low-Poly-3D-Kurzfilm)

**„Was wäre, wenn der schönste Himmel deines Lebens der letzte wäre?“** – 45 s · 1080×1920 · 30 fps ·
Ich-Perspektive auf einer Frankfurter Straße bei Nacht, ruhiger „Simulations“-Look, ohne Sprecher (alles über Text verständlich).
Oben links immer „DEIN AKKU“ (34 % → 0 %) mit szenenabhängiger Zeile, Untertitel kursiv im unteren Drittel.

| Zeit | Szene | Akku · Zeile |
|---|---|---|
| 0–2 s | Polarlichter + Titelfrage, Blick nach oben | 34 % |
| 2–7 s | Skyline, Menge filmt, du filmst mit | 34 % · Stärkster Sturm seit 1859 |
| 7–11 s | Laternen und Fenster gehen aus, „Kein Netz“, Polarlichter heller/röter | 31 % · Kein Netz |
| 11–16 s | Heller Streifen, Menge jubelt | 28 % · Zeit bis zum Einschlag 5…1 s |
| 16–20 s | Weißer Blitz, Feuerball hinter der Skyline | 24 % · Mehr Energie als alle Atomwaffen der Welt |
| 20–24 s | Erdbeben, Risse, Autos springen, Handys fallen | 19 % · Bodenwelle · 20 s nach dem Einschlag |
| 24–29 s | 1 s Stille, dann Luftwand: Scheiben bersten, Autos überschlagen sich | 13 % · 5 Minuten nach dem Einschlag |
| 29–34 s | Am Boden: brennende Trümmer, Staub verschluckt den Himmel | 6 % · Staub verdunkelt den Himmel |
| 34–42 s | Wendung: gesprungenes Handy spielt die Polarlicht-Aufnahme ab, Ascheregen, Akku leer | 1 % → 0 % |
| 42–45 s | Endkarte „Was wäre, wenn … Teil 1“ / Teil 2: Die Sonne verschwindet | 0 % |

```bash
cd src/waswaere
npm install                 # three.js 0.170
python3 audio.py            # Sounddesign (numpy) -> build/waswaere/audio.wav
./render_all.sh             # 1350 Frames, 3 parallele Headless-Chromium-Prozesse (~1 h, SwiftShader)
node render.mjs stills /tmp/st 0.5 14 27.3 36    # einzelne Standbilder
```

- `film.js` – komplette Szene (three.js): ray-marched Polarlichter im Himmels-Shader, Straße, Menge, Autos,
  Meteor, Feuerball, Druckwelle, Glassplitter, Trümmer, Staub, Handy-Nahaufnahme; HUD/Untertitel als 2D-Overlay.
  Jeder Zustand ist eine reine Funktion der Zeit → jeder Frame ist einzeln renderbar.
- `timeline.js` – Texte, Akkustände, HUD-Zeilen und Zeiten.
- `fonts/PlayfairDisplay*` – Playfair Display / SC (SIL Open Font License).
