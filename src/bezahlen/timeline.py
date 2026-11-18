"""Gemeinsame Zeitachse: Sprecher-Timings, Tage, alle Kaufereignisse.

Die Beträge sind eine Beispielrechnung. Gleicher Einkaufszettel für alle drei,
Unterschiede entstehen nur durch Spontankäufe ("Extras").
Kontrollpunkte (kumuliert):
  Tag  8: BAR 142 · KARTE 163 · HANDY 171
  Tag 15: BAR 272 · KARTE 318 · HANDY 312   (Handy bremst durch Push)
  Tag 22: BAR 468 · KARTE 485 · HANDY 476   (Bar zieht durch Kleingeld an)
  Tag 30: BAR 629 · KARTE 668 · HANDY 641   (Karte läuft am schnellsten)
"""
import json
from pathlib import Path

from script import SCENES

BUILD = Path(__file__).resolve().parents[2] / "build" / "bezahlen"
DURATION = 60.0

# ------------------------------------------------------------------ Sprecher
TIM = json.loads((BUILD / "timings.json").read_text())
KEYS = [s["key"] for s in SCENES]

AUDIO_START = []
_prev_end = 0.0
for _i, (_s, _t) in enumerate(zip(SCENES, TIM)):
    _st = max(_s["start"] + (0.05 if _i == 0 else 0.15), _prev_end + 0.2)
    AUDIO_START.append(_st)
    _prev_end = _st + _t["words"][-1]["end"]


def _tokens(text):
    """Wörter mit Satzzeichen; ein freistehender Gedankenstrich hängt am Wort davor (Untertitel-Umbruch)."""
    out = []
    for tok in text.split():
        if any(ch.isalnum() for ch in tok):
            out.append(tok)
        elif out:
            out[-1] += " " + tok
    return out


def _norm(s):
    return "".join(ch for ch in s.lower() if ch.isalnum())


# Wortliste mit absoluten Zeiten + Anzeige-Token (inkl. Satzzeichen)
WORDS = []
for _i, (_s, _t) in enumerate(zip(SCENES, TIM)):
    toks = _tokens(_s["text"])
    k = 0
    for w in _t["words"]:
        nw = _norm(w["text"])
        # passendes Token suchen
        j = k
        while j < len(toks) and not _norm(toks[j]).startswith(nw[:3]):
            j += 1
        if j >= len(toks):
            j = min(k, len(toks) - 1)
        n = max(1, len(w["text"].split()))   # z. B. "470 Euro" kommt als eine Wortgrenze
        WORDS.append({"scene": _s["key"], "show": " ".join(toks[j:j + n]), "word": w["text"],
                      "start": AUDIO_START[_i] + w["start"], "end": AUDIO_START[_i] + w["end"]})
        k = j + n


def at(scene, prefix, occ=0):
    n = 0
    for w in WORDS:
        if w["scene"] == scene and _norm(w["word"]).startswith(_norm(prefix)):
            if n == occ:
                return w["start"]
            n += 1
    raise KeyError((scene, prefix, occ))


def scene_t(key):
    s = SCENES[KEYS.index(key)]
    return s["start"], s["end"]


# ------------------------------------------------------------------ Tage
# (erster Tag, letzter Tag, Startzeit, Endzeit)
DAYSEG = [(1, 8, 8.0, 16.0), (9, 15, 22.0, 30.0), (16, 22, 30.0, 38.0), (23, 30, 38.0, 43.6)]


def day_start(d):
    for a, b, t0, t1 in DAYSEG:
        if a <= d <= b:
            return t0 + (d - a) * (t1 - t0) / (b - a + 1)
    raise ValueError(d)


def current_day(t):
    for a, b, t0, t1 in DAYSEG:
        if t < t0:
            return max(1, a - 1)
        if t < t1:
            return min(b, a + int((t - t0) / ((t1 - t0) / (b - a + 1))))
    return 30


def is_moving(t):
    return any(t0 <= t < t1 for _, _, t0, t1 in DAYSEG)


def walked(t, speed=150.0):
    return sum(max(0.0, min(t, t1) - t0) for _, _, t0, t1 in DAYSEG) * speed


# ------------------------------------------------------------------ Einkäufe
FIGS = ["bar", "karte", "handy"]
PAY = {"bar": "bills", "karte": "card", "handy": "phone"}

SHOP = {  # gleicher Einkaufszettel: (Tag, Betrag)
    1: [(1, 38.40), (3, 29.90), (5, 34.60), (7, 27.10)],
    2: [(9, 31.20), (11, 26.80), (13, 29.50), (15, 27.50)],
    3: [(16, 36.90), (18, 33.40), (20, 38.20), (22, 31.50)],
    4: [(23, 34.80), (25, 29.60), (27, 33.10), (29, 27.50)],
}

