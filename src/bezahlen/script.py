"""Sprechertext je Szene (feste Zeitfenster, 60 s gesamt)."""
VOICE = "de-DE-ConradNeural"   # ruhige, tiefe Erzählstimme

# start/end = Zeitfenster der Szene im Video (Sekunden)
SCENES = [
    {"key": "titel",   "start": 0,  "end": 3,  "text": "Drei Leute, gleiches Geld, gleicher Einkaufszettel. Wer gibt mehr aus?"},
    {"key": "start",   "start": 3,  "end": 8,  "text": "Jeder kauft dasselbe. Aber jeder zahlt anders."},
    {"key": "woche1",  "start": 8,  "end": 16, "text": "Mit Karte und Handy geht es schneller. Und es kommt mehr dazu."},
    {"key": "falsch",  "start": 16, "end": 22, "text": "Also ist das Handy am schlimmsten? Noch nicht."},
    {"key": "push",    "start": 22, "end": 30, "text": "Das Handy zeigt jede Zahlung sofort an. Und das tut weh – fast wie Bargeld."},
    {"key": "bar",     "start": 30, "end": 38, "text": "Und Bargeld? Kleingeld taucht in keiner App auf. Es fühlt sich an wie geschenkt."},
    {"key": "karte",   "start": 38, "end": 44, "text": "Nur eine Figur spürt gar nichts."},
    {"key": "endstand","start": 44, "end": 50, "text": "Die Karte gewinnt. Aber nicht so deutlich, wie alle denken."},
    {"key": "schmerz", "start": 50, "end": 57, "text": "Du gibst weniger aus, wenn du siehst, dass Geld weggeht."},
    {"key": "ende",    "start": 57, "end": 60, "text": "Wie zahlst du? Schreib's in die Kommentare."},
]
