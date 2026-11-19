"""Shared flat-illustration helpers (canvas, easing, props, cartoon kid).
Copied from src/motivation/render.py so this video builds on its own."""
import math
import random
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent.parent
FONTS = ROOT / "fonts"
W, H, FPS = 1080, 1920, 30
S = 2
F_HEAD = str(FONTS / "Unbounded_900Black.ttf")
F_HEAD_B = str(FONTS / "Unbounded_700Bold.ttf")
F_HAND = str(FONTS / "Caveat_700Bold.ttf")
F_BODY = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

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

