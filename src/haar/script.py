VOICE = "de-AT-JonasNeural"   # Erzähler
RATE = "+16%"
KEVIN = dict(voice="de-DE-ChristophNeural", rate="+14%", pitch="+12Hz")
KELLNER = dict(voice="it-IT-DiegoNeural", rate="+6%", pitch="+0Hz")

SCENES = [
    {"key": "k1", **KEVIN, "text": "Ey! Da ist ein Haar drin! Ich zahl gar nix!"},
    {"key": "n1", "text": "Kleines Problem: Kevin hat den ganzen Teller schon aufgegessen."},
    {"key": "w1", **KELLNER, "text": "Signore… der Teller ist komplett leer!"},
    {"key": "k2", **KEVIN, "text": "Ja Mann, das Haar war halt ganz unten!"},
    {"key": "w2", **KELLNER, "text": "Und warum ist das Haar… lila? Wie deine Haare?"},
    {"key": "k3", **KEVIN, "text": "Zufall."},
    {"key": "r1", "text": "Und was sagt das Recht? Ein Haar im Essen ist ein Mangel. Aber du musst sofort reklamieren – dann bekommst du einen neuen Teller. Wer erst aufisst und dann meckert, zahlt den vollen Preis."},
    {"key": "r2", "text": "Und hat Kevin das Haar selbst reingelegt, um nicht zu zahlen? Dann ist das versuchter Betrug, Paragraf 263 Strafgesetzbuch – bis zu fünf Jahre Haft."},
    {"key": "cta", "text": "Kennt ihr auch so einen Kevin? Markiert ihn in den Kommentaren!"},
]
