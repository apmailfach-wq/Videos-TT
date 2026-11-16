"""Render the TikTok video (1080x1920, 30 fps) from build/timings.json.

Pipeline: Pillow draws every frame -> raw RGB piped into ffmpeg -> H.264 + AAC.
"""
import json
import math
import os
import random
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
W, H, FPS = 1080, 1920, 30
TAIL = 0.7  # seconds of silence after the last word

FONT_DIR = "/usr/share/fonts/opentype/inter/"
F_BLACK = FONT_DIR + "Inter-Black.otf"
F_XBOLD = FONT_DIR + "Inter-ExtraBold.otf"
F_BOLD = FONT_DIR + "Inter-Bold.otf"
F_SEMI = FONT_DIR + "Inter-SemiBold.otf"

WHITE = (255, 255, 255)
MUTED = (170, 180, 200)

ACCENTS = {
    "hook": (255, 59, 92),
    "notwehr": (34, 211, 238),
    "exzess": (167, 139, 250),
    "grenze": (255, 77, 77),
    "tipps": (251, 191, 36),
}
CHIPS = {
    "hook": "RECHT KOMPAKT",
    "notwehr": "§ 32 StGB · NOTWEHR",
    "exzess": "§ 33 StGB · NOTWEHREXZESS",
    "grenze": "ACHTUNG · DIE GRENZE",
    "tipps": "3 GOLDENE TIPPS",
}


@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, size)


def ease_out_back(x, s=1.6):
    x = min(max(x, 0.0), 1.0) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------------------------------------------------------- timing data
TIM = json.loads((BUILD / "timings.json").read_text())
from script import SCENES  # noqa: E402

SCENE_KEYS = [s["key"] for s in SCENES]
OFFSETS = []
_acc = 0.0
for s in TIM:
    OFFSETS.append(_acc)
    _acc += s["duration"]
TOTAL = _acc + TAIL
NFRAMES = int(math.ceil(TOTAL * FPS))


def at(scene, word, occ=0, lead=0.08):
    """Global time (s) at which `word` (occurrence `occ`) starts in scene."""
    si = SCENE_KEYS.index(scene)
    n = 0
    for w in TIM[si]["words"]:
        if w["text"].strip(".,:!?").startswith(word):
            if n == occ:
                return OFFSETS[si] + w["start"] - lead
            n += 1
    raise KeyError((scene, word, occ))


def scene_start(scene):
    return OFFSETS[SCENE_KEYS.index(scene)]


def scene_end(scene):
    i = SCENE_KEYS.index(scene)
    return OFFSETS[i] + TIM[i]["duration"] + (TAIL if i == len(TIM) - 1 else 0)


def scene_at(t):
    for i in range(len(OFFSETS) - 1, -1, -1):
        if t >= OFFSETS[i]:
            return i
    return 0


# ---------------------------------------------------------------- icons
SS = 2  # supersampling for icons


