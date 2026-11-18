"""Vector cartoon toolkit: camera-aware pen (2x supersampled), car, stick-figure hero, hand, bubbles."""
import math
import random
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fuehrerschein"))
from core import (W, H, FPS, font, clamp01, lerp, ease_out, ease_in, ease_io, ease_back, mixc,  # noqa: E402,F401
                  gradient, radial, glow_dot, paste_c, zoom_frame, text_img, emoji, F_EMOJI)

SS = 2  # supersampling factor for all vector drawing

OUT = (8, 10, 16)
SKIN = (240, 188, 148)
SKIN_D = (205, 150, 115)
SHIRT = (255, 196, 52)
SHIRT_D = (210, 150, 30)
PANTS = (38, 48, 78)
HAIR = (46, 30, 24)
CAR = (150, 166, 182)
CAR_D = (96, 110, 128)
CAR_L = (205, 218, 230)
GLASS = (70, 120, 150)
RED = (236, 38, 44)
RED_D = (150, 16, 24)
TEAL = (40, 190, 175)
WATER_TOP = (24, 112, 112)
WATER_BOT = (2, 14, 24)
NIGHT_TOP = (5, 8, 22)
NIGHT_BOT = (16, 36, 52)
LAMP = (255, 214, 120)


def rgba(c, a=255):
    return tuple(c[:3]) + (int(a),)


@lru_cache(maxsize=12)
def grad2x(top, bot):
    return gradient(W * SS, H * SS, top, bot)


class Pen:
    """Draws world-space shapes through a 2D camera (center x/y, zoom, rotation, optional mirror)."""

    def __init__(self, cam, top=NIGHT_TOP, bot=NIGHT_BOT, img=None):
        cx, cy, z, rot = cam[:4]
        flip = cam[4] if len(cam) > 4 else 1
        self.img = img if img is not None else grad2x(top, bot).copy()
        self.d = ImageDraw.Draw(self.img, "RGBA")
        a = math.radians(rot)
        c, s = math.cos(a) * z, math.sin(a) * z
        # screen = R*(flip*(p - cam)) + center
        M = np.array([[c * flip, -s, 0], [s * flip, c, 0], [0, 0, 1.0]])
        T = np.array([[1, 0, -cx], [0, 1, -cy], [0, 0, 1.0]])
        C = np.array([[1, 0, W / 2], [0, 1, H / 2], [0, 0, 1.0]])
        self.M = C @ M @ T
        self.z = z
        self.stack = []

    # ---- transforms
    def push(self, x=0, y=0, ang=0, sx=1.0, sy=None):
        sy = sx if sy is None else sy
        a = math.radians(ang)
        c, s = math.cos(a), math.sin(a)
        L = np.array([[c * sx, -s * sy, x], [s * sx, c * sy, y], [0, 0, 1.0]])
        self.stack.append((self.M, self.z))
        self.M = self.M @ L
        self.z *= (abs(sx) + abs(sy)) / 2

    def pop(self):
        self.M, self.z = self.stack.pop()

    def P(self, pts):
        a = np.asarray(pts, np.float64).reshape(-1, 2)
        o = (a @ self.M[:2, :2].T + self.M[:2, 2]) * SS
        return [tuple(p) for p in o]

    def screen(self, x, y):
        p = self.P([(x, y)])[0]
        return p[0] / SS, p[1] / SS

    def lw(self, w):
        return max(1, int(round(w * self.z * SS)))

    # ---- primitives
    def poly(self, pts, fill=None, ol=OUT, w=0):
        P = self.P(pts)
        if len(P) < 3:
            return
        if fill is not None:
            self.d.polygon(P, fill=fill)
        if ol is not None and w:
            lw = self.lw(w)
            self.d.line(P + [P[0], P[1]], fill=ol, width=lw, joint="curve")

    def ell(self, cx, cy, rx, ry=None, fill=None, ol=OUT, w=0, ang=0, n=44):
        ry = rx if ry is None else ry
        th = np.linspace(0, 2 * np.pi, n, endpoint=False)
        x, y = rx * np.cos(th), ry * np.sin(th)
        if ang:
            a = math.radians(ang)
            x, y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
        self.poly(np.c_[cx + x, cy + y], fill, ol, w)

    def rect(self, x0, y0, x1, y1, fill=None, ol=OUT, w=0):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, ol, w)

    def rrect(self, x0, y0, x1, y1, r, fill=None, ol=OUT, w=0):
        r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
        pts = []
        for (cx, cy, a0) in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
            for k in range(7):
                a = math.radians(a0 + k * 15)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        self.poly(pts, fill, ol, w)

    def line(self, pts, col, w, cap=True):
        P = self.P(pts)
        lw = self.lw(w)
        self.d.line(P, fill=col, width=lw, joint="curve")
        if cap and lw > 3:
            r = lw / 2
            for p in (P[0], P[-1]):
                self.d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=col)

    def limb(self, pts, col, w, ow=7):
        """Thick outlined limb (outline first, colour on top)."""
        self.line(pts, OUT, w + 2 * ow)
        self.line(pts, col, w)

    def arc(self, cx, cy, r, a0, a1, col, w, n=24):
        th = np.radians(np.linspace(a0, a1, n))
        self.line(np.c_[cx + r * np.cos(th), cy + r * np.sin(th)], col, w)

    def arrow(self, x0, y0, x1, y1, w, fill, ol=OUT, ow=7, head=2.2):
        ang = math.atan2(y1 - y0, x1 - x0)
        L = math.hypot(x1 - x0, y1 - y0)
        hl = min(L * 0.5, w * head)
        ca, sa = math.cos(ang), math.sin(ang)

        def p(u, v):
            return (x0 + ca * u - sa * v, y0 + sa * u + ca * v)
        pts = [p(0, -w / 2), p(L - hl, -w / 2), p(L - hl, -w * 1.15), p(L, 0), p(L - hl, w * 1.15), p(L - hl, w / 2),
               p(0, w / 2)]
        self.poly(pts, fill, ol, ow)

    def finish(self):
        return self.img.reduce(SS)


