# Videos-TT

Automatisch generierte TikTok-Videos (1080×1920, 30 fps) – komplett per Code gerendert.

## notwehr-video.mp4

**Thema:** Strafe nach einer Schlägerei, wenn man selbst angegriffen wurde (Rechtslage in Deutschland)
Länge ca. 85 s · Voiceover: edge-tts `de-AT-JonasNeural` (+12 % Tempo)

| Abschnitt | Zeit | Inhalt |
|---|---|
| 0–6 s | „Frieda geht einkaufen 🛒“ – „Der Nächste!“ – Frieda: „Eine Gurke. Was soll da schon schiefgehen?“ |
| 6–14 s | Typ am Handy: „Bro, zwei Minuten. Ich drängel mich vor.“ – „Hallo?! Hier ist 'ne Schlange!“ – „Sorry Oma, ich hab nur eine Sache.“ |
| 14–17 s | Musik weg, Close-up: „Ich auch.“ – „Hä?“ |
| 17–22 s | Zeitlupe: Judo-Hüftwurf ans Ende der Schlange, **IPPON!** + Gong, Applaus |
| 22–28 s | „Hinten anstellen, Junge. Ach – bist ja schon da.“ – „Hat mich grad 'ne Oma geworfen?“ |
| 28–35 s | „Wo lernt man denn so was?“ – Rückblende (Sepia): „Deutsche Meisterin. 1974.“ |
| 35–41 s | Gurke aufs Band – „Respekt! 0,49 €.“ – „Mit Karte oder bar?“ |
| 41–48 s | Close-up mit Strickzeug: „Mit Stil.“ + Zwinkern – „Bro … die Oma ist Endgegner.“ – „Das ist Frieda.“ |

Caption: `Vordrängeln? Nicht bei Frieda 🥋 #omafrieda #judooma #supermarkt #oma #comedy #fyp`

```bash
cd src/frieda
python3 tts.py       # Stimmen (script.py): edge-tts ohne Tonhöhen-Verbiegung + Supermarkt-Raumklang per ffmpeg
python3 render.py    # -> ../../frieda-supermarkt.mp4  (Timing oben in render.py: T_LINE, T_GRAB, CAM_KEYS …)
python3 render.py preview 4.6 5.6 9.6   # Standbilder
```
