"""Rendert bar-karte-handy-video.mp4 (1080x1920, 30 fps, 60 s) als flache 2D-Animation.

Dunkelblauer Hintergrund mit langsam wandernden Lichtern, drei Bahnen mit
Strichfiguren (BAR gelb, KARTE rot, HANDY türkis) mit Gesichtern, dauerhafte
Anzeige oben (Tag-Uhr + drei Zähler mit "MEISTE AUSGABEN"-Marke), Kapitel-Banner,
Glow, Kamera-Wackler, Konfetti, Wort-für-Wort-Untertitel. Zeichnen mit Cairo.

  python3 render.py                 # komplettes Video
  python3 render.py still 1 17 33   # Standbilder -> build/bezahlen/stills/
"""
import math
import os
import random
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

import cairo

from timeline import (ATM_T, BUILD, DURATION, EVENTS, FIGS, PUSH_FROM, WORDS, at, current_day, is_moving,
                      scene_t, walked)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / os.environ.get("VIDEO_OUT", "bar-karte-handy-video.mp4")
W, H, FPS = 1080, 1920, 30
NFRAMES = int(DURATION * FPS)


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
COL = {"bar": YEL, "karte": RED, "handy": TEAL}
NAME = {"bar": "BAR", "karte": "KARTE", "handy": "HANDY"}
PAYICON = {"bar": "bills", "karte": "card", "handy": "phone"}

BLACK_F = "Inter Display Black"
XB_F = "Inter Display ExtraBold"

# ------------------------------------------------------------------ Layout
CLOCK_Y = 170
BOX_Y, BOX_H, BOX_W, BOX_GAP = 300, 176, 316, 26
BOX_X0 = (W - 3 * BOX_W - 2 * BOX_GAP) / 2
LANE_Y0, LANE_H, LANE_GAP = 528, 286, 16
LANE_X0, LANE_X1 = 30, 1050
FIG_X = 232
GRID_X0, GRID_DX, GRID_COLS = 470, 44, 13
SUB_Y = 1545
STAGE_TOP, STAGE_BOT = LANE_Y0, LANE_Y0 + 3 * LANE_H + 2 * LANE_GAP

T_END0 = scene_t("endstand")[0]
T_PAIN0 = scene_t("schmerz")[0]
T_OUTRO0 = scene_t("ende")[0]


def lane_y(f):
    return LANE_Y0 + FIGS.index(f) * (LANE_H + LANE_GAP)


def ground_y(f):
    return lane_y(f) + 246


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


# ------------------------------------------------------------------ Kamera-Wackler
SHAKES = [
    (at("falsch", "Noch") - 0.05, 16, 0.35),
    (at("endstand", "meisten") - 0.1, 14, 0.35),
    (0.0, 10, 0.3),
]


def shake(t):
    dx = dy = 0.0
    for t0, amp, dur in SHAKES:
        d = t - t0
        if 0 <= d < dur:
            k = amp * (1 - d / dur)
            dx += k * math.sin(d * 75)
            dy += k * 0.7 * math.cos(d * 63)
    return dx, dy


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


# ------------------------------------------------------------------ Zähler
def counter_value(f, t):
    v = 0.0
    for e in EVENTS:
        if e["fig"] != f or e["t"] > t:
            continue
        v += e["amount"] * ease((t - e["t"]) / 0.3)
    return v


def last_pay(f, t, window=0.35):
    best = None
    for e in EVENTS:
        if e["fig"] == f and e["amount"] > 0 and e["t"] <= t < e["t"] + window:
            best = e
    return best