# ---------------------------------------------------------------- environment pieces
def god_rays(pen, t, x0=-200, x1=1300, y0=-200, length=2200, n=7, col=(140, 230, 215), alpha=16, seed=1):
    r = random.Random(seed)
    for i in range(n):
        x = lerp(x0, x1, (i + 0.5) / n) + 60 * math.sin(t * 0.9 + i * 1.7)
        wdt = 70 + 90 * r.random()
        sk = 120 + 160 * r.random()
        a = alpha * (0.6 + 0.4 * math.sin(t * 1.3 + i))
        pen.poly([(x - wdt / 2, y0), (x + wdt / 2, y0), (x + wdt * 1.8 + sk, y0 + length), (x - wdt * 1.4 + sk, y0 + length)],
                 rgba(col, a), None)


def specks(pen, t, n=60, seed=3, area=(-200, -200, 1280, 2120), col=(160, 220, 210), drift=(8, -20), size=4):
    r = random.Random(seed)
    x0, y0, x1, y1 = area
    for i in range(n):
        x = x0 + (r.random() * (x1 - x0) + drift[0] * t * (0.5 + r.random())) % (x1 - x0)
        y = y0 + (r.random() * (y1 - y0) + drift[1] * t * (0.5 + r.random())) % (y1 - y0)
        s = size * (0.4 + r.random())
        pen.ell(x, y, s, fill=rgba(col, 60 + 80 * r.random()), ol=None, n=8)