def icon_image(name, accent, size=300):
    S = size * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    lw = int(S * 0.045)
    # base disc + ring
    d.ellipse([S * 0.04, S * 0.04, S * 0.96, S * 0.96], fill=accent + (46,),
              outline=accent + (255,), width=int(S * 0.025))
    col = WHITE + (255,)
    acc = accent + (255,)

    def line(pts, color=col, width=lw):
        d.line(pts, fill=color, width=width, joint="curve")
        r = width / 2
        for p in (pts[0], pts[-1]):
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)

    def rel(x, y):
        return (c + x * S, c + y * S)

    if name == "bolt":
        pts = [rel(0.06, -0.30), rel(-0.14, 0.03), rel(0.0, 0.03), rel(-0.06, 0.30),
               rel(0.15, -0.04), rel(0.01, -0.04), rel(0.08, -0.30)]
        d.polygon(pts, fill=col)
    elif name == "doc":
        x0, y0, x1, y1 = c - S * 0.18, c - S * 0.25, c + S * 0.18, c + S * 0.25
        d.rounded_rectangle([x0, y0, x1, y1], radius=S * 0.03, outline=col, width=lw)
        for k in range(3):
            yy = y0 + S * (0.13 + k * 0.1)
            line([(x0 + S * 0.08, yy), (x1 - S * 0.08 - (S * 0.08 if k == 2 else 0), yy)],
                 width=int(lw * 0.7))
        # red stamp "!"
        d.ellipse([x1 - S * 0.1, y1 - S * 0.12, x1 + S * 0.1, y1 + S * 0.08], fill=acc)
        f = font(F_BLACK, int(S * 0.15))
        d.text((x1, y1 - S * 0.02), "!", font=f, fill=WHITE, anchor="mm")
    elif name == "para":
        f = font(F_BLACK, int(S * 0.5))
        d.text((c, c + S * 0.02), "§", font=f, fill=col, anchor="mm")
    elif name == "scale":
        line([rel(0, -0.27), rel(0, 0.24)])
        line([rel(-0.16, 0.25), rel(0.16, 0.25)])
        line([rel(-0.26, -0.17), rel(0.26, -0.17)])
        d.ellipse([c - S * 0.04, c - S * 0.31, c + S * 0.04, c - S * 0.23], fill=col)
        for sx in (-1, 1):
            px = c + sx * S * 0.22
            py = c - S * 0.17
            line([(px, py), (px - S * 0.09, py + S * 0.2)], width=int(lw * 0.6))
            line([(px, py), (px + S * 0.09, py + S * 0.2)], width=int(lw * 0.6))
            d.chord([px - S * 0.12, py + S * 0.1, px + S * 0.12, py + S * 0.3], 0, 180, fill=acc)
    elif name == "shield":
        pts = [rel(0, -0.29), rel(0.22, -0.2), rel(0.2, 0.06), rel(0, 0.3),
               rel(-0.2, 0.06), rel(-0.22, -0.2)]
        d.polygon(pts, fill=accent + (90,))
        line(pts + [pts[0]])
        line([rel(-0.09, 0.0), rel(-0.02, 0.08), rel(0.11, -0.08)], width=int(lw * 1.1))
    elif name == "check":
        line([rel(-0.17, 0.01), rel(-0.05, 0.13), rel(0.19, -0.13)], width=int(lw * 1.4))
    elif name == "cross":
        line([rel(-0.15, -0.15), rel(0.15, 0.15)], color=acc, width=int(lw * 1.4))
        line([rel(-0.15, 0.15), rel(0.15, -0.15)], color=acc, width=int(lw * 1.4))
    elif name == "norun":
        line([rel(-0.22, 0.0), rel(0.18, 0.0)], width=int(lw * 1.2))
        line([rel(0.06, -0.12), rel(0.2, 0.0), rel(0.06, 0.12)], width=int(lw * 1.2))
        d.ellipse([c - S * 0.3, c - S * 0.3, c + S * 0.3, c + S * 0.3], outline=acc, width=int(lw * 1.1))
        line([rel(-0.21, -0.21), rel(0.21, 0.21)], color=acc, width=int(lw * 1.1))
    elif name == "quote":
        f = font(F_BLACK, int(S * 0.62))
        d.text((c, c + S * 0.13), "„", font=f, fill=col, anchor="mm")
    elif name == "pulse":
        pts = [rel(-0.3, 0.02), rel(-0.13, 0.02), rel(-0.07, -0.18), rel(0.01, 0.2),
               rel(0.08, -0.08), rel(0.12, 0.02), rel(0.3, 0.02)]
        line(pts, width=int(lw * 1.1))
    elif name == "stop":
        r = S * 0.3
        pts = [(c + r * math.cos(math.radians(22.5 + 45 * k)),
                c + r * math.sin(math.radians(22.5 + 45 * k))) for k in range(8)]
        d.polygon(pts, fill=acc, outline=WHITE, width=int(lw * 0.5))
        f = font(F_BLACK, int(S * 0.15))
        d.text((c, c), "STOP", font=f, fill=WHITE, anchor="mm")
    elif name == "flag":
        line([rel(-0.16, -0.28), rel(-0.16, 0.29)])
        d.polygon([rel(-0.14, -0.26), rel(0.2, -0.2), rel(0.1, -0.08), rel(0.22, 0.04),
                   rel(-0.14, 0.0)], fill=col)
    elif name == "de":
        bw, bh = S * 0.5, S * 0.11
        for k, colr in enumerate([(20, 20, 20), (221, 0, 0), (255, 206, 0)]):
            y0 = c - bh * 1.5 + k * bh
            d.rectangle([c - bw / 2, y0, c + bw / 2, y0 + bh], fill=colr + (255,))
        d.rectangle([c - bw / 2, c - bh * 1.5, c + bw / 2, c + bh * 1.5], outline=col, width=int(lw * 0.4))
    elif name == "star":
        pts = []
        for k in range(10):
            r = S * (0.29 if k % 2 == 0 else 0.12)
            a = math.radians(-90 + 36 * k)
            pts.append((c + r * math.cos(a), c + r * math.sin(a)))
        d.polygon(pts, fill=acc)
    elif name == "lock":
        d.rounded_rectangle([c - S * 0.19, c - S * 0.04, c + S * 0.19, c + S * 0.26],
                            radius=S * 0.04, fill=col)
        d.arc([c - S * 0.13, c - S * 0.28, c + S * 0.13, c + S * 0.06], 180, 360, fill=col, width=lw)
        line([rel(-0.13, -0.11), rel(-0.13, -0.04)])
        line([rel(0.13, -0.11), rel(0.13, -0.04)])
        d.ellipse([c - S * 0.04, c + S * 0.06, c + S * 0.04, c + S * 0.14], fill=accent + (255,))
    elif name == "med":
        a, b = S * 0.08, S * 0.24
        d.rounded_rectangle([c - a, c - b, c + a, c + b], radius=S * 0.02, fill=col)
        d.rounded_rectangle([c - b, c - a, c + b, c + a], radius=S * 0.02, fill=col)
    elif name == "bookmark":
        pts = [rel(-0.15, -0.27), rel(0.15, -0.27), rel(0.15, 0.28), rel(0, 0.14), rel(-0.15, 0.28)]
        d.polygon(pts, fill=acc)
        d.line(pts + [pts[0]], fill=col, width=int(lw * 0.6), joint="curve")
    elif name == "skull":  # head icon for "Tritte gegen den Kopf"
        d.ellipse([c - S * 0.2, c - S * 0.26, c + S * 0.2, c + S * 0.14], outline=col, width=lw)
        line([rel(-0.06, 0.14), rel(-0.06, 0.26)])
        line([rel(0.06, 0.14), rel(0.06, 0.26)])
        line([rel(-0.12, -0.1), rel(-0.04, -0.02)], color=acc)
        line([rel(-0.12, -0.02), rel(-0.04, -0.1)], color=acc)
        line([rel(0.04, -0.1), rel(0.12, -0.02)], color=acc)
        line([rel(0.04, -0.02), rel(0.12, -0.1)], color=acc)
    return im.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- rich text
