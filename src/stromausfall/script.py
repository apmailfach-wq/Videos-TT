VOICE = "de-AT-JonasNeural"
RATE = "+12%"

# Beispielrechnung: 7 Tage ohne Strom.
# Gespart (Strom): ca. 3,15 €/Tag  -> ~22 €
# Ausgegeben: 25 + 60 + 35 + 50 + 70 = 240 €
SCENES = [
    {"key": "hook", "text": "Was wäre, wenn eine Woche der Strom ausfällt – was kostet dich das? Rechnen wir nach."},
    {"key": "tag1", "text": "Tag eins: Licht aus. Kerzen und Batterien: 25 Euro."},
    {"key": "tag2", "text": "Tag zwei: Der Kühlschrank tropft. Essen im Müll: 60 Euro."},
    {"key": "tag3", "text": "Tag drei: Kein Herd, also bestellen. 35 Euro."},
    {"key": "tag45", "text": "Tag vier und fünf: Die Pizzakartons stapeln sich. 50 Euro."},
    {"key": "tag67", "text": "Tag sechs und sieben: Tiefkühltruhe aufgetaut, Waschsalon, Powerbank. 70 Euro."},
    {"key": "fazit", "text": "Ergebnis: 22 Euro Strom gespart – aber 240 Euro ausgegeben."},
    {"key": "cta", "text": "Was würdest du ohne Strom als Erstes vermissen? Schreib's in die Kommentare!"},
]

QUESTION = "Was würdest du ohne Strom als *Erstes* *vermissen?*"
