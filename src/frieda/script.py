"""Frieda an der Supermarktkasse – Dialog & Stimmen (ca. 10 s Clip)."""

VOICES = {
    # speaker: (edge-tts voice, rate, pitch[, ffmpeg-Filter])
    "frieda":  ("de-AT-IngridNeural", "-2%", "-7Hz", "vibrato=f=5.5:d=0.035,volume=1.1"),  # wie in Oma Frieda Faust
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
