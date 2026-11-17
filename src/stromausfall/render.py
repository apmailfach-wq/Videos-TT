"""Render stromausfall-video.mp4 (1080x1920, 30 fps) – "Was wäre, wenn…?"-Erklärformat.

Oben ein großer Tageszähler (TAG 1 … TAG 7), darunter zwei Anzeigen (Gespart: Strom / Ausgegeben),
darunter eine feste Szene: eine Wohnung, die mit jedem Tag dunkler wird (Licht aus, Kühlschrank tropft,
Kerzen, Pizzakartons), Strichmännchen in Türkis. Untertitel Wort für Wort, Emoji-Sticker,
Whoosh- und Kassen-Sounds, Community-Frage am Ende.

    python3 tts.py && python3 render.py           # -> ../../stromausfall-video.mp4
    python3 render.py preview 2 9 20 40            # Standbilder -> build/stromausfall/stills/
"""
import json
import math
import os
import subprocess
import sys
import wave
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "stromausfall"
FONTS = ROOT / "fonts"
W, H, FPS = 1080, 1920, 30
TAIL = 1.3

F_HEAD = str(FONTS / "Unbounded_900Black.ttf")
F_HEAD_B = str(FONTS / "Unbounded_700Bold.ttf")
F_HAND = str(FONTS / "Caveat_700Bold.ttf")
F_BODY_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_CAP = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

INK = (20, 22, 26)
GREY = (139, 147, 155)
TEAL = (24, 168, 152)
TEAL_F = (34, 179, 164)
TEAL_B = (20, 140, 128)
GREEN = (30, 168, 88)
RED = (229, 72, 77)
PAPER = (255, 255, 255)
YELLOW = (255, 226, 0)

ROOM_X, ROOM_Y, ROOM_W, ROOM_H = 40, 600, 1000, 900
GROUND = 805          # figure ground line (room-local)


@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, size)


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def ease_back(x, s=1.4):
    x = clamp01(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_col(a, b, t):
    return tuple(int(lerp(a[i], b[i], t)) for i in range(len(a)))


# ------------------------------------------------------------------ timings
TIM = json.loads((BUILD / "timings.json").read_text())
sys.path.insert(0, str(Path(__file__).resolve().parent))
from script import SCENES, QUESTION  # noqa: E402

KEYS = [s["key"] for s in SCENES]
OFF = []
_a = 0.0
for _s in TIM:
    OFF.append(_a)
    _a += _s["duration"]
TOTAL = _a + TAIL
NFRAMES = int(math.ceil(TOTAL * FPS))


def at(scene, word, occ=0, lead=0.05):
    si = KEYS.index(scene)
    n = 0
    for w in TIM[si]["words"]:
        if w["text"].strip(".,:!?").startswith(word):
            if n == occ:
                return OFF[si] + w["start"] - lead
            n += 1
    raise KeyError((scene, word, occ))


def s0(scene):
    return OFF[KEYS.index(scene)]


def s1(scene):
    i = KEYS.index(scene)
    return OFF[i] + TIM[i]["duration"] + (TAIL if i == len(TIM) - 1 else 0)


# ------------------------------------------------------------------ story data
# Tagesgrenzen (Beginn von Tag 1..7) und Ende der Woche
DAYS = [s0("tag1"), s0("tag2"), s0("tag3"), s0("tag45"), at("tag45", "fünf"), s0("tag67"), at("tag67", "sieben")]
WEEK_END = s1("tag67")
SAVED_TOTAL = 22
# Ausgaben: (Zeitpunkt, Betrag) – Summe 240 €
SPENDS = [(at("tag1", "25"), 25), (at("tag2", "60"), 60), (at("tag3", "35"), 35),
          (at("tag45", "50"), 50), (at("tag67", "70"), 70)]
SPENT_TOTAL = sum(a for _, a in SPENDS)
T_LIGHT_OFF = at("tag1", "Licht")
T_DRIP = at("tag2", "tropft")
T_TRASH = at("tag2", "Müll")
T_STAMP = at("fazit", "ausgegeben")
T_Q = s0("cta")


def day_float(t):
    """0 before day 1, 7 at the end of the week (continuous)."""
    if t < DAYS[0]:
        return 0.0
    bounds = DAYS + [WEEK_END]
    for i in range(7):
        if t < bounds[i + 1]:
            return i + (t - bounds[i]) / (bounds[i + 1] - bounds[i])
    return 7.0


def day_num(t):
    n = 0
    for i, d in enumerate(DAYS):
        if t >= d:
            n = i + 1
    return n


def saved(t):
    return SAVED_TOTAL * day_float(t) / 7


def spent(t):
    v = 0.0
    for ts, a in SPENDS:
        v += a * ease_out((t - ts) / 0.7)
    return v


def darkness(t):
    if t < T_LIGHT_OFF + 0.1:
        return 0.0
    flick = T_LIGHT_OFF + 0.1
    if t < flick + 0.35:   # lamp flickers out
        u = (t - flick) / 0.35
        return 0.5 * u * (0.6 + 0.4 * (math.sin(u * 40) > 0))
    return 0.55 + 0.33 * clamp01(day_float(t) / 7)


# candles: (room-local x, time lit)
CANDLES = [(452, at("tag1", "Kerzen") + 0.1), (598, s0("tag3") + 0.3), (525, s0("tag45") + 0.2),
           (402, s0("tag67") + 0.3)]
TABLE_TOP = 585


def flames(t):
    out = []
    for k, (x, t0) in enumerate(CANDLES):
        if t < t0:
            continue
        p = ease_back((t - t0) / 0.4, 1.6)
        hgt = 74 - 38 * clamp01((t - t0) / 30)
        fl = 1 + 0.07 * math.sin(t * 13 + k * 2.1) + 0.05 * math.sin(t * 23.7 + k)
        out.append((x, TABLE_TOP - hgt, hgt, p * fl, p))
    return out


# pizza boxes: times each box lands
PIZZA = [at("tag3", "bestellen") + 0.35, s0("tag45") + 0.2, at("tag45", "fünf") + 0.1,
         at("tag45", "Pizzakartons"), at("tag45", "stapeln"), at("tag45", "sich"), s0("tag67") + 0.4]

# Emoji-Sticker: (time, emoji, frame x, frame y)
STICKERS = [
    (at("hook", "Strom"), "🔌", 905, 700),
    (at("hook", "kostet"), "💶", 175, 700),
    (T_LIGHT_OFF, "💡", 905, 700),
    (at("tag1", "Kerzen"), "🕯️", 175, 700),
    (T_DRIP, "💧", 175, 700),
    (T_TRASH, "🗑️", 905, 700),
    (at("tag3", "Herd"), "🍳", 905, 700),
    (at("tag3", "bestellen"), "🛵", 175, 700),
    (at("tag45", "Pizzakartons"), "🍕", 905, 700),
    (at("tag67", "Tiefkühltruhe"), "🧊", 175, 700),
    (at("tag67", "Waschsalon"), "🧺", 905, 700),
    (at("tag67", "Powerbank"), "🔋", 175, 700),
    (at("fazit", "22"), "⚡", 175, 700),
    (at("fazit", "240"), "💸", 905, 700),
]


# ------------------------------------------------------------------ helpers
def supersample(w, h, draw_fn, ss=2):
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    draw_fn(im, ImageDraw.Draw(im), ss)
    return im.resize((w, h), Image.LANCZOS)


def with_shadow(im, dy=16, blur=18, alpha=0.22, pad=40):
    out = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    a = im.getchannel("A").point(lambda v: int(v * alpha))
    sh = Image.new("RGBA", im.size, (20, 26, 36, 0))
    sh.putalpha(a)
    tmp = Image.new("RGBA", out.size, (0, 0, 0, 0))
    tmp.alpha_composite(sh, (pad, pad + dy))
    tmp = tmp.filter(ImageFilter.GaussianBlur(blur))
    tmp.alpha_composite(im, (pad, pad))
    return tmp


def paste_center(dst, img, cx, cy, scale=1.0, rot=0.0, alpha=1.0):
    if rot:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    if abs(scale - 1) > 0.01:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BICUBIC)
    if alpha < 0.99:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    dst.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))


