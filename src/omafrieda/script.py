"""Sprechertext für 'Oma Frieda Faust – Folge 1'. Jede Zeile hat einen festen Startpunkt (Sekunden)
und ein spätestes Ende; ist die TTS-Zeile zu lang, wird sie per atempo eingepasst."""

VOICES = {
    # speaker: (edge-tts voice, rate, pitch, ffmpeg post filter)
    "erz":   ("de-DE-ChristophNeural", "-4%", "-16Hz",
              "bass=g=5:f=110,aecho=0.8:0.5:40|75:0.18|0.10,volume=1.15"),          # Trailer-Erzähler
    "oma":   ("de-AT-IngridNeural", "-2%", "-7Hz", "vibrato=f=5.5:d=0.035,volume=1.1"),  # Oma Frieda
    "omaruf": ("de-AT-IngridNeural", "+18%", "+4Hz", "vibrato=f=5.5:d=0.03,volume=1.35"),
    "omaflott": ("de-AT-IngridNeural", "+12%", "-7Hz", "vibrato=f=5.5:d=0.035,volume=1.1"),
    "jung":  ("de-AT-JonasNeural", "+6%", "+2Hz", "volume=1.0"),                    # Typ im Bus
    "muskel": ("de-CH-JanNeural", "+4%", "-6Hz", "volume=1.05"),                    # Fitness-Typ
    "lach":  ("de-AT-JonasNeural", "+10%", "-4Hz", "volume=0.9"),
    "dieb":  ("de-AT-JonasNeural", "-20%", "+18Hz", "volume=1.0"),
}

# (id, speaker, text, start_s, latest_end_s)
LINES = [
    ("oma1",  "oma",    "Ich erklär's euch.",                                1.00, 1.95),
    ("erz1",  "erz",    "Das ist Frieda.",                                   3.00, 4.25),
    ("erz2",  "erz",    "Sie ist achtzig.",                                  4.40, 5.40),
    ("erz3",  "erz",    "Sie strickt.",                                      5.55, 6.40),
    ("erz4",  "erz",    "Sie füttert Tauben.",                               6.55, 7.80),
    ("erz5",  "erz",    "Und sie war vierzig Jahre lang Judo-Trainerin.",    8.35, 10.90),
    ("jung1", "jung",   "Oma, der Platz ist besetzt.",                       11.15, 12.65),
    ("lach1", "lach",   "Hahaha!",                                           16.05, 16.60),
    ("musk1", "muskel", "Oma, die Hantel ist zu schwer für dich!",           16.65, 18.45),
    ("erz6",  "erz",    "Und jetzt … der Dieb.",                             21.10, 22.55),
    ("oma2",  "omaruf", "Hilfe, Dieb!",                                      23.25, 24.30),
    ("dieb1", "dieb",   "Aaaaaah!",                                          25.25, 26.25),
    ("oma3",  "omaflott", "Hustenbonbon? Du bist ja ganz nass, Junge.",      26.55, 29.10),
    ("oma4",  "oma",    "Mit Frieda Faust legt man sich nicht an!",          29.45, 31.80),
    ("erz7",  "erz",    "Wo geht Oma Frieda als Nächstes hin?",              32.10, 34.30),
]

TOTAL = 35.0
