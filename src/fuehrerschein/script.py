"""Dialogue/voice script for 'Gestern gewonnen, heute den Führerschein verloren?'."""

VOICES = {
    # speaker: (edge-tts voice, rate, pitch)
    "erz":     ("de-DE-TanjaNeural", "+10%", "+0Hz"),     # Erzählerin
    "rafael":  ("de-AT-JonasNeural", "+10%", "+0Hz"),      # ca. 30
    "klaus":   ("de-DE-ConradNeural", "+0%", "-10Hz"),     # 55
    "polizei": ("de-DE-ConradNeural", "+4%", "+5Hz"),
}

# (id, speaker, text, pause_after_seconds)
LINES = [
    ("hook1", "erz", "Gestern hat Deutschland gewonnen.", 0.15),
    ("hook2", "erz", "Heute verlieren zwei Kollegen ihren Führerschein.", 0.5),
    ("raf1", "rafael", "Darauf gönn ich mir einen!", 0.3),
    ("kla1", "klaus", "Noch eine Runde! Auf Deutschland!", 1.2),
    ("night", "erz", "Die Nacht vergeht – doch THC und Alkohol bauen sich nur langsam ab.", 1.0),
    ("raf2", "rafael", "Zehn Stunden her. Alles weg, Bro.", 0.2),
    ("kla2", "klaus", "Paar Bier, geschlafen, passt schon.", 0.15),
    ("wirk", "erz", "Wirklich?", 4.2),
    ("pol1", "polizei", "Cannabis konsumiert in letzter Zeit?", 0.3),
    ("pol2", "polizei", "Einmal kräftig pusten, bitte.", 0.8),
    ("f1", "erz", "Der THC-Grenzwert liegt bei 3,5 Nanogramm pro Milliliter Blutserum. Eine sichere Wartezeit gibt es nicht.", 0.3),
    ("f2", "erz", "Ab 0,5 Promille oder 3,5 Nanogramm THC – beim ersten Verstoß: 500 Euro, zwei Punkte und ein Monat Fahrverbot.", 0.3),
    ("f3", "erz", "Schon ab 0,3 Promille mit Fahrfehler oder Ausfallerscheinungen ist es eine Straftat.", 0.3),
    ("f4", "erz", "Cannabis und Alkohol zusammen: mindestens 1.000 Euro.", 0.3),
    ("f5", "erz", "Und in der Probezeit oder unter 21 gilt: null Toleranz.", 0.7),
    ("kla3", "klaus", "Deutschland hat gewonnen …", 0.15),
    ("raf3", "rafael", "… und wir haben verloren.", 0.4),
    ("bus", "erz", "Nach der Party: Bus, Bahn oder Taxi.", 0.3),
    ("cta", "erz", "Wie habt ihr den Sieg gefeiert? Und wusstet ihr, wie gefährlich Restalkohol am nächsten Morgen ist? Ab in die Kommentare!", 1.6),
]
