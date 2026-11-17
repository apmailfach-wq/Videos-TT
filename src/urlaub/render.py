"""Render urlaub-video.mp4 (1080x1920, 30 fps) – „Was passiert mit deinem Körper im Urlaub?“

Gleiche Machart wie stromausfall-video: großer Tageszähler (TAG 1 … TAG 14), zwei Anzeigen
(Erholung grün / Stress rot), eine feste Szene – Strand mit Sonne, Meer, Wellen, Möwen, Liege und
Sonnenschirm – mit Zeitraffer-Nacht zwischen den Tagen, virtueller Kamera (Schnitte, Close-ups, Whip-Pans),
Partikeln (Zzz, Niesen, Funkeln) und am Ende dem harten Schnitt ins Büro. Untertitel Wort für Wort,
Emoji-Sticker, Sounds, Kommentar-Frage + Folgen-Button.

    python3 tts.py && python3 render.py           # -> ../../urlaub-video.mp4
    python3 render.py preview 2 7 12 20            # Standbilder -> build/urlaub/stills/
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
BUILD = ROOT / "build" / "urlaub"
FONTS = ROOT / "fonts"
W, H, FPS = 1080, 1920, 30
TAIL = 1.4

F_HEAD = str(FONTS / "Unbounded_900Black.ttf")
F_HEAD_B = str(FONTS / "Unbounded_700Bold.ttf")
F_BODY_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_CAP = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

INK = (20, 22, 26)
GREY = (139, 147, 155)
TEAL = (24, 168, 152)
TEAL_F = (34, 179, 164)
TEAL_B = (20, 140, 128)
SICK_F = (156, 196, 96)
SICK_B = (124, 160, 70)
GREEN = (30, 168, 88)
RED = (229, 72, 77)
PAPER = (255, 255, 255)
YELLOW = (255, 226, 0)

ROOM_X, ROOM_Y, ROOM_W, ROOM_H = 40, 600, 1000, 900
K, DS = 2, 4
HORIZON = 440
SHORE = 600


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


def keyed(keys, t):
    """piecewise eased interpolation over [(t, v), ...]"""
    if t <= keys[0][0]:
        return keys[0][1]
    for (ta, va), (tb, vb) in zip(keys, keys[1:]):
        if ta <= t < tb:
            return lerp(va, vb, ease_io((t - ta) / max(1e-3, tb - ta)))
    return keys[-1][1]


# ------------------------------------------------------------------ story data
T_OFFICE = at("tag14", "Alltag")
T_Q = s0("cta")
T_WEG = at("fazit", "weg")
T_PEAK = at("tag8", "erholtesten")

# Tageszähler: (Zeit, Tag) – Zeitraffer-Sprünge bei Tag 6–8 und 9–14
DAYMARKS = [(s0("tag1"), 1), (s0("tag2"), 2), (s0("tag35"), 3), (at("tag35", "bis"), 4), (at("tag35", "fünf"), 5)]
DAYMARKS += [(s0("tag8") + i * 0.16, 6 + i) for i in range(3)]
DAYMARKS += [(s0("tag14") + i * 0.11, 9 + i) for i in range(6)]
NIGHTS = [s0(k) for k in ("tag2", "tag35", "tag8", "tag14")]   # time-lapse nights between the days
WHIPS = [s0(k) for k in ("tag1", "tag2", "tag35", "tag8", "tag14")] + [T_OFFICE]

ERHOLUNG = [(0, 10), (s0("tag1"), 12), (s0("tag2"), 16), (at("tag2", "Freizeitkrankheit"), 14), (s0("tag35"), 25),
            (s1("tag35") - 0.3, 64), (s0("tag8") + 0.4, 72), (T_PEAK, 100), (s0("tag14"), 96), (T_OFFICE, 92),
            (at("fazit", "Nach"), 88), (T_WEG + 0.2, 12)]
STRESS = [(0, 90), (s0("tag1"), 88), (at("tag1", "Mails"), 92), (s0("tag2"), 84), (at("tag2", "Kopfweh"), 80),
          (s0("tag35"), 70), (s1("tag35") - 0.3, 30), (T_PEAK, 8), (s0("tag14"), 12), (T_OFFICE, 30),
          (at("fazit", "Haken"), 40), (T_WEG + 0.2, 90)]

STICKERS = [
    (at("hook", "Urlaub"), "🏖️", 905, 700),
    (at("hook", "Tag"), "⏳", 175, 700),
    (at("tag1", "Büro"), "💼", 905, 700),
    (at("tag1", "Mails"), "📧", 175, 700),
    (at("tag1", "Handy"), "📱", 905, 700),
    (at("tag2", "Kopfweh"), "🤕", 175, 700),
    (at("tag2", "Schnupfen"), "🤧", 905, 700),
    (at("tag2", "Freizeitkrankheit"), "🤒", 175, 700),
    (at("tag35", "Stresshormone"), "📉", 905, 700),
    (at("tag35", "schläfst"), "😴", 175, 700),
    (at("tag8", "acht"), "☀️", 905, 700),
    (T_PEAK, "🔋", 175, 700),
    (at("tag14", "Koffer"), "🧳", 905, 700),
    (T_OFFICE, "🏢", 175, 700),
    (at("fazit", "Haken"), "🎣", 905, 700),
    (T_WEG, "💨", 175, 700),
]

HL_WORDS = ("Körper", "Urlaub", "Büro", "Mails", "Kopfweh", "Schnupfen", "Freizeitkrankheit", "Stresshormone",
            "sinken", "erholtesten", "Alltag", "Haken", "weg", "abschaltest", "folg", "Strand", "tiefer")


def warmth(t):
    """0 = midday, 1 = deep sunset (per scene)."""
    return keyed([(0, 0.75), (s0("tag1") - 0.01, 0.75), (s0("tag1"), 0.1), (s0("tag2"), 0.0), (s0("tag35"), 0.35),
                  (s0("tag8"), 0.45), (T_PEAK, 1.0), (s0("tag14"), 0.2)], t)


def night(t):
    v = 0.0
    for tn in NIGHTS:
        d = abs(t - tn)
        if d < 0.45:
            v = max(v, 1 - d / 0.45)
    return ease_io(v)


def sick(t):
    return clamp01(min((t - s0("tag2") + 0.2) / 0.4, (s0("tag35") + 0.6 - t) / 0.6))


def day_num(t):
    n = 0
    for tm, d in DAYMARKS:
        if t >= tm:
            n = d
    return n


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


def text_img(text, f, fill, stroke=0, stroke_fill=(0, 0, 0)):
    l, t, r, b = f.getbbox(text, stroke_width=stroke)
    im = Image.new("RGBA", (r - l + 8, b - t + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - l, 4 - t), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    return im


def radial(size, col, peak, power=2.2):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
    a = np.clip(1 - r, 0, 1) ** power * peak
    arr = np.zeros((size, size, 4), np.uint8)
    arr[..., :3] = col
    arr[..., 3] = a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


# ------------------------------------------------------------------ stick figure
SEG = dict(torso=92, ua=56, fa=54, th=70, sh=68, head=31, limb=25, tw=33)
POSES = {
    "stand":  dict(t=0, uaf=10, faf=14, uab=-10, fab=-6, thf=5, shf=0, thb=-5, shb=0),
    "cower":  dict(t=-12, uaf=70, faf=168, uab=58, fab=172, thf=32, shf=-12, thb=6, shb=-26),
    "walk1":  dict(t=4, uaf=30, faf=45, uab=-30, fab=-15, thf=24, shf=4, thb=-24, shb=-34),
    "walk2":  dict(t=4, uaf=-30, faf=-15, uab=30, fab=45, thf=-24, shf=-34, thb=24, shb=4),
    "handsup": dict(t=-4, uaf=158, faf=172, uab=148, fab=168, thf=5, shf=0, thb=-5, shb=0),
    "cheer":  dict(t=-6, uaf=150, faf=150, uab=-150, fab=-150, thf=14, shf=-10, thb=-14, shb=10),
    "shrug":  dict(t=0, uaf=30, faf=120, uab=-30, fab=-120, thf=5, shf=0, thb=-5, shb=0),
    "facepalm": dict(t=8, uaf=60, faf=175, uab=-12, fab=-8, thf=6, shf=0, thb=-6, shb=0),
    "relax":  dict(t=0, uaf=150, faf=-120, uab=-150, fab=120, thf=5, shf=0, thb=-5, shb=0),
    "lying":  dict(t=-90, uaf=96, faf=92, uab=84, fab=88, thf=92, shf=90, thb=88, shb=90),
    "lie_phone": dict(t=-90, uaf=150, faf=200, uab=84, fab=88, thf=92, shf=90, thb=88, shb=90),
    "lie_relax": dict(t=-90, uaf=-150, faf=-60, uab=-150, fab=-70, thf=80, shf=100, thb=92, shb=90),
    "lie_sneeze": dict(t=-70, uaf=60, faf=150, uab=50, fab=150, thf=92, shf=90, thb=88, shb=90),
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
    """keys: (time, pose, x, facing, ground_y)"""

    def __init__(self, keys, s=1.2, jumps=(), jolts=()):
        self.keys, self.s, self.jumps, self.jolts = sorted(keys, key=lambda k: k[0]), s, jumps, jolts

    def state(self, t):
        ks = self.keys
        if t <= ks[0][0]:
            k = ks[0]
            return POSES[k[1]], k[2], k[3], k[4]
        for a, b in zip(ks, ks[1:]):
            if a[0] <= t < b[0]:
                u = ease_io((t - a[0]) / (b[0] - a[0]))
                return lerp_pose(POSES[a[1]], POSES[b[1]], u), lerp(a[2], b[2], u), b[3] if u > 0.5 else a[3], \
                    lerp(a[4], b[4], u)
        k = ks[-1]
        return POSES[k[1]], k[2], k[3], k[4]

    def offset(self, t):
        dy = 0.0
        for tj in self.jumps:
            u = (t - tj) / 0.5
            if 0 <= u < 1:
                dy -= math.sin(u * math.pi) * 70
        dx = 0.0
        for tj in self.jolts:
            u = (t - tj) / 0.4
            if 0 <= u < 1:
                dx += math.sin(u * 30) * 8 * (1 - u)
        return dx, dy

    def point(self, t, name):
        p, x, facing, gy = self.state(t)
        dx, dy = self.offset(t)
        q = figure_points(p, facing, self.s)[name]
        return x + dx + q[0], gy + dy + q[1]

    def draw(self, d, t, ss):
        p, x, facing, gy = self.state(t)
        dx, dy = self.offset(t)
        sk = sick(t)
        cf, cb = lerp_col(TEAL_F, SICK_F, sk), lerp_col(TEAL_B, SICK_B, sk)
        sw = 70 * self.s * (1 + dy / 300)
        if gy > 780:
            d.ellipse([(x + dx - sw) * ss, (gy - 12 * self.s) * ss, (x + dx + sw) * ss, (gy + 12 * self.s) * ss],
                      fill=(60, 40, 20, 50))
        draw_figure(d, figure_points(p, facing, self.s), x + dx, gy + dy, self.s, cf, cb, ss)


LOUNGE_Y = 712


def walk(t0, t1, x0, x1, gy=805, end="stand", step=0.22):
    facing = 1 if x1 >= x0 else -1
    keys, n = [], max(2, int((t1 - t0) / step))
    for i in range(n + 1):
        u = i / n
        pose = end if i == n else ("walk1" if i % 2 else "walk2")
        keys.append((lerp(t0, t1, u), pose, lerp(x0, x1, u), facing, gy))
    return keys


def build_figure():
    k = [(0.0, "stand", 400, 1, 805), (at("hook", "Körper"), "relax", 400, 1, 805),
         (at("hook", "Urlaub"), "handsup", 400, 1, 805), (at("hook", "Tag"), "relax", 400, 1, 805)]
    a = s0("tag1")
    k += [(a - 0.01, "relax", 400, 1, 805), (a, "lie_phone", 735, 1, LOUNGE_Y),
          (at("tag1", "Büro"), "lie_phone", 735, 1, LOUNGE_Y), (at("tag1", "Mails"), "lie_phone", 735, 1, LOUNGE_Y)]
    a = s0("tag2")
    k += [(a, "lying", 735, 1, LOUNGE_Y), (at("tag2", "Schnupfen") - 0.1, "lying", 735, 1, LOUNGE_Y),
          (at("tag2", "Schnupfen"), "lie_sneeze", 735, 1, LOUNGE_Y),
          (at("tag2", "Schnupfen") + 0.45, "lying", 735, 1, LOUNGE_Y)]
    a = s0("tag35")
    k += [(a, "lie_relax", 735, 1, LOUNGE_Y), (s1("tag35"), "lie_relax", 735, 1, LOUNGE_Y)]
    a = s0("tag8")
    k += [(a, "stand", 380, 1, 805), (at("tag8", "Laut"), "cheer", 380, 1, 805),
          (at("tag8", "jetzt"), "handsup", 380, 1, 805), (T_PEAK + 0.4, "cheer", 380, 1, 805)]
    a = s0("tag14")
    k += [(a, "stand", 470, 1, 805), (at("tag14", "Koffer"), "shrug", 470, 1, 805)]
    k += walk(at("tag14", "Zurück") - 0.1, T_OFFICE - 0.02, 470, 560)
    k += [(T_OFFICE, "stand", 500, 1, 805), (at("fazit", "Haken"), "facepalm", 500, 1, 805),
          (at("fazit", "Wochen"), "stand", 500, 1, 805), (T_WEG, "cower", 500, 1, 805),
          (T_Q, "shrug", 500, 1, 805)]
    jumps = [at("tag8", "Studien"), T_PEAK]
    jolts = [at("tag2", "Schnupfen") + 0.15, T_WEG]
    return Fig(k, jumps=jumps, jolts=jolts)


# ------------------------------------------------------------------ camera
SHOTS = [
    (0.0, 760, 300, 1.45, -2, "cut"),
    (at("hook", "Körper"), 420, 560, 1.7, 2, "cut"),
    (at("hook", "Urlaub"), 500, 450, 1.0, 0, "ease"),
    (s0("tag1"), 700, 610, 1.6, 2, "cut"),
    (at("tag1", "Büro"), 640, 560, 1.95, -2, "ease"),
    (at("tag1", "Mails"), 520, 470, 1.1, 0, "cut"),
    (s0("tag2"), 690, 630, 1.8, -2, "cut"),
    (at("tag2", "Schnupfen"), 650, 600, 1.5, 3, "cut"),
    (at("tag2", "Freizeitkrankheit"), 520, 470, 1.1, 0, "ease"),
    (s0("tag35"), 500, 450, 1.0, 0, "cut"),
    (at("tag35", "Stresshormone"), 680, 620, 1.5, -2, "ease"),
    (at("tag35", "schläfst"), 640, 610, 1.95, 1, "ease"),
    (s0("tag8"), 740, 330, 1.4, -2, "cut"),
    (at("tag8", "Studien"), 400, 560, 1.6, 2, "cut"),
    (T_PEAK, 470, 470, 1.08, 0, "ease"),
    (s0("tag14"), 540, 610, 1.6, -2, "cut"),
    (T_OFFICE, 500, 450, 1.0, 0, "cut"),
    (at("fazit", "Haken"), 510, 480, 1.55, 2, "ease"),
    (at("fazit", "Wochen"), 500, 450, 1.05, 0, "ease"),
    (T_WEG, 510, 470, 1.7, -3, "cut"),
    (T_Q, 500, 450, 1.0, 0, "ease"),
]


def camera(t):
    i = max(j for j in range(len(SHOTS)) if SHOTS[j][0] <= t + 1e-6)
    t0, cx, cy, z, r, mode = SHOTS[i]
    if mode == "ease" and i > 0:
        _, pcx, pcy, pz, pr, _ = SHOTS[i - 1]
        u = ease_io((t - t0) / 0.45)
        cx, cy, z, r = lerp(pcx, cx, u), lerp(pcy, cy, u), lerp(pz, z, u), lerp(pr, r, u)
    z *= 1 + 0.05 * ease_io(clamp01((t - t0) / 4))
    cx += 4 * math.sin(t * 1.3) + 2 * math.sin(t * 2.9)
    cy += 3 * math.sin(t * 1.7 + 1)
    r += 0.4 * math.sin(t * 0.9)
    shake = 0.0
    for ts, amp in ((T_WEG, 14), (T_OFFICE, 8), (T_PEAK, 6), (at("tag2", "Schnupfen") + 0.15, 7)):
        if 0 <= t - ts < 0.5:
            shake = max(shake, amp * (1 - (t - ts) / 0.5))
    cx += math.sin(t * 87) * shake
    cy += math.cos(t * 71) * shake
    return cx, cy, z, r


def whip(t):
    return max([1 - abs(t - ts) / 0.14 for ts in WHIPS if abs(t - ts) < 0.14] or [0])


# ------------------------------------------------------------------ scene sprites
SAND = (238, 214, 168)
SAND_D = (222, 192, 140)


def beach_base(sunset):
    w, h = ROOM_W, ROOM_H

    def fn(im, d, S):
        top = (255, 140, 90) if sunset else (90, 170, 235)
        mid = (255, 196, 120) if sunset else (170, 215, 245)
        hor = (255, 222, 160) if sunset else (220, 238, 250)
        for y in range(0, HORIZON, 3):
            u = y / HORIZON
            c = lerp_col(top, mid, u / 0.6) if u < 0.6 else lerp_col(mid, hor, (u - 0.6) / 0.4)
            if sunset:
                c = lerp_col((120, 70, 140), c, clamp01(u * 2.2))
            d.rectangle([0, y * S, w * S, (y + 3) * S], fill=c)
        # clouds
        cl = Image.new("RGBA", im.size, (0, 0, 0, 0))
        cd = ImageDraw.Draw(cl)
        ccol = (255, 170, 150, 170) if sunset else (255, 255, 255, 200)
        for cx, cy, rw in ((160, 90, 120), (240, 110, 90), (520, 60, 140), (600, 80, 90), (900, 150, 110)):
            cd.ellipse([(cx - rw) * S, (cy - rw * 0.32) * S, (cx + rw) * S, (cy + rw * 0.32) * S], fill=ccol)
        im.alpha_composite(cl.filter(ImageFilter.GaussianBlur(6 * S)))
        # far island
        d.polygon([(40 * S, HORIZON * S), (150 * S, (HORIZON - 34) * S), (230 * S, (HORIZON - 20) * S),
                   (300 * S, HORIZON * S)], fill=(150, 110, 140) if sunset else (120, 160, 170))
        # sea
        seat, seab = ((220, 120, 120), (40, 110, 150)) if sunset else ((60, 150, 200), (30, 170, 180))
        for y in range(HORIZON, SHORE, 2):
            u = (y - HORIZON) / (SHORE - HORIZON)
            d.rectangle([0, y * S, w * S, (y + 2) * S], fill=lerp_col(seat, seab, u ** 0.7))
        # sand
        for y in range(SHORE, h, 3):
            u = (y - SHORE) / (h - SHORE)
            c = lerp_col(SAND_D, SAND, ease_out(u * 1.5))
            if sunset:
                c = lerp_col(c, (240, 180, 130), 0.35)
            d.rectangle([0, y * S, w * S, (y + 3) * S], fill=c)
        rng = np.random.default_rng(3)
        for _ in range(500):
            x, y = rng.uniform(0, w), rng.uniform(SHORE + 20, h)
            d.ellipse([x * S, y * S, (x + 2.5) * S, (y + 2.5) * S], fill=(200, 170, 120))
        # contact shadows
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        for x0, x1, y in ((560, 900, 760), (620, 780, 772), (110, 260, 790), (840, 920, 760)):
            sd.ellipse([x0 * S, (y - 12) * S, x1 * S, (y + 14) * S], fill=(90, 60, 20, 90))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8 * S)))
        # palm tree
        pts = [(160 + 30 * math.sin(i / 12 * 1.6) * (i / 12), 790 - i * 42) for i in range(13)]
        for i, (x, y) in enumerate(pts):
            r = 24 - i
            d.ellipse([(x - r) * S, (y - 16) * S, (x + r) * S, (y + 22) * S], fill=(150, 104, 60) if i % 2 else (128, 88, 50))
        tx, ty = pts[-1]
        leaf = (40, 140, 70) if not sunset else (50, 90, 60)
        for ang in (-160, -120, -60, -20, 20, 200):
            a = math.radians(ang)
            L = 190
            ex, ey = tx + math.cos(a) * L, ty + math.sin(a) * L * 0.5 + 60
            mx, my = tx + math.cos(a) * L * 0.5, ty + math.sin(a) * L * 0.5 - 30
            d.line([(tx * S, ty * S), (mx * S, my * S), (ex * S, ey * S)], fill=leaf, width=26 * S, joint="curve")
            for k in range(1, 8):
                u = k / 8
                px, py = lerp(lerp(tx, mx, u), lerp(mx, ex, u), u), lerp(lerp(ty, my, u), lerp(my, ey, u), u)
                d.polygon([(px * S, py * S), ((px - 14) * S, (py + 34) * S), ((px + 14) * S, (py + 30) * S)], fill=leaf)
        for cx in (-12, 12):
            d.ellipse([(tx + cx - 12) * S, (ty + 4) * S, (tx + cx + 12) * S, (ty + 28) * S], fill=(110, 76, 40))
        # umbrella
        d.line([(720 * S, 450 * S), (705 * S, 770 * S)], fill=(240, 240, 236), width=8 * S)
        for i in range(8):
            a0, a1 = 180 + i * 22.5, 180 + (i + 1) * 22.5
            d.pieslice([570 * S, 380 * S, 870 * S, 530 * S], a0, a1, fill=(232, 74, 72) if i % 2 else (250, 246, 240))
        d.ellipse([712 * S, 446 * S, 728 * S, 462 * S], fill=(240, 240, 236))
        # lounger
        d.polygon([(560 * S, 700 * S), (600 * S, 640 * S), (620 * S, 648 * S), (585 * S, 712 * S)], fill=(40, 150, 160))
        d.rounded_rectangle([580 * S, 708 * S, 900 * S, 726 * S], radius=6 * S, fill=(40, 150, 160))
        for x in range(600, 900, 26):
            d.line([(x * S, 711 * S), (x * S, 723 * S)], fill=(250, 250, 250), width=3 * S)
        for lx in (600, 880):
            d.line([(lx * S, 724 * S), ((lx - 10) * S, 768 * S)], fill=(200, 200, 200), width=6 * S)
            d.line([(lx * S, 724 * S), ((lx + 10) * S, 768 * S)], fill=(200, 200, 200), width=6 * S)
        # side table
        d.rounded_rectangle([905 * S, 690 * S, 975 * S, 702 * S], radius=4 * S, fill=(150, 110, 70))
        d.line([(940 * S, 700 * S), (940 * S, 765 * S)], fill=(130, 94, 60), width=6 * S)
        # towel
        d.polygon([(260 * S, 840 * S), (440 * S, 830 * S), (470 * S, 880 * S), (280 * S, 892 * S)], fill=(250, 200, 60))
        for k in range(3):
            d.line([((290 + k * 50) * S, 838 * S), ((310 + k * 50) * S, 888 * S)], fill=(240, 120, 60), width=8 * S)
    return supersample(w * K, h * K, lambda im, d, ss: fn(im, d, ss * K))


def office_base():
    w, h = ROOM_W, ROOM_H

    def fn(im, d, S):
        for y in range(0, 660, 3):
            d.rectangle([0, y * S, w * S, (y + 3) * S], fill=lerp_col((150, 160, 174), (196, 204, 214), y / 660))
        for y in range(660, h, 3):
            d.rectangle([0, y * S, w * S, (y + 3) * S], fill=lerp_col((96, 102, 114), (126, 132, 144), (y - 660) / 240))
        d.rectangle([0, 650 * S, w * S, 664 * S], fill=(226, 230, 234))
        # rainy window
        d.rectangle([620 * S, 110 * S, 900 * S, 400 * S], fill=(120, 132, 146))
        for bx, bw, bh in ((620, 80, 200), (700, 90, 240), (790, 110, 170)):
            d.rectangle([bx * S, (400 - bh) * S, (bx + bw) * S, 400 * S], fill=(92, 100, 114))
        d.rectangle([620 * S, 110 * S, 900 * S, 400 * S], outline=(236, 238, 240), width=14 * S)
        d.line([(760 * S, 110 * S), (760 * S, 400 * S)], fill=(236, 238, 240), width=10 * S)
        # fluorescent tubes
        for x0 in (140, 420):
            d.rounded_rectangle([x0 * S, 18 * S, (x0 + 240) * S, 34 * S], radius=8 * S, fill=(238, 246, 255))
        # clock
        d.ellipse([360 * S, 120 * S, 470 * S, 230 * S], fill=PAPER, outline=INK, width=6 * S)
        d.line([(415 * S, 175 * S), (415 * S, 138 * S)], fill=INK, width=6 * S)
        d.line([(415 * S, 175 * S), (445 * S, 185 * S)], fill=INK, width=5 * S)
        # filing cabinet + wilted plant
        d.rounded_rectangle([50 * S, 380 * S, 210 * S, 690 * S], radius=8 * S, fill=(112, 120, 132))
        for y in (460, 540, 620):
            d.line([(60 * S, y * S), (200 * S, y * S)], fill=(90, 96, 108), width=4 * S)
            d.rounded_rectangle([110 * S, (y - 40) * S, 150 * S, (y - 30) * S], radius=3 * S, fill=(180, 186, 196))
        d.polygon([(100 * S, 380 * S), (160 * S, 380 * S), (150 * S, 330 * S), (110 * S, 330 * S)], fill=(150, 90, 60))
        d.line([(130 * S, 330 * S), (120 * S, 280 * S), (90 * S, 300 * S)], fill=(120, 110, 60), width=5 * S)
        d.line([(130 * S, 330 * S), (150 * S, 270 * S), (175 * S, 295 * S)], fill=(120, 110, 60), width=5 * S)
        # sticky notes
        for i, (x, y, c) in enumerate(((250, 300, (255, 230, 90)), (300, 330, (255, 160, 160)), (262, 370, (160, 220, 255)))):
            d.rectangle([x * S, y * S, (x + 44) * S, (y + 44) * S], fill=c)
    return supersample(w * K, h * K, lambda im, d, ss: fn(im, d, ss * K))


def suitcase_img():
    w, h = 120, 150

    def fn(im, d, ss):
        S = ss * K
        d.rounded_rectangle([40 * S, 0, 80 * S, 30 * S], radius=8 * S, outline=(60, 60, 70), width=7 * S)
        d.rounded_rectangle([0, 24 * S, w * S, (h - 10) * S], radius=16 * S, fill=(232, 90, 70))
        for x in (30, 60, 90):
            d.line([(x * S, 34 * S), (x * S, (h - 20) * S)], fill=(200, 64, 50), width=5 * S)
        d.rectangle([10 * S, 70 * S, 50 * S, 96 * S], fill=(250, 220, 90))
        for x in (16, 104):
            d.ellipse([(x - 8) * S, (h - 16) * S, (x + 8) * S, h * S], fill=(40, 40, 46))
    return supersample(w * K, h * K, fn)


def make_bg(cold):
    y = np.linspace(0, 1, H)[:, None]
    if not cold:
        top, bot = np.array([255, 251, 244], np.float32), np.array([244, 228, 204], np.float32)
    else:
        top, bot = np.array([236, 240, 244], np.float32), np.array([196, 204, 214], np.float32)
    g = top + (bot - top) * y[..., None]
    return Image.fromarray(np.repeat(g, W, axis=1).clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")


def vignette():
    yy, xx = np.mgrid[0:ROOM_H, 0:ROOM_W].astype(np.float32)
    r = np.sqrt(((xx - ROOM_W / 2) / (ROOM_W * 0.62)) ** 2 + ((yy - ROOM_H / 2) / (ROOM_H * 0.62)) ** 2)
    a = np.clip((r - 0.55) / 0.6, 0, 1) ** 1.5 * 130
    arr = np.zeros((ROOM_H, ROOM_W, 4), np.uint8)
    arr[..., 3] = a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


# ------------------------------------------------------------------ HUD sprites
def meter_card(label, col, emoji):
    w, h = 480, 230

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=30 * S, fill=PAPER)
        d.rounded_rectangle([0, 0, 16 * S, h * S], radius=8 * S, fill=col)
        d.text((96 * S, 54 * S), label, font=font(F_HEAD_B, 27 * S), fill=col, anchor="lm")
        d.rounded_rectangle([40 * S, 192 * S, (w - 40) * S, 206 * S], radius=7 * S, fill=(230, 233, 236))
    im = supersample(w, h, fn)
    e = emoji_img(emoji, 50, shadow=False)
    im.alpha_composite(e, (34, 54 - e.height // 2))
    return im


def question_card():
    w = 940
    f = font(F_HEAD, 58)
    words = [(tok.strip("*").upper(), tok.startswith("*")) for tok in QUESTION.split()]
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
        d.text((w / 2 * S, (h - 52) * S), "Schreib deine Zahl in die Kommentare",
               font=font(F_BODY_B, 34 * S), fill=(90, 96, 104), anchor="mm")
    return with_shadow(supersample(w, h, fn), dy=16, blur=24, alpha=0.35)


def follow_pill():
    w, h = 470, 104

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=h / 2 * S, fill=(254, 44, 85))
        d.text((w / 2 * S, h / 2 * S), "+ FOLGEN", font=font(F_HEAD, 42 * S), fill=PAPER, anchor="mm")
    im = supersample(w, h, fn)
    out = with_shadow(im, dy=10, blur=14, alpha=0.35, pad=30)
    t2 = text_img("@alltagklar · mehr Was-wäre-wenn", font(F_BODY_B, 30), (235, 238, 242))
    full = Image.new("RGBA", (max(out.width, t2.width), out.height + t2.height + 6), (0, 0, 0, 0))
    full.alpha_composite(out, ((full.width - out.width) // 2, 0))
    full.alpha_composite(t2, ((full.width - t2.width) // 2, out.height - 14))
    return full


@lru_cache(maxsize=16)
def chip_img(text, col):
    f = font(F_HEAD, 46)
    tw = f.getlength(text)
    w, h = int(tw + 60), 84

    def fn(im, d, ss):
        d.rounded_rectangle([0, 0, w * ss, h * ss], radius=h / 2 * ss, fill=col)
        d.text((w / 2 * ss, h / 2 * ss), text, font=font(F_HEAD, 46 * ss), fill=PAPER, anchor="mm")
    return with_shadow(supersample(w, h, fn), dy=8, blur=10, alpha=0.3, pad=24)


# ------------------------------------------------------------------ init
G = {}


def init():
    rng = np.random.default_rng(5)
    G["day"], G["sunset"], G["office"] = beach_base(False), beach_base(True), office_base()
    G["fig"] = build_figure()
    G["suitcase"] = suitcase_img()
    G["drink"] = emoji_img("🍹", 70 * K, shadow=False)
    G["m_rest"] = meter_card("ERHOLUNG", GREEN, "😌")
    G["m_stress"] = meter_card("STRESS", RED, "😫")
    G["question"] = question_card()
    G["follow"] = follow_pill()
    G["bg"] = (make_bg(False), make_bg(True))
    G["vig"] = vignette()
    m = Image.new("L", (ROOM_W * 2, ROOM_H * 2), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, ROOM_W * 2, ROOM_H * 2], radius=80, fill=255)
    G["round"] = m.resize((ROOM_W, ROOM_H), Image.LANCZOS)
    G["sunglow"] = radial(520 * K, (255, 220, 150), 170, 1.6)
    G["aura"] = radial(420 * K, (255, 236, 150), 150, 1.8)
    G["screen"] = radial(360 * K, (150, 200, 255), 90, 1.8)
    G["stars"] = [(rng.uniform(0, 1000), rng.uniform(0, 420), rng.uniform(1, 3)) for _ in range(90)]
    G["sparkle"] = [(rng.uniform(-170, 170), rng.uniform(-330, 10), rng.uniform(0, 6.28)) for _ in range(18)]
    G["drops"] = [(rng.uniform(-1, 1), rng.uniform(-0.6, 0.6), rng.uniform(0.6, 1.0)) for _ in range(16)]
    G["rain"] = [(rng.uniform(628, 892), rng.uniform(0, 1), rng.uniform(0.7, 1.3)) for _ in range(40)]
    G["caps"] = build_caps()
    G["grain"] = [rng.integers(-3, 4, (H, W, 1), dtype=np.int16) for _ in range(6)]


# ------------------------------------------------------------------ scene per frame
def draw_scene(t):
    office = t >= T_OFFICE
    fig = G["fig"]
    if office:
        room = G["office"].copy()
    else:
        wm = warmth(t)
        room = Image.blend(G["day"], G["sunset"], wm) if 0.01 < wm < 0.99 else \
            (G["day"] if wm <= 0.01 else G["sunset"]).copy()
        # sun + glow (behind the horizon line)
        sx, sy = 770, lerp(130, HORIZON + 10, wm ** 1.3)
        sky = Image.new("RGBA", (ROOM_W * K, HORIZON * K), (0, 0, 0, 0))
        paste_center(sky, G["sunglow"], sx * K, sy * K, scale=0.8 + 0.4 * wm)
        sd = ImageDraw.Draw(sky)
        r = 46 + 10 * wm
        sd.ellipse([(sx - r) * K, (sy - r) * K, (sx + r) * K, (sy + r) * K],
                   fill=lerp_col((255, 250, 220), (255, 150, 70), wm))
        room.alpha_composite(sky)
        if t >= s0("tag35"):
            p = ease_back((t - s0("tag35")) / 0.4, 2)
            if p > 0 and t < s0("tag8"):
                paste_center(room, G["drink"], 945 * K, 660 * K, scale=max(0.05, p))
        if s0("tag14") <= t:
            p = ease_back((t - at("tag14", "Koffer")) / 0.4, 2)
            if p > 0:
                paste_center(room, G["suitcase"], 600 * K, 730 * K, scale=max(0.05, p))

    S = DS
    fl = Image.new("RGBA", (ROOM_W * S, ROOM_H * S), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fl)
    if not office:
        wm = warmth(t)
        # sun reflection + waves
        sx = 770
        for k in range(14):
            y = HORIZON + 8 + k * 11
            wdt = 18 + k * 5 + 8 * math.sin(t * 3 + k)
            fd.line([((sx - wdt) * S, y * S), ((sx + wdt) * S, y * S)],
                    fill=lerp_col((255, 255, 240), (255, 200, 120), wm) + (int(170 - k * 9),), width=3 * S)
        for i in range(6):
            y0 = HORIZON + 20 + i * 26
            pts = [(x * S, (y0 + math.sin(x * 0.02 + t * 1.8 + i * 1.3) * (2 + i)) * S) for x in range(0, 1001, 25)]
            fd.line(pts, fill=(255, 255, 255, 60 + i * 12), width=(2 + i // 2) * S)
        # shoreline wash + foam
        wash = 10 * math.sin(t * 1.1) + 6
        pts = [(x * S, (SHORE + wash + 6 * math.sin(x * 0.015 + t * 1.6)) * S) for x in range(0, 1001, 20)]
        fd.polygon(pts + [(1000 * S, (SHORE - 4) * S), (0, (SHORE - 4) * S)], fill=(80, 190, 200, 200))
        fd.line(pts, fill=(255, 255, 255, 230), width=6 * S)
        # seagulls
        for k in range(3):
            gx = (t * (55 + k * 12) + k * 380) % 1300 - 150
            gy = 110 + k * 50 + math.sin(t * 2 + k) * 12
            flap = math.sin(t * 9 + k * 2) * 10
            sc = 1 - k * 0.2
            fd.line([((gx - 22 * sc) * S, (gy - flap * sc) * S), (gx * S, gy * S), ((gx + 22 * sc) * S, (gy - flap * sc) * S)],
                    fill=(50, 50, 60), width=int(4 * S * sc), joint="curve")
    else:
        for (rx, ry, sp) in G["rain"]:
            y = 117 + ((ry + t * 1.4 * sp) % 1.0) * 276
            if abs(rx - 760) < 7:
                continue
            fd.line([(rx * S, y * S), ((rx - 3) * S, (y + 16) * S)], fill=(210, 220, 235, 150), width=2 * S)

    fig.draw(fd, t, S)

    # phone in hand (day 1)
    if s0("tag1") <= t < s0("tag2"):
        hx, hy = fig.point(t, "hf")
        fd.rounded_rectangle([(hx - 10) * S, (hy - 18) * S, (hx + 10) * S, (hy + 18) * S], radius=3 * S, fill=(20, 22, 28))
        fd.rounded_rectangle([(hx - 8) * S, (hy - 15) * S, (hx + 8) * S, (hy + 14) * S], radius=2 * S, fill=(170, 210, 255))
    # sneeze droplets
    ts = at("tag2", "Schnupfen") + 0.1
    if 0 <= t - ts < 0.8:
        hx, hy = fig.point(t, "head")
        u = (t - ts) / 0.8
        for dx, dy, sp in G["drops"]:
            px, py = hx - 40 - (dx + 1.2) * 160 * sp * ease_out(u), hy + dy * 90 * ease_out(u) + 60 * u * u
            r = 4 * (1 - u) + 1
            fd.ellipse([(px - r) * S, (py - r) * S, (px + r) * S, (py + r) * S], fill=(170, 220, 255, int(230 * (1 - u))))
    # Zzz while sleeping
    if s0("tag35") + 0.3 <= t < s0("tag8"):
        hx, hy = fig.point(t, "head")
        for k in range(3):
            u = ((t - s0("tag35")) * 0.7 + k / 3) % 1.0
            sz = int((22 + 26 * u) * S)
            fd.text(((hx + 20 + 60 * u + 10 * math.sin(u * 6)) * S, (hy - 40 - 140 * u) * S), "Z",
                    font=font(F_HEAD, sz), fill=(255, 255, 255, int(255 * (1 - u) ** 0.7)), anchor="mm",
                    stroke_width=max(1, sz // 10), stroke_fill=(60, 90, 140, int(200 * (1 - u))))
    # recovery sparkles (day 8)
    if s0("tag8") + 0.3 <= t < s0("tag14"):
        hx, hy = fig.point(t, "hip")
        for ox, oy, ph in G["sparkle"]:
            tw = (math.sin(t * 6 + ph) + 1) / 2
            r = 4 + 12 * tw
            cx, cy = hx + ox, hy + oy
            c = (255, 250, 200, int(120 + 135 * tw))
            fd.polygon([(cx * S, (cy - r) * S), ((cx + r * 0.25) * S, (cy - r * 0.25) * S), ((cx + r) * S, cy * S),
                        ((cx + r * 0.25) * S, (cy + r * 0.25) * S), (cx * S, (cy + r) * S),
                        ((cx - r * 0.25) * S, (cy + r * 0.25) * S), ((cx - r) * S, cy * S),
                        ((cx - r * 0.25) * S, (cy - r * 0.25) * S)], fill=c)
    # office desk in front of the figure + glowing monitor + paper pile
    if office:
        fd.rounded_rectangle([270 * S, 630 * S, 760 * S, 652 * S], radius=6 * S, fill=(150, 156, 166))
        fd.rectangle([290 * S, 650 * S, 740 * S, 800 * S], fill=(128, 134, 146))
        fd.rectangle([290 * S, 650 * S, 740 * S, 662 * S], fill=(110, 116, 128))
        fd.rounded_rectangle([560 * S, 470 * S, 740 * S, 590 * S], radius=8 * S, fill=(30, 32, 40))
        fd.rounded_rectangle([570 * S, 480 * S, 730 * S, 580 * S], radius=4 * S, fill=(200, 225, 255))
        n_mail = int(clamp01((t - T_OFFICE) / 3.5) * 9)
        for k in range(n_mail):
            fd.rectangle([(584) * S, (490 + k * 10) * S, (716 - (k * 23) % 50) * S, (496 + k * 10) * S], fill=(120, 150, 200))
        fd.rectangle([640 * S, 590 * S, 660 * S, 630 * S], fill=(30, 32, 40))
        n = int(clamp01((t - T_OFFICE) / 4.5) * 9)
        for k in range(n):
            ox = ((k * 7) % 5 - 2) * 3
            fd.rectangle([(320 + ox) * S, (624 - k * 11) * S, (440 + ox) * S, (632 - k * 11) * S], fill=(248, 248, 244),
                         outline=(200, 200, 196), width=S)
    room.alpha_composite(fl.reduce(DS // K))

    if not office:
        if s0("tag8") + 0.3 <= t < s0("tag14"):
            hx, hy = fig.point(t, "hip")
            paste_center(room, G["aura"], hx * K, (hy - 120) * K, scale=0.9 + 0.1 * math.sin(t * 4),
                         alpha=clamp01((t - s0("tag8") - 0.3) / 0.5))
    else:
        paste_center(room, G["screen"], 650 * K, 530 * K, alpha=0.9)
        cold = Image.new("RGBA", room.size, (120, 150, 200, 255))
        room = Image.blend(room, cold, 0.12)
    # time-lapse night between the days
    nv = night(t)
    if nv > 0.01 and not office:
        dark = Image.new("RGBA", room.size, (10, 16, 46, 255))
        room = Image.blend(room, dark, nv * 0.82)
        d = ImageDraw.Draw(room)
        a = int(255 * clamp01((nv - 0.25) / 0.5))
        if a > 0:
            for x, y, r in G["stars"]:
                d.ellipse([x * K, y * K, (x + r) * K, (y + r) * K], fill=(255, 255, 240, a))
            mx, my = 250, 120
            d.ellipse([(mx - 34) * K, (my - 34) * K, (mx + 34) * K, (my + 34) * K], fill=(250, 246, 220, a))
            d.ellipse([(mx - 18) * K, (my - 40) * K, (mx + 46) * K, (my + 26) * K], fill=(30, 36, 70, a))
    return room


def shoot(room, t):
    cx, cy, z, r = camera(t)
    cw, ch = ROOM_W / z, ROOM_H / z
    pad = 1 + abs(math.sin(math.radians(r))) * 1.2
    cw2, ch2 = min(ROOM_W, cw * pad), min(ROOM_H, ch * pad)
    cx = min(max(cx, cw2 / 2), ROOM_W - cw2 / 2)
    cy = min(max(cy, ch2 / 2), ROOM_H - ch2 / 2)
    box = [int((cx - cw2 / 2) * K), int((cy - ch2 / 2) * K), int((cx + cw2 / 2) * K), int((cy + ch2 / 2) * K)]
    img = room.resize((int(ROOM_W * cw2 / cw), int(ROOM_H * ch2 / ch)), Image.LANCZOS, box=box)
    if abs(r) > 0.05:
        img = img.rotate(r, resample=Image.BICUBIC)
    l, tp = (img.width - ROOM_W) // 2, (img.height - ROOM_H) // 2
    img = img.crop((l, tp, l + ROOM_W, tp + ROOM_H))
    wv = whip(t)
    if wv > 0.02:
        arr = np.asarray(img, np.float32)
        acc = np.zeros_like(arr)
        offs = [int(o * 90 * wv) for o in (-1, -0.5, 0, 0.5, 1)]
        for o in offs:
            acc += np.roll(arr, o, axis=1)
        img = Image.fromarray((acc / len(offs)).astype(np.uint8), "RGBA")
    img.alpha_composite(G["vig"])
    img.putalpha(G["round"])
    out = Image.new("RGBA", (ROOM_W + 16, ROOM_H + 16), (0, 0, 0, 0))
    ImageDraw.Draw(out).rounded_rectangle([0, 0, ROOM_W + 15, ROOM_H + 15], radius=46, fill=PAPER)
    out.alpha_composite(img, (8, 8))
    return out


# ------------------------------------------------------------------ HUD per frame
def draw_counter(frame, t):
    n = day_num(t)
    if t >= T_OFFICE:
        p = ease_back((t - T_OFFICE) / 0.45, 1.6)
        paste_center(frame, text_img("ZURÜCK IM BÜRO", font(F_HEAD, 84), INK), W / 2, 150, scale=max(0.05, p))
        paste_center(frame, text_img("Montag, 8:00 Uhr", font(F_HEAD_B, 36), GREY), W / 2, 255, alpha=clamp01(p))
        return
    if n == 0:
        p1 = ease_back((t - 0.05) / 0.45, 1.6)
        p2 = ease_back((t - at("hook", "Urlaub")) / 0.45, 1.6)
        if p1 > 0:
            paste_center(frame, text_img("2 WOCHEN URLAUB", font(F_HEAD, 74), INK), W / 2, 125, scale=max(0.05, p1))
            paste_center(frame, text_img("WAS PASSIERT IN DIR?", font(F_HEAD, 60), TEAL), W / 2, 215, scale=max(0.05, p1))
        if p2 > 0:
            paste_center(frame, text_img("Tag für Tag erklärt", font(F_HEAD_B, 34), GREY), W / 2, 290, alpha=clamp01(p2))
        return
    tn = max(tm for tm, d in DAYMARKS if d == n)
    p = (t - tn) / 0.3
    fT = font(F_HEAD, 168)
    img = text_img(f"TAG {n}", fT, INK)
    if p < 1 and n > 1:
        old = text_img(f"TAG {n - 1}", fT, INK)
        e = ease_out(p)
        paste_center(frame, old, W / 2, 160 - e * 120, scale=1 - 0.3 * e, alpha=1 - e)
        paste_center(frame, img, W / 2, 160 + (1 - ease_back(p, 1.8)) * 120, scale=0.7 + 0.3 * ease_back(p, 1.8),
                     alpha=clamp01(p * 2))
    else:
        sc = 1 + 0.12 * (1 - ease_out(p * 2)) if (n == 1 and p < 1) else 1
        paste_center(frame, img, W / 2, 160, scale=sc)
    d = ImageDraw.Draw(frame)
    for i in range(14):
        cx = W / 2 + (i - 6.5) * 54
        col = TEAL if i < n else (210, 204, 192)
        if i == 7:
            col = (255, 170, 40) if i < n else (240, 214, 170)
        d.rounded_rectangle([cx - 21, 278, cx + 21, 292], radius=7, fill=col)


def draw_meters(frame, t):
    p = ease_back((t - at("hook", "Körper")) / 0.5, 1.6)
    if p <= 0:
        return
    rest, stress = keyed(ERHOLUNG, t), keyed(STRESS, t)
    for k, (base, val, col, cx) in enumerate(((G["m_rest"], rest, GREEN, 280), (G["m_stress"], stress, RED, 800))):
        card = base.copy()
        d = ImageDraw.Draw(card)
        d.text((40, 130), f"{int(round(val))} %", font=font(F_HEAD, 88), fill=col, anchor="lm")
        d.rounded_rectangle([40, 192, 40 + max(14, 400 * val / 100), 206], radius=7, fill=col)
        pulse = 0.0
        for tp, kk in ((T_PEAK, 0), (T_WEG, 0), (T_WEG, 1), (at("tag1", "Mails"), 1)):
            if kk == k and 0 <= t - tp < 0.5:
                pulse = max(pulse, 1 - (t - tp) / 0.5)
        if k == 0 and T_PEAK <= t < s0("tag14"):
            pulse = max(pulse, 0.3 + 0.3 * math.sin(t * 8))
        img = with_shadow(card, dy=10, blur=16, alpha=0.25, pad=30)
        paste_center(frame, img, cx, 455, scale=max(0.05, p) * (1 + 0.08 * pulse))
    for tp, text, col, x in ((T_PEAK, "100 %", GREEN, 280), (T_WEG, "WEG!", RED, 280)):
        u = (t - tp) / 1.1
        if 0 <= u <= 1:
            paste_center(frame, chip_img(text, col), x, 720 - 80 * ease_out(u), scale=0.6 + 0.4 * ease_back(u * 3, 2),
                         alpha=1 - clamp01((u - 0.7) / 0.3))


def draw_stickers(frame, t):
    for i, (ts, ch, x, y) in enumerate(STICKERS):
        if t < ts:
            continue
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


def draw_flyers(frame, t):
    groups = []
    for tm in (at("tag1", "Mails"), at("tag1", "Handy")):
        groups.append((tm, "📧", (W + 60, ROOM_Y + 200), (800, 455), 5))
    groups.append((at("tag35", "sinken"), "😌", (W / 2, ROOM_Y + 500), (280, 455), 4))
    groups.append((T_PEAK, "☀️", (W / 2, ROOM_Y + 300), (280, 455), 6))
    for k in range(4):
        groups.append((T_OFFICE + 0.5 + k * 0.9, "📧", (W + 60, ROOM_Y + 150 + k * 60), (800, 455), 3))
    for gi, (ts, ch, src, dst, n) in enumerate(groups):
        for k in range(n):
            u = (t - ts - k * 0.07) / 0.65
            if not 0 <= u < 1:
                continue
            e = ease_io(u)
            sx = src[0] + ((k * 53 + gi * 31) % 160 - 80)
            sy = src[1] + ((k * 29 + gi * 17) % 120 - 60)
            mx, my = (sx + dst[0]) / 2, min(sy, dst[1]) - 200
            x = (1 - e) ** 2 * sx + 2 * (1 - e) * e * mx + e * e * dst[0]
            y = (1 - e) ** 2 * sy + 2 * (1 - e) * e * my + e * e * dst[1]
            paste_center(frame, emoji_img(ch, 78), x, y, scale=lerp(1.0, 0.45, e), rot=(u * 300 + k * 40) % 360,
                         alpha=1 - clamp01((u - 0.85) / 0.15))


# ------------------------------------------------------------------ captions
def build_caps():
    caps = []
    for si, sc in enumerate(TIM):
        for w in sc["words"]:
            caps.append(dict(text=w["text"], start=OFF[si] + w["start"], end=OFF[si] + w["end"]))
    for i, c in enumerate(caps):
        nxt = caps[i + 1]["start"] if i + 1 < len(caps) else TOTAL
        c["end"] = min(nxt, c["end"] + 0.35)
    return caps


@lru_cache(maxsize=256)
def cap_img(text, hl):
    im = text_img(text, font(F_CAP, 96), YELLOW if hl else PAPER, stroke=12)
    sh = Image.new("RGBA", (im.width + 40, im.height + 40), (0, 0, 0, 0))
    a = Image.new("L", sh.size, 0)
    a.paste(im.getchannel("A"), (20, 26))
    sh.putalpha(a.filter(ImageFilter.GaussianBlur(9)).point(lambda v: int(v * 0.5)))
    sh.alpha_composite(im, (20, 20))
    return sh


def draw_caption(frame, t):
    if t >= T_Q - 0.05:
        return
    for c in G["caps"]:
        if c["start"] <= t < c["end"]:
            img = cap_img(c["text"], any(k in c["text"] for k in HL_WORDS))
            p = clamp01((t - c["start"]) / 0.12)
            sc = (0.8 + 0.2 * ease_back(p, 2.2)) * min(1.0, 1000 / img.width)
            paste_center(frame, img, W / 2, 1612, scale=sc)
            return


# ------------------------------------------------------------------ frame
def render_frame(fi):
    t = fi / FPS
    office = clamp01((t - T_OFFICE) / 0.3)
    frame = Image.blend(G["bg"][0], G["bg"][1], office) if office > 0.005 else G["bg"][0].copy()
    d = ImageDraw.Draw(frame)
    d.rounded_rectangle([40, 26, W - 40, 34], radius=4, fill=(128, 128, 128, 60))
    d.rounded_rectangle([40, 26, 40 + (W - 80) * clamp01(t / TOTAL), 34], radius=4, fill=TEAL)

    frame.alpha_composite(shoot(draw_scene(t), t), (ROOM_X - 8, ROOM_Y - 8))
    if t >= T_Q:
        p = (t - T_Q) / 0.5
        frame.alpha_composite(Image.new("RGBA", (W, ROOM_H + 40), (8, 10, 20, int(150 * clamp01(p * 2)))),
                              (0, ROOM_Y - 20))
        paste_center(frame, G["question"], W / 2, ROOM_Y + 360, scale=max(0.05, 0.3 + 0.7 * ease_back(p, 1.6)),
                     alpha=clamp01(p * 3))
        tf = at("cta", "folg")
        q = (t - tf + 0.3) / 0.4
        if q > 0:
            tap = 1 - 0.08 * math.sin(clamp01((t - tf - 0.25) / 0.25) * math.pi)
            paste_center(frame, G["follow"], W / 2, ROOM_Y + 745, scale=max(0.05, ease_back(q, 2)) * tap)
            u = (t - tf - 0.25) / 0.5
            if 0 <= u < 1:   # tap ripple
                dd = ImageDraw.Draw(frame)
                r = 30 + 80 * ease_out(u)
                dd.ellipse([W / 2 + 120 - r, ROOM_Y + 725 - r, W / 2 + 120 + r, ROOM_Y + 725 + r],
                           outline=(255, 255, 255, int(220 * (1 - u))), width=6)

    draw_counter(frame, t)
    draw_flyers(frame, t)
    draw_meters(frame, t)
    draw_stickers(frame, t)
    draw_caption(frame, t)

    tcol = (120, 112, 100) if office < 0.5 else (110, 118, 126)
    if t >= s0("fazit"):
        paste_center(frame, text_img("Vereinfacht nach Studien · Angaben ohne Gewähr", font(F_BODY_B, 30), tcol),
                     W / 2, 1745, alpha=clamp01((t - s0("fazit")) / 0.4))
    paste_center(frame, text_img("@alltagklar", font(F_HEAD_B, 30), tcol), W / 2, 1855, alpha=0.85)
    arr = np.asarray(frame.convert("RGB"), np.int16) + G["grain"][(fi // 2) % len(G["grain"])]
    return np.clip(arr, 0, 255).astype(np.uint8).tobytes()


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
        y += (0.02 + 0.35 * math.sin(math.pi * u) ** 2) * (noise[i] - y)
        out[i] = y
    return out * np.sin(np.pi * np.linspace(0, 1, n)) ** 1.5 * 0.9


def sfx_pop():
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    f = 700 + 900 * (t / t[-1])
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.025) * 0.6


def sfx_ding():
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for st, f in ((0.0, 1318.5), (0.09, 1760.0)):
        i = int(st * SR)
        tt = t[: n - i]
        out[i:] += (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt / 0.18) * \
            np.minimum(1, tt / 0.002)
    return out * 0.3


def sfx_chime():
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k, f in enumerate((523.25, 659.25, 783.99, 1046.5, 1318.5)):
        i = int(k * 0.07 * SR)
        tt = t[: n - i]
        out[i:] += np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.6) * np.minimum(1, tt / 0.003) * 0.22
    return out


def sfx_powerdown():
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    f = 600 * np.exp(-t * 2.4) + 60
    sig = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.25 + np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.4
    return sig * np.minimum(1, t / 0.01) * np.exp(-t / 0.5) * 0.6


def sfx_thud(rng):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (55 + 90 * np.exp(-t * 30)) * t) * _env(n, 0.001, 0.1)
    return (body + rng.standard_normal(n) * _env(n, 0.0005, 0.012) * 0.5) * 0.9


def sfx_sneeze(rng):
    n = int(0.55 * SR)
    t = np.arange(n) / SR
    inhale = rng.standard_normal(n) * np.clip(t / 0.3, 0, 1) * (t < 0.3) * 0.15
    burst = np.convolve(rng.standard_normal(n), np.ones(4) / 4, mode="same") * (t >= 0.3) * \
        np.exp(-np.clip(t - 0.3, 0, None) / 0.08) * 0.9
    return inhale + burst


def sfx_gull(rng):
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = 1400 - 500 * t / t[-1] + 80 * np.sin(2 * np.pi * 12 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.3 * np.sin(3 * ph)
    return sig * np.sin(np.pi * t / t[-1]) ** 2 * 0.07


def waves_bed(dur, rng):
    n = int(dur * SR)
    nz = rng.standard_normal(n)
    lp = np.zeros(n)
    y = 0.0
    a = 0.04
    for i in range(n):
        y += a * (nz[i] - y)
        lp[i] = y
    t = np.arange(n) / SR
    swell = 0.35 + 0.65 * (0.5 + 0.5 * np.sin(2 * np.pi * t / 5.5)) ** 2
    return lp * swell * 4.0


def office_bed(dur, rng):
    n = int(dur * SR)
    t = np.arange(n) / SR
    hum = np.sin(2 * np.pi * 100 * t) * 0.02 + np.sin(2 * np.pi * 200 * t) * 0.01
    out = hum.copy()
    tm = 0.0
    while tm < dur:
        tm += rng.uniform(0.08, 0.25)
        i = int(tm * SR)
        k = int(0.012 * SR)
        if i + k < n:
            out[i:i + k] += rng.standard_normal(k) * np.exp(-np.arange(k) / (0.002 * SR)) * 0.25
    return out


def beat_bed(dur, bpm=104):
    rng = np.random.default_rng(3)
    n = int(dur * SR)
    out = np.zeros(n)
    beat = 60 / bpm
    kick_n = int(0.3 * SR)
    kt = np.arange(kick_n) / SR
    kick = np.sin(2 * np.pi * (48 + 90 * np.exp(-kt * 25)) * kt) * _env(kick_n, 0.001, 0.12)
    hat_n = int(0.04 * SR)
    hat = np.diff(rng.standard_normal(hat_n + 1)) * _env(hat_n, 0.0005, 0.01) * 0.25
    chords = [[261.63, 329.63, 392.0], [196.0, 246.94, 293.66], [220.0, 261.63, 329.63], [174.61, 220.0, 261.63]]
    i, tb = 0, 0.0
    while tb < dur:
        a0 = int(tb * SR)
        bb = i % 4
        if bb in (0, 2):
            seg = kick[: max(0, min(kick_n, n - a0))]
            out[a0:a0 + len(seg)] += seg * 0.7
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

    for ts in WHIPS:
        put(sfx_whoosh(rng) * 0.6, ts - 0.15)
    for ts, *_ in SHOTS[1:]:
        if all(abs(ts - w) > 0.05 for w in WHIPS):
            put(sfx_whoosh(rng, 0.22) * 0.3, ts - 0.08)
    for tm, d in DAYMARKS:
        put(sfx_pop() * 0.35, tm)
    for tm in (at("tag1", "Mails"), at("tag1", "Handy")):
        for k in range(3):
            put(sfx_ding() * 0.8, tm + 0.25 + k * 0.18)
    for k in range(4):
        put(sfx_ding() * 0.7, T_OFFICE + 0.9 + k * 0.9)
    put(sfx_sneeze(rng), at("tag2", "Schnupfen") - 0.2)
    put(sfx_chime(), T_PEAK)
    put(sfx_powerdown(), T_WEG)
    put(sfx_thud(rng), T_WEG + 0.02)
    put(sfx_thud(rng) * 0.6, at("tag14", "Koffer") + 0.1)
    for ts, *_ in STICKERS:
        put(sfx_pop() * 0.6, ts + 0.08)
    put(sfx_pop() * 0.9, T_Q + 0.1)
    put(sfx_pop() * 1.0, at("cta", "folg") - 0.3)
    put(sfx_ding() * 0.6, at("cta", "folg") + 0.25)
    for tg in (0.6, 4.2, 8.5, 13.0, 19.5, 24.0):
        if tg < T_OFFICE - 0.5:
            put(sfx_gull(rng), tg)
    amb = np.zeros(n)
    wv = waves_bed(T_OFFICE + 0.3, rng)
    wv *= np.minimum(1, (len(wv) - np.arange(len(wv))) / (0.3 * SR))
    amb[: len(wv)] += wv * 0.5
    ob = office_bed(TOTAL - T_OFFICE, rng)
    i0 = int(T_OFFICE * SR)
    amb[i0:i0 + len(ob)] += ob[: n - i0]
    bed = beat_bed(TOTAL)
    mix = np.zeros(n)
    mix[: len(out)] += out * 0.55
    mix += amb * 0.5
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
    out = ROOT / os.environ.get("VIDEO_OUT", "urlaub-video.mp4")
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
           "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "slow", "-crf", "21",
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