def parse_rich(text):
    """'Niemand muss *WEGLAUFEN*' -> [(word, highlighted)]"""
    out, hl = [], False
    for tok in text.split(" "):
        start = tok.startswith("*")
        if start:
            hl = True
            tok = tok[1:]
        tail = ""
        while tok and tok[-1] in ".,:!?…" and tok.rstrip(".,:!?…").endswith("*"):
            tail = tok[-1] + tail
            tok = tok[:-1]
        end = tok.endswith("*")
        if end:
            tok = tok[:-1] + tail
        out.append((tok, hl))
        if end:
            hl = False
    return out


def text_block(text, fpath, size, accent, max_w=900, color=WHITE, line_gap=1.12,
               stroke=0, shadow=True):
    f = font(fpath, size)
    words = parse_rich(text)
    space = f.getlength(" ")
    lines, cur, cur_w = [], [], 0.0
    for wd, hl in words:
        if wd == "\\n":
            lines.append(cur)
            cur, cur_w = [], 0.0
            continue
        ww = f.getlength(wd)
        if cur and cur_w + space + ww > max_w:
            lines.append(cur)
            cur, cur_w = [], 0.0
        cur.append((wd, hl, ww))
        cur_w += (space if len(cur) > 1 else 0) + ww
    if cur:
        lines.append(cur)
    lh = int(size * line_gap)
    pad = 30
    bw = int(max(sum(w for _, _, w in ln) + space * (len(ln) - 1) for ln in lines)) + pad * 2
    bh = lh * len(lines) + pad * 2
    im = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for li, ln in enumerate(lines):
        lw = sum(w for _, _, w in ln) + space * (len(ln) - 1)
        x = (bw - lw) / 2
        y = pad + li * lh + lh / 2
        for wd, hl, ww in ln:
            d.text((x, y), wd, font=f, fill=(accent if hl else color) + (255,), anchor="lm",
                   stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
            x += ww + space
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sh.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(10)).point(lambda v: v * 0.7))
        base = Image.new("RGBA", im.size, (0, 0, 0, 0))
        base.alpha_composite(sh, (0, 6))
        base.alpha_composite(im)
        im = base
    return im