def hud(c, t):
    day = current_day(t)
    flash = 0.5 + 0.5 * math.sin((t - 43.6) * 9) if 43.6 <= t < 45 else 0.0
    pw = 380
    shadow_rrect(c, W / 2 - pw / 2, CLOCK_Y - 62, pw, 124, 62)
    fill_rrect(c, W / 2 - pw / 2, CLOCK_Y - 62, pw, 124, 62, mix(PANEL, ORANGE, flash * 0.6))
    glow_rrect(c, W / 2 - pw / 2, CLOCK_Y - 62, pw, 124, 62, ORANGE if is_moving(t) else WHITE,
               0.8 if is_moving(t) else 0.2, 3)
    cx, cy = W / 2 - pw / 2 + 64, CLOCK_Y
    c.arc(cx, cy, 36, 0, 2 * math.pi); rgba(c, WHITE); c.fill()
    frac = (day - 1) / 29
    c.move_to(cx, cy); c.arc(cx, cy, 30, -math.pi / 2, -math.pi / 2 + 2 * math.pi * max(frac, 0.001)); c.close_path()
    rgba(c, ORANGE); c.fill()
    hand_a = -math.pi / 2 + t * 4.0 * (1 if is_moving(t) else 0.08)
    c.set_line_width(5); c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.move_to(cx, cy); c.line_to(cx + 24 * math.cos(hand_a), cy + 24 * math.sin(hand_a)); rgba(c, INK); c.stroke()
    text(c, f"TAG {day}", W / 2 + 40, CLOCK_Y + 2, 74, WHITE)
    tw = 6
    x0 = W / 2 - (30 * (tw + 4)) / 2
    for d in range(1, 31):
        fill_rrect(c, x0 + (d - 1) * (tw + 4), CLOCK_Y + 74, tw, 14, 3, ORANGE if d <= day else PANEL2)

    vals = {f: counter_value(f, t) for f in FIGS}
    leader = max(FIGS, key=lambda f: vals[f])
    others = sorted(vals.values())[-2]
    for i, f in enumerate(FIGS):
        x = BOX_X0 + i * (BOX_W + BOX_GAP)
        e = last_pay(f, t)
        pulse = 1 - (t - e["t"]) / 0.35 if e else 0.0
        hl = 0.5 + 0.5 * math.sin(t * 8) if (16.6 <= t < 22.0 and f == "handy") else 0.0
        if t >= T_END0:
            hl = 0.5 + 0.5 * math.sin(t * 6) if f == "karte" else 0.0
        sc = 1 + 0.05 * pulse
        with Saved(c, 1.0, x + BOX_W / 2, BOX_Y + BOX_H / 2, sc):
            shadow_rrect(c, -BOX_W / 2, -BOX_H / 2, BOX_W, BOX_H, 28)
            fill_rrect(c, -BOX_W / 2, -BOX_H / 2, BOX_W, BOX_H, 28, mix(PANEL, COL[f], 0.2 * pulse + 0.14 * hl))
            glow_rrect(c, -BOX_W / 2, -BOX_H / 2, BOX_W, BOX_H, 28, COL[f], 0.5 + 0.5 * max(pulse, hl), 4)
            fill_rrect(c, -BOX_W / 2 + 14, -BOX_H / 2 + 14, BOX_W - 28, 44, 20, COL[f])
            w1 = text_w(c, NAME[f], 25)
            w2 = text_w(c, " · AUSGEGEBEN", 21, XB_F)
            lx = -(w1 + w2) / 2
            text(c, NAME[f], lx, -BOX_H / 2 + 36, 25, INK, align="l")
            text(c, " · AUSGEGEBEN", lx + w1, -BOX_H / 2 + 36, 21, INK, face=XB_F, align="l")
            text(c, euro(vals[f]), 0, 34, 78, WHITE, maxw=BOX_W - 30, glow=COL[f] if pulse > 0 else None)
        if f == leader and t > 8.6 and vals[f] - others >= 1:
            with Saved(c, 1.0, x + BOX_W / 2, BOX_Y + BOX_H + 2, 1.0 + 0.06 * math.sin(t * 6)):
                fill_rrect(c, -122, -17, 244, 34, 17, WHITE)
                text(c, "▲ MEISTE AUSGABEN", 0, 0, 19, RED)


# ------------------------------------------------------------------ Kapitel
CHAPTERS = [
    (3.1, 8.0, "DIE REGELN", WHITE),
    (8.0, 16.0, "WOCHE 1 · ALLE KAUFEN EIN", WHITE),
    (16.0, 22.0, "ZWISCHENSTAND", TEAL),
    (22.0, 30.0, "WOCHE 2 · HANDY MELDET JEDE ZAHLUNG", TEAL),
    (30.0, 38.0, "WOCHE 3 · BARGELD", YEL),
    (38.0, T_END0, "WOCHE 4 · KARTE", RED),
]


def chapter(c, t):
    for t0, t1, txt, col in CHAPTERS:
        a = win(t, t0, t1, 0.2, 0.15)
        if a <= 0:
            continue
        k = eback((t - t0) / 0.35)
        tw = text_w(c, txt, 24) + 60
        with Saved(c, a, W / 2, STAGE_TOP - 4, 0.6 + 0.4 * k):
            fill_rrect(c, -tw / 2, -21, tw, 42, 21, INK)
            glow_rrect(c, -tw / 2, -21, tw, 42, 21, col, 0.9, 3)
            c.arc(-tw / 2 + 24, 0, 6, 0, 2 * math.pi); rgba(c, col); c.fill()
            text(c, txt, 12, 0, 24, WHITE)
        d = t - t0
        if 0 <= d < 0.45 and t0 > 3.5:
            xx = -500 + d / 0.45 * 2100
            c.save()
            rrect(c, LANE_X0, STAGE_TOP, LANE_X1 - LANE_X0, STAGE_BOT - STAGE_TOP, 30)
            c.clip()
            c.move_to(xx, STAGE_TOP); c.line_to(xx + 180, STAGE_TOP); c.line_to(xx - 120, STAGE_BOT)
            c.line_to(xx - 300, STAGE_BOT); c.close_path()
            rgba(c, col, 0.13); c.fill()
            c.restore()


# ------------------------------------------------------------------ Bahnen
def focus(t):
    if 16.3 <= t < 30.0:
        return "handy"
    if 30.0 <= t < 38.0:
        return "bar"
    if 38.0 <= t < 43.8:
        return "karte"
    return None


def focus_alpha(f, t):
    fo = focus(t)
    if fo is None:
        return 1.0
    k = ease((t - 16.3) / 0.4) if fo == "handy" and t < 17 else 1.0
    return 1.0 if f == fo else lerp(1.0, 0.4, k)


def lane_label(c, f, t, txt, t0, t1, icon_kind=None, col=None):
    a = win(t, t0, t1, 0.3, 0.3)
    if a <= 0:
        return
    col = col or COL[f]
    y = lane_y(f)
    tw = text_w(c, txt, 26) + (46 if icon_kind else 0)
    x = (GRID_X0 + LANE_X1) / 2 - 20 - tw / 2
    with Saved(c, a, 0, (1 - eback((t - t0) / 0.35)) * -14):
        fill_rrect(c, x, y + 14, tw + 36, 48, 24, col)
        tx = x + 18
        if icon_kind:
            with Saved(c, 1.0, tx + 16, y + 38):
                icon(c, icon_kind, 30, col=INK)
            tx += 46
        text(c, txt, tx, y + 38, 26, INK, align="l")


def slot_pos(f, slot):
    col, row = slot % GRID_COLS, slot // GRID_COLS
    return GRID_X0 + col * GRID_DX, lane_y(f) + 92 + row * 44


