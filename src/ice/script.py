"""Der ICE – Satire-Kurzfilm. Der Zug erzählt selbst (deadpan), Kind & Papa als eigene Stimmen."""
NARR = dict(voice="de-DE-FlorianMultilingualNeural", rate="+16%", pitch="+0Hz")
PA = dict(voice="de-DE-SeraphinaMultilingualNeural", rate="-6%", pitch="-2Hz")
KID = dict(voice="de-DE-KatjaNeural", rate="+12%", pitch="+55Hz")
DAD = dict(voice="de-DE-KillianNeural", rate="-6%", pitch="-8Hz")

SCENES = [
    {"key": "hook", **NARR, "text": "Heute war ich pünktlich. Deutschland ist in Panik."},
    {"key": "einfahrt", **NARR, "text": "6 Uhr 12. Ich fahre ein. Auf die Minute. In der richtigen Wagenreihung."},
    {"key": "durchsage", **PA, "text": "Sehr geehrte Fahrgäste, aufgrund einer unerwarteten Pünktlichkeit kommt es zu erheblichen Verspätungen im gesamten Betriebsablauf."},
    {"key": "bahnsteig", **NARR, "text": "Auf dem Bahnsteig: Stille. Eine Frau lässt ihren Kaffee fallen. Ein Mann ruft seine Mutter an, um sich zu verabschieden. Ein Rentner weint. Er wartet hier seit 1998 auf seinen Anschluss."},
    {"key": "news", **NARR, "text": "Die Nachrichten unterbrechen ihr Programm. Experten sprechen von einem Systemfehler. Der Bahnvorstand kündigt eine Untersuchung an. Und sicherheitshalber eine Preiserhöhung."},
    {"key": "kassel", **NARR, "text": "Kassel: wieder pünktlich. Die Leute filmen mich. Das WLAN funktioniert. Jemand ruft einen Exorzisten."},
    {"key": "kind", **KID, "text": "Papa, ist das ein Zug?"},
    {"key": "papa", **DAD, "text": "Ich … weiß es nicht, mein Sohn. Ich hab noch nie einen fahren sehen."},
    {"key": "kuh", **NARR, "text": "Dann, kurz vor Fulda: eine Kuh auf dem Gleis. Sie schaut mich an. Ich schaue sie an. Wir verstehen uns. Ich glaube, sie wurde geschickt."},
    {"key": "warten", **NARR, "text": "Ich warte 70 Minuten. Klimaanlage aus. Bistro geschlossen. Toilette defekt. Endlich fühle ich mich wieder wie ich selbst."},
    {"key": "ende", **NARR, "text": "Die Ordnung ist wiederhergestellt. Deutschland atmet auf. Und die Kuh? Sitzt jetzt im Vorstand. Mit Bonus."},
]

# Nur eingeblendet (nicht gesprochen) – Kommentar-Köder am Ende
CTA = "Eure schlimmste Bahn-Story?"