def bubble(pen, x, y, r, a=1.0):
    if r < 1:
        return
    pen.ell(x, y, r, fill=(170, 240, 235, int(40 * a)), ol=(205, 255, 250, int(210 * a)), w=max(1.5, r * 0.12),
            n=max(10, min(36, int(r))))
    pen.ell(x - r * 0.35, y - r * 0.38, r * 0.28, r * 0.18, fill=(255, 255, 255, int(200 * a)), ol=None, ang=-30, n=12)


def bubble_burst(pen, t, ox, oy, n=60, seed=5, spread=900, rise=500, rmin=6, rmax=40, life=1.4, t0=0.0):
    """Deterministic bubble explosion from (ox, oy) starting at local time t0."""
    r = random.Random(seed)
    for i in range(n):
        st = t0 + r.random() * 0.25
        age = t - st
        ang = r.uniform(0, 2 * math.pi)
        sp = spread * (0.25 + r.random())
        rad = rmin + (rmax - rmin) * r.random() ** 2
        lf = life * (0.6 + 0.6 * r.random())
        if age < 0 or age > lf:
            continue
        k = 1 - math.exp(-age * 3.2)
        x = ox + math.cos(ang) * sp * k / 3.2 * 2 + 25 * math.sin(age * 7 + i)
        y = oy + math.sin(ang) * sp * k / 3.2 * 2 - rise * age * age
        bubble(pen, x, y, rad * (0.6 + 0.6 * k), a=1 - clamp01((age - lf * 0.7) / (lf * 0.3)))


def bubble_column(pen, t, x, y, n=18, seed=9, height=900, speed=420, rmax=16, wobble=20):
    r = random.Random(seed)
    for i in range(n):
        ph = r.random()
        yy = y - ((t * speed * (0.7 + 0.5 * r.random()) + ph * height) % height)
        xx = x + wobble * math.sin(t * 6 + i * 2.1) + r.uniform(-30, 30)
        bubble(pen, xx, yy, 3 + rmax * r.random(), 0.9)


def wave_line(x0, x1, y, amp, t, k=0.012, speed=2.2, n=60, phase=0.0):
    xs = np.linspace(x0, x1, n)
    ys = y + amp * np.sin(xs * k + t * speed + phase) + amp * 0.5 * np.sin(xs * k * 2.3 - t * speed * 1.4 + phase)
    return np.c_[xs, ys]


# ---------------------------------------------------------------- car
CAR_BODY = [(-282, 40), (-284, -12), (-256, -42), (-128, -52), (-74, -120), (92, -126), (162, -56), (262, -46),
            (288, -10), (288, 40), (254, 58), (-254, 58)]
CAR_LOWER = [(-282, 40), (-284, -12), (-256, -42), (-128, -52), (-70, -58), (150, -58), (162, -56), (262, -46),
             (288, -10), (288, 40), (254, 58), (-254, 58)]
REAR_WIN = [(-62, -110), (0, -113), (0, -60), (-108, -57)]
FRONT_WIN = [(12, -113), (84, -115), (144, -60), (12, -60)]