@lru_cache(maxsize=64)
def emoji_img(ch, size=150, shadow=True):
    f = ImageFont.truetype(F_EMOJI, 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((80, 80), ch, font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox())
    sc = size / max(im.size)
    im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
    return with_shadow(im, dy=8, blur=10, alpha=0.3, pad=30) if shadow else im


# ------------------------------------------------------------------ stick figure (wie Vorlage)
SEG = dict(torso=92, ua=56, fa=54, th=70, sh=68, head=31, limb=25, tw=33)
POSES = {
    "stand":  dict(t=0, uaf=10, faf=14, uab=-10, fab=-6, thf=5, shf=0, thb=-5, shb=0),
    "cower":  dict(t=-12, uaf=70, faf=168, uab=58, fab=172, thf=32, shf=-12, thb=6, shb=-26),
    "walk1":  dict(t=4, uaf=30, faf=45, uab=-30, fab=-15, thf=24, shf=4, thb=-24, shb=-34),
    "walk2":  dict(t=4, uaf=-30, faf=-15, uab=30, fab=45, thf=-24, shf=-34, thb=24, shb=4),
    "handsup": dict(t=-4, uaf=158, faf=172, uab=148, fab=168, thf=5, shf=0, thb=-5, shb=0),
    "shrug":  dict(t=0, uaf=30, faf=120, uab=-30, fab=-120, thf=5, shf=0, thb=-5, shb=0),
    "phone":  dict(t=2, uaf=40, faf=165, uab=-10, fab=-6, thf=5, shf=0, thb=-5, shb=0),
    "facepalm": dict(t=8, uaf=60, faf=175, uab=-12, fab=-8, thf=6, shf=0, thb=-6, shb=0),
    "reach":  dict(t=10, uaf=82, faf=86, uab=-12, fab=-8, thf=12, shf=2, thb=-12, shb=0),
}


def lerp_pose(a, b, t):
    return {k: lerp(a[k], b[k], t) for k in a}


def figure_points(p, facing=1, s=1.0):
    def v(a, L, up=False):
        r = math.radians(a)
        if up:
            return (math.sin(r) * facing * L * s, -math.cos(r) * L * s)
        return (math.sin(r) * facing * L * s, math.cos(r) * L * s)

    add = lambda P, Q: (P[0] + Q[0], P[1] + Q[1])  # noqa: E731
    hip = (0.0, 0.0)
    sho = add(hip, v(p["t"], SEG["torso"], up=True))
    head = add(sho, v(p["t"], SEG["head"] + 10, up=True))
    ef = add(sho, v(p["uaf"], SEG["ua"]))
    hf = add(ef, v(p["faf"], SEG["fa"]))
    eb = add(sho, v(p["uab"], SEG["ua"]))
    hb = add(eb, v(p["fab"], SEG["fa"]))
    kf = add(hip, v(p["thf"], SEG["th"]))
    ff = add(kf, v(p["shf"], SEG["sh"]))
    kb = add(hip, v(p["thb"], SEG["th"]))
    fb = add(kb, v(p["shb"], SEG["sh"]))
    pts = dict(hip=hip, sho=sho, head=head, ef=ef, hf=hf, eb=eb, hb=hb, kf=kf, ff=ff, kb=kb, fb=fb)
    lw = SEG["limb"] * s / 2
    ground = max(max(q[1] + lw for k, q in pts.items() if k != "head"), head[1] + SEG["head"] * s)
    return {k: (q[0], q[1] - ground) for k, q in pts.items()}


def draw_figure(d, pts, ox, oy, s, col_f, col_b, ss=1):
    def P(k):
        return ((ox + pts[k][0]) * ss, (oy + pts[k][1]) * ss)

    cur = [col_b]

    def limb(a, b, c, w):
        w = w * s * ss
        seq = [P(a), P(b)] + ([P(c)] if c else [])
        d.line(seq, fill=cur[0], width=int(w), joint="curve")
        for q in seq:
            d.ellipse([q[0] - w / 2, q[1] - w / 2, q[0] + w / 2, q[1] + w / 2], fill=cur[0])

    limb("sho", "eb", "hb", SEG["limb"])
    limb("hip", "kb", "fb", SEG["limb"])
    cur[0] = col_f
    limb("hip", "sho", None, SEG["tw"])
    hx, hy = P("head")
    r = SEG["head"] * s * ss
    d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=col_f)
    limb("hip", "kf", "ff", SEG["limb"])
    limb("sho", "ef", "hf", SEG["limb"])