def fly_end(e):
    return 0.55 if e["pay"] == "coin" else 0.8


def draw_lane(c, f, t):
    y = lane_y(f)
    gy = ground_y(f)
    colr = COL[f]
    fo = focus(t) == f
    shadow_rrect(c, LANE_X0, y, LANE_X1 - LANE_X0, LANE_H, 30, 0.35)
    g = cairo.LinearGradient(0, y, 0, y + LANE_H)
    g.add_color_stop_rgb(0, *mix(LANE, colr, 0.07))
    g.add_color_stop_rgb(1, *LANE)
    rrect(c, LANE_X0, y, LANE_X1 - LANE_X0, LANE_H, 30)
    c.set_source(g)
    c.fill()
    if fo:
        glow_rrect(c, LANE_X0, y, LANE_X1 - LANE_X0, LANE_H, 30, colr, 0.9, 4)
    else:
        rrect(c, LANE_X0, y, LANE_X1 - LANE_X0, LANE_H, 30)
        rgba(c, colr, 0.35); c.set_line_width(3); c.stroke()
    fill_rrect(c, LANE_X0, y + 30, 10, LANE_H - 60, 5, colr)
    fill_rrect(c, LANE_X0 + 26, y + 16, 150, 48, 24, colr)
    with Saved(c, 1.0, LANE_X0 + 56, y + 40, 0.72):
        icon(c, PAYICON[f], 44)
    text(c, NAME[f], LANE_X0 + 84, y + 40, 28, INK, align="l", maxw=88)
    off = walked(t) % 60
    c.set_line_width(4)
    rgba(c, colr, 0.35)
    c.move_to(LANE_X0 + 30, gy + 2); c.line_to(LANE_X1 - 30, gy + 2); c.stroke()
    rgba(c, colr, 0.6)
    xx = LANE_X0 + 40 - off
    while xx < LANE_X1 - 40:
        if xx > LANE_X0 + 30:
            c.move_to(xx, gy + 14); c.line_to(min(xx + 24, LANE_X1 - 40), gy + 14)
        xx += 60
    c.stroke()
    sa = win(t, 3.2, 8.4, 0.3, 0.4)
    if sa > 0:
        for k in range(8):
            for j in range(2):
                if (k + j) % 2 == 0:
                    c.rectangle(FIG_X + 74 + j * 12, gy - 96 + k * 12, 12, 12)
        rgba(c, WHITE, sa * 0.9); c.fill()
        text(c, "START", FIG_X + 86, gy - 116, 22, WHITE, sa)
    done = [e for e in EVENTS if e["fig"] == f and e["extra"] and t >= e["t"] + fly_end(e)]
    for e in done:
        px, py = slot_pos(f, e["slot"])
        with Saved(c, 1.0, px, py):
            icon(c, e["kind"], 36)
    s = sum(e["amount"] for e in done)
    text(c, f"SPONTANKÄUFE: {len(done)}  ·  {euro(s, True)}", LANE_X1 - 34, y + LANE_H - 18, 22, colr, 0.95,
         face=XB_F, align="r")


def gesture(f, t):
    for e in EVENTS:
        if e["fig"] != f or e["skip"]:
            continue
        d = t - (e["t"] - 0.12)
        dur = e["paydur"]
        if 0 <= d <= dur + 0.15:
            k = min(d / 0.12, 1.0, (dur + 0.15 - d) / 0.15)
            n = 1 + min(2, int(d / 0.25)) if (e["pay"] == "bills" and dur > 0.5) else 1
            return k, e["pay"], n, e
    return 0.0, None, 1, None