def pill(text, accent, size=40, fpath=F_XBOLD, filled=False, padx=34, pady=18):
    f = font(fpath, size)
    tw = f.getlength(text)
    bw, bh = int(tw + padx * 2), int(size + pady * 2)
    im = Image.new("RGBA", (bw + 8, bh + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if filled:
        d.rounded_rectangle([4, 4, bw + 4, bh + 4], radius=bh / 2, fill=accent + (255,))
        d.text((4 + bw / 2, 4 + bh / 2), text, font=f, fill=(12, 14, 22), anchor="mm")
    else:
        d.rounded_rectangle([4, 4, bw + 4, bh + 4], radius=bh / 2, fill=(255, 255, 255, 18),
                            outline=accent + (255,), width=4)
        d.text((4 + bw / 2, 4 + bh / 2), text, font=f, fill=WHITE, anchor="mm")
    return im


def glow_icon(name, accent, size=300):
    ic = icon_image(name, accent, size)
    pad = 60
    im = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    g = Image.new("RGBA", im.size, accent + (0,))
    a = Image.new("L", im.size, 0)
    ImageDraw.Draw(a).ellipse([pad, pad, pad + size, pad + size], fill=150)
    g.putalpha(a.filter(ImageFilter.GaussianBlur(28)))
    im.alpha_composite(g)
    im.alpha_composite(ic, (pad, pad))
    return im


def tip_row(num, text, accent, active):
    w, h = 920, 170
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bg = accent + (60,) if active else (255, 255, 255, 16)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=36, fill=bg,
                        outline=(accent + (255,)) if active else (255, 255, 255, 50), width=4)
    d.ellipse([26, 30, 136, 140], fill=accent + (255,))
    d.text((81, 86), str(num), font=font(F_BLACK, 64), fill=(12, 14, 22), anchor="mm")
    f = font(F_XBOLD, 52)
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        y = h / 2 + (i - (len(lines) - 1) / 2) * 56
        d.text((168, y), ln, font=f, fill=WHITE + (255,), anchor="lm")
    return im


# ---------------------------------------------------------------- cards
# Each card: start, end, list of elements. Element = (appear_time, image, y_center)
CARD_TOP = 470  # card canvas spans y = CARD_TOP .. CARD_TOP + CARD_H
CARD_H = 900


class Card:
    def __init__(self, scene, start, end):
        self.scene = scene
        self.start = start
        self.end = end
        self.els = []

    def add(self, img, y, t=None, kind="pop"):
        self.els.append((self.start if t is None else t, img, y, kind))
        return self


def build_cards():
    cards = []
    A = ACCENTS

    def card(scene, start, end):
        c = Card(scene, start, end)
        cards.append(c)
        return c

    # --- 1 Hook
    a = A["hook"]
    t1, t2, t3 = -0.3, at("hook", "bekommst"), at("hook", "So")
    (card("hook", t1, t2)
     .add(glow_icon("bolt", a), 230)
     .add(text_block("Du wirst *ANGEGRIFFEN*", F_BLACK, 104, a), 520)
     .add(text_block("…und wehrst dich.", F_BOLD, 64, a, color=MUTED), 680, at("hook", "wehrst")))
    (card("hook", t2, t3)
     .add(glow_icon("doc", a), 230)
     .add(text_block("Plötzlich hast *DU* eine *ANZEIGE?!*", F_BLACK, 96, a), 560))
    (card("hook", t3, scene_end("hook"))
     .add(glow_icon("de", a), 230)
     .add(text_block("So ist die *Rechtslage* in Deutschland", F_BLACK, 92, a), 560))

    # --- 2 Notwehr §32
    a = A["notwehr"]
    s = scene_start("notwehr")
    k = [s, at("notwehr", "Wirst"), at("notwehr", "darfst"), at("notwehr", "Wichtig"),
         at("notwehr", "Und"), at("notwehr", "Das"), scene_end("notwehr")]
    (card("notwehr", k[0], k[1])
     .add(glow_icon("shield", a), 230)
     .add(text_block("*NOTWEHR*", F_BLACK, 150, a), 520)
     .add(pill("§ 32 StGB", a, 52, filled=True), 690, s + 1.4))
    (card("notwehr", k[1], k[2])
     .add(glow_icon("bolt", a), 220)
     .add(text_block("Angriff ist…", F_BOLD, 64, a, color=MUTED), 450)
     .add(pill("✓ GEGENWÄRTIG", a, 56), 580, at("notwehr", "gegenwärtig"))
     .add(pill("✓ RECHTSWIDRIG", a, 56), 720, at("notwehr", "rechtswidrig")))
    (card("notwehr", k[2], k[3])
     .add(glow_icon("check", a), 230)
     .add(text_block("Du darfst dich *verteidigen*", F_BLACK, 92, a), 520)
     .add(pill("= STRAFFREI", a, 70, F_BLACK, filled=True), 730, at("notwehr", "straffrei")))
    (card("notwehr", k[3], k[4])
     .add(glow_icon("scale", a), 230)
     .add(text_block("Das *mildeste Mittel*…", F_BLACK, 96, a), 510)
     .add(text_block("…das den Angriff *SICHER* beendet", F_BOLD, 66, a, color=WHITE), 700,
          at("notwehr", "das", 1)))
    (card("notwehr", k[4], k[5])
     .add(glow_icon("norun", a), 230)
     .add(text_block("Niemand muss *WEGLAUFEN*", F_BLACK, 104, a), 560))
    (card("notwehr", k[5], k[6])
     .add(glow_icon("quote", a), 230)
     .add(text_block("Das Recht muss dem *Unrecht* nicht weichen.", F_BLACK, 88, a), 570))

    # --- 3 Notwehrexzess §33
    a = A["exzess"]
    s = scene_start("exzess")
    k = [s, at("exzess", "Hast"), at("exzess", "bleibst"), at("exzess", "Denn"), scene_end("exzess")]
    (card("exzess", k[0], k[1])
     .add(glow_icon("para", a), 230)
     .add(text_block("*NOTWEHR-EXZESS*", F_BLACK, 92, a), 520)
     .add(pill("§ 33 StGB", a, 52, filled=True), 690, s + 1.6))
    (card("exzess", k[1], k[2])
     .add(text_block("Zu hart reagiert aus…", F_BOLD, 64, a, color=MUTED), 170)
     .add(pill("FURCHT", a, 84, F_BLACK), 340, at("exzess", "Furcht"))
     .add(pill("SCHRECKEN", a, 84, F_BLACK), 520, at("exzess", "Schrecken"))
     .add(pill("VERWIRRUNG", a, 84, F_BLACK), 700, at("exzess", "Verwirrung")))
    (card("exzess", k[2], k[3])
     .add(glow_icon("check", a), 230)
     .add(text_block("Trotzdem *oft*", F_BLACK, 96, a), 500)
     .add(pill("STRAFFREI", a, 84, F_BLACK, filled=True), 680, at("exzess", "straffrei")))
    (card("exzess", k[3], k[4])
     .add(glow_icon("pulse", a), 230)
     .add(text_block("In *Panik* reagiert niemand perfekt.", F_BLACK, 92, a), 560))

    # --- 4 Die Grenze
    a = A["grenze"]
    s = scene_start("grenze")
    k = [s, at("grenze", "Sobald"), at("grenze", "Wer"), at("grenze", "Das"),
         at("grenze", "Bei"), scene_end("grenze")]
    (card("grenze", k[0], k[1])
     .add(glow_icon("stop", a), 230)
     .add(text_block("Hier ist die *GRENZE*", F_BLACK, 112, a), 540))
    (card("grenze", k[1], k[2])
     .add(glow_icon("flag", a), 220)
     .add(text_block("Angreifer *am Boden* oder *gibt auf*", F_BLACK, 84, a), 500)
     .add(pill("= SCHLUSS!", a, 76, F_BLACK, filled=True), 710, at("grenze", "Schluss")))
    (card("grenze", k[2], k[3])
     .add(glow_icon("cross", a), 220)
     .add(text_block("*Nachtreten* oder *Rache*", F_BLACK, 96, a), 480)
     .add(text_block("= keine Notwehr mehr. Du bist jetzt der *Angreifer*.", F_BOLD, 62, a), 680,
          at("grenze", "verteidigt")))
    (card("grenze", k[3], k[4])
     .add(pill("§ 223 StGB", a, 52, filled=True), 150)
     .add(text_block("Körperverletzung", F_BLACK, 96, a), 300)
     .add(text_block("bis zu", F_BOLD, 60, a, color=MUTED), 450, at("grenze", "bis"))
     .add(text_block("*5 JAHRE*", F_BLACK, 170, a), 590, at("grenze", "fünf"))
     .add(text_block("Haft", F_BOLD, 60, a, color=MUTED), 740, at("grenze", "Haft")))
    (card("grenze", k[4], k[5])
     .add(glow_icon("skull", a, 220), 110)
     .add(text_block("z. B. *Tritte gegen den Kopf*", F_BOLD, 62, a), 290)
     .add(pill("§ 224 StGB", a, 50, filled=True), 420, at("grenze", "gefährliche"))
     .add(text_block("Gefährliche Körperverletzung", F_BLACK, 74, a), 560, at("grenze", "gefährliche"))
     .add(text_block("*6 MONATE – 10 JAHRE*", F_BLACK, 92, a), 750, at("grenze", "sechs")))

    # --- 5 Tipps
    a = A["tipps"]
    s = scene_start("tipps")
    k = [s, at("tipps", "Eins"), at("tipps", "Zwei"), at("tipps", "Drei", 1),
         at("tipps", "Speicher"), scene_end("tipps")]
    (card("tipps", k[0], k[1])
     .add(glow_icon("star", a), 230)
     .add(text_block("3 *GOLDENE* TIPPS", F_BLACK, 116, a), 530))
    tips = [("Bei der Polizei:\nerst mal SCHWEIGEN", "lock"),
            ("Verletzungen attestieren\n+ Zeugen sichern", "med"),
            ("Fachanwalt für\nStrafrecht einschalten", "scale")]
    for i in range(3):
        c = card("tipps", k[1 + i], k[2 + i])
        c.add(glow_icon(tips[i][1], a, 200), 120)
        for j in range(3):
            y = 350 + j * 195
            if j <= i:
                c.add(tip_row(j + 1, tips[j][0], a, j == i), y, k[1 + j] if j == i else None,
                      kind="slide" if j == i else "static")
    (card("tipps", k[4], k[5])
     .add(glow_icon("bookmark", a), 230)
     .add(text_block("*SPEICHER* dir das Video", F_BLACK, 100, a), 520)
     .add(text_block("für den Ernstfall!", F_BOLD, 66, a, color=MUTED), 690, at("tipps", "für", 1))
     .add(text_block("Keine Rechtsberatung – im Einzelfall Anwalt fragen.", F_SEMI, 34, a,
                     color=(130, 140, 160), shadow=False), 840, at("tipps", "Ernstfall")))
    return cards


# ---------------------------------------------------------------- subtitles
def build_subs():
    subs = []
    for si, s in enumerate(TIM):
        words = []
        for w in s["words"]:
            txt = w["text"].replace("Paragraf", "§").rstrip(".")
            words.append({"text": txt, "start": OFFSETS[si] + w["start"],
                          "end": OFFSETS[si] + w["end"]})
        # glue "§" to the following number so it never stands alone
        merged, skip = [], set()
        for wi, w in enumerate(words):
            if wi in skip:
                continue
            if w["text"] == "§" and wi + 1 < len(words):
                n = words[wi + 1]
                merged.append({"text": "§ " + n["text"], "start": w["start"], "end": n["end"],
                               "orig": [wi, wi + 1]})
                skip.add(wi + 1)
            else:
                merged.append(dict(w, orig=[wi]))
        # punctuation positions from the script text to break chunks naturally
        script_words = SCENES[si]["text"].replace(" –", ",").split()
        punct_after = set()
        j = 0
        for wi, w in enumerate(s["words"]):
            n = len(w["text"].split())
            j += n
            if j - 1 < len(script_words) and script_words[j - 1][-1] in ",.:!?":
                punct_after.add(wi)
        chunk = []
        words_m = merged
        for mi, w in enumerate(words_m):
            if chunk and sum(len(x["text"]) for x in chunk) + len(w["text"]) > 21:
                subs.append({"words": chunk, "scene": si})
                chunk = []
            chunk.append(w)
            chars = sum(len(x["text"]) for x in chunk)
            nxt_gap = words_m[mi + 1]["start"] - w["end"] if mi + 1 < len(words_m) else 9
            if punct_after.intersection(w["orig"]) or len(chunk) >= 3 or chars >= 18 or nxt_gap > 0.3:
                subs.append({"words": chunk, "scene": si})
                chunk = []
        if chunk:
            subs.append({"words": chunk, "scene": si})
    for c in subs:
        c["start"] = c["words"][0]["start"]
    for i, c in enumerate(subs):
        nxt = subs[i + 1]["start"] if i + 1 < len(subs) else TOTAL
        c["end"] = min(nxt, c["words"][-1]["end"] + 0.6)
    return subs


@lru_cache(maxsize=4096)
def sub_image(ci, active):
    c = SUBS[ci]
    accent = ACCENTS[SCENE_KEYS[c["scene"]]]
    f = font(F_BLACK, 70)
    space = f.getlength(" ")
    widths = [f.getlength(w["text"]) for w in c["words"]]
    total = sum(widths) + space * (len(widths) - 1)
    pad = 40
    im = Image.new("RGBA", (int(total + pad * 2), 70 + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = pad
    for i, (w, ww) in enumerate(zip(c["words"], widths)):
        if i == active:
            d.rounded_rectangle([x - 12, pad - 8, x + ww + 12, pad + 82], radius=16,
                                fill=accent + (255,))
            d.text((x, pad + 37), w["text"], font=f, fill=(10, 12, 20), anchor="lm")
        else:
            d.text((x, pad + 37), w["text"], font=f, fill=WHITE, anchor="lm",
                   stroke_width=6, stroke_fill=(0, 0, 0))
        x += ww + space
    return im


# ---------------------------------------------------------------- background
def radial(size, color, alpha):
    s = size
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    r = np.sqrt((xx - s / 2) ** 2 + (yy - s / 2) ** 2) / (s / 2)
    a = np.clip(1 - r, 0, 1) ** 2.2 * alpha
    arr = np.zeros((s, s, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def make_base():
    y = np.linspace(0, 1, H)[:, None]
    top = np.array([9, 11, 20], np.float32)
    bot = np.array([15, 18, 32], np.float32)
    g = top + (bot - top) * y[..., None]
    arr = np.repeat(g, W, axis=1)
    # vignette
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.7)) ** 2)
    arr *= np.clip(1.15 - 0.55 * v, 0.45, 1)[..., None]
    im = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    # subtle grid
    d = ImageDraw.Draw(im, "RGBA")
    for x in range(0, W, 90):
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 7), width=1)
    for yv in range(0, H, 90):
        d.line([(0, yv), (W, yv)], fill=(255, 255, 255, 7), width=1)
    return im


