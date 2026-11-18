"""Rendert bar-karte-handy-video.mp4 (1080x1920, 30 fps, 60 s) als flache 2D-Animation.

Dunkelblauer Hintergrund, drei Bahnen mit Strichfiguren (BAR gelb, KARTE rot,
HANDY türkis), dauerhafte Anzeige oben (Tag-Uhr + drei Zähler), Wort-für-Wort-
Untertitel unten. Zeichnen mit Cairo (Kantenglättung), Ton aus audio.py.

  python3 render.py                 # komplettes Video
  python3 render.py still 1 17 33   # Standbilder -> build/bezahlen/stills/
"""
import math
import os
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

import cairo

from timeline import (ATM_T, BUILD, DURATION, EVENTS, FIGS, PUSH_FROM, WORDS, at, current_day, is_moving,
                      walked)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / os.environ.get("VIDEO_OUT", "bar-karte-handy-video.mp4")
W, H, FPS = 1080, 1920, 30
NFRAMES = int(DURATION * FPS)

# ------------------------------------------------------------------ Farben
def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


BG1, BG2 = hexc("#0f2350"), hexc("#081634")
PANEL = hexc("#16295a")
PANEL2 = hexc("#1d3470")
LANE = hexc("#11234d")
INK = hexc("#0a1530")
WHITE = (1, 1, 1)
MUTED = hexc("#8fa3cf")
YEL = hexc("#ffcf2e")
RED = hexc("#ff4f5a")
TEAL = hexc("#2fe0d0")
ORANGE = hexc("#ff8a1f")
GREEN = hexc("#7fdc8a")
COL = {"bar": YEL, "karte": RED, "handy": TEAL}
NAME = {"bar": "BAR", "karte": "KARTE", "handy": "HANDY"}

BLACK_F = "Inter Display Black"
XB_F = "Inter Display ExtraBold"

# ------------------------------------------------------------------ Layout
CLOCK_Y = 170
BOX_Y, BOX_H, BOX_W, BOX_GAP = 300, 176, 316, 26
BOX_X0 = (W - 3 * BOX_W - 2 * BOX_GAP) / 2
LANE_Y0, LANE_H, LANE_GAP = 512, 290, 18
LANE_X0, LANE_X1 = 30, 1050
FIG_X = 232
GRID_X0, GRID_DX, GRID_COLS = 470, 44, 13
SUB_Y = 1530
STAGE_TOP, STAGE_BOT = LANE_Y0, LANE_Y0 + 3 * LANE_H + 2 * LANE_GAP


def lane_y(f):
    return LANE_Y0 + FIGS.index(f) * (LANE_H + LANE_GAP)


def ground_y(f):
    return lane_y(f) + 248


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
    """Sichtbarkeit 0..1 für ein Element zwischen t0 und t1."""
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