def draw_figure_lane(c, f, t):
    gy = ground_y(f)
    moving = is_moving(t) and t < 43.6
    walk = walked(t) / 150 * 7.0
    pay, held, n, ev = gesture(f, t)
    lean, nod, face = 0.0, 0.0, "smile"
    if ev is not None and ev["extra"]:
        face = "happy"
    if f == "handy":
        for e in EVENTS:
            if e["fig"] == "handy" and e["push"] and 0.15 < t - e["t"] < 0.85:
                lean = -0.35 * math.sin((t - e["t"] - 0.15) / 0.7 * math.pi)
                face = "wince"
    for e in EVENTS:
        if e["fig"] == f and e["skip"] and 0 < t - e["t"] < 0.8:
            nod = math.sin((t - e["t"]) * 30) * (1 - (t - e["t"]) / 0.8)
            face = "neutral"
    if 16.3 <= t < 22 and f == "handy" and t > at("falsch", "Noch") - 0.1:
        face = "shock"
    if moving and pay > 0.3:
        moving = False
    head, hand = figure(c, FIG_X, gy, COL[f], walk, moving, pay, lean, held, n, nod, face)

    if face == "wince":
        text(c, "autsch!", head[0] - 50, head[1] - 48, 30, ORANGE, 1.0, outline=8)
    if ev is not None and ev["pay"] == "bills" and ev["paydur"] > 0.5:
        k = cl((t - ev["t"]) / 0.6)
        dots = "." * (1 + int(k * 2.9))
        fill_rrect(c, head[0] - 112, head[1] - 22, 70, 42, 20, WHITE, 0.92 * pay)
        text(c, dots, head[0] - 77, head[1] - 6, 34, INK, pay)

    if f == "bar":
        a = win(t, ATM_T[0] - 0.1, ATM_T[1] + 0.5, 0.25, 0.35)
        if a > 0:
            ax, ay = FIG_X + 150, gy - 170
            with Saved(c, a, ax, ay, 0.9 + 0.1 * eback((t - ATM_T[0]) / 0.3)):
                fill_rrect(c, -60, 0, 120, 170, 14, hexc("#3d5aa8"))
                glow_rrect(c, -60, 0, 120, 170, 14, YEL, 0.7, 3)
                fill_rrect(c, -44, 16, 88, 56, 8, hexc("#9fd3ff"))
                text(c, "ATM", 0, 44, 26, INK)
                fill_rrect(c, -40, 90, 80, 10, 5, INK)
                k = cl((t - ATM_T[0] - 0.3) / 0.6)
                for j in range(3):
                    with Saved(c, 1.0, -10 - 70 * k + j * 8, 100 + 18 * k + j * 5, 0.9, -0.4 * k):
                        icon(c, "bills", 40)
                text(c, "GELD ABHEBEN", 0, 194, 20, WHITE, face=XB_F)
        burst(c, t, ATM_T[0] + 0.9, FIG_X - 20, gy - 70, n=14, seed=5, kinds=("coin",), speed=420, life=0.9,
              grav=1600, size=0.8)
        if ATM_T[0] + 0.7 < t < 44:
            for j in range(3):
                jig = math.sin(t * 13 + j * 2.1) * 4 if is_moving(t) else 0
                with Saved(c, min(1, (t - ATM_T[0] - 0.7) / 0.3), FIG_X - 40 + j * 13, gy - 66 + jig - j * 6, 0.62):
                    icon(c, "coin", 44)
            if 31.2 < t < 38 and int(t * 2.2) % 3 == 0:
                text(c, "kling!", FIG_X - 74, gy - 110, 24, YEL, 0.9, face=XB_F, outline=6)

    for e in EVENTS:
        if e["fig"] != f:
            continue
        d = t - e["t"]
        if d < 0 or d > 1.3:
            continue
        hx, hy = FIG_X + 56, lane_y(f) + 50
        if e["skip"]:
            a = win(d, 0, 0.95, 0.12, 0.3)
            with Saved(c, a, hx + math.sin(d * 28) * 5 * (1 - d), hy, eback(d / 0.2)):
                skip_icon(c, e["kind"], 50, 1.0)
            continue
        if e["extra"]:
            fe = fly_end(e)
            if d >= fe:
                continue
            hold = fe * 0.45
            if d < hold:
                with Saved(c, 1.0, hx, hy - 6 * d, eback(d / 0.18) * 1.2):
                    icon(c, e["kind"], 44)
                text(c, "+" + euro(e["amount"], True), hx + 34, hy - 6 * d, 26, WHITE, 1.0, face=XB_F, align="l",
                     outline=7)
            else:
                k = ease((d - hold) / (fe - hold))
                tx, ty = slot_pos(f, e["slot"])
                px = lerp(hx, tx, k)
                py = lerp(hy, ty, k) - math.sin(k * math.pi) * 60
                with Saved(c, 1.0, px, py, lerp(1.2, 0.82, k)):
                    icon(c, e["kind"], 44)
        else:
            a = win(d, 0, 1.1, 0.1, 0.35)
            with Saved(c, a, hx, hy - 10 * d, eback(d / 0.2)):
                icon(c, "einkauf", 46)
            text(c, "+" + euro(e["amount"], True), hx + 34, hy - 10 * d, 26, WHITE, a, face=XB_F, align="l",
                 outline=7)
            text(c, "WOCHENEINKAUF", hx + 34, hy - 10 * d + 28, 16, MUTED, a, face=XB_F, align="l")


def push_banners(c, t):
    y = lane_y("handy")
    shown = [e for e in EVENTS if e["push"] and 0 <= t - e["t"] < 1.15]
    for e in shown[-1:]:
        d = t - e["t"]
        a = win(d, 0, 1.15, 0.12, 0.25)
        x0, w, h = 520, 500, 92
        yy = y + 74 + (1 - eout(d / 0.18)) * -40
        with Saved(c, a):
            shadow_rrect(c, x0, yy, w, h, 22)
            fill_rrect(c, x0, yy, w, h, 22, WHITE)
            fill_rrect(c, x0 + 16, yy + 16, 60, 60, 16, TEAL)
            text(c, "€", x0 + 46, yy + 46, 34, INK)
            text(c, "ZAHLUNG", x0 + 92, yy + 30, 22, hexc("#5a6a8f"), face=XB_F, align="l")
            text(c, "–" + euro(e["amount"], True), x0 + 92, yy + 62, 38, RED, align="l")
            with Saved(c, 1.0, x0 + w - 42, yy + 46, 1 + 0.2 * math.sin(d * 30) * (1 - cl(d / 0.5))):
                icon(c, "bell", 38, col=ORANGE)


def stage(c, t):
    for f in FIGS:
        with Saved(c, focus_alpha(f, t)):
            draw_lane(c, f, t)
            draw_figure_lane(c, f, t)
    push_banners(c, t)
    lane_label(c, "karte", t, "SPONTANKÄUFE LANDEN HIER  ↓", 9.0, 14.8, col=WHITE)
    lane_label(c, "handy", t, "HANDY MELDET JEDE ZAHLUNG", PUSH_FROM + 0.1, 30.0, "bell")
    lane_label(c, "bar", t, "KLEINGELD FÜHLT SICH WIE SPIELGELD AN", 31.0, 38.0)
    lane_label(c, "karte", t, "KEINE NACHRICHT · KEIN GEFÜHL", 38.4, 43.9)


# ------------------------------------------------------------------ Szenen-Überlagerungen
def dim_stage(c, a):
    if a > 0:
        fill_rrect(c, LANE_X0 - 10, STAGE_TOP - 10, LANE_X1 - LANE_X0 + 20, STAGE_BOT - STAGE_TOP + 20, 34, BG2, a)


