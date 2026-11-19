"""Render handy-weg-motivation.mp4 (1080x1920, 30 fps).

Flat-illustration motivation short: colourful gradient / sunburst stages, a
cartoon kid in a blue hoodie, one huge word at a time synced to the voiceover,
a synthesized beat that drops when the message turns positive.

    python3 tts.py && python3 render.py          # full video
    python3 render.py preview 1 6 20             # stills -> build/motivation/stills
"""
import json
import math
import random
import subprocess
import sys
import wave
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BUILD = ROOT / "build" / "motivation"
FONTS = ROOT / "fonts"
OUT = ROOT / "handy-weg-motivation.mp4"
W, H, FPS = 1080, 1920, 30
S = 2                       # supersampling for the illustration layer
TAIL = 1.2

F_HEAD = str(FONTS / "Unbounded_900Black.ttf")
F_HAND = str(FONTS / "Caveat_700Bold.ttf")
F_BODY = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"

SKIN = (247, 196, 160)
SKIN_D = (226, 165, 128)
HAIR = (52, 36, 32)
HOOD = (52, 120, 230)
HOOD_D = (36, 92, 190)
PANTS = (40, 44, 70)
SHOE = (245, 245, 250)
YELLOW = (255, 214, 64)
WHITE = (255, 255, 255)
INK = (22, 18, 40)

sys.path.insert(0, str(HERE))
from script import SCENES  # noqa: E402

TIM = json.loads((BUILD / "timings.json").read_text())
KEYS = [s["key"] for s in SCENES]
OFF, _a = [], 0.0
for s in TIM:
    OFF.append(_a)
    _a += s["duration"]
TOTAL = _a + TAIL
NFRAMES = int(math.ceil(TOTAL * FPS))


def s0(k):
    return OFF[KEYS.index(k)]


def at(k, word, occ=0, lead=0.05):
    i, n = KEYS.index(k), 0
    for w in TIM[i]["words"]:
        if w["text"].strip(".,!?").lower().startswith(word.lower()):
            if n == occ:
                return OFF[i] + w["start"] - lead
            n += 1
    raise KeyError((k, word))


# ------------------------------------------------------------------ easing
def c01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):
    return 1 - (1 - c01(x)) ** 3


def ease_back(x, s=1.7):
    x = c01(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, t):
    return a + (b - a) * t


def lcol(a, b, t):
    return tuple(int(lerp(a[i], b[i], t)) for i in range(len(a)))


@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, size)


# ------------------------------------------------------------------ canvas
class C:
    """ImageDraw wrapper working in 1080x1920 units on an S-times larger image."""

    def __init__(self, img):
        self.img = img
        self.d = ImageDraw.Draw(img, "RGBA")

    def ellipse(self, cx, cy, rx, ry, fill, outline=None, width=0):
        self.d.ellipse([(cx - rx) * S, (cy - ry) * S, (cx + rx) * S, (cy + ry) * S],
                       fill=fill, outline=outline, width=int(width * S))

    def circle(self, cx, cy, r, fill, **kw):
        self.ellipse(cx, cy, r, r, fill, **kw)

    def rect(self, x0, y0, x1, y1, fill, r=0, outline=None, width=0):
        self.d.rounded_rectangle([x0 * S, y0 * S, x1 * S, y1 * S], radius=int(r * S),
                                 fill=fill, outline=outline, width=int(width * S))

    def poly(self, pts, fill):
        self.d.polygon([(x * S, y * S) for x, y in pts], fill=fill)

    def line(self, pts, fill, width, round_=True):
        p = [(x * S, y * S) for x, y in pts]
        self.d.line(p, fill=fill, width=int(width * S), joint="curve")
        if round_:
            r = width / 2
            for x, y in pts:
                self.circle(x, y, r, fill)

    def arc(self, cx, cy, r, a0, a1, fill, width):
        self.d.arc([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], a0, a1,
                   fill=fill, width=int(width * S))

    def text(self, x, y, s, size, fill, f=F_HEAD, anchor="mm", stroke=0, sfill=None):
        if size < 4:
            return
        self.d.text((x * S, y * S), s, font=font(f, int(size * S)), fill=fill, anchor=anchor,
                    stroke_width=int(stroke * S), stroke_fill=sfill)


@lru_cache(maxsize=16)
def gradient(top, bottom):
    t = np.linspace(0, 1, H * S)[:, None, None]
    a = np.array(top, float)[None, None, :]
    b = np.array(bottom, float)[None, None, :]
    g = (a * (1 - t) + b * t).astype(np.uint8)
    return Image.fromarray(np.repeat(g, W * S, axis=1), "RGB")


def background(top, bottom):
    return gradient(top, bottom).copy()


def sunburst(c, cx, cy, color, rot, n=18, alpha=40):
    R = 2600
    for i in range(n):
        a0 = math.radians(rot + i * 360 / n)
        a1 = a0 + math.radians(360 / n / 2)
        c.poly([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)),
                (cx + R * math.cos(a1), cy + R * math.sin(a1))], color + (alpha,))


STARS = [(random.Random(i).uniform(0, W), random.Random(i + 999).uniform(0, H),
          random.Random(i + 77).uniform(1.5, 4)) for i in range(120)]