class Fig:
    def __init__(self, keys, s=1.25):
        self.keys, self.s = sorted(keys, key=lambda k: k[0]), s

    def state(self, t):
        ks = self.keys
        if t <= ks[0][0]:
            return POSES[ks[0][1]], ks[0][2], ks[0][3]
        for (ta, pa, xa, fa), (tb, pb, xb, fb) in zip(ks, ks[1:]):
            if ta <= t < tb:
                u = ease_io((t - ta) / (tb - ta))
                return lerp_pose(POSES[pa], POSES[pb], u), lerp(xa, xb, u), fb if u > 0.5 else fa
        return POSES[ks[-1][1]], ks[-1][2], ks[-1][3]

    def draw(self, d, t, ss):
        p, x, facing = self.state(t)
        sw = 70 * self.s
        d.ellipse([(x - sw) * ss, (GROUND - 12 * self.s) * ss, (x + sw) * ss, (GROUND + 12 * self.s) * ss],
                  fill=(20, 30, 40, 50))
        draw_figure(d, figure_points(p, facing, self.s), x, GROUND, self.s, TEAL_F, TEAL_B, ss)


def walk(t0, t1, x0, x1, end="stand", step=0.22):
    facing = 1 if x1 >= x0 else -1
    keys, n = [], max(2, int((t1 - t0) / step))
    for i in range(n + 1):
        u = i / n
        pose = end if i == n else ("walk1" if i % 2 else "walk2")
        keys.append((lerp(t0, t1, u), pose, lerp(x0, x1, u), facing))
    return keys


def build_figure():
    k = [(0.0, "stand", 560, -1), (at("hook", "Strom"), "reach", 560, -1),
         (at("hook", "kostet"), "shrug", 560, -1), (at("hook", "Rechnen"), "stand", 560, 1)]
    k += [(T_LIGHT_OFF, "handsup", 560, 1), (T_LIGHT_OFF + 0.7, "cower", 560, 1)]
    k += walk(at("tag1", "Kerzen") - 0.3, at("tag1", "Kerzen") + 0.6, 560, 640, "reach")
    k += [(at("tag1", "Batterien"), "stand", 640, -1)]
    k += walk(s0("tag2") + 0.1, s0("tag2") + 1.0, 640, 330, "reach")
    k += [(T_DRIP, "cower", 330, -1), (T_TRASH, "facepalm", 330, -1)]
    k += walk(s0("tag3") + 0.05, s0("tag3") + 0.8, 330, 620, "stand")
    k += [(at("tag3", "Herd"), "shrug", 620, 1), (at("tag3", "bestellen"), "phone", 620, 1)]
    k += walk(s0("tag45") + 0.05, s0("tag45") + 0.7, 620, 700, "stand")
    k += [(at("tag45", "Pizzakartons"), "shrug", 700, 1), (at("tag45", "50"), "facepalm", 700, 1)]
    k += walk(s0("tag67") + 0.05, s0("tag67") + 1.0, 700, 520, "cower")
    k += [(at("tag67", "Waschsalon"), "shrug", 520, -1), (at("tag67", "Powerbank"), "phone", 520, -1)]
    k += [(s0("fazit"), "stand", 520, 1), (at("fazit", "aber"), "handsup", 520, 1),
          (T_STAMP + 0.4, "facepalm", 520, 1)]
    k += [(T_Q, "shrug", 520, 1)]
    return Fig(k)


# ------------------------------------------------------------------ room sprites
WALL = (232, 220, 200)
WALL_D = (214, 200, 178)
FLOOR = (190, 150, 108)
FLOOR_L = (176, 136, 96)