def hook(c, t):
    """0–3 s: 'GLEICHER EINKAUF – EINER ZAHLT +39 € – WER ZAHLT MEHR?'"""
    a = win(t, -1, 3.35, 0, 0.3)
    if a <= 0:
        return
    dim_stage(c, 0.82 * a)
    out = ease((t - 3.0) / 0.35)
    with Saved(c, a, W / 2, 970, 1.0 + 0.18 * out):
        shadow_rrect(c, -490, -420, 980, 840, 46)
        fill_rrect(c, -490, -420, 980, 840, 46, PANEL)
        glow_rrect(c, -490, -420, 980, 840, 46, WHITE, 0.25, 3)
        text(c, "GLEICHER EINKAUF", 0, -350, 62, WHITE)
        for i, f in enumerate(FIGS):
            x = -300 + i * 300
            k = eback((t - 0.05 - i * 0.12) / 0.3)
            with Saved(c, cl(k * 2), x, -40, 1.05 * (0.7 + 0.3 * k)):
                figure(c, 0, 0, COL[f], walk=t * 3, face="neutral")
                bob = math.sin(t * 6 + i) * 6
                text(c, "?", 50, -230 + bob, 64, WHITE, 1.0, glow=COL[f])
                fill_rrect(c, -80, 22, 160, 50, 25, COL[f])
                text(c, NAME[f], 0, 47, 28, INK)
        p = 1 + 0.04 * math.sin(t * 9)
        k = eback(t / 0.25, 2.2)
        with Saved(c, 1.0, 0, 150, p * (0.6 + 0.4 * k)):
            text(c, "EINER ZAHLT", 0, -70, 40, MUTED, face=XB_F)
            text(c, "+39 €", 0, 30, 150, RED, glow=RED)
        with Saved(c, 1.0, 0, 330, 1.0):
            fill_rrect(c, -260, -54, 520, 108, 54, WHITE)
            text(c, "WER ZAHLT MEHR?", 0, 0, 52, INK)


def sign(c, t, t0, t1, cy, kind, txt1, txt2=None):
    a = win(t, t0, t1, 0.25, 0.3)
    if a <= 0:
        return
    k = eback((t - t0) / 0.4)
    with Saved(c, a, 750 + (1 - k) * 300, cy, 1.0, -0.025 if kind == "list" else 0.025):
        shadow_rrect(c, -270, -100, 540, 200, 30)
        fill_rrect(c, -270, -100, 540, 200, 30, WHITE)
        with Saved(c, 1.0, -190, 0, 2.2):
            icon(c, kind, 44)
        text(c, txt1, 50, -24 if txt2 else 0, 50 if txt2 else 84, INK, maxw=300)
        if txt2:
            text(c, txt2, 50, 34, 50, INK, maxw=300)


def lane_intro(c, t):
    """3–8 s: wer zahlt wie, dann die gleichen Regeln."""
    texts = {"bar": ("zahlt alles ", "BAR"), "karte": ("zahlt alles mit ", "KARTE"),
             "handy": ("zahlt alles mit ", "HANDY")}
    for i, f in enumerate(FIGS):
        t0 = 3.35 + i * 0.3
        a = win(t, t0, 5.6, 0.25, 0.25)
        if a <= 0:
            continue
        k = eback((t - t0) / 0.35)
        y = lane_y(f) + 140
        pre, key = texts[f]
        w1 = text_w(c, pre, 40, XB_F)
        w2 = text_w(c, key, 58)
        x = 750 - (w1 + w2) / 2 + (1 - k) * 200
        with Saved(c, a):
            text(c, pre, x, y, 40, WHITE, face=XB_F, align="l")
            text(c, key, x + w1, y, 58, COL[f], align="l", glow=COL[f])
    sign(c, t, 5.5, 7.85, lane_y("bar") + 140, "list", "GLEICHER", "EINKAUFSZETTEL")
    sign(c, t, 5.75, 7.85, lane_y("karte") + 140, "calendar", "30 TAGE")
    sign(c, t, 6.0, 7.85, lane_y("handy") + 140, "coin", "GLEICHES", "BUDGET")


def falsch(c, t):
    t0 = at("falsch", "Ist") - 0.05
    t_noch = at("falsch", "Noch") - 0.05
    a = win(t, t0, 21.85, 0.25, 0.3)
    if a <= 0:
        return
    k = eback((t - t0) / 0.35)
    with Saved(c, a, W / 2, 735, 0.7 + 0.3 * k):
        shadow_rrect(c, -480, -125, 960, 250, 40)
        fill_rrect(c, -480, -125, 960, 250, 40, PANEL2)
        glow_rrect(c, -480, -125, 960, 250, 40, TEAL, 1.0, 5)
        text(c, "HANDY =", 0, -52, 72, TEAL, glow=TEAL)
        text(c, "GRÖSSTE GELDFALLE?", 0, 46, 74, WHITE, maxw=900)
    if t > t0 + 0.3:
        ax = BOX_X0 + 2 * (BOX_W + BOX_GAP) + BOX_W / 2
        bob = math.sin(t * 7) * 8
        with Saved(c, a, ax, 540 + bob):
            c.move_to(-26, 30); c.line_to(0, -6); c.line_to(26, 30); c.close_path(); rgba(c, TEAL); c.fill()
    b = win(t, t_noch, 21.85, 0.12, 0.3)
    if b > 0:
        k2 = eback((t - t_noch) / 0.25, 2.5)
        with Saved(c, b, W / 2, 1010, 1.7 - 0.7 * k2, -0.06):
            shadow_rrect(c, -400, -95, 800, 190, 34)
            fill_rrect(c, -400, -95, 800, 190, 34, ORANGE)
            glow_rrect(c, -400, -95, 800, 190, 34, ORANGE, 1.0, 2)
            text(c, "NOCH NICHT.", 0, 2, 108, INK, maxw=740)
    burst(c, t, t_noch + 0.1, W / 2, 1010, n=26, seed=11, kinds=("dot", "rect"), cols=(ORANGE, WHITE, YEL),
          speed=700, life=1.0)


