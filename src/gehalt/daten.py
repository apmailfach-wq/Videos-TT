"""Alle Beträge und Texte – ein Monat aus dem deutschen Leben.

Annahmen (Stand 2026, gerundet, ohne Gewähr): 3.350 € brutto, Steuerklasse I, keine Kinder,
keine Kirchensteuer, gesetzlich versichert (Ø-Zusatzbeitrag 2,9 %), Großstadt, Single.
Beträge in Cent.
"""

BRUTTO = 335_000

# key: (Label im Level, Name im Kontoauszug, Betrag in Cent, Kategorie, Emoji)
ITEMS = {
    # 1. Lohnabzüge (Schranken im Schacht – jeder zahlt sie)
    "lohnsteuer": ("LOHNSTEUER", "Lohnsteuer", -39_200, "abzug", "🏛"),
    "rente": ("RENTENVERS. 9,3 %", "Rentenversicherung", -31_155, "abzug", "👴"),
    "kranken": ("KRANKENVERS. 8,75 %", "Krankenversicherung", -29_313, "abzug", "🏥"),
    "pflege": ("PFLEGEVERS. 2,4 %", "Pflegeversicherung", -8_040, "abzug", "🧓"),
    "arbeitslos": ("ARBEITSLOSENV. 1,3 %", "Arbeitslosenvers.", -4_355, "abzug", "📋"),
    # 2. Fixkosten (Rotoren)
    "miete": ("WARMMIETE", "Warmmiete", -115_000, "fix", "🏠"),
    "strom": ("STROM", "Strom", -8_900, "fix", "⚡"),
    "handy": ("HANDY + WLAN", "Handy + Internet", -6_498, "fix", "📱"),
    # 3. Alltag (Plinko-Pins)
    "kaffee": ("", "Kaffee to go", -390, "alltag", "☕"),
    "brezel": ("", "Butterbrezel", -180, "alltag", "🥨"),
    "doener": ("", "Döner", -850, "alltag", "🥙"),
    "pizza": ("", "Pizza", -1_290, "alltag", "🍕"),
    "bier": ("", "Feierabendbier", -480, "alltag", "🍺"),
    "paket": ("", "Online-Bestellung", -2_999, "alltag", "📦"),
    "pfand": ("PFAND", "Pfandflaschen", +325, "bonus", "♻"),
    # 4. Überraschungen (Kugeln mit Gesicht)
    "einkauf": ("WOCHEN-\nEINKAUF", "Wocheneinkauf", -9_420, "extra", "🛒"),
    "zahnarzt": ("ZAHN-\nREINIGUNG", "Zahnreinigung", -12_000, "extra", "🦷"),
    "gez": ("RUNDFUNK-\nBEITRAG", "Rundfunkbeitrag", -1_836, "extra", "📺"),
    "gym": ("FITNESS-\nSTUDIO", "Fitnessstudio", -3_990, "extra", "🏋"),
    "streaming": ("STREAMING\nABOS", "Streaming-Abos", -3_297, "extra", "🍿"),
    "liefer": ("LIEFER-\nDIENST", "Lieferdienst", -3_450, "extra", "🛵"),
    # 5. Monatsende
    "kfz": ("KFZ-VERSICHERUNG", "Kfz-Versicherung", -7_840, "fix", "🚗"),
    "ticket": ("DEUTSCHLANDTICKET", "Deutschlandticket", -6_300, "fix", "🚆"),
    "knoellchen": ("KNÖLLCHEN", "Knöllchen", -3_500, "extra", "🚨"),
    "erstattung": ("STEUER-\nERSTATTUNG", "Steuererstattung", +28_700, "bonus", "💶"),
    "geschenk": ("", "Geschenk Kollegin", -1_000, "alltag", "🎁"),
    "nachzahlung": ("NEBENKOSTEN-NACHZAHLUNG", "NK-Nachzahlung", -24_000, "extra", "🧾"),
}

CATEGORIES = [
    ("abzug", "Steuern & Sozialabgaben"),
    ("fix", "Fixkosten"),
    ("alltag", "Alltag & Kleinkram"),
    ("extra", "Überraschungen"),
    ("bonus", "Rückflüsse"),
]

CHAPTERS = [  # (Welt-y ab dem das Kapitel beginnt, Titel)
    (0, "1 · LOHNABZÜGE"),
    (1750, "2 · FIXKOSTEN"),
    (2950, "3 · ALLTAG"),
    (4150, "4 · ÜBERRASCHUNGEN"),
    (5450, "5 · MONATSENDE"),
]

POCKETS = {
    "dispo": ("DISPO", "11,9 % Zinsen", "💳"),
    "urlaub": ("URLAUB", "Mallorca", "🏝"),
    "nudeln": ("NUDELN", "bis zum 1.", "🍝"),
}

T = {
    "hook0": "3.350 € BRUTTO",
    "hook1": "SCHAFFT ES MEIN GEHALT",
    "hook2": "BIS ZUM URLAUB?",
    "brutto": "KONTOSTAND · BRUTTO",
    "netto": "KONTOSTAND · NETTO",
    "netto_stamp": "NETTO",
    "salary": "GEHALT",
    "paid": "BEZAHLT",
    "comeon": "KOMM SCHON... KOMM SCHON...",
    "made_it": "GESCHAFFT!",
    "broke": "PLEITE!",
    "statement": "MONATSABRECHNUNG MAI",
    "brutto_line": "Brutto",
    "rest": "Übrig für den Urlaub",
    "punch": "Mallorca? Eher Balkonien.",
    "cta1": "WIE VIEL BLEIBT DIR",
    "cta2": "AM MONATSENDE?",
    "cta3": "Brutto → Rest in die Kommentare",
    "month": "Mai",
    "foot": "StKl. I · keine Kinder · ohne Kirchensteuer · Werte gerundet",
}


def eur(cents, sign=False):
    v = abs(int(round(cents)))
    e, c = divmod(v, 100)
    s = f"{e:,}".replace(",", ".") + f",{c:02d} €"
    if sign:
        return ("+" if cents > 0 else "−") + s
    return ("−" if cents < 0 else "") + s


def eur_short(cents, sign=False):
    """Ganze Euro, wenn glatt (für Beschriftungen im Level)."""
    if cents % 100 == 0:
        v = abs(cents) // 100
        s = f"{v:,}".replace(",", ".") + " €"
        return (("+" if cents > 0 else "−") if sign else ("−" if cents < 0 else "")) + s
    return eur(cents, sign)