def font(c, size, face=BLACK_F):
    c.select_font_face(face, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    c.set_font_size(size)


def text_w(c, s, size, face=BLACK_F):
    font(c, size, face)
    return c.text_extents(s).x_advance


def text(c, s, x, y, size, col, a=1.0, face=BLACK_F, align="c", maxw=None, outline=0, ocol=INK):
    """y = optische Mitte der Großbuchstaben."""
    if maxw:
        while size > 10 and text_w(c, s, size, face) > maxw:
            size -= 1
    font(c, size, face)
    adv = c.text_extents(s).x_advance
    x0 = {"c": x - adv / 2, "l": x, "r": x - adv}[align]
    base = y + 0.36 * size
    if outline:
        c.move_to(x0, base)
        c.text_path(s)
        rgba(c, ocol, a)
        c.set_line_width(outline)
        c.set_line_join(cairo.LINE_JOIN_ROUND)
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
    """with Saved(c, alpha, x, y, scale, rot): zeichnet Inhalt transformiert/transparent."""

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


# ------------------------------------------------------------------ Symbole (zentriert, Größe s)
def icon(c, kind, s=44, a=1.0, col=None):
    c.save()
    c.scale(s / 44, s / 44)
    lw = 3.2
    c.set_line_width(lw)
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
        for k, yy in enumerate((-9, 0, 9)):
            c.move_to(-9, yy); c.line_to(-6, yy + 3); c.line_to(-2, yy - 3); rgba(c, hexc("#2c8a4a"), a); c.stroke()
            c.move_to(2, yy); c.line_to(10, yy); rgba(c, hexc("#9aa8c8"), a); c.stroke()
    elif kind == "calendar":
        fill_rrect(c, -17, -15, 34, 32, 4, WHITE, a)
        fill_rrect(c, -17, -15, 34, 10, 4, RED, a)
        text(c, "30", 0, 6, 15, INK, a)
    c.restore()


def skip_icon(c, kind, s, a):
    icon(c, kind, s, a * 0.55)
    c.set_line_width(5)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    r = s * 0.42
    c.move_to(-r, -r); c.line_to(r, r); c.move_to(r, -r); c.line_to(-r, r)
    rgba(c, RED, a); c.stroke()


# ------------------------------------------------------------------ Strichfigur
def figure(c, x, gy, col, walk=0.0, moving=False, pay=0.0, lean=0.0, held=None, held_n=1, nod=0.0):
    """Einfache Strichfigur, Blick nach rechts. pay 0..1 hebt den rechten Arm."""
    lw = 10
    c.set_line_width(lw)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    bob = abs(math.sin(walk)) * 5 if moving else 0
    hip = (x, gy - 66 - bob)
    sh = (x + lean * 30, gy - 124 - bob)
    head = (x + lean * 40 + nod * 3, gy - 160 - bob)
    rgba(c, col)
    # Beine
    for ph in (0, math.pi):
        aa = 0.48 * math.sin(walk + ph) if moving else (0.18 if ph else -0.18)
        knee = (hip[0] + math.sin(aa) * 34, hip[1] + math.cos(aa) * 34)
        foot = (knee[0] + math.sin(aa * 0.6) * 34 + (6 if moving else 0), gy)
        c.move_to(*hip); c.line_to(*knee); c.line_to(*foot); c.stroke()
    # Körper
    c.move_to(*hip); c.line_to(*sh); c.stroke()
    # hinterer Arm
    ab = -0.4 * math.sin(walk) if moving else 0.25
    el = (sh[0] - math.sin(ab) * 30 - 4, sh[1] + math.cos(ab) * 30)
    c.move_to(*sh); c.line_to(*el); c.line_to(el[0] + 4, el[1] + 28); c.stroke()
    # vorderer Arm (bezahlt)
    idle = 0.4 * math.sin(walk) if moving else -0.15
    up = -1.25
    ang = lerp(idle, up, ease(pay))
    elb = (sh[0] + math.sin(-ang) * 0 + 14 + 18 * ease(pay), sh[1] + 30 - 22 * ease(pay))
    hand = (elb[0] + 30 * math.cos(lerp(1.35, -0.25, ease(pay))), elb[1] + 30 * math.sin(lerp(1.35, -0.25, ease(pay))))
    c.move_to(*sh); c.line_to(*elb); c.line_to(*hand); c.stroke()
    # Kopf
    c.arc(head[0], head[1], 23, 0, 2 * math.pi)
    rgba(c, col); c.fill()
    c.arc(head[0] + 9, head[1] - 3, 3.6, 0, 2 * math.pi)
    rgba(c, INK); c.fill()
    if held and pay > 0.05:
        if held == "bills" and held_n > 1:
            for k in range(held_n):
                with Saved(c, ease(pay), hand[0] + 10 + k * 6, hand[1] - 14 - k * 4, 0.95, -0.25 + k * 0.18):
                    icon(c, "bills", 40)
        else:
            with Saved(c, ease(pay), hand[0] + 12, hand[1] - 14, 1.0, -0.15):
                icon(c, held, 40)
    return head, hand


# ------------------------------------------------------------------ Szene: Hintergrund & Kopfzeile
_BG = None


def background(c):
    global _BG
    if _BG is None:
        _BG = cairo.LinearGradient(0, 0, 0, H)
        _BG.add_color_stop_rgb(0, *BG1)
        _BG.add_color_stop_rgb(1, *BG2)
    c.set_source(_BG)
    c.paint()
    # feines Punktraster
    rgba(c, WHITE, 0.035)
    for yy in range(40, H, 60):
        for xx in range(30, W, 60):
            c.rectangle(xx, yy, 3, 3)
    c.fill()


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
    # Tag-Uhr
    day = current_day(t)
    flash = 0.0
    if t >= 43.6:
        flash = 0.5 + 0.5 * math.sin((t - 43.6) * 9) if t < 45 else 0.0
    pw = 380
    fill_rrect(c, W / 2 - pw / 2, CLOCK_Y - 62, pw, 124, 62, mix(PANEL, ORANGE, flash * 0.6))
    rrect(c, W / 2 - pw / 2, CLOCK_Y - 62, pw, 124, 62)
    rgba(c, WHITE, 0.18); c.set_line_width(3); c.stroke()
    # Ziffernblatt
    cx, cy = W / 2 - pw / 2 + 64, CLOCK_Y
    c.arc(cx, cy, 36, 0, 2 * math.pi); rgba(c, WHITE); c.fill()
    frac = (day - 1) / 29
    c.move_to(cx, cy); c.arc(cx, cy, 30, -math.pi / 2, -math.pi / 2 + 2 * math.pi * max(frac, 0.001)); c.close_path()
    rgba(c, ORANGE); c.fill()
    hand_a = -math.pi / 2 + t * 4.0 * (1 if is_moving(t) else 0.08)
    c.set_line_width(5); c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.move_to(cx, cy); c.line_to(cx + 24 * math.cos(hand_a), cy + 24 * math.sin(hand_a)); rgba(c, INK); c.stroke()
    text(c, f"TAG {day}", W / 2 + 40, CLOCK_Y + 2, 74, WHITE)
    # 30 Fortschritts-Striche
    tw = 6
    x0 = W / 2 - (30 * (tw + 4)) / 2
    for d in range(1, 31):
        fill_rrect(c, x0 + (d - 1) * (tw + 4), CLOCK_Y + 74, tw, 14, 3, ORANGE if d <= day else PANEL2)

    # Drei Zähler
    for i, f in enumerate(FIGS):
        x = BOX_X0 + i * (BOX_W + BOX_GAP)
        e = last_pay(f, t)
        pulse = 0.0
        if e:
            pulse = 1 - (t - e["t"]) / 0.35
        hl = 0.0
        if 16.6 <= t < 22.0 and f == "handy":
            hl = 0.5 + 0.5 * math.sin(t * 8)
        if t >= 44.0:
            hl = 0.0
        sc = 1 + 0.04 * pulse
        with Saved(c, 1.0, x + BOX_W / 2, BOX_Y + BOX_H / 2, sc):
            fill_rrect(c, -BOX_W / 2, -BOX_H / 2, BOX_W, BOX_H, 28, mix(PANEL, COL[f], 0.18 * pulse + 0.12 * hl))
            rrect(c, -BOX_W / 2, -BOX_H / 2, BOX_W, BOX_H, 28)
            rgba(c, COL[f], 0.55 + 0.45 * max(pulse, hl)); c.set_line_width(4 + 4 * hl); c.stroke()
            # Kopf des Kästchens
            fill_rrect(c, -BOX_W / 2 + 14, -BOX_H / 2 + 14, BOX_W - 28, 44, 20, COL[f])
            font(c, 25, BLACK_F)
            lab1 = NAME[f]
            w1 = text_w(c, lab1, 25)
            w2 = text_w(c, " · AUSGEGEBEN", 21, XB_F)
            lx = -(w1 + w2) / 2
            text(c, lab1, lx, -BOX_H / 2 + 36, 25, INK, align="l")
            text(c, " · AUSGEGEBEN", lx + w1, -BOX_H / 2 + 36, 21, INK, face=XB_F, align="l")
            v = counter_value(f, t)
            text(c, euro(v), 0, 34, 76, WHITE, maxw=BOX_W - 30)


# ------------------------------------------------------------------ Bahnen
def focus_alpha(f, t):
    """Abdunkeln der Bahnen, die gerade nicht im Mittelpunkt stehen."""
    focus = None
    if 16.3 <= t < 30.0:
        focus = "handy"
    elif 30.0 <= t < 38.0:
        focus = "bar"
    elif 38.0 <= t < 43.8:
        focus = "karte"
    if focus is None:
        return 1.0
    k = min(ease((t - 16.3) / 0.4) if focus == "handy" and t < 17 else 1.0, 1.0)
    return 1.0 if f == focus else lerp(1.0, 0.42, k)


def lane_label(c, f, t, txt, t0, t1, icon_kind=None):
    a = win(t, t0, t1, 0.3, 0.3)
    if a <= 0:
        return
    y = lane_y(f)
    font(c, 27, BLACK_F)
    tw = text_w(c, txt, 27) + (50 if icon_kind else 0)
    x = (GRID_X0 + LANE_X1) / 2 - 14 - tw / 2 - 18
    with Saved(c, a, 0, (1 - eback((t - t0) / 0.35)) * -14):
        fill_rrect(c, x, y + 14, tw + 36, 50, 25, COL[f])
        tx = x + 18
        if icon_kind:
            with Saved(c, 1.0, tx + 18, y + 39):
                icon(c, icon_kind, 30, col=INK)
            tx += 50
        text(c, txt, tx, y + 39, 27, INK, align="l")


def slot_pos(f, slot):
    col, row = slot % GRID_COLS, slot // GRID_COLS
    return GRID_X0 + col * GRID_DX, lane_y(f) + 92 + row * 44


def draw_lane(c, f, t):
    y = lane_y(f)
    gy = ground_y(f)
    colr = COL[f]
    fill_rrect(c, LANE_X0, y, LANE_X1 - LANE_X0, LANE_H, 30, LANE)
    rrect(c, LANE_X0, y, LANE_X1 - LANE_X0, LANE_H, 30)
    rgba(c, colr, 0.35); c.set_line_width(3); c.stroke()
    fill_rrect(c, LANE_X0, y + 30, 10, LANE_H - 60, 5, colr)
    # Namensschild
    fill_rrect(c, LANE_X0 + 26, y + 16, 150, 48, 24, colr)
    with Saved(c, 1.0, LANE_X0 + 56, y + 40, 0.72):
        icon(c, {"bar": "bills", "karte": "card", "handy": "phone"}[f], 44)
    text(c, NAME[f], LANE_X0 + 84, y + 40, 28, INK, align="l", maxw=88)
    # Boden mit laufenden Strichen
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
    # Start-Linie (Szene 2)
    sa = win(t, 3.2, 8.4, 0.3, 0.4)
    if sa > 0:
        for k in range(8):
            for j in range(2):
                if (k + j) % 2 == 0:
                    c.rectangle(FIG_X + 70 + j * 12, gy - 96 + k * 12, 12, 12)
        rgba(c, WHITE, sa * 0.9); c.fill()
        text(c, "START", FIG_X + 82, gy - 116, 22, WHITE, sa)

    # Extras-Raster: bereits gelandete Extras
    done = [e for e in EVENTS if e["fig"] == f and e["extra"] and t >= e["t"] + fly_end(e)]
    for e in done:
        px, py = slot_pos(f, e["slot"])
        with Saved(c, 1.0, px, py):
            icon(c, e["kind"], 36)
    # Extras-Zähler unten rechts
    n = len(done)
    s = sum(e["amount"] for e in done)
    text(c, f"EXTRAS: {n}  ·  {euro(s, True)}", LANE_X1 - 34, y + LANE_H - 18, 22, colr, 0.95, face=XB_F, align="r")


def fly_end(e):
    return 0.55 if e["pay"] in ("coin",) else 0.8


def gesture(f, t):
    """Aktuelle Bezahlgeste der Figur: (pay 0..1, gehaltenes Ding, Anzahl Scheine, Ereignis)."""
    for e in EVENTS:
        if e["fig"] != f or e["skip"]:
            continue
        d = t - (e["t"] - 0.12)
        dur = e["paydur"]
        if 0 <= d <= dur + 0.15:
            k = min(d / 0.12, 1.0, (dur + 0.15 - d) / 0.15)
            n = 1
            if e["pay"] == "bills" and dur > 0.5:
                n = 1 + min(2, int(d / 0.25))
            return k, e["pay"], n, e
    return 0.0, None, 1, None


def draw_figure_lane(c, f, t):
    gy = ground_y(f)
    moving = is_moving(t) and t < 43.6
    walk = walked(t) / 150 * 7.0
    pay, held, n, ev = gesture(f, t)
    lean, nod = 0.0, 0.0
    # Handy zuckt nach Push-Nachricht zurück
    if f == "handy":
        for e in EVENTS:
            if e["fig"] == "handy" and e["push"] and 0.15 < t - e["t"] < 0.75:
                lean = -0.35 * math.sin((t - e["t"] - 0.15) / 0.6 * math.pi)
    # Kopfschütteln bei ausgelassenem Extra
    for e in EVENTS:
        if e["fig"] == f and e["skip"] and 0 < t - e["t"] < 0.8:
            nod = math.sin((t - e["t"]) * 30) * (1 - (t - e["t"]) / 0.8)
    if moving and pay > 0.3:
        moving = False
    head, hand = figure(c, FIG_X, gy, COL[f], walk, moving, pay, lean, held, n, nod)

    # Ausrufezeichen beim Zucken
    if lean < -0.1:
        text(c, "!", head[0] - 42, head[1] - 34, 48, ORANGE, min(1, -lean * 4))
    # Zögern der Bar: Gedankenpunkte beim Scheine-Zählen
    if ev is not None and ev["pay"] == "bills" and ev["paydur"] > 0.5:
        k = cl((t - ev["t"]) / 0.6)
        dots = "." * (1 + int(k * 2.9))
        fill_rrect(c, head[0] - 108, head[1] - 22, 70, 42, 20, WHITE, 0.92 * pay)
        text(c, dots, head[0] - 73, head[1] - 6, 34, INK, pay)

    # Bargeld: Geldautomat + Kleingeld in der Tasche
    if f == "bar":
        a = win(t, ATM_T[0] - 0.1, ATM_T[1] + 0.5, 0.25, 0.35)
        if a > 0:
            ax, ay = FIG_X + 150, gy - 170
            with Saved(c, a, ax, ay, 0.9 + 0.1 * eback((t - ATM_T[0]) / 0.3)):
                fill_rrect(c, -60, 0, 120, 170, 14, hexc("#3d5aa8"))
                fill_rrect(c, -44, 16, 88, 56, 8, hexc("#9fd3ff"))
                text(c, "ATM", 0, 44, 26, INK)
                fill_rrect(c, -40, 90, 80, 10, 5, INK)
                k = cl((t - ATM_T[0] - 0.3) / 0.6)
                for j in range(3):
                    with Saved(c, 1.0, -10 - 70 * k + j * 8, 100 + 18 * k + j * 5, 0.9, -0.4 * k):
                        icon(c, "bills", 40)
                text(c, "GELD ABHEBEN", 0, 194, 20, WHITE, face=XB_F)
        if t > ATM_T[0] + 0.7 and t < 44:
            # klimperndes Kleingeld an der Hosentasche
            for j in range(3):
                jig = math.sin(t * 13 + j * 2.1) * 4 if is_moving(t) else 0
                with Saved(c, min(1, (t - ATM_T[0] - 0.7) / 0.3), FIG_X - 38 + j * 13, gy - 66 + jig - j * 6, 0.62):
                    icon(c, "coin", 44)
            if 31.2 < t < 38 and int(t * 2.2) % 3 == 0:
                text(c, "kling!", FIG_X - 70, gy - 108, 22, YEL, 0.8, face=XB_F)

    # Gekaufte Dinge über dem Kopf / Flug ins Raster
    for e in EVENTS:
        if e["fig"] != f:
            continue
        d = t - e["t"]
        if d < 0 or d > 1.3:
            continue
        hx, hy = FIG_X + 52, lane_y(f) + 50
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
                with Saved(c, 1.0, hx, hy - 6 * d, eback(d / 0.18) * 1.15):
                    icon(c, e["kind"], 44)
                text(c, "+" + euro(e["amount"], True), hx + 34, hy - 6 * d, 25, WHITE, 1.0, face=XB_F, align="l",
                     outline=6)
            else:
                k = ease((d - hold) / (fe - hold))
                tx, ty = slot_pos(f, e["slot"])
                px = lerp(hx, tx, k)
                py = lerp(hy, ty, k) - math.sin(k * math.pi) * 60
                with Saved(c, 1.0, px, py, lerp(1.15, 0.82, k)):
                    icon(c, e["kind"], 44)
        else:  # Wocheneinkauf (gleicher Zettel)
            a = win(d, 0, 1.1, 0.1, 0.35)
            with Saved(c, a, hx, hy - 10 * d, eback(d / 0.2)):
                icon(c, "einkauf", 46)
            text(c, "+" + euro(e["amount"], True), hx + 34, hy - 10 * d, 25, WHITE, a, face=XB_F, align="l",
                 outline=6)
            text(c, "EINKAUF", hx + 34, hy - 10 * d + 28, 16, MUTED, a, face=XB_F, align="l")


def push_banners(c, t):
    f = "handy"
    y = lane_y(f)
    shown = [e for e in EVENTS if e["push"] and 0 <= t - e["t"] < 1.15]
    for e in shown[-1:]:
        d = t - e["t"]
        a = win(d, 0, 1.15, 0.12, 0.25)
        x0, w, h = 520, 500, 92
        yy = y + 74 + (1 - eout(d / 0.18)) * -40
        with Saved(c, a):
            fill_rrect(c, x0 + 4, yy + 8, w, h, 22, INK, 0.5)
            fill_rrect(c, x0, yy, w, h, 22, WHITE)
            fill_rrect(c, x0 + 16, yy + 16, 60, 60, 16, TEAL)
            text(c, "€", x0 + 46, yy + 46, 34, INK)
            text(c, "ZAHLUNG", x0 + 92, yy + 30, 22, hexc("#5a6a8f"), face=XB_F, align="l")
            text(c, "–" + euro(e["amount"], True), x0 + 92, yy + 62, 38, RED, align="l")
            with Saved(c, 1.0, x0 + w - 42, yy + 46, 1 + 0.2 * math.sin(d * 30) * (1 - cl(d / 0.5))):
                icon(c, "bell", 38, col=ORANGE)


def stage(c, t):
    for f in FIGS:
        a = focus_alpha(f, t)
        with Saved(c, a):
            draw_lane(c, f, t)
            draw_figure_lane(c, f, t)
    push_banners(c, t)
    lane_label(c, "handy", t, "PUSH-NACHRICHT AN", PUSH_FROM + 0.1, 30.0, "bell")
    lane_label(c, "bar", t, "KLEINGELD FÜHLT SICH WIE SPIELGELD AN", 31.0, 38.0)
    lane_label(c, "karte", t, "KEINE NACHRICHT · KEIN GEFÜHL", 38.4, 43.9)


# ------------------------------------------------------------------ Überlagerungen
def dim_stage(c, a):
    if a > 0:
        fill_rrect(c, LANE_X0 - 10, STAGE_TOP - 10, LANE_X1 - LANE_X0 + 20, STAGE_BOT - STAGE_TOP + 20, 34, BG2, a)


def title_card(c, t):
    a = win(t, -1, 3.35, 0, 0.3)
    if a <= 0:
        return
    dim_stage(c, 0.72 * a)
    sc = 1.0 if t > 0.25 else 0.94 + 0.06 * eback(t / 0.25)
    cy = 900
    with Saved(c, a, W / 2, cy, sc):
        fill_rrect(c, -480, -330, 960, 680, 46, PANEL)
        rrect(c, -480, -330, 960, 680, 46); rgba(c, WHITE, 0.15); c.set_line_width(3); c.stroke()
        rows = [("BAR", YEL, -230), ("vs", MUTED, -150), ("KARTE", RED, -70), ("vs", MUTED, 10), ("HANDY", TEAL, 90)]
        for i, (s, col, yy) in enumerate(rows):
            k = eback((t - i * 0.08) / 0.3) if t < 1 else 1.0
            size = 46 if s == "vs" else 118
            text(c, s, 0, yy, size * (0.6 + 0.4 * k), col, cl(k * 1.5))
        fill_rrect(c, -430, 170, 860, 140, 36, WHITE)
        text(c, "WER GIBT IM MONAT", 0, 212, 54, INK)
        text(c, "MEHR AUS?", 0, 270, 54, RED)


def sign(c, t, t0, t1, cy, kind, txt1, txt2=None):
    a = win(t, t0, t1, 0.25, 0.3)
    if a <= 0:
        return
    k = eback((t - t0) / 0.4)
    cx = 750
    with Saved(c, a, cx + (1 - k) * 300, cy, 1.0, -0.03 if kind == "list" else 0.03):
        fill_rrect(c, -270, -105, 540, 210, 30, WHITE)
        with Saved(c, 1.0, -190, 0, 2.2):
            icon(c, kind, 44)
        text(c, txt1, 50, -24 if txt2 else 0, 50 if txt2 else 84, INK, maxw=300)
        if txt2:
            text(c, txt2, 50, 34, 50, INK, maxw=300)


def scene2(c, t):
    sign(c, t, 3.4, 7.7, 660, "list", "GLEICHER", "EINKAUFSZETTEL")
    sign(c, t, 4.5, 7.7, 960, "calendar", "30 TAGE")
    a = win(t, 5.2, 7.7, 0.3, 0.3)
    if a > 0:
        text(c, "JEDER ZAHLT ANDERS", 750, 1210, 40, WHITE, a, outline=10)


def falsch(c, t):
    t0 = at("falsch", "Also") - 0.05
    t_noch = at("falsch", "Noch") - 0.05
    a = win(t, t0, 21.85, 0.25, 0.3)
    if a <= 0:
        return
    dim_stage(c, 0.0)
    k = eback((t - t0) / 0.35)
    with Saved(c, a, W / 2, 700, 0.7 + 0.3 * k):
        fill_rrect(c, -470, -110, 940, 220, 40, PANEL2)
        rrect(c, -470, -110, 940, 220, 40); rgba(c, TEAL); c.set_line_width(6); c.stroke()
        text(c, "HANDY =", 0, -45, 76, TEAL)
        text(c, "GELDFRESSER?", 0, 48, 88, WHITE, maxw=880)
    # Pfeil nach oben zum Handy-Zähler
    if t > t0 + 0.3:
        ax = BOX_X0 + 2 * (BOX_W + BOX_GAP) + BOX_W / 2
        bob = math.sin(t * 7) * 8
        with Saved(c, a, ax, 520 + bob):
            c.move_to(-26, 30); c.line_to(0, -6); c.line_to(26, 30); c.close_path(); rgba(c, TEAL); c.fill()
    b = win(t, t_noch, 21.85, 0.12, 0.3)
    if b > 0:
        k2 = eback((t - t_noch) / 0.25, 2.5)
        with Saved(c, b, W / 2, 965, 1.6 - 0.6 * k2, -0.06):
            fill_rrect(c, -400, -95, 800, 190, 34, ORANGE)
            text(c, "NOCH NICHT.", 0, 2, 104, INK, maxw=740)


def panel_frame(c, t, t0, t1):
    a = win(t, t0, t1, 0.3, 0.3)
    if a <= 0:
        return 0.0, 0.0
    k = eout((t - t0) / 0.4)
    dim_stage(c, 0.85 * a)
    with Saved(c, a, 0, (1 - k) * 80):
        fill_rrect(c, LANE_X0, STAGE_TOP, LANE_X1 - LANE_X0, STAGE_BOT - STAGE_TOP, 40, PANEL)
        rrect(c, LANE_X0, STAGE_TOP, LANE_X1 - LANE_X0, STAGE_BOT - STAGE_TOP, 40)
        rgba(c, WHITE, 0.15); c.set_line_width(3); c.stroke()
    return a, (1 - k) * 80


def endstand(c, t):
    a, dy = panel_frame(c, t, 43.95, 50.1)
    if a <= 0:
        return
    with Saved(c, a, 0, dy):
        text(c, "ENDSTAND · TAG 30", W / 2, STAGE_TOP + 80, 60, WHITE)
        rows = [("karte", 668), ("handy", 641), ("bar", 629)]
        t_first = at("endstand", "Karte") - 0.1
        for i, (f, v) in enumerate(rows):
            tr = t_first + i * 0.55
            k = eback((t - tr) / 0.35)
            if t < tr:
                continue
            yy = STAGE_TOP + 210 + i * 150
            with Saved(c, cl(k * 2), (1 - k) * -120, 0):
                fill_rrect(c, 70, yy - 52, 940, 104, 30, PANEL2 if i else mix(PANEL2, RED, 0.25))
                text(c, f"{i + 1}.", 116, yy, 46, MUTED)
                fill_rrect(c, 156, yy - 30, 196, 60, 30, COL[f])
                text(c, NAME[f], 254, yy, 34, INK, maxw=170)
                bw = 380 * v / 668 * ease((t - tr) / 0.6)
                fill_rrect(c, 372, yy - 16, max(bw, 8), 32, 16, COL[f], 0.85)
                text(c, f"{v} €", 990, yy, 62, WHITE, align="r")
        tb = at("endstand", "Aber") - 0.1
        if t > tb - 0.6:
            tb = min(tb, t_first + 1.65)
        b = win(t, tb, 99, 0.2, 0)
        if b > 0:
            k = eback((t - tb) / 0.3)
            with Saved(c, b, W / 2, STAGE_TOP + 700, 0.8 + 0.2 * k):
                fill_rrect(c, -440, -62, 880, 124, 34, RED)
                text(c, "KARTE GIBT AM MEISTEN AUS", 0, 0, 52, WHITE, maxw=820)
        td = at("endstand", "deutlich") - 0.1
        d = win(t, td, 99, 0.25, 0)
        if d > 0:
            text(c, "Unterschied Karte ↔ Bar: nur 39 € (≈ 6 %)", W / 2, STAGE_TOP + 820, 34, WHITE, d, face=XB_F)


def schmerz(c, t):
    a, dy = panel_frame(c, t, 49.95, 57.1)
    if a <= 0:
        return
    with Saved(c, a, 0, dy):
        text(c, "SCHMERZ BEIM BEZAHLEN", W / 2, STAGE_TOP + 78, 58, WHITE, maxw=940)
        cols = [("bar", 0.92, "HOCH", "man sieht das", "Geld gehen", "bills"),
                ("handy", 0.56, "MITTEL", "Push-", "Nachricht", "phone"),
                ("karte", 0.16, "NIEDRIG", "man sieht", "nichts", "card")]
        base = STAGE_TOP + 520
        for i, (f, v, lab, c1, c2, ik) in enumerate(cols):
            tr = 50.3 + i * 0.45
            if t < tr:
                continue
            x = 240 + i * 300
            k = eout((t - tr) / 0.6)
            hgt = 330 * v * k
            fill_rrect(c, x - 85, base - 330, 170, 330, 24, PANEL2)
            fill_rrect(c, x - 85, base - hgt, 170, max(hgt, 24), 24, COL[f])
            text(c, lab, x, base - hgt - 34, 40, COL[f], cl(k * 2))
            with Saved(c, cl(k * 2), x, base - 40, 1.4):
                icon(c, ik, 44)
            fill_rrect(c, x - 90, base + 22, 180, 54, 27, COL[f])
            text(c, NAME[f], x, base + 49, 30, INK)
            text(c, c1, x, base + 108, 28, WHITE, cl(k * 2), face=XB_F)
            text(c, c2, x, base + 142, 28, WHITE, cl(k * 2), face=XB_F)
        ts = at("schmerz", "wenn") - 0.2
        b = win(t, ts, 99, 0.3, 0)
        if b > 0:
            k = eback((t - ts) / 0.35)
            with Saved(c, b, W / 2, STAGE_TOP + 800, 0.85 + 0.15 * k):
                fill_rrect(c, -480, -78, 960, 156, 34, WHITE)
                text(c, "NICHT DAS ZAHLUNGSMITTEL ENTSCHEIDET –", 0, -30, 38, INK, maxw=900)
                text(c, "SONDERN OB DU ES SIEHST", 0, 30, 52, ORANGE, maxw=900, outline=0)


def endkarte(c, t):
    a, dy = panel_frame(c, t, 56.95, 61)
    if a <= 0:
        return
    with Saved(c, a, 0, dy):
        k1 = eback((t - 57.0) / 0.35)
        with Saved(c, cl(k1 * 2), W / 2, STAGE_TOP + 120, 0.8 + 0.2 * k1):
            text(c, "Was wäre, wenn …", 0, 0, 70, WHITE, maxw=920)
            fill_rrect(c, -230, 52, 460, 84, 42, ORANGE)
            text(c, "TEIL 2 FOLGT.", 0, 94, 48, INK)
        k2 = eback((t - 57.25) / 0.35)
        with Saved(c, cl(k2 * 2), W / 2, STAGE_TOP + 400, 0.8 + 0.2 * k2):
            text(c, "Wie zahlst du?", 0, 0, 92, WHITE, maxw=940)
            text(c, "Schreib's in die Kommentare.", 0, 90, 50, MUTED, face=XB_F, maxw=920)
        for i, f in enumerate(["bar", "karte", "handy"]):
            k = eback((t - 57.5 - i * 0.12) / 0.3)
            if t < 57.5 + i * 0.12:
                continue
            x = 220 + i * 320
            with Saved(c, cl(k * 2), x, STAGE_TOP + 640, 0.6 + 0.4 * k):
                fill_rrect(c, -135, -52, 270, 104, 52, COL[f])
                with Saved(c, 1.0, -78, 0, 1.0):
                    icon(c, {"bar": "bills", "karte": "card", "handy": "phone"}[f], 44)
                text(c, NAME[f], 22, 0, 40, INK, maxw=150)
        text(c, "BEISPIELRECHNUNG · RICHTUNG NACH STUDIEN ZUM ‚BEZAHLSCHMERZ'", W / 2, STAGE_BOT - 50, 22,
             MUTED, face=XB_F, maxw=960)


# ------------------------------------------------------------------ Untertitel
HL = {"bar": YEL, "bargeld": YEL, "kleingeld": YEL, "karte": RED, "handy": TEAL}


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
        if cur and (cur[-1]["scene"] != w["scene"]):
            chunks.append(cur)
            cur = []
        cur.append(w)
        if w["show"][-1] in ".,?!" or len(cur) >= 4:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


CHUNKS = build_chunks()
SUB_SIZE = 66


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
        # Zeilenumbruch bei Überbreite
        lines, line, lw = [], [], 0
        for j, wd in enumerate(widths):
            if line and lw + sp + wd > 940:
                lines.append((line, lw))
                line, lw = [], 0
            lw = lw + (sp if line else 0) + wd
            line.append(j)
        lines.append((line, lw))
        for li, (idxs, lwid) in enumerate(lines):
            y = SUB_Y + (li - (len(lines) - 1) / 2) * 84
            x = W / 2 - lwid / 2
            for j in idxs:
                w = ch[j]
                if t >= w["start"] - 0.04:
                    act = w["start"] - 0.04 <= t < (ch[j + 1]["start"] if j + 1 < len(ch) else w["end"] + 0.15)
                    k = eback((t - w["start"] + 0.04) / 0.16)
                    sc = (1.12 if act else 1.0) * (0.7 + 0.3 * k)
                    cx = x + widths[j] / 2
                    with Saved(c, 1.0, cx, y, sc):
                        if act:
                            fill_rrect(c, -widths[j] / 2 - 12, -46, widths[j] + 24, 92, 18, WHITE, 0.14)
                        text(c, words[j], 0, 0, SUB_SIZE, word_color(w), 1.0, outline=12)
                x += widths[j] + sp
        break


# ------------------------------------------------------------------ Frame
def frame(t):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    c = cairo.Context(surf)
    background(c)
    stage(c, t)
    title_card(c, t)
    scene2(c, t)
    falsch(c, t)
    endstand(c, t)
    schmerz(c, t)
    endkarte(c, t)
    hud(c, t)
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
           "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", "-t", f"{DURATION}", "-movflags", "+faststart", str(OUT)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, b in enumerate(pool.imap(frame_bytes, range(NFRAMES), chunksize=8)):
            p.stdin.write(b)
            if i % 150 == 0:
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