# ---------------------------------------------------------------- frame
BASE = None
GLOWS = None
CARDS = None
SUBS = None
PARTICLES = None
CHIP_IMGS = None


def init():
    global BASE, GLOWS, CARDS, SUBS, PARTICLES, CHIP_IMGS
    BASE = make_base()
    GLOWS = {k: radial(1300, v, 0.42) for k, v in ACCENTS.items()}
    CARDS = build_cards()
    SUBS = build_subs()
    rnd = random.Random(7)
    PARTICLES = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(8, 30), rnd.uniform(2, 5),
                  rnd.uniform(0, 6.28)) for _ in range(40)]
    CHIP_IMGS = {k: pill(CHIPS[k], ACCENTS[k], 34, F_XBOLD) for k in ACCENTS}


def place(frame, img, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0.01 or scale <= 0.01:
        return
    if abs(scale - 1.0) > 0.003:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                         Image.BICUBIC)
    if alpha < 0.999:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    frame.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))


def render_frame(fi):
    t = fi / FPS
    si = scene_at(t)
    key = SCENE_KEYS[si]
    accent = ACCENTS[key]
    frame = BASE.copy()

    # glow, crossfading between scene colors
    glow = GLOWS[key]
    ts = t - OFFSETS[si]
    gx = W / 2 + math.sin(t * 0.35) * 120
    gy = 900 + math.cos(t * 0.27) * 110
    breathe = 1.0 + 0.06 * math.sin(t * 1.3)
    place(frame, glow, gx, gy, breathe, 1.0)
    if si > 0 and ts < 0.6:
        place(frame, GLOWS[SCENE_KEYS[si - 1]], gx, gy, breathe, 1 - ts / 0.6)

    # particles
    d = ImageDraw.Draw(frame, "RGBA")
    for px, py, sp, r, ph in PARTICLES:
        y = (py - t * sp) % H
        x = px + math.sin(t * 0.6 + ph) * 18
        a = int(50 + 40 * math.sin(t * 1.7 + ph))
        d.ellipse([x - r, y - r, x + r, y + r], fill=accent + (a,))

    # cards (content layer with gentle zoom)
    layer = Image.new("RGBA", (W, CARD_H), (0, 0, 0, 0))
    active = False
    for c in CARDS:
        if not (c.start - 0.001 <= t < c.end + 0.25):
            continue
        out = clamp01((t - c.end) / 0.25)  # exit fade
        if out >= 1:
            continue
        active = True
        for (ta, img, y, kind) in c.els:
            if kind == "static":
                ta = c.start - 1
            p = (t - ta) / 0.45
            if p < 0:
                continue
            if kind == "slide":
                e = ease_out(p)
                place(layer, img, W / 2 + (1 - e) * 500, y, 1.0, clamp01(p * 2) * (1 - out))
            else:
                sc = 0.6 + 0.4 * ease_out_back(p)
                yy = y + (1 - ease_out(p)) * 40 - out * 30
                place(layer, img, W / 2, yy, sc, clamp01(p * 2.2) * (1 - out))
        # zoom based on card life
        life = clamp01((t - c.start) / max(0.5, c.end - c.start))
        zoom = 1.0 + 0.06 * life
    if active:
        place(frame, layer, W / 2, CARD_TOP + CARD_H / 2, zoom)

    # scene flash on transition
    if si > 0 and ts < 0.25:
        fl = Image.new("RGBA", (W, H), accent + (int(70 * (1 - ts / 0.25)),))
        frame.alpha_composite(fl)

    # header: chip + step dots + progress
    chip = CHIP_IMGS[key]
    cp = clamp01(ts / 0.4)
    place(frame, chip, W / 2, 250, 0.85 + 0.15 * ease_out_back(cp), cp)
    d = ImageDraw.Draw(frame, "RGBA")
    n = len(SCENE_KEYS)
    for k in range(n):
        cx = W / 2 + (k - (n - 1) / 2) * 44
        if k == si:
            d.rounded_rectangle([cx - 16, 326, cx + 16, 338], radius=6, fill=accent + (255,))
        else:
            d.ellipse([cx - 6, 326, cx + 6, 338], fill=(255, 255, 255, 110 if k < si else 50))
    bx0, bx1, by = 140, W - 140, 365
    d.rounded_rectangle([bx0, by, bx1, by + 8], radius=4, fill=(255, 255, 255, 30))
    d.rounded_rectangle([bx0, by, bx0 + (bx1 - bx0) * min(1, t / TOTAL), by + 8], radius=4,
                        fill=accent + (255,))

    # subtitles
    for ci, c in enumerate(SUBS):
        if c["start"] <= t < c["end"]:
            act = -1
            for wi, w in enumerate(c["words"]):
                if t >= w["start"]:
                    act = wi
            img = sub_image(ci, act)
            fit = min(1.0, 980 / img.width)
            p = clamp01((t - c["start"]) / 0.15)
            place(frame, img, W / 2, 1450, fit * (0.88 + 0.12 * ease_out_back(p)), clamp01(p * 2))
            break

    return frame.convert("RGB").tobytes()