def room_base(lights_on):
    w, h = ROOM_W, ROOM_H

    def fn(im, d, ss):
        S = ss
        d.rectangle([0, 0, w * S, 640 * S], fill=WALL)
        for x in range(0, w, 70):  # subtle wallpaper stripes
            d.rectangle([x * S, 0, (x + 32) * S, 640 * S], fill=lerp_col(WALL, WALL_D, 0.25))
        d.rectangle([0, 620 * S, w * S, 648 * S], fill=(245, 240, 230))         # skirting
        d.rectangle([0, 648 * S, w * S, h * S], fill=FLOOR)
        for y in (700, 770, 850):
            d.line([(0, y * S), (w * S, y * S)], fill=FLOOR_L, width=3 * S)
        for i, y in enumerate((648, 700, 770, 850)):
            for x in range(60 + i * 90, w, 260):
                d.line([(x * S, y * S), (x * S, min(h, y + (52 if y == 648 else 70 if y == 700 else 80)) * S)],
                       fill=FLOOR_L, width=3 * S)
        # window with night city
        wx0, wy0, wx1, wy1 = 640, 120, 880, 390
        for yy in range(wy0, wy1):
            u = (yy - wy0) / (wy1 - wy0)
            d.line([(wx0 * S, yy * S), (wx1 * S, yy * S)], fill=lerp_col((26, 34, 68), (70, 74, 120), u), width=S)
        d.ellipse([(wx0 + 30) * S, (wy0 + 26) * S, (wx0 + 66) * S, (wy0 + 62) * S], fill=(250, 244, 210))
        for bx, bw, bh in ((640, 70, 150), (705, 60, 210), (760, 80, 120), (835, 50, 180)):
            d.rectangle([bx * S, (wy1 - bh) * S, (bx + bw) * S, wy1 * S], fill=(36, 40, 58))
            for r in range(wy1 - bh + 16, wy1 - 12, 26):
                for c in range(bx + 10, bx + bw - 12, 20):
                    lit = lights_on and ((r * 7 + c * 3) % 5 != 0)
                    d.rectangle([c * S, r * S, (c + 9) * S, (r + 12) * S],
                                fill=(255, 214, 110) if lit else (52, 58, 78))
        d.rectangle([wx0 * S, wy0 * S, wx1 * S, wy1 * S], outline=(250, 250, 248), width=14 * S)
        d.line([((wx0 + wx1) / 2 * S, wy0 * S), ((wx0 + wx1) / 2 * S, wy1 * S)], fill=(250, 250, 248), width=10 * S)
        d.rectangle([(wx0 - 20) * S, wy1 * S, (wx1 + 20) * S, (wy1 + 16) * S], fill=(245, 242, 236))
        # TV sideboard
        d.rounded_rectangle([700 * S, 560 * S, 960 * S, 700 * S], radius=8 * S, fill=(120, 96, 76))
        d.line([(830 * S, 570 * S), (830 * S, 690 * S)], fill=(96, 76, 60), width=4 * S)
        d.rounded_rectangle([730 * S, 430 * S, 930 * S, 550 * S], radius=8 * S, fill=(30, 32, 38))
        d.rectangle([822 * S, 550 * S, 838 * S, 562 * S], fill=(30, 32, 38))
        if lights_on:
            d.rounded_rectangle([742 * S, 442 * S, 918 * S, 538 * S], radius=4 * S, fill=(80, 150, 210))
            d.ellipse([800 * S, 470 * S, 860 * S, 510 * S], fill=(140, 200, 240))
        # fridge
        fx0, fx1, fy0, fy1 = 60, 250, 230, 690
        d.rounded_rectangle([fx0 * S, fy0 * S, fx1 * S, fy1 * S], radius=18 * S, fill=(238, 242, 245),
                            outline=(170, 178, 186), width=4 * S)
        d.line([(fx0 * S, 380 * S), (fx1 * S, 380 * S)], fill=(170, 178, 186), width=4 * S)
        d.rounded_rectangle([(fx1 - 34) * S, 270 * S, (fx1 - 22) * S, 350 * S], radius=6 * S, fill=(160, 168, 176))
        d.rounded_rectangle([(fx1 - 34) * S, 410 * S, (fx1 - 22) * S, 520 * S], radius=6 * S, fill=(160, 168, 176))
        d.rounded_rectangle([90 * S, 300 * S, 120 * S, 334 * S], radius=4 * S, fill=(250, 210, 80))  # magnet
        d.rounded_rectangle([130 * S, 430 * S, 175 * S, 480 * S], radius=4 * S, fill=(255, 255, 255),
                            outline=(200, 205, 210), width=2 * S)                                   # note
        # trash bin
        d.rounded_rectangle([272 * S, 600 * S, 352 * S, 705 * S], radius=10 * S, fill=(120, 130, 140))
        d.rounded_rectangle([264 * S, 588 * S, 360 * S, 606 * S], radius=6 * S, fill=(96, 104, 114))
        # table
        d.rounded_rectangle([370 * S, TABLE_TOP * S, 680 * S, (TABLE_TOP + 20) * S], radius=6 * S,
                            fill=(150, 104, 70))
        for lx in (390, 648):
            d.rectangle([lx * S, (TABLE_TOP + 18) * S, (lx + 14) * S, 735 * S], fill=(128, 88, 58))
        # ceiling lamp cord + shade
        d.line([(500 * S, 0), (500 * S, 120 * S)], fill=(70, 70, 76), width=4 * S)
        d.chord([440 * S, 110 * S, 560 * S, 210 * S], 180, 360, fill=(60, 66, 76))
        d.ellipse([486 * S, 146 * S, 514 * S, 174 * S], fill=(255, 238, 170) if lights_on else (190, 192, 186))
    return supersample(w, h, fn)


def lamp_cone():
    w, h = ROOM_W, ROOM_H
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(450, 160), (550, 160), (760, 760), (240, 760)], fill=(255, 236, 160, 46))
    return im.filter(ImageFilter.GaussianBlur(18))


def pizza_box(k):
    w, h = 210, 40

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=5 * S, fill=(205, 160, 104), outline=(160, 120, 74),
                            width=3 * S)
        d.rectangle([4 * S, 4 * S, (w - 4) * S, 12 * S], fill=(222, 182, 128))
        d.ellipse([(w / 2 - 15) * S, 12 * S, (w / 2 + 15) * S, 36 * S], fill=(214, 64, 52))
        d.text((w / 2 * S, 24 * S), "P", font=font(F_HEAD, 16 * S), fill=PAPER, anchor="mm")
    return supersample(w, h, fn)