def car_side(pen, x, y, s, ang, lights=True, front_open=0.0, inside=None, glass_col=GLASS, door_glow=0.0,
             crack=0.0):
    """Side view, facing +x. inside(pen) draws occupants (in car coords) between glass and body."""
    pen.push(x, y, ang, s)
    if lights:
        pen.poly([(286, -24), (900, -150), (900, 160), (286, 0)], (255, 230, 150, 34), None)
    # cabin + body silhouette
    pen.poly(CAR_BODY, CAR, OUT, 9)
    # interior darkness behind windows
    pen.poly(REAR_WIN, (14, 22, 32), None)
    pen.poly(FRONT_WIN, (14, 22, 32), None)
    if inside:
        inside(pen)
    # glass
    pen.poly(REAR_WIN, rgba(glass_col, 150), OUT, 5)
    gtop = lerp(-113, -60, front_open)
    if front_open < 0.98:
        fw = [(12, gtop), (lerp(84, 144, front_open), gtop), (144, -60), (12, -60)]
        pen.poly(fw, rgba(glass_col, 150), None)
        pen.line([(26, gtop + 8), (46, gtop + 8 + 30)], (220, 245, 255, 120), 6)
    pen.poly(FRONT_WIN, None, OUT, 5)
    # lower body drawn again so occupants are hidden below the window line
    pen.poly(CAR_LOWER, CAR, OUT, 9)
    pen.poly([(-282, 18), (288, 18), (288, 40), (254, 58), (-254, 58), (-282, 40)], CAR_D, None)
    pen.line([(-250, -36), (150, -50), (258, -40)], CAR_L, 5)
    # door seams + handles
    pen.line([(6, -58), (6, 48)], OUT, 4)
    pen.line([(-118, -50), (-118, 48)], OUT, 4)
    pen.line([(150, -56), (158, 46)], OUT, 4)
    pen.rrect(-70, -36, -38, -26, 4, (60, 70, 84), OUT, 3)
    pen.rrect(60, -36, 92, -26, 4, (60, 70, 84), OUT, 3)
    if door_glow > 0:
        pen.poly([(6, -118), (90, -120), (150, -56), (158, 48), (6, 48)], None, rgba(RED, 255 * door_glow), 10)
    # mirror, lights
    pen.poly([(140, -66), (168, -80), (176, -62), (150, -54)], CAR_D, OUT, 4)
    pen.ell(272, -24, 16, 12, LAMP if lights else (120, 110, 80), OUT, 4)
    pen.rect(-284, -34, -268, -6, RED, OUT, 4)
    # wheels
    for wx in (-168, 176):
        pen.ell(wx, 56, 50, fill=(22, 24, 30), ol=OUT, w=6)
        pen.ell(wx, 56, 22, fill=(120, 130, 140), ol=OUT, w=4)
    if crack > 0:
        r = random.Random(4)
        for k in range(9):
            a = r.uniform(0, 2 * math.pi)
            L = 50 * crack * (0.5 + r.random())
            pen.line([(110, -80), (110 + math.cos(a) * L, -80 + math.sin(a) * L)], (240, 250, 255), 3)
    pen.pop()


def car_front(pen, x, y, s, ang, lights=True, face=None, sy=1.0):
    """Front view. face: expression for a tiny driver visible behind the windshield."""
    pen.push(x, y, ang, s, s * sy)
    pen.poly([(-168, -232), (168, -232), (226, -86), (-226, -86)], CAR, OUT, 9)
    pen.poly([(-150, -212), (150, -212), (196, -98), (-196, -98)], (16, 26, 36), None)
    if face:
        head(pen, -70, -142, 34, face, look=(0, 0.4))
        pen.limb([(-108, -98), (-130, -160)], SHIRT, 12, 4)
        pen.limb([(-32, -98), (-10, -162)], SHIRT, 12, 4)
    pen.poly([(-150, -212), (150, -212), (196, -98), (-196, -98)], rgba(GLASS, 120), OUT, 6)
    pen.line([(-120, -196), (-150, -120)], (220, 245, 255, 110), 8)
    pen.rrect(-268, -96, 268, 96, 40, CAR, OUT, 9)
    pen.rect(-262, 40, 262, 90, CAR_D, None)
    pen.rrect(-112, -10, 112, 52, 14, (30, 34, 42), OUT, 6)
    for gx in range(-90, 100, 30):
        pen.line([(gx, -2), (gx, 44)], (70, 76, 88), 4, cap=False)
    for sx_ in (-1, 1):
        pen.ell(sx_ * 186, 4, 50, 36, LAMP if lights else (110, 100, 70), OUT, 6)
        pen.ell(sx_ * 186 - 14, -6, 16, 10, (255, 255, 230), None)
        pen.ell(sx_ * 262, -118, 30, 22, CAR_D, OUT, 5)
        pen.rrect(sx_ * 210 - 40, 86, sx_ * 210 + 40, 150, 14, (22, 24, 30), OUT, 6)
    pen.rrect(-280, 66, 280, 108, 20, (70, 80, 94), OUT, 7)
    pen.rect(-60, 70, 60, 98, (225, 230, 235), OUT, 4)
    pen.line([(-240, -60), (240, -60)], CAR_L, 5)
    pen.pop()


