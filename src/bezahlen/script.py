"""Sprechertext je Szene (feste Zeitfenster, 60 s gesamt)."""
VOICE = "de-DE-ConradNeural"   # ruhige, tiefe Erzählstimme

# start/end = Zeitfenster der Szene im Video (Sekunden)
SCENES = [
    {"key": "titel",   "start": 0,  "end": 3,  "text": "Deine Bezahlart kostet dich fast 470 Euro im Jahr. Welche?"},
    {"key": "start",   "start": 3,  "end": 8,  "text": "Gleicher Einkauf. Nur das Bezahlen ist anders."},
    {"key": "woche1",  "start": 8,  "end": 16, "text": "Mit Karte und Handy geht Bezahlen blitzschnell. Deshalb landen öfter Kaffee und Snacks im Korb."},
    {"key": "falsch",  "start": 16, "end": 22, "text": "Ist also das Handy die größte Geldfalle? Noch nicht."},
    {"key": "push",    "start": 22, "end": 30, "text": "Denn das Handy meldet jede Zahlung sofort. Das tut weh – also kauft es weniger."},
    {"key": "bar",     "start": 30, "end": 38, "text": "Und Bargeld? Kleingeld taucht in keiner App auf. Es fühlt sich an wie geschenkt."},
    {"key": "karte",   "start": 38, "end": 44, "text": "Nur die Karte spürt gar nichts. Keine Nachricht, kein Geld in der Hand."},
    {"key": "endstand","start": 44, "end": 50, "text": "Ergebnis: Mit Karte gibst du am meisten aus. Aufs Jahr fast 470 Euro mehr."},
    {"key": "schmerz", "start": 50, "end": 56, "text": "Du gibst weniger aus, wenn du spürst, dass Geld weggeht. Tipp: Push-Nachricht an!"},
    {"key": "ende",    "start": 56, "end": 60, "text": "Wie zahlst du? Schreib's in die Kommentare und abonnier für Teil 2!"},
]
