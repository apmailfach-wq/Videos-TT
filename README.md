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

## ueberleben-folge2.mp4 („Überlebst du das?“ – Folge 2)

**Thema:** Mit dem Auto von der Brücke in den Fluss – Tür oder Fenster?
Genau 30,0 s · 1080×1920 · 30 fps · Cartoon-Look, dunkle Töne, Wasser blaugrün, Gefahr rot · kein Voiceover, nur Sounddesign.
Oben durchgehend der „ÜBERLEBEN“-Balken in Prozent; alle Texte deutsch, weiß mit schwarzer Kontur, mit Impact-Effekt und leichtem Wackeln.
Kamera wechselt alle 1–1,5 s (24 Einstellungen), jede Einstellung bewegt sich.

| Zeit | Inhalt | Text |
|---|---|---|
| 0–2 s | Auto durchbricht das Geländer, Zeitlupen-Sturz | DIE MEISTEN STERBEN HIER. |
| 2–4 s | Unterwasser: Auto stürzt auf die Kamera zu, Blasenexplosion | – |
| 4–8 s | Innenraum, Wasser bis zur Brust, Buttons A/B, Timer 3…2…1, Herzschlag | WAS MACHST DU? |
| 8–14 s | A: Türgriff, Druckpfeile außen + Draufsicht, Licht aus → alles blau, Balken rot | FALSCH. DAS WASSER DRÜCKT DIE TÜR ZU. |
| 14–15 s | Rewind (VHS-Rücklauf), B wird gewählt | NOCHMAL. |
| 15–22 s | B: Gurt, Fenster runter, raus, Richtung Licht, Auftauchen + Atemzug, Balken grün | GURT. FENSTER. RAUS. SOFORT. |
| 22–26 s | Fenster klemmt → Nothammer in die Ecke, Glas zerspringt in Zeitlupe | FENSTER KLEMMT? IN DIE ECKE SCHLAGEN! |
| 26–30 s | Close-up, Blick in die Kamera, harter Schnitt (Loop) | EHRLICH: A ODER B? 👇 · Folge 3 morgen |

Look: Cel-Shading + Randlicht an der Figur, Glow auf echten Lichtern, animierte Unterwasser-Kaustiken,
Motion Blur in schnellen Einstellungen, Whip-Blur auf jedem Schnitt, Grading (unter Wasser dunkel blaugrün, Variante A rote Ränder,
Licht aus → blau), Filmkorn, Vignette.

Ton (Stereo, komplett synthetisiert): Moll-Drohne mit Sidechain-Ducking, Sub-Puls (schneller in der Flucht), Braams auf
Crash / „FALSCH.“ / „FENSTER KLEMMT?“, Riser in jeden Wendepunkt, Sub-Drops, Impact + Whoosh auf jedem Schnitt, Uhrticken +
Herzschlag + Countdown-Piepen, Türgriff, Druck-Ächzen, Stromausfall, Rewind, Gurt-Klick, Fensterheber, Luftschnappen,
Dur-Akkord beim Auftauchen, Glas, Hall; unter Wasser alles dumpf; Stille direkt vor dem Finale, dann leiser Herzschlag.

```bash
cd src/ueberleben
python3 render.py                  # -> ../../ueberleben-folge2.mp4
python3 render.py preview 5 12.9   # Standbilder -> build/ueberleben/stills/
```
`draw.py` (Kamera-Pen mit 2× Supersampling, Auto, Figur, Hand, Blasen) · `shots.py` (alle Einstellungen) ·
`render.py` (Schnittliste, Balken, Impact-Texte, Buttons, Timer, Rewind, Grading, Sounddesign, ffmpeg).

**Beschreibung:** Die meisten würden hier falsch entscheiden. Du auch? 🚗💦 Folge 2 – „Überlebst du das?“
**Hashtags:** #überlebstdudas #survival #notfall #wasweresdu #wissen #lifehack #fürdich #fyp #deutschland

## wildunfall-folge3.mp4 („Überlebst du das?“ – Folge 3: Wildunfall)

48,2 s · 1080×1920 · 30 fps · Stereo · Draufsicht-Format (wie virale „Was tun auf Glatteis?“-Clips), ruhig erzählt mit Action.
Voiceover: edge-tts `de-DE-ChristophNeural` (+8 %), Untertitel Wort-für-Wort (Nunito Black, Schlüsselwörter gelb).

| Abschnitt | Inhalt |
|---|---|
| Hook | Nachts auf der Landstraße – Reh springt ins Fernlicht, Augen leuchten |
| Instinkt | Karte „LENKRAD REISSEN“, Auto weicht aus → Freeze „FALSCH!“ → Schleudern, Baum, Laub fliegt |
| Zurückspulen | VHS-Rücklauf bis vor das Reh |
| Richtig | „LENKRAD FEST“, „VOLL BREMSEN“ (ABS, Bremsspuren), „HUPEN“, „ABBLENDEN“ – Auto steht, Reh springt weg, zwei weitere folgen |
| Vergleich | Karten REH vs. BAUM (Gefahrenbalken) |
| Danach | Warnblinker, Warnweste, Warndreieck, Polizei rufen |
| Merk dir | NICHT AUSWEICHEN · FESTHALTEN · BREMSEN |
| Frage | „Ehrlich: Wärst du ausgewichen? 👇“ – leuchtende Augen im Wald |

Grafik: Vektor-Engine mit 2× Supersampling, Echtzeit-Lichtkarte (Fern-/Abblendlicht-Kegel, Rück-/Bremslicht,
Warnblinker, Leitpfosten-Reflexe, Augenreflexe), Tone-Mapping, Glow, Bodennebel, Herbstwald, Filmkorn.
Ton: Stimme + ruhige Spannungs-Pads mit Ducking, tempoabhängiger Motor/Reifen, Eule, Quietschen, Crash + Tinnitus,
Tape-Rewind, ABS-Bremse, Hupe, Relais, Schritte, DTMF 110 – alles synthetisiert.

```bash
cd src/wildunfall
python3 tts.py       # Stimme + Wort-Timings
python3 render.py    # -> ../../wildunfall-folge3.mp4
```
Fakten (ADAC/DVR): bei Wild auf der Fahrbahn abblenden, hupen, bremsen; bei unvermeidbarem Zusammenstoß Lenkrad
festhalten, nicht ausweichen; danach Unfallstelle sichern und Polizei rufen, Tier nicht anfassen.

**Beschreibung:** Würdest du ausweichen? Genau das ist der Fehler. 🦌🚗 Folge 3 – „Überlebst du das?“
**Hashtags:** #überlebstdudas #wildunfall #wildwechsel #autofahren #führerschein #wissen #lifehack #fürdich #fyp #deutschland
