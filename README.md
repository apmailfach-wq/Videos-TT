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

## frieda-supermarkt.mp4 (Oma Frieda an der Kasse, 64 s)

Alle Figuren im Stil von „Oma Frieda Faust“ (`src/frieda/fchars.py` + `fgfx.py`, übernommen aus `src/omafrieda/`,
Branch `claude/oma-frieda-faust-tiktok-vicu2i`). Frieda im aktuellen Outfit (korallrote Bluse, Perlenkette, rote
Blumenbrosche, roter Blümchenrock, rote Schuhe, rosa Strickzeug). Drängler: Cap + Kopfhörer, „NO RULES“-Hoodie,
Sonnenbrille, Energy-Drink. Dazu Kassiererin, Kundin in Orange, Muskelprotz, Mädchen, älterer Herr, Kunde vorne.
Supermarkt mit Deckenlicht, Gang-Schildern, Regalen mit Preisschildern, Obststand; Kasse mit Laufband, Warentrenner,
Scanner, Kassenmonitor, Kartenterminal (zeigt Summe/„Karte?“), Kassenlicht „1“ und Quengelregal.

| Zeit | Inhalt |
|---|---|
| 0–6 s | „Frieda geht einkaufen 🛒“ – „Der Nächste!“ – Frieda: „Eine Gurke. Was soll da schon schiefgehen?“ |
| 6–14 s | Typ am Handy: „Bro, zwei Minuten. Ich drängel mich vor.“ – „Hallo?! Hier ist 'ne Schlange!“ – „Sorry Oma, ich hab nur eine Sache.“ |
| 14–26 s | Schuss/Gegenschuss: „Ich auch.“ – „Hä? Was willst du machen – mich wegstricken?“ – „Letzte Chance, Bürschchen. Ab nach hinten.“ – (Brille ab, Faust, rotes Licht) „Sonst was … Oma?“ – „Sonst … das hier.“ |
| 26–30 s | Zeitlupe: Judo-Hüftwurf ans Ende der Schlange, die Energy-Drink-Dose fliegt weg – Frieda fängt sie blind. **IPPON!** + Gong |
| 30–33 s | Wertungstafeln wie bei Olympia: „10“, „10“, „10“ … das Mädchen: „9,5“. Muskelprotz: „Ich … stell mich mal hinten an.“ |
| 33–40 s | „Hinten anstellen, Junge. Ach – bist ja schon da.“ – „Hat mich grad 'ne Oma geworfen?“ |
| 40–46 s | „Wo lernt man denn so was?“ – Rückblende (Sepia): „Deutsche Meisterin. 1974.“ |
| 46–55 s | Gurke + Dose aufs Band – „Respekt! 0,49 €.“ – „Und sein Energy-Drink?“ – „Den zahlt er … hinten.“ – „Mit Karte oder bar?“ |
| 55–64 s | Close-up: „Mit Stil.“ + Zwinkern – „Bro … die Oma ist Endgegner.“ – Kumpel am Handy: „Frieda?! Bro … lauf!“ – „Das ist Frieda.“ |

### Kurzfassung: `frieda-supermarkt-kurz.mp4` (46 s, für TikTok)

| Zeit | Inhalt |
|---|---|
| 0–2 s | **Cold Open:** Wurf in Zeitlupe, Freeze am höchsten Punkt – „Er hat sich vor der falschen Oma vorgedrängelt 😳“ – Rückspulen „⏪ Kurz vorher …“ |
| 2–7 s | Typ drängelt sich vor: „Ich zahl jetzt. Sie warten hier – ich hab keine Zeit.“ |
| 7–28 s | Gespräch (Schuss/Gegenschuss): „Ich auch nicht, junger Mann.“ – „Oma, chill. Du hast doch den ganzen Tag Zeit.“ – „Junge, ich bin achtzig. Ich hab am wenigsten Zeit von allen.“ – „Ja und? Was willst du machen – mich wegstricken?“ – „Letzte Chance, Bürschchen. Ab nach hinten.“ – (Brille ab, Faust) „Sonst was … Oma?“ – „Sonst … das hier.“ |
| 28–33 s | Wurf, **IPPON!**, Wertungstafeln (10 – 10 – 9,5), Frieda fängt die Dose |
| 33–41 s | „Und sein Energy-Drink?“ – „Den zahlt er … hinten.“ – „Mit Karte oder bar?“ – „Mit Stil.“ + Zwinkern |
| 41–46 s | „Bro … die Oma ist Endgegner.“ – „Frieda?! Bro … lauf!“ + „Das ist Frieda.“ – harter Schnitt |

Quelle: `src/frieda/render_short.py` (nutzt Figuren/Sets aus `render.py`, eigene Zeitleiste):
`cd src/frieda && python3 tts.py && python3 render_short.py`

Caption: `Vordrängeln? Nicht bei Frieda 🥋 #omafrieda #judooma #supermarkt #oma #comedy #fyp`

```bash
cd src/frieda
python3 tts.py       # Stimmen (script.py): edge-tts ohne Tonhöhen-Verbiegung + Supermarkt-Raumklang per ffmpeg
python3 render.py    # -> ../../frieda-supermarkt.mp4  (Timing oben in render.py: T_LINE, T_GRAB, CAM_KEYS …)
python3 render.py preview 15 23.5 28 42.5   # Standbilder
```