def stars(c, t, alpha=200):
    for i, (x, y, r) in enumerate(STARS):
        tw = 0.55 + 0.45 * math.sin(t * 2.3 + i)
        c.circle(x, y, r, (255, 255, 255, int(alpha * tw)))


def glow(c, cx, cy, r, color, steps=8, a=26):
    for k in range(steps, 0, -1):
        c.circle(cx, cy, r * k / steps, color + (a,))


# ------------------------------------------------------------------ props
def phone(c, cx, cy, w, h, ang=0, screen=(20, 24, 40), glow_col=None, content=None, t=0):
    """Phone drawn on its own layer so it can be rotated."""
    pad = 40
    lw, lh = int((w + 2 * pad) * S), int((h + 2 * pad) * S)
    lay = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    lc = C(lay)
    if glow_col:
        lc.rect(pad - 18, pad - 18, pad + w + 18, pad + h + 18, glow_col + (60,), r=w * 0.2)
    lc.rect(pad, pad, pad + w, pad + h, (24, 24, 30), r=w * 0.14)
    lc.rect(pad + w * 0.06, pad + w * 0.06, pad + w * 0.94, pad + h - w * 0.06, screen, r=w * 0.1)
    lc.rect(pad + w * 0.38, pad + w * 0.1, pad + w * 0.62, pad + w * 0.16, (10, 10, 14), r=8)
    if content:
        content(lc, pad + w * 0.06, pad + w * 0.06, pad + w * 0.94, pad + h - w * 0.06, t)
    if ang:
        lay = lay.rotate(ang, resample=Image.BICUBIC, expand=True)
    c.img.paste(lay, (int(cx * S - lay.width / 2), int(cy * S - lay.height / 2)), lay)