def panel_frame(c, t, t0, t1):
    a = win(t, t0, t1, 0.3, 0.3)
    if a <= 0:
        return 0.0, 0.0
    k = eout((t - t0) / 0.4)
    dim_stage(c, 0.88 * a)
    dy = (1 - k) * 80
    with Saved(c, a, 0, dy):
        shadow_rrect(c, LANE_X0, STAGE_TOP, LANE_X1 - LANE_X0, STAGE_BOT - STAGE_TOP, 40)
        g = cairo.LinearGradient(0, STAGE_TOP, 0, STAGE_BOT)
        g.add_color_stop_rgb(0, *PANEL2)
        g.add_color_stop_rgb(1, *PANEL)
        rrect(c, LANE_X0, STAGE_TOP, LANE_X1 - LANE_X0, STAGE_BOT - STAGE_TOP, 40)
        c.set_source(g)
        c.fill()
        glow_rrect(c, LANE_X0, STAGE_TOP, LANE_X1 - LANE_X0, STAGE_BOT - STAGE_TOP, 40, WHITE, 0.25, 3)
    return a, dy


def ergebnis(c, t):
    a, dy = panel_frame(c, t, T_END0 - 0.05, T_PAIN0 + 0.1)
    if a <= 0:
        return
    with Saved(c, a, 0, dy):
        text(c, "ERGEBNIS NACH 30 TAGEN", W / 2, STAGE_TOP + 70, 56, WHITE, maxw=940)
        text(c, "Wer hat am meisten Geld ausgegeben?", W / 2, STAGE_TOP + 130, 32, MUTED, face=XB_F)
        rows = [("karte", 668, "MEISTE AUSGABEN", RED), ("handy", 641, None, None),
                ("bar", 629, "AM SPARSAMSTEN", GREEN)]
        t_first = at("endstand", "Mit") - 0.1
        for i, (f, v, tag, tcol) in enumerate(rows):
            tr = t_first + i * 0.45
            if t < tr:
                continue
            k = eback((t - tr) / 0.35)
            yy = STAGE_TOP + 250 + i * 135
            with Saved(c, cl(k * 2), (1 - k) * -120, 0):
                fill_rrect(c, 70, yy - 50, 940, 100, 30, mix(PANEL, COL[f], 0.12))
                if i == 0:
                    glow_rrect(c, 70, yy - 50, 940, 100, 30, RED, 0.6 + 0.4 * math.sin(t * 6), 4)
                fill_rrect(c, 96, yy - 30, 210, 60, 30, COL[f])
                with Saved(c, 1.0, 132, yy, 0.8):
                    icon(c, PAYICON[f], 44)
                text(c, NAME[f], 222, yy, 32, INK, maxw=120)
                bw = 380 * v / 668 * ease((t - tr) / 0.6)
                fill_rrect(c, 326, yy - 15, max(bw, 8), 30, 15, COL[f], 0.85)
                text(c, f"{v} €", 990, yy, 62, WHITE, align="r")
                if tag:
                    tw = text_w(c, tag, 20) + 30
                    fill_rrect(c, 1000 - tw, yy - 66, tw, 32, 16, tcol)
                    text(c, tag, 1000 - tw / 2, yy - 50, 20, INK if tcol == GREEN else WHITE)
        tb = at("endstand", "meisten") - 0.15
        b = win(t, tb, 99, 0.15, 0)
        if b > 0:
            k = eback((t - tb) / 0.3, 2.2)
            with Saved(c, b, W / 2, STAGE_TOP + 650, 1.4 - 0.4 * k, -0.02):
                fill_rrect(c, -470, -74, 940, 148, 36, RED)
                glow_rrect(c, -470, -74, 940, 148, 36, RED, 1.0, 2)
                text(c, "MIT KARTE GIBST DU", 0, -26, 50, WHITE, maxw=880)
                text(c, "AM MEISTEN AUS", 0, 32, 60, WHITE, maxw=880)
        burst(c, t, tb + 0.05, W / 2, STAGE_TOP + 650, n=34, seed=21, kinds=("bills", "coin", "card"), speed=950,
              life=1.4, size=0.9)
        ty = at("endstand", "Aufs") - 0.1
        d = win(t, ty, 99, 0.25, 0)
        if d > 0:
            k = eback((t - ty) / 0.3)
            cnt = 39 + (468 - 39) * ease((t - ty - 0.5) / 0.9)
            with Saved(c, d, W / 2, STAGE_TOP + 820, 0.8 + 0.2 * k):
                fill_rrect(c, -470, -58, 940, 116, 30, WHITE)
                text(c, "+39 € IM MONAT", -250, -22, 30, INK, face=XB_F)
                text(c, "mehr als mit Bargeld", -250, 18, 24, hexc("#5a6a8f"), face=XB_F)
                text(c, "→", -50, 0, 60, INK)
                text(c, f"+{int(cnt)} €", 175, -6, 74, RED)
                text(c, "IM JAHR", 395, 4, 28, INK, face=XB_F)