# ---------------------------------------------------------------- hero
def head(pen, x, y, r, expr="neutral", look=(0, 0), blink=0.0, brow=0.0, wet=False, ang=0):
    pen.push(x, y, ang, r / 100)
    # ears
    for sx_ in (-1, 1):
        pen.ell(sx_ * 98, 8, 18, 26, SKIN, OUT, 7)
    pen.ell(0, 0, 100, 104, SKIN, OUT, 9)
    pen.ell(0, 46, 82, 44, rgba(SKIN_D, 70), None)
    # hair
    hair = [(-100, -6), (-96, -46), (-72, -86), (-30, -106), (16, -110), (58, -98), (90, -66), (102, -20), (80, -40),
            (56, -58), (40, -46), (14, -66), (-20, -54), (-50, -64), (-78, -34)]
    pen.poly(hair, HAIR, OUT, 7)
    if wet:
        for dx in (-62, 70):
            pen.ell(dx, -30, 7, 11, (170, 230, 240, 220), OUT, 3)
    # eyes
    lx, ly = look
    for sx_ in (-1, 1):
        ex = sx_ * 36
        if blink > 0.6:
            pen.line([(ex - 20, -2), (ex + 20, -2)], OUT, 6)
            continue
        ry = 30 if expr in ("panic", "gasp") else 26
        pen.ell(ex, -4, 24, ry * (1 - blink), (255, 255, 255), OUT, 6)
        pr = 9 if expr in ("panic", "gasp") else 12
        pen.ell(ex + lx * 9, -4 + ly * 12, pr, pr * (1 - blink), OUT, None)
        pen.ell(ex + lx * 9 - 3, -8 + ly * 12, 3.5, fill=(255, 255, 255), ol=None, n=8)
    # brows
    if expr in ("panic", "gasp"):
        b = [(-58, -46 - brow), (-18, -58 - brow)], [(18, -58 - brow), (58, -46 - brow)]
    elif expr == "determined":
        b = [(-58, -48), (-16, -38)], [(16, -38), (58, -48)]
    elif expr == "sly":
        b = [(-58, -44), (-16, -42)], [(16, -52 - brow), (58, -62 - brow)]
    else:
        b = [(-56, -44 - brow), (-18, -48 - brow)], [(18, -48 - brow), (56, -44 - brow)]
    for seg in b:
        pen.line(seg, OUT, 9)
    # mouth
    if expr == "panic":
        pen.ell(0, 52, 22, 26, (90, 20, 30), OUT, 6)
        pen.ell(0, 64, 12, 8, (220, 90, 100), None)
    elif expr == "gasp":
        pen.ell(0, 50, 28, 34, (90, 20, 30), OUT, 6)
        pen.ell(0, 66, 16, 10, (220, 90, 100), None)
    elif expr == "determined":
        pen.line([(-24, 52), (24, 52)], OUT, 8)
    elif expr == "sly":
        pen.line([(-26, 54), (0, 56), (26, 46)], OUT, 8)
    elif expr == "relief":
        pen.arc(0, 30, 30, 20, 160, OUT, 8)
    else:
        pen.line([(-20, 54), (20, 54)], OUT, 8)
    if expr == "panic":
        pen.poly([(84, -60), (94, -36), (88, -24), (78, -28), (76, -40)], (170, 230, 255, 230), OUT, 4)
    pen.pop()