K, S, Z, O = "kaffee", "snack", "zeitschrift", "online"
EXTRAS = {
    "bar": {
        1: [(K, 3.2), (S, 2.5), (Z, 4.8), (S, 1.5)],
        2: [(K, 3.2), (S, 2.5), (Z, 4.8), (K, 3.2), (S, 1.3)],
        3: [(S, 2.5), (K, 3.2), (S, 1.8), (S, 2.5), (K, 3.2), (S, 2.0), (Z, 4.8), (S, 2.5), (K, 3.2), (S, 1.8),
            (S, 2.5), (K, 3.2), (S, 2.0), (K, 3.2), (S, 2.5), (Z, 4.8), (K, 3.2), (S, 2.5), (K, 3.2), (S, 1.4)],
        4: [(K, 3.2), (S, 2.5), (S, 1.8), (K, 3.2), (Z, 4.8), (S, 2.5), (K, 3.2), (S, 2.0), (K, 3.2), (S, 2.5),
            (S, 1.8), (K, 3.2), (S, 2.1)],
    },
    "karte": {
        1: [(K, 3.2), (S, 2.5), (K, 3.2), (Z, 4.8), (S, 2.5), (K, 3.2), (O, 13.6)],
        2: [(K, 3.2), (S, 2.5), (K, 3.2), (O, 17.9), (S, 2.5), (K, 3.2), (Z, 4.8), (S, 2.7)],
        3: [(K, 3.2), (S, 2.5), (O, 12.9), (K, 3.2), (S, 2.5), (S, 2.7)],
        4: [(K, 3.2), (S, 2.5), (O, 15.7), (K, 3.2), (S, 2.5), (Z, 4.8), (K, 3.2), (O, 14.9), (S, 2.5), (K, 3.2),
            (S, 2.3)],
    },
    "handy": {
        1: [(K, 3.2), (S, 2.5), (K, 3.2), (S, 2.5), (Z, 4.8), (K, 3.2), (S, 2.5), (O, 19.1)],
        2: [(Z, 4.8), (K, 3.2), (S, 2.5), (O, 15.5)],
        3: [(K, 3.2), (S, 2.5), (O, 13.5), (K, 3.2), (S, 1.6)],
        4: [(K, 3.2), (S, 2.5), (O, 18.4), (K, 3.2), (Z, 4.8), (S, 2.5), (K, 3.2), (S, 2.2)],
    },
}
# Ausgelassene Extras (zögern / Push wirkt): (Segment, Anzahl, Symbol)
SKIPS = {"bar": {1: [K, S, Z], 2: [S, K]}, "handy": {2: [K, S, K, O]}}

TARGET = {"bar": [142, 272, 468, 629], "karte": [163, 318, 485, 668], "handy": [171, 312, 476, 641]}

ATM_T = (30.15, 31.7)   # Bar hebt Geld ab
PUSH_FROM = 22.0        # ab hier zeigt das Handy jede Zahlung an


def _spread(n, t0, t1, avoid, phase=0.5, jitter=0.0, seed=0):
    out = []
    for k in range(n):
        t = t0 + (k + phase) / n * (t1 - t0)
        t += jitter * (((k * 7919 + seed * 104729) % 97) / 97 - 0.5)
        for a in avoid:
            if abs(t - a) < 0.28:
                t = a + 0.3
        out.append(round(t, 3))
    return out


def build_events():
    ev = []
    for fi, f in enumerate(FIGS):
        slot = 0
        for seg in (1, 2, 3, 4):
            a, b, t0, t1 = DAYSEG[seg - 1]
            shop_ts = []
            for d, amt in SHOP[seg]:
                ts = day_start(d) + 0.12 + 0.05 * fi
                shop_ts.append(ts)
                ev.append(dict(t=ts, fig=f, kind="einkauf", amount=amt, extra=False, skip=False))
            lo = t0 + 0.35
            if f == "bar" and seg == 3:
                lo = ATM_T[1] + 0.15
            hi = t1 - 0.35
            items = EXTRAS[f][seg]
            for (kind, amt), ts in zip(items, _spread(len(items), lo, hi, shop_ts, 0.45, 0.25, fi + seg)):
                ev.append(dict(t=ts, fig=f, kind=kind, amount=amt, extra=True, skip=False, slot=slot))
                slot += 1
            sk = SKIPS.get(f, {}).get(seg, [])
            taken = shop_ts + [e["t"] for e in ev if e["fig"] == f]
            for kind, ts in zip(sk, _spread(len(sk), lo, hi, taken, 0.85, 0.2, fi * 3 + seg)):
                ev.append(dict(t=ts, fig=f, kind=kind, amount=0.0, extra=False, skip=True))
    # Mindestabstand je Figur, damit sich Gesten nicht überlagern
    for f in FIGS:
        mine = sorted((e for e in ev if e["fig"] == f), key=lambda e: e["t"])
        for p, q in zip(mine, mine[1:]):
            if q["t"] < p["t"] + 0.2:
                q["t"] = round(p["t"] + 0.2, 3)
    for e in ev:
        f = e["fig"]
        e["pay"] = PAY[f]
        if f == "bar" and e["t"] >= ATM_T[0] and e["extra"]:
            e["pay"] = "coin"
        e["push"] = f == "handy" and not e["skip"] and e["t"] >= PUSH_FROM
        # Bar zählt in den ersten zwei Wochen Scheine ab -> längere Bezahlgeste
        e["paydur"] = 0.85 if (e["pay"] == "bills" and not e["skip"]) else 0.45
    ev.sort(key=lambda e: e["t"])
    return ev


EVENTS = build_events()


def check():
    cps = [16.0, 30.0, 38.0, 43.6]
    for f in FIGS:
        vals = [round(sum(e["amount"] for e in EVENTS if e["fig"] == f and e["t"] < cp), 2) for cp in cps]
        assert vals == [float(v) for v in TARGET[f]], (f, vals, TARGET[f])
        assert all(e["t"] + 0.35 < 43.6 for e in EVENTS), "Kauf nach Tag 30"
    return True


if __name__ == "__main__":
    check()
    print("Kontrollpunkte stimmen.")
    for i, s in enumerate(SCENES):
        print(f"{s['key']:9s} audio {AUDIO_START[i]:5.2f} – {AUDIO_START[i] + TIM[i]['words'][-1]['end']:5.2f}"
              f"   Fenster {s['start']}–{s['end']}")
    print(len(EVENTS), "Ereignisse")
    for f in FIGS:
        print(f, sum(1 for e in EVENTS if e["fig"] == f and e["extra"]), "Extras")
