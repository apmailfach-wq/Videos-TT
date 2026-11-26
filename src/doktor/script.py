"""Sketch: doctor joke – two voices, one line per entry. Language via env DOKTOR_LANG (ru|de)."""
import os

LANG = os.environ.get("DOKTOR_LANG", "ru")

if LANG == "de":
    DOC = "de-DE-KatjaNeural"       # Ärztin
    PAT = "de-DE-ConradNeural"      # Patient
    LINES = [
        ("pat", "Frau Doktor, wie lange habe ich noch zu leben?", PAT, "+8%", "+0Hz", 0.15),
        ("doc", "Rauchen Sie?",                                    DOC, "+0%", "+0Hz", 0.25),
        ("pat", "Nein.",                                           PAT, "+0%", "+0Hz", 0.12),
        ("doc", "Trinken Sie?",                                    DOC, "+0%", "+0Hz", 0.18),
        ("pat", "Nein.",                                           PAT, "-5%", "+0Hz", 0.12),
        ("doc", "Und Frauen?",                                     DOC, "+0%", "+0Hz", 0.18),
        ("pat", "Nei-ein…",                                        PAT, "-15%", "+0Hz", 0.15),
        ("doc", "Und wozu wollen Sie dann so lange leben?",        DOC, "-10%", "+0Hz", 2.1),
    ]
    TXT = {
        "head": ["WENN DU DEN ARZT FRAGST,", "WIE LANGE DU NOCH HAST…"],
        "card": "PATIENTENAKTE", "labels": ["Raucht?", "Trinkt?", "Frauen?"],
        "no": "NEIN", "final": "SINNLOS", "chip_pat": "PATIENT", "chip_doc": "ÄRZTIN",
        "stage": "*nimmt die Brille ab*",
        "cta1": "MARKIER EINEN FREUND,", "cta2": "der so antworten würde", "cta3": "schreib's in die Kommentare",
    }
else:
    DOC = "ru-RU-SvetlanaNeural"
    PAT = "ru-RU-DmitryNeural"
    # who, text, voice, rate, pitch, gap_before (s)
    LINES = [
        ("pat", "Доктор, сколько мне осталось жить?", PAT, "+8%", "+0Hz", 0.15),
        ("doc", "Вы курите?",                         DOC, "+0%", "+0Hz", 0.25),
        ("pat", "Нет.",                               PAT, "+0%", "+0Hz", 0.12),
        ("doc", "Пьёте?",                             DOC, "+0%", "+0Hz", 0.18),
        ("pat", "Нет.",                               PAT, "-5%", "+0Hz", 0.12),
        ("doc", "Женщинами увлекаетесь?",             DOC, "+0%", "+0Hz", 0.18),
        ("pat", "Не-ет…",                             PAT, "-15%", "+0Hz", 0.15),
        # glasses-off pause happens before this line
        ("doc", "А смысл тогда вас долго держать?",   DOC, "-12%", "+0Hz", 2.1),
    ]
    TXT = {
        "head": ["КОГДА СПРОСИЛ ВРАЧА,", "СКОЛЬКО МНЕ ОСТАЛОСЬ…"],
        "card": "МЕДКАРТА", "labels": ["Курит?", "Пьёт?", "Женщины?"],
        "no": "НЕТ", "final": "СМЫСЛА НЕТ", "chip_pat": "ПАЦИЕНТ", "chip_doc": "ВРАЧ",
        "stage": "*снимает очки*",
        "cta1": "ОТМЕТЬ ДРУГА,", "cta2": "который ответил бы", "cta3": "пиши в комменты",
    }

BUILD_NAME = "doktor" if LANG == "ru" else f"doktor_{LANG}"
VIDEO_NAME = "doktor-video.mp4" if LANG == "ru" else f"doktor-video-{LANG}.mp4"
