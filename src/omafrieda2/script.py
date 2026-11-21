"""Sprechertext für 'Oma Frieda Faust – Folge 2: Oma Frieda geht zur Schule'."""

VOICES = {
    "erz":   ("de-DE-ChristophNeural", "-4%", "-16Hz",
              "bass=g=5:f=110,aecho=0.8:0.5:40|75:0.18|0.10,volume=1.15"),
    "oma":   ("de-AT-IngridNeural", "-2%", "-7Hz", "vibrato=f=5.5:d=0.035,volume=1.1"),
    "omaflott": ("de-AT-IngridNeural", "+12%", "-7Hz", "vibrato=f=5.5:d=0.035,volume=1.1"),
    "gamer": ("de-AT-JonasNeural", "+10%", "+30Hz", "volume=1.0"),
    "girl":  ("de-DE-TanjaNeural", "+16%", "+38Hz", "volume=1.0"),
    "rowdy": ("de-CH-JanNeural", "+10%", "+14Hz", "volume=1.05"),
    "kleiner": ("de-AT-JonasNeural", "+8%", "+48Hz", "volume=1.0"),
}

# (id, speaker, text, start_s, latest_end_s)
LINES = [
    ("oma1",  "oma",      "Ich erklär's euch.",                               1.00, 1.95),
    ("erz1",  "erz",      "Das ist Frieda.",                                  3.20, 4.40),
    ("erz2",  "erz",      "Sie ist achtzig.",                                 4.55, 5.55),
    ("erz3",  "erz",      "Und heute ist sie Vertretungslehrerin.",           5.75, 8.30),
    ("girl1", "girl",     "Ey, die Oma ist unsere Lehrerin?",                 8.55, 10.30),
    ("lach1", "gamer",    "Hahaha!",                                          10.30, 10.90),
    ("girl2", "girl",     "Wooow!",                                           12.85, 13.40),
    ("erz4",  "erz",      "Vierzig Jahre Judo-Trainerin.",                    13.50, 15.40),
    ("oma2",  "oma",      "Handy weg. Erst Mathe.",                           16.20, 18.40),
    ("gam1",  "gamer",    "Mein Handy!",                                      18.50, 19.20),
    ("row1",  "rowdy",    "Her mit dem Pausenbrot, Kleiner!",                 19.90, 21.60),
    ("kle1",  "kleiner",  "Hey, das ist meins!",                              21.70, 22.80),
    ("oma3",  "oma",      "Junge. Gib das zurück.",                           23.10, 25.20),
    ("row2",  "rowdy",    "Was willst du denn, Oma?",                         25.35, 26.75),
    ("row3",  "rowdy",    "Aaaaaah!",                                         27.60, 28.60),
    ("oma4",  "omaflott", "Hustenbonbon? Du bist ja ganz sandig, Junge.",     29.30, 32.20),
    ("oma5",  "omaflott", "Und das Brot gehört dem Kleinen.",                 32.35, 34.20),
    ("kle2",  "kleiner",  "Danke, Frau Faust!",                               34.35, 35.55),
    ("oma6",  "oma",      "Mit Frieda Faust legt man sich nicht an!",         36.20, 38.50),
    ("erz5",  "erz",      "Wo geht Oma Frieda als Nächstes hin?",             39.15, 41.40),
]

TOTAL = 42.5
