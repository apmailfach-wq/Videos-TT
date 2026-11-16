"""Render notwehr-video.mp4 (1080x1920, 30 fps) in a flat "explainer" look.

Light grey stage, extra-wide headline that types itself in at the top, chapter
badge, animated stick figures (teal = you, navy = attacker) and paper props
(law pages, polaroids, envelopes, stamps). Frames are drawn with Pillow and
piped into ffmpeg together with the voiceover from build/timings.json.
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
FONTS = ROOT / "fonts"
W, H, FPS = 1080, 1920, 30
TAIL = 0.8

F_HEAD = str(FONTS / "Unbounded_900Black.ttf")
F_HEAD_B = str(FONTS / "Unbounded_700Bold.ttf")
F_HAND = str(FONTS / "Caveat_700Bold.ttf")
F_BODY = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
F_BODY_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"

INK = (20, 22, 26)
GREY = (139, 147, 155)
TEAL = (24, 168, 152)
TEAL_L = (158, 228, 218)
RED = (229, 72, 77)
NAVY = (46, 55, 66)
NAVY_B = (70, 80, 92)
TEAL_F = (34, 179, 164)
TEAL_B = (20, 140, 128)
PAPER = (255, 255, 255)
BEIGE = (240, 234, 222)

STAGE_Y = 650          # stage layer occupies y = STAGE_Y .. H
STAGE_H = H - STAGE_Y


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
    return tuple(int(lerp(a[i], b[i], t)) for i in range(3))


# ------------------------------------------------------------------ timings
TIM = json.loads((BUILD / "timings.json").read_text())
sys.path.insert(0, str(Path(__file__).resolve().parent))
from script import SCENES  # noqa: E402

KEYS = [s["key"] for s in SCENES]
OFF = []
_a = 0.0
for s in TIM:
    OFF.append(_a)
    _a += s["duration"]
TOTAL = _a + TAIL
NFRAMES = int(math.ceil(TOTAL * FPS))


def at(scene, word, occ=0, lead=0.06):
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


# ------------------------------------------------------------------ helpers
def supersample(w, h, draw_fn, ss=2):
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    draw_fn(im, ImageDraw.Draw(im), ss)
    return im.resize((w, h), Image.LANCZOS)


def with_shadow(im, dy=16, blur=18, alpha=0.22, pad=40):
    out = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    a = im.getchannel("A").point(lambda v: int(v * alpha))
    sh = Image.new("RGBA", im.size, (30, 40, 50, 0))
    sh.putalpha(a)
    tmp = Image.new("RGBA", out.size, (0, 0, 0, 0))
    tmp.alpha_composite(sh, (pad, pad + dy))
    tmp = tmp.filter(ImageFilter.GaussianBlur(blur))
    tmp.alpha_composite(im, (pad, pad))
    return tmp


def text_tracked(d, xy, text, f, fill, tracking=0, anchor_center=True):
    widths = [f.getlength(c) for c in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x, y = xy
    if anchor_center:
        x -= total / 2
    for c, cw in zip(text, widths):
        d.text((x, y), c, font=f, fill=fill, anchor="ls")
        x += cw + tracking
    return total


def wrap_lines(text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if cur and f.getlength(t) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------------------ stick figures
SEG = dict(torso=92, ua=56, fa=54, th=70, sh=68, head=31, limb=25, tw=33)

POSES = {
    "stand":  dict(t=0, uaf=10, faf=14, uab=-10, fab=-6, thf=5, shf=0, thb=-5, shb=0),
    "guard":  dict(t=6, uaf=38, faf=150, uab=22, fab=158, thf=18, shf=0, thb=-16, shb=0),
    "punch":  dict(t=14, uaf=88, faf=90, uab=15, fab=160, thf=28, shf=4, thb=-24, shb=-6),
    "hit":    dict(t=-24, uaf=-35, faf=5, uab=-55, fab=-25, thf=22, shf=6, thb=-12, shb=-4),
    "push":   dict(t=12, uaf=78, faf=84, uab=72, fab=80, thf=26, shf=4, thb=-26, shb=-6),
    "lying":  dict(t=-90, uaf=96, faf=92, uab=84, fab=88, thf=92, shf=90, thb=88, shb=90),
    "kick":   dict(t=-14, uaf=55, faf=80, uab=-40, fab=-20, thf=78, shf=86, thb=-4, shb=0),
    "stomp":  dict(t=4, uaf=40, faf=60, uab=-30, fab=-15, thf=55, shf=40, thb=-6, shb=0),
    "cower":  dict(t=-12, uaf=70, faf=168, uab=58, fab=172, thf=32, shf=-12, thb=6, shb=-26),
    "walk1":  dict(t=4, uaf=30, faf=45, uab=-30, fab=-15, thf=24, shf=4, thb=-24, shb=-34),
    "walk2":  dict(t=4, uaf=-30, faf=-15, uab=30, fab=45, thf=-24, shf=-34, thb=24, shb=4),
    "handsup": dict(t=-4, uaf=158, faf=172, uab=148, fab=168, thf=5, shf=0, thb=-5, shb=0),
    "shrug":  dict(t=0, uaf=30, faf=120, uab=-30, fab=-120, thf=5, shf=0, thb=-5, shb=0),
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

    def limb(a, b, c, w):
        w = w * s * ss
        seq = [P(a), P(b)] + ([P(c)] if c else [])
        d.line(seq, fill=cur[0], width=int(w), joint="curve")
        for q in seq:
            d.ellipse([q[0] - w / 2, q[1] - w / 2, q[0] + w / 2, q[1] + w / 2], fill=cur[0])

    cur = [col_b]
    limb("sho", "eb", "hb", SEG["limb"])
    limb("hip", "kb", "fb", SEG["limb"])
    cur[0] = col_f
    limb("hip", "sho", None, SEG["tw"])
    hx, hy = P("head")
    r = SEG["head"] * s * ss
    d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=col_f)
    limb("hip", "kf", "ff", SEG["limb"])
    limb("sho", "ef", "hf", SEG["limb"])


TEAM = {"you": (TEAL_F, TEAL_B), "foe": (NAVY, NAVY_B), "grey": ((120, 130, 140), (150, 158, 166))}


def figure_image(pose, team="you", facing=1, s=1.0, shadow=True):
    """Static anti-aliased figure (used inside polaroids)."""
    p = POSES[pose] if isinstance(pose, str) else pose
    pts = figure_points(p, facing, s)
    xs = [q[0] for q in pts.values()]
    ys = [q[1] for q in pts.values()]
    m = 50 * s
    x0, x1, y0 = min(xs) - m, max(xs) + m, min(ys) - m
    w, h = int(x1 - x0), int(-y0 + m * 0.6)
    cf, cb = TEAM[team]

    def fn(im, d, ss):
        if shadow:
            d.ellipse([(-x0 - 60 * s) * ss, (h - m * 0.6 - 10 * s) * ss,
                       (-x0 + 60 * s) * ss, (h - m * 0.6 + 10 * s) * ss], fill=(0, 0, 0, 30))
        draw_figure(d, pts, -x0, h - m * 0.6, s, cf, cb, ss)

    return supersample(w, h, fn), (-x0, h - m * 0.6)


class Fig:
    """Animated stick figure on the stage. keys: list of (time, pose, x)."""

    def __init__(self, team, y, keys, facing=1, s=1.3, recolor=None, shake=None):
        self.team, self.y, self.keys, self.facing, self.s = team, y, keys, facing, s
        self.recolor = recolor  # (t, team) -> morph colours
        self.shake = shake      # (t0, t1) trembling

    def state(self, t):
        ks = self.keys
        if t <= ks[0][0]:
            return POSES[ks[0][1]], ks[0][2]
        for (ta, pa, xa), (tb, pb, xb) in zip(ks, ks[1:]):
            if ta <= t < tb:
                u = ease_io((t - ta) / (tb - ta))
                return lerp_pose(POSES[pa], POSES[pb], u), lerp(xa, xb, u)
        return POSES[ks[-1][1]], ks[-1][2]

    def draw(self, d, t, ss, dx=0, dy=0):
        p, x = self.state(t)
        if self.shake and self.shake[0] <= t < self.shake[1]:
            x += math.sin(t * 60) * 4
        cf, cb = TEAM[self.team]
        if self.recolor and t >= self.recolor[0]:
            u = clamp01((t - self.recolor[0]) / 0.5)
            nf, nb = TEAM[self.recolor[1]]
            cf, cb = lerp_col(cf, nf, u), lerp_col(cb, nb, u)
        pts = figure_points(p, self.facing, self.s)
        gx, gy = x + dx, self.y + dy
        sw = 70 * self.s
        d.ellipse([(gx - sw) * ss, (gy - 12 * self.s) * ss, (gx + sw) * ss, (gy + 12 * self.s) * ss],
                  fill=(20, 30, 40, 34))
        draw_figure(d, pts, gx, gy, self.s, cf, cb, ss)


# ------------------------------------------------------------------ props
def doc_page(header, title, body, lines=4, w=620, h=780, accent=TEAL_L, extra=None):
    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 18 * S, (w - 6) * S, h * S], radius=10 * S, fill=(196, 204, 210))
        d.rounded_rectangle([14 * S, 0, w * S, (h - 14) * S], radius=10 * S, fill=PAPER)
        x = 60 * S
        y = 70 * S
        d.text((x, y), header.upper(), font=font(F_HEAD_B, 19 * S), fill=(150, 158, 165), anchor="ls")
        y += 34 * S
        tsize = 38
        while tsize > 20 and max(font(F_HEAD, tsize).getlength(l) for l in title.split("\n")) > w - 140:
            tsize -= 1
        ft = font(F_HEAD, tsize * S)
        for ln in title.split("\n"):
            tw = ft.getlength(ln)
            d.rectangle([x - 8 * S, y, x + tw + 10 * S, y + 50 * S], fill=accent)
            d.text((x, y + 40 * S), ln, font=ft, fill=INK, anchor="ls")
            y += 52 * S
        y += 34 * S
        fb = font(F_BODY, 27 * S)
        for ln in wrap_lines(body, fb, (w - 130) * S):
            d.text((x + 6 * S, y), ln, font=fb, fill=(52, 56, 62), anchor="lt")
            y += 38 * S
        y += 30 * S
        rnd = random.Random(len(title))
        for i in range(lines):
            ww = rnd.uniform(0.55, 0.85) * (w - 140) * S
            d.rounded_rectangle([x, y, x + ww, y + 12 * S], radius=6 * S, fill=(222, 227, 231))
            y += 34 * S
        if extra:
            extra(d, S, x, y)
    return with_shadow(supersample(w, h, fn))


def polaroid(scene_fn, caption, w=330, h=390):
    def fn(im, d, ss):
        S = ss
        d.rectangle([0, 0, w * S, h * S], fill=PAPER)
        d.rectangle([20 * S, 20 * S, (w - 20) * S, (h - 92) * S], fill=(226, 231, 235))
        d.text((w / 2 * S, (h - 42) * S), caption, font=font(F_HAND, 44 * S), fill=(40, 44, 50), anchor="mm")
    base = supersample(w, h, fn)
    if scene_fn:
        scene_fn(base, (20, 20, w - 20, h - 92))
    return with_shadow(base, dy=10, blur=12)


def photo_figs(*figs):
    """figs: (pose, team, facing, rel_x, scale)."""
    def fn(base, box):
        x0, y0, x1, y1 = box
        for pose, team, facing, rx, sc in figs:
            img, (ax, ay) = figure_image(pose, team, facing, sc, shadow=True)
            px = int(x0 + rx * (x1 - x0) - ax)
            py = int(y1 - 18 - ay)
            base.alpha_composite(img, (max(0, px), max(0, py)))
    return fn


def photo_shoe(base, box):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(base)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    d.rounded_rectangle([cx - 45, cy - 100, cx + 45, cy + 10], radius=40, fill=(90, 98, 108))
    d.rounded_rectangle([cx - 38, cy + 26, cx + 38, cy + 100], radius=34, fill=(90, 98, 108))
    for k in range(5):
        yy = cy - 82 + k * 18
        d.line([(cx - 30, yy), (cx + 30, yy)], fill=(200, 206, 212), width=6)
    for k in range(3):
        yy = cy + 44 + k * 18
        d.line([(cx - 26, yy), (cx + 26, yy)], fill=(200, 206, 212), width=6)


def envelope(label, col=RED, w=460, h=280):
    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=8 * S, fill=BEIGE)
        d.line([(0, 0), (w / 2 * S, h * 0.55 * S), (w * S, 0)], fill=(214, 206, 190), width=4 * S)
        f = font(F_HEAD, 30 * S)
        tw = f.getlength(label)
        bx0, by0 = (w / 2) * S - tw / 2 - 26 * S, h * 0.62 * S
        d.rounded_rectangle([bx0, by0, bx0 + tw + 52 * S, by0 + 62 * S], radius=10 * S, fill=col)
        d.text((w / 2 * S, by0 + 31 * S), label, font=f, fill=PAPER, anchor="mm")
    return with_shadow(supersample(w, h, fn), dy=8, blur=12)


def stamp(text, col=RED, size=54, fill=False):
    f = font(F_HEAD, size)
    lines = text.split("\n")
    tw = max(f.getlength(l) for l in lines)
    w, h = int(tw + 70), int(size * 1.25 * len(lines) + 46)

    def fn(im, d, ss):
        S = ss
        if fill:
            d.rounded_rectangle([0, 0, w * S, h * S], radius=14 * S, fill=col)
        else:
            d.rounded_rectangle([4 * S, 4 * S, (w - 4) * S, (h - 4) * S], radius=14 * S, outline=col,
                                width=7 * S)
        for i, ln in enumerate(lines):
            d.text((w / 2 * S, (h / 2 + (i - (len(lines) - 1) / 2) * size * 1.2) * S), ln, font=font(F_HEAD, size * S),
                   fill=PAPER if fill else col, anchor="mm")
    im = supersample(w, h, fn)
    # worn ink texture
    rnd = np.random.default_rng(len(text) * 7)
    noise = rnd.random((h, w))
    a = np.array(im.getchannel("A"), np.float32)
    a *= np.where(noise < 0.10, 0.35, 1.0)
    im.putalpha(Image.fromarray(a.astype(np.uint8)))
    return im


def check_badge(r=56, col=TEAL):
    def fn(im, d, ss):
        S = ss
        d.ellipse([0, 0, 2 * r * S, 2 * r * S], fill=col)
        d.line([(r * 0.55 * S, r * 1.02 * S), (r * 0.88 * S, r * 1.35 * S), (r * 1.48 * S, r * 0.7 * S)],
               fill=PAPER, width=int(r * 0.22 * S), joint="curve")
    return with_shadow(supersample(2 * r, 2 * r, fn), dy=6, blur=8, pad=20)


def cross_mark(r=70, col=RED):
    def fn(im, d, ss):
        S = ss
        wd = int(r * 0.32 * S)
        d.line([(wd, wd), (2 * r * S - wd, 2 * r * S - wd)], fill=col, width=wd)
        d.line([(wd, 2 * r * S - wd), (2 * r * S - wd, wd)], fill=col, width=wd)
    return supersample(2 * r, 2 * r, fn)


def ruler(w=900):
    h = 90

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=10 * S, fill=(234, 244, 242), outline=(170, 210, 204),
                            width=3 * S)
        for i in range(0, w - 30, 18):
            L = 34 if (i // 18) % 5 == 0 else 20
            d.line([(20 * S + i * S, 0), (20 * S + i * S, L * S)], fill=(110, 170, 160), width=3 * S)
    return with_shadow(supersample(w, h, fn), dy=8, blur=10)


def red_line(w=900, th=14):
    def fn(im, d, ss):
        d.rounded_rectangle([0, 0, w * ss, th * ss], radius=th / 2 * ss, fill=RED)
    return supersample(w, th, fn)


def dashed_arrow(w=420):
    h = 80

    def fn(im, d, ss):
        S = ss
        x = w - 10
        while x > 80:
            d.line([(x * S, 40 * S), ((x - 34) * S, 40 * S)], fill=(150, 160, 170), width=10 * S)
            x -= 56
        d.polygon([(10 * S, 40 * S), (70 * S, 8 * S), (70 * S, 72 * S)], fill=(150, 160, 170))
    return supersample(w, h, fn)


def business_card():
    w, h = 660, 380

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=18 * S, fill=PAPER)
        d.rectangle([0, 0, 22 * S, h * S], fill=TEAL)
        d.text((70 * S, 90 * S), "KANZLEI", font=font(F_HEAD_B, 22 * S), fill=GREY, anchor="ls")
        d.text((70 * S, 160 * S), "Fachanwalt", font=font(F_HEAD, 46 * S), fill=INK, anchor="ls")
        d.text((70 * S, 215 * S), "für Strafrecht", font=font(F_HEAD, 46 * S), fill=TEAL, anchor="ls")
        d.text((70 * S, 290 * S), "Notruf 24/7 · Strafverteidigung", font=font(F_BODY, 26 * S), fill=(80, 86, 94),
               anchor="ls")
        # scales icon
        cx, cy = 560 * S, 110 * S
        d.line([(cx, cy - 50 * S), (cx, cy + 50 * S)], fill=INK, width=8 * S)
        d.line([(cx - 60 * S, cy - 30 * S), (cx + 60 * S, cy - 30 * S)], fill=INK, width=8 * S)
        d.line([(cx - 40 * S, cy + 50 * S), (cx + 40 * S, cy + 50 * S)], fill=INK, width=8 * S)
        for sx in (-1, 1):
            px = cx + sx * 52 * S
            d.chord([px - 30 * S, cy - 10 * S, px + 30 * S, cy + 40 * S], 0, 180, fill=TEAL)
    return with_shadow(supersample(w, h, fn))


def bookmark_card():
    w, h = 640, 300

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=40 * S, fill=INK)
        bx, by = 80 * S, 70 * S
        d.polygon([(bx, by), (bx + 100 * S, by), (bx + 100 * S, by + 160 * S), (bx + 50 * S, by + 115 * S),
                   (bx, by + 160 * S)], fill=(250, 204, 21))
        d.text((230 * S, 135 * S), "SPEICHERN", font=font(F_HEAD, 40 * S), fill=PAPER, anchor="lm")
        d.text((230 * S, 190 * S), "für den Ernstfall", font=font(F_BODY_B, 30 * S), fill=(170, 178, 186),
               anchor="lm")
    return with_shadow(supersample(w, h, fn))


def tip_card(num, text):
    w, h = 300, 360

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=18 * S, fill=PAPER)
        d.rounded_rectangle([w / 2 * S - 55 * S, 50 * S, w / 2 * S + 55 * S, 160 * S], radius=22 * S, fill=INK)
        d.text((w / 2 * S, 106 * S), str(num), font=font(F_HEAD, 64 * S), fill=PAPER, anchor="mm")
        for i, ln in enumerate(text.split("\n")):
            d.text((w / 2 * S, (230 + i * 50) * S), ln, font=font(F_HAND, 46 * S), fill=(40, 44, 50), anchor="mm")
    return with_shadow(supersample(w, h, fn), dy=10, blur=12)


def toc_page():
    def extra(d, S, x, y):
        pass
    body = ""
    w, h = 640, 800

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 18 * S, (w - 6) * S, h * S], radius=10 * S, fill=(196, 204, 210))
        d.rounded_rectangle([14 * S, 0, w * S, (h - 14) * S], radius=10 * S, fill=PAPER)
        x = 60 * S
        d.text((x, 80 * S), "STRAFGESETZBUCH", font=font(F_HEAD_B, 20 * S), fill=(150, 158, 165), anchor="ls")
        d.text((x, 150 * S), "StGB", font=font(F_HEAD, 64 * S), fill=INK, anchor="ls")
        rows = [("§ 32", "Notwehr", TEAL_L), ("§ 33", "Notwehrexzess", TEAL_L),
                ("§ 223", "Körperverletzung", (250, 200, 200)), ("§ 224", "Gefährliche KV", (250, 200, 200))]
        y = 230 * S
        for p, t, c in rows:
            d.rectangle([x - 8 * S, y - 6 * S, x + 520 * S, y + 62 * S], fill=c)
            d.text((x + 6 * S, y + 28 * S), p, font=font(F_HEAD, 32 * S), fill=INK, anchor="lm")
            d.text((x + 150 * S, y + 28 * S), t, font=font(F_BODY_B, 32 * S), fill=INK, anchor="lm")
            y += 100 * S
        for i in range(4):
            d.rounded_rectangle([x, y + 10 * S, x + (380 - i * 40) * S, y + 22 * S], radius=6 * S,
                                fill=(222, 227, 231))
            y += 36 * S
    return with_shadow(supersample(w, h, fn))


QUESTION = ("Wurdet ihr schon mal *angegriffen* und musstet euch *wehren* – "
            "und wie ist es *ausgegangen?*")


def question_bubble(w=960):
    f = font(F_HEAD, 54)
    words = parse_rich(QUESTION.upper())
    sp = f.getlength(" ")
    lines, cur, cw = [], [], 0
    for wd, hl in words:
        ww = f.getlength(wd)
        if cur and cw + sp + ww > w - 110:
            lines.append(cur)
            cur, cw = [], 0
        cur.append((wd, hl, ww))
        cw += (sp if len(cur) > 1 else 0) + ww
    lines.append(cur)
    lh = 74
    h = lh * len(lines) + 110
    H2 = h + 60

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=44 * S, fill=PAPER)
        d.polygon([(110 * S, (h - 2) * S), (210 * S, (h - 2) * S), (95 * S, (H2 - 4) * S)], fill=PAPER)
        fs = font(F_HEAD, 54 * S)
        y = 55 + lh * 0.78
        for ln in lines:
            lw = sum(x[2] for x in ln) + sp * (len(ln) - 1)
            x = (w - lw) / 2
            for wd, hl, ww in ln:
                col = (RED if "ANGEGRIFFEN" in wd else TEAL) if hl else INK
                d.text((x * S, y * S), wd, font=fs, fill=col, anchor="ls")
                x += ww + sp
            y += lh
    return with_shadow(supersample(w, H2, fn), dy=14, blur=20, alpha=0.2)


def cta_pill(emoji, text, bg):
    f = font(F_HEAD, 36)
    tw = f.getlength(text)
    em = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(em).text((80, 80), emoji, font=ImageFont.truetype(
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109), embedded_color=True, anchor="mm")
    em = em.crop(em.getbbox()).resize((62, 62), Image.LANCZOS)
    w, h = int(tw + 62 + 110), 112

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=h / 2 * S, fill=bg)
        d.text(((62 + 78) * S, h / 2 * S), text, font=font(F_HEAD, 36 * S), fill=PAPER, anchor="lm")
    im = supersample(w, h, fn)
    im.alpha_composite(em, (40, (h - 62) // 2))
    return with_shadow(im, dy=10, blur=14, alpha=0.25)


class Prop:
    def __init__(self, img, x, y, t, rot=0.0, enter="up", z=0):
        self.img, self.x, self.y, self.t, self.rot, self.enter, self.z = img, x, y, t, rot, enter, z
        self._rot_cache = {}

    def rotated(self, angle):
        key = round(angle * 4) / 4
        if key not in self._rot_cache:
            self._rot_cache[key] = self.img.rotate(key, resample=Image.BICUBIC, expand=True) if key else self.img
        return self._rot_cache[key]

    def draw(self, layer, t, out):
        p = (t - self.t) / 0.5
        if p < 0:
            return
        img = None
        x, y, alpha, scale, rot = self.x, self.y, 1.0, 1.0, self.rot
        if self.enter == "up":
            e = ease_back(p, 1.1)
            y += (1 - e) * 700
            rot = self.rot + (1 - ease_out(p)) * 10
        elif self.enter == "left":
            e = ease_back(p, 1.0)
            x -= (1 - e) * 1100
            rot = self.rot - (1 - ease_out(p)) * 12
        elif self.enter == "right":
            e = ease_back(p, 1.0)
            x += (1 - e) * 1100
            rot = self.rot + (1 - ease_out(p)) * 12
        elif self.enter == "drop":
            e = ease_back(p * 1.3, 1.8)
            y -= (1 - e) * 160
            alpha = clamp01(p * 3)
        elif self.enter == "stamp":
            q = clamp01((t - self.t) / 0.18)
            scale = lerp(1.9, 1.0, ease_out(q))
            alpha = q
        elif self.enter == "pop":
            scale = 0.2 + 0.8 * ease_back(p * 1.4, 2.2)
            alpha = clamp01(p * 4)
        elif self.enter == "wipe":
            q = ease_io((t - self.t) / 0.7)
            if q <= 0:
                return
            img = self.img.crop((0, 0, max(1, int(self.img.width * q)), self.img.height))
            layer.alpha_composite(img, (int(x - self.img.width / 2), int(y - STAGE_Y - self.img.height / 2)))
            return
        elif self.enter == "fade":
            alpha = clamp01(p * 2)
        alpha *= 1 - out
        y += out * 60
        img = self.rotated(rot)
        if abs(scale - 1) > 0.01:
            img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BICUBIC)
        if alpha < 0.99:
            img = img.copy()
            img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
        layer.alpha_composite(img, (int(x - img.width / 2), int(y - STAGE_Y - img.height / 2)))


# ------------------------------------------------------------------ cards
class Card:
    def __init__(self, start, end, badge=None, dark=False):
        self.start, self.end, self.badge, self.dark = start, end, badge, dark
        self.texts = []   # (t, kicker, headline, sub)
        self.props = []
        self.figs = []

    def text(self, t, kicker, head, sub=""):
        self.texts.append((t, kicker, head, sub))
        return self

    def prop(self, *a, **k):
        self.props.append(Prop(*a, **k))
        return self

    def fig(self, *a, **k):
        self.figs.append(Fig(*a, **k))
        return self


GROUND = 1500  # default ground line (frame coords)


def build_cards():
    C = []

    def card(*a, **k):
        c = Card(*a, **k)
        C.append(c)
        return c

    # ============================ HOOK
    t0, tw, tb, tso = -0.2, at("hook", "wehrst"), at("hook", "bekommst"), at("hook", "So")
    c = card(t0, tb)
    c.text(t0, "", "DU WIRST *ANGEGRIFFEN*").text(tw, "", "DU *WEHRST* DICH")
    c.fig("you", GROUND, [(0, "guard", 380), (0.55, "guard", 380), (0.75, "hit", 360), (1.05, "guard", 370),
                          (tw + 0.05, "guard", 400), (tw + 0.3, "punch", 430), (tw + 0.55, "guard", 420),
                          (tw + 0.8, "punch", 450), (tw + 1.1, "guard", 440)], facing=1)
    c.fig("foe", GROUND, [(0, "guard", 760), (0.4, "guard", 700), (0.62, "punch", 640), (0.95, "guard", 680),
                          (tw + 0.25, "guard", 690), (tw + 0.42, "hit", 720), (tw + 0.6, "guard", 715),
                          (tw + 0.9, "hit", 760), (tw + 1.4, "lying", 800)], facing=-1)
    c = card(tb, tso)
    c.text(tb, "UND PLÖTZLICH BEKOMMST DU", "*EINE ANZEIGE?!*")
    c.prop(doc_page("Polizei · Vorgang Nr. 32/2026", "Strafanzeige", "wegen Körperverletzung (§ 223 StGB)."
                    " Beschuldigt: DU.", lines=5), 540, 1260, tb, rot=-3)
    c.prop(polaroid(photo_figs(("guard", "you", 1, 0.5, 0.75)), "beschuldigt"), 840, 1540, tb + 0.35, rot=6,
           enter="right")
    c.prop(stamp("ANZEIGE"), 520, 1460, at("hook", "Anzeige"), rot=-12, enter="stamp")
    c = card(tso, s1("hook"))
    c.text(tso, "SO IST DIE", "*RECHTSLAGE*", "IN DEUTSCHLAND")
    c.prop(toc_page(), 540, 1250, tso, rot=2)

    # ============================ 1 NOTWEHR
    B = (1, "NOTWEHR")
    a0, aW, aD, aWi, aU, aDas = (s0("notwehr"), at("notwehr", "Wirst"), at("notwehr", "darfst"),
                                 at("notwehr", "Wichtig"), at("notwehr", "Und"), at("notwehr", "Das"))
    c = card(a0, aW, B)
    c.text(a0, "", "*NOTWEHR*", "§ 32 STRAFGESETZBUCH")
    c.prop(doc_page("Strafgesetzbuch", "§ 32\nNotwehr",
                    "(2) Notwehr ist die Verteidigung, die erforderlich ist, um einen gegenwärtigen "
                    "rechtswidrigen Angriff von sich oder einem anderen abzuwenden.", lines=3), 540, 1270, a0 + 0.3, rot=-2)
    c = card(aW, aD, B)
    c.text(aW, "DER ANGRIFF IST", "*GEGENWÄRTIG*").text(at("notwehr", "rechtswidrig"), "UND", "*RECHTSWIDRIG*")
    c.prop(envelope("ANGRIFF"), 540, 960, aW, rot=-4, enter="drop")
    c.prop(polaroid(photo_figs(("guard", "you", 1, 0.3, 0.62), ("punch", "foe", -1, 0.68, 0.62)), "Nr. 1 · jetzt"),
           330, 1330, aW + 0.25, rot=-6, enter="left")
    c.prop(polaroid(photo_figs(("hit", "you", 1, 0.3, 0.62), ("push", "foe", -1, 0.66, 0.62)), "Nr. 2 · ohne Recht"),
           750, 1350, at("notwehr", "rechtswidrig"), rot=5, enter="right")
    c = card(aD, aWi, B)
    c.text(aD, "DU DARFST DICH", "*VERTEIDIGEN*").text(at("notwehr", "bleibst"), "UND BLEIBST", "*STRAFFREI*")
    c.prop(doc_page("Staatsanwaltschaft", "Einstellung\ndes Verfahrens",
                    "Die Tat war durch Notwehr gerechtfertigt (§ 32 StGB).", lines=4), 540, 1270, aD, rot=2)
    c.prop(stamp("KEINE\nSTRAFTAT", TEAL, 50), 560, 1490, at("notwehr", "straffrei"), rot=-8, enter="stamp")
    c = card(aWi, aU, B)
    c.text(aWi, "WICHTIG: DU NIMMST DAS", "*MILDESTE* MITTEL").text(at("notwehr", "das", 1), "DAS DEN ANGRIFF",
                                                                     "*SICHER* BEENDET")
    c.prop(polaroid(photo_figs(("guard", "you", 1, 0.32, 0.6), ("guard", "foe", -1, 0.68, 0.6)), "abwehren"),
           215, 1170, aWi + 0.15, rot=-5, enter="left")
    c.prop(polaroid(photo_figs(("push", "you", 1, 0.36, 0.6), ("hit", "foe", -1, 0.7, 0.6)), "wegstoßen"),
           540, 1150, aWi + 0.35, rot=2, enter="up")
    c.prop(polaroid(photo_figs(("punch", "you", 1, 0.34, 0.6), ("hit", "foe", -1, 0.7, 0.6)), "zuschlagen"),
           865, 1170, aWi + 0.55, rot=6, enter="right")
    c.prop(ruler(940), 540, 1510, aWi + 0.7, enter="up")
    c.prop(red_line(940), 540, 1585, at("notwehr", "das", 1), enter="wipe")
    c.prop(check_badge(), 640, 960, at("notwehr", "sicher"), enter="pop")
    c = card(aU, aDas, B)
    c.text(aU, "UND: NIEMAND MUSS", "*WEGLAUFEN*")
    c.prop(dashed_arrow(380), 250, 1380, aU + 0.2, enter="wipe")
    c.prop(cross_mark(), 250, 1380, at("notwehr", "weglaufen"), enter="stamp")
    c.fig("you", GROUND + 40, [(aU, "stand", 520), (aU + 0.6, "guard", 520)], facing=1)
    c.fig("foe", GROUND + 40, [(aU, "walk1", 980), (aU + 0.4, "walk2", 900), (aU + 0.8, "walk1", 830),
                               (aU + 1.1, "guard", 800)], facing=-1)
    c = card(aDas, s1("notwehr"), B)
    c.text(aDas, "DAS RECHT MUSS DEM UNRECHT", "*NICHT WEICHEN*")
    c.fig("you", GROUND + 40, [(aDas, "guard", 470), (aDas + 0.6, "push", 520), (aDas + 1.0, "guard", 520)], facing=1)
    c.fig("foe", GROUND + 40, [(aDas, "guard", 760), (aDas + 0.65, "hit", 820), (aDas + 1.1, "stand", 880)], facing=-1)
    c.prop(check_badge(), 520, 1080, at("notwehr", "weichen"), enter="pop")

    # ============================ 2 NOTWEHREXZESS
    B = (2, "NOTWEHREXZESS")
    e0, eH, eB, eD = s0("exzess"), at("exzess", "Hast"), at("exzess", "bleibst"), at("exzess", "Denn")
    c = card(e0, eH, B)
    c.text(e0, "", "NOTWEHR- *EXZESS*", "§ 33 STRAFGESETZBUCH")
    c.prop(doc_page("Strafgesetzbuch", "§ 33 Über-\nschreitung",
                    "Überschreitet der Täter die Grenzen der Notwehr aus Verwirrung, Furcht oder Schrecken, "
                    "so wird er nicht bestraft.", lines=3), 540, 1270, e0 + 0.3, rot=-2)
    c = card(eH, eB, B, dark=True)
    c.text(eH, "ZU HART REAGIERT AUS", "*FURCHT*").text(at("exzess", "Schrecken"), "ZU HART REAGIERT AUS",
                                                        "*SCHRECKEN*").text(
        at("exzess", "Verwirrung"), "ZU HART REAGIERT AUS", "*VERWIRRUNG*")
    c.fig("you", GROUND, [(eH, "cower", 470), (eH + 1.3, "cower", 470), (eH + 1.6, "punch", 520),
                          (eH + 1.85, "guard", 510), (eH + 2.1, "punch", 540), (eH + 2.4, "punch", 560)],
          facing=1, shake=(eH, eH + 1.3))
    c.fig("foe", GROUND, [(eH, "walk1", 900), (eH + 0.6, "walk2", 760), (eH + 1.1, "guard", 680),
                          (eH + 1.65, "hit", 720), (eH + 2.15, "hit", 760), (eH + 2.6, "lying", 800)], facing=-1)
    c = card(eB, eD, B)
    c.text(eB, "BLEIBST DU TROTZDEM OFT", "*STRAFFREI*")
    c.prop(doc_page("Amtsgericht · Im Namen des Volkes", "Urteil",
                    "Der Angeklagte wird freigesprochen. Er handelte aus Furcht und Schrecken (§ 33 StGB).",
                    lines=4), 540, 1270, eB, rot=-2)
    c.prop(stamp("STRAFFREI", TEAL, 56), 560, 1500, at("exzess", "straffrei"), rot=-9, enter="stamp")
    c = card(eD, s1("exzess"), B, dark=True)
    c.text(eD, "IN PANIK REAGIERT", "NIEMAND *PERFEKT*")
    c.fig("you", GROUND, [(eD, "cower", 540), (eD + 0.5, "shrug", 540), (eD + 1.2, "cower", 540),
                          (eD + 1.7, "shrug", 540)], facing=1, shake=(eD, eD + 3))

    # ============================ 3 DIE GRENZE
    B = (3, "DIE GRENZE")
    g0, gS, gW, gD, gB = (s0("grenze"), at("grenze", "Sobald"), at("grenze", "Wer"), at("grenze", "Das"),
                          at("grenze", "Bei"))
    c = card(g0, gS, B)
    c.text(g0, "ABER ACHTUNG, HIER IST", "DIE *GRENZE*")
    c.prop(ruler(960), 540, 1250, g0, enter="up")
    c.prop(red_line(960, 18), 540, 1335, g0 + 0.6, enter="wipe")
    c.fig("you", 1180, [(g0, "stand", 300)], facing=1, s=0.8)
    c.fig("foe", 1180, [(g0, "stand", 780)], facing=-1, s=0.8)
    c = card(gS, gW, B)
    c.text(gS, "SOBALD DER ANGREIFER", "*AM BODEN* LIEGT").text(at("grenze", "oder"), "ODER", "*AUFGIBT*").text(
        at("grenze", "Schluss"), "DANN IST", "*SCHLUSS!*")
    c.fig("foe", GROUND, [(gS, "guard", 720), (gS + 0.3, "hit", 750), (gS + 0.8, "lying", 790),
                          (at("grenze", "oder"), "lying", 790)], facing=-1)
    c.fig("you", GROUND, [(gS, "guard", 400), (at("grenze", "Schluss"), "guard", 400),
                          (at("grenze", "Schluss") + 0.5, "stand", 380)], facing=1)
    c.prop(red_line(380, 10).rotate(90, expand=True), 590, GROUND - 120, at("grenze", "Schluss"), enter="fade")
    c.prop(stamp("STOPP", RED, 60, fill=True), 560, 1000, at("grenze", "Schluss"), rot=-6, enter="stamp")
    c = card(gW, gD, B)
    c.text(gW, "WER JETZT", "*NACHTRITT*").text(at("grenze", "aus"), "ODER AUS", "*RACHE* WEITERSCHLÄGT").text(
        at("grenze", "verteidigt"), "VERTEIDIGT SICH NICHT MEHR", "ER *GREIFT AN*")
    keys = [(gW, "stand", 470)]
    tt = gW + 0.25
    while tt < gD - 0.5:
        keys += [(tt, "stand", 470), (tt + 0.25, "stomp", 500), (tt + 0.5, "stand", 470)]
        tt += 0.75
    c.fig("you", GROUND, keys, facing=1, recolor=(at("grenze", "greift"), "foe"))
    c.fig("foe", GROUND, [(gW, "lying", 760)], facing=-1)
    c.prop(stamp("STRAFTAT", RED, 58), 720, 1180, at("grenze", "greift"), rot=-8, enter="stamp")
    c = card(gD, gB, B)
    c.text(gD, "DAS IST", "*KÖRPER-* *VERLETZUNG*", "§ 223 STGB").text(at("grenze", "bis"), "§ 223 STGB · BIS ZU",
                                                                    "*5 JAHRE* HAFT")
    c.prop(doc_page("Staatsanwaltschaft", "Anklageschrift", "Der Angeschuldigte trat auf den bereits am Boden "
                    "liegenden Geschädigten ein. Strafbar gemäß § 223 StGB.", lines=3), 520, 1270, gD, rot=-2)
    c.prop(polaroid(photo_figs(("stomp", "foe", 1, 0.36, 0.55), ("lying", "grey", -1, 0.68, 0.55)), "nachgetreten"),
           830, 1530, gD + 0.4, rot=7, enter="right")
    c.prop(stamp("BIS 5 JAHRE", RED, 50), 520, 1520, at("grenze", "fünf"), rot=-7, enter="stamp")
    c = card(gB, s1("grenze"), B)
    c.text(gB, "BEI TRITTEN", "GEGEN DEN *KOPF*").text(at("grenze", "gefährliche"), "§ 224 STGB",
                                                         "GEFÄHRLICHE *KÖRPERVERLETZUNG*").text(
        at("grenze", "sechs"), "§ 224 STGB", "*6 MONATE* BIS *10 JAHRE*")
    c.prop(envelope("BEWEISMITTEL"), 560, 920, gB, rot=3, enter="drop")
    c.prop(polaroid(photo_figs(("kick", "foe", 1, 0.32, 0.55), ("lying", "grey", -1, 0.7, 0.55)), "Nr. 1 · Kopf"),
           300, 1300, gB + 0.25, rot=-6, enter="left")
    c.prop(polaroid(photo_shoe, "Nr. 2 · Schuh"), 760, 1320, gB + 0.5, rot=5, enter="right")
    c.prop(stamp("6 MON. – 10 J.", RED, 50, fill=True), 540, 1590, at("grenze", "sechs"), rot=-5, enter="stamp")

    # ============================ 4 TIPPS
    B = (4, "3 GOLDENE TIPPS")
    p0, p1, p2, p3, pS = (s0("tipps"), at("tipps", "Eins"), at("tipps", "Zwei"), at("tipps", "Drei", 1),
                          s1("tipps"))
    c = card(p0, p1, B)
    c.text(p0, "ZUM SCHLUSS", "3 GOLDENE *TIPPS*")
    c.prop(tip_card(1, "schweigen"), 230, 1250, p0 + 0.1, rot=-7, enter="left")
    c.prop(tip_card(2, "Attest +\nZeugen"), 540, 1220, p0 + 0.3, rot=0, enter="up")
    c.prop(tip_card(3, "Anwalt"), 850, 1250, p0 + 0.5, rot=7, enter="right")
    c = card(p1, p2, B)
    c.text(p1, "TIPP 1 · BEI DER POLIZEI", "ERST MAL *SCHWEIGEN*")

    def hand_note(d, S, x, y):
        d.text((x, y + 30 * S), "„Ich mache keine Angaben.“", font=font(F_HAND, 52 * S), fill=(30, 90, 160), anchor="lt")
    c.prop(doc_page("Polizei · Vernehmung", "Beschuldigten-\nvernehmung",
                    "Sie haben das Recht zu schweigen und einen Verteidiger zu befragen.", lines=1,
                    extra=hand_note), 540, 1270, p1, rot=-2)
    c.prop(check_badge(64), 820, 1520, at("tipps", "schweigen"), enter="pop")
    c = card(p2, p3, B)
    c.text(p2, "TIPP 2 · SOFORT VOM ARZT", "*ATTEST* HOLEN").text(at("tipps", "sichere"), "TIPP 2 · UND",
                                                                  "*ZEUGEN* SICHERN")

    def red_cross(d, S, x, y):
        cx, cy = x + 440 * S, 80 * S
        d.rectangle([cx - 14 * S, cy - 44 * S, cx + 14 * S, cy + 44 * S], fill=RED)
        d.rectangle([cx - 44 * S, cy - 14 * S, cx + 44 * S, cy + 14 * S], fill=RED)
    c.prop(doc_page("Praxis Dr. med.", "Ärztliches\nAttest", "Befund: Prellungen, Hämatom am Unterarm, "
                    "Platzwunde. Datum + Uhrzeit dokumentiert.", lines=2, accent=(250, 205, 205),
                    extra=red_cross), 420, 1270, p2, rot=-3)
    c.prop(polaroid(photo_figs(("stand", "grey", 1, 0.5, 0.6)), "Zeuge 1"), 840, 1040,
           at("tipps", "sichere"), rot=6, enter="right")
    c.prop(polaroid(photo_figs(("stand", "grey", -1, 0.5, 0.6)), "Zeuge 2"), 800, 1480,
           at("tipps", "Zeugen") + 0.1, rot=-4, enter="right")
    c = card(p3, pS, B)
    c.text(p3, "TIPP 3 · SCHALTE EINEN", "*FACHANWALT* EIN", "FÜR STRAFRECHT")
    c.prop(business_card(), 540, 1230, p3 + 0.2, rot=-3)
    c.prop(check_badge(64), 820, 1050, at("tipps", "Strafrecht"), enter="pop")

    # ============================ CTA: question to the viewers
    q0 = s0("cta")
    c = card(q0, s1("cta"))
    c.text(q0, "UND JETZT SEID IHR DRAN", "EURE *ERFAHRUNG?*")
    c.prop(question_bubble(), 540, 1110, q0 + 0.05, enter="pop")
    c.prop(cta_pill("💬", "Schreibt's in die Kommentare!", INK), 540, 1450, at("cta", "Schreibt"), enter="pop")
    c.prop(cta_pill("📌", "Speichern für den Ernstfall", TEAL), 540, 1580, at("cta", "speichert"), enter="pop")
    return C


# ------------------------------------------------------------------ backgrounds / header
def make_bg(dark):
    y = np.linspace(0, 1, H)[:, None]
    if not dark:
        top = np.array([255, 255, 255], np.float32)
        mid = np.array([228, 233, 236], np.float32)
        bot = np.array([212, 219, 223], np.float32)
        t1 = np.clip((y - 0.22) / 0.16, 0, 1)
        t2 = np.clip((y - 0.38) / 0.62, 0, 1)
        g = top + (mid - top) * t1[..., None]
        g = g + (bot - mid) * t2[..., None]
    else:
        top = np.array([28, 33, 39], np.float32)
        bot = np.array([42, 48, 56], np.float32)
        g = top + (bot - top) * y[..., None]
    arr = np.repeat(g, W, axis=1)
    if dark:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / 430) ** 2 + ((yy - 1330) / 430) ** 2)
        light = np.clip(1 - r, 0, 1) ** 0.8
        arr = arr + (np.array([245, 247, 248]) - arr) * light[..., None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")


def parse_rich(text):
    out, hl = [], False
    for tok in text.split(" "):
        if tok.startswith("*"):
            hl, tok = True, tok[1:]
        end = tok.endswith("*") or tok.rstrip("!?.").endswith("*")
        if end:
            tok = tok.replace("*", "")
        out.append((tok, hl))
        if end:
            hl = False
    return out


@lru_cache(maxsize=512)
def head_layout(head):
    """Return (size, lines) where lines = list of [(word, hl)], fitting 980px."""
    words = parse_rich(head)
    for size in range(124, 50, -4):
        f = font(F_HEAD, size)
        space = f.getlength(" ")
        lines, cur, cw = [], [], 0
        ok = True
        for w, hl in words:
            ww = f.getlength(w)
            if ww > 980:
                ok = False
                break
            gap = 0 if (cur and cur[-1][0].endswith("-")) else space
            if cur and cw + gap + ww > 980:
                lines.append(cur)
                cur, cw, gap = [], 0, 0
            cur.append((w, hl))
            cw += (gap if len(cur) > 1 else 0) + ww
        if cur:
            lines.append(cur)
        if ok and len(lines) <= 2:
            return size, lines
    return size, lines


def draw_header(frame, card, t):
    d = ImageDraw.Draw(frame)
    dark = card.dark
    if card.badge:
        n, label = card.badge
        bg = (52, 62, 74) if dark else INK
        d.rounded_rectangle([56, 74, 128, 146], radius=18, fill=bg)
        d.text((92, 111), str(n), font=font(F_HEAD, 40), fill=PAPER, anchor="mm")
        text_tracked(d, (150, 124), label.upper(), font(F_HEAD_B, 28), (150, 158, 166) if dark else GREY, 2,
                     anchor_center=False)
    st = None
    for s in card.texts:
        if t >= s[0] - 0.001:
            st = s
    if st is None:
        st = card.texts[0]
    t_state, kicker, head, sub = st
    # typing: kicker continues if unchanged from previous state
    prev = [s for s in card.texts if s[0] < t_state]
    k_start = t_state
    for s in reversed(prev):
        if s[1] == kicker:
            k_start = s[0]
        else:
            break
    CPS = 42.0
    kcol = (150, 160, 168) if dark else GREY
    hcol = PAPER if dark else INK
    y = 255
    if kicker:
        fk = font(F_HEAD_B, 36)
        lines = wrap_lines(kicker, fk, 960)
        n = int((t - k_start) * CPS)
        for ln in lines:
            vis = ln[:max(0, n)]
            if vis:
                full = sum(fk.getlength(c) for c in ln) + 3 * (len(ln) - 1)
                x = W / 2 - full / 2
                for c in vis:
                    d.text((x, y), c, font=fk, fill=kcol, anchor="ls")
                    x += fk.getlength(c) + 3
            n -= len(ln)
            y += 52
        y += 8
        h_start = t_state + (0.15 if k_start == t_state else 0)
    else:
        y = 300
        h_start = t_state
    size, lines = head_layout(head)
    fh = font(F_HEAD, size)
    n_total = (t - h_start) * CPS * 1.15
    idx = 0
    y += size * 0.95
    for ln in lines:
        space = fh.getlength(" ")
        full = sum(fh.getlength(w) for w, _ in ln) + space * sum(1 for w, _ in ln[:-1] if not w.endswith("-"))
        x = W / 2 - full / 2
        for w, hl in ln:
            col = TEAL if hl else hcol
            if hl and any(k in head for k in ("ANZEIGE", "WEGLAUFEN", "FURCHT", "SCHRECKEN", "VERWIRRUNG",
                                              "GRENZE", "SCHLUSS", "NACHTRITT", "RACHE", "GREIFT",
                                              "VERLETZUNG", "JAHRE", "KOPF", "MONATE", "AUFGIBT", "AM BODEN")):
                col = RED
            for ch in w:
                prog = clamp01((n_total - idx) / 4.0)
                if prog > 0:
                    dy = (1 - ease_out(prog)) * -size * 0.35
                    if prog < 1:
                        a = int(255 * prog)
                        tmp = Image.new("RGBA", (int(size * 1.3), int(size * 1.6)), (0, 0, 0, 0))
                        ImageDraw.Draw(tmp).text((0, size * 1.2), ch, font=fh, fill=col + (a,), anchor="ls")
                        frame.alpha_composite(tmp, (int(x), int(y + dy - size * 1.2)))
                    else:
                        d.text((x, y), ch, font=fh, fill=col, anchor="ls")
                x += fh.getlength(ch)
                idx += 1
            if not w.endswith("-"):
                x += space
            idx += 1
        y += size * 1.12
    if sub:
        fs = font(F_HEAD_B, 34)
        prog = clamp01((t - h_start - len(head) / (CPS * 1.15)) / 0.3)
        if prog > 0:
            tmp = Image.new("RGBA", (W, 70), (0, 0, 0, 0))
            text_tracked(ImageDraw.Draw(tmp), (W / 2, 50), sub, fs, kcol + (int(255 * prog),), 3)
            frame.alpha_composite(tmp, (0, int(y - 30)))


# ------------------------------------------------------------------ frame
BG = {}
CARDS = []


def init():
    global CARDS
    BG[False] = make_bg(False)
    BG[True] = make_bg(True)
    CARDS = build_cards()
    CAPS[:] = build_caps()


def card_at(t):
    cur = CARDS[0]
    for c in CARDS:
        if t >= c.start:
            cur = c
    return cur


# ------------------------------------------------------------------ trend layer: emojis, captions, progress
F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
F_CAP = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
CARD_EMOJI = ["🥊", "🚨", "⚖️", "🛡️", "👊", "✅", "🤏", "🙅", "💪", "😰", "😱", "✅", "😵",
              "🛑", "✋", "🚫", "🚔", "⛓️", "💡", "🤐", "🩺", "💼", "💬"]
YELLOW = (255, 226, 0)


@lru_cache(maxsize=64)
def emoji_img(ch, size=150):
    f = ImageFont.truetype(F_EMOJI, 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((80, 80), ch, font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox())
    sc = size / max(im.size)
    im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
    return with_shadow(im, dy=8, blur=10, alpha=0.25, pad=30)


def draw_emoji(frame, card, idx, t):
    if idx >= len(CARD_EMOJI):
        return
    p = (t - card.start - 0.25) / 0.35
    if p <= 0:
        return
    img = emoji_img(CARD_EMOJI[idx])
    sc = 0.2 + 0.8 * ease_back(p, 2.4)
    rot = 12 + math.sin(t * 3.2) * 6
    img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    img = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))), Image.BICUBIC)
    y = 770 + math.sin(t * 2.4) * 10
    frame.alpha_composite(img, (int(915 - img.width / 2), int(y - img.height / 2)))


def build_caps():
    caps = []
    for si, sc in enumerate(TIM):
        words = [dict(text=w["text"].replace("Paragraf", "§").rstrip("."), start=OFF[si] + w["start"],
                      end=OFF[si] + w["end"]) for w in sc["words"]]
        merged, skip = [], False
        for i, w in enumerate(words):
            if skip:
                skip = False
                continue
            if w["text"] == "§" and i + 1 < len(words):
                merged.append(dict(text="§ " + words[i + 1]["text"], start=w["start"], end=words[i + 1]["end"]))
                skip = True
            else:
                merged.append(w)
        sw = SCENES[si]["text"].replace(" –", ",").split()
        punct, j = set(), 0
        for i, w in enumerate(sc["words"]):
            j += len(w["text"].split())
            if j - 1 < len(sw) and sw[j - 1][-1] in ",.:!?":
                punct.add(w["text"].replace("Paragraf", "§").rstrip("."))
        chunk = []
        for i, w in enumerate(merged):
            if chunk and (len(chunk) >= 3 or sum(len(x["text"]) for x in chunk) + len(w["text"]) > 18):
                caps.append(chunk)
                chunk = []
            chunk.append(w)
            if w["text"].split()[-1] in punct or w["text"] in punct:
                caps.append(chunk)
                chunk = []
        if chunk:
            caps.append(chunk)
    out = []
    for i, ch in enumerate(caps):
        nxt = caps[i + 1][0]["start"] if i + 1 < len(caps) else TOTAL
        out.append(dict(words=ch, start=ch[0]["start"], end=min(nxt, ch[-1]["end"] + 0.5)))
    return out


@lru_cache(maxsize=2048)
def cap_img(ci, active):
    c = CAPS[ci]
    f = font(F_CAP, 76)
    sp = f.getlength(" ")
    ws = [f.getlength(w["text"]) for w in c["words"]]
    tw = sum(ws) + sp * (len(ws) - 1)
    im = Image.new("RGBA", (int(tw + 60), 130), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 30
    for i, (w, ww) in enumerate(zip(c["words"], ws)):
        d.text((x, 65), w["text"], font=f, fill=YELLOW if i == active else PAPER, anchor="lm",
               stroke_width=10, stroke_fill=(0, 0, 0))
        x += ww + sp
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(8)).point(lambda v: int(v * 0.5)))
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (0, 5))
    out.alpha_composite(im)
    return out


def draw_caption(frame, t):
    if t >= s0("cta") - 0.05:   # the question itself is shown big on screen
        return
    for ci, c in enumerate(CAPS):
        if c["start"] <= t < c["end"]:
            act = max([i for i, w in enumerate(c["words"]) if t >= w["start"]] or [0])
            img = cap_img(ci, act)
            p = clamp01((t - c["start"]) / 0.12)
            sc = (0.85 + 0.15 * ease_back(p, 2.0)) * min(1.0, 1000 / img.width)
            if abs(sc - 1) > 0.01:
                img = img.resize((int(img.width * sc), int(img.height * sc)), Image.BICUBIC)
            frame.alpha_composite(img, (int(W / 2 - img.width / 2), int(1610 - img.height / 2)))
            return


def draw_progress(frame, t, dark):
    d = ImageDraw.Draw(frame)
    d.rounded_rectangle([40, 30, W - 40, 38], radius=4, fill=(255, 255, 255, 60) if dark else (0, 0, 0, 25))
    d.rounded_rectangle([40, 30, 40 + (W - 80) * clamp01(t / TOTAL), 38], radius=4, fill=TEAL)


CAPS = []


SS = 2


def render_frame(fi):
    t = fi / FPS
    card = card_at(t)
    frame = BG[card.dark].copy()

    # stage: props + figures, gentle camera push
    layer = Image.new("RGBA", (W, STAGE_H), (0, 0, 0, 0))
    out = clamp01((t - (card.end - 0.12)) / 0.12) if card is not CARDS[-1] else 0
    for p in sorted(card.props, key=lambda p: p.z):
        p.draw(layer, t, out)
    if card.figs:
        fl = Image.new("RGBA", (W * SS, STAGE_H * SS), (0, 0, 0, 0))
        fd = ImageDraw.Draw(fl)
        for f in card.figs:
            f.draw(fd, t, SS, dy=-STAGE_Y)
        fl = fl.resize((W, STAGE_H), Image.BILINEAR)
        # props drawn after figures should be on top (stamps); keep simple: figures under stamps
        base = Image.new("RGBA", (W, STAGE_H), (0, 0, 0, 0))
        base.alpha_composite(fl)
        base.alpha_composite(layer)
        layer = base
    life = clamp01((t - card.start) / max(1.0, card.end - card.start))
    zoom = 1.0 + 0.05 * ease_io(life)
    if zoom > 1.001:
        zw, zh = int(W * zoom), int(STAGE_H * zoom)
        layer = layer.resize((zw, zh), Image.BILINEAR)
        cx = (zw - W) // 2
        cy = int((zh - STAGE_H) * 0.45)
        layer = layer.crop((cx, cy, cx + W, cy + STAGE_H))
    frame.alpha_composite(layer, (0, STAGE_Y))

    hl = Image.new("RGBA", (W, STAGE_Y), (0, 0, 0, 0))
    draw_header(hl, card, t)
    ts = max([s[0] for s in card.texts if s[0] <= t] or [card.start])
    punch = 1 + 0.08 * (1 - ease_out((t - ts) / 0.2))
    if punch > 1.003:
        hl = hl.resize((int(W * punch), int(STAGE_Y * punch)), Image.BICUBIC)
        hl = hl.crop((int((hl.width - W) / 2), int((hl.height - STAGE_Y) * 0.45),
                      int((hl.width - W) / 2) + W, int((hl.height - STAGE_Y) * 0.45) + STAGE_Y))
    frame.alpha_composite(hl)
    draw_emoji(frame, card, CARDS.index(card), t)
    draw_caption(frame, t)
    draw_progress(frame, t, card.dark)
    return frame.convert("RGB").tobytes()


# ------------------------------------------------------------------ sound design (synthesised)
SR = 48000


def _env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)


def sfx_whoosh(rng):
    n = int(0.42 * SR)
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


def sfx_thud(rng):
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (60 + 80 * np.exp(-t * 30)) * t) * _env(n, 0.001, 0.08)
    click = rng.standard_normal(n) * _env(n, 0.0005, 0.012) * 0.5
    return (body + click) * 0.9


def sfx_tick():
    n = int(0.03 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * 2400 * t) * _env(n, 0.0005, 0.006) * 0.25


def beat_bed(dur, bpm=96):
    rng = np.random.default_rng(3)
    n = int(dur * SR)
    out = np.zeros(n)
    beat = 60 / bpm
    kick_n = int(0.3 * SR)
    kt = np.arange(kick_n) / SR
    kick = np.sin(2 * np.pi * (48 + 90 * np.exp(-kt * 25)) * kt) * _env(kick_n, 0.001, 0.12)
    hat_n = int(0.04 * SR)
    hat = np.diff(rng.standard_normal(hat_n + 1)) * _env(hat_n, 0.0005, 0.01) * 0.25
    # soft minor pad (A minor / F major alternating)
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 246.94, 293.66], [164.81, 196.0, 246.94]]
    i = 0
    tb = 0.0
    while tb < dur:
        s0 = int(tb * SR)
        bar_beat = i % 4
        if bar_beat in (0, 2):
            seg = kick[: max(0, min(kick_n, n - s0))]
            out[s0:s0 + len(seg)] += seg * 0.8
        for half in (0.5,):
            h0 = int((tb + beat * half) * SR)
            seg = hat[: max(0, min(hat_n, n - h0))]
            out[h0:h0 + len(seg)] += seg
        if bar_beat == 0:
            ch = chords[(i // 4) % 4]
            L = int(beat * 4 * SR)
            pt = np.arange(min(L, n - s0)) / SR
            pad = sum(np.sin(2 * np.pi * f * pt) + 0.3 * np.sin(4 * np.pi * f * pt) for f in ch)
            pad *= np.minimum(1, pt / 0.4) * np.minimum(1, (L / SR - pt) / 0.4) * 0.05
            out[s0:s0 + len(pad)] += pad
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

    for k, c in enumerate(CARDS):
        if k:
            put(sfx_whoosh(rng) * 0.55, c.start - 0.12)
        put(sfx_pop() * 0.8, c.start + 0.3)            # emoji pop
        for st in c.texts[1:]:
            put(sfx_tick() * 2, st[0])
        for pr in c.props:
            if pr.enter == "stamp":
                put(sfx_thud(rng), pr.t + 0.12)
            elif pr.enter == "pop":
                put(sfx_pop(), pr.t + 0.1)
    bed = beat_bed(TOTAL)
    mix = np.zeros(n)
    mix[: len(out)] += out * 0.5
    mix[: len(bed)] += bed * 0.22
    mix = np.clip(mix, -1, 1)
    import wave
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
            Image.frombytes("RGB", (W, H), render_frame(int(tt * FPS))).save(
                BUILD / "stills" / f"t{tt:05.1f}.png")
        return
    out = ROOT / "notwehr-video.mp4"
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
                    "[1:a]volume=0.55[s];[0:a][s]amix=inputs=2:normalize=0:duration=first,"
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
