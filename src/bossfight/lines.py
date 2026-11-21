"""BOSS FIGHT #1: Du vs. dein Handy – fighting-game format (series)."""
VOICES = {
    "phone": {"voice": "de-DE-AmalaNeural", "rate": "+18%", "pitch": "+22Hz"},   # the boss (same phone as before)
    "narr":  {"voice": "de-DE-ConradNeural", "rate": "+14%", "pitch": "-10Hz"},  # arena announcer
}
LINES = [
    ("hook",    "narr",  "Gestern hat dein Handy dich sieben Stunden lang besiegt. Heute: Revanche. Runde eins. Kämpft!"),
    ("boss",    "phone", "Haha! Ich hab hundert Benachrichtigungen. Was hast du?"),
    ("combo",   "narr",  "Combo-Angriff! Push-Nachricht! Reel! Noch ein Reel!"),
    ("crit",    "narr",  "Kritischer Treffer: Drei Uhr nachts. Zwei Prozent Akku. Deiner, nicht seiner."),
    ("giveup",  "phone", "Gib auf. Nur noch ein Video."),
    ("special", "narr",  "Nein. Jetzt kommt deine Spezialattacke!"),
    ("attacks", "narr",  "Handy in die Schublade! Training! Lernen! Etwas bauen!"),
    ("lose",    "phone", "Nein! Meine Bildschirmzeit!"),
    ("ko",      "narr",  "Knockout! Du gewinnst. Level up!"),
    ("cta",     "narr",  "Morgen kommt der nächste Boss. Folg mir, sonst gewinnt dein Handy."),
]