def person(pen, x, y, s, ang=0, la=(160, 30), ra=(-160, -30), ll=(10, 0), rl=(-10, 0), expr="neutral", look=(0, 0),
           blink=0.0, silhouette=None, wet=False):
    """Upright figure centred on torso. Arm/leg angles: (upper, lower-bend) degrees from straight down."""
    pen.push(x, y, ang, s)
    col_sh = SHIRT if silhouette is None else silhouette
    col_p = PANTS if silhouette is None else silhouette
    col_sk = SKIN if silhouette is None else silhouette

    def chain(o, a1, a2, L1, L2):
        p1 = (o[0] + L1 * math.sin(math.radians(a1)), o[1] + L1 * math.cos(math.radians(a1)))
        p2 = (p1[0] + L2 * math.sin(math.radians(a1 + a2)), p1[1] + L2 * math.cos(math.radians(a1 + a2)))
        return [o, p1, p2]

    for leg, ox in ((ll, -24), (rl, 24)):
        pts = chain((ox, 60), leg[0], leg[1], 70, 66)
        pen.limb(pts, col_p, 34)
        pen.ell(pts[-1][0], pts[-1][1] + 6, 24, 14, (30, 30, 36) if silhouette is None else silhouette, OUT, 5)
    pen.rrect(-56, -70, 56, 76, 34, col_sh, OUT, 8)
    if silhouette is None:
        pen.line([(-40, 30), (40, 30)], SHIRT_D, 6)
    for arm, ox in ((la, -48), (ra, 48)):
        pts = chain((ox, -50), arm[0], arm[1], 62, 58)
        pen.limb(pts, col_sh, 30)
        pen.ell(pts[-1][0], pts[-1][1], 19, fill=col_sk, ol=OUT, w=6)
    pen.pop()
    if silhouette is None:
        pen.push(x, y, ang, s)
        head(pen, 0, -150, 82, expr, look, blink, wet=wet)
        pen.pop()
    else:
        pen.push(x, y, ang, s)
        pen.ell(0, -150, 82, 86, silhouette, OUT, 6)
        pen.pop()


def hand(pen, x, y, s, ang=0, curl=1.0, sleeve=True, thumb_out=0.0):
    """Big cartoon hand, fingers pointing +x, palm centre at origin."""
    pen.push(x, y, ang, s)
    if sleeve:
        pen.rrect(-260, -62, -70, 62, 22, SHIRT, OUT, 8)
        pen.rect(-110, -64, -84, 64, SHIRT_D, None)
    pen.rrect(-90, -58, 40, 58, 34, SKIN, OUT, 8)
    for k, fy in enumerate((-42, -14, 14, 42)):
        L = 70 - abs(k - 1.5) * 8
        bend = curl * 70
        p0 = (30, fy)
        p1 = (30 + L * 0.6, fy)
        p2 = (p1[0] + L * 0.5 * math.cos(math.radians(bend)), fy + L * 0.5 * math.sin(math.radians(bend)))
        pen.limb([p0, p1, p2], SKIN, 24, 6)
    ta = -40 - 50 * thumb_out
    pen.limb([(-20, -40), (-20 + 44 * math.cos(math.radians(ta)), -40 + 44 * math.sin(math.radians(ta))),
              (-20 + 80 * math.cos(math.radians(ta + 30)), -40 + 80 * math.sin(math.radians(ta + 30)))], SKIN, 26, 6)
    pen.pop()


def hammer(pen, x, y, s, ang):
    pen.push(x, y, ang, s)
    pen.rrect(-30, -20, 230, 20, 16, RED, OUT, 8)
    pen.rect(150, -20, 170, 20, RED_D, None)
    pen.rrect(-70, -60, 10, 60, 14, (40, 42, 50), OUT, 8)
    pen.poly([(-70, -60), (-100, -82), (-74, -40)], (200, 210, 220), OUT, 6)
    pen.poly([(-70, 60), (-100, 82), (-74, 40)], (200, 210, 220), OUT, 6)
    pen.line([(-50, -40), (-10, -40)], (120, 125, 140), 5)
    pen.pop()
