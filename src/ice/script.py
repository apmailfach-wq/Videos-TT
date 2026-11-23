"""Der ICE – Satire-Kurzfilm. Der Zug erzählt selbst (deadpan), Kind & Papa als eigene Stimmen."""
NARR = dict(voice="de-DE-ConradNeural", rate="+4%", pitch="-4Hz")
KID = dict(voice="de-DE-KatjaNeural", rate="+12%", pitch="+55Hz")
DAD = dict(voice="de-DE-KillianNeural", rate="-18%", pitch="-8Hz")

SCENES = [
    {"key": "hook", **NARR, "text": "Heute war ich pünktlich. Deutschland ist in Panik."},
    {"key": "einfahrt", **NARR, "text": "6 Uhr 12. Ich fahre ein. Auf die Minute."},
    {"key": "bahnsteig", **NARR, "text": "Auf dem Bahnsteig: Stille. Eine Frau lässt ihren Kaffee fallen. Ein Mann ruft seine Mutter an, um sich zu verabschieden."},
    {"key": "news", **NARR, "text": "Die Nachrichten unterbrechen ihr Programm. Experten sprechen von einem Systemfehler."},
    {"key": "kassel", **NARR, "text": "Kassel: wieder pünktlich. Die Leute filmen mich."},
    {"key": "kind", **KID, "text": "Papa, ist das ein Zug?"},
    {"key": "papa", **DAD, "text": "Ich … weiß es nicht, mein Sohn."},
    {"key": "kuh", **NARR, "text": "Dann, kurz vor Fulda: eine Kuh auf dem Gleis. Sie schaut mich an. Ich schaue sie an. Wir verstehen uns."},
    {"key": "warten", **NARR, "text": "Ich warte 70 Minuten."},
    {"key": "ende", **NARR, "text": "Die Ordnung ist wiederhergestellt. Deutschland atmet auf."},
]

# Nur eingeblendet (nicht gesprochen) – Kommentar-Köder am Ende
CTA = "Was war eure längste Verspätung?"
