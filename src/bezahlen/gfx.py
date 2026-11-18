"""Gemeinsame Grafik-Bausteine (Cairo) für die Bezahl-Erklärfilme: Farben, Easing,
abgerundete Kästen mit Glow/Schatten, Text, Symbole, Partikel, Strichfigur, Hintergrund."""
import math
import random

import cairo

W, H = 1080, 1920


# ------------------------------------------------------------------ Farben
def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


BG1, BG2 = hexc("#10245a"), hexc("#060f2a")
PANEL = hexc("#15285a")
PANEL2 = hexc("#1e3778")
LANE = hexc("#10214b")
INK = hexc("#0a1530")
WHITE = (1, 1, 1)
MUTED = hexc("#93a6d4")
YEL = hexc("#ffcf2e")
RED = hexc("#ff4757")
TEAL = hexc("#2fe0d0")
ORANGE = hexc("#ff8a1f")
GREEN = hexc("#4be38a")
PURPLE = hexc("#7b5cff")

BLACK_F = "Inter Display Black"
XB_F = "Inter Display ExtraBold"


# ------------------------------------------------------------------ Easing
def cl(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease(x):
    x = cl(x)
    return x * x * (3 - 2 * x)


def eout(x):
    x = cl(x)
    return 1 - (1 - x) ** 3


def eback(x, s=1.7):
    x = cl(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def win(t, t0, t1, fin=0.25, fout=0.25):
    if t < t0 or t > t1:
        return 0.0
    return min(eout((t - t0) / fin) if fin else 1.0, eout((t1 - t) / fout) if fout else 1.0)


def lerp(a, b, k):
    return a + (b - a) * k


def mix(c1, c2, k):
    return tuple(lerp(a, b, k) for a, b in zip(c1, c2))


# ------------------------------------------------------------------ Cairo-Helfer
def rgba(c, col, a=1.0):
    c.set_source_rgba(col[0], col[1], col[2], a)


def rrect(c, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    c.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    c.close_path()


def fill_rrect(c, x, y, w, h, r, col, a=1.0):
    rrect(c, x, y, w, h, r)
    rgba(c, col, a)
    c.fill()


def glow_rrect(c, x, y, w, h, r, col, a=1.0, width=4):
    """Leuchtender Rand (Neon-Effekt) aus mehreren weichen Strichen."""
    for lw, al in ((width + 26, 0.05), (width + 16, 0.09), (width + 8, 0.16)):
        rrect(c, x, y, w, h, r)
        rgba(c, col, al * a)
        c.set_line_width(lw)
        c.stroke()
    rrect(c, x, y, w, h, r)
    rgba(c, col, a)
    c.set_line_width(width)
    c.stroke()


def shadow_rrect(c, x, y, w, h, r, a=0.45, dy=12):
    for k, al in ((26, 0.10), (16, 0.14), (8, 0.18)):
        fill_rrect(c, x - k / 2, y + dy - k / 2 + 6, w + k, h + k, r + k / 2, hexc("#020716"), al * a / 0.45)


def font(c, size, face=BLACK_F):
    c.select_font_face(face, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)


def text_w(c, s, size, face=BLACK_F):
    font(c, size, face)
    return c.text_extents(s).x_advance


def text(c, s, x, y, size, col, a=1.0, face=BLACK_F, align="c", maxw=None, outline=0, ocol=INK, glow=None):
    """y = optische Mitte der Großbuchstaben."""
    if maxw:
        while size > 10 and text_w(c, s, size, face) > maxw:
            size -= 1
    font(c, size, face)
    adv = c.text_extents(s).x_advance
    x0 = {"c": x - adv / 2, "l": x, "r": x - adv}[align]
    base = y + 0.36 * size
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    if glow:
        for lw, al in ((size * 0.5, 0.06), (size * 0.3, 0.1), (size * 0.15, 0.18)):
            c.move_to(x0, base)
            c.text_path(s)
            rgba(c, glow, al * a)
            c.set_line_width(lw)
            c.stroke()
    if outline:
        c.move_to(x0, base)
        c.text_path(s)
        rgba(c, ocol, a)
        c.set_line_width(outline)
        c.stroke()
    c.move_to(x0, base)
    rgba(c, col, a)
    c.show_text(s)
    return adv


def euro(v, dec=False):
    if dec:
        return f"{v:.2f}".replace(".", ",") + " €"
    return f"{int(round(v))} €"


class Saved:
    def __init__(self, c, alpha=1.0, x=0.0, y=0.0, scale=1.0, rot=0.0):
        self.c, self.alpha, self.x, self.y, self.scale, self.rot = c, alpha, x, y, scale, rot

    def __enter__(self):
        c = self.c
        if self.alpha < 0.999:
            c.push_group()
        c.save()
        c.translate(self.x, self.y)
        if self.rot:
            c.rotate(self.rot)
        if self.scale != 1.0:
            c.scale(self.scale, self.scale)
        return c

    def __exit__(self, *a):
        c = self.c
        c.restore()
        if self.alpha < 0.999:
            c.pop_group_to_source()
            c.paint_with_alpha(max(0.0, self.alpha))


# ------------------------------------------------------------------ Symbole
def icon(c, kind, s=44, a=1.0, col=None):
    c.save()
    c.scale(s / 44, s / 44)
    c.set_line_width(3.2)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    if kind == "kaffee":
        c.move_to(-14, -8); c.line_to(14, -8); c.line_to(11, 16); c.line_to(-11, 16); c.close_path()
        rgba(c, WHITE, a); c.fill_preserve(); rgba(c, hexc("#8a5a3a"), a); c.stroke()
        fill_rrect(c, -14, -2, 28, 8, 2, hexc("#8a5a3a"), a)
        c.arc(16, 4, 6, -math.pi / 2, math.pi / 2); rgba(c, WHITE, a); c.stroke()
        for dx in (-6, 2):
            c.move_to(dx, -13); c.curve_to(dx - 4, -17, dx + 4, -20, dx, -24); rgba(c, WHITE, a * 0.7); c.stroke()
    elif kind == "snack":
        c.save(); c.rotate(-0.35)
        fill_rrect(c, -16, -9, 32, 18, 4, hexc("#ff9a3c"), a)
        fill_rrect(c, -9, -9, 18, 18, 2, hexc("#6b3b1f"), a)
        for sx in (-1, 1):
            c.move_to(sx * 16, -9)
            for k in range(4):
                c.line_to(sx * (16 + (5 if k % 2 == 0 else 0)), -9 + (k + 1) * 4.5)
            c.line_to(sx * 16, 9); c.close_path(); rgba(c, hexc("#ff9a3c"), a); c.fill()
        c.restore()
    elif kind == "zeitschrift":
        fill_rrect(c, -13, -17, 26, 34, 3, hexc("#ff7ab6"), a)
        fill_rrect(c, -9, -13, 18, 9, 2, WHITE, a)
        for yy in (2, 7, 12):
            c.move_to(-8, yy); c.line_to(8, yy); rgba(c, WHITE, a * 0.85); c.stroke()
    elif kind == "online":
        c.move_to(-16, -6); c.line_to(0, -14); c.line_to(16, -6); c.line_to(16, 12); c.line_to(0, 19)
        c.line_to(-16, 12); c.close_path(); rgba(c, hexc("#d6a066"), a); c.fill()
        c.move_to(-16, -6); c.line_to(0, 2); c.line_to(16, -6); c.move_to(0, 2); c.line_to(0, 19)
        rgba(c, hexc("#8a5a2a"), a); c.stroke()
        c.move_to(-8, -10); c.line_to(8, -2); rgba(c, WHITE, a * 0.9); c.stroke()
    elif kind == "einkauf":
        fill_rrect(c, -15, -8, 30, 26, 4, hexc("#c9d6f5"), a)
        c.arc(0, -8, 8, math.pi, 0); rgba(c, hexc("#c9d6f5"), a); c.stroke()
        c.move_to(-6, 4); c.line_to(-1, 9); c.line_to(7, -1); rgba(c, hexc("#2c8a4a"), a); c.stroke()
    elif kind == "coin":
        c.arc(0, 0, 14, 0, 2 * math.pi); rgba(c, hexc("#ffd34d"), a); c.fill_preserve()
        rgba(c, hexc("#c99410"), a); c.stroke()
        text(c, "€", 0, 0, 16, hexc("#8a6200"), a)
    elif kind == "bills":
        for k, off in enumerate((-4, 0, 4)):
            fill_rrect(c, -20 + off, -12 + off * 0.5, 40, 24, 3, hexc("#9fe0a8") if k % 2 else hexc("#7ccf86"), a)
        text(c, "€", 4, 2, 15, hexc("#1f6b2c"), a)
    elif kind == "card":
        fill_rrect(c, -20, -13, 40, 26, 4, RED, a)
        fill_rrect(c, -14, -6, 9, 7, 1.5, hexc("#ffd34d"), a)
        c.move_to(-14, 7); c.line_to(10, 7); rgba(c, WHITE, a * 0.8); c.stroke()
    elif kind == "phone":
        fill_rrect(c, -12, -20, 24, 40, 5, hexc("#0b1a33"), a)
        fill_rrect(c, -9, -16, 18, 30, 2, TEAL, a)
        c.arc(0, 17, 1.6, 0, 2 * math.pi); rgba(c, WHITE, a); c.fill()
    elif kind == "bell":
        c.move_to(-11, 8); c.curve_to(-11, -14, 11, -14, 11, 8); c.line_to(14, 11); c.line_to(-14, 11)
        c.close_path(); rgba(c, col or INK, a); c.fill()
        c.arc(0, 14, 3.5, 0, 2 * math.pi); c.fill()
    elif kind == "list":
        fill_rrect(c, -15, -19, 30, 38, 4, WHITE, a)
        for yy in (-9, 0, 9):
            c.move_to(-9, yy); c.line_to(-6, yy + 3); c.line_to(-2, yy - 3); rgba(c, hexc("#2c8a4a"), a); c.stroke()
            c.move_to(2, yy); c.line_to(10, yy); rgba(c, hexc("#9aa8c8"), a); c.stroke()
    elif kind == "calendar":
        fill_rrect(c, -17, -15, 34, 32, 4, WHITE, a)
        fill_rrect(c, -17, -15, 34, 10, 4, RED, a)
        text(c, "30", 0, 6, 15, INK, a)
    elif kind == "comment":
        rrect(c, -18, -15, 36, 26, 9); rgba(c, col or WHITE, a); c.fill()
        c.move_to(-8, 10); c.line_to(-12, 19); c.line_to(2, 10); c.close_path(); c.fill()
        for dx in (-8, 0, 8):
            c.arc(dx, -2, 2.6, 0, 2 * math.pi); rgba(c, INK, a); c.fill()
    elif kind == "cursor":
        c.move_to(0, 0); c.line_to(0, 30); c.line_to(8, 23); c.line_to(14, 36); c.line_to(19, 34)
        c.line_to(13, 21); c.line_to(23, 21); c.close_path()
        rgba(c, WHITE, a); c.fill_preserve(); rgba(c, INK, a); c.set_line_width(2.5); c.stroke()
    c.restore()


def skip_icon(c, kind, s, a):
    icon(c, kind, s, a * 0.55)
    c.set_line_width(5)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    r = s * 0.42
    c.move_to(-r, -r); c.line_to(r, r); c.move_to(r, -r); c.line_to(-r, r)
    rgba(c, RED, a); c.stroke()


# ------------------------------------------------------------------ Partikel
def burst(c, t, t0, x, y, n=46, seed=1, kinds=("rect",), cols=(YEL, RED, TEAL, ORANGE, WHITE), speed=900,
          life=1.6, grav=1400, size=1.0):
    d = t - t0
    if d < 0 or d > life:
        return
    rnd = random.Random(seed)
    for i in range(n):
        ang = rnd.uniform(-math.pi, 0) if rnd.random() < 0.85 else rnd.uniform(0, math.pi)
        sp = rnd.uniform(0.35, 1.0) * speed
        vx, vy = math.cos(ang) * sp, math.sin(ang) * sp - 250
        px = x + vx * d
        py = y + vy * d + 0.5 * grav * d * d
        rot = rnd.uniform(0, 6) + d * rnd.uniform(-9, 9)
        a = cl(1 - d / life) * 1.4
        kind = rnd.choice(kinds)
        col = rnd.choice(cols)
        with Saved(c, min(a, 1.0), px, py, size, rot):
            if kind == "rect":
                fill_rrect(c, -9, -5, 18, 10, 2, col)
            elif kind == "dot":
                c.arc(0, 0, 6, 0, 2 * math.pi); rgba(c, col); c.fill()
            else:
                icon(c, kind, 34)


# ------------------------------------------------------------------ Strichfigur mit Gesicht
def figure(c, x, gy, col, walk=0.0, moving=False, pay=0.0, lean=0.0, held=None, held_n=1, nod=0.0, face="smile"):
    lw = 11
    c.set_line_width(lw)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    bob = abs(math.sin(walk)) * 5 if moving else 0
    hip = (x, gy - 66 - bob)
    sh = (x + lean * 30, gy - 122 - bob)
    head = (x + lean * 42 + nod * 3, gy - 160 - bob)
    rgba(c, col)
    for ph in (0, math.pi):
        aa = 0.48 * math.sin(walk + ph) if moving else (0.18 if ph else -0.18)
        knee = (hip[0] + math.sin(aa) * 34, hip[1] + math.cos(aa) * 34)
        foot = (knee[0] + math.sin(aa * 0.6) * 34 + (6 if moving else 0), gy)
        c.move_to(*hip); c.line_to(*knee); c.line_to(*foot); c.stroke()
    c.move_to(*hip); c.line_to(*sh); c.stroke()
    ab = -0.4 * math.sin(walk) if moving else 0.25
    el = (sh[0] - math.sin(ab) * 30 - 4, sh[1] + math.cos(ab) * 30)
    c.move_to(*sh); c.line_to(*el); c.line_to(el[0] + 4, el[1] + 28); c.stroke()
    ep = ease(pay)
    elb = (sh[0] + 14 + 18 * ep, sh[1] + 30 - 22 * ep)
    ang = lerp(1.35, -0.25, ep)
    hand = (elb[0] + 30 * math.cos(ang), elb[1] + 30 * math.sin(ang))
    c.move_to(*sh); c.line_to(*elb); c.line_to(*hand); c.stroke()
    # Kopf mit Gesicht (Blick nach rechts)
    hx, hy = head
    c.arc(hx, hy, 27, 0, 2 * math.pi)
    rgba(c, col); c.fill()
    rgba(c, INK)
    c.set_line_width(3.4)
    if face == "wince":
        for ex in (4, 16):
            c.move_to(hx + ex - 4, hy - 9); c.line_to(hx + ex + 3, hy - 5); c.line_to(hx + ex - 4, hy - 1)
        c.stroke()
        c.move_to(hx + 2, hy + 11)
        for k in range(4):
            c.line_to(hx + 5 + k * 4, hy + (7 if k % 2 == 0 else 12))
        c.stroke()
    else:
        for ex in (6, 17):
            c.arc(hx + ex, hy - 5, 3.6 if face != "shock" else 4.6, 0, 2 * math.pi); c.fill()
        if face == "shock":
            c.arc(hx + 12, hy + 10, 6, 0, 2 * math.pi); c.fill()
        elif face == "neutral":
            c.move_to(hx + 6, hy + 10); c.line_to(hx + 19, hy + 10); c.stroke()
        else:
            big = face == "happy"
            c.arc(hx + 11, hy + (4 if big else 6), 9 if big else 7, 0.15 * math.pi, 0.85 * math.pi)
            if big:
                c.close_path(); c.fill()
            else:
                c.stroke()
    if held and pay > 0.05:
        if held == "bills" and held_n > 1:
            for k in range(held_n):
                with Saved(c, ep, hand[0] + 10 + k * 6, hand[1] - 14 - k * 4, 0.95, -0.25 + k * 0.18):
                    icon(c, "bills", 40)
        else:
            with Saved(c, ep, hand[0] + 12, hand[1] - 14, 1.0, -0.15):
                icon(c, held, 40)
    return head, hand


# ------------------------------------------------------------------ Hintergrund
_BG = None
GLOWS = [(200, 500, 700, PURPLE, 0.0), (900, 1300, 750, TEAL, 2.0), (500, 1800, 800, hexc("#2a4bd8"), 4.0)]


def background(c, t):
    global _BG
    if _BG is None:
        _BG = cairo.LinearGradient(0, 0, 0, H)
        _BG.add_color_stop_rgb(0, *BG1)
        _BG.add_color_stop_rgb(1, *BG2)
    c.set_source(_BG)
    c.paint()
    for cx0, cy0, r, col, ph in GLOWS:
        cx = cx0 + 90 * math.sin(t * 0.35 + ph)
        cy = cy0 + 70 * math.cos(t * 0.27 + ph)
        g = cairo.RadialGradient(cx, cy, 0, cx, cy, r)
        g.add_color_stop_rgba(0, col[0], col[1], col[2], 0.16)
        g.add_color_stop_rgba(1, col[0], col[1], col[2], 0.0)
        c.set_source(g)
        c.paint()
    rnd = random.Random(3)
    for i in range(22):
        x = rnd.uniform(0, W)
        sp = rnd.uniform(20, 45)
        y = H + 60 - ((t * sp + rnd.uniform(0, H)) % (H + 120))
        sz = rnd.uniform(26, 58)
        text(c, "€", x + 14 * math.sin(t * 0.8 + i), y, sz, WHITE, 0.045)


