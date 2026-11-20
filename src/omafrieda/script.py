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
    "muskel": ("de-CH-JanNeural", "+14%", "-6Hz", "volume=1.05"),                    # Fitness-Typ
    "lach":  ("de-AT-JonasNeural", "+10%", "-4Hz", "volume=0.9"),
    "dieb":  ("de-AT-JonasNeural", "-20%", "+18Hz", "volume=1.0"),
    "fluester": ("de-CH-JanNeural", "-6%", "-8Hz", "volume=0.9"),
    "kleinlaut": ("de-AT-JonasNeural", "+8%", "+22Hz", "volume=0.95"),
}

# (id, speaker, text, start_s, latest_end_s)
LINES = [
    ("oma1",  "oma",      "Ich erklär's euch.",                                          1.00, 1.95),
    ("erz1",  "erz",      "Das ist Frieda.",                                             3.20, 4.45),
    ("erz2",  "erz",      "Sie ist achtzig.",                                            4.60, 5.60),
    ("erz3",  "erz",      "Sie strickt.",                                                5.75, 6.60),
    ("erz4",  "erz",      "Sie füttert Tauben.",                                         6.75, 8.00),
    ("erz5",  "erz",      "Und sie war vierzig Jahre lang Judo-Trainerin.",              8.85, 11.40),
    ("erz5b", "erz",      "Schwarzer Gürtel.",                                           11.60, 12.65),
    ("jung1", "jung",     "Oma, der Platz ist besetzt.",                                 13.05, 14.55),
    ("jung2", "jung",     "Bitte sehr, der Platz ist frei!",                             16.65, 18.05),
    ("musk1", "muskel",   "Oma, Armdrücken? Gegen mich?",                                18.40, 20.65),
    ("lach1", "lach",     "Hahaha!",                                                     20.65, 21.20),
    ("oma5",  "oma",      "Na gut, Junge.",                                              21.35, 22.30),
    ("oma6",  "oma",      "Nächster?",                                                   25.00, 25.75),
    ("erz6",  "erz",      "Und jetzt … die Diebe.",                                      26.85, 28.35),
    ("dieb2", "fluester", "Leichte Beute.",                                              28.60, 29.50),
    ("oma2",  "omaruf",   "Hilfe, Diebe!",                                               30.35, 31.25),
    ("dieb1", "dieb",     "Aaaaaah!",                                                    33.05, 34.10),
    ("oma3",  "omaflott", "Hustenbonbon? Ihr seid ja ganz nass, Jungs.",                 34.50, 37.30),
    ("dieb3", "kleinlaut", "Danke, Oma.",                                                37.40, 38.30),
    ("oma7",  "omaflott", "Und nächstes Mal fragt ihr, ob ihr die Tasche tragen dürft.", 38.45, 41.15),
    ("oma4",  "oma",      "Mit Frieda Faust legt man sich nicht an!",                    41.65, 44.00),
    ("erz7",  "erz",      "Wo geht Oma Frieda als Nächstes hin?",                        44.55, 46.75),
]

TOTAL = 47.9
