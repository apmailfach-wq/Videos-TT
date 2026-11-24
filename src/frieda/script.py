"""Frieda an der Supermarktkasse – Dialog & Stimmen (ca. 45 s)."""

VOICES = {
    # speaker: (edge-tts voice, rate, pitch[, ffmpeg-Filter])
    "frieda": ("de-AT-IngridNeural", "-2%", "-7Hz", "vibrato=f=5.5:d=0.035,volume=1.1"),  # wie in Oma Frieda Faust
    "typ":    ("de-AT-JonasNeural", "+12%", "+4Hz"),     # lässiger Drängler
    "typ_k":  ("de-AT-JonasNeural", "-6%", "+10Hz"),     # Drängler, kleinlaut/benommen
    "kasse":  ("de-DE-TanjaNeural", "+6%", "+0Hz"),      # Kassiererin
    "k2":     ("de-CH-LeniNeural", "+10%", "+6Hz"),      # Kundin in Rosa
    "k3":     ("de-DE-ChristophNeural", "-4%", "-12Hz", "volume=1.1"),  # älterer Herr, trocken
}

# (id, speaker, text) – Startzeiten legt render.py fest
LINES = [
    ("kas0", "kasse", "Der Nächste, bitte!"),
    ("fr0", "frieda", "Na endlich. Nur eine Gurke."),
    ("typ0", "typ", "Ja Bro, bin in zwei Minuten draußen."),
    ("k2a", "k2", "Hey! Da ist 'ne Schlange!"),
    ("typ1", "typ", "Sorry Oma, ich hab nur eine Sache."),
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
