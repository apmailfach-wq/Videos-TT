"""Render fuehrerschein-video.mp4 (1080x1920, 30 fps) in a flat "explainer" look.

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

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / os.environ.get("VOICE_DIR", "unfall2")
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


TEAM = {"you": (TEAL_F, TEAL_B), "foe": (NAVY, NAVY_B), "grey": ((120, 130, 140), (150, 158, 166)),
        "klaus": ((236, 128, 38), (200, 98, 22)), "cop": ((38, 72, 160), (64, 96, 180))}


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

    def __init__(self, team, y, keys, facing=1, s=1.45, recolor=None, shake=None, gloves=None):
        self.team, self.y, self.keys, self.facing, self.s = team, y, keys, facing, s
        self.gloves = gloves
        self.recolor = recolor  # (t, team) -> morph colours
        self.shake = shake      # (t0, t1) trembling

    def state(self, t):
        ks = [k if len(k) == 4 else (k[0], k[1], k[2], 0) for k in self.keys]
        self._dy = ks[0][3]
        if t <= ks[0][0]:
            return POSES[ks[0][1]], ks[0][2]
        for (ta, pa, xa, ya), (tb, pb, xb, yb) in zip(ks, ks[1:]):
            if ta <= t < tb:
                u = ease_io((t - ta) / (tb - ta))
                self._dy = lerp(ya, yb, u)
                return lerp_pose(POSES[pa], POSES[pb], u), lerp(xa, xb, u)
        self._dy = ks[-1][3]
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
        gx, gy = x + dx, self.y + dy + self._dy
        sw = 70 * self.s
        d.ellipse([(gx - sw) * ss, (gy - 12 * self.s) * ss, (gx + sw) * ss, (gy + 12 * self.s) * ss],
                  fill=(20, 30, 40, 34))
        draw_figure(d, pts, gx, gy, self.s, cf, cb, ss)
        if self.gloves:
            for k in ("hb", "hf"):
                hx, hy = (gx + pts[k][0]) * ss, (gy + pts[k][1]) * ss
                r = 27 * self.s * ss
                d.ellipse([hx - r, hy - r, hx + r, hy + r], fill=self.gloves)
                d.ellipse([hx - r * 0.55, hy - r * 0.75, hx + r * 0.05, hy - r * 0.2], fill=(255, 255, 255, 90))
                d.ellipse([hx - r * 0.8, hy + r * 0.35, hx + r * 0.8, hy + r * 1.05], fill=PAPER)


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


def toc_page(header="STRAFGESETZBUCH", title="StGB", rows=None):
    w, h = 640, 800

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 18 * S, (w - 6) * S, h * S], radius=10 * S, fill=(196, 204, 210))
        d.rounded_rectangle([14 * S, 0, w * S, (h - 14) * S], radius=10 * S, fill=PAPER)
        x = 60 * S
        d.text((x, 80 * S), header, font=font(F_HEAD_B, 20 * S), fill=(150, 158, 165), anchor="ls")
        d.text((x, 150 * S), title, font=font(F_HEAD, 64 * S), fill=INK, anchor="ls")
        y = 230 * S
        for p, t, c in rows:
            d.rectangle([x - 8 * S, y - 6 * S, x + 520 * S, y + 62 * S], fill=c)
            d.text((x + 6 * S, y + 28 * S), p, font=font(F_HEAD, 26 * S), fill=INK, anchor="lm")
            d.text((x + 250 * S, y + 28 * S), t, font=font(F_BODY_B, 30 * S), fill=INK, anchor="lm")
            y += 100 * S
        for i in range(4):
            d.rounded_rectangle([x, y + 10 * S, x + (380 - i * 40) * S, y + 22 * S], radius=6 * S,
                                fill=(222, 227, 231))
            y += 36 * S
    return with_shadow(supersample(w, h, fn))


QUESTION = ("Wer *zahlt?* Wer *haftet?* Wer ist *schuld?* *Autofahrer* oder *Radfahrer?*")


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
                col = (ORANGE if "AUTO" in wd else RED if "SCHULD" in wd else TEAL) if hl else INK
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


RED_KEYS = ("K.O.", "RING", "POLIZEI", "WAHNSINN", "AUTO", "STIRN", "MOTORHAUBE", "KAPUTT", "ACHTER", "SCHULTER", "DELLE", "BEULE",
            "SCHLECHTE", "ANGEFANGEN", "KÜRZEN", "§", "SCHULD", "HANDY", "REPARATUR", "AUFEINANDER")
ORANGE = (236, 128, 38)


def car_flat(col, w=560):
    h = int(w * 0.46)

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([w * 0.2 * S, 0, w * 0.78 * S, h * 0.55 * S], radius=40 * S, fill=lerp_col(col, (20, 20, 30), 0.15))
        d.rounded_rectangle([w * 0.25 * S, 18 * S, w * 0.48 * S, h * 0.46 * S], radius=18 * S, fill=(205, 228, 240))
        d.rounded_rectangle([w * 0.51 * S, 18 * S, w * 0.73 * S, h * 0.46 * S], radius=18 * S, fill=(205, 228, 240))
        d.rounded_rectangle([0, h * 0.38 * S, w * S, h * 0.82 * S], radius=36 * S, fill=col)
        d.rounded_rectangle([w * 0.9 * S, h * 0.48 * S, w * S, h * 0.6 * S], radius=8 * S, fill=(255, 236, 160))
        d.rounded_rectangle([0, h * 0.48 * S, w * 0.06 * S, h * 0.6 * S], radius=8 * S, fill=(240, 80, 80))
        for fx in (0.22, 0.78):
            cx, cy, r = w * fx * S, h * 0.8 * S, h * 0.19 * S
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(40, 44, 52))
            d.ellipse([cx - r * 0.45, cy - r * 0.45, cx + r * 0.45, cy + r * 0.45], fill=(200, 205, 212))
    return with_shadow(supersample(w, h, fn), dy=10, blur=12)


def beer_glass(w=130):
    h = int(w * 1.5)

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, h * 0.18 * S, w * 0.8 * S, h * S], radius=16 * S, fill=(246, 184, 40))
        d.rounded_rectangle([w * 0.72 * S, h * 0.38 * S, w * S, h * 0.75 * S], radius=18 * S, outline=(230, 236, 240),
                            width=int(10 * S))
        d.ellipse([-6 * S, 0, w * 0.86 * S, h * 0.32 * S], fill=PAPER)
        for k in range(5):
            x = w * (0.15 + 0.12 * k) * S
            y = h * (0.45 + 0.08 * (k % 3)) * S
            d.ellipse([x, y, x + 9 * S, y + 9 * S], fill=(255, 236, 170))
    return with_shadow(supersample(w, h, fn), dy=8, blur=10)


def license_card():
    w, h = 720, 460

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=36 * S, fill=(250, 196, 214))
        d.rounded_rectangle([0, 0, w * S, 96 * S], radius=36 * S, fill=(214, 84, 140))
        d.rectangle([0, 60 * S, w * S, 96 * S], fill=(214, 84, 140))
        d.text((40 * S, 50 * S), "FÜHRERSCHEIN", font=font(F_HEAD, 44 * S), fill=PAPER, anchor="lm")
        d.rounded_rectangle([40 * S, 130 * S, 240 * S, 400 * S], radius=18 * S, fill=(214, 222, 236))
        d.ellipse([95 * S, 165 * S, 185 * S, 255 * S], fill=(120, 130, 150))
        d.chord([70 * S, 255 * S, 210 * S, 420 * S], 180, 360, fill=(120, 130, 150))
        for i, t in enumerate(["1. KOLLEGE", "2. FUSSBALLFAN", "4a. 2026", "9. B"]):
            d.text((280 * S, (170 + i * 58) * S), t, font=font(F_HEAD_B, 28 * S), fill=(110, 50, 90), anchor="lm")
    return with_shadow(supersample(w, h, fn))


def breathalyzer(val="0,5 ‰"):
    w, h = 260, 470

    def fn(im, d, ss):
        S = ss
        d.rectangle([110 * S, 0, 150 * S, 50 * S], fill=(230, 233, 236))
        d.rounded_rectangle([0, 40 * S, w * S, h * S], radius=50 * S, fill=(250, 204, 21))
        d.rounded_rectangle([30 * S, 100 * S, 230 * S, 230 * S], radius=18 * S, fill=(20, 24, 22))
        d.text((130 * S, 168 * S), val, font=font(F_HEAD, 48 * S), fill=(255, 90, 90), anchor="mm")
        d.ellipse([90 * S, 300 * S, 170 * S, 380 * S], fill=(40, 44, 50))
    return with_shadow(supersample(w, h, fn))


def promille_chart():
    w, h = 900, 560

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=26 * S, fill=PAPER)
        x0, y0, x1, y1 = 110, 60, 860, 460
        d.line([(x0 * S, y0 * S), (x0 * S, y1 * S), (x1 * S, y1 * S)], fill=(150, 158, 166), width=4 * S)
        def Y(v):
            return y1 - (v / 1.3) * (y1 - y0)
        for v in (0.5, 1.0):
            d.text(((x0 - 18) * S, Y(v) * S), f"{v:.1f}".replace(".", ","), font=font(F_HEAD_B, 24 * S),
                   fill=(120, 128, 136), anchor="rm")
        # 0,5 limit dashed
        x = x0
        while x < x1:
            d.line([(x * S, Y(0.5) * S), (min(x1, x + 26) * S, Y(0.5) * S)], fill=RED, width=5 * S)
            x += 44
        d.text(((x1 - 4) * S, (Y(0.5) - 26) * S), "Grenze 0,5 ‰", font=font(F_HEAD_B, 24 * S), fill=RED, anchor="rm")
        pts = []
        for k in range(41):
            u = k / 40
            v = 1.25 - 0.1 * 7.5 * u if u > 0.08 else 1.0 + 3.1 * u
            pts.append(((x0 + 20 + u * (x1 - x0 - 40)) * S, Y(max(0.0, v)) * S))
        d.line(pts, fill=ORANGE, width=12 * S, joint="curve")
        d.ellipse([pts[-1][0] - 16 * S, pts[-1][1] - 16 * S, pts[-1][0] + 16 * S, pts[-1][1] + 16 * S], fill=RED)
        for u, lab in ((0.0, "23:00"), (0.5, "03:00"), (1.0, "06:30")):
            d.text(((x0 + 20 + u * (x1 - x0 - 40)) * S, (y1 + 36) * S), lab, font=font(F_HEAD_B, 24 * S),
                   fill=(120, 128, 136), anchor="mm")
        d.text((x0 * S, 30 * S), "Promille im Blut (Beispiel)", font=font(F_HEAD_B, 24 * S), fill=INK, anchor="lm")
        d.text(((x0 + 20 + 0.5 * (x1 - x0 - 40)) * S, Y(0.98) * S), "Abbau nur ca. 0,1–0,15 ‰ pro Stunde",
               font=font(F_BODY_B, 26 * S), fill=(80, 86, 94), anchor="mm")
    return with_shadow(supersample(w, h, fn))


def emoji_card(ch, text, w=300, h=330):
    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=26 * S, fill=PAPER)
        for i, ln in enumerate(text.split("\n")):
            d.text((w / 2 * S, (240 + i * 48) * S), ln, font=font(F_HEAD, 34 * S), fill=INK, anchor="mm")
    base = supersample(w, h, fn)
    e = emoji_img(ch, 140)
    base.alpha_composite(e, ((w - e.width) // 2, 20))
    return with_shadow(base, dy=10, blur=12)


def big_emoji(ch, size=260):
    return emoji_img(ch, size)


def bubble(text, col=TEAL):
    lines = text.split("\n")
    f = font(F_HAND, 64)
    tw = max(f.getlength(l) for l in lines)
    w, h = int(tw + 110), int(76 * len(lines) + 80)

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=40 * S, fill=PAPER, outline=col, width=6 * S)
        for i, ln in enumerate(lines):
            d.text((w / 2 * S, (60 + i * 76) * S), ln, font=font(F_HAND, 64 * S), fill=INK, anchor="mm")
    im = supersample(w, h + 70, lambda im, d, ss: (fn(im, d, ss), d.polygon(
        [(70 * ss, (h - 3) * ss), (150 * ss, (h - 3) * ss), (40 * ss, (h + 64) * ss)], fill=PAPER)))
    return with_shadow(im, dy=10, blur=14)


def clock_card(txt="06:30"):
    w, h = 400, 190

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=30 * S, fill=INK)
        d.text((w / 2 * S, h / 2 * S), txt, font=font(F_HEAD, 92 * S), fill=(120, 255, 200), anchor="mm")
    return with_shadow(supersample(w, h, fn))


def disclaimer():
    w, h = 900, 60

    def fn(im, d, ss):
        d.text((w / 2 * ss, h / 2 * ss), "Angaben ohne Gewähr · Stand 2026 · keine Rechtsberatung",
               font=font(F_BODY_B, 28 * ss), fill=(120, 128, 136), anchor="mm")
    return supersample(w, h, fn)


# ------------------------------------------------------------------ accident props (flat style)
CAR_BLUE = (70, 120, 190)


def car_dmg(col=ORANGE, w=560, dent=True):
    img = car_flat(col, w)
    if not dent:
        return img
    im = img.copy()
    d = ImageDraw.Draw(im)
    h = int(w * 0.46)
    ox, oy = (im.width - w) // 2, (im.height - h) // 2 - 4
    # dent + scratches on the front (right side)
    cx, cy = ox + w * 0.84, oy + h * 0.6
    d.ellipse([cx - w * 0.07, cy - h * 0.1, cx + w * 0.07, cy + h * 0.1], fill=lerp_col(col, (0, 0, 0), 0.35))
    d.arc([cx - w * 0.07, cy - h * 0.1, cx + w * 0.07, cy + h * 0.1], 200, 340, fill=(255, 255, 255), width=4)
    rnd = random.Random(5)
    for k in range(6):
        x0 = ox + w * rnd.uniform(0.6, 0.86)
        y0 = oy + h * rnd.uniform(0.45, 0.7)
        d.line([(x0, y0), (x0 + rnd.uniform(30, 70), y0 + rnd.uniform(-8, 8))], fill=(255, 255, 255), width=3)
    return im


def wheel_img(t, R=210, buckle=1.0, spin_speed=5.0):
    """Flat front wheel with a clearly visible 'Achter' that wobbles while spinning."""
    S2 = 2
    size = int(R * 2.7)

    def fn(im, d, ss):
        c = size / 2 * ss
        r = R * ss
        spin = t * spin_speed
        yaw = 0.9
        B = r * 0.24 * buckle
        rim, tire = [], []
        for k in range(121):
            th = k / 120 * math.tau
            z = B * (math.sin(2 * (th - spin) + 0.4) + 0.3 * math.sin(3 * (th - spin)))
            X = r * math.cos(th) * math.cos(yaw) + z * math.sin(yaw)
            rim.append((c + X, c + r * math.sin(th)))
            Xt = r * 1.1 * math.cos(th) * math.cos(yaw) + z * math.sin(yaw)
            tire.append((c + Xt, c + r * 1.1 * math.sin(th)))
        d.line(tire, fill=INK, width=int(r * 0.15), joint="curve")
        d.line(rim, fill=(200, 206, 214), width=int(r * 0.05), joint="curve")
        for k in range(0, 120, 6):
            d.line([(c, c), rim[k]], fill=(170, 178, 186), width=max(2, int(r * 0.014)))
        d.ellipse([c - r * 0.09, c - r * 0.09, c + r * 0.09, c + r * 0.09], fill=GREY)
        d.line([(c, c), (c - r * 0.18, c - r * 1.4)], fill=TEAL, width=int(r * 0.08))
    return supersample(size, size, fn, S2)


def bike_flat(w=520, buckle=False):
    h = int(w * 0.62)

    def fn(im, d, ss):
        S = ss
        R = h * 0.3
        rw, fw = (w * 0.24, h * 0.66), (w * 0.78, h * 0.66)
        bb = (w * 0.48, h * 0.7)
        seat, head = (w * 0.38, h * 0.26), (w * 0.7, h * 0.24)
        for i, (x, y) in enumerate((rw, fw)):
            if buckle and i == 1:
                d.ellipse([(x - R * 0.75) * S, (y - R) * S, (x + R * 0.8) * S, (y + R) * S], outline=INK,
                          width=int(16 * S))
            else:
                d.ellipse([(x - R) * S, (y - R) * S, (x + R) * S, (y + R) * S], outline=INK, width=int(16 * S))
        for a, b in ((rw, bb), (rw, seat), (bb, seat), (bb, head), (seat, head), (head, fw)):
            d.line([(a[0] * S, a[1] * S), (b[0] * S, b[1] * S)], fill=TEAL_F, width=int(14 * S))
        d.rounded_rectangle([(seat[0] - 40) * S, (seat[1] - 22) * S, (seat[0] + 30) * S, (seat[1] - 6) * S],
                            radius=8 * S, fill=INK)
        d.line([(head[0] * S, head[1] * S), ((head[0] + 10) * S, (head[1] - 40) * S)], fill=INK, width=int(10 * S))
        d.line([((head[0] - 20) * S, (head[1] - 44) * S), ((head[0] + 40) * S, (head[1] - 40) * S)], fill=INK,
               width=int(12 * S))
    return with_shadow(supersample(w, h, fn), dy=10, blur=12)


def phone_cracked(w=240):
    h = int(w * 2.0)

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=34 * S, fill=INK)
        d.rounded_rectangle([12 * S, 12 * S, (w - 12) * S, (h - 12) * S], radius=26 * S, fill=(60, 110, 170))
        ix, iy = w * 0.6, h * 0.35
        rnd = random.Random(3)
        for k in range(12):
            a = k / 12 * math.tau + rnd.uniform(-0.2, 0.2)
            pts, r = [(ix * S, iy * S)], 0
            while r < h:
                r += rnd.uniform(25, 55)
                a += rnd.uniform(-0.3, 0.3)
                x = min(max(ix + math.cos(a) * r, 14), w - 14)
                y = min(max(iy + math.sin(a) * r, 14), h - 14)
                pts.append((x * S, y * S))
            d.line(pts, fill=PAPER, width=int(3 * S))
        d.ellipse([(ix - 10) * S, (iy - 10) * S, (ix + 10) * S, (iy + 10) * S], fill=PAPER)
    return with_shadow(supersample(w, h, fn), dy=10, blur=12)


def share_bar(w=860):
    """'Wer zahlt welchen Anteil?' split bar."""
    h = 210

    def fn(im, d, ss):
        S = ss
        d.rounded_rectangle([0, 0, w * S, h * S], radius=28 * S, fill=PAPER)
        d.text((w / 2 * S, 46 * S), "WER ZAHLT WIE VIEL?", font=font(F_HEAD, 34 * S), fill=INK, anchor="mm")
        x0, x1, y0, y1 = 40, w - 40, 96, 170
        d.rounded_rectangle([x0 * S, y0 * S, x1 * S, y1 * S], radius=20 * S, fill=(236, 128, 38))
        d.rounded_rectangle([(x0 + (x1 - x0) * 0.62) * S, y0 * S, x1 * S, y1 * S], radius=20 * S, fill=TEAL_F)
        d.rectangle([(x0 + (x1 - x0) * 0.62) * S, y0 * S, (x0 + (x1 - x0) * 0.62 + 20) * S, y1 * S], fill=TEAL_F)
        d.text(((x0 + 30) * S, (y0 + y1) / 2 * S), "Auto  ?%", font=font(F_HEAD, 32 * S), fill=PAPER, anchor="lm")
        d.text(((x1 - 30) * S, (y0 + y1) / 2 * S), "?%  Rad", font=font(F_HEAD, 32 * S), fill=PAPER, anchor="rm")
    return with_shadow(supersample(w, h, fn))


def paper_stack(n=14, w=520):
    h = 40 + n * 22 + 60

    def fn(im, d, ss):
        S = ss
        rnd = random.Random(2)
        for k in range(n):
            y = h - 60 - k * 22
            jx = rnd.uniform(-18, 18)
            d.rectangle([(20 + jx) * S, (y - 20) * S, (w - 20 + jx) * S, y * S], fill=PAPER, outline=(200, 206, 212),
                        width=2 * S)
    return with_shadow(supersample(w, h, fn))


def steering_wheel(w=300):
    h = int(w * 1.6)

    def fn(im, d, ss):
        S = ss
        d.line([(w * 0.5 * S, h * 0.5 * S), (w * 0.95 * S, h * 0.95 * S)], fill=(90, 98, 108), width=int(26 * S))
        d.ellipse([w * 0.3 * S, 0, w * 0.7 * S, h * S * 0.9], outline=INK, width=int(30 * S))
        d.ellipse([w * 0.43 * S, h * 0.38 * S, w * 0.57 * S, h * 0.52 * S], fill=(90, 98, 108))
    return with_shadow(supersample(w, h, fn), dy=8, blur=10)


def photo_emoji(ch, size=150):
    def fn(base, box):
        x0, y0, x1, y1 = box
        e = emoji_img(ch, size)
        base.alpha_composite(e, (int((x0 + x1) / 2 - e.width / 2), int((y0 + y1) / 2 - e.height / 2)))
    return fn


def photo_wheel(base, box):
    x0, y0, x1, y1 = box
    wimg = wheel_img(0.7, R=95)
    base.alpha_composite(wimg, (int((x0 + x1) / 2 - wimg.width / 2), int((y0 + y1) / 2 - wimg.height / 2)))


def ring_back(w=1080):
    """Boxing ring behind the fighters: canvas floor, corner posts, back ropes."""
    h = 760

    def fn(im, d, ss):
        S = ss
        # spotlight
        d.ellipse([120 * S, 0, (w - 120) * S, 520 * S], fill=(255, 255, 255, 120))
        # floor (canvas) in perspective
        d.polygon([(110 * S, 520 * S), ((w - 110) * S, 520 * S), (w * S, 700 * S), (0, 700 * S)],
                  fill=(64, 120, 200))
        d.polygon([(0, 700 * S), (w * S, 700 * S), (w * S, 760 * S), (0, 760 * S)], fill=(40, 80, 150))
        # back posts + ropes
        for x, col in ((150, RED), (w - 150, (40, 90, 200))):
            d.rounded_rectangle([(x - 14) * S, 170 * S, (x + 14) * S, 530 * S], radius=10 * S, fill=col)
        for k, col in enumerate(((240, 70, 80), PAPER, (60, 110, 220))):
            y = 230 + k * 85
            d.line([(150 * S, y * S), ((w - 150) * S, y * S)], fill=col + (200,), width=int(9 * S))
    return supersample(w, h, fn)


def ring_front(w=1080):
    h = 420

    def fn(im, d, ss):
        S = ss
        for x, col in ((40, RED), (w - 40, (40, 90, 200))):
            d.rounded_rectangle([(x - 22) * S, 0, (x + 22) * S, 420 * S], radius=14 * S, fill=col)
            d.rounded_rectangle([(x - 30) * S, 0, (x + 30) * S, 40 * S], radius=12 * S, fill=PAPER)
        for k, col in enumerate(((240, 70, 80), PAPER, (60, 110, 220))):
            y = 70 + k * 95
            d.line([(40 * S, y * S), ((w - 40) * S, (y + 10) * S)], fill=col, width=int(14 * S))
    return supersample(w, h, fn)


def health_bars(t, hits_a, hits_b, t0):
    """Fighting-game style health bars. hits_* = times where that fighter loses health."""
    w, h = 1000, 120
    la = max(0.12, 1 - 0.17 * sum(1 for x in hits_a if t >= x))
    lb = max(0.12, 1 - 0.17 * sum(1 for x in hits_b if t >= x))
    flash_a = any(0 <= t - x < 0.15 for x in hits_a)
    flash_b = any(0 <= t - x < 0.15 for x in hits_b)

    def fn(im, d, ss):
        S = ss
        for side, life, name, col, fl in ((0, la, "RADFAHRER", TEAL_F, flash_a), (1, lb, "AUTOFAHRER", ORANGE, flash_b)):
            x0 = 0 if side == 0 else 540
            d.rounded_rectangle([x0 * S, 50 * S, (x0 + 460) * S, 100 * S], radius=12 * S, fill=INK)
            bw = 448 * life
            bx0 = x0 + 6 if side == 0 else x0 + 454 - bw
            d.rounded_rectangle([bx0 * S, 56 * S, (bx0 + bw) * S, 94 * S], radius=9 * S,
                                fill=PAPER if fl else (RED if life < 0.4 else col))
            d.text(((x0 + (0 if side == 0 else 460)) * S, 26 * S), name, font=font(F_HEAD, 30 * S), fill=INK,
                   anchor="ls" if side == 0 else "rs")
        d.ellipse([462 * S, 30 * S, 538 * S, 106 * S], fill=YELLOW_K)
        d.text((500 * S, 69 * S), "VS", font=font(F_HEAD, 30 * S), fill=INK, anchor="mm")
    return supersample(w, h, fn)


YELLOW_K = (255, 214, 0)


def impact(t, hits, x_of):
    """Comic hit flashes: starburst + POW word for 0.3 s after each hit."""
    w, h = 1080, 700
    words = ["POW!", "BAM!", "WUMMS!", "KLATSCH!", "BÄM!", "ZACK!"]

    def fn(im, d, ss):
        S = ss
        for i, th in enumerate(hits):
            u = (t - th) / 0.32
            if not 0 <= u < 1:
                continue
            cx, cy = x_of(i), 300
            r = (90 + 70 * ease_out(u)) * S
            pts = []
            for k in range(16):
                a = k / 16 * math.tau + i
                rr = r if k % 2 == 0 else r * 0.5
                pts.append((cx * S + math.cos(a) * rr, cy * S + math.sin(a) * rr))
            a = int(255 * (1 - u))
            d.polygon(pts, fill=(255, 214, 0, a), outline=(229, 72, 77, a), width=int(6 * S))
            wd = words[i % len(words)]
            d.text((cx * S, (cy - 150 - 40 * u) * S), wd, font=font(F_HEAD, int(64 * S)), fill=(229, 72, 77, a),
                   anchor="mm", stroke_width=int(6 * S), stroke_fill=(255, 255, 255, a))
    return supersample(w, h, fn)


class AnimProp(Prop):
    """Prop whose image is regenerated each frame (e.g. a spinning, wobbling wheel)."""

    def __init__(self, fn, *a, **k):
        super().__init__(fn(0.0), *a, **k)
        self.fn = fn

    def draw(self, layer, t, out):
        self.img = self.fn(t)
        self._rot_cache = {}
        super().draw(layer, t, out)


GROUND = 1500
EXTRA_SFX = []


def build_cards():
    EXTRA_SFX.clear()
    C = []

    def card(*a, **k):
        c = Card(*a, **k)
        C.append(c)
        return c

    def walk(t0, t1, x0, x1):
        ks, tt, k = [(t0, "stand", x0)], t0 + 0.15, 0
        while tt < t1:
            u = (tt - t0) / max(0.01, t1 - t0)
            ks.append((tt, "walk1" if k % 2 == 0 else "walk2", lerp(x0, x1, u)))
            tt += 0.28
            k += 1
        ks.append((t1, "stand", x1))
        return ks

    # ============================ HOOK
    h0, hB, hZ, hW = -0.2, at("hook", "Bis"), at("hook", "zusammenkrachen"), at("hook", "Wer")
    c = card(h0, hB)
    c.text(-2.0, "EIN GANZ NORMALER TAG", "NUR KURZ *BRÖTCHEN* HOLEN")
    c.prop(car_dmg(ORANGE, 560, dent=False), 540, 1250, -1.0, enter="left")
    c.prop(emoji_card("🥐", "Bäcker"), 820, 900, h0 + 0.4, rot=6, enter="pop")
    c = card(hB, hW)
    c.text(hB, "BIS ZWEI ZUSAMMENKRACHEN", "*RAD* GEGEN *AUTO*")
    c.prop(car_dmg(ORANGE, 520), 330, 1300, hB, enter="left")
    c.prop(bike_flat(440), 790, 1290, hB + 0.15, enter="right")
    c.prop(stamp("KRACH!", RED, 90, fill=True), 560, 980, hZ + 0.25, rot=-8, enter="stamp")
    hS = at("hook", "So")
    c = card(hS, s1("hook"))
    c.text(hS, "SO IST DIE", "*RECHTSLAGE*", "IN DEUTSCHLAND")
    c.prop(toc_page("GESETZE ZUM UNFALL", "Wer zahlt?", [
        ("§ 7 StVG", "Halterhaftung", TEAL_L), ("§ 9 StVG", "Mitverschulden", TEAL_L),
        ("§ 253 BGB", "Schmerzensgeld", TEAL_L), ("§ 223 StGB", "Körperverletzung", (250, 200, 200))]),
        540, 1250, hS + 0.05, rot=2)
    C.remove(c)
    c_toc = c
    c = card(hW, hS)
    c.text(hW, "WER ZAHLT JETZT", "DEN GANZEN *WAHNSINN?*")
    c.prop(doc_page("Polizei · Unfallaufnahme", "Rad gegen\nPkw", "Beteiligt: Radfahrer (35) und Autofahrer "
                    "(40). Fünf Schäden. Schuldfrage: ungeklärt.", lines=3), 540, 1260, hW + 0.05, rot=-2)
    c.prop(stamp("UNGEKLÄRT", RED, 62), 560, 1480, at("hook", "Wahnsinn"), rot=-9, enter="stamp")
    C.append(c_toc)

    # ============================ 1 UNFALL
    B = (1, "DER UNFALL")
    u0, uR = s0("unfall"), at("unfall", "Radfahrer")
    c = card(u0, uR, B)
    c.text(u0, "DER AUTOFAHRER BREMST –", "*STIRN* AUFS LENKRAD")
    c.fig("klaus", GROUND, [(u0, "stand", 420), (at("unfall", "knallt"), "stand", 420),
                            (at("unfall", "knallt") + 0.15, "push", 470), (at("unfall", "Lenkrad") + 0.2, "hit", 430),
                            (at("unfall", "Lenkrad") + 0.6, "cower", 430)], facing=1, s=1.5)
    c.prop(steering_wheel(), 700, 1230, u0 + 0.1, rot=-8, enter="right")
    c.prop(stamp("HUUUP!", (236, 160, 0), 84, fill=True), 540, 900, at("unfall", "Stirn"), rot=7, enter="stamp")
    c.prop(big_emoji("🤕", 170), 820, 1120, at("unfall", "Lenkrad"), enter="pop")
    c = card(uR, s1("unfall"), B)
    c.text(uR, "DER RADFAHRER FLIEGT", "ÜBER DIE *MOTORHAUBE*")
    c.prop(car_dmg(ORANGE, 640), 540, 1360, uR - 0.1, enter="fade")
    tf = at("unfall", "fliegt")
    c.fig("you", GROUND - 220, [(uR, "stand", 900, 0), (tf, "handsup", 860, 0), (tf + 0.35, "lying", 640, -300),
                                (tf + 0.7, "lying", 420, -360), (tf + 1.05, "lying", 220, -120),
                                (tf + 1.3, "lying", 180, 150)], facing=-1, s=1.3)
    c.prop(stamp("ZEITLUPE", INK, 40), 540, 860, uR + 0.2, rot=-4, enter="pop")

    # ============================ 2 SCHÄDEN
    B = (2, "DIE SCHÄDEN")
    d0, dF, dS, dA, dW = (s0("schaden"), at("schaden", "Fahrrad"), at("schaden", "rechte"), at("schaden", "Am"),
                          at("schaden", "Willkommen"))
    c = card(d0, dF, B)
    c.text(d0, "BILANZ NR. 1", "HANDY *KAPUTT*")
    c.prop(phone_cracked(300), 540, 1180, d0 + 0.1, rot=-10, enter="drop")
    c = card(dF, dS, B)
    c.text(dF, "BILANZ NR. 2 – ES EIERT!", "FAHRRAD MIT *ACHTER*")
    c.props.append(AnimProp(lambda t: wheel_img(t), 540, 1190, dF, enter="pop"))
    c.prop(stamp("EIERT", RED, 56), 820, 1450, at("schaden", "Achter") + 0.2, rot=-10, enter="stamp")
    c = card(dS, dA, B)
    c.text(dS, "BILANZ NR. 3", "RECHTE *SCHULTER* AUA")
    c.fig("you", GROUND, [(dS, "stand", 540), (dS + 0.3, "cower", 540)], facing=1, s=1.5, shake=(dS + 0.3, dA))
    c.prop(big_emoji("💥", 150), 420, 930, at("schaden", "Schulter"), enter="pop")
    c = card(dA, dW, B)
    c.text(dA, "UND AM AUTO", "KRATZER + *DELLE*").text(at("schaden", "plus"), "PLUS", "*BEULE* AN DER STIRN")
    c.prop(car_dmg(ORANGE, 640), 540, 1130, dA, enter="left")
    c.fig("klaus", GROUND + 80, [(dA, "stand", 840), (at("schaden", "plus"), "cower", 840)], facing=-1, s=1.0)
    c.prop(big_emoji("🤕", 130), 840, 1180, at("schaden", "Beule"), enter="pop")
    c = card(dW, s1("schaden"), B)
    c.text(dW, "WILLKOMMEN IM", "*SCHADENS-* MUSEUM")
    for k, (e, lab) in enumerate((("📱", "Nr. 1 · Handy"), ("🚲", "Nr. 2 · Achter"), ("💪", "Nr. 3 · Schulter"),
                                  ("🚗", "Nr. 4 · Delle"), ("🤕", "Nr. 5 · Stirn"))):
        x = 200 + (k % 3) * 340 if k < 3 else 370 + (k - 3) * 340
        y = 990 if k < 3 else 1365
        scene = photo_wheel if e == "🚲" else photo_emoji(e)
        c.prop(polaroid(scene, lab, 300, 350), x, y, dW + 0.05 + k * 0.12, rot=(k % 2 - 0.5) * 9, enter="pop")

    # ============================ 3 STREIT
    B = (3, "DER STREIT")
    r0, rA, rD = s0("streit"), at("streit", "Autofahrer"), at("streit", "Dann")
    c = card(r0, rA, B)
    c.text(r0, "DER RADFAHRER:", "SIE ZAHLEN MEIN *HANDY!*")
    c.fig("you", GROUND, [(r0, "stand", 300), (r0 + 0.3, "punch", 330)], facing=1)
    c.fig("klaus", GROUND, [(r0, "stand", 780)], facing=-1)
    c.prop(bubble("Sie zahlen\nmein Handy!", TEAL), 430, 950, r0 + 0.2, enter="pop")
    c = card(rA, rD, B)
    c.text(rA, "DER AUTOFAHRER:", "UND MEINE *REPARATUR?*")
    c.fig("you", GROUND, [(rA, "punch", 330), (rA + 0.3, "stand", 300)], facing=1)
    c.fig("klaus", GROUND, [(rA, "stand", 780), (rA + 0.3, "punch", 750)], facing=-1)
    c.prop(bubble("Und wer zahlt\nmeine Reparatur?", ORANGE), 640, 950, rA + 0.2, enter="pop")
    c = card(rD, s1("streit"), B)
    tG = at("streit", "Ganz")
    c.text(rD, "DANN WIRD GERANGELT –", "MITTEN AUF DER *STRASSE*").text(tG, "UND DAS IST EINE GANZ",
                                                                       "*SCHLECHTE* IDEE")
    c.no_emoji = True
    # street backdrop: the crashed car and the bike with the Achter
    c.prop(car_dmg(ORANGE, 520), 300, 1050, rD, enter="fade", z=-1)
    c.prop(bike_flat(360, buckle=True), 820, 1090, rD, rot=-8, enter="fade", z=-1)
    # boxer stance, then alternating punches
    ka, kb = [(rD, "guard", 380, 0)], [(rD, "guard", 700, 0)]
    hits, xs = [], {}
    tt, k = rD + 0.15, 0
    while tt < rD + 0.6:
        ka.append((tt, "guard", 390, -6 if k % 2 else 4))
        kb.append((tt, "guard", 690, 4 if k % 2 else -6))
        tt += 0.22
        k += 1
    k = 0
    end = s1("streit") - 0.35
    while tt < end:
        if k % 2 == 0:
            ka += [(tt, "guard", 400, 0), (tt + 0.13, "punch", 450, 0), (tt + 0.34, "guard", 410, 0)]
            kb += [(tt + 0.13, "guard", 690, 0), (tt + 0.19, "hit", 720, 0), (tt + 0.42, "guard", 700, 0)]
            xs[tt + 0.16] = 640
        else:
            kb += [(tt, "guard", 680, 0), (tt + 0.13, "punch", 630, 0), (tt + 0.34, "guard", 670, 0)]
            ka += [(tt + 0.13, "guard", 410, 0), (tt + 0.19, "hit", 380, 0), (tt + 0.42, "guard", 400, 0)]
            xs[tt + 0.16] = 440
        hits.append(tt + 0.16)
        tt += 0.48
        k += 1
    ka.append((s1("streit"), "cower", 380, 0))
    kb.append((s1("streit"), "cower", 700, 0))
    c.fig("you", GROUND + 10, ka, facing=1, s=1.45)
    c.fig("klaus", GROUND + 10, kb, facing=-1, s=1.45)
    c.props.append(AnimProp(lambda t: impact(t, hits, lambda i: xs[hits[i]]), 540, 1050, rD, enter="fade"))
    c.prop(stamp("SLAPSTICK – NICHT NACHMACHEN!", RED, 30, fill=True), 540, 820, tG, rot=-3, enter="stamp")
    EXTRA_SFX.extend([("punch", x) for x in hits])

    # ============================ 4 POLIZEI
    B = (4, "DIE POLIZEI")
    p0, pB, pD = s0("polizei"), at("polizei", "Beide"), at("polizei", "Der")
    c = card(p0, pB, B)
    c.text(p0, "DIE POLIZEI FRAGT:", "WER HAT *ANGEFANGEN?*")
    c.fig("cop", GROUND, [(p0, "stand", 540), (p0 + 0.4, "shrug", 540)], facing=1, s=1.4)
    c.prop(stamp("POLIZEI", (38, 72, 160), 54, fill=True), 540, 900, p0 + 0.2, rot=-5, enter="stamp")
    c = card(pB, pD, B)
    c.text(pB, "BEIDE ZEIGEN", "*AUFEINANDER*")
    c.fig("you", GROUND, [(pB, "stand", 330), (pB + 0.25, "punch", 360)], facing=1)
    c.fig("klaus", GROUND, [(pB, "stand", 750), (pB + 0.25, "punch", 720)], facing=-1)
    c.prop(stamp("ER!", RED, 70, fill=True), 300, 960, pB + 0.4, rot=-10, enter="stamp")
    c.prop(stamp("ER!", (236, 128, 38), 70, fill=True), 780, 960, pB + 0.55, rot=10, enter="stamp")
    c = card(pD, s1("polizei"), B)
    c.text(pD, "DER BEAMTE BRAUCHT JETZT", "ERST MAL *URLAUB*")
    c.fig("cop", GROUND, [(pD, "stand", 330), (pD + 0.4, "shrug", 330)], facing=1, s=1.3)
    c.prop(emoji_card("🌴", "Urlaubs-\nantrag"), 760, 1120, pD + 0.3, rot=6, enter="right")
    c.prop(stamp("GENEHMIGT", TEAL, 50), 760, 1300, at("polizei", "Urlaub") + 0.2, rot=-10, enter="stamp")

    # ============================ 5 RECHTSLAGE
    B = (5, "DIE RECHTSLAGE")
    j0, jN, jA, jH, jU = (s0("recht"), at("recht", "Nach"), at("recht", "Aber"), at("recht", "Handy"),
                          at("recht", "Und"))
    jS = at("recht", "Schmerzensgeld")
    c = card(j0, jA, B)
    c.text(j0, "JETZT WIRD'S SPANNEND", "§ 7 *STVG*").text(at("recht", "Halter"), "§ 7 STVG – AUCH OHNE VERSCHULDEN",
                                                          "*HALTER* KANN HAFTEN")
    c.prop(doc_page("Straßenverkehrsgesetz", "§ 7\nHalterhaftung",
                    "Wird beim Betrieb eines Kfz ein Mensch verletzt oder eine Sache beschädigt, kann der Halter "
                    "zum Schadensersatz verpflichtet sein.", lines=2), 540, 1240, jN, rot=-2)
    c.prop(stamp("AUCH OHNE\nVERSCHULDEN", TEAL, 40), 560, 1500, at("recht", "ohne"), rot=-8, enter="stamp")
    c = card(jA, jH, B)
    c.text(jA, "ABER: MITVERSCHULDEN", "KANN *KÜRZEN*")
    c.prop(share_bar(), 540, 1100, jA + 0.1, enter="wipe")
    c.prop(emoji_card("🚗", "Auto"), 300, 1420, jA + 0.4, rot=-6, enter="left")
    c.prop(emoji_card("🚲", "Rad"), 780, 1420, jA + 0.5, rot=6, enter="right")
    c = card(jH, jU, B)
    c.text(jH, "HANDY + FAHRRAD", "*ERSATZ* MÖGLICH").text(jS, "SCHMERZENSGELD – UNTER UMSTÄNDEN",
                                                           "FÜR *BEIDE*")
    c.prop(phone_cracked(170), 250, 1070, jH, rot=-8, enter="pop")
    c.prop(bike_flat(380, buckle=True), 700, 1080, at("recht", "Fahrrad"), enter="pop")
    c.prop(check_badge(50), 540, 1000, at("recht", "ersetzt"), enter="pop")
    c.prop(emoji_card("💪", "Radfahrer"), 330, 1440, jS + 0.2, rot=-6, enter="pop")
    c.prop(emoji_card("🤕", "Autofahrer"), 750, 1440, jS + 0.35, rot=6, enter="pop")
    c = card(jU, s1("recht"), B)
    c.text(jU, "RANGELEI MIT VERLETZUNG?", "*§ 223* STGB")
    c.prop(doc_page("Strafgesetzbuch", "§ 223\nKörperverletzung",
                    "Wer eine andere Person vorsätzlich körperlich misshandelt oder an der Gesundheit schädigt, "
                    "wird bestraft.", lines=2), 540, 1240, jU + 0.05, rot=-2)
    c.prop(stamp("ANZEIGE", RED, 64), 560, 1490, at("recht", "Anzeige"), rot=-9, enter="stamp")

    # ============================ 6 TIPPS
    B = (6, "3 GOLDENE TIPPS")
    t0 = s0("tipps")
    c = card(t0, s1("tipps"), B)
    c.text(t0, "NACH DEM UNFALL", "3 GOLDENE *TIPPS*").text(at("tipps", "Erstens"), "TIPP 1", "*POLIZEI* RUFEN").text(
        at("tipps", "Zweitens"), "TIPP 2", "*FOTOS* + ZEUGEN").text(at("tipps", "Drittens"), "TIPP 3",
                                                                   "*ARZT* DOKUMENTIERT")
    c.prop(tip_card(1, "Polizei\nrufen"), 230, 1250, at("tipps", "Erstens"), rot=-7, enter="left")
    c.prop(tip_card(2, "Fotos +\nZeugen"), 540, 1220, at("tipps", "Zweitens"), rot=0, enter="up")
    c.prop(tip_card(3, "Attest"), 850, 1250, at("tipps", "Drittens"), rot=7, enter="right")

    # ============================ 7 FAZIT
    B = (7, "FAZIT")
    z0, zF, zD, zM = s0("fazit"), at("fazit", "fünf"), at("fazit", "drei"), at("fazit", "mehr")
    c = card(z0, s1("fazit"), B)
    c.text(z0, "EIN KLEINER UNFALL:", "*5* SCHÄDEN").text(
        zD, "EIN KLEINER UNFALL:", "*3* STREITPARTEIEN").text(zM, "MEHR PAPIERKRAM ALS", "BEI EINER *HOCHZEIT*")
    c.fig("you", GROUND, [(z0, "cower", 220)], facing=1, s=1.3, shake=(z0, s1("fazit")))
    c.fig("cop", GROUND, [(z0, "shrug", 540)], facing=1, s=1.3)
    c.fig("klaus", GROUND, [(z0, "cower", 860)], facing=-1, s=1.3, shake=(z0, s1("fazit")))
    c.prop(paper_stack(12), 540, 870, zM, enter="drop")
    c.prop(big_emoji("💍", 120), 540, 730, zM + 0.4, enter="pop")

    # ============================ CTA
    q0 = s0("cta")
    c = card(q0, s1("cta"))
    c.text(q0, "UND JETZT DU:", "WER IST *SCHULD?*")
    c.prop(question_bubble(880), 520, 900, q0 + 0.05, enter="pop")
    c.prop(cta_pill("🚗", "Autofahrer", ORANGE), 290, 1190, at("cta", "Autofahrer"), enter="pop")
    c.prop(cta_pill("🚲", "Radfahrer", TEAL), 760, 1190, at("cta", "Radfahrer"), enter="pop")
    c.prop(cta_pill("💬", "Schreib's in die Kommentare!", INK), 520, 1320, at("cta", "Schreib"), enter="pop")
    c.prop(cta_pill("📌", "Speichern für den Ernstfall", TEAL), 520, 1445, at("cta", "speicher"), enter="pop")
    c.prop(disclaimer(), 520, 1550, q0 + 0.5, enter="fade")
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
    CPS = 78.0
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
            if hl and any(k in w for k in RED_KEYS):
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
CARD_EMOJI = ["🥐", "💥", "🤔", "⚖️", "📯", "🎢", "📱", "🚲", "😖", "🚗", "🏛️", "😤", "🔧", "🤼", "🚔", "👉",
              "🌴", "⚖️", "⚠️", "💶", "🚨", "🩺", "📄", "💬"]
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
    if idx >= len(CARD_EMOJI) or card is CARDS[-1] or getattr(card, "no_emoji", False):
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
            sc = (0.85 + 0.15 * ease_back(p, 2.0)) * min(1.0, 860 / img.width)
            if abs(sc - 1) > 0.01:
                img = img.resize((int(img.width * sc), int(img.height * sc)), Image.BICUBIC)
            frame.alpha_composite(img, (int(520 - img.width / 2), int(1470 - img.height / 2)))
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
    back = Image.new("RGBA", (W, STAGE_H), (0, 0, 0, 0))
    for p in sorted(card.props, key=lambda p: p.z):
        p.draw(back if p.z < 0 else layer, t, out)
    if card.figs or any(p.z < 0 for p in card.props):
        fl = Image.new("RGBA", (W * SS, STAGE_H * SS), (0, 0, 0, 0))
        fd = ImageDraw.Draw(fl)
        for f in card.figs:
            f.draw(fd, t, SS, dy=-STAGE_Y)
        fl = fl.resize((W, STAGE_H), Image.BILINEAR)
        base = back
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
    fade = np.minimum(1, np.minimum(np.arange(n) / SR / 0.05, (n - np.arange(n)) / SR / 1.5))
    return out * fade


def sfx_bell():
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    one = sum(np.sin(2 * np.pi * f * t) * g for f, g in ((1180, 1.0), (2950, 0.5), (4100, 0.25))) * _env(n, 0.001, 0.35)
    out = np.zeros(n + int(0.28 * SR))
    out[:n] += one * 0.35
    out[int(0.28 * SR):int(0.28 * SR) + n] += one * 0.35
    return out


def sfx_punch(rng):
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (90 + 120 * np.exp(-t * 40)) * t) * _env(n, 0.001, 0.06)
    slap = rng.standard_normal(n) * _env(n, 0.0005, 0.02)
    return (body * 1.1 + slap * 0.7)


def sfx_crowd(rng, dur):
    n = int(dur * SR)
    x = np.convolve(rng.standard_normal(n), np.ones(30) / 30, mode="same")
    am = 1 + 0.35 * np.sin(np.arange(n) / SR * 2 * np.pi * 3.3)
    env = np.minimum(1, np.minimum(np.arange(n) / SR / 0.4, (n - np.arange(n)) / SR / 0.6))
    return x * am * env * 1.6


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
    for kind, tx in EXTRA_SFX:
        if kind == "bell":
            put(sfx_bell(), tx)
        elif kind == "punch":
            put(sfx_punch(rng) * 0.9, tx)
        elif kind == "crowd":
            put(sfx_crowd(rng, s1("streit") - tx), tx)
    bed = beat_bed(TOTAL)
    mix = np.zeros(n)
    mix[: len(out)] += out * 0.32
    mix[: len(bed)] += bed * 0.2
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
    out = ROOT / os.environ.get("VIDEO_OUT", "unfall-video-erklaer.mp4")
    audio = BUILD / "voice.wav"
    lst = BUILD / "concat.txt"
    lst.write_text("".join(f"file '{s['audio']}'\n" for s in TIM))
    voice = BUILD / "voice_only.wav"
    # even, punchy voice: per-scene loudness already equal -> gentle compression, no dynamic normaliser
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-af", f"apad=pad_dur={TAIL},highpass=f=70,"
                    "acompressor=threshold=0.08:ratio=3:attack=8:release=120:makeup=2,alimiter=limit=0.9",
                    "-ar", "48000", "-ac", "1", str(voice)], check=True)
    sfx = BUILD / "sfx.wav"
    make_sfx(sfx)
    raw = BUILD / "mix_raw.wav"
    # music/sfx ducked under the voice (sidechain), then mixed
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice), "-i", str(sfx), "-filter_complex",
                    "[0:a]asplit=2[v][sc];[1:a]volume=0.5[s];"
                    "[s][sc]sidechaincompress=threshold=0.03:ratio=4:attack=10:release=250[sd];"
                    "[v][sd]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95",
                    "-ar", "48000", str(raw)], check=True)
    # two-pass loudness normalisation (linear -> constant gain, no pumping)
    m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(raw), "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    js = json.loads(m[m.rindex("{"):m.rindex("}") + 1])
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:"
                    f"measured_I={js['input_i']}:measured_TP={js['input_tp']}:measured_LRA={js['input_lra']}:"
                    f"measured_thresh={js['input_thresh']}:offset={js['target_offset']}",
                    "-ar", "48000", str(audio)], check=True)
    if len(sys.argv) > 1 and sys.argv[1] == "audio":
        return
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