def feed(lc, x0, y0, x1, y1, t, speed=900):
    """Endless scrolling feed of colourful video cards inside a phone screen."""
    cols = [(255, 87, 140), (80, 200, 255), (255, 190, 60), (140, 110, 255), (60, 220, 160)]
    ch = (y1 - y0) * 0.9
    off = (t * speed) % ch
    lc.d.rectangle([x0 * S, y0 * S, x1 * S, y1 * S], fill=(12, 12, 20))
    for k in range(-1, 3):
        yy = y0 + k * ch - off + 12
        if yy > y1 or yy + ch < y0:
            continue
        col = cols[(k + int((t * speed) // ch)) % 5]
        a0, a1 = max(yy, y0), min(yy + ch - 24, y1)
        if a1 > a0:
            lc.d.rectangle([(x0 + 10) * S, a0 * S, (x1 - 10) * S, a1 * S], fill=col)
            cy = yy + ch * 0.45
            if y0 < cy < y1:
                lc.poly([(x0 + (x1 - x0) * 0.42, cy - 30), (x0 + (x1 - x0) * 0.42, cy + 30),
                         (x0 + (x1 - x0) * 0.6, cy)], (255, 255, 255, 220))


def dumbbell(c, cx, cy, s, col=(60, 60, 80)):
    c.rect(cx - 50 * s, cy - 7 * s, cx + 50 * s, cy + 7 * s, (170, 170, 185), r=6 * s)
    for sx in (-1, 1):
        c.rect(cx + sx * 40 * s - 11 * s, cy - 32 * s, cx + sx * 40 * s + 11 * s, cy + 32 * s, col, r=7 * s)
        c.rect(cx + sx * 58 * s - 8 * s, cy - 22 * s, cx + sx * 58 * s + 8 * s, cy + 22 * s, col, r=6 * s)


def book(c, cx, cy, s, col=(255, 110, 90)):
    c.rect(cx - 60 * s, cy - 42 * s, cx + 60 * s, cy + 42 * s, col, r=8 * s)
    c.rect(cx - 52 * s, cy - 36 * s, cx + 52 * s, cy + 30 * s, (255, 250, 240), r=4 * s)
    c.line([(cx, cy - 36 * s), (cx, cy + 30 * s)], col, 4 * s)
    for k in range(4):
        y = cy - 22 * s + k * 13 * s
        c.line([(cx - 42 * s, y), (cx - 10 * s, y)], (190, 190, 200), 3 * s)
        c.line([(cx + 10 * s, y), (cx + 42 * s, y)], (190, 190, 200), 3 * s)


def brush(c, cx, cy, s):
    c.line([(cx - 50 * s, cy + 50 * s), (cx + 25 * s, cy - 25 * s)], (190, 120, 60), 14 * s)
    c.poly([(cx + 18 * s, cy - 32 * s), (cx + 32 * s, cy - 18 * s), (cx + 60 * s, cy - 60 * s)],
           (255, 80, 120))
    c.circle(cx - 40 * s, cy - 40 * s, 14 * s, (80, 200, 255))
    c.circle(cx - 10 * s, cy - 58 * s, 10 * s, (255, 214, 64))


def tree(c, cx, cy, s):
    c.rect(cx - 9 * s, cy, cx + 9 * s, cy + 60 * s, (140, 90, 50), r=4 * s)
    c.circle(cx, cy - 20 * s, 48 * s, (60, 190, 110))
    c.circle(cx - 30 * s, cy + 5 * s, 32 * s, (50, 170, 95))
    c.circle(cx + 30 * s, cy + 5 * s, 32 * s, (70, 205, 120))


def bricks(c, cx, by, n, s=1.0):
    cols = [(232, 112, 80), (214, 96, 66)]
    for k in range(n):
        row, i = divmod(k, 3)
        sh = 22 * s if row % 2 else 0
        x = cx - 75 * s + i * 50 * s + sh - 11 * s
        y = by - (row + 1) * 28 * s
        c.rect(x, y, x + 46 * s, y + 25 * s, cols[(row + i) % 2], r=3 * s)


def clock(c, cx, cy, r, t_hand):
    c.circle(cx, cy + 10, r, (0, 0, 0, 60))
    c.circle(cx, cy, r, (255, 255, 255))
    c.circle(cx, cy, r * 0.9, (250, 246, 236))
    for k in range(12):
        a = math.radians(k * 30)
        r0 = r * (0.74 if k % 3 == 0 else 0.8)
        c.line([(cx + r0 * math.sin(a), cy - r0 * math.cos(a)),
                (cx + r * 0.86 * math.sin(a), cy - r * 0.86 * math.cos(a))], INK, 10 if k % 3 == 0 else 6)
    ah = math.radians(t_hand * 30)
    am = math.radians(t_hand * 360)
    c.line([(cx, cy), (cx + r * 0.45 * math.sin(ah), cy - r * 0.45 * math.cos(ah))], INK, 18)
    c.line([(cx, cy), (cx + r * 0.7 * math.sin(am), cy - r * 0.7 * math.cos(am))], (240, 70, 90), 10)
    c.circle(cx, cy, 16, INK)


# ------------------------------------------------------------------ the kid
def kid(c, x, y, s=1.0, la=20, ra=-20, lel=0, rel=0, mood="neutral", look=0,
        legs="stand", hold_phone=False, phone_glow=False, bob=0.0, t=0.0):
    """Flat cartoon kid. (x, y) = point between the feet. Arm angles in degrees,
    0 = hanging down, 90 = sideways out, 180 = straight up."""
    y = y - bob

    def P(dx, dy):
        return (x + dx * s, y + dy * s)

    # shadow
    c.ellipse(x, y + bob + 6 * s, 70 * s, 14 * s, (0, 0, 0, 55))
    # legs
    hip_y = -150
    if legs == "stand":
        for sx in (-1, 1):
            c.line([P(sx * 20, hip_y), P(sx * 24, -18)], PANTS, 30 * s)
            c.rect(*P(sx * 24 - 22, -24), *P(sx * 24 + 26, 4), SHOE, r=12 * s)
    elif legs == "sit":
        for sx in (-1, 1):
            c.line([P(sx * 20, hip_y), P(sx * 20 + 70, hip_y + 4), P(sx * 20 + 72, -18)], PANTS, 30 * s)
            c.rect(*P(sx * 20 + 52, -24), *P(sx * 20 + 102, 4), SHOE, r=12 * s)
    elif legs == "jump":
        for sx in (-1, 1):
            c.line([P(sx * 20, hip_y), P(sx * 46, -70), P(sx * 30, -18)], PANTS, 30 * s)
            c.rect(*P(sx * 30 - 22, -24), *P(sx * 30 + 26, 4), SHOE, r=12 * s)
    # body (hoodie)
    sh_y = -300
    c.rect(*P(-62, sh_y), *P(62, hip_y + 10), HOOD, r=40 * s)
    c.rect(*P(-40, hip_y - 60), *P(40, hip_y - 10), HOOD_D, r=16 * s)  # pocket
    c.line([P(-14, sh_y + 20), P(-16, sh_y + 80)], WHITE, 6 * s)
    c.line([P(14, sh_y + 20), P(16, sh_y + 80)], WHITE, 6 * s)

    # arms: shoulder -> elbow -> hand
    hands = []
    for sx, ang, el in ((-1, la, lel), (1, ra, rel)):
        sxp, syp = P(sx * 56, sh_y + 26)
        a = math.radians(ang)
        ex, ey = sxp + sx * math.sin(a) * 80 * s, syp + math.cos(a) * 80 * s
        a2 = a + math.radians(el)
        hx, hy = ex + sx * math.sin(a2) * 78 * s, ey + math.cos(a2) * 78 * s
        c.line([(sxp, syp), (ex, ey), (hx, hy)], HOOD, 30 * s)
        c.circle(hx, hy, 17 * s, SKIN)
        hands.append((hx, hy))

    # head
    hx0, hy0 = P(look * 6, -390)
    c.rect(hx0 - 22 * s, hy0 + 40 * s, hx0 + 22 * s, hy0 + 100 * s, SKIN_D, r=10 * s)  # neck
    c.circle(hx0, hy0, 92 * s, SKIN)
    c.circle(hx0 - 90 * s, hy0 + 8 * s, 18 * s, SKIN)
    c.circle(hx0 + 90 * s, hy0 + 8 * s, 18 * s, SKIN)
    # hair
    c.poly([(hx0 - 96 * s, hy0 - 6 * s), (hx0 - 90 * s, hy0 - 70 * s), (hx0 - 40 * s, hy0 - 110 * s),
            (hx0 + 10 * s, hy0 - 132 * s), (hx0 + 20 * s, hy0 - 104 * s), (hx0 + 80 * s, hy0 - 86 * s),
            (hx0 + 98 * s, hy0 - 20 * s), (hx0 + 70 * s, hy0 - 50 * s), (hx0 + 20 * s, hy0 - 40 * s),
            (hx0 - 30 * s, hy0 - 56 * s), (hx0 - 70 * s, hy0 - 40 * s)], HAIR)
    # face
    ex = look * 10
    for sx in (-1, 1):
        cx, cy = hx0 + sx * 34 * s + ex * s, hy0 + 10 * s
        if mood == "tired":
            c.circle(cx, cy, 18 * s, WHITE)
            c.circle(cx, cy + 4 * s, 9 * s, INK)
            c.rect(cx - 21 * s, cy - 22 * s, cx + 21 * s, cy - 2 * s, SKIN)       # heavy lids
            c.line([(cx - 18 * s, cy + 22 * s), (cx + 18 * s, cy + 22 * s)], (200, 140, 170), 4 * s)
        elif mood == "happy":
            c.arc(cx, cy + 8 * s, 15 * s, 200, 340, INK, 7 * s)
        elif mood == "shock":
            c.circle(cx, cy, 22 * s, WHITE)
            c.circle(cx, cy, 8 * s, INK)
        else:
            c.circle(cx, cy, 18 * s, WHITE)
            c.circle(cx + look * 4 * s, cy + 2 * s, 10 * s, INK)
            c.circle(cx + look * 4 * s + 3 * s, cy - 2 * s, 3 * s, WHITE)
        # brows
        by = cy - (34 if mood in ("shock", "happy") else 28) * s
        tilt = {"determined": 8, "tired": -4}.get(mood, 0) * s
        c.line([(cx - 18 * s, by - sx * -tilt), (cx + 18 * s, by + sx * -tilt)], HAIR, 7 * s)
    mx, my = hx0 + ex * s, hy0 + 52 * s
    if mood == "happy":
        c.d.chord([(mx - 30 * s) * S, (my - 22 * s) * S, (mx + 30 * s) * S, (my + 26 * s) * S], 0, 180,
                  fill=(150, 40, 60))
    elif mood == "shock":
        c.ellipse(mx, my + 4 * s, 12 * s, 16 * s, (150, 40, 60))
    elif mood == "tired":
        c.line([(mx - 16 * s, my + 4 * s), (mx + 16 * s, my)], (150, 70, 70), 6 * s)
    elif mood == "determined":
        c.arc(mx, my - 14 * s, 22 * s, 50, 130, (150, 70, 70), 7 * s)
    else:
        c.arc(mx, my - 18 * s, 22 * s, 60, 120, (150, 70, 70), 6 * s)

    if hold_phone:
        px, py = hands[1]
        phone(c, px - 6 * s, py - 30 * s, 62 * s, 112 * s, ang=8,
              content=lambda lc, a, b, cc, d, tt: feed(lc, a, b, cc, d, tt, speed=500), t=t,
              glow_col=(120, 200, 255) if phone_glow else None)
        if phone_glow:
            glow(c, hx0, hy0 + 20 * s, 130 * s, (120, 200, 255), steps=4, a=10)
    return hands


# ------------------------------------------------------------------ scenes
def sc_hook(c, t, lt):
    sunburst(c, W / 2, 1180, (255, 255, 255), lt * 12, alpha=34)
    z = lerp(1.12, 1.0, ease_out(lt / 0.6))
    kid(c, W / 2, 1830, s=1.75 * z, la=10, ra=-150, rel=-115, mood="tired", hold_phone=True,
        phone_glow=True, t=t, bob=4 * math.sin(lt * 3))
    # screen-time counter
    secs = int(lerp(2 * 3600 + 41 * 60, 3 * 3600 + 2 * 60, ease_out((lt - 0.6) / 1.8)))
    hh, mm = divmod(secs // 60, 60)
    pop = ease_back((lt - 0.7) / 0.3)
    if pop > 0:
        c.rect(W / 2 - 300 * pop, 690 - 70 * pop, W / 2 + 300 * pop, 690 + 70 * pop, (20, 12, 40, 210), r=36)
        if pop > 0.6:
            c.text(W / 2, 668, "BILDSCHIRMZEIT HEUTE", 28, (255, 180, 210), f=F_BODY)
            c.text(W / 2, 718, f"{hh} Std. {mm:02d} Min.", 54, YELLOW if hh >= 3 else WHITE)


def sc_scroll(c, t, lt):
    stars(c, t, 120)
    # giant phone with fast feed; speeds up
    sp = 900 + 900 * c01(lt / 7)
    phone(c, W / 2, 1150, 480, 860, ang=-4 + 2 * math.sin(lt * 1.5), glow_col=(255, 80, 160),
          content=lambda lc, a, b, cc, d, tt: feed(lc, a, b, cc, d, tt, speed=sp), t=lt)
    # thumb swiping
    sw = (lt * 1.6) % 1
    ty = lerp(1480, 1180, ease_out(sw / 0.6))
    c.ellipse(W / 2 + 140, ty, 70, 90, SKIN)
    c.ellipse(W / 2 + 140, ty - 50, 44, 30, (255, 225, 210))
    # "?" bubbles when he forgets what he saw
    if lt > 4.3:
        for k, (x, y) in enumerate([(220, 860), (860, 980), (180, 1420), (880, 1560)]):
            p = ease_back((lt - 4.4 - k * 0.25) / 0.3)
            if p > 0:
                c.text(x, y + 6 * math.sin(lt * 4 + k), "?", 120 * p, (255, 255, 255, 230),
                       stroke=4, sfill=(140, 40, 120))


def sc_others(c, t, lt):
    sunburst(c, W / 2, 1300, (255, 255, 255), -lt * 10, alpha=22)
    c.rect(-50, 1640, W + 50, H + 50, (40, 150, 110))
    xs = [200, 540, 880]
    for i, x in enumerate(xs):
        p = ease_back((lt - [0.6, 1.6, 2.2][i]) / 0.35)
        if p <= 0:
            continue
        s = 0.95 * p
        if i == 0:   # training
            lift = 0.5 + 0.5 * math.sin(lt * 6)
            hands = kid(c, x, 1660, s=s, la=lerp(60, 165, lift), ra=-lerp(60, 165, lift),
                        lel=lerp(-80, 0, lift), rel=lerp(-80, 0, lift), mood="determined", legs="stand")
            mid = ((hands[0][0] + hands[1][0]) / 2, (hands[0][1] + hands[1][1]) / 2)
            dumbbell(c, mid[0], mid[1], 0.9 * s)
            dumbbell(c, mid[0], mid[1], 0.9 * s)
        elif i == 1:  # learning
            hands = kid(c, x, 1660, s=s, la=40, ra=-40, lel=-95, rel=-95, mood="neutral", look=0)
            book(c, x, hands[0][1] - 26 * s, 1.0 * s)
        else:         # building
            n = int(c01((lt - 2.3) / 1.6) * 12)
            bricks(c, x + 70, 1660, n, 0.9)
            kid(c, x - 70, 1660, s=s, la=30, ra=-80 + 20 * math.sin(lt * 5), mood="happy")
    # labels
    for i, (x, w) in enumerate(zip(xs, ["TRAINIEREN", "LERNEN", "BAUEN"])):
        p = ease_out((lt - [0.7, 1.75, 2.35][i]) / 0.3)
        if p > 0:
            c.text(x, 1760, w, 34, (255, 255, 255, int(255 * p)), f=F_HEAD)


def sc_clock(c, t, lt):
    stars(c, t, 160)
    spin = lt * lerp(0.6, 5, c01((lt - 0.8) / 2.2))
    glow(c, W / 2, 1060, 420, (255, 120, 80), a=16)
    clock(c, W / 2, 1060, 300, spin * 3)
    # 24h ring counting down
    left = 24 - 24 * ease_out((lt - 1.0) / 3.5) * 0.85
    c.arc(W / 2, 1060, 350, -90, -90 + 360 * left / 24, YELLOW, 22)
    c.text(W / 2, 1490, f"{left:.1f} h übrig".replace(".", ","), 52, WHITE, stroke=3, sfill=INK)
    # app icon eating time
    if lt > 3.0:
        p = ease_back((lt - 3.0) / 0.4)
        x, y = W / 2 + 270, 780
        c.rect(x - 95 * p, y - 95 * p, x + 95 * p, y + 95 * p, (255, 60, 120), r=40 * p)
        c.rect(x - 95 * p, y - 95 * p, x + 95 * p, y - 10 * p, (255, 110, 160), r=40 * p)
        mouth = abs(math.sin(lt * 9)) * 40 * p
        c.ellipse(x, y + 30 * p, 52 * p, 8 * p + mouth / 2, INK)
        for sx in (-1, 1):
            c.circle(x + sx * 36 * p, y - 30 * p, 14 * p, WHITE)
            c.circle(x + sx * 34 * p, y - 28 * p, 7 * p, INK)


def sc_turn(c, t, lt):
    sunburst(c, W / 2, 1250, (255, 255, 255), lt * 25, alpha=40)
    up = ease_back((lt - 1.7) / 0.5)
    if lt < 1.8:   # sitting, holding phone, looking up
        c.rect(220, 1520, 860, 1640, (120, 70, 200), r=40)
        c.rect(200, 1440, 880, 1540, (140, 90, 220), r=40)
        kid(c, 440, 1640, s=1.25, la=10, ra=-150, rel=-115, legs="sit", mood="shock",
            hold_phone=True, t=t, look=0.5)
    else:          # stands up, phone flies away
        c.rect(220, 1520, 860, 1640, (120, 70, 200), r=40)
        c.rect(200, 1440, 880, 1540, (140, 90, 220), r=40)
        kid(c, W / 2, lerp(1640, 1780, up), s=lerp(1.25, 1.4, up), la=30, ra=-lerp(150, 170, up),
            mood="determined")
        ft = lt - 1.8
        phone(c, W / 2 + 120 + ft * 600, 700 - ft * 500 + ft * ft * 500, 90, 160, ang=-ft * 540)


def sc_steps(c, t, lt):
    sunburst(c, W / 2, 1200, (255, 255, 255), -lt * 15, alpha=30)
    T = lambda w, o=0: at("steps", w, o) - s0("steps")
    # phone into drawer / box
    if lt < T("Eine") + 0.2:
        c.rect(300, 1300, 780, 1640, (180, 110, 60), r=24)
        c.rect(300, 1300, 780, 1360, (150, 90, 50), r=24)
        p = ease_out((lt - T("weg")) / 0.5)
        if p < 1:
            phone(c, W / 2, lerp(950, 1350, p), 160, 290, ang=lerp(0, 20, p))
        c.rect(300, 1360, 780, 1640, (180, 110, 60), r=24)
        c.text(W / 2, 1500, "HANDY", 60, (110, 60, 30))
    elif lt < T("Sport") - 0.1:   # one hour timer + "nur für dich"
        prog = c01((lt - T("Eine")) / (T("Sport") - T("Eine")))
        c.circle(W / 2, 1200, 290, (255, 255, 255, 60))
        c.arc(W / 2, 1200, 270, -90, -90 + 360 * prog, WHITE, 40)
        rem = max(0, 3600 - int(prog * 900))
        c.text(W / 2, 1180, f"{rem // 60:02d}:{rem % 60:02d}", 120, WHITE, stroke=4, sfill=INK)
        if lt > T("Nur"):
            p = ease_back((lt - T("Nur")) / 0.35)
            c.text(W / 2, 1310, "NUR FÜR DICH", 46 * p, YELLOW, stroke=3, sfill=INK)
    else:                         # icons pop on each word
        items = [("Sport", dumbbell, 300, 1080), ("lernen", book, 780, 1080),
                 ("malen", brush, 300, 1500), ("rausgehen", tree, 780, 1500)]
        for w, fn, x, y in items:
            p = ease_back((lt - T(w)) / 0.35)
            if p > 0:
                wob = math.sin(lt * 3 + x) * 6
                c.circle(x, y + wob, 175 * p, (255, 255, 255, 235))
                fn(c, x, y + wob, 1.7 * p)
        if lt > T("Egal"):
            p = ease_back((lt - T("Egal")) / 0.3)
            c.circle(W / 2, 1290, 110 * p, YELLOW)
            c.line([(W / 2 - 50 * p, 1295), (W / 2 - 12 * p, 1335), (W / 2 + 55 * p, 1250)], INK, 22 * p)


def sc_future(c, t, lt):
    # sunset + hill
    glow(c, W / 2, 1300, 360, (255, 230, 150), a=30)
    c.circle(W / 2, 1300, 200, (255, 236, 160))
    c.ellipse(W / 2, 1900, 900, 380, (70, 50, 130))
    c.ellipse(W / 2 - 200, 1960, 800, 300, (95, 60, 160))
    jump = abs(math.sin(lt * 4)) * 60 * c01((lt - 0.8) / 0.3)
    kid(c, W / 2, 1600, s=1.1, la=165, ra=-165, mood="happy", legs="jump" if jump > 10 else "stand",
        bob=jump)
    # flag
    c.line([(W / 2 + 230, 1610), (W / 2 + 230, 1300)], WHITE, 10)
    wave_ = math.sin(lt * 6) * 14
    c.poly([(W / 2 + 235, 1300), (W / 2 + 400, 1330 + wave_), (W / 2 + 235, 1380)], YELLOW)
    # confetti
    rng = random.Random(3)
    for i in range(70):
        x = rng.uniform(0, W)
        sp = rng.uniform(250, 520)
        y = -60 + (lt * sp + rng.uniform(0, 900)) % 1900 if lt > 0.9 else -100
        col = rng.choice([(255, 90, 140), (80, 200, 255), YELLOW, (120, 230, 150), WHITE])
        a = lt * rng.uniform(2, 7)
        c.poly([(x + 12 * math.cos(a), y + 6 * math.sin(a)), (x - 12 * math.cos(a), y - 6 * math.sin(a)),
                (x - 12 * math.cos(a) + 6, y - 6 * math.sin(a) + 10)], col)


def sc_cta(c, t, lt):
    sunburst(c, W / 2, 1150, (255, 255, 255), lt * 8, alpha=18)
    T = lambda w, o=0: at("cta", w, o) - s0("cta")
    # big phone with "lock" that goes dark
    off = ease_out((lt - T("weg")) / 0.4)
    def screen(lc, x0, y0, x1, y1, tt):
        if off < 0.35:
            feed(lc, x0, y0, x1, y1, tt, speed=600)
        else:
            lc.d.rectangle([x0 * S, y0 * S, x1 * S, y1 * S], fill=(8, 8, 14))
    if lt < T("Und"):
        phone(c, W / 2, 1180, 380, 680, ang=lerp(-6, 0, off), content=screen, t=lt)
        if off > 0.3:
            p = ease_back((lt - T("weg") - 0.1) / 0.4)
            c.circle(W / 2, 1180, 120 * p, (255, 255, 255, 40))
            c.text(W / 2, 1180, "OFF", 80 * p, WHITE)
        if lt > T("Ja"):
            p = ease_back((lt - T("Ja")) / 0.3)
            c.text(W / 2, 1650, "(ja, genau du 👀)".replace("👀", ""), 54 * p, (255, 230, 240),
                   f=F_HAND)
    else:            # comment prompt
        p = ease_back((lt - T("Und")) / 0.45)
        y = 1240
        c.rect(110, y - 210 * p, 970, y + 210 * p, (255, 255, 255, 245), r=50)
        if p > 0.7:
            c.circle(210, y - 90, 50, HOOD)
            c.text(210, y - 92, "DU", 34, WHITE)
            c.text(290, y - 120, "@du · morgen", 34, (130, 130, 150), f=F_BODY, anchor="lm")
            c.text(290, y - 60, "Heute 1 Stunde", 44, INK, f=F_BODY, anchor="lm")
            c.text(290, y, "ohne Handy geschafft:", 44, INK, f=F_BODY, anchor="lm")
            blink = (lt * 2) % 1 < 0.6
            c.text(290, y + 70, "______" + ("|" if blink else ""), 52, (255, 60, 120), f=F_BODY,
                   anchor="lm")
            # heart + count
            hc = int(lerp(0, 2481, ease_out((lt - T("Kommentare")) / 1.5)))
            c.text(880, y + 140, f"♥ {hc}", 36, (255, 60, 120), f="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", anchor="rm")
        # pointing arrow
        if lt > T("Kommentare"):
            bounce = math.sin(lt * 8) * 18
            c.poly([(W / 2 - 60, 1560 + bounce), (W / 2 + 60, 1560 + bounce), (W / 2, 1650 + bounce)], YELLOW)


SCENE_DEF = {
    "hook":   (sc_hook,   (255, 92, 150), (150, 40, 170)),
    "scroll": (sc_scroll, (24, 16, 60),   (70, 30, 110)),
    "others": (sc_others, (70, 210, 190), (30, 130, 170)),
    "clock":  (sc_clock,  (16, 20, 60),   (60, 30, 90)),
    "turn":   (sc_turn,   (255, 170, 60), (240, 80, 90)),
    "steps":  (sc_steps,  (60, 200, 255), (90, 90, 240)),
    "future": (sc_future, (255, 130, 90), (120, 60, 170)),
    "cta":    (sc_cta,    (60, 30, 120),  (230, 60, 130)),
}

# ------------------------------------------------------------------ captions
HIGHLIGHT = {"drei", "stunden", "nicht", "andere", "vierundzwanzig", "app", "jetzt", "ändern",
             "weg", "stunde", "dich", "sport", "lernen", "malen", "rausgehen", "jahr", "danken",
             "kommentare", "geschafft", "video", "wischen", "trainieren", "bauen", "leben", "genau"}

WORDS = []
for i, sc in enumerate(TIM):
    ws = sc["words"]
    for j, w in enumerate(ws):
        st = OFF[i] + w["start"] - 0.03
        nxt = OFF[i] + ws[j + 1]["start"] - 0.03 if j + 1 < len(ws) else OFF[i] + sc["duration"]
        en = min(nxt, OFF[i] + w["end"] + 0.45)
        WORDS.append((st, en, w["text"].strip(".,!?").upper()))


@lru_cache(maxsize=256)
def caption_img(word):
    base = word.strip(".,!?")
    col = YELLOW if base.lower() in HIGHLIGHT else WHITE
    size = 150
    while size > 60 and font(F_HEAD, size).getlength(base) > 940:
        size -= 6
    f = font(F_HEAD, size)
    l, tp, r, b = f.getbbox(base, stroke_width=14)
    w, h = r - l + 40, b - tp + 60
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((20 - l, 38 - tp), base, font=f, fill=(0, 0, 0, 150),
                           stroke_width=14, stroke_fill=(0, 0, 0, 150))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    ImageDraw.Draw(im).text((20 - l, 20 - tp), base, font=f, fill=col, stroke_width=12, stroke_fill=INK)
    return im


def draw_caption(frame, t):
    for st, en, w in WORDS:
        if st <= t < en:
            p = c01((t - st) / 0.14)
            sc = lerp(1.35, 1.0, ease_out(p))
            im = caption_img(w)
            if sc != 1.0:
                im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BILINEAR)
            frame.alpha_composite(im, (int(W / 2 - im.width / 2), int(470 - im.height / 2)))
            return


# ------------------------------------------------------------------ frame
def scene_at(t):
    idx = 0
    for i, o in enumerate(OFF):
        if t >= o:
            idx = i
    return idx


def render_frame(n):
    t = n / FPS
    i = scene_at(t)
    key = KEYS[i]
    lt = t - OFF[i]
    fn, top, bot = SCENE_DEF[key]
    img = background(top, bot)
    c = C(img)
    fn(c, t, lt)
    frame = img.resize((W, H), Image.LANCZOS).convert("RGBA")
    # scene-in punch: quick zoom + white flash
    if lt < 0.18 and i > 0:
        k = 1 - lt / 0.18
        z = 1 + 0.08 * k
        frame = frame.resize((int(W * z), int(H * z)), Image.BILINEAR).crop(
            (int((W * z - W) / 2), int((H * z - H) / 2), int((W * z - W) / 2) + W, int((H * z - H) / 2) + H))
        frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(110 * k * k))))
    draw_caption(frame, t)
    # thin progress bar (retention)
    d = ImageDraw.Draw(frame)
    d.rectangle([0, H - 10, int(W * t / TOTAL), H], fill=YELLOW)
    # fade out
    if t > TOTAL - 0.5:
        frame.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * c01((t - TOTAL + 0.5) / 0.5)))))
    return frame.convert("RGB").tobytes()


