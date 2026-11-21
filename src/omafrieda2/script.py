"""Sprechertext für 'Oma Frieda Faust – Folge 2: Oma Frieda geht zur Schule'."""

VOICES = {
    # natürlichere Stimmen: Multilingual-Neural für Oma & Erzähler, Kinder von jungen Frauenstimmen (leicht angehoben)
    "erz":   ("de-DE-FlorianMultilingualNeural", "-6%", "-6Hz", "bass=g=3:f=110,aecho=0.8:0.4:30:0.08,volume=1.1"),
    "oma":   ("de-DE-SeraphinaMultilingualNeural", "-6%", "-10Hz", "vibrato=f=5:d=0.015,volume=1.1"),
    "omaflott": ("de-DE-SeraphinaMultilingualNeural", "+3%", "-10Hz", "vibrato=f=5:d=0.015,volume=1.1"),
    "gamer": ("de-DE-TanjaNeural", "+6%", "+18Hz", "volume=1.0"),
    "girl":  ("de-DE-AmalaNeural", "+8%", "+20Hz", "volume=1.0"),
    "rowdy": ("de-DE-KillianNeural", "+4%", "+6Hz", "volume=1.05"),
    "kleiner": ("de-DE-KatjaNeural", "+6%", "+24Hz", "volume=1.0"),
    "bully2": ("de-AT-JonasNeural", "+8%", "+4Hz", "volume=1.0"),
    "dixi":  ("de-DE-KillianNeural", "-5%", "+6Hz", "lowpass=f=650,aecho=0.8:0.6:25:0.3,volume=1.6"),
}

# (id, speaker, text, start_s, latest_end_s)
# Einschübe für zusätzliche Gags: (Zeitpunkt in der alten Zeitachse, Dauer)
INS = [(5.90, 2.4), (13.85, 12.6), (41.70, 4.8), (43.95, 1.2), (49.90, 1.4), (56.30, 3.8)]


def R(t):
    """Alte Zeit -> neue Zeit (Einschübe davor werden addiert)."""
    return t + sum(d for p, d in INS if t >= p)


def R_end(t):
    return t + sum(d for p, d in INS if t > p)


def at(k, off):
    """Zeitpunkt innerhalb von Einschub k."""
    p, _ = INS[k]
    return R_end(p) + off


_LINES_OLD = [
    ("oma1",  "oma",      "Ich erklär's euch.",                                              1.00, 1.95),
    ("erz1",  "erz",      "Das ist Frieda. Sie ist achtzig.",                                3.30, 5.80),
    ("erz2",  "erz",      "Heute ist sie Vertretungslehrerin.",                              6.00, 8.10),
    ("girl1", "girl",     "Ey, die Oma ist unsere Lehrerin?",                                8.40, 10.35),
    ("lach1", "gamer",    "Hahaha!",                                                         10.45, 10.95),
    ("oma2",  "omaflott", "Und ihr seid heute meine Enkel. Pech gehabt.",                    11.20, 13.85),
    ("oma3",  "oma",      "Zielen üben wir in Sport.",                                       15.00, 16.60),
    ("girl2", "girl",     "Wooow!",                                                          16.70, 17.20),
    ("oma4",  "omaflott", "Handy weg. Ich hab achtzig Jahre ohne geschafft.",                18.00, 20.95),
    ("gam1",  "gamer",    "Mein Handy!",                                                     21.05, 21.75),
    ("girl3", "girl",     "Frau Faust, die Klos sind schon wieder kaputt!",                  21.85, 24.45),
    ("oma5",  "omaflott", "Kaputt gemacht, Kind. Das ist ein Unterschied.",                  24.55, 27.25),
    ("erz3",  "erz",      "Und dann … die große Pause.",                                     27.45, 29.45),
    ("row1",  "rowdy",    "Na, Kleiner? Ab ins Dixi mit dir!",                               29.65, 31.95),
    ("kle1",  "kleiner",  "Lasst mich in Ruhe!",                                             32.05, 33.10),
    ("oma6",  "omaflott", "Jungs. Zwei Große gegen einen Kleinen. Wie mutig.",               33.25, 37.05),
    ("row2",  "rowdy",    "Halt dich raus, Oma!",                                            37.20, 38.45),
    ("oma7",  "omaflott", "Ich bin achtzig. Ich halt mich aus gar nichts mehr raus.",        38.60, 41.65),
    ("row3",  "rowdy",    "Aaaaaah!",                                                        42.90, 43.90),
    ("oma8",  "oma",      "Du auch?",                                                        44.70, 45.40),
    ("bul1",  "bully2",   "Ich geh schon!",                                                  45.50, 46.40),
    ("oma9",  "omaflott", "Hustenbonbon? Riecht ja streng da drin.",                         47.20, 49.70),
    ("oma10", "omaflott", "Und du: Sowas sagst du sofort. Das ist nicht petzen. Das ist mutig.", 50.00, 54.70),
    ("kle2",  "kleiner",  "Danke, Frau Faust!",                                              54.85, 56.05),
    ("oma11", "oma",      "Mit Frieda Faust legt man sich nicht an!",                        56.60, 58.90),
    ("erz5",  "erz",      "Wo geht Oma Frieda als Nächstes hin?",                            59.60, 61.85),
]

LINES = [(i, sp, tx, round(R(a), 2), round(R_end(b), 2)) for i, sp, tx, a, b in _LINES_OLD] + [
    ("gag1", "oma",      "Ah … der Duft der Bildung.",                      at(0, 0.20), at(0, 2.25)),
    ("gagA", "omaflott", "Anwesenheit! Wer fehlt, hebt die Hand.",         at(1, 0.10), at(1, 2.70)),
    ("gagB", "girl",     "Frau Faust, wie alt sind Sie eigentlich?",       at(1, 3.55), at(1, 5.80)),
    ("gagC", "omaflott", "Alt genug, um alle eure Ausreden zu kennen.",    at(1, 5.95), at(1, 8.35)),
    ("gag2", "gamer",    "Faust? Wie die Hand?",                           at(1, 8.50), at(1, 10.20)),
    ("gag3", "oma",      "Genau wie die Hand.",                            at(1, 10.40), at(1, 12.00)),
    ("gag4", "rowdy",    "Was willst du machen? Stricken?",                at(2, 0.10), at(2, 2.10)),
    ("gag5", "omaflott", "Ich strick dir gleich 'nen Knoten in die Beine.", at(2, 2.25), at(2, 4.70)),
    ("gag6", "oma",      "Besetzt.",                                       at(3, 0.25), at(3, 1.10)),
    ("gag7", "dixi",     "Danke, Oma …",                                   at(4, 0.20), at(4, 1.30)),
    ("gag8", "kleiner",  "Sind Sie morgen wieder da?",                     at(5, 0.15), at(5, 1.60)),
    ("gag9", "omaflott", "Kommt drauf an, wer frech ist.",                 at(5, 1.75), at(5, 3.70)),
]
LINES.sort(key=lambda l: l[3])

TOTAL = round(R(63.1), 2)
