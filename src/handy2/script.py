"""'Dein Handy redet mit dir' – humorous motivation short.

who = "phone" (clingy, pitched-up voice, shown as chat bubbles)
      "narr"  (dry, deep narrator, shown as big slam captions)
"""
VOICES = {
    "phone": {"voice": "de-DE-AmalaNeural", "rate": "+18%", "pitch": "+22Hz"},
    "narr":  {"voice": "de-DE-ConradNeural", "rate": "+12%", "pitch": "-4Hz"},
}

LINES = [
    ("hook",    "phone", "Hey! Nicht weiterscrollen. Ich bin's. Dein Handy."),
    ("stats",   "phone", "Wir hatten gestern sieben Stunden zusammen. Mit deiner Mama redest du sieben Minuten."),
    ("akku",    "narr",  "Dein Handy hat hundert Prozent Akku. Du hast zwei."),
    ("please",  "phone", "Komm schon. Nur noch ein Video."),
    ("count",   "narr",  "Das hast du vor siebenundvierzig Videos gesagt."),
    ("night",   "narr",  "Drei Uhr nachts. Du schaust, wie jemand Seife schneidet. Bruder, das ist kein Leben. Das ist ein Ladebildschirm."),
    ("offline", "narr",  "Jeder, den du feierst, hat sein Ding offline gebaut. Nicht im Feed."),
    ("plan",    "narr",  "Also: Eine Stunde am Tag. Handy in die Schublade. Training, lernen, irgendwas bauen."),
    ("panic",   "phone", "Was?! Und wer liked dann deine Storys?"),
    ("dreams",  "narr",  "Die Likes warten. Deine Träume nicht."),
    ("sad",     "phone", "Okay. Aber du kommst wieder, oder?"),
    ("update",  "narr",  "Klar. In einer Stunde. Als bessere Version."),
    ("cta",     "narr",  "Schick das dem Freund mit der höchsten Bildschirmzeit. Du weißt genau, wer gemeint ist."),
]
