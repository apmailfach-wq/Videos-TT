"""Frieda an der Supermarktkasse – Dialog & Stimmen (ca. 10 s Clip)."""

VOICES = {
    # speaker: (edge-tts voice, rate, pitch)
    "frieda":  ("de-AT-IngridNeural", "-4%", "-18Hz"),   # Oma, warm & trocken
    "typ":     ("de-AT-JonasNeural", "+12%", "+4Hz"),    # lässiger Drängler
    "kasse":   ("de-DE-TanjaNeural", "+6%", "+0Hz"),     # Kassiererin, beeindruckt
}

# (id, speaker, text) – Startzeiten legt render.py fest
LINES = [
    ("typ1", "typ", "Sorry Oma, ich hab nur eine Sache."),
    ("fr1", "frieda", "Ich auch."),
    ("kas1", "kasse", "Mit Karte oder bar?"),
    ("fr2", "frieda", "Mit Stil."),
]
