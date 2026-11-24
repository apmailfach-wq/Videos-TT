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
    "frieda": ("de-AT-IngridNeural", "-6%", "-3Hz", ROOM),      # ruhig, trocken
    "typ":    ("de-AT-JonasNeural", "+3%", "+0Hz", ROOM),       # lässiger Drängler
    "typ_k":  ("de-AT-JonasNeural", "-12%", "+0Hz", ROOM),      # benommen / kleinlaut
    "kasse":  ("de-DE-TanjaNeural", "+0%", "+0Hz", ROOM),       # Kassiererin
    "k2":     ("de-CH-LeniNeural", "+4%", "+0Hz", ROOM_FAR),    # Kundin weiter hinten
    "k3":     ("de-DE-ChristophNeural", "-8%", "-4Hz", ROOM),   # älterer Herr, trocken
}

# (id, speaker, text) – Startzeiten legt render.py fest
LINES = [
    ("kas0", "kasse", "Der Nächste, bitte!"),
    ("fr0", "frieda", "Na endlich … Nur eine Gurke."),
    ("typ0", "typ", "Ja, Bro – bin in zwei Minuten draußen."),
    ("k2a", "k2", "Hey! Da ist 'ne Schlange!"),
    ("typ1", "typ", "Sorry, Oma – ich hab nur eine Sache."),
    ("fr1", "frieda", "Ich auch."),
    ("typ2", "typ", "Hä?"),
    ("k3a", "k3", "Willkommen am Ende der Schlange, junger Mann."),
    ("typ3", "typ_k", "Was … war das denn?"),
    ("kas2", "kasse", "Wo haben Sie das denn gelernt?"),
    ("fr3", "frieda", "Deutsche Meisterin. Neunzehnhundertvierundsiebzig."),
    ("kas3", "kasse", "Respekt! Das macht neunundvierzig Cent."),
    ("kas1", "kasse", "Mit Karte oder bar?"),
    ("fr2", "frieda", "Mit Stil."),
    ("typ4", "typ_k", "Bro … wird doch länger."),
]

# Für später (ElevenLabs, Modell eleven_v4 mit Regie-Tags wie [sighs], [dryly], [smug]) – Besetzung:
#   Frieda: "Elinor - The Gruff Aunt" (gDQfVolj9RbmXgumLcOq)   Typ: "Jordi Türmer" (9VeBtouyYRANyE97rZR1)
#   Kasse:  "Elke Collins" (Ns3AEOIovhjdrxad17pt)            Kundin: "Klara" (vPFocGjG5CEBbSByU2UY)
#   Herr:   "Philipp" (2O58da3udJ2JloNG1uP1)
