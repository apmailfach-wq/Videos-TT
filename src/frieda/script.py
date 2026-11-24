"""Frieda an der Supermarktkasse – Dialog & Stimmen (ca. 45 s).

Natürlicher Klang: kaum Tonhöhen-/Tempo-Verbiegung (die klingt synthetisch), Pausen über Satzzeichen,
danach ein kleiner Supermarkt-Raumklang (EQ, sanfte Kompression, kurzer Hall); Kunden weiter hinten klingen
etwas entfernter.
Hinweis: Bei edge-tts klingen alle de-DE-Stimmen wie Tanja (w) bzw. Christoph (m) – unterscheidbar sind nur
Tanja, Christoph, Ingrid/Jonas (AT) und Leni/Jan (CH).
"""

ROOM = ("highpass=f=85,lowpass=f=10500,"
        "equalizer=f=220:t=q:w=1.2:g=-2,equalizer=f=3200:t=q:w=1.5:g=2,"
        "acompressor=threshold=-20dB:ratio=2.5:attack=6:release=90:makeup=2,"
        "aecho=0.9:0.5:19|37:0.10|0.06")
ROOM_FAR = ("highpass=f=110,lowpass=f=7500,"
            "acompressor=threshold=-20dB:ratio=2.5:attack=6:release=90:makeup=2,"
            "aecho=0.85:0.55:23|47|71:0.16|0.10|0.06")

VOICES = {
    # speaker: (edge-tts voice, rate, pitch, ffmpeg-Filter)
    "frieda": ("de-AT-IngridNeural", "-2%", "-3Hz", ROOM),      # ruhig, trocken
    "typ":    ("de-AT-JonasNeural", "+3%", "+0Hz", ROOM),       # lässiger Drängler
    "typ_f":  ("de-AT-JonasNeural", "+12%", "+0Hz", ROOM),      # gehetzt am Handy
    "typ_b":  ("de-AT-JonasNeural", "-8%", "-8Hz", ROOM),      # leise-bedrohlich
    "musk":   ("de-CH-JanNeural", "-6%", "-6Hz", ROOM),         # Muskelprotz, kleinlaut
    "tel":    ("de-AT-JonasNeural", "+14%", "+18Hz",
               "highpass=f=450,lowpass=f=3200,acrusher=bits=10:mix=0.25,volume=0.9"),  # Kumpel am Handy
    "typ_k":  ("de-AT-JonasNeural", "-12%", "+0Hz", ROOM),      # benommen / kleinlaut
    "kasse":  ("de-DE-TanjaNeural", "+0%", "+0Hz", ROOM),       # Kassiererin
    "k2":     ("de-CH-LeniNeural", "+4%", "+0Hz", ROOM_FAR),    # Kundin weiter hinten
    "k3":     ("de-DE-ChristophNeural", "-8%", "-4Hz", ROOM),   # älterer Herr, trocken
}

# (id, speaker, gesprochener Text[, Text in der Sprechblase]) – Startzeiten legt render.py fest
LINES = [
    ("kas0", "kasse", "Der Nächste!"),
    ("fr0", "frieda", "Eine Gurke. Was soll da schon schiefgehen?"),
    ("typ0", "typ_f", "Bro, zwei Minuten. Ich drängel mich vor."),
    ("k2a", "k2", "Hallo?! Hier ist 'ne Schlange!"),
    ("typ1", "typ", "Sorry, Oma – ich hab nur eine Sache.", "Sorry Oma, ich hab nur eine Sache."),
    ("fr1", "frieda", "Ich auch."),
    ("typ2", "typ", "Hä? Was willst du machen – mich wegstricken?"),
    ("fr4", "frieda", "Letzte Chance, Bürschchen. Ab nach hinten."),
    ("typ5", "typ_b", "Sonst was … Oma?"),
    ("fr5", "frieda", "Sonst … das hier."),
    ("mk1", "musk", "Ich … stell mich mal hinten an."),
    ("k3a", "k3", "Hinten anstellen, Junge. Ach – bist ja schon da.", "Hinten anstellen, Junge. Ach – bist ja schon da."),
    ("typ3", "typ_k", "Hat mich grad 'ne Oma geworfen?"),
    ("kas2", "kasse", "Wo lernt man denn so was?"),
    ("fr3", "frieda", "Deutsche Meisterin. Vierundsiebzig.", "Deutsche Meisterin. 1974."),
    ("kas3", "kasse", "Respekt! Neunundvierzig Cent.", "Respekt! 0,49 €."),
    ("kas4", "kasse", "Und sein Energy-Drink?"),
    ("fr6", "frieda", "Den zahlt er … hinten."),
    ("kas1", "kasse", "Mit Karte oder bar?"),
    ("fr2", "frieda", "Mit Stil."),
    ("typ4", "typ_k", "Bro … die Oma ist Endgegner."),
    ("tel", "tel", "Frieda?! Bro … lauf!"),
]

# Für später (ElevenLabs, Modell eleven_v4 mit Regie-Tags wie [sighs], [dryly], [smug]) – Besetzung:
#   Frieda: "Elinor - The Gruff Aunt" (gDQfVolj9RbmXgumLcOq)   Typ: "Jordi Türmer" (9VeBtouyYRANyE97rZR1)
#   Kasse:  "Elke Collins" (Ns3AEOIovhjdrxad17pt)            Kundin: "Klara" (vPFocGjG5CEBbSByU2UY)
#   Herr:   "Philipp" (2O58da3udJ2JloNG1uP1)