# ------------------------------------------------------------------ HUD sprites
def meter_card(label, col, emoji):
    w, h = 480, 230

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=30 * S, fill=PAPER)
        d.rounded_rectangle([0, 0, 16 * S, h * S], radius=8 * S, fill=col)
        d.text((96 * S, 54 * S), label, font=font(F_HEAD_B, 25 * S), fill=col, anchor="lm")
        d.rounded_rectangle([40 * S, 192 * S, (w - 40) * S, 206 * S], radius=7 * S, fill=(230, 233, 236))
    im = supersample(w, h, fn)
    e = emoji_img(emoji, 46, shadow=False)
    im.alpha_composite(e, (36, 54 - e.height // 2))
    return im


def question_card():
    w = 940
    f = font(F_HEAD, 58)
    words = []
    for tok in QUESTION.split():
        words.append((tok.strip("*").upper(), tok.startswith("*")))
    sp = f.getlength(" ")
    lines, cur, cw = [], [], 0
    for wd, hl in words:
        ww = f.getlength(wd)
        if cur and cw + sp + ww > w - 100:
            lines.append(cur)
            cur, cw = [], 0
        cur.append((wd, hl, ww))
        cw += (sp if len(cur) > 1 else 0) + ww
    lines.append(cur)
    lh = 80
    h = lh * len(lines) + 200

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=48 * S, fill=PAPER)
        d.text((w / 2 * S, 64 * S), "UND DU?", font=font(F_HEAD_B, 30 * S), fill=GREY, anchor="mm")
        y = 110 + lh * 0.78
        for ln in lines:
            lw = sum(x[2] for x in ln) + sp * (len(ln) - 1)
            x = (w - lw) / 2
            for wd, hl, ww in ln:
                d.text((x * S, y * S), wd, font=font(F_HEAD, 58 * S), fill=(TEAL if hl else INK), anchor="ls")
                x += ww + sp
            y += lh
        d.text((w / 2 * S, (h - 52) * S), "Schreib's in die Kommentare 👇".replace(" 👇", ""),
               font=font(F_BODY_B, 34 * S), fill=(90, 96, 104), anchor="mm")
    im = supersample(w, h, fn)
    return with_shadow(im, dy=16, blur=24, alpha=0.35)


def stamp_img(text, col=RED, size=70):
    f = font(F_HEAD, size)
    lines = text.split("\n")
    tw = max(f.getlength(l) for l in lines)
    w, h = int(tw + 80), int(size * 1.25 * len(lines) + 50)

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([4 * S, 4 * S, (w - 4) * S, (h - 4) * S], radius=16 * S, fill=PAPER, outline=col,
                            width=8 * S)
        for i, ln in enumerate(lines):
            d.text((w / 2 * S, (h / 2 + (i - (len(lines) - 1) / 2) * size * 1.2) * S), ln,
                   font=font(F_HEAD, size * S), fill=col, anchor="mm")
    return with_shadow(supersample(w, h, fn), dy=10, blur=14, alpha=0.4)


def text_img(text, f, fill, stroke=0, stroke_fill=(0, 0, 0)):
    l, t, r, b = f.getbbox(text, stroke_width=stroke)
    im = Image.new("RGBA", (r - l + 8, b - t + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - l, 4 - t), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    return im


def make_bg(dark):
    y = np.linspace(0, 1, H)[:, None]
    if not dark:
        top, bot = np.array([250, 251, 252], np.float32), np.array([214, 221, 226], np.float32)
    else:
        top, bot = np.array([18, 22, 30], np.float32), np.array([34, 40, 52], np.float32)
    g = top + (bot - top) * y[..., None]
    arr = np.repeat(g, W, axis=1)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")


# ------------------------------------------------------------------ globals built in init()
G = {}
YY, XX = np.mgrid[0:ROOM_H, 0:ROOM_W].astype(np.float32)


def init():
    G["bg"] = (make_bg(False), make_bg(True))
    G["room_on"] = room_base(True)
    G["room_off"] = room_base(False)
    G["cone"] = lamp_cone()
    G["pizza"] = pizza_box(0)
    G["fig"] = build_figure()
    G["m_saved"] = meter_card("GESPART: STROM", GREEN, "⚡")
    G["m_spent"] = meter_card("AUSGEGEBEN", RED, "💸")
    G["question"] = question_card()
    G["stamp"] = stamp_img("BILANZ\n−218 €")
    G["trash"] = [emoji_img(e, 54, shadow=False) for e in ("🥩", "🥛", "🧀")]
    G["caps"] = build_caps()
    G["round"] = room_mask()


def room_mask():
    m = Image.new("L", (ROOM_W * 2, ROOM_H * 2), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, ROOM_W * 2, ROOM_H * 2], radius=80, fill=255)
    return m.resize((ROOM_W, ROOM_H), Image.LANCZOS)


# ------------------------------------------------------------------ room per frame
def draw_room(t):
    dk = darkness(t)
    lights = t < T_LIGHT_OFF + 0.1 or (t < T_LIGHT_OFF + 0.45 and math.sin((t - T_LIGHT_OFF) * 40) > 0)
    room = (G["room_on"] if lights else G["room_off"]).copy()
    d = ImageDraw.Draw(room)
    # fridge display
    if lights:
        d.rounded_rectangle([100, 250, 170, 282], radius=6, fill=(20, 30, 36))
        d.text((135, 266), "4°C", font=font(F_HEAD_B, 18), fill=(90, 230, 170), anchor="mm")
    else:
        d.rounded_rectangle([100, 250, 170, 282], radius=6, fill=(20, 22, 26))
    # puddle under fridge
    if t >= T_DRIP:
        grow = 40 + 120 * ease_out((t - T_DRIP) / 6) + 110 * ease_out((t - at("tag67", "Tiefkühltruhe")) / 3)
        pw, ph = grow, grow * 0.16
        cx, cy = 175, 712
        d.ellipse([cx - pw, cy - ph, cx + pw, cy + ph], fill=(120, 180, 230))
        d.ellipse([cx - pw * 0.6, cy - ph * 0.55, cx - pw * 0.1, cy - ph * 0.1], fill=(190, 225, 250))
    # trash overflow
    if t >= T_TRASH:
        for k, (img, (ox, oy, r)) in enumerate(zip(G["trash"], ((292, 578, -15), (322, 570, 12), (308, 548, 4)))):
            p = ease_back((t - T_TRASH - k * 0.12) / 0.35, 2.0)
            if p > 0:
                paste_center(room, img, ox, oy - (1 - p) * 60, scale=max(0.05, p), rot=r)
    # pizza boxes on the floor (right), stacking up
    n = 0
    for k, tp in enumerate(PIZZA):
        p = (t - tp) / 0.35
        if p <= 0:
            continue
        y = 850 - k * 36 - (1 - ease_out(p)) * 260
        x = 845 + (((k * 37) % 17) - 8) * 1.8
        room.alpha_composite(G["pizza"], (int(x - 105), int(y - 40)))
        n += 1
    if lights:
        room.alpha_composite(G["cone"])

    # anti-aliased dynamic layer: candles, drips, figure
    SS = 2
    fl = Image.new("RGBA", (ROOM_W * SS, ROOM_H * SS), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fl)
    for (x, ytop, hgt, f, p) in flames(t):
        cw = 22
        fd.rounded_rectangle([(x - cw / 2) * SS, ytop * SS, (x + cw / 2) * SS, TABLE_TOP * SS], radius=5 * SS,
                             fill=(250, 244, 228))
        fd.rounded_rectangle([(x - 18) * SS, (TABLE_TOP - 6) * SS, (x + 18) * SS, (TABLE_TOP + 2) * SS],
                             radius=4 * SS, fill=(190, 160, 110))
        fh = 30 * f * p
        sway = math.sin(t * 9 + x) * 2.5
        fd.ellipse([(x - 9 * p + sway) * SS, (ytop - 6 - fh) * SS, (x + 9 * p + sway) * SS, (ytop + 4) * SS],
                   fill=(255, 170, 40))
        fd.ellipse([(x - 4.5 * p + sway) * SS, (ytop - 2 - fh * 0.6) * SS, (x + 4.5 * p + sway) * SS,
                    (ytop + 2) * SS], fill=(255, 245, 190))
    if t >= T_DRIP:
        for k in range(3):
            u = ((t - T_DRIP) * 0.9 + k / 3) % 1.0
            dx, dy = 200 + k * 14, lerp(392, 700, u ** 1.6)
            a = int(255 * (1 - clamp01((u - 0.85) / 0.15)))
            fd.ellipse([(dx - 7) * SS, (dy - 10) * SS, (dx + 7) * SS, (dy + 8) * SS], fill=(80, 150, 225, a))
    G["fig"].draw(fd, t, SS)
    fl = fl.resize((ROOM_W, ROOM_H), Image.LANCZOS)
    room.alpha_composite(fl)

    # darkness with candle glow
    if dk > 0.001:
        arr = np.asarray(room.convert("RGB"), np.float32)
        glow = np.zeros((ROOM_H, ROOM_W), np.float32)
        for (x, ytop, hgt, f, p) in flames(t):
            R = (205 - 35 * clamp01(day_float(t) / 7)) * f * p + 1
            glow += np.exp(-(((XX - x) ** 2 + ((YY - ytop + 20) * 0.9) ** 2) / (R * R)))
        glow = np.clip(glow, 0, 1.15)
        a = dk * (1 - np.clip(glow, 0, 0.82))
        dark = np.array([10, 14, 32], np.float32)
        arr = arr * (1 - a[..., None]) + dark * a[..., None]
        arr += np.array([255, 150, 50], np.float32) * (glow * dk * 0.22)[..., None]
        room = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    room.putalpha(G["round"])
    return room


# ------------------------------------------------------------------ HUD per frame
def fmt_eur(v):
    return f"{int(round(v))} €"


def draw_counter(frame, t, bgdk):
    col = lerp_col(INK, PAPER, clamp01(bgdk / 0.3))
    sub = lerp_col(GREY, (150, 160, 175), clamp01(bgdk / 0.3))
    n = day_num(t)
    if n == 0:
        # hook title
        f1, f2 = font(F_HEAD, 74), font(F_HEAD, 74)
        p1 = ease_back((t - 0.05) / 0.45, 1.6)
        p2 = ease_back((t - at("hook", "was") + 0.05) / 0.45, 1.6)
        if p1 > 0:
            paste_center(frame, text_img("1 WOCHE", f1, col), W / 2, 120, scale=max(0.05, p1))
            paste_center(frame, text_img("OHNE STROM?", f1, TEAL), W / 2, 210, scale=max(0.05, p1))
        if p2 > 0:
            paste_center(frame, text_img("Was kostet dich das?", font(F_HEAD_B, 36), sub), W / 2, 285,
                         alpha=clamp01(p2))
        return
    tn = DAYS[n - 1]
    p = (t - tn) / 0.45
    fT = font(F_HEAD, 168)
    label = f"TAG {n}"
    img = text_img(label, fT, col)
    if p < 1 and n > 1:
        old = text_img(f"TAG {n - 1}", fT, col)
        e = ease_out(p)
        paste_center(frame, old, W / 2, 160 - e * 120, scale=1 - 0.3 * e, alpha=1 - e)
        paste_center(frame, img, W / 2, 160 + (1 - ease_back(p, 1.8)) * 120, scale=0.7 + 0.3 * ease_back(p, 1.8),
                     alpha=clamp01(p * 2))
    else:
        sc = 1 + 0.12 * (1 - ease_out(p * 2)) if n == 1 else 1
        paste_center(frame, img, W / 2, 160, scale=sc if p < 1 else 1)
    # 7 progress dots
    d = ImageDraw.Draw(frame)
    df = day_float(t)
    for i in range(7):
        cx = W / 2 + (i - 3) * 62
        cy = 285
        fill = clamp01(df - i)
        d.rounded_rectangle([cx - 24, cy - 8, cx + 24, cy + 8], radius=8, fill=lerp_col(sub, col, 0.0) + (90,))
        if fill > 0:
            d.rounded_rectangle([cx - 24, cy - 8, cx - 24 + 48 * fill, cy + 8], radius=8, fill=TEAL)


def draw_meters(frame, t):
    p = ease_back((t - at("hook", "kostet")) / 0.5, 1.6)
    if p <= 0:
        return
    sv, sp = saved(t), spent(t)
    fin = t >= at("fazit", "22")
    for k, (base, val, col, sign) in enumerate(((G["m_saved"], sv, GREEN, "+"), (G["m_spent"], sp, RED, "−"))):
        card = base.copy()
        d = ImageDraw.Draw(card)
        txt = (sign if val >= 0.5 else "") + fmt_eur(val)
        d.text((40, 130), txt, font=font(F_HEAD, 88), fill=col, anchor="lm")
        frac = clamp01(val / SPENT_TOTAL)
        if frac > 0.002:
            d.rounded_rectangle([40, 192, 40 + max(14, 400 * frac), 206], radius=7, fill=col)
        # pulse on spend / finale highlight
        pulse = 0.0
        if k == 1:
            for ts, _ in SPENDS:
                pulse = max(pulse, 1 - clamp01((t - ts) / 0.35) if t >= ts else 0)
        if fin:
            tf = at("fazit", "22") if k == 0 else at("fazit", "240")
            if t >= tf:
                pulse = max(pulse, 1 - clamp01((t - tf) / 0.5))
        img = with_shadow(card, dy=10, blur=16, alpha=0.25, pad=30)
        cx = 40 + 240 if k == 0 else 560 + 240
        paste_center(frame, img, cx, 455, scale=max(0.05, p) * (1 + 0.08 * pulse), rot=0)
    # floating "−25 €" chips
    for ts, a in SPENDS:
        u = (t - ts) / 1.1
        if 0 <= u <= 1:
            chip = chip_img(f"−{a} €")
            paste_center(frame, chip, 800, 720 - 80 * ease_out(u), scale=0.6 + 0.4 * ease_back(u * 3, 2),
                         alpha=1 - clamp01((u - 0.7) / 0.3))


@lru_cache(maxsize=16)
def chip_img(text):
    f = font(F_HEAD, 46)
    tw = f.getlength(text)
    w, h = int(tw + 60), 84

    def fn(im, d, ss):
        d.rounded_rectangle([0, 0, w * ss, h * ss], radius=h / 2 * ss, fill=RED)
        d.text((w / 2 * ss, h / 2 * ss), text, font=font(F_HEAD, 46 * ss), fill=PAPER, anchor="mm")
    return with_shadow(supersample(w, h, fn), dy=8, blur=10, alpha=0.3, pad=24)


def draw_stickers(frame, t):
    for i, (ts, ch, x, y) in enumerate(STICKERS):
        if t < ts:
            continue
        # a sticker lives until the next one on the same side replaces it
        nxt = [s[0] for s in STICKERS[i + 1:] if s[2] == x]
        end = (nxt[0] if nxt else T_Q) - 0.05
        if t >= end + 0.2:
            continue
        p = (t - ts) / 0.35
        out = clamp01((t - end) / 0.2)
        sc = (0.2 + 0.8 * ease_back(p, 2.4)) * (1 - out)
        if sc <= 0.02:
            continue
        rot = (12 if x > W / 2 else -12) + math.sin(t * 3.2 + i) * 6
        paste_center(frame, emoji_img(ch, 140), x, y + math.sin(t * 2.4 + i) * 8, scale=sc, rot=rot)


# ------------------------------------------------------------------ captions (Wort für Wort)
def build_caps():
    caps = []
    for si, sc in enumerate(TIM):
        for w in sc["words"]:
            txt = w["text"].replace(" Euro", " €")
            caps.append(dict(text=txt, start=OFF[si] + w["start"], end=OFF[si] + w["end"]))
    for i, c in enumerate(caps):
        nxt = caps[i + 1]["start"] if i + 1 < len(caps) else TOTAL
        c["end"] = min(nxt, c["end"] + 0.35)
    return caps


@lru_cache(maxsize=256)
def cap_img(text, hl):
    f = font(F_CAP, 96)
    im = text_img(text, f, YELLOW if hl else PAPER, stroke=12)
    sh = Image.new("RGBA", (im.width + 40, im.height + 40), (0, 0, 0, 0))
    a = Image.new("L", sh.size, 0)
    a.paste(im.getchannel("A"), (20, 26))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(9)).point(lambda v: int(v * 0.5)))
    sh.alpha_composite(im, (20, 20))
    return sh