def _worker_init():
    init()


def main():
    out = ROOT / "notwehr-video.mp4"
    preview = len(sys.argv) > 1 and sys.argv[1] == "preview"
    init()
    if preview:  # dump some stills for checking the layout
        (BUILD / "stills").mkdir(exist_ok=True)
        times = [float(x) for x in sys.argv[2:]] or [1, 4, 6.5, 9, 13, 18, 24, 30, 34, 38, 44,
                                                      48, 52, 56, 62, 66.8, 69, 73, 77, 81.5]
        for tt in times:
            fi = int(tt * FPS)
            Image.frombytes("RGB", (W, H), render_frame(fi)).save(BUILD / "stills" / f"t{tt:05.1f}.png")
        return

    audio = BUILD / "voice.wav"
    lst = BUILD / "concat.txt"
    lst.write_text("".join(f"file '{s['audio']}'\n" for s in TIM))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-af", f"apad=pad_dur={TAIL},loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000",
                    str(audio)], check=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio),
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-t", f"{NFRAMES / FPS:.3f}", "-shortest", str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=_worker_init) as pool:
        for i, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=8)):
            ff.stdin.write(buf)
            if i % 300 == 0:
                print(f"frame {i}/{NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", out, f"{NFRAMES / FPS:.2f}s")


if __name__ == "__main__":
    main()
