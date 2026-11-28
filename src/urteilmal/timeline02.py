"""URTEIL MAL! Folge 02 – Die Dauerkarten-Klage: Zeitplan, Kamera, Mimik (Format wie timeline.py)."""

from timeline import SPEAKERS  # noqa: F401  (gleiche Figuren/Farben)

TEMPO = 1.46
TEMPO_LAW = 1.55

Y = (255, 220, 40)
WH_ = (255, 255, 255)
LOOK_DENNIS = {"richard": (-0.8, 0.8), "klaus": (-1, 0.1), "sabine": (-1, 0.1), "horst": (-0.9, 0.7)}

EVENTS = [
    # HOOK: Sabines stärkster Satz sofort in Sekunde 0 (Ausschnitt aus Aufnahme d13)
    dict(id="h0", src="d13", clip=(3.8,), who="sabine",
         text="Das ist kein Fußballverein. Das ist eine organisierte Enttäuschungsanstalt!",
         cam=("sabine", 1050, 760), hook=True, fx=["whoosh", "lines", "sting_late"],
         expr={"sabine": "outraged", "dennis": "upset", "klaus": "shock", "richard": "brow"}, extra={"sabine": "anger"},
         big=dict(lines=[("EHEPAAR VERKLAGT", WH_), ("FUSSBALLVEREIN!", Y)], y=405, size=56, instant=True)),
    dict(id="d01", who="richard", text="Herr Dennis, Frau Sabine, warum verklagen Sie Ihren Fußballverein?",
         cam=("wide", 2160, 1800), fx=["whoosh"], expr={"richard": "brow", "dennis": "upset", "sabine": "upset"},
         big=dict(lines=[("5 JAHRE DAUERKARTE", WH_), ("0 TITEL", Y)], y=780, size=54)),
    dict(id="d02", who="dennis", text="Herr Richter, wir haben seit fünf Jahren Dauerkarten! FÜNF JAHRE!",
         cam=("dennis", 1200, 950), expr={"dennis": "shout", "sabine": "upset"}, extra={"dennis": "anger"}, pose={"dennis": "scarf_up"}, fx=["lines", "whoosh"]),
    dict(id="e01", who="sabine", text="Und was haben wir bekommen? Nichts! Die schaffen es ja nicht mal, ein Freundschaftsspiel zu gewinnen!",
         cam=("sabine", 1100, 950), expr={"sabine": "outraged", "dennis": "upset"}),
    dict(id="d04", who="richard", text="Aber der Verein hat doch jedes Jahr gespielt?", cam=("richard", 1000, 930)),
    dict(id="d07", who="dennis", text="Letzten Samstag hat sie mich sogar aus dem Schlafzimmer geworfen, weil ich nach dem 0:4 noch gesagt habe: Nächste Saison wird alles besser!",
         cam=("dennis", 1150, 950), expr={"dennis": "upset", "sabine": "smug"}, extra={"dennis": "sweat"}),
    dict(id="d08", who="sabine", text="Das war die fünfte nächste Saison!", cam=("sabine", 950, 820),
         expr={"sabine": "smug", "dennis": "shock"}, fx=["sting"]),
    dict(id="d09", who="horst", text="Bei mir ist es die dreiundzwanzigste.", cam=("horst", 1000, 880),
         expr={"horst": "sad", "richard": "brow"}, extra={"horst": "tears"}),
    dict(id="08", who="richard", text="Horst.", cam=("richard", 950, 950), expr={"richard": "deadpan", "horst": "sad"}),
    dict(id="d10", who="richard", text="Was genau wurde Ihnen denn zugesichert?", cam=("richard", 1050, 950),
         expr={"richard": "brow"}),
    dict(id="d11", who="dennis", text="Meisterschaft! Pokalsieg! Wenigstens Vizemeister! Irgendwas!",
         cam=("dennis", 1150, 900), expr={"dennis": "shout", "sabine": "upset"}, extra={"dennis": "anger"}, pose={"dennis": "fist"}, fx=["bang", "shake", "folder"]),
    dict(id="d12", who="klaus", text="Einspruch! Mein Mandant hat nie Siege versprochen. Nur Emotionen. Und die haben Sie bekommen!",
         cam=("klaus", 1100, 880), expr={"klaus": "dramatic", "dennis": "outraged", "sabine": "outraged"}, expr2={"klaus": "smug"}, pose={"klaus": "finger"},
         fx=["lines", "whoosh"]),
    dict(id="d13", src="d13", clip=(3.8,), who="sabine", text="Das ist kein Fußballverein. Das ist eine organisierte Enttäuschungsanstalt!",
         cam=("sabine", 1150, 820), expr={"sabine": "outraged", "klaus": "shock"}, extra={"sabine": "anger"}, fx=["sting_late"],
         big=dict(lines=[("ORGANISIERTE", WH_), ("ENTTÄUSCHUNGS-", Y), ("ANSTALT", Y)], y=470, size=66, at=0.4)),
    dict(id="d14", who="richard", text="Ich verstehe. Und was fordern Sie als Schadensersatz?", cam=("richard", 1050, 950), expr={"richard": "brow"}),
    dict(id="e02", who="dennis", text="Alle Eintrittsgelder zurück! Und zwar zusammen mit Sabine!", cam=("dennis", 1000, 880),
         expr={"dennis": "shout", "sabine": "proud"}, fx=["lines"]),
    dict(id="e03", who="sabine", text="Moment! Ich will das Geld aber MIT ZINSEN zurück!", cam=("sabine", 1000, 820),
         expr={"sabine": "outraged", "dennis": "shock"}, extra={"sabine": "anger"}, fx=["whoosh", "shake"]),
    dict(id="e04", who="richard", text="Mit Zinsen? Warum denn das?", cam=("richard", 1000, 900), pre=0.15,
         expr={"richard": "brow"}),
    dict(id="e05", who="sabine", text="Herr Richter, die Bratwurst kostet mittlerweile ein Vermögen, das Bier auch – aber die Leistung unserer Mannschaft gibt's inzwischen praktisch zum Nulltarif!",
         cam=("sabine", 1150, 950), expr={"sabine": "upset", "dennis": "upset"}, post=0.35),
    dict(id="e06", who="dennis", text="Genau! Für das Geld hätten wir nicht nur Würstchen kaufen können, sondern gleich eine eigene Imbissbude aufmachen können!",
         cam=("dennis", 1150, 900), expr={"dennis": "dramatic", "sabine": "proud"}, post=0.2,
         big=dict(lines=[("EIGENE", WH_), ("IMBISSBUDE!", Y)], y=430, size=64, at=0.75)),
    dict(id="p0", pause=0.8, cam=("richard", 950, 860), expr={"richard": "tired", "dennis": "proud", "sabine": "proud"},
         pose={"richard": "facepalm"}),
    dict(id="e07", who="richard", law=True,
         text="Mit einer Dauerkarte kauft man einen Platz im Stadion. Keinen Sieg. Verlieren ist keine Pflichtverletzung. "
              "Ein Anspruch auf Schadensersatz nach Paragraf 280 BGB besteht daher nicht.",
         cam=("richard", 1150, 1080), hide={"horst"}),
    dict(id="d18", who="richard", text="Den Antrag auf Rückerstattung lehne ich ab. Aber ich verurteile den Verein zu einer sofortigen Meisterschaft!",
         cam=("wide", 2160, 2000), fx=["gavel"], expr={"dennis": "shock", "sabine": "shock", "klaus": "shock"}),
    dict(id="d19", who="dennis", text="JAAA!", cam=("dennis", 1000, 900), expr={"dennis": "happy", "sabine": "puzzled"},
         pose={"dennis": "cheer"}, fx=["lines"], post=0.15),
    dict(id="d20", who="richard", text="Allerdings erst, wenn er sportlich dazu in der Lage ist.", cam=("richard", 1000, 900),
         expr={"richard": "deadpan"}),
    dict(id="p1", pause=0.7, cam=("wide", 2160, 1900), music=False, fx=["cricket"], look=LOOK_DENNIS,
         expr={"dennis": "shock"}, pose={"dennis": "cheer"}, extra={"dennis": "sweat"}, cricket_text=True),
    dict(id="d21", who="sabine", text="Na super. Dann sehen wir uns hier in weiteren fünf Jahren.",
         cam=("sabine", 1000, 880), expr={"sabine": "deadpan", "dennis": "sad"}, look={"sabine": (-1, 0.1)}),
    dict(id="d22", who="horst", text="Ich hab schon verlängert. Bis 2040.", cam=("horst", 1050, 900),
         expr={"horst": "happy", "dennis": "shock", "sabine": "shock"}, pose={"horst": "card"}, fx=["sparkle"], post=0.5),
    dict(id="p2", pause=0.6, cam=("richard", 900, 820), expr={"richard": "twitch"}, look={"richard": (0.9, 0.5)}),
    dict(id="e08", who="richard",
         text="Und jetzt mal ehrlich: Würdet ihr euren Fußballverein auch verklagen, wenn er fünf Jahre lang nur verliert? Und was würdet ihr als Schadensersatz verlangen?",
         cam=("richard", 1450, 1250), pre=0.1, post=1.8, expr={"richard": "deadpan"}, look={"richard": (0, 0.2)},
         end=True),
]

LAW_CARDS = [
    (0.05, "DAUERKARTE", "= Platz im Stadion, kein Sieg"),
    (0.38, "VERLIEREN", "ist keine Pflichtverletzung"),
    (0.62, "§ 280 BGB", "Kein Anspruch auf Schadensersatz"),
]
END_LINES = [("URTEIL MAL!", (255, 90, 90)), ("WAS WÜRDEST", (255, 255, 255)), ("DU TUN?", (255, 220, 40))]
END_BANNER = "SCHREIB'S IN DIE KOMMENTARE!"
