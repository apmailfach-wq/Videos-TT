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

## oma-frieda-faust-folge-1.mp4 (Serie „Oma Frieda Faust“, Folge 1)

**Titel:** Alle unterschätzen Oma Frieda · ca. 48 s · 1080×1920 · 30 fps · weicher 3D-Cartoon-Look
Aussehen Oma Frieda: grau-weißer Dutt, schmale runde Brille, Perlenkette, cremefarbene Strickjacke mit hellem Oberteil,
beiger Rock mit kleinen Punkten, braune Schuhe, braune Leder-Umhängetasche.
Format: „Eingefrorenes Bild – Plattenkratzer – Ich erklär's euch“ mit Loop (letzter Frame = erster Frame).

| Zeit | Szene |
|---|---|
| 0–2 s | Hook: zwei Diebe fliegen kopfüber über den Brunnen, Freeze + Plattenkratzer, „Sie haben die FALSCHE Oma beklaut 😳“, Oma: „Ich erklär's euch.“ |
| 2–9 s | Zurückspulen → „5 Minuten vorher …“, sonniger Park: strickt, füttert Tauben |
| 9–13 s | Tape-Stop, S/W-Foto 1976: Judo-Trainerin, „Schwarzer Gürtel.“ |
| 13–18 s | Bus: „Oma, der Platz ist besetzt.“ → „Der Blick 👀“ → Typ springt auf: „Bitte sehr, der Platz ist frei!“ |
| 18–27 s | Fitnessstudio: „Oma, Armdrücken? Gegen mich?“ → Oma strickt mit links weiter und knallt ihn mit rechts auf den Tisch → „Nächster?“ → zweiter Typ rennt weg |
| 27–34 s | „Und jetzt … die Diebe.“ – „Leichte Beute.“ – „Hilfe, Diebe!“ – Tauziehen, Oma lässt los, beide fliegen in Zeitlupe in den Brunnen |
| 34–41 s | Hustenbonbons für beide (einer per Schnipser in den Mund), Taube auf dem Kopf, „Danke, Oma.“, „Und nächstes Mal fragt ihr, ob ihr die Tasche tragen dürft.“ + Sicherheitstipp |
| 41–44 s | Heldenshot: „Mit Frieda Faust legt man sich nicht an!“ + Titel |
| 44–48 s | Abstimmung 1️⃣ Supermarkt 🛒 2️⃣ Schule 🏫 3️⃣ Disco 🪩 → Plattenkratzer, Freeze-Bild vom Anfang |

Stimmen: edge-tts (`de-DE-ChristophNeural` tief als Trailer-Erzähler, `de-AT-IngridNeural` als Oma, u. a.),
Musik und alle Soundeffekte werden in `render.py` synthetisch erzeugt.

```bash
cd src/omafrieda
python3 tts.py                          # Sprachzeilen mit festen Startzeiten -> build/omafrieda/
python3 render.py                       # rendert ../../oma-frieda-faust-folge-1.mp4
python3 render.py preview 0.3 14 25.9   # Standbilder -> build/omafrieda/stills/
```
- `script.py` – Text, Stimmen, Zeitfenster je Zeile · `chars.py` – Figuren (Oma Frieda, Dieb, Bus-Typ, Muskeltypen …)
- `world.py` – Park/Brunnen, Bus, Fitnessstudio, Foto · `shots.py` – Schnittliste · `gfx.py` – Soft-3D-Shader, Text

## oma-frieda-faust-folge-2.mp4 (Folge 2: Oma Frieda geht zur Schule – neue Fassung)

99 s (mit Extra-Gags, natürliche Stimmen) · 1080×1920 · 30 fps · natürlicherer Look (Hände mit Fingern, Schnürschuhe, Waden, gedeckte Farben, Filmkorn),
realistischer Schulhof (Betonbau, Asphalt mit Rissen, Graffiti, Fahrradständer, Dixi-Klos + Zettel „Toiletten defekt“).

| Zeit | Szene |
|---|---|
| 0–2 s | Hook: Achtklässler kippt nach Omas Fußfeger rückwärts ins Dixi, „Er hat sich mit der FALSCHEN Oma angelegt 😳“ |
| 2–8 s | „Heute Morgen …“: Oma kommt zur Schule (Dixis, Zettel), „Frau Faust“ an der Tafel – Vertretungslehrerin |
| 8–17 s | „Ey, die Oma ist unsere Lehrerin?“ – „Lacht ruhig. Ich hab schon eure Eltern unterrichtet.“ – Papierkügelchen auf der Stricknadel: „Zielen üben wir in Sport.“ |
| 17–27 s | „Handy weg. Ich hab achtzig Jahre ohne geschafft.“ – „Die Klos sind schon wieder kaputt!“ – „Kaputt gemacht, Kind. Das ist ein Unterschied.“ |
| 27–41 s | Große Pause: zwei Achtklässler nehmen einem Fünftklässler den Rucksack weg, „Ab ins Dixi mit dir!“ – Oma: „Zwei Große gegen einen Kleinen. Wie mutig.“ – „Ich bin achtzig. Ich halt mich aus gar nichts mehr raus.“ |
| 41–47 s | Griff → Schritt → Fußfeger (sichtbar, Zeitlupe) → er kippt ins Dixi, Tür knallt, BESETZT. „Du auch?“ – „Ich geh schon!“ (zweiter verschwindet selbst im Dixi) |
| 47–56 s | Hustenbonbon unter der Tür durch: „Riecht ja streng da drin.“ – Rucksack zurück: „Das ist nicht petzen. Das ist mutig.“ + Tipp gegen Mobbing |
| 56–63 s | „Mit Frieda Faust legt man sich nicht an!“ → Abstimmung 1️⃣ Supermarkt 2️⃣ Disco 3️⃣ Arztpraxis → Loop |

**Kurzfassung:** `oma-frieda-faust-folge-2-kurz.mp4` (75 s) – ohne Anwesenheit, „Faust? Wie die Hand?“, Handy-Szene,
„Duft der Bildung“, „Danke, Frau Faust!“ und „Sind Sie morgen wieder da?“; Schnitte nur zwischen ganzen Sätzen.

```bash
cd src/omafrieda2
python3 tts.py && python3 render.py      # -> ../../oma-frieda-faust-folge-2.mp4
```
Stimmen: Seraphina (Oma) und Florian (Erzähler) als Multilingual-Neural-Stimmen, Kinder über junge Frauenstimmen;
natürliche Sprechgeschwindigkeit, die Zeitachse wird pro Zeile gedehnt (`tts.py`, „warp“ in timeline.json).
Zusätzlich im Unterricht: „Anwesenheit! Wer fehlt, hebt die Hand.“ – „Wie alt sind Sie eigentlich?“ /
„Alt genug, um alle eure Ausreden zu kennen.“

Extra-Gags (als Einschübe, `script.py: INS`): „Der Duft der Bildung.“ – „Faust? Wie die Hand?“ / „Genau wie die Hand.“ –
„Stricken?“ / „Ich strick dir gleich 'nen Knoten in die Beine.“ – „Besetzt.“ – gedämpft aus dem Dixi: „Danke, Oma …“ –
„Sind Sie morgen wieder da?“ / „Kommt drauf an, wer frech ist.“

Nutzt Figuren/Grafik aus `src/omafrieda/`; neu: `world3.py` (Schulhof + Dixi-Klos), `shots3.py` (Schnittliste),
`world2.py` (Klassenzimmer).
