"""Render ice-video.mp4 (1080x1920, 30 fps): "Der ICE" – a deadpan satire told by the train.

Flat cartoon look: a white high-speed train with big googly eyes, a blue departure
board on top whose delay field turns from a panicking green "+0" into a reassuring
red "+70", word-by-word TikTok captions and synthesised SFX. Comedy beats (pauses)
are inserted into the voiceover at chosen words.
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BUILD = ROOT / "build" / "ice"
FONTS = ROOT / "fonts"
sys.path.insert(0, str(HERE))
from script import SCENES, CTA  # noqa: E402

W, H, FPS, SR = 1080, 1920, 30, 48000

F_HEAD = str(FONTS / "Unbounded_900Black.ttf")
F_HEAD_B = str(FONTS / "Unbounded_700Bold.ttf")
F_HAND = str(FONTS / "Caveat_700Bold.ttf")
F_BODY = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_BODY_X = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

INK = (22, 24, 30)
WHITE = (255, 255, 255)
TRAIN_W = (246, 248, 251)
TRAIN_O = (170, 178, 190)
TRAIN_G = (212, 218, 226)
GLASS = (30, 40, 58)
RED = (228, 30, 42)
BOARD = (16, 52, 125)
BOARD_D = (10, 36, 92)
YEL = (255, 214, 0)
GREEN = (40, 200, 90)
SKIN = (246, 200, 165)
SKIN2 = (198, 140, 100)


@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, size)


def c01(x):
    return min(max(x, 0.0), 1.0)


def eo(x):
    x = c01(x)
    return 1 - (1 - x) ** 3


def eio(x):
    x = c01(x)
    return x * x * (3 - 2 * x)


def eback(x, s=1.7):
    x = c01(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, t):
    return a + (b - a) * t


def lcol(a, b, t):
    return tuple(int(lerp(a[i], b[i], t)) for i in range(len(a)))


# ================================================================== timeline
# extra silence (s) after a given word (scene, word, occurrence) -> comedy timing
BEATS = {("einfahrt", "6 Uhr 12", 0): 0.35, ("einfahrt", "ein", 0): 0.25,
         ("bahnsteig", "Stille", 0): 1.0, ("bahnsteig", "fallen", 0): 0.35,
         ("news", "Programm", 0): 0.35,
         ("kassel", "pünktlich", 0): 0.3,
         ("kuh", "Gleis", 0): 0.7, ("kuh", "an", 0): 0.55, ("kuh", "an", 1): 0.7}
PAD = {"hook": 0.3, "einfahrt": 0.3, "bahnsteig": 0.45, "news": 0.45, "kassel": 0.35,
       "kind": 0.35, "papa": 1.4, "kuh": 1.2, "warten": 2.7, "ende": 3.4}


def norm(w):
    return w.strip(".,:!?…„“\"").strip()


def decode(path):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1",
                                   "-ar", str(SR), "-"])
    return np.frombuffer(raw, dtype=np.float32).copy()


def build_timeline():
    tim = json.loads((BUILD / "timings.json").read_text())
    pieces, words, segs = [], [], {}
    t = 0.0
    for sc, tm in zip(SCENES, tim):
        key = sc["key"]
        audio = decode(tm["audio"])
        ws = tm["words"]
        cuts = []  # (cut_time, extra)
        occ = {}
        for k, w in enumerate(ws):
            n = norm(w["text"])
            o = occ.get(n, 0)
            occ[n] = o + 1
            ex = BEATS.get((key, n, o))
            if ex and k + 1 < len(ws):
                cuts.append(((w["end"] + ws[k + 1]["start"]) / 2, ex))
        start = t
        shift = 0.0
        prev = 0.0
        for c, ex in cuts + [(len(audio) / SR, 0.0)]:
            pieces.append((key, audio[int(prev * SR):int(c * SR)], t + prev + shift))
            prev, shift = c, shift + ex
        for w in ws:
            add = sum(ex for c, ex in cuts if c <= w["start"])
            words.append({"key": key, "text": w["text"], "s": t + w["start"] + add, "e": t + w["end"] + add})
        t = t + len(audio) / SR + shift + PAD.get(key, 0.3)
        segs[key] = (start, t)
    return pieces, words, segs, t


PIECES, WORDS, SEG, TOTAL = build_timeline()
KEYS = [s["key"] for s in SCENES]
NFRAMES = int(math.ceil(TOTAL * FPS))


def at(key, word, occ=0, lead=0.04):
    n = 0
    for w in WORDS:
        if w["key"] == key and word in (norm(w["text"]), norm(w["text"]).split()[0]):
            if n == occ:
                return w["s"] - lead
            n += 1
    raise KeyError((key, word, occ))


def scene_at(t):
    for k in KEYS:
        if SEG[k][0] <= t < SEG[k][1]:
            return k
    return KEYS[-1]


# ================================================================== drawing helpers
def patch(w, h, fn, ss=2):
    im = Image.new("RGBA", (int(w * ss), int(h * ss)), (0, 0, 0, 0))
    fn(ImageDraw.Draw(im), ss)
    return im.reduce(ss) if ss > 1 else im


def paste(dst, im, x, y, center=True, alpha=1.0):
    if alpha <= 0.01:
        return
    if alpha < 0.999:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    if center:
        x, y = x - im.width // 2, y - im.height // 2
    dst.alpha_composite(im, (int(x), int(y))) if 0 <= x and 0 <= y and x + im.width <= dst.width \
        and y + im.height <= dst.height else _paste_clip(dst, im, int(x), int(y))


def _paste_clip(dst, im, x, y):
    l, t = max(0, -x), max(0, -y)
    r, b = min(im.width, dst.width - x), min(im.height, dst.height - y)
    if r <= l or b <= t:
        return
    dst.alpha_composite(im.crop((l, t, r, b)), (x + l, y + t))


def scaled(im, s):
    if abs(s - 1) < 0.004:
        return im
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BICUBIC)


def shadowed(im, dy=14, blur=14, a=0.28):
    pad = blur * 2
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad + dy), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (20, 25, 40, 0))
    sh.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    out.alpha_composite(sh, (pad, pad + dy))
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(im, (pad, pad))
    return out


def bez(p0, p1, p2, n=24):
    return [((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0],
             (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]) for u in (i / n for i in range(n + 1))]


def S(pts, s, ox=0, oy=0):
    return [(ox + x * s, oy + y * s) for x, y in pts]


def text_center(d, cx, y, txt, f, fill, stroke=0, sfill=INK):
    w = d.textlength(txt, font=f)
    d.text((cx - w / 2, y), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)


def emoji(ch, size):
    f = font(F_EMOJI, 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((80, 80), ch, font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox() or (0, 0, 160, 160))
    return im.resize((size, int(size * im.height / im.width)), Image.LANCZOS)


# ------------------------------------------------------------------ eyes / faces
def eye(d, cx, cy, rx, ry, look=(0, 0), lid=0.0, s=1, lid_col=GLASS, pupil=0.45, lower=0.0):
    """Cartoon eye. look in [-1,1]^2, lid 0=open..1=closed (from top), lower = lower lid."""
    box = [(cx - rx) * s, (cy - ry) * s, (cx + rx) * s, (cy + ry) * s]
    d.ellipse(box, fill=WHITE, outline=INK, width=max(1, int(3 * s)))
    pr = min(rx, ry) * pupil
    px = cx + look[0] * (rx - pr * 1.15)
    py = cy + look[1] * (ry - pr * 1.15)
    d.ellipse([(px - pr) * s, (py - pr) * s, (px + pr) * s, (py + pr) * s], fill=INK)
    hr = pr * 0.32
    d.ellipse([(px - pr * 0.35 - hr) * s, (py - pr * 0.4 - hr) * s, (px - pr * 0.35 + hr) * s,
               (py - pr * 0.4 + hr) * s], fill=WHITE)
    if lid > 0.02:
        yl = cy - ry + 2 * ry * c01(lid)
        pts = []
        for i in range(41):
            a = math.pi + math.pi * i / 40
            x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
            pts.append((x, y))
        # top cap of ellipse down to the lid line
        if lid < 0.5:
            pts = [(x, y) for x, y in pts if y <= yl]
        else:
            lo = []
            for i in range(41):
                a = math.pi - math.pi * i / 40
                x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
                lo.append((x, min(y, yl)))
            pts = lo + pts
        if len(pts) >= 3:
            dx = rx * math.sqrt(max(0, 1 - ((yl - cy) / ry) ** 2))
            poly = ([(cx - dx, yl)] + pts + [(cx + dx, yl)]) if lid < 0.5 else pts
            d.polygon(S(poly, s), fill=lid_col)
            d.line(S([(cx - dx, yl), (cx + dx, yl)], s), fill=INK, width=max(1, int(4 * s)))
        d.ellipse(box, outline=INK, width=max(1, int(3 * s)))


def brow(d, x0, y0, x1, y1, s, col=WHITE, w=14):
    d.line([x0 * s, y0 * s, x1 * s, y1 * s], fill=col, width=int(w * s))
    for x, y in ((x0, y0), (x1, y1)):
        r = w / 2
        d.ellipse([(x - r) * s, (y - r) * s, (x + r) * s, (y + r) * s], fill=col)


def mouth(d, cx, cy, w, kind, s, open_=0.0, col=INK, th=8):
    if kind == "smile":
        d.arc([(cx - w / 2) * s, (cy - w * 0.35) * s, (cx + w / 2) * s, (cy + w * 0.35) * s], 20, 160,
              fill=col, width=int(th * s))
    elif kind == "grin":
        d.chord([(cx - w / 2) * s, (cy - w * 0.45) * s, (cx + w / 2) * s, (cy + w * 0.45) * s], 0, 180,
                fill=col)
        d.chord([(cx - w * 0.3) * s, (cy + w * 0.12) * s, (cx + w * 0.3) * s, (cy + w * 0.42) * s], 180, 360,
                fill=(230, 90, 100))
    elif kind == "flat":
        d.line([(cx - w / 2) * s, cy * s, (cx + w / 2) * s, cy * s], fill=col, width=int(th * s))
    elif kind == "wavy":
        pts = [((cx - w / 2 + w * i / 12) * s, (cy + 6 * math.sin(i * 1.6)) * s) for i in range(13)]
        d.line(pts, fill=col, width=int(th * s), joint="curve")
    elif kind == "o":
        r = w * (0.18 + 0.12 * open_)
        d.ellipse([(cx - r * 0.8) * s, (cy - r) * s, (cx + r * 0.8) * s, (cy + r) * s], fill=col)
    elif kind == "frown":
        d.arc([(cx - w / 2) * s, (cy) * s, (cx + w / 2) * s, (cy + w * 0.6) * s], 200, 340,
              fill=col, width=int(th * s))


# expression presets: look, lid, brow (inner dy, outer dy), mouth, sweat, blush
EXPR = {
    "neutral": dict(lid=0.15, brow=(0, 0), mouth="smile", sweat=0, blush=0),
    "proud": dict(lid=0.38, brow=(-10, -22), mouth="smile", sweat=0, blush=0),
    "nervous": dict(lid=0.0, brow=(-26, 6), mouth="wavy", sweat=1, blush=0),
    "shock": dict(lid=0.0, brow=(-30, -30), mouth="o", sweat=1, blush=0),
    "stare": dict(lid=0.42, brow=(16, -6), mouth="flat", sweat=0, blush=0),
    "calm": dict(lid=0.55, brow=(-4, -4), mouth="smile", sweat=0, blush=0),
    "shy": dict(lid=0.2, brow=(-18, -4), mouth="smile", sweat=0, blush=1),
    "awkward": dict(lid=0.25, brow=(-20, 4), mouth="flat", sweat=1, blush=0),
    "happy": dict(lid=0.3, brow=(-14, -24), mouth="grin", sweat=0, blush=1),
}


def blink(t, period=3.7, phase=0.0):
    u = (t + phase) % period
    return 1.0 if u < 0.12 else 0.0


# ------------------------------------------------------------------ train (front view)
def train_front(ex, t=0.0, look=(0, 0), extra_lid=0.0, scale=1.0):
    e = EXPR[ex]
    lid = max(e["lid"], blink(t, 3.3), extra_lid)

    def fn(d, s):
        s = s * scale
        d.rounded_rectangle([20 * s, 40 * s, 540 * s, 610 * s], radius=190 * s, fill=TRAIN_W,
                            outline=TRAIN_O, width=int(5 * s))
        d.rounded_rectangle([60 * s, 540 * s, 500 * s, 630 * s], radius=36 * s, fill=TRAIN_G,
                            outline=TRAIN_O, width=int(4 * s))
        d.rounded_rectangle([70 * s, 112 * s, 490 * s, 360 * s], radius=120 * s, fill=GLASS)
        d.polygon(S([(120, 140), (190, 125), (110, 300), (90, 260)], s), fill=(52, 66, 92))
        d.rounded_rectangle([48 * s, 452 * s, 512 * s, 486 * s], radius=17 * s, fill=RED)
        for x in (95, 385):
            d.rounded_rectangle([x * s, 505 * s, (x + 80) * s, 532 * s], radius=12 * s, fill=(255, 244, 196),
                                outline=TRAIN_O, width=int(2 * s))
        lk = look
        eye(d, 190, 238, 80, 90, lk, lid, s)
        eye(d, 370, 238, 80, 90, lk, lid, s)
        bi, bo = e["brow"]
        brow(d, 130, 140 + bo, 245, 142 + bi, s)
        brow(d, 315, 142 + bi, 430, 140 + bo, s)
        mouth(d, 280, 410, 120, e["mouth"], s, open_=0.5 + 0.5 * math.sin(t * 9))
        if e["blush"]:
            for x in (130, 430):
                d.ellipse([(x - 48) * s, 392 * s, (x + 48) * s, 428 * s], fill=(255, 150, 160))
        if e["sweat"]:
            yy = 120 + (t * 90) % 60
            d.polygon(S([(520, yy - 40), (500, yy), (540, yy)], s), fill=(120, 200, 255))
            d.ellipse([500 * s, (yy - 20) * s, 540 * s, (yy + 20) * s], fill=(120, 200, 255))

    return patch(int(560 * scale), int(650 * scale), fn)


# ------------------------------------------------------------------ train (side view)
TS_H = 400


@lru_cache(maxsize=4)
def train_side_body(L=2600, sc=1.0):
    def fn(d, s):
        s = s * sc
        nose = bez((300, 30), (60, 34), (0, 300)) + [(0, 330), (40, 350), (300, 350)]
        d.rounded_rectangle([260 * s, 30 * s, L * s, 350 * s], radius=40 * s, fill=TRAIN_W,
                            outline=TRAIN_O, width=int(5 * s))
        d.polygon(S(nose, s), fill=TRAIN_W, outline=TRAIN_O)
        d.line(S(bez((300, 30), (60, 34), (0, 300)), s), fill=TRAIN_O, width=int(5 * s))
        glass = bez((285, 52), (95, 60), (38, 225)) + [(285, 225)]
        d.polygon(S(glass, s), fill=GLASS)
        d.rectangle([290 * s, 34 * s, 300 * s, 346 * s], fill=TRAIN_W)
        for x in range(380, L, 175):
            d.rounded_rectangle([x * s, 95 * s, (x + 125) * s, 175 * s], radius=20 * s, fill=GLASS)
            d.polygon(S([(x + 14, 102), (x + 44, 102), (x + 20, 168), (x + 10, 168)], 1), fill=None)
        for x in range(960, L, 1050):
            d.rounded_rectangle([x * s, 80 * s, (x + 80) * s, 335 * s], radius=10 * s, outline=TRAIN_O,
                                width=int(4 * s), fill=(236, 239, 244))
            d.rounded_rectangle([(x + 15) * s, 100 * s, (x + 65) * s, 170 * s], radius=8 * s, fill=GLASS)
        stripe = [(30, 252), (L, 252), (L, 276), (22, 276)]
        d.polygon(S(stripe, s), fill=RED)
        d.rectangle([60 * s, 318 * s, L * s, 352 * s], fill=TRAIN_G)
        for bx in range(220, L, 900):
            d.rounded_rectangle([bx * s, 340 * s, (bx + 330) * s, 385 * s], radius=14 * s, fill=(60, 66, 78))
            for wx in (bx + 70, bx + 260):
                d.ellipse([(wx - 38) * s, 340 * s, (wx + 38) * s, 398 * s], fill=(40, 44, 52))
                d.ellipse([(wx - 14) * s, 355 * s, (wx + 14) * s, 383 * s], fill=(120, 126, 138))
        d.ellipse([18 * s, 286 * s, 62 * s, 308 * s], fill=(255, 244, 196), outline=TRAIN_O)

    return patch(int(L * sc), int(TS_H * sc), fn)


def train_side(dst, x, y, ex, t, look=(0, 0), sc=1.0, extra_lid=0.0):
    """x,y = top-left of the nose. Train extends to the right off-screen."""
    body = train_side_body(2600, round(sc, 3))
    paste(dst, body, x, y, center=False)
    e = EXPR[ex]
    lid = max(e["lid"], blink(t, 3.1, 0.7), extra_lid)

    def fn(d, s):
        eye(d, 120, 140, 50, 58, look, lid, s)
        eye(d, 222, 132, 50, 58, look, lid, s)
        bi, bo = e["brow"]
        brow(d, 80, 72 + bo, 150, 70 + bi, s, w=11)
        brow(d, 190, 66 + bi, 258, 64 + bo, s, w=11)
        mouth(d, 120, 250, 70, e["mouth"] if e["mouth"] != "grin" else "smile", s, th=7)
        if e["blush"]:
            d.ellipse([40 * s, 232 * s, 90 * s, 256 * s], fill=(255, 150, 160))
        if e["sweat"]:
            yy = 40 + (t * 70) % 40
            d.ellipse([285 * s, yy * s, 310 * s, (yy + 25) * s], fill=(120, 200, 255))

    face = patch(320, 300, fn)
    paste(dst, scaled(face, sc), x, y, center=False)


# ------------------------------------------------------------------ people
def person(spec, pose, t=0.0, h=520):
    """Simple cartoon person; returns RGBA patch with feet at bottom-center. spec: dict."""
    sh = spec.get("shirt", (80, 120, 200))
    pants = spec.get("pants", (50, 56, 70))
    skin = spec.get("skin", SKIN)
    hair = spec.get("hair", (70, 50, 40))
    style = spec.get("style", "short")
    k = h / 520
    Wd = 360

    def arm(d, s, sx, sy, a1, a2, L1=95, L2=90, col=sh, w=26):
        a1r, a2r = math.radians(a1), math.radians(a1 + a2)
        ex_, ey_ = sx + math.sin(a1r) * L1, sy + math.cos(a1r) * L1
        hx, hy = ex_ + math.sin(a2r) * L2, ey_ + math.cos(a2r) * L2
        d.line([sx * s, sy * s, ex_ * s, ey_ * s], fill=col, width=int(w * s))
        d.line([ex_ * s, ey_ * s, hx * s, hy * s], fill=col, width=int(w * s))
        for (x, y) in ((sx, sy), (ex_, ey_)):
            d.ellipse([(x - w / 2) * s, (y - w / 2) * s, (x + w / 2) * s, (y + w / 2) * s], fill=col)
        d.ellipse([(hx - 15) * s, (hy - 15) * s, (hx + 15) * s, (hy + 15) * s], fill=skin)
        return hx, hy

    def fn(d, s):
        s = s * k
        cx = Wd / 2
        # legs
        for dx in (-26, 26):
            d.line([(cx + dx) * s, 330 * s, (cx + dx * 1.2) * s, 505 * s], fill=pants, width=int(34 * s))
            d.ellipse([(cx + dx * 1.2 - 26) * s, 492 * s, (cx + dx * 1.2 + 26) * s, 520 * s], fill=INK)
        # body
        if style == "long" and spec.get("dress"):
            d.polygon(S([(cx - 60, 190), (cx + 60, 190), (cx + 95, 400), (cx - 95, 400)], s), fill=sh)
        d.rounded_rectangle([(cx - 66) * s, 180 * s, (cx + 66) * s, 350 * s], radius=46 * s, fill=sh)
        if spec.get("tie"):
            d.polygon(S([(cx - 10, 190), (cx + 10, 190), (cx + 14, 290), (cx, 310), (cx - 14, 290)], s),
                      fill=spec["tie"])
        hands = {}
        la, ra = pose.get("l", (20, 0)), pose.get("r", (-20, 0))
        hands["l"] = arm(d, s, cx + 56, 205, la[0], la[1])
        hands["r"] = arm(d, s, cx - 56, 205, ra[0], ra[1])
        # head
        tilt = pose.get("tilt", 0)
        hx, hy = cx + tilt, 118
        if style == "long":
            d.rounded_rectangle([(hx - 80) * s, (hy - 75) * s, (hx + 80) * s, (hy + 95) * s], radius=60 * s,
                                fill=hair)
        d.ellipse([(hx - 70) * s, (hy - 75) * s, (hx + 70) * s, (hy + 72) * s], fill=skin)
        if style in ("short", "long", "kid"):
            d.chord([(hx - 74) * s, (hy - 82) * s, (hx + 74) * s, (hy + 40) * s], 180, 360, fill=hair)
        if style == "bald":
            d.chord([(hx - 74) * s, (hy - 40) * s, (hx + 74) * s, (hy + 40) * s], 160, 200, fill=hair)
            d.chord([(hx - 74) * s, (hy - 40) * s, (hx + 74) * s, (hy + 40) * s], 340, 380, fill=hair)
        lk = pose.get("look", (0, 0))
        el = max(pose.get("lid", 0.0), blink(t, 4.1, spec.get("ph", 0)))
        for ex_ in (-28, 28):
            if el > 0.5:
                d.line([(hx + ex_ - 12) * s, (hy + 6) * s, (hx + ex_ + 12) * s, (hy + 6) * s], fill=INK,
                       width=int(5 * s))
            else:
                r = pose.get("eye", 9)
                d.ellipse([(hx + ex_ + lk[0] * 5 - r) * s, (hy + lk[1] * 4 - r + 4) * s,
                           (hx + ex_ + lk[0] * 5 + r) * s, (hy + lk[1] * 4 + r + 4) * s], fill=INK)
        if spec.get("glasses"):
            for ex_ in (-28, 28):
                d.ellipse([(hx + ex_ - 22) * s, (hy - 16) * s, (hx + ex_ + 22) * s, (hy + 26) * s], outline=INK,
                          width=int(5 * s))
            d.line([(hx - 6) * s, (hy + 2) * s, (hx + 6) * s, (hy + 2) * s], fill=INK, width=int(5 * s))
        mouth(d, hx, hy + 40, 40, pose.get("mouth", "smile"), s, open_=0.5 + 0.5 * math.sin(t * 12), th=6)
        if pose.get("hold") == "coffee":
            x, y = hands["r"]
            cup(d, x, y - 10, s)
        if pose.get("hold") == "phone":
            x, y = hands["l"]
            d.rounded_rectangle([(x - 20) * s, (y - 46) * s, (x + 18) * s, (y + 22) * s], radius=8 * s, fill=INK)

    return patch(Wd * k, 540 * k, fn)


def cup(d, x, y, s, ang=0):
    pts = [(-24, -36), (24, -36), (18, 34), (-18, 34)]
    ca, sa = math.cos(ang), math.sin(ang)
    rot = [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts]
    d.polygon(S(rot, s), fill=(250, 250, 245), outline=INK)
    lid = [(-28, -44), (28, -44), (26, -34), (-26, -34)]
    d.polygon(S([(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in lid], s), fill=(120, 80, 50))
    band = [(-22, -10), (22, -10), (20, 10), (-20, 10)]
    d.polygon(S([(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in band], s), fill=(180, 130, 90))


# ------------------------------------------------------------------ cow
def cow_face(t, look=(0, 0), lid=0.3, chew=0.0, scale=1.0, extra_lid=0.0):
    def fn(d, s):
        s *= scale
        # horns + ears
        for sgn in (-1, 1):
            cx = 300 + sgn * 150
            d.polygon(S([(cx, 120), (cx + sgn * 70, 40), (cx + sgn * 40, 140)], s), fill=(240, 228, 200),
                      outline=INK)
            d.ellipse([(300 + sgn * 230 - 70) * s, 170 * s, (300 + sgn * 230 + 70) * s, 230 * s],
                      fill=(240, 240, 240), outline=INK, width=int(3 * s))
        d.rounded_rectangle([140 * s, 100 * s, 460 * s, 520 * s], radius=150 * s, fill=(250, 250, 250),
                            outline=INK, width=int(4 * s))
        d.ellipse([150 * s, 120 * s, 290 * s, 260 * s], fill=INK)
        d.ellipse([360 * s, 300 * s, 450 * s, 400 * s], fill=INK)
        d.chord([140 * s, 90 * s, 460 * s, 180 * s], 180, 360, fill=INK)
        ll = max(lid, blink(t, 4.6, 1.3), extra_lid)
        eye(d, 235, 265, 50, 52, look, ll, s, lid_col=(250, 250, 250))
        eye(d, 365, 265, 50, 52, look, ll, s, lid_col=(250, 250, 250))
        jaw = 8 * math.sin(chew * 2 * math.pi)
        d.rounded_rectangle([170 * s, (380 + jaw * 0.3) * s, 430 * s, (540 + jaw) * s], radius=80 * s,
                            fill=(250, 175, 185), outline=INK, width=int(4 * s))
        for x in (245, 355):
            d.ellipse([(x - 20) * s, (440 + jaw * 0.5) * s, (x + 20) * s, (470 + jaw * 0.5) * s],
                      fill=(150, 70, 90))

    return patch(int(600 * scale), int(560 * scale), fn)


def cow_side(t, lying=False, look=(0, 0), chew=0.0):
    def fn(d, s):
        by = 60 if lying else 0
        if not lying:
            for x in (120, 165, 330, 375):
                d.rounded_rectangle([(x - 16) * s, 230 * s, (x + 16) * s, 330 * s], radius=10 * s,
                                    fill=(250, 250, 250), outline=INK, width=int(3 * s))
                d.rectangle([(x - 16) * s, 318 * s, (x + 16) * s, 332 * s], fill=INK)
        else:
            for x in (130, 330):
                d.ellipse([(x - 40) * s, 300 * s, (x + 50) * s, 335 * s], fill=(250, 250, 250), outline=INK,
                          width=int(3 * s))
        d.rounded_rectangle([90 * s, (110 + by) * s, 420 * s, (260 + by) * s], radius=70 * s, fill=(250, 250, 250),
                            outline=INK, width=int(4 * s))
        d.ellipse([170 * s, (115 + by) * s, 260 * s, (190 + by) * s], fill=INK)
        d.ellipse([310 * s, (170 + by) * s, 380 * s, (240 + by) * s], fill=INK)
        d.line([418 * s, (140 + by) * s, 450 * s, (230 + by + 8 * math.sin(t * 5)) * s], fill=INK, width=int(6 * s))
        # head (facing left / camera)
        jaw = 5 * math.sin(chew * 2 * math.pi)
        hx, hy = 70, 120 + by
        for sgn in (-1, 1):
            d.polygon(S([(hx + sgn * 40, hy - 50), (hx + sgn * 72, hy - 92), (hx + sgn * 58, hy - 40)], s),
                      fill=(240, 228, 200), outline=INK)
        d.rounded_rectangle([(hx - 62) * s, (hy - 60) * s, (hx + 62) * s, (hy + 90) * s], radius=55 * s,
                            fill=(250, 250, 250), outline=INK, width=int(4 * s))
        d.rounded_rectangle([(hx - 54) * s, (hy + 30 + jaw * 0.3) * s, (hx + 54) * s, (hy + 100 + jaw) * s],
                            radius=34 * s, fill=(250, 175, 185), outline=INK, width=int(3 * s))
        ll = max(0.35 if lying else 0.15, blink(t, 4.0, 0.4))
        eye(d, hx - 24, hy - 4, 20, 22, look, ll, s, lid_col=(250, 250, 250))
        eye(d, hx + 24, hy - 4, 20, 22, look, ll, s, lid_col=(250, 250, 250))

    return patch(480, 360, fn)


# ------------------------------------------------------------------ backgrounds
def vgrad(w, h, top, bot):
    a = np.linspace(0, 1, h)[:, None, None]
    arr = (np.array(top)[None, None, :] * (1 - a) + np.array(bot)[None, None, :] * a)
    arr = np.repeat(arr, w, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


RAIL_Y = 1215          # top of rails (train wheels stand here)


def bg_platform(kassel=False):
    im = vgrad(W, H, (150, 205, 245), (225, 240, 252))
    d = ImageDraw.Draw(im)
    # skyline
    rng = np.random.default_rng(5)
    x = -20
    while x < W:
        bw, bh = int(rng.integers(70, 160)), int(rng.integers(120, 360))
        d.rectangle([x, 1020 - bh, x + bw, 1100], fill=(178, 200, 222))
        for wy in range(1040 - bh, 1080, 40):
            for wx in range(x + 14, x + bw - 14, 30):
                d.rectangle([wx, wy, wx + 12, wy + 18], fill=(196, 216, 236))
        x += bw + int(rng.integers(5, 30))
    d.rectangle([0, 1000, W, 1230], fill=(160, 168, 178))
    # canopy posts + roof
    d.rectangle([0, 450, W, 492], fill=(90, 100, 116))
    d.polygon([(0, 492), (W, 492), (W, 520), (0, 540)], fill=(110, 120, 136))
    # track bed
    d.rectangle([0, 1210, W, 1290], fill=(120, 108, 98))
    for xx in range(-10, W, 48):
        d.rectangle([xx, 1236, xx + 26, 1290], fill=(96, 80, 66))
    d.rectangle([0, 1222, W, 1232], fill=(150, 156, 166))
    d.rectangle([0, 1262, W, 1272], fill=(150, 156, 166))
    # platform
    d.rectangle([0, 1290, W, H], fill=(196, 199, 205))
    d.rectangle([0, 1290, W, 1306], fill=(240, 240, 240))
    for xx in range(0, W, 26):
        d.rectangle([xx, 1316, xx + 14, 1330], fill=(245, 245, 245))
    for yy in range(1380, H, 110):
        d.line([0, yy, W, yy], fill=(186, 189, 196), width=3)
    return im


def bg_country():
    im = vgrad(W, H, (110, 190, 245), (210, 236, 252))
    d = ImageDraw.Draw(im)
    d.ellipse([-300, 860, 700, 1400], fill=(120, 190, 110))
    d.ellipse([400, 900, 1500, 1400], fill=(100, 176, 96))
    d.rectangle([0, 1100, W, H], fill=(128, 196, 112))
    for x in (120, 860, 990):
        d.rectangle([x - 8, 1000, x + 8, 1080], fill=(110, 80, 50))
        d.ellipse([x - 55, 900, x + 55, 1030], fill=(70, 150, 80))
    d.rectangle([0, 1210, W, 1290], fill=(150, 136, 120))
    for xx in range(-10, W, 48):
        d.rectangle([xx, 1236, xx + 26, 1290], fill=(110, 92, 74))
    d.rectangle([0, 1222, W, 1232], fill=(150, 156, 166))
    d.rectangle([0, 1262, W, 1272], fill=(150, 156, 166))
    for x in range(0, W, 40):
        d.line([x, 1300 + (x * 7) % 23, x + 8, 1290 + (x * 7) % 23], fill=(90, 160, 80), width=4)
    # km sign
    d.rectangle([905, 1060, 917, 1215], fill=(90, 90, 90))
    d.rounded_rectangle([840, 1010, 985, 1080], radius=8, fill=WHITE, outline=INK, width=4)
    text_center(d, 912, 1022, "Fulda 3", font(F_BODY_X, 32), INK)
    return im


def bg_news_room():
    im = vgrad(W, H, (52, 44, 60), (30, 26, 36))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 1380, W, H], fill=(70, 52, 44))
    d.polygon([(0, 1380), (W, 1380), (W, 1400), (0, 1400)], fill=(90, 68, 56))
    return im


# ------------------------------------------------------------------ departure board
DEST = "München Hbf"


def board_state(t):
    k = scene_at(t)
    if k == "hook":
        return dict(time="06:12", delay="+0", dcol=GREEN, blink=True,
                    ticker="+++ ACHTUNG: Dieser Zug ist pünktlich +++ Bitte bewahren Sie Ruhe +++")
    if k == "einfahrt":
        return dict(time="06:12", delay="+0", dcol=GREEN, blink=False,
                    ticker="Planmäßige Einfahrt. Wir bitten um Ihr Verständnis.")
    if k in ("bahnsteig", "news"):
        return dict(time="06:12", delay="+0", dcol=GREEN, blink=True,
                    ticker="+++ Grund für die Pünktlichkeit: unbekannt +++ Behörden ermitteln +++")
    if k in ("kassel", "kind", "papa"):
        return dict(time="07:41", delay="+0", dcol=GREEN, blink=True,
                    ticker="Kassel-Wilhelmshöhe: pünktlich. Schon wieder. +++ Bitte nicht in Panik verfallen +++")
    if k == "kuh":
        return dict(time="08:19", delay="?", dcol=YEL, blink=True,
                    ticker="Verzögerung wegen Tier im Gleis. Wir danken für Ihr Verständnis.")
    if k == "warten":
        u = eio((t - (SEG["warten"][0] + 0.3)) / (SEG["warten"][1] - SEG["warten"][0] - 0.6))
        return dict(time="08:19", delay=f"+{int(round(70 * u))}", dcol=RED, blink=False,
                    ticker="Verzögerung ca. 70 Minuten. Vielen Dank, dass Sie mit uns warten.")
    return dict(time="08:19", delay="+70", dcol=RED, blink=True,
                ticker="+++ Alles wieder normal +++ Wir wünschen eine gute Fahrt +++")


def draw_board(frame, t, y=70, punch=1.0):
    st = board_state(t)
    bw, bh = 980, 330

    def fn(d, s):
        d.rounded_rectangle([0, 0, bw * s, bh * s], radius=26 * s, fill=BOARD_D)
        d.rounded_rectangle([8 * s, 8 * s, (bw - 8) * s, (bh - 8) * s], radius=20 * s, fill=BOARD)
        d.text((38 * s, 30 * s), st["time"], font=font(F_BODY_X, int(74 * s)), fill=WHITE)
        d.rounded_rectangle([300 * s, 44 * s, 492 * s, 104 * s], radius=10 * s, fill=WHITE)
        d.text((318 * s, 50 * s), "ICE 572", font=font(F_BODY_X, int(42 * s)), fill=BOARD)
        d.text((38 * s, 128 * s), DEST, font=font(F_BODY_X, int(70 * s)), fill=WHITE)
        d.text((40 * s, 214 * s), "über Kassel-Wilhelmshöhe · Fulda", font=font(F_BODY, int(30 * s)),
               fill=(190, 210, 240))
        on = not st["blink"] or (t * 2.4) % 1 < 0.7
        dx = bw - 250
        d.rounded_rectangle([dx * s, 34 * s, (bw - 34) * s, 190 * s], radius=16 * s, fill=BOARD_D)
        if on:
            f = font(F_HEAD, int(76 * s))
            txt = st["delay"]
            tw = d.textlength(txt, font=f)
            d.text(((dx + 108) * s - tw / 2, 54 * s), txt, font=f, fill=st["dcol"])
            text_center(d, (dx + 108) * s, 150 * s, "MIN", font(F_BODY_X, int(28 * s)), st["dcol"])
        # ticker strip
        d.rectangle([8 * s, 262 * s, (bw - 8) * s, (bh - 8) * s], fill=WHITE)
        d.rounded_rectangle([8 * s, 262 * s, (bw - 8) * s, (bh - 8) * s], radius=20 * s, fill=WHITE)
        d.rectangle([8 * s, 262 * s, (bw - 8) * s, 290 * s], fill=WHITE)
        f2 = font(F_BODY_X, int(36 * s))
        txt = st["ticker"] + "      "
        tw = d.textlength(txt, font=f2)
        off = (t * 170 * s) % tw
        x = 20 * s - off
        while x < bw * s:
            d.text((x, 270 * s), txt, font=f2, fill=BOARD)
            x += tw

    im = patch(bw, bh, fn)
    im = shadowed(im, dy=10, blur=12, a=0.35)
    paste(frame, scaled(im, punch), W // 2, y + bh // 2 + 6, center=True)


# ------------------------------------------------------------------ captions
def build_caps():
    caps = []
    for k in KEYS:
        if k in ("hook", "kind", "papa"):
            continue
        ws = [w for w in WORDS if w["key"] == k]
        src = next(sc["text"] for sc in SCENES if sc["key"] == k)
        pos = 0
        for w in ws:  # recover punctuation from the script text
            j = src.find(w["text"], pos)
            if j >= 0:
                pos = j + len(w["text"])
                w["punct"] = src[pos:pos + 1] if src[pos:pos + 1] in ".,:!?…" else ""
                if w["punct"] == ":":
                    w["text"] += ":"
        cur = []
        for i, w in enumerate(ws):
            cur.append(w)
            txt = " ".join(x["text"] for x in cur)
            end_punct = bool(w.get("punct"))
            nxt = ws[i + 1]["text"] if i + 1 < len(ws) else ""
            if end_punct or len(cur) >= 3 or len(txt + " " + nxt) > 17 or i == len(ws) - 1:
                caps.append(cur)
                cur = []
    out = []
    for i, c in enumerate(caps):
        s = c[0]["s"] - 0.05
        e = c[-1]["e"] + 0.35
        if i + 1 < len(caps):
            e = min(e, caps[i + 1][0]["s"] - 0.05)
        out.append((s, e, c))
    return out


CAPS = []


@lru_cache(maxsize=256)
def cap_img(ci, active):
    s, e, ws = CAPS[ci]
    f = font(F_HEAD, 74)
    txts = [w["text"].upper() for w in ws]
    sp = f.getlength(" ")
    wid = sum(f.getlength(x) for x in txts) + sp * (len(txts) - 1)
    if wid > 960:
        f = font(F_HEAD, int(74 * 960 / wid))
        sp = f.getlength(" ")
        wid = sum(f.getlength(x) for x in txts) + sp * (len(txts) - 1)
    im = Image.new("RGBA", (int(wid) + 40, 130), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 20
    for i, tx in enumerate(txts):
        col = YEL if i == active else WHITE
        d.text((x, 20), tx, font=f, fill=col, stroke_width=9, stroke_fill=INK)
        x += f.getlength(tx) + sp
    return im


def draw_caption(frame, t, y=1560):
    for ci, (s, e, ws) in enumerate(CAPS):
        if s <= t < e:
            act = max([i for i, w in enumerate(ws) if w["s"] - 0.05 <= t] or [0])
            im = cap_img(ci, act)
            pop = 0.86 + 0.14 * eback((t - s) / 0.16)
            paste(frame, scaled(im, pop), W // 2, y, center=True)
            return


# ------------------------------------------------------------------ bubbles, stamps
def bubble(text, w=760, hand=True, col=WHITE, tcol=INK, tail="down", fsize=64):
    f = font(F_HAND if hand else F_HEAD_B, fsize)
    words = text.split()
    lines, cur = [], ""
    for wd in words:
        if f.getlength((cur + " " + wd).strip()) > w - 80:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    lines.append(cur)
    lh = int(fsize * 1.12)
    bh = lh * len(lines) + 60
    bw = int(max(f.getlength(l) for l in lines) + 90)

    def fn(d, s):
        d.rounded_rectangle([4 * s, 4 * s, (bw - 4) * s, (bh - 4) * s], radius=44 * s, fill=col, outline=INK,
                            width=int(6 * s))
        if tail == "down":
            d.polygon(S([(bw * 0.3, bh - 8), (bw * 0.3 + 60, bh - 8), (bw * 0.22, bh + 50)], s), fill=col,
                      outline=INK)
            d.line([bw * 0.3 * s + 6 * s, (bh - 7) * s, (bw * 0.3 + 54) * s, (bh - 7) * s], fill=col,
                   width=int(8 * s))
        for i, l in enumerate(lines):
            text_center(d, bw / 2 * s, (28 + i * lh) * s, l, font(f.path, int(fsize * s)), tcol)

    return patch(bw, bh + 60, fn)


def stamp(text, col=GREEN, size=66, rot=-8):
    f = font(F_HEAD, size)
    tw = f.getlength(text)
    w, h = int(tw + 70), int(size * 1.7)

    def fn(d, s):
        d.rounded_rectangle([4 * s, 4 * s, (w - 4) * s, (h - 4) * s], radius=18 * s, outline=col,
                            width=int(9 * s), fill=(255, 255, 255, 235))
        d.text((35 * s, (h - size * 1.25) / 2 * s), text, font=font(F_HEAD, int(size * s)), fill=col)

    return patch(w, h, fn).rotate(rot, expand=True, resample=Image.BICUBIC)


def station_clock(hh, mm, sec, r=130):
    def fn(d, s):
        d.ellipse([0, 0, 2 * r * s, 2 * r * s], fill=WHITE, outline=INK, width=int(12 * s))
        c = r * s
        for i in range(60):
            a = math.radians(i * 6)
            r0 = r * (0.78 if i % 5 == 0 else 0.86)
            d.line([c + math.sin(a) * r0 * s, c - math.cos(a) * r0 * s, c + math.sin(a) * r * 0.92 * s,
                    c - math.cos(a) * r * 0.92 * s], fill=INK, width=int((9 if i % 5 == 0 else 3) * s))

        def hand(ang, L, wd, col):
            a = math.radians(ang)
            d.line([c - math.sin(a) * L * 0.18 * s, c + math.cos(a) * L * 0.18 * s, c + math.sin(a) * L * s,
                    c - math.cos(a) * L * s], fill=col, width=int(wd * s))

        hand((hh % 12 + mm / 60) * 30, r * 0.52, 16, INK)
        hand((mm + sec / 60) * 6, r * 0.8, 11, INK)
        hand(sec * 6, r * 0.82, 5, RED)
        d.ellipse([c - 9 * s, c - 9 * s, c + 9 * s, c + 9 * s], fill=INK)

    return patch(2 * r + 4, 2 * r + 4, fn)


def headline(lines, f=F_HEAD, size=82, cols=None):
    fo = font(f, size)
    lh = int(size * 1.22)
    wid = int(max(fo.getlength(l) for l in lines)) + 40
    im = Image.new("RGBA", (wid, lh * len(lines) + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        col = (cols or [WHITE] * len(lines))[i]
        w = fo.getlength(l)
        d.text(((wid - w) / 2, 10 + i * lh), l, font=fo, fill=col, stroke_width=10, stroke_fill=INK)
    return im


def phone_hand(t, rec=True, sc=1.0):
    def fn(d, s):
        s *= sc
        d.rounded_rectangle([60 * s, 250 * s, 190 * s, 520 * s], radius=40 * s, fill=SKIN2 if False else SKIN)
        d.rounded_rectangle([20 * s, 0, 230 * s, 360 * s], radius=26 * s, fill=INK)
        d.rounded_rectangle([32 * s, 14 * s, 218 * s, 346 * s], radius=18 * s, fill=(150, 205, 245))
        d.rectangle([32 * s, 220 * s, 218 * s, 346 * s], fill=(196, 199, 205))
        d.rounded_rectangle([60 * s, 150 * s, 218 * s, 225 * s], radius=10 * s, fill=TRAIN_W)
        d.rectangle([60 * s, 196 * s, 218 * s, 204 * s], fill=RED)
        if rec and (t * 2) % 1 < 0.6:
            d.ellipse([46 * s, 30 * s, 72 * s, 56 * s], fill=RED)
        for fx in (40, 150):
            d.ellipse([(fx - 10) * s, 260 * s, (fx + 40) * s, 300 * s], fill=SKIN)

    return patch(int(250 * sc), int(520 * sc), fn)


def flash(frame, x, y, a):
    if a <= 0.02:
        return
    r = int(140 * (0.6 + a))
    im = Image.new("RGBA", (r * 2, r * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([r * 0.4, r * 0.4, r * 1.6, r * 1.6], fill=(255, 255, 255, int(255 * a)))
    for k in range(8):
        ang = k * math.pi / 4
        d.line([r, r, r + math.cos(ang) * r, r + math.sin(ang) * r], fill=(255, 255, 230, int(220 * a)), width=8)
    im = im.filter(ImageFilter.GaussianBlur(4))
    paste(frame, im, x, y)


# ================================================================== scenes
BG = {}


def init():
    global CAPS
    if BG:
        return
    BG["platform"] = bg_platform()
    BG["country"] = bg_country()
    BG["news"] = bg_news_room()
    CAPS = build_caps()


def train_y(sc=1.0):
    return RAIL_Y - int(385 * sc)


def sc_hook(fr, t, ts, te):
    u = t - ts
    fr.alpha_composite(BG["platform"])
    dark = Image.new("RGBA", (W, H), (60, 0, 10, 140))
    fr.alpha_composite(dark)
    # rotating alarm light glow
    pan = at("hook", "Panik")
    a = 0.5 + 0.5 * math.sin(u * 10)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for cx in (0, W):
        gd.ellipse([cx - 420, 300 - 420, cx + 420, 300 + 420], fill=(255, 30, 30, int(120 * a)))
    fr.alpha_composite(glow.filter(ImageFilter.GaussianBlur(60)))
    expr = "proud" if t < pan - 0.2 else "shock"
    look = (math.sin(u * 7) * 0.8, 0.2) if t >= pan - 0.2 else (0, 0)
    tf = train_front(expr, t, look=look)
    zoom = 1.18 + 0.08 * eo(u / 4)
    paste(fr, scaled(tf, zoom), W // 2, 960 + 30 * (1 - eo(u / 0.4)))
    # headline
    l1 = headline(["HEUTE WAR ICH", "PÜNKTLICH."], size=84, cols=[WHITE, GREEN])
    pop = eback(u / 0.25)
    paste(fr, scaled(l1, 0.6 + 0.4 * pop), W // 2, 1450)
    if t >= pan - 0.45:
        v = t - (pan - 0.45)
        l2 = headline(["DEUTSCHLAND", "IST IN PANIK."], size=84, cols=[WHITE, (255, 70, 70)])
        paste(fr, scaled(l2, 0.6 + 0.4 * eback(v / 0.22)), W // 2, 1690)


def sc_einfahrt(fr, t, ts, te):
    u = t - ts
    fr.alpha_composite(BG["platform"])
    t12 = at("einfahrt", "6 Uhr 12")
    tmin = at("einfahrt", "Minute")
    # clock: second hand sweeps to 12 exactly at "12"
    sec = 60 - max(0.0, (t12 + 0.25 - t)) * 6 if t < t12 + 0.25 else 0
    mm = 11 if t < t12 + 0.25 else 12
    clk = station_clock(6, mm, sec % 60, r=150)
    paste(fr, shadowed(clk), 250, 760)
    # train slides in from the right, stops at x=40 exactly at "Minute"
    tin = at("einfahrt", "fahre") - 0.3
    p = eo((t - tin) / (tmin + 0.15 - tin))
    x = lerp(W + 50, 40, p)
    ex = "proud" if p > 0.99 else "neutral"
    train_side(fr, x, train_y(), ex, t, look=(-0.6, 0) if p < 0.99 else (0.5, 0.3))
    if p < 0.99 and t > tin:
        sp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sp)
        for i in range(6):
            yy = 900 + i * 55
            sd.line([x + 380 + i * 60, yy, x + 700 + i * 60, yy], fill=(255, 255, 255, 160), width=6)
        fr.alpha_composite(sp)
    if t >= tmin + 0.1:
        v = t - (tmin + 0.1)
        st = stamp("AUF DIE MINUTE ✓" if False else "AUF DIE MINUTE", GREEN, 60)
        paste(fr, scaled(st, 1.6 - 0.6 * eo(v / 0.18)), 690, 720, alpha=c01(v / 0.1))


def platform_with_train(fr, t, ex, look, x=40):
    fr.alpha_composite(BG["platform"])
    train_side(fr, x, train_y(), ex, t, look=look)


WOMAN = dict(shirt=(230, 120, 60), pants=(60, 64, 90), hair=(120, 70, 40), style="long", ph=0.6)
MAN = dict(shirt=(80, 130, 200), pants=(50, 50, 60), hair=(50, 40, 30), style="bald", ph=1.7)
MAN2 = dict(shirt=(120, 170, 90), pants=(70, 60, 50), hair=(200, 170, 90), style="short", ph=2.4)
DAD = dict(shirt=(70, 90, 120), pants=(40, 44, 56), hair=(90, 60, 40), style="short", glasses=True, ph=0.3)
KID = dict(shirt=(250, 200, 40), pants=(70, 110, 190), hair=(180, 120, 60), style="kid", ph=1.1)


def sc_bahnsteig(fr, t, ts, te):
    u = t - ts
    t_still = at("bahnsteig", "Stille")
    t_frau = at("bahnsteig", "Frau")
    t_fall = at("bahnsteig", "fallen")
    t_mann = at("bahnsteig", "Mann")
    t_mut = at("bahnsteig", "Mutter")
    platform_with_train(fr, t, "proud" if t < t_fall else "awkward", (0.6, 0.5))
    shock = t > t_still
    still_mode = t_still < t < t_frau
    if still_mode:
        gray = Image.new("RGBA", (W, H), (20, 25, 40, 70))
        fr.alpha_composite(gray)
    # woman with coffee (left), man (right), bystander (center)
    pw = dict(r=(-20, -110) if t < t_fall else (-60, -20), l=(15, 0), hold="coffee" if t < t_fall else None,
              mouth="o" if shock else "smile", look=(-0.5, -0.3), eye=12 if shock else 9)
    paste(fr, person(WOMAN, pw, t), 430, 1520 - 270, center=True)
    pm2 = dict(r=(-30, 0), l=(30, 0), mouth="o" if shock else "flat", look=(-0.8, -0.3), eye=12 if shock else 9)
    paste(fr, person(MAN2, pm2, t, h=470), 660, 1520 - 245, center=True)
    phone = t >= t_mut - 0.4
    pm = dict(r=(-25, 0), l=(150, 175) if phone else (25, 0), hold="phone" if phone else None,
              mouth="wavy" if phone else ("o" if shock else "flat"), look=(-0.8, -0.3), tilt=-10 if phone else 0,
              eye=12 if shock and not phone else 9, lid=0.5 if phone else 0)
    paste(fr, person(MAN, pm, t), 900, 1520 - 270, center=True)
    # falling cup
    if t >= t_fall:
        v = t - t_fall
        if v < 0.45:
            cl = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
            cup(ImageDraw.Draw(cl), 100, 100, 1, ang=v * 9)
            paste(fr, cl, 360 - v * 40, 1180 + 900 * v * v)
        else:
            sp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            sd = ImageDraw.Draw(sp)
            g = eo((v - 0.45) / 0.25)
            sd.ellipse([350 - 110 * g, 1500 - 18 * g, 350 + 110 * g, 1500 + 22 * g], fill=(120, 75, 40))
            for k in range(7):
                ang = math.pi + k * math.pi / 6
                rr_ = 60 + 90 * g
                sd.ellipse([350 + math.cos(ang) * rr_ - 9, 1500 + math.sin(ang) * rr_ * 0.6 - 9,
                            350 + math.cos(ang) * rr_ + 9, 1500 + math.sin(ang) * rr_ * 0.6 + 9],
                           fill=(120, 75, 40, int(255 * (1 - c01((v - 0.6) / 0.6)))))
            fr.alpha_composite(sp)
            cl = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
            cup(ImageDraw.Draw(cl), 100, 100, 1, ang=1.57)
            paste(fr, cl, 440, 1480)
    if still_mode:
        b = bubble("…", w=300, fsize=110)
        paste(fr, b, 540, 820, alpha=c01((t - t_still) / 0.15))
    if t >= t_mut - 0.2:
        b = bubble("Mama … ich hab dich lieb. Es ist so weit.", w=600, fsize=58)
        paste(fr, b, 720, 770, alpha=c01((t - t_mut + 0.2) / 0.15))


def sc_news(fr, t, ts, te):
    u = t - ts
    fr.alpha_composite(BG["news"])
    t_exp = at("news", "Experten")
    tvw, tvh = 980, 700
    tv = Image.new("RGBA", (tvw, tvh), (0, 0, 0, 0))
    d = ImageDraw.Draw(tv)
    d.rounded_rectangle([0, 0, tvw, tvh], radius=30, fill=(20, 20, 24))
    scr = vgrad(tvw - 60, tvh - 60, (30, 70, 150), (12, 30, 80))
    sd = ImageDraw.Draw(scr)
    for i in range(0, tvw, 60):
        sd.line([i, 0, i - 200, tvh], fill=(40, 85, 170), width=2)
    if t < t_exp:
        # live picture of the punctual train
        mini = Image.new("RGBA", scr.size, (0, 0, 0, 0))
        train_side(mini, 90, 120, "proud", t, look=(-0.5, 0.2), sc=0.62)
        scr.alpha_composite(mini)
        sd.rectangle([0, 390, scr.width, 410], fill=(150, 160, 170))
        sd.rounded_rectangle([30, 30, 190, 80], radius=8, fill=RED)
        sd.text((52, 36), "LIVE", font=font(F_BODY_X, 36), fill=WHITE)
    else:
        ex = person(dict(shirt=(60, 60, 70), tie=RED, hair=(200, 200, 200), style="bald", glasses=True, ph=0.2),
                    dict(r=(-160, -60), l=(10, 0), mouth="o" if (t * 3) % 1 < 0.5 else "flat",
                         look=(0, 0)), t, h=760)
        scr.alpha_composite(ex.crop((0, 0, ex.width, min(ex.height, scr.height - 40))), (300, 40))
        # chart
        sd.rounded_rectangle([40, 70, 300, 330], radius=14, fill=WHITE)
        pts = [(60, 300), (100, 290), (140, 296), (180, 292), (220, 298), (250, 120), (280, 90)]
        sd.line(pts, fill=RED, width=7, joint="curve")
        sd.text((58, 82), "Pünktlichkeit", font=font(F_BODY_X, 26), fill=INK)
        sd.text((240, 130), "?!", font=font(F_HEAD, 40), fill=RED)
    # breaking banner + lower third
    sd.rectangle([0, 450, scr.width, 520], fill=RED)
    sd.text((24, 458), "EILMELDUNG", font=font(F_HEAD, 46), fill=WHITE)
    sd.rectangle([0, 520, scr.width, 580], fill=WHITE)
    lt = "ICE 572 KOMMT PÜNKTLICH AN" if t < t_exp else "Prof. Dr. Gleis: „Ein Systemfehler.“"
    sd.text((24, 530), lt, font=font(F_BODY_X, 38), fill=INK)
    sd.rectangle([0, 580, scr.width, 640], fill=(10, 20, 40))
    tick = "+++ Bahnsteig in Schockstarre +++ Kaffeeumsatz bricht ein +++ Krisenstab tagt +++ "
    f = font(F_BODY_X, 32)
    tw = f.getlength(tick)
    x = -((t * 200) % tw)
    while x < scr.width:
        sd.text((x, 592), tick, font=f, fill=YEL)
        x += tw
    tv.alpha_composite(scr, (30, 30))
    zoom = 1.0 + 0.05 * eio(u / (te - ts))
    paste(fr, shadowed(scaled(tv, zoom), dy=20, blur=30, a=0.6), W // 2, 920)
    # interrupting "jingle" flash
    if u < 0.25:
        fr.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(200 * (1 - u / 0.25)))))


def sc_kassel(fr, t, ts, te):
    u = t - ts
    t_film = at("kassel", "Leute")
    platform_with_train(fr, t, "shy" if t > t_film else "proud", (0.6, 0.6))
    # station sign
    sg = Image.new("RGBA", (760, 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(sg)
    d.rounded_rectangle([0, 0, 760, 120], radius=14, fill=BOARD, outline=WHITE, width=6)
    text_center(d, 380, 26, "Kassel-Wilhelmshöhe", font(F_BODY_X, 60), WHITE)
    for x in (180, 900):
        ImageDraw.Draw(fr).rectangle([x - 8, 470, x + 8, 590], fill=(90, 100, 116))
    paste(fr, shadowed(sg), W // 2, 640)
    if t > t_film - 0.2:
        v = t - (t_film - 0.2)
        for i, (px, delay, rot) in enumerate([(170, 0.0, 8), (420, 0.12, -4), (680, 0.06, 5), (930, 0.2, -9)]):
            p = eo((v - delay) / 0.35)
            ph = phone_hand(t + i * 0.3, sc=1.0).rotate(rot, expand=True, resample=Image.BICUBIC)
            paste(fr, ph, px, lerp(2100, 1560 + (i % 2) * 70, p))
        for i, (fx, fy, ft) in enumerate([(300, 900, 0.3), (780, 980, 0.6), (520, 860, 0.95), (880, 820, 1.3)]):
            flash(fr, fx, fy, 1 - c01((v - ft) / 0.15) if v >= ft else 0)


def sc_kind(fr, t, ts, te, papa=False):
    t0 = SEG["kind"][0]
    u = t - t0
    platform_with_train(fr, t, "awkward" if papa else "neutral", (0.4, 0.7) if papa else (0.7, 0.7))
    # camera push towards the family
    kid_pose = dict(r=(-150, -10), l=(20, 0), mouth="o" if not papa and (t * 6) % 1 < 0.6 else "smile",
                    look=(-1, -1), eye=11)
    dad_think = t > SEG["papa"][0] + 0.1
    dad_pose = dict(r=(-160, -150) if dad_think else (-20, 0), l=(20, 0),
                    mouth="wavy" if dad_think else "smile", look=(-1, -0.6) if not dad_think else (0, -1),
                    tilt=12 if dad_think else 0)
    paste(fr, person(DAD, dad_pose, t, h=600), 700, 1525 - 312, center=True)
    paste(fr, person(KID, kid_pose, t, h=330), 420, 1525 - 172, center=True)
    if not papa:
        b = bubble("Papa, ist das ein Zug?", w=640, fsize=72)
        paste(fr, b, 470, 1700 - 60 + 0 * u, alpha=c01(u / 0.12))
    else:
        v = t - SEG["papa"][0]
        b = bubble("Ich … weiß es nicht, mein Sohn.", w=700, fsize=70)
        paste(fr, b, 560, 1700 - 60, alpha=c01(v / 0.12))
        if dad_think:
            q = font(F_HEAD, 80)
            d = ImageDraw.Draw(fr)
            for i, (qx, qy) in enumerate([(830, 760), (900, 700), (960, 790)]):
                if v > 0.3 + i * 0.3:
                    d.text((qx, qy - 10 * math.sin(t * 4 + i)), "?", font=q, fill=YEL, stroke_width=6,
                           stroke_fill=INK)


def sc_kuh(fr, t, ts, te):
    u = t - ts
    t_kuh = at("kuh", "Kuh")
    t_sie = at("kuh", "Sie")
    t_ich = at("kuh", "Ich")
    t_wir = at("kuh", "Wir")
    if t < t_sie:
        fr.alpha_composite(BG["country"])
        if t >= t_kuh - 0.3:
            paste(fr, cow_side(t, look=(1, 0)), 330, RAIL_Y - 150)
        # train runs in from right and brakes before the cow
        p = eo((t - ts) / (t_sie - 0.3 - ts))
        x = lerp(W + 200, 560, p)
        train_side(fr, x, train_y(), "shock" if t > t_kuh else "proud", t, look=(-1, 0.3))
        if 0.3 < p < 0.98 and t > t_kuh - 0.2:
            sp = ImageDraw.Draw(fr)
            for k in range(10):
                a = math.radians(200 + (k * 37 + int(t * 60) * 13) % 60)
                L = 40 + (k * 17) % 50
                sx, sy = x + 260 + k * 40, RAIL_Y - 5
                sp.line([sx, sy, sx + math.cos(a) * L, sy + math.sin(a) * L], fill=(255, 200, 40), width=5)
        return
    # western standoff: split screen, letterbox
    fr.alpha_composite(vgrad(W, H, (240, 170, 90), (200, 110, 60)))
    d = ImageDraw.Draw(fr)
    v = t - t_sie
    wir = t >= t_wir
    lidc = 0.0
    if wir:
        lidc = c01(math.sin(c01((t - t_wir - 0.4) / 1.1) * math.pi))  # slow, mutual blink
    top_z = 1.0 + 0.12 * eio(v / 2.5)
    cf = cow_face(t, look=(0, 0.25), lid=0.45, chew=t * 1.4, scale=1.15 * top_z, extra_lid=lidc)
    tf = train_front("stare" if not wir else "calm", t, look=(0, -0.2), extra_lid=lidc,
                     scale=1.0 * (1.0 + 0.12 * eio((t - t_ich) / 2.5)) if t >= t_ich else 1.0)
    top = Image.new("RGBA", (W, 620), (0, 0, 0, 0))
    paste(top, cf, W // 2, 330)
    bot = Image.new("RGBA", (W, 620), (0, 0, 0, 0))
    paste(bot, tf, W // 2, 330)
    a_top = 1.0
    a_bot = c01((t - t_ich + 0.1) / 0.2)
    fr.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 0)))
    paste(fr, top, 0, 450, center=False, alpha=a_top)
    d.rectangle([0, 1068, W, 1082], fill=INK)
    if a_bot > 0:
        paste(fr, bot, 0, 1082, center=False, alpha=a_bot)
    if wir and t > t_wir + 0.5:
        h = emoji("🤝", int(150 * eback((t - t_wir - 0.5) / 0.3)))
        paste(fr, h, W // 2 + 330, 1075)


def sc_warten(fr, t, ts, te):
    u = t - ts
    dur = te - ts
    # time-lapse sky: day passes quickly
    k = c01(u / dur)
    fr.alpha_composite(BG["country"])
    sky = Image.new("RGBA", (W, H), (255, 140, 60, int(80 * math.sin(k * math.pi))))
    fr.alpha_composite(sky)
    d = ImageDraw.Draw(fr)
    sx = lerp(150, 950, k)
    sy = 700 - 180 * math.sin(k * math.pi)
    d.ellipse([sx - 60, sy - 60, sx + 60, sy + 60], fill=(255, 220, 80))
    for i in range(3):
        cx = (i * 400 + u * 520) % (W + 400) - 200
        d.ellipse([cx - 110, 560 + i * 90, cx + 110, 640 + i * 90], fill=(255, 255, 255, 230))
        d.ellipse([cx - 50, 520 + i * 90, cx + 70, 610 + i * 90], fill=(255, 255, 255, 230))
    paste(fr, cow_side(t, lying=True, look=(1, -0.2), chew=t * 1.6), 330, RAIL_Y - 150)
    train_side(fr, 560, train_y(), "calm", t, look=(-0.8, 0.4))
    clk = station_clock(8, int(19 + 70 * eio(u / dur)) % 60, (u * 400) % 60, r=110)
    hh = 8 + (19 + 70 * eio(u / dur)) // 60
    clk = station_clock(int(hh), (19 + 70 * eio(u / dur)) % 60, (u * 400) % 60, r=110)
    paste(fr, shadowed(clk), 180, 610)
    # big delay counter
    dl = int(round(70 * eio((u - 0.3) / (dur - 0.6))))
    big = headline([f"+{dl} MIN"], size=120, cols=[(255, 60, 60)])
    paste(fr, scaled(big, 1.0 + 0.04 * math.sin(u * 20) * (dl < 70)), 640, 640)
    z = emoji("💤", 90)
    paste(fr, z, 250 + 10 * math.sin(t * 3), 1000 - 20 * ((t * 0.8) % 1), alpha=0.9)


def sc_ende(fr, t, ts, te):
    u = t - ts
    t_dt = at("ende", "Deutschland")
    t_atmet = at("ende", "atmet")
    t_end = WORDS[-1]["e"]
    fr.alpha_composite(BG["platform"])
    p = eo(u / 1.4)
    train_side(fr, lerp(W + 50, 40, p), train_y(), "happy" if p > 0.98 else "calm", t, look=(0.5, 0.5))
    relieved = t >= t_atmet - 0.1
    for (spec, x, h, ph) in [(WOMAN, 210, 520, 0), (MAN, 840, 520, 1), (MAN2, 520, 470, 2)]:
        pose = dict(r=(-150, -20) if relieved else (-20, 0), l=(150, 20) if relieved else (20, 0),
                    mouth="grin" if relieved else "smile", look=(-0.5, -0.4), lid=0.6 if relieved else 0,
                    hold="coffee" if spec is WOMAN and not relieved else None)
        jump = -30 * abs(math.sin((t + ph) * 6)) if relieved and t < t_end + 1.0 else 0
        paste(fr, person(spec, pose, t, h=h), x, 1520 - h * 0.52 + jump)
    if relieved:
        v = t - t_atmet
        wl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        wd = ImageDraw.Draw(wl)
        for i in range(6):
            yy = 700 + i * 70
            x0 = (v * 900 + i * 140) % (W + 600) - 300
            wd.arc([x0, yy, x0 + 300, yy + 60], 200, 340, fill=(255, 255, 255, 200), width=8)
        fr.alpha_composite(wl)
        st = stamp("ORDNUNG WIEDERHERGESTELLT", RED, 44, rot=-6)
        paste(fr, st, W // 2, 690, alpha=c01(v / 0.15))
    # comment bait at the end
    if t >= t_end + 0.25:
        v = t - (t_end + 0.25)
        b = bubble(CTA + " 👇" if False else CTA, w=860, hand=False, fsize=56, col=YEL)
        paste(fr, scaled(b, 0.7 + 0.3 * eback(v / 0.3)), W // 2, 1640)
        e = emoji("👇", 110)
        paste(fr, e, W // 2, 1840 + 12 * math.sin(t * 6), alpha=c01(v / 0.2))


SCENE_FN = {"hook": sc_hook, "einfahrt": sc_einfahrt, "bahnsteig": sc_bahnsteig, "news": sc_news,
            "kassel": sc_kassel, "kind": sc_kind, "papa": lambda *a: sc_kind(*a, papa=True), "kuh": sc_kuh,
            "warten": sc_warten, "ende": sc_ende}


def render_frame(fi):
    init()
    t = fi / FPS
    k = scene_at(t)
    ts, te = SEG[k]
    fr = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    SCENE_FN[k](fr, t, ts, te)
    # board punch when delay jumps / hook
    punch = 1.0
    if k == "hook":
        punch = 1.0 + 0.04 * math.sin(t * 18) * (t > at("hook", "Panik") - 0.2)
    draw_board(fr, t, punch=punch)
    if k not in ("ende",) or t < WORDS[-1]["e"] + 0.25:
        if k != "hook":
            draw_caption(fr, t)
    # screen shake on "Panik"
    if k == "hook":
        tp = at("hook", "Panik")
        if t > tp - 0.1:
            a = 14 * max(0, 1 - (t - tp) / 0.9)
            dx, dy = int(a * math.sin(t * 90)), int(a * math.cos(t * 77))
            fr = fr.transform(fr.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), fillcolor=(0, 0, 0, 255))
    # whip transition between scenes
    v = t - ts
    if v < 0.12 and k != "hook" and k != "papa":
        fr.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(150 * (1 - v / 0.12)))))
    # progress bar
    d = ImageDraw.Draw(fr)
    d.rectangle([0, H - 12, int(W * t / TOTAL), H], fill=YEL)
    return fr.convert("RGB").tobytes()


# ================================================================== sound design
def env(n, a, dcy):
    tt = np.arange(n) / SR
    return np.minimum(1, tt / max(a, 1e-4)) * np.exp(-tt / dcy)


def tone(f, dur, a=0.005, dcy=0.4, harm=(1.0,)):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    return sum(h * np.sin(2 * np.pi * f * (i + 1) * tt) for i, h in enumerate(harm)) * env(n, a, dcy)


def lowpass(x, alpha):
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += alpha * (x[i] - acc)
        y[i] = acc
    return y


def onepole(x, fc):
    # vectorised-ish one-pole lowpass via scipy-free recursion in chunks
    a = 1 - math.exp(-2 * math.pi * fc / SR)
    return lowpass(x, a)


def saw(f_arr):
    ph = np.cumsum(f_arr) / SR
    return 2 * (ph % 1) - 1


def sfx_gong():
    return (np.concatenate([tone(659.25, 0.7, dcy=0.5, harm=(1, .3, .1)),
                            np.zeros(1)]) * 0.5 +
            np.pad(tone(523.25, 1.4, dcy=0.7, harm=(1, .3, .1)), (int(0.45 * SR), 0))[:int(0.7 * SR) + 1] * 0)


def chime():
    a = tone(659.25, 0.9, dcy=0.5, harm=(1, .35, .12))
    b = tone(523.25, 1.6, dcy=0.8, harm=(1, .35, .12))
    out = np.zeros(int(2.2 * SR))
    out[:len(a)] += a
    o = int(0.5 * SR)
    out[o:o + len(b)] += b
    return out * 0.45


def horn(dur=1.0):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    sig = sum(np.sign(np.sin(2 * np.pi * f * tt)) * 0.3 + np.sin(2 * np.pi * f * tt) for f in (330, 392))
    e = np.minimum(1, tt / 0.04) * np.minimum(1, (dur - tt) / 0.12)
    return onepole(sig * e, 1800) * 0.35


def whoosh(rng, dur=0.35):
    n = int(dur * SR)
    no = rng.standard_normal(n)
    e = np.sin(np.pi * np.linspace(0, 1, n)) ** 2
    return onepole(no * e, 2500) * 0.6


def splash(rng):
    n = int(0.5 * SR)
    no = rng.standard_normal(n)
    return (onepole(no, 1500) * env(n, 0.002, 0.12) * 0.9 + tone(90, 0.3, 0.001, 0.08) * 0.6
            if False else onepole(no, 1500)[:n] * env(n, 0.002, 0.12) * 0.9)


def shutter(rng):
    n = int(0.09 * SR)
    no = rng.standard_normal(n)
    c = np.zeros(n)
    c[:int(0.012 * SR)] = 1
    c[int(0.05 * SR):int(0.062 * SR)] = 0.7
    return no * c * 0.4


def cricket(dur):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    gate = ((tt * 14) % 1 < 0.45) & ((tt * 1.3) % 1 < 0.45)
    return np.sin(2 * np.pi * 4300 * tt) * gate * 0.06


def moo(dur=1.6):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f = 105 + 30 * np.sin(np.pi * np.minimum(1, tt / dur)) - 15 * (tt / dur)
    src = saw(f)
    # crude formants
    out = onepole(src, 700) * 0.8 + onepole(src, 1400) * 0.2
    e = np.minimum(1, tt / 0.15) * np.minimum(1, (dur - tt) / 0.35)
    return out * e * 0.6


def news_sting():
    out = np.zeros(int(1.4 * SR))
    for i, f in enumerate([392, 523.25, 659.25, 783.99]):
        tn = tone(f, 0.9, 0.003, 0.35, harm=(1, .5, .25))
        o = int(i * 0.09 * SR)
        out[o:o + len(tn)] += tn * 0.35
    hit = tone(55, 1.0, 0.002, 0.35, harm=(1, .5))
    out[int(0.36 * SR):int(0.36 * SR) + len(hit)] += hit * 0.7
    return out


def standoff():
    # lonely whistle-ish tone + low drone
    n = int(2.0 * SR)
    tt = np.arange(n) / SR
    f = 880 + 60 * np.sin(2 * np.pi * 5 * tt) * (tt > 0.6)
    w = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, tt / 0.1) * np.minimum(1, (2.0 - tt) / 0.6)
    dr = np.sin(2 * np.pi * 73.4 * tt) * 0.5
    return (w * 0.16 + dr * 0.18 * np.minimum(1, tt / 0.4) * np.minimum(1, (2.0 - tt) / 0.5))


def tick():
    return tone(2400, 0.03, 0.0005, 0.006) * 0.25


def alarm(dur):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    f = 700 + 300 * (np.sin(2 * np.pi * 2.2 * tt) > 0)
    return np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.05 * np.minimum(1, (dur - tt) / 0.3)


def sigh(rng):
    n = int(1.4 * SR)
    no = rng.standard_normal(n)
    tt = np.arange(n) / SR
    e = np.minimum(1, tt / 0.2) * np.exp(-tt / 0.6)
    return onepole(no, 900) * e * 0.5


def fanfare():
    out = np.zeros(int(2.0 * SR))
    for i, (f, dt) in enumerate([(523.25, 0), (659.25, 0.12), (783.99, 0.24), (1046.5, 0.36)]):
        tn = tone(f, 1.4, 0.004, 0.5, harm=(1, .4, .2))
        o = int(dt * SR)
        out[o:o + len(tn)] += tn * 0.25
    return out


def bed(dur, bpm=100):
    rng = np.random.default_rng(3)
    n = int(dur * SR)
    out = np.zeros(n)
    beat = 60 / bpm
    kn = int(0.3 * SR)
    kt = np.arange(kn) / SR
    kick = np.sin(2 * np.pi * (48 + 90 * np.exp(-kt * 25)) * kt) * env(kn, 0.001, 0.12)
    hn = int(0.04 * SR)
    hat = np.diff(rng.standard_normal(hn + 1)) * env(hn, 0.0005, 0.01) * 0.25
    pl = [261.63, 329.63, 392.0, 329.63, 293.66, 349.23, 440.0, 349.23]
    i, tb = 0, 0.0
    while tb < dur:
        s0 = int(tb * SR)
        if i % 2 == 0:
            seg = kick[:max(0, min(kn, n - s0))]
            out[s0:s0 + len(seg)] += seg * 0.7
        h0 = int((tb + beat / 2) * SR)
        seg = hat[:max(0, min(hn, n - h0))]
        out[h0:h0 + len(seg)] += seg
        pz = tone(pl[i % 8], 0.25, 0.002, 0.08, harm=(1, .3)) * 0.12
        pz = pz[:max(0, n - s0)]
        out[s0:s0 + len(pz)] += pz
        tb += beat
        i += 1
    return out


def make_audio(path):
    rng = np.random.default_rng(11)
    n = int((TOTAL + 0.5) * SR)
    voice = np.zeros(n)
    for _, sig, st in PIECES:
        i = int(st * SR)
        sig = sig[:max(0, n - i)]
        voice[i:i + len(sig)] += sig
    pk = np.max(np.abs(voice)) or 1
    voice = voice / pk * 0.9
    fx = np.zeros(n)

    def put(sig, t, g=1.0):
        i = int(max(0, t) * SR)
        sig = sig[:max(0, n - i)]
        fx[i:i + len(sig)] += sig * g

    put(alarm(SEG["hook"][1] - at("hook", "Panik") + 0.2), at("hook", "Panik") - 0.1, 1.2)
    put(whoosh(rng, 0.5), at("hook", "Panik") - 0.15, 0.8)
    put(chime(), SEG["einfahrt"][0] + 0.05, 0.9)
    put(horn(0.9), at("einfahrt", "fahre") - 0.2, 0.7)
    put(tone(1320, 0.4, 0.002, 0.15, harm=(1, .3)) * 0.4, at("einfahrt", "Minute") + 0.3)
    put(cricket(1.2), at("bahnsteig", "Stille") + 0.3, 1.0)
    put(splash(rng), at("bahnsteig", "fallen") + 0.45, 1.0)
    put(news_sting(), SEG["news"][0], 0.9)
    for i in range(6):
        put(shutter(rng), at("kassel", "Leute") + 0.3 + i * 0.27 + 0.05 * (i % 2), 1.0)
    pe = [w for w in WORDS if w["key"] == "papa"][-1]["e"]
    put(cricket(SEG["papa"][1] - pe), pe + 0.1, 1.2)
    put(horn(1.2), at("kuh", "Kuh") - 0.2, 0.8)
    put(moo(1.6), at("kuh", "Gleis") + 0.25, 1.0)
    put(standoff(), at("kuh", "Sie") - 0.2, 1.0)
    put(tone(2000, 0.6, 0.002, 0.25, harm=(1, .5)) * 0.25, at("kuh", "Wir") + 0.9)
    ws, we = SEG["warten"]
    for k in range(70):
        tt = ws + 0.3 + (we - ws - 0.6) * (k / 70)
        put(tick(), tt, 1.0)
    put(moo(1.2), we - 1.2, 0.6)
    put(sigh(rng), at("ende", "atmet"), 1.0)
    put(fanfare(), at("ende", "atmet") + 0.5, 1.0)
    for k in KEYS[1:]:
        if k != "papa":
            put(whoosh(rng, 0.3), SEG[k][0] - 0.15, 0.35)
    b = bed(TOTAL + 0.5)[:n]
    # duck the bed in the silent/comic beats
    gate = np.ones(n)
    for a_, b_ in [(at("bahnsteig", "Stille") + 0.2, at("bahnsteig", "Eine")),
                   ([w for w in WORDS if w["key"] == "papa"][-1]["e"], SEG["papa"][1]),
                   (at("kuh", "Sie") - 0.2, SEG["kuh"][1])]:
        gate[int(a_ * SR):int(b_ * SR)] = 0
    gate = np.convolve(gate, np.ones(4800) / 4800, mode="same")
    mix = voice + fx * 0.6 + b * gate * 0.22
    fade = np.minimum(1, (n - np.arange(n)) / SR / 0.6)
    mix = np.clip(mix * fade, -1, 1)
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
    if len(sys.argv) > 1 and sys.argv[1] == "times":
        for k in KEYS:
            print(f"{k:10s} {SEG[k][0]:6.2f} – {SEG[k][1]:6.2f}")
        print("total", round(TOTAL, 2))
        return
    out = ROOT / os.environ.get("VIDEO_OUT", "ice-video.mp4")
    raw = BUILD / "mix_raw.wav"
    make_audio(raw)
    audio = BUILD / "mix.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", str(audio)], check=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-t", f"{NFRAMES / FPS:.3f}", str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=init) as pool:
        for i, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=4)):
            ff.stdin.write(buf)
            if i % 300 == 0:
                print(f"frame {i}/{NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", out, f"{NFRAMES / FPS:.2f}s")


if __name__ == "__main__":
    main()
