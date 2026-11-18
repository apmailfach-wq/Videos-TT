"""Teil 2 – Sprechertext je Szene (feste Zeitfenster, 60 s gesamt)."""
VOICE = "de-DE-ConradNeural"

SCENES = [
    {"key": "titel",   "start": 0,  "end": 3,  "text": "Einer zahlt 148 Euro mehr – und merkt es nicht."},
    {"key": "start",   "start": 3,  "end": 8,  "text": "Teil 2: Debitkarte, Kreditkarte oder später zahlen."},
    {"key": "woche1",  "start": 8,  "end": 16, "text": "Die Debitkarte bucht sofort ab. Die Kreditkarte erst nächsten Monat – das fühlt sich an wie gratis."},
    {"key": "falsch",  "start": 16, "end": 22, "text": "Also ist die Kreditkarte die größte Geldfalle? Noch nicht."},
    {"key": "raten",   "start": 22, "end": 30, "text": "Später zahlen macht aus 60 Euro viermal 15. Plötzlich passt die Jacke ins Budget."},
    {"key": "stapel",  "start": 30, "end": 38, "text": "Dann noch Kopfhörer. Jede Rate klingt klein – aber sie laufen alle gleichzeitig."},
    {"key": "rechnung","start": 38, "end": 44, "text": "Und die Kreditkarte? Am Monatsende kommt die Rechnung. Alles auf einmal."},
    {"key": "endstand","start": 44, "end": 50, "text": "Ergebnis: Mit später zahlen gibst du am meisten aus. Und die Raten laufen weiter."},
    {"key": "schmerz", "start": 50, "end": 56, "text": "Je später du zahlst, desto mehr kaufst du. Tipp: Kauf nur, was du heute zahlen könntest."},
    {"key": "ende",    "start": 56, "end": 60, "text": "Wie zahlst du? Schreib's in die Kommentare und abonnier für Teil 3!"},
]
