"""ALLTAG KLAR – Fahrradfahrer gegen Autofahrer: Wer zahlt den ganzen Wahnsinn?"""

VOICES = {
    # speaker: (edge-tts voice, rate, pitch)
    "erz":     ("de-DE-ConradNeural", "+32%", "-2Hz"),            # trockener Erzähler
    "auto":    ("de-DE-KillianNeural", "+26%", "-6Hz"),           # Autofahrer, ~40
    "radler":  ("de-DE-FlorianMultilingualNeural", "+30%", "+0Hz"),  # Radfahrer, ~35
    "polizei": ("de-DE-ChristophNeural", "+14%", "-8Hz"),          # genervter Beamter
}

LEAD = 1.15  # cold open (freeze frame + "WER ZAHLT?") before the first line

# (id, speaker, text, pause_after_seconds)
LINES = [
    ("e1", "erz", "Ein ganz normaler Tag.", 0.45),
    ("e2", "erz", "Bis zwei Verkehrsteilnehmer beschlossen, daraus ein juristisches Großprojekt zu machen!", 0.6),
    ("r1", "radler", "Mein Handy! Mein Fahrrad! Meine Hand! Wirtschaftlicher Totalschaden meines Lebens!", 0.2),
    ("a1", "auto", "Mein Auto! Meine Stirn! Ich wollte doch nur Brötchen holen!", 0.25),
    ("e3", "erz", "Handy kaputt, Fahrrad mit Achter, Schulter hinüber und eine Stirn mit neuem Design. Willkommen im Schadensmuseum!", 0.3),
    ("r2", "radler", "Sie bezahlen mein Handy und mein Fahrrad! Und meine Schulter!", 0.1),
    ("a2", "auto", "Und wer bezahlt meine Reparatur? Soll ich meine Stirn mit Ihrer Haftpflicht polieren lassen?", 0.1),
    ("r3", "radler", "Sie sind schuld!", 0.0),
    ("a3", "auto", "Sie sind mir vors Auto gefahren!", 1.3),
    ("e4", "erz", "Und weil der Unfall noch nicht teuer genug war, riskieren die beiden jetzt auch noch ein Strafverfahren!", 0.25),
    ("p1", "polizei", "Was ist denn hier passiert?", 0.05),
    ("a4", "auto", "Er ist mir vors Auto gefahren!", 0.0),
    ("r4", "radler", "Er hat mich umgefahren!", 0.1),
    ("p2", "polizei", "Und wer hat angefangen?", 0.75),
    ("e5", "erz", "Der Polizist wollte nur einen Unfall aufnehmen. Jetzt braucht er erst mal Urlaub.", 0.3),
    ("j0", "erz", "Aber jetzt wird's interessant:", 0.15),
    ("j1", "erz", "Nach Paragraf 7 Straßenverkehrsgesetz kann der Halter des Autos für Schäden beim Betrieb des Fahrzeugs haften.", 0.15),
    ("j2", "erz", "Aber Achtung: Wer wie viel zahlt, hängt von den genauen Umständen ab. Auch ein Mitverschulden des Radfahrers kann zählen.", 0.15),
    ("j3", "erz", "Handy und Fahrrad können ersetzt werden. Und für die Verletzungen kann es Schmerzensgeld geben, unter Umständen sogar für beide!", 0.15),
    ("j4", "erz", "Und die Rangelei? Wer dabei vorsätzlich jemanden verletzt, kann sich wegen Körperverletzung strafbar machen. Paragraf 223 Strafgesetzbuch.", 0.3),
    ("a5", "auto", "Haben Sie eigentlich eine Rechtsschutzversicherung?", 0.1),
    ("r5", "radler", "Nein. Aber nach heute brauche ich drei!", 0.4),
    ("e6", "erz", "Alltag klar: Ein kleiner Unfall. Fünf Schäden, drei Streitparteien und mehr Papierkram als bei einer Hochzeit!", 0.25),
    ("cta", "erz", "Wer zahlt? Wer haftet? Wer ist schuld? Schreib deine Meinung in die Kommentare!", 1.6),
]
