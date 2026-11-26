"""Sketch: "Доктор, сколько мне осталось жить?" – two voices, one line per entry."""
DOC = "ru-RU-SvetlanaNeural"     # Ärztin
PAT = "ru-RU-DmitryNeural"       # Patient

# who, text, voice, rate, pitch, gap_before (s), caption text
LINES = [
    ("pat", "Доктор, сколько мне осталось жить?", PAT, "+8%", "+0Hz", 0.15),
    ("doc", "Вы курите?",                         DOC, "+0%", "+0Hz", 0.25),
    ("pat", "Нет.",                               PAT, "+0%", "+0Hz", 0.12),
    ("doc", "Пьёте?",                             DOC, "+0%", "+0Hz", 0.18),
    ("pat", "Нет.",                               PAT, "-5%", "+0Hz", 0.12),
    ("doc", "Женщинами увлекаетесь?",             DOC, "+0%", "+0Hz", 0.18),
    ("pat", "Не-ет…",                             PAT, "-15%", "+0Hz", 0.15),
    # glasses-off pause happens before this line (see render.GLASSES_PAUSE)
    ("doc", "А смысл тогда вас долго держать?",   DOC, "-12%", "+0Hz", 2.1),
]