# ------------------------------------------------------------------ audio
SR = 44100


def make_music():
    n = int(TOTAL * SR)
    tt = np.arange(n) / SR
    out = np.zeros(n)
    bpm = 104
    beat = 60 / bpm
    drop = s0("turn")
    # chord pad (Am - F - C - G), 2 bars each
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [261.63, 329.63, 392.0], [196.0, 246.94, 293.66]]
    bar = beat * 4
    for k in range(int(TOTAL / (bar * 2)) + 1):
        a, b = int(k * bar * 2 * SR), min(n, int((k + 1) * bar * 2 * SR))
        if a >= n:
            break
        seg = tt[a:b] - tt[a]
        env = np.minimum(1, seg / 0.4) * np.minimum(1, (seg[-1] - seg + 1e-3) / 0.4)
        for f in chords[k % 4]:
            for det in (0.997, 1.003):
                out[a:b] += 0.05 * env * np.sin(2 * np.pi * f * det * seg) + 0.02 * env * np.sin(4 * np.pi * f * det * seg)
    # dark filter before drop: simple lowpass via moving average, lighter after
    pre = int(drop * SR)
    ker = np.ones(40) / 40
    out[:pre] = np.convolve(out[:pre], ker, mode="same") * 0.8
    # beat after drop: kick + clap + hats
    kick_len = int(0.35 * SR)
    kt = np.arange(kick_len) / SR
    kick = np.sin(2 * np.pi * (50 + 110 * np.exp(-kt * 30)) * kt) * np.exp(-kt * 9)
    rng = np.random.default_rng(1)
    clap = rng.standard_normal(int(0.18 * SR)) * np.exp(-np.arange(int(0.18 * SR)) / SR * 22)
    hat = rng.standard_normal(int(0.05 * SR)) * np.exp(-np.arange(int(0.05 * SR)) / SR * 90)
    hat = np.diff(hat, prepend=0)
    bt = drop
    k = 0
    end_beat = TOTAL - 1.0
    while bt < end_beat:
        i = int(bt * SR)
        out[i:i + kick_len] += 0.55 * kick[:max(0, min(kick_len, n - i))]
        if k % 2 == 1:
            out[i:i + len(clap)] += 0.12 * clap[:max(0, min(len(clap), n - i))]
        j = int((bt + beat / 2) * SR)
        out[j:j + len(hat)] += 0.10 * hat[:max(0, min(len(hat), n - j))]
        bt += beat
        k += 1
    # heartbeat-ish tick before the drop (tension)
    bt = 0.0
    while bt < drop - 0.3:
        i = int(bt * SR)
        out[i:i + kick_len] += 0.18 * kick[:max(0, min(kick_len, n - i))]
        bt += beat * 2
    # riser into drop
    rl = int(1.5 * SR)
    a = max(0, pre - rl)
    noise = rng.standard_normal(pre - a)
    ramp = np.linspace(0, 1, pre - a) ** 2
    out[a:pre] += 0.12 * noise * ramp
    # whoosh on scene cuts
    for o in OFF[1:]:
        i = int(o * SR) - int(0.12 * SR)
        L = int(0.3 * SR)
        wn = rng.standard_normal(L) * np.sin(np.linspace(0, np.pi, L)) ** 2
        wn = np.convolve(wn, np.ones(8) / 8, mode="same")
        out[i:i + L] += 0.10 * wn[:max(0, min(L, n - i))]
    fade = np.minimum(1, (TOTAL - tt) / 1.0)
    out *= np.clip(fade, 0, 1)
    out = out / max(1e-6, np.abs(out).max()) * 0.9
    st = (np.clip(out, -1, 1) * 32767).astype(np.int16)
    p = BUILD / "music.wav"
    with wave.open(str(p), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(st.tobytes())
    return p


def make_voice():
    lst = BUILD / "concat.txt"
    lst.write_text("".join(f"file '{s['audio']}'\n" for s in TIM))
    p = BUILD / "voice.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-ar", str(SR), "-ac", "1", str(p)], check=True)
    return p


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        d = BUILD / "stills"
        d.mkdir(exist_ok=True)
        for a in sys.argv[2:]:
            n = int(float(a) * FPS)
            Image.frombytes("RGB", (W, H), render_frame(n)).save(d / f"t{float(a):05.1f}.png")
        print("stills ->", d)
        return
    voice, music = make_voice(), make_music()
    ff = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(voice), "-i", str(music),
        "-filter_complex",
        "[1:a]apad,volume=1.6,asplit=2[v][vs];[2:a]volume=0.32[m];[m][vs]sidechaincompress=threshold=0.05:ratio=6:attack=20:release=300[md];"
        "[v][md]amix=inputs=2:normalize=0:duration=shortest,alimiter=limit=0.95[a]",
        "-map", "0:v", "-map", "[a]", "-t", f"{TOTAL:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(OUT)], stdin=subprocess.PIPE)
    with Pool() as pool:
        for k, fr in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=8)):
            ff.stdin.write(fr)
            if k % 150 == 0:
                print(f"{k}/{NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("->", OUT)


if __name__ == "__main__":
    main()