def schmerz(c, t):
    a, dy = panel_frame(c, t, T_PAIN0 - 0.05, T_OUTRO0 + 0.1)
    if a <= 0:
        return
    with Saved(c, a, 0, dy):
        text(c, "WIE SEHR SPÜRST DU DIE ZAHLUNG?", W / 2, STAGE_TOP + 70, 48, WHITE, maxw=950)
        text(c, "Forscher nennen das „Bezahlschmerz“", W / 2, STAGE_TOP + 126, 30, MUTED, face=XB_F)
        cols = [("bar", 0.92, "STARK", "man sieht das", "Geld gehen"),
                ("handy", 0.56, "MITTEL", "Push-", "Nachricht"),
                ("karte", 0.16, "KAUM", "man sieht", "nichts")]
        base = STAGE_TOP + 470
        for i, (f, v, lab, c1, c2) in enumerate(cols):
            tr = T_PAIN0 + 0.3 + i * 0.4
            if t < tr:
                continue
            x = 240 + i * 300
            k = eout((t - tr) / 0.6)
            hgt = 270 * v * k
            fill_rrect(c, x - 85, base - 270, 170, 270, 24, PANEL)
            fill_rrect(c, x - 85, base - max(hgt, 24), 170, max(hgt, 24), 24, COL[f])
            text(c, lab, x, base - max(hgt, 24) - 32, 38, COL[f], cl(k * 2), glow=COL[f])
            with Saved(c, cl(k * 2), x, base - 36, 1.3):
                icon(c, PAYICON[f], 44)
            fill_rrect(c, x - 90, base + 18, 180, 50, 25, COL[f])
            text(c, NAME[f], x, base + 43, 28, INK)
            text(c, c1, x, base + 96, 26, WHITE, cl(k * 2), face=XB_F)
            text(c, c2, x, base + 128, 26, WHITE, cl(k * 2), face=XB_F)
        ts = at("schmerz", "wenn") - 0.2
        b = win(t, ts, 99, 0.3, 0)
        if b > 0:
            k = eback((t - ts) / 0.35)
            with Saved(c, b, W / 2, STAGE_TOP + 705, 0.85 + 0.15 * k):
                fill_rrect(c, -480, -70, 960, 140, 34, WHITE)
                text(c, "JE WENIGER DU ES SPÜRST,", 0, -26, 44, INK, maxw=900)
                text(c, "DESTO MEHR GIBST DU AUS.", 0, 30, 50, ORANGE, maxw=900)
        tt = at("schmerz", "Tipp") - 0.1
        d = win(t, tt, 99, 0.2, 0)
        if d > 0:
            k = eback((t - tt) / 0.3, 2.2)
            with Saved(c, d, W / 2, STAGE_TOP + 845, 0.7 + 0.3 * k):
                fill_rrect(c, -440, -42, 880, 84, 42, GREEN)
                glow_rrect(c, -440, -42, 880, 84, 42, GREEN, 0.8, 2)
                with Saved(c, 1.0, -395, 0, 1.0 + 0.15 * math.sin(t * 20) * (1 - cl((t - tt) / 0.8))):
                    icon(c, "bell", 40, col=INK)
                text(c, "TIPP: PUSH-NACHRICHT FÜR DEINE KARTE AN", 25, 0, 32, INK, maxw=760)


def outro(c, t):
    t0 = T_OUTRO0
    a, dy = panel_frame(c, t, t0 - 0.05, 61)
    if a <= 0:
        return
    t_click = at("ende", "abonnier") + 0.1
    with Saved(c, a, 0, dy):
        k1 = eback((t - t0) / 0.35)
        with Saved(c, cl(k1 * 2), W / 2, STAGE_TOP + 105, 0.8 + 0.2 * k1):
            text(c, "WIE ZAHLST DU?", 0, 0, 96, WHITE, maxw=960, glow=PURPLE)
        with Saved(c, cl(eback((t - t0 - 0.2) / 0.3) * 2), W / 2, STAGE_TOP + 205):
            with Saved(c, 1.0, -300, 0, 1.2):
                icon(c, "comment", 44, col=WHITE)
            text(c, "Schreib's in die Kommentare:", 30, 0, 38, MUTED, face=XB_F)
        for i, f in enumerate(FIGS):
            tr = t0 + 0.35 + i * 0.12
            if t < tr:
                continue
            k = eback((t - tr) / 0.3)
            x = 210 + i * 330
            with Saved(c, cl(k * 2), x, STAGE_TOP + 315, (0.6 + 0.4 * k) * (1 + 0.04 * math.sin(t * 5 + i))):
                fill_rrect(c, -145, -52, 290, 104, 52, COL[f])
                with Saved(c, 1.0, -88, 0, 1.0):
                    icon(c, PAYICON[f], 44)
                text(c, NAME[f], 22, 0, 42, INK, maxw=160)
        tb = t0 + 0.6
        if t >= tb:
            k = eback((t - tb) / 0.35)
            clicked = t >= t_click
            press = 1 - 0.08 * math.sin(cl((t - t_click) / 0.18) * math.pi) if clicked else 1.0
            with Saved(c, cl(k * 2), W / 2, STAGE_TOP + 520, (0.7 + 0.3 * k) * press):
                shadow_rrect(c, -330, -70, 660, 140, 70)
                if not clicked:
                    fill_rrect(c, -330, -70, 660, 140, 70, RED)
                    glow_rrect(c, -330, -70, 660, 140, 70, RED, 0.6 + 0.4 * math.sin(t * 10), 2)
                    text(c, "+ ABONNIEREN", 0, 0, 66, WHITE)
                else:
                    fill_rrect(c, -330, -70, 660, 140, 70, hexc("#e8edf8"))
                    text(c, "✓ ABONNIERT", -20, 0, 62, INK)
                    with Saved(c, 1.0, 250, 0, 1.2 + 0.2 * math.sin((t - t_click) * 25) * (1 - cl((t - t_click) / 0.8))):
                        icon(c, "bell", 44, col=RED)
            kc = ease((t - (t_click - 0.7)) / 0.6)
            cx = lerp(900, 640, kc)
            cy = lerp(STAGE_TOP + 760, STAGE_TOP + 540, kc)
            with Saved(c, cl((t - (t_click - 0.8)) / 0.2), cx, cy, 2.2 * (0.9 if 0 <= t - t_click < 0.15 else 1.0)):
                icon(c, "cursor", 44)
        burst(c, t, t_click + 0.05, W / 2, STAGE_TOP + 520, n=60, seed=31, speed=1000, life=1.8)
        kt = eback((t - t0 - 0.9) / 0.35)
        if t > t0 + 0.9:
            with Saved(c, cl(kt * 2), W / 2, STAGE_TOP + 700, 0.8 + 0.2 * kt):
                fill_rrect(c, -260, -42, 520, 84, 42, ORANGE)
                text(c, "TEIL 2 FOLGT", 0, 0, 44, INK)
        text(c, "BEISPIELRECHNUNG · RICHTUNG NACH STUDIEN ZUM ‚BEZAHLSCHMERZ'", W / 2, STAGE_BOT - 44, 22,
             MUTED, face=XB_F, maxw=960)


