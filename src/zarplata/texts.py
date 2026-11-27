"""All on-screen texts. LANG=ru (default) or LANG=de."""
import os

LANG = os.environ.get("LANG_VIDEO", "ru")

_TEXTS = {
    "ru": {
        "salary": "ЗАРПЛАТА",
        "rent": "АРЕНДА",
        "util_spin": "КОММУНАЛКА",
        "tax": "НАЛОГИ",
        "cashback": "КЭШБЭК",
        "food": "ДОСТАВКА\nЕДЫ",
        "dentist": "ВНЕЗАПНЫЙ\nЗУБНОЙ",
        "subs": "ПОДПИСКИ",
        "bday": "ДР\nДРУГА",
        "credit": "КРЕДИТ",
        "fine": "ШТРАФ",
        "bonus": "ПРЕМИЯ",
        "prices": "ЦЕНЫ ВЫРОСЛИ",
        "loan": "МИКРО-\nЗАЙМ",
        "vacation": "ОТПУСК",
        "broke": "ДОШИРАК\nДО ЗП",
        "hook1": "ДОЖИВЁТ ЛИ",
        "hook2": "МОЯ ЗАРПЛАТА",
        "hook3": "ДО ОТПУСКА?",
        "payday": "ДЕНЬ ЗАРПЛАТЫ",
        "to_vacation": "до отпуска",
        "made_it": "ДОЛЕТЕЛА!",
        "left": "Осталось на отпуск:",
        "punch": "Отпуск: шашлык на балконе",
        "cta1": "А ТВОЯ ЗАРПЛАТА",
        "cta2": "ДОЛЕТЕЛА БЫ?",
        "cta3": "Пиши в комменты, что съедает твою",
        "comeon": "НУ ЖЕ... НУ ЖЕ...",
        "paid": "ОПЛАЧЕНО",
        "currency": "₽",
        "sep": " ",
    },
    "de": {
        "salary": "GEHALT",
        "rent": "MIETE",
        "util_spin": "NEBENKOSTEN",
        "tax": "STEUER",
        "cashback": "CASHBACK",
        "food": "ESSEN\nBESTELLT",
        "dentist": "ZAHNARZT\nÜBERRASCHUNG",
        "subs": "ABOS",
        "bday": "GEBURTS-\nTAG",
        "credit": "KREDIT",
        "fine": "KNÖLLCHEN",
        "bonus": "BONUS",
        "prices": "INFLATION",
        "loan": "DISPO",
        "vacation": "URLAUB",
        "broke": "NUDELN\nBIS ZUM 1.",
        "hook1": "SCHAFFT ES",
        "hook2": "MEIN GEHALT",
        "hook3": "BIS ZUM URLAUB?",
        "payday": "ZAHLTAG",
        "to_vacation": "bis Urlaub",
        "made_it": "GESCHAFFT!",
        "left": "Übrig für den Urlaub:",
        "punch": "Urlaub: Balkonien",
        "cta1": "WÜRDE DEIN GEHALT",
        "cta2": "ES SCHAFFEN?",
        "cta3": "Schreib in die Kommentare, was deins frisst",
        "comeon": "KOMM SCHON...",
        "paid": "BEZAHLT",
        "currency": "€",
        "sep": ".",
    },
}

# money is simulated in roubles; for German we scale to euro-ish numbers
SCALE = {"ru": 1.0, "de": 0.03}[LANG]

T = _TEXTS[LANG]


def money(v, sign=False):
    v = round(v * SCALE)
    s = f"{abs(v):,}".replace(",", T["sep"])
    pre = ("+" if v > 0 else "−" if v < 0 else "") if sign else ("−" if v < 0 else "")
    return f"{pre}{s} {T['currency']}"