HL_WORDS = ("Strom", "kostet", "Licht", "Kühlschrank", "tropft", "Müll", "Herd", "Pizzakartons", "Tiefkühltruhe",
            "€", "Erstes", "vermissen", "gespart", "ausgegeben", "Kerzen")


def draw_caption(frame, t):
    if t >= T_Q - 0.05:
        return
    for c in G["caps"]:
        if c["start"] <= t < c["end"]:
            hl = any(k in c["text"] for k in HL_WORDS)
            img = cap_img(c["text"], hl)
            p = clamp01((t - c["start"]) / 0.12)
            sc = (0.8 + 0.2 * ease_back(p, 2.2)) * min(1.0, 1000 / img.width)
            paste_center(frame, img, W / 2, 1612, scale=sc)
            return


# ------------------------------------------------------------------ frame
def render_frame(fi):
    t = fi / FPS
    dk = darkness(t)
    bgdk = min(1.0, dk * 1.3)
    frame = Image.blend(G["bg"][0], G["bg"][1], bgdk) if bgdk > 0.005 else G["bg"][0].copy()
    d = ImageDraw.Draw(frame)
    # progress bar
    d.rounded_rectangle([40, 26, W - 40, 34], radius=4, fill=(128, 128, 128, 60))
    d.rounded_rectangle([40, 26, 40 + (W - 80) * clamp01(t / TOTAL), 34], radius=4, fill=TEAL)

    # room (with gentle camera push per scene, small shake when money leaves)
    room = draw_room(t)
    si = max(i for i in range(len(OFF)) if OFF[i] <= t + 1e-6)
    life = clamp01((t - OFF[si]) / max(1.0, s1(KEYS[si]) - OFF[si]))
    zoom = 1.0 + 0.035 * ease_io(life)
    shake = 0
    for ts, _ in SPENDS:
        if 0 <= t - ts < 0.25:
            shake = math.sin((t - ts) * 90) * 6 * (1 - (t - ts) / 0.25)
    rs = with_room_frame(room, bgdk)
    paste_center(frame, rs, ROOM_X + ROOM_W / 2 + shake, ROOM_Y + ROOM_H / 2, scale=zoom)

    # fazit stamp
    if t >= T_STAMP:
        q = clamp01((t - T_STAMP) / 0.18)
        paste_center(frame, G["stamp"], W / 2, ROOM_Y + 300, scale=lerp(1.9, 1.0, ease_out(q)), rot=-8,
                     alpha=q * (1 - clamp01((t - T_Q) / 0.3)))
    # final question
    if t >= T_Q:
        p = (t - T_Q) / 0.5
        ov = Image.new("RGBA", (W, ROOM_H + 40), (8, 10, 20, int(150 * clamp01(p * 2))))
        frame.alpha_composite(ov, (0, ROOM_Y - 20))
        paste_center(frame, G["question"], W / 2, ROOM_Y + ROOM_H / 2, scale=max(0.05, 0.3 + 0.7 * ease_back(p, 1.6)),
                     alpha=clamp01(p * 3))

    draw_counter(frame, t, bgdk)
    draw_meters(frame, t)
    draw_stickers(frame, t)
    draw_caption(frame, t)

    # disclaimer + handle
    tcol = lerp_col((110, 118, 126), (170, 178, 190), clamp01(bgdk / 0.6))
    if t >= s0("fazit"):
        a = clamp01((t - s0("fazit")) / 0.4)
        paste_center(frame, text_img("Beispielrechnung, Angaben ohne Gewähr", font(F_BODY_B, 32), tcol),
                     W / 2, 1745, alpha=a)
    paste_center(frame, text_img("@alltagklar", font(F_HEAD_B, 30), tcol), W / 2, 1855, alpha=0.85)
    return frame.convert("RGB").tobytes()