# ------------------------------------------------------------------ Untertitel
HL = {"bar": YEL, "bargeld": YEL, "kleingeld": YEL, "karte": RED, "handy": TEAL, "39": RED, "470": RED,
      "ergebnis": ORANGE, "tipp": GREEN, "kommentare": ORANGE, "abonnier": RED, "geldfalle": TEAL}


def _key(s):
    return "".join(ch for ch in s.lower() if ch.isalnum())


def word_color(w):
    k = _key(w["show"])
    if w["scene"] == "falsch" and k in ("noch", "nicht"):
        return ORANGE
    return HL.get(k, WHITE)


def build_chunks():
    chunks, cur = [], []
    for w in WORDS:
        if cur and cur[-1]["scene"] != w["scene"]:
            chunks.append(cur)
            cur = []
        cur.append(w)
        if w["show"][-1] in ".,?!:–" or len(cur) >= 4:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


CHUNKS = build_chunks()
SUB_SIZE = 68


def subtitles(c, t):
    for i, ch in enumerate(CHUNKS):
        t0 = ch[0]["start"] - 0.05
        nxt = CHUNKS[i + 1][0]["start"] - 0.05 if i + 1 < len(CHUNKS) else 99
        t1 = min(nxt, ch[-1]["end"] + 0.7)
        if not (t0 <= t < t1):
            continue
        words = [w["show"] for w in ch]
        sp = SUB_SIZE * 0.42
        widths = [text_w(c, s, SUB_SIZE) for s in words]
        lines, line, lw = [], [], 0
        for j, wd in enumerate(widths):
            if line and lw + sp + wd > 940:
                lines.append((line, lw))
                line, lw = [], 0
            lw = lw + (sp if line else 0) + wd
            line.append(j)
        lines.append((line, lw))
        for li, (idxs, lwid) in enumerate(lines):
            y = SUB_Y + (li - (len(lines) - 1) / 2) * 86
            x = W / 2 - lwid / 2
            for j in idxs:
                w = ch[j]
                if t >= w["start"] - 0.04:
                    act = w["start"] - 0.04 <= t < (ch[j + 1]["start"] if j + 1 < len(ch) else w["end"] + 0.15)
                    k = eback((t - w["start"] + 0.04) / 0.16)
                    sc = (1.12 if act else 1.0) * (0.7 + 0.3 * k)
                    col = word_color(w)
                    with Saved(c, 1.0, x + widths[j] / 2, y, sc, -0.03 if act and col != WHITE else 0):
                        if act:
                            fill_rrect(c, -widths[j] / 2 - 12, -46, widths[j] + 24, 92, 18, col, 0.18)
                        text(c, words[j], 0, 0, SUB_SIZE, col, 1.0, outline=13, glow=col if col != WHITE else None)
                x += widths[j] + sp
        break


# ------------------------------------------------------------------ Frame
def frame(t):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(surf)
    background(c, t)
    dx, dy = shake(t)
    c.save()
    c.translate(dx, dy)
    stage(c, t)
    chapter(c, t)
    hook(c, t)
    lane_intro(c, t)
    falsch(c, t)
    ergebnis(c, t)
    schmerz(c, t)
    outro(c, t)
    hud(c, t)
    c.restore()
    subtitles(c, t)
    surf.flush()
    return surf


def frame_bytes(i):
    return bytes(frame(i / FPS).get_data())


def render():
    wav = BUILD / "mix.wav"
    if not wav.exists():
        subprocess.check_call([sys.executable, str(Path(__file__).with_name("audio.py"))])
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "192k",
           "-t", f"{DURATION}", "-movflags", "+faststart", str(OUT)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, b in enumerate(pool.imap(frame_bytes, range(NFRAMES), chunksize=8)):
            p.stdin.write(b)
            if i % 300 == 0:
                print(f"frame {i}/{NFRAMES}", flush=True)
    p.stdin.close()
    p.wait()
    print("->", OUT)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "still":
        d = BUILD / "stills"
        d.mkdir(parents=True, exist_ok=True)
        for s in sys.argv[2:]:
            frame(float(s)).write_to_png(str(d / f"t{float(s):05.1f}.png"))
            print(d / f"t{float(s):05.1f}.png")
    else:
        render()
