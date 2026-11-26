"""URTEIL MAL! Folge 01 – Der Döner-Skandal: Zeitplan, Kamera, Mimik.

Jeder Eintrag ist entweder eine Sprechzeile (id = Datei in build/doener/trim/<id>.wav)
oder eine stumme Pause ('pause') für Gags. Kamera: (Ziel, Zoombreite_start, Zoombreite_ende).
"""

SPEAKERS = {
    "dennis": ("DENNIS", (120, 200, 255)),
    "sabine": ("SABINE", (255, 140, 200)),
    "richard": ("RICHTER RICHARD", (255, 215, 90)),
    "klaus": ("ANWALT KLAUS", (255, 110, 110)),
    "horst": ("HORST", (140, 230, 160)),
    "sprecher": ("", (255, 255, 255)),
}

TEMPO = 1.27         # Sprechtempo für alle Dialoge (Comedy-Tempo)
TEMPO_LAW = 1.5      # Rechts-Erklärung schneller

# text = Untertitel (ohne Regie-Tags)
EVENTS = [
    dict(id="01", who="dennis", text="Herr Richter, ich will die Scheidung! Sie hat meinen Döner gegessen!",
         cam=("dennis", 1500, 1000), expr={"dennis": "shout"}, pose={"dennis": "foil_up"},
         fx=["lines", "whoosh"], hook=True),
    dict(id="02", who="richard", text="Wegen eines Döners.", cam=("richard", 1000, 950)),
    dict(id="03", who="dennis", text="MIT EXTRA FLEISCH!", cam=("dennis", 820, 780),
         expr={"dennis": "shout"}, pose={"dennis": "foil_up"}, fx=["lines", "shake"]),
    dict(id="04", who="richard", text="… Fahren Sie fort.", cam=("richard", 1050, 900), pre=0.55,
         expr={"richard": "deadpan"}),
    dict(id="05", who="dennis", text="Versteckt im Kühlschrank! Hinter dem Rosenkohl! Da guckt NIEMAND hin!",
         cam=("dennis", 1250, 1100), expr={"dennis": "upset"}),
    dict(id="06", who="sabine", text="Da stand „Finger weg“. Hab ich mich dran gehalten. Ich hab ’ne Gabel genommen.",
         cam=("sabine", 1150, 1000), pose={"sabine": "fork"}),
    dict(id="07", who="horst", text="Rechtlich sauber.", cam=("horst", 1000, 950),
         expr={"horst": "proud"}, pose={"horst": "finger"}),
    dict(id="08", who="richard", text="Horst.", cam=("richard", 950, 950)),
    dict(id="p1", pause=0.8, cam=("horst", 950, 820), expr={"horst": "longing"},
         look={"horst": (-0.9, -0.6)}, fx=["sparkle_doener"]),
    dict(id="09", who="klaus", text="Hohes Gericht! Meine Mandantin hat den Döner nicht gegessen – sie hat ihn GERETTET!",
         cam=("klaus", 1100, 850), expr={"klaus": "dramatic"}, pose={"klaus": "finger"}, fx=["lines", "whoosh"]),
    dict(id="10", who="dennis", text="Sie hat die Alufolie AUSGELECKT!", cam=("dennis", 1000, 950),
         expr={"dennis": "disgust"}, pose={"dennis": "foil_up"}),
    dict(id="11", who="sabine", text="Die Soße wär sonst schlecht geworden.", cam=("sabine", 1000, 950)),
    dict(id="12", who="klaus", text="Lebensmittelrettung! Andere kriegen dafür einen Preis!",
         cam=("klaus", 1050, 950), expr={"klaus": "dramatic"}, pose={"klaus": "fist"}, fx=["shake", "bang"]),
    dict(id="13", who="richard", text="Herr Anwalt. Das ist ein Döner. Nicht die Vereinten Nationen.",
         cam=("richard", 1050, 900), expr={"richard": "brow"}),
    dict(id="p2", pause=0.8, cam=("wide", 2160, 2000), expr={"horst": "longing"},
         look={"horst": (-0.9, -0.6)}, fx=["sparkle_doener"]),
    dict(id="14", who="sabine", text="Übrigens: Den Döner hab ICH bezahlt.", cam=("sabine", 1150, 850),
         expr={"sabine": "smug"}, pose={"sabine": "receipt"}, fx=["sting"]),
    dict(id="15", who="dennis", text="Aber ICH hab ihn ausgesucht!", cam=("dennis", 1000, 950),
         expr={"dennis": "upset"}),
    dict(id="16", who="sabine", text="Und letzten Dienstag hast du MEINEN gegessen. Mit Schafskäse.",
         cam=("sabine", 1000, 900), expr={"sabine": "smug"}, pose={"sabine": "receipt"}),
    dict(id="p3", pause=1.3, cam=("wide", 2160, 1700), music=False, fx=["cricket"],
         look={"richard": (-0.8, 0.8), "klaus": (-1, 0.1), "sabine": (-1, 0.1), "horst": (-0.9, 0.7)},
         expr={"dennis": "nervous"}, extra={"dennis": "sweat"}),
    dict(id="17", who="dennis", text="Das war … ein Geschmackstest.", cam=("dennis", 900, 800),
         expr={"dennis": "nervous"}, extra={"dennis": "sweat"}),
    dict(id="18", who="klaus", text="Einspruch! … Nein, warte. Das ist gut für uns.", cam=("klaus", 1000, 950),
         expr={"klaus": "outraged"}, expr2={"klaus": "smug"}),
    dict(id="19", who="richard", text="Ich habe in meinem Leben schon viel erlebt. Aber das hier ist wirklich eine Zumutung!",
         cam=("richard", 1050, 820), expr={"richard": "tired"}, pose={"richard": "facepalm"}),
    dict(id="20", who="richard", law=True,
         text="Ehe heißt nicht: Alles gehört beiden. Das Vermögen bleibt getrennt – Paragraf 1363 BGB. "
              "Geschieden wird nur, wenn die Ehe gescheitert ist – Paragraf 1565. Ein Döner reicht nicht. "
              "Und selbst wenn jeder Ersatz verlangen könnte: Döner gegen Döner – das rechnet sich auf. Paragraf 387.",
         cam=("richard", 1150, 1080), hide={"horst"}),
    dict(id="21", who="richard", text="Urteil: Zwei Döner. Zwei Kühlschränke. Und ich habe Feierabend.",
         cam=("wide", 2160, 2100), fx=["gavel"], hide={"horst"}),
    dict(id="p4", pause=1.0, cam=("doener", 760, 640), music=False, fx=["sting"], doener="empty", hide={"horst"}),
    dict(id="p5", pause=0.8, cam=("richard_horst", 1250, 1150), music=False, doener="empty",
         expr={"richard": "shock"}, horst_final=True, look={"richard": (1, 0)}),
    dict(id="22", who="horst", text="Da stand nur „Finger weg“.", cam=("richard_horst", 1150, 1050),
         doener="empty", horst_final=True, expr={"richard": "twitch", "horst": "innocent"},
         look={"richard": (1, 0)}),
    dict(id="23", who="sprecher", text="Und jetzt seid ihr dran: Wer hat hier eigentlich Recht?",
         cam=("richard_horst", 1050, 900), pre=0.3, post=1.6, doener="empty", horst_final=True,
         expr={"richard": "twitch", "horst": "innocent"}, look={"richard": (1, 0)}, freeze=True, end=True),
]

# Text-Einblendungen während der Rechts-Erklärung: (Anteil der Zeile, Titel, Untertitel)
LAW_CARDS = [
    (0.10, "§ 1363 BGB", "Vermögen bleibt getrennt"),
    (0.40, "§ 1565 BGB", "Scheidung nur, wenn die Ehe gescheitert ist"),
    (0.66, "DÖNER ≠ HÄRTEFALL", "Ein Döner reicht nicht"),
    (0.86, "§ 387 BGB", "Aufrechnung: Döner gegen Döner"),
]
