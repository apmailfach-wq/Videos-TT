"""'Dein Handy redet mit dir' – humorous motivation short.

who = "phone" (clingy, pitched-up voice, shown as chat bubbles)
      "narr"  (dry, deep narrator, shown as big slam captions)
"""
VOICES = {
    "phone": {"voice": "de-DE-AmalaNeural", "rate": "+18%", "pitch": "+22Hz"},
    "narr":  {"voice": "de-DE-ConradNeural", "rate": "+16%", "pitch": "-6Hz"},
}

LINES = [
    ("hook",    "narr",  "STOPP! Leg das Handy weg! Du scrollst gerade dein Leben weg!"),
    ("stats",   "phone", "Hör nicht auf ihn. Wir hatten gestern sieben Stunden zusammen. Mit deiner Mama redest du sieben Minuten."),
    ("akku",    "narr",  "Dein Handy hat hundert Prozent Akku. Du hast zwei."),
    ("please",  "phone", "Komm schon. Nur noch ein Video."),
    ("count",   "narr",  "Das hast du vor siebenundvierzig Videos gesagt."),
    ("night",   "narr",  "Drei Uhr nachts. Seifen-Videos. Bruder, das ist kein Leben. Das ist ein Ladebildschirm."),
    ("plan",    "narr",  "Handy weg. Ab in die Schublade. Eine Stunde am Tag. Training, lernen, bauen. Keine Ausreden!"),
    ("panic",   "phone", "Was?! Und wer liked dann deine Storys?"),
    ("dreams",  "narr",  "Die Likes warten. Deine Träume nicht."),
    ("cta",     "narr",  "Schick das dem Freund mit der höchsten Bildschirmzeit. Du weißt, wer gemeint ist."),
]