def with_room_frame(room, bgdk):
    out = Image.new("RGBA", (ROOM_W + 16, ROOM_H + 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle([0, 0, ROOM_W + 15, ROOM_H + 15], radius=46,
                        fill=lerp_col((255, 255, 255), (70, 78, 96), clamp01(bgdk / 0.6)))
    out.alpha_composite(room, (8, 8))
    return out


# ------------------------------------------------------------------ sound design (synthesised)
SR = 48000


def _env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)


def sfx_whoosh(rng, dur=0.45):
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    y = 0.0
    for i in range(n):
        u = i / n
        alpha = 0.02 + 0.35 * math.sin(math.pi * u) ** 2
        y += alpha * (noise[i] - y)
        out[i] = y
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.5
    return out * env * 0.9


def sfx_pop():
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    f = 700 + 900 * (t / t[-1])
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.025) * 0.6


def sfx_click(rng):
    n = int(0.06 * SR)
    return rng.standard_normal(n) * _env(n, 0.0003, 0.006) * 0.8


def sfx_kaching(rng):
    """Registrierkasse: Schublade (Rumpeln) + zwei Glockenschläge + Münzklimpern."""
    n = int(1.1 * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    # drawer: low filtered noise burst
    m = int(0.12 * SR)
    nz = rng.standard_normal(m)
    lp = np.convolve(nz, np.ones(18) / 18, mode="same")
    out[:m] += lp * _env(m, 0.002, 0.05) * 1.6
    out[:m] += np.sin(2 * np.pi * 110 * t[:m]) * _env(m, 0.001, 0.04) * 0.5
    # bell strikes
    for st, f0, g in ((0.09, 2093.0, 0.55), (0.2, 2637.0, 0.7)):
        i0 = int(st * SR)
        tt = t[: n - i0]
        bell = sum(a * np.sin(2 * np.pi * f0 * r * tt) * np.exp(-tt / dcy)
                   for r, a, dcy in ((1.0, 1.0, 0.45), (2.76, 0.45, 0.18), (5.4, 0.25, 0.08), (0.5, 0.2, 0.3)))
        out[i0:] += bell * np.minimum(1, tt / 0.002) * g * 0.35
    # coins
    for _ in range(9):
        i0 = int(rng.uniform(0.12, 0.45) * SR)
        k = int(0.03 * SR)
        f = rng.uniform(4000, 7000)
        seg = np.sin(2 * np.pi * f * t[:k]) * _env(k, 0.0003, 0.008) * 0.12
        out[i0:i0 + k] += seg[: n - i0]
    return out


def beat_bed(dur, bpm=100):
    rng = np.random.default_rng(3)
    n = int(dur * SR)
    out = np.zeros(n)
    beat = 60 / bpm
    kick_n = int(0.3 * SR)
    kt = np.arange(kick_n) / SR
    kick = np.sin(2 * np.pi * (48 + 90 * np.exp(-kt * 25)) * kt) * _env(kick_n, 0.001, 0.12)
    hat_n = int(0.04 * SR)
    hat = np.diff(rng.standard_normal(hat_n + 1)) * _env(hat_n, 0.0005, 0.01) * 0.25
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 246.94, 293.66], [164.81, 196.0, 246.94]]
    i, tb = 0, 0.0
    while tb < dur:
        a0 = int(tb * SR)
        bb = i % 4
        if bb in (0, 2):
            seg = kick[: max(0, min(kick_n, n - a0))]
            out[a0:a0 + len(seg)] += seg * 0.8
        h0 = int((tb + beat * 0.5) * SR)
        seg = hat[: max(0, min(hat_n, n - h0))]
        out[h0:h0 + len(seg)] += seg
        if bb == 0:
            ch = chords[(i // 4) % 4]
            L = int(beat * 4 * SR)
            pt = np.arange(min(L, n - a0)) / SR
            pad = sum(np.sin(2 * np.pi * f * pt) + 0.3 * np.sin(4 * np.pi * f * pt) for f in ch)
            pad *= np.minimum(1, pt / 0.4) * np.minimum(1, (L / SR - pt) / 0.4) * 0.05
            out[a0:a0 + len(pad)] += pad
        tb += beat
        i += 1
    fade = np.minimum(1, np.minimum(np.arange(n) / SR / 1.0, (n - np.arange(n)) / SR / 1.5))
    return out * fade


def make_sfx(path):
    rng = np.random.default_rng(11)
    n = int(TOTAL * SR) + SR
    out = np.zeros(n)

    def put(sig, t):
        i = int(max(0, t) * SR)
        sig = sig[: max(0, n - i)]
        out[i:i + len(sig)] += sig

    for k in KEYS[1:]:
        put(sfx_whoosh(rng) * 0.6, s0(k) - 0.15)        # whoosh on every new day / chapter
    put(sfx_whoosh(rng, 0.3) * 0.45, at("tag45", "fünf") - 0.1)
    put(sfx_whoosh(rng, 0.3) * 0.45, at("tag67", "sieben") - 0.1)
    put(sfx_click(rng), T_LIGHT_OFF + 0.08)              # light switch
    for ts, _ in SPENDS:
        put(sfx_kaching(rng) * 0.9, ts)                  # cash register
    put(sfx_kaching(rng) * 0.9, at("fazit", "240"))
    put(sfx_click(rng) * 1.2, T_STAMP + 0.12)
    for ts, *_ in STICKERS:
        put(sfx_pop() * 0.6, ts + 0.08)
    put(sfx_pop() * 0.9, T_Q + 0.1)
    bed = beat_bed(TOTAL)
    mix = np.zeros(n)
    mix[: len(out)] += out * 0.55
    mix[: len(bed)] += bed * 0.2
    mix = np.clip(mix, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32000).astype(np.int16).tobytes())


def main():
    init()
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        (BUILD / "stills").mkdir(exist_ok=True)
        for tt in [float(x) for x in sys.argv[2:]]:
            Image.frombytes("RGB", (W, H), render_frame(int(tt * FPS))).save(BUILD / "stills" / f"t{tt:05.1f}.png")
        return
    out = ROOT / os.environ.get("VIDEO_OUT", "stromausfall-video.mp4")
    audio = BUILD / "voice.wav"
    lst = BUILD / "concat.txt"
    lst.write_text("".join(f"file '{s['audio']}'\n" for s in TIM))
    voice = BUILD / "voice_only.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-af", f"apad=pad_dur={TAIL},loudnorm=I=-16:TP=-2:LRA=11", "-ar", "48000", str(voice)],
                   check=True)
    sfx = BUILD / "sfx.wav"
    make_sfx(sfx)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice), "-i", str(sfx), "-filter_complex",
                    "[1:a]volume=0.6[s];[0:a][s]amix=inputs=2:normalize=0:duration=first,"
                    "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", str(audio)], check=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-t", f"{NFRAMES / FPS:.3f}", "-shortest", str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=init) as pool:
        for i, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=6)):
            ff.stdin.write(buf)
            if i % 300 == 0:
                print(f"frame {i}/{NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", out, f"{NFRAMES / FPS:.2f}s")


if __name__ == "__main__":
    main()
