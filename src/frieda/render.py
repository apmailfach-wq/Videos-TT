"""Frieda an der Supermarktkasse – 3D-Spielzeug-Look, 1080x1920, 30 fps, ~57 s.

python3 tts.py && python3 render.py            -> ../../frieda-supermarkt.mp4
python3 render.py preview 2 15 17 23 25.5 28 33 42 46 51.5    -> build/frieda/stills/
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
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fuehrerschein"))
import fchars  # Oma Frieda Faust – Original-Figur (Folge 1) mit aktuellem Outfit
from core import (F_BLACK, F_INTER, W, H, FPS, capsule, gradient, ease_in, clamp01, ease_back, ease_io, ease_out, emoji, font,  # noqa
                  lerp, mixc, paste_c, sphere, text_img, zoom_frame)

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "frieda"
OUT = Path(os.environ.get("VIDEO_OUT", ROOT / "frieda-supermarkt.mp4"))
SR = 48000

# ------------------------------------------------------------------ timeline (seconds)
LINES = {l["id"]: l for l in json.loads((BUILD / "lines.json").read_text())}

T_LINE = {
    "kas0": 2.0, "fr0": 3.0, "typ0": 6.3, "k2a": 9.45, "typ1": 12.1,
    "fr1": 14.85, "typ2": 15.75, "fr4": 19.0, "typ5": 22.6, "fr5": 25.2,
    "mk1": 31.3,
    "k3a": 33.2, "typ3": 37.4,
    "kas2": 39.95, "fr3": 42.15,
    "kas3": 46.45, "kas4": 49.95, "fr6": 51.75, "kas1": 53.35,
    "fr2": 55.3, "typ4": 57.2, "tel": 59.5,
}
for _k in LINES:                      # Zeilen anderer Fassungen hier stumm schalten
    T_LINE.setdefault(_k, 999.0)
T_K0_LEAVE = 2.5                      # Kunde vor Frieda geht
T_GUY_IN0, T_GUY_IN1 = 6.1, 9.3       # Drängler läuft rein (telefoniert)
T_PUSH = 14.3                         # Musik weg, Kamera drückt rein
T_CONF_A, T_CONF_B = 14.6, 26.45      # Schuss/Gegenschuss vor dem Wurf
T_GRAB, T_THROW, T_FLY, T_LAND, T_SLOW_END = 26.45, 27.1, 27.6, 29.75, 30.15
T_IPPON = 29.85
T_CARDS = 30.1                        # Wertungstafeln hoch
T_TITLE_END = 2.7                     # Titel "Frieda geht einkaufen"
T_IPPON_END = None                    # None = bis kurz nach den Wertungstafeln
T_CLAP0, T_CLAP1 = 30.15, 32.5
T_MUSK0, T_MUSK1 = 31.0, 32.8         # Muskelprotz schleicht nach hinten
T_CATCH = T_LAND + 0.3                # Frieda fängt die Dose
T_BACK1A, T_BACK1B = 33.1, 39.65      # Ende der Schlange: Herr + benommener Typ
T_CARDS_END = T_BACK1A
T_FLASH_A, T_FLASH_B = 41.85, 45.7    # Rückblende 1974
T_CUKE = 45.85                        # Gurke + Dose aufs Band
T_BEEP = 46.25
T_CLOSE2A = 54.95                     # Close-up "Mit Stil."
T_WINK = 56.4
T_BACK2A, T_BACK2B = 57.0, 61.75      # Typ hinten am Handy (+ Kumpel antwortet)
T_END_TXT = 62.05
T_CLOSE = T_CLOSE2A
TOTAL = 64.3
NF = int(TOTAL * FPS)

SKIN = (247, 200, 170)
DARK = (48, 36, 52)


# ------------------------------------------------------------------ helpers
def seg(t, a, b):
    return clamp01((t - a) / (b - a))


def speaking(lid, t):
    """Mouth openness 0..1 while the line is spoken."""
    l = LINES[lid]
    t0 = T_LINE[lid]
    lt = t - t0 + l["lead"]
    for w in l["words"]:
        if w["start"] - 0.02 <= lt <= w["end"] + 0.02:
            p = (lt - w["start"]) / max(0.05, w["end"] - w["start"])
            return 0.35 + 0.65 * abs(math.sin(p * math.pi * max(1, len(w["text"]) / 3)))
    return 0.0


def line_on(lid, t, extra=0.35):
    t0 = T_LINE[lid]
    return t0 - 0.08 <= t <= t0 + LINES[lid]["speech"] + extra


def rot_paste(dst, img, cx, cy, ang):
    if abs(ang) > 0.3:
        img = img.rotate(ang, resample=Image.BICUBIC, expand=True)
    paste_c(dst, img, cx, cy)


# ------------------------------------------------------------------ Figuren (Oma-Frieda-Faust-Stil für alle)
fchars.person_raw = lru_cache(maxsize=500)(fchars.person_raw.__wrapped__)
fchars.head = lru_cache(maxsize=500)(fchars.head.__wrapped__)
fchars.CFG["kasse"] = dict(skin=(244, 200, 172), hair="pigtails", eye=(110, 72, 40), glasses=False, old=False,
                           female=True, brow=(70, 45, 35), body="kasse", lash=True)
fchars.BODY["kasse"] = dict(sh=0.48, hip=0.5, tl=1.3, arm=0.28, hand=0.13, top=(30, 165, 150), leg=(50, 60, 90),
                            shoe=(40, 40, 40), pants=(50, 60, 90))
_STL = (((-0.18, 1.3), (-0.2, 2.0), (-0.22, 2.7)), ((0.18, 1.3), (0.2, 2.0), (0.22, 2.7)))
_KIDL = (((-0.18, 1.2), (-0.2, 1.7), (-0.22, 2.2)), ((0.18, 1.2), (0.2, 1.7), (0.22, 2.2)))
_HANG_L = ((-0.62, 0.7), (-0.58, 1.3), "front")
for name, legs in (("", _STL), ("kid_", _KIDL)):
    fchars.POSES[name + "clap_a"] = dict(lower="pants", legs=legs, arms=(((-0.62, 0.6), (-0.34, 0.62), "front"),
                                                                         ((0.62, 0.6), (0.34, 0.62), "front")))
    fchars.POSES[name + "clap_b"] = dict(lower="pants", legs=legs, arms=(((-0.62, 0.6), (-0.07, 0.6), "front"),
                                                                         ((0.62, 0.6), (0.07, 0.6), "front")))
fchars.POSES["g_phone"] = dict(lower="pants", legs=_STL, arms=(_HANG_L, ((0.86, 0.45), (0.44, -0.36), "front")))
fchars.POSES["g_shrug"] = dict(lower="pants", legs=_STL, arms=(((-0.85, 0.55), (-1.12, 0.3), "front"),
                                                               ((0.85, 0.55), (1.12, 0.3), "front")))
fchars.POSES["g_film"] = dict(lower="pants", legs=_STL, arms=(_HANG_L, ((0.86, 0.35), (0.66, -0.18), "front")))
GUY_LIVE = False   # Kurzfassung: der Drängler filmt sich im Livestream
fchars.POSES["c_wave"] = dict(lower="pants", legs=_STL, arms=(_HANG_L, ((0.85, 0.2), (0.95, -0.45), "front")))
KIDS = {"girl", "kid3", "kid4", "kleiner"}
SER_D = 200   # Kopf-Einheit bei Szenen-Skalierung 1.0


def K(who, pose=None, expr="neutral", m=0.0, mirror=False, shades=False, can=False, bag=False, phone=False,
      blink=False):
    if pose is None:
        pose = "kid_stand" if who in KIDS else "b_stand"
    return (who, pose, expr, round(m, 1), mirror, shades, can, bag, phone, blink)


@lru_cache(maxsize=64)
def eye_boxes(who, D, pose, expr):
    a, (nx, ny), _ = fchars.person(who, D, pose, expr=expr)
    b, _, _ = fchars.person(who, D, pose, expr=expr, blink=True)
    diff = np.abs(np.asarray(a).astype(np.int16) - np.asarray(b).astype(np.int16)).sum(axis=2) > 6
    boxes = []
    for side in (0, 1):
        m = diff.copy()
        if side == 0:
            m[:, int(nx):] = False
        else:
            m[:, : int(nx)] = False
        ys, xs = np.nonzero(m)
        if len(xs):
            boxes.append((xs.min(), ys.min(), xs.max(), ys.max()))
    return boxes


@lru_cache(maxsize=8)
def can_sprite(D):
    k = D / 200
    can = capsule(max(8, int(46 * k)), max(16, int(96 * k)), (30, 40, 70), None, radius=max(3, int(12 * k))).copy()
    cd = ImageDraw.Draw(can)
    cd.polygon([(26 * k, 14 * k), (12 * k, 50 * k), (24 * k, 50 * k), (17 * k, 82 * k), (35 * k, 42 * k),
                (23 * k, 42 * k)], fill=(170, 255, 40))
    return can


@lru_cache(maxsize=8)
def bag_sprite(D):
    k = D / 200
    bg = capsule(int(120 * k), int(130 * k), (205, 160, 110), None, radius=int(14 * k)).copy()
    paste_c(bg, sphere(int(46 * k), (240, 60, 60), None, 0.4), 40 * k, 14 * k)
    paste_c(bg, capsule(int(30 * k), int(70 * k), (250, 220, 80), None), 80 * k, 10 * k)
    return bg


@lru_cache(maxsize=400)
def series_sprite(key, D):
    who, pose, expr, m, mirror, shades, can, bag, phone, blink = key
    P = fchars.pose_dict(who, pose)
    items = ()
    if phone:
        hx, hy = P["arms"][1][1]
        items = (("phone", (hx + 0.02, hy - 0.1)),)
    im, (nx, ny), sc = fchars.person(who, D, pose, expr=expr, mouth=m, items=items, blink=blink)
    im = im.copy()
    Dq = D / sc
    if shades:
        d = ImageDraw.Draw(im)
        bx = eye_boxes(who, int(round(Dq)), pose, "neutral")
        cs = []
        for (x0, y0, x1, y1) in bx:
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + Dq * 0.01
            w = Dq * 0.27
            h = w * 0.7
            d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=h * 0.35, fill=(18, 18, 24))
            d.line([(cx - w * 0.3, cy - h * 0.15), (cx - w * 0.05, cy - h * 0.3)], fill=(150, 200, 255),
                   width=max(2, int(Dq * 0.02)))
            cs.append((cx, cy, w))
        if len(cs) == 2:
            (ax, ay, aw), (bx2, by, bw) = sorted(cs)
            d.line([(ax + aw / 2, ay - aw * 0.12), (bx2 - bw / 2, by - bw * 0.12)], fill=(18, 18, 24),
                   width=max(3, int(Dq * 0.03)))
    if can:
        hx, hy = P["arms"][0][1]
        paste_c(im, can_sprite(int(Dq)), nx + hx * Dq, ny + hy * Dq - Dq * 0.12)
    if bag:
        hx, hy = P["arms"][0][1]
        paste_c(im, bag_sprite(int(Dq)), nx + hx * Dq, ny + hy * Dq + Dq * 0.3)
    if abs(sc - 1) > 0.01:
        im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
        nx, ny = nx * sc, ny * sc
    if mirror:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
        nx = im.width - nx
    feet = im.getbbox()[3] - 4 * D / 200
    return im, nx, ny, feet


def draw_series(frame, key, x, y, s, rot=0.0, alpha=1.0, squash=1.0):
    D = max(24, int(round(SER_D * s)))
    im, nx, ny, feet = series_sprite(key, D)
    if squash != 1.0:
        im = im.resize((int(im.width / squash ** 0.5), int(im.height * squash)), Image.BICUBIC)
        nx, ny, feet = nx / squash ** 0.5, ny * squash, feet * squash
    if rot:
        cy = (ny + feet) / 2
        im = im.rotate(rot, resample=Image.BICUBIC, center=(nx, cy))
        paste_c(frame, im, x - nx + im.width / 2, y - (feet - cy) - cy + im.height / 2, alpha=alpha)
    else:
        paste_c(frame, im, x - nx + im.width / 2, y - feet + im.height / 2, alpha=alpha)


def head_top(x, y, s, who="adult"):
    D = SER_D * s
    return x, y - (2.25 if who in KIDS else 2.9) * D - 0.75 * D


# ------------------------------------------------------------------ Supermarkt
VPX, VPY = 540, 470
FLOOR_Y = 830


@lru_cache(maxsize=1)
def background():
    yy = np.linspace(0, 1, H)[:, None]
    wall = np.zeros((H, W, 3), np.float32)
    wall[:] = (np.array((252, 244, 232)) * (1 - yy[..., None]) + np.array((244, 232, 220)) * yy[..., None])
    # heller, glänzender Fliesenboden
    ys, xs = np.mgrid[FLOOR_Y:H, 0:W].astype(np.float32)
    z = 520.0 / (ys - VPY)
    xw = (xs - VPX) * z
    par = (np.floor(xw / 70) + np.floor(z * 6)) % 2
    c1, c2 = np.array((246, 246, 244)), np.array((210, 222, 230))
    fl = c1 * (1 - par[..., None]) + c2 * par[..., None]
    gl = np.exp(-((ys - FLOOR_Y) / 140.0)) * 0.35          # Glanz der Deckenlampen
    fl = fl * (1 - gl[..., None]) + 255 * gl[..., None]
    fl = fl * (1 - 0.08 * np.clip((z - 0.4), 0, 1)[..., None])
    wall[FLOOR_Y:] = fl
    img = Image.fromarray(wall.clip(0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img)
    # Decke mit Lichtpaneelen
    d.rectangle([0, 0, W, 150], fill=(232, 232, 238))
    d.line([(0, 150), (W, 150)], fill=(200, 200, 210), width=4)
    glow = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for x in (90, 400, 710, 1020):
        gd.rounded_rectangle([x - 110, 40, x + 110, 80], radius=10, fill=(255, 255, 240, 255))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(18)))
    img.alpha_composite(glow)
    # Gang-Schilder
    for x, txt, col in ((190, "OBST & GEMÜSE", (60, 160, 80)), (540, "GETRÄNKE", (40, 110, 200)),
                        (890, "SÜSSES", (220, 70, 130))):
        d.line([(x - 90, 150), (x - 90, 186)], fill=(150, 150, 160), width=4)
        d.line([(x + 90, 150), (x + 90, 186)], fill=(150, 150, 160), width=4)
        paste_c(img, capsule(300, 66, col, None, radius=16), x, 214)
        d.text((x, 216), txt, font=font(F_BLACK, 30), fill=(255, 255, 255), anchor="mm")
    # Regale: Rückwand, Böden, Ware, Preisschilder
    d.rectangle([14, 252, W - 14, FLOOR_Y], fill=(236, 226, 212))
    d.rectangle([14, 252, W - 14, 274], fill=(205, 70, 70))
    rng = random.Random(7)
    pal = [(255, 90, 90), (255, 190, 40), (90, 170, 255), (120, 220, 120), (255, 130, 200), (170, 120, 255),
           (255, 150, 60), (60, 200, 190)]
    for row, y in enumerate((405, 555, 700, 818)):
        x = 30
        while x < W - 80:
            kind = rng.random()
            col = rng.choice(pal)
            if kind < 0.45:
                w, h = rng.randint(58, 84), rng.randint(84, 120)
                paste_c(img, capsule(w, h, col, None, radius=12), x + w / 2, y - h / 2 + 2)
                d.rounded_rectangle([x + 9, y - h * 0.65, x + w - 9, y - h * 0.4], radius=6, fill=(255, 255, 255))
            elif kind < 0.8:
                w, h = rng.randint(40, 56), rng.randint(100, 136)
                paste_c(img, capsule(w, h, col, None), x + w / 2, y - h / 2 + 2)
                paste_c(img, capsule(w // 2, 28, mixc(col, (255, 255, 255), 0.5), None), x + w / 2, y - h + 6)
            else:
                w = rng.randint(60, 78)
                paste_c(img, sphere(w, col, None, 0.4), x + w / 2, y - w / 2 + 4)
            x += w + rng.randint(5, 12)
        d.rounded_rectangle([20, y, W - 20, y + 18], radius=6, fill=(190, 196, 206))
        d.line([(20, y + 2), (W - 20, y + 2)], fill=(240, 244, 250), width=3)
        for px in range(70, W - 60, 150):  # Preisschilder
            d.rectangle([px, y + 3, px + 46, y + 17], fill=(255, 226, 60))
            d.text((px + 23, y + 10), f"{rng.randint(0, 4)},{rng.choice([19, 49, 79, 99])}",
                   font=font(F_BLACK, 11), fill=(40, 30, 30), anchor="mm")
    # Obststand rechts hinten
    for i, (fc, kind) in enumerate((((230, 50, 50), "s"), ((255, 210, 40), "b"), ((255, 150, 30), "s"))):
        x0 = 640 + i * 150
        paste_c(img, capsule(140, 80, (70, 150, 80), None, radius=12), x0 + 70, 930)
        d.line([(x0 + 8, 912), (x0 + 132, 912)], fill=(50, 120, 60), width=4)
        for j in range(7):
            fx, fy = x0 + 18 + (j % 4) * 34 + (17 if j >= 4 else 0), 890 - (12 if j >= 4 else 0)
            if kind == "s":
                paste_c(img, sphere(36, fc, None, 0.5), fx, fy)
            else:
                rot_paste(img, capsule(22, 60, fc, None), fx, fy, 60)
        d.rounded_rectangle([x0 + 40, 950, x0 + 100, 972], radius=4, fill=(255, 255, 255))
        d.text((x0 + 70, 961), ("1,29", "0,99", "1,99")[i], font=font(F_BLACK, 15), fill=(200, 40, 40), anchor="mm")
    return img


@lru_cache(maxsize=1)
def counter_static():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Kassenlicht "1"
    d.rounded_rectangle([18, 760, 32, 1620], radius=6, fill=(170, 176, 186))
    paste_c(img, capsule(96, 80, (40, 44, 52), None, radius=14), 25, 740)
    lamp = Image.new("RGBA", (W, 220), (0, 0, 0, 0))
    ImageDraw.Draw(lamp).ellipse([0, 50, 60, 120], fill=(80, 255, 140, 200))
    img.alpha_composite(lamp.filter(ImageFilter.GaussianBlur(14)), (0, 650))
    d.text((32, 742), "1", font=font(F_BLACK, 54), fill=(120, 255, 160), anchor="mm")
    # Kassentisch: Front
    paste_c(img, capsule(860, 300, (238, 236, 232), None, radius=34), 370, 1820)
    d.rectangle([-40, 1716, 800, 1730], fill=(196, 200, 208))
    d.rectangle([-40, 1748, 790, 1792], fill=(214, 44, 52))
    d.text((370, 1872), "FRISCH & BUNT", font=font(F_BLACK, 50), fill=(214, 44, 52), anchor="mm")
    d.text((370, 1771), "IHR SUPERMARKT", font=font(F_BLACK, 24), fill=(255, 255, 255), anchor="mm")
    # Laufband mit Metallkanten
    d.polygon([(-20, 1606), (800, 1606), (790, 1700), (-20, 1700)], fill=(66, 70, 82))
    d.rounded_rectangle([-30, 1594, 812, 1612], radius=8, fill=(214, 218, 226))
    d.line([(-30, 1598), (812, 1598)], fill=(250, 252, 255), width=3)
    d.rounded_rectangle([-30, 1696, 802, 1716], radius=8, fill=(190, 194, 204))
    # Scanner: Glasplatte + Turm
    d.rounded_rectangle([44, 1616, 214, 1690], radius=10, fill=(150, 156, 168))
    d.rounded_rectangle([62, 1626, 196, 1680], radius=8, fill=(40, 26, 36))
    paste_c(img, capsule(150, 96, (176, 182, 194), None, radius=18), 130, 1560)
    d.rounded_rectangle([82, 1530, 178, 1588], radius=10, fill=(40, 26, 36))
    # Warentrenner auf dem Band
    rot_paste(img, capsule(26, 190, (250, 150, 40), None, radius=10), 700, 1650, 90)
    d.text((700, 1650), "WARENTRENNER", font=font(F_BLACK, 12), fill=(80, 40, 10), anchor="mm")
    # Kassenmonitor (zur Kassiererin) auf Stange
    d.rounded_rectangle([250, 1470, 262, 1600], radius=4, fill=(170, 176, 186))
    paste_c(img, capsule(170, 116, (52, 56, 66), None, radius=14), 256, 1440)
    # Kartenterminal zum Kunden
    d.rounded_rectangle([452, 1546, 464, 1600], radius=4, fill=(150, 156, 168))
    paste_c(img, capsule(96, 130, (40, 42, 50), None, radius=16), 458, 1510)
    for r in range(3):
        for c in range(3):
            d.rounded_rectangle([430 + c * 20, 1520 + r * 15, 444 + c * 20, 1531 + r * 15], radius=3,
                                fill=(200, 205, 215))
    # Quengelregal rechts
    d.rounded_rectangle([880, 1360, 1090, 1730], radius=14, fill=(196, 200, 210))
    rng = random.Random(3)
    for r, y in enumerate((1400, 1480, 1560, 1640)):
        d.rectangle([890, y + 56, 1080, y + 64], fill=(150, 156, 168))
        x = 896
        while x < 1060:
            w = rng.randint(26, 40)
            col = rng.choice([(255, 80, 80), (255, 200, 40), (90, 170, 255), (255, 120, 200), (120, 220, 120)])
            paste_c(img, capsule(w, 50, col, None, radius=6), x + w / 2, y + 30)
            x += w + 4
    d.rounded_rectangle([900, 1330, 1070, 1372], radius=10, fill=(255, 214, 60))
    d.text((985, 1352), "SÜSSES", font=font(F_BLACK, 26), fill=(160, 40, 60), anchor="mm")
    return img


def draw_counter(frame, t):
    frame.alpha_composite(counter_static())
    d = ImageDraw.Draw(frame)
    off = (max(0.0, t - T_CUKE - 0.5) * 120) % 46
    for i in range(20):
        x = 230 + i * 46 - off
        if 226 < x < 790:
            d.line([(x, 1612), (x - 6, 1694)], fill=(54, 58, 70), width=5)
    a = 0.6 + 0.4 * math.sin(t * 20)
    d.line([(70, 1654), (188, 1654)], fill=(255, int(60 * a), int(60 * a)), width=4)
    d.line([(92, 1560), (168, 1560)], fill=(255, int(60 * a), int(60 * a)), width=3)
    # Kassenmonitor + Terminal-Anzeige
    if t < T_K0_LEAVE:
        txt, term = "12,87", "12,87"
    elif t < T_BEEP:
        txt, term = "0,00", "Hallo!"
    else:
        txt, term = "0,49", "0,49 €"
    d.rounded_rectangle([186, 1396, 326, 1484], radius=8, fill=(20, 40, 50))
    d.text((256, 1424), "SUMME", font=font(F_BLACK, 18), fill=(140, 220, 255), anchor="mm")
    d.text((256, 1456), txt, font=font(F_BLACK, 34), fill=(120, 255, 180), anchor="mm")
    if T_LINE["kas1"] <= t:
        term = "Karte?"
    d.rounded_rectangle([422, 1462, 494, 1508], radius=6, fill=(170, 230, 200))
    d.text((458, 1485), term, font=font(F_BLACK, 15), fill=(20, 60, 40), anchor="mm")


# ------------------------------------------------------------------ positions (x, feet_y, scale)
FRIEDA = (575, 1645, 0.95)
CASH = (150, 1625, 0.86)
K0 = (330, 1665, 0.9)
GUY_SPOT = (300, 1700, 0.95)
QUEUE = [("pass1", 790, 1365, 0.78), ("musk1", 585, 1190, 0.6), ("girl", 775, 1060, 0.56),
         ("pass2", 600, 955, 0.46)]
LAND = (790, 885, 0.4)
GUY = "bully2"


def k0_state(t):
    if t >= T_K0_LEAVE + 1.6:
        return None
    p = ease_io(seg(t, T_K0_LEAVE, T_K0_LEAVE + 1.6))
    bob = abs(math.sin(t * 13)) * 12 if 0 < p < 1 else 0
    return K0[0] - 560 * p, K0[1] - bob, K0[2], K("gamer", expr="smile", bag=True)


def guy_state(t):
    """dict(x, y, s, rot, key[, trail, squash])"""
    if t < T_GUY_IN0:
        return None
    shades = t < T_LINE["typ5"]
    if t < T_GUY_IN1:  # telefoniert, läuft an der Schlange vorbei bis ganz vorne
        p = ease_io(seg(t, T_GUY_IN0, T_GUY_IN1))
        bob = abs(math.sin(t * 13)) * 14 * (1 if p < 0.97 else 0)
        m = speaking("typ0", t)
        m = max(m, speaking("typL", t))
        return dict(x=lerp(1260, GUY_SPOT[0], p), y=GUY_SPOT[1] - bob, s=GUY_SPOT[2], rot=0,
                    key=K(GUY, "g_film" if GUY_LIVE else "g_phone", "smirk", m, shades=shades, can=True, phone=True))
    if t < T_GRAB + 0.2:
        m = max(speaking("typ1", t), speaking("typ2", t), speaking("typ1b", t))
        pose, expr = "b_stand", "arrogant"
        if line_on("typ1", t, 0) or line_on("typ1b", t, 0):
            pose, expr = "g_shrug", "smirk"
        if t >= T_LINE["typ5"]:
            pose, expr = "b_hold", "glare"
        if t >= T_GRAB:
            pose, expr = "pass_shock", "shock"
        live = GUY_LIVE and pose in ("b_stand", "g_shrug")
        if live:
            pose = "g_film"
        return dict(x=GUY_SPOT[0], y=GUY_SPOT[1], s=GUY_SPOT[2], rot=0,
                    key=K(GUY, pose, expr, m, shades=shades, can=pose != "pass_shock", phone=live))
    if t < T_FLY:  # wird über Friedas Hüfte gehebelt (Zeitlupe)
        p = ease_io(seg(t, T_GRAB + 0.2, T_FLY))
        x = lerp(GUY_SPOT[0], FRIEDA[0], p)
        y = lerp(GUY_SPOT[1], 1300, p) - math.sin(p * math.pi) * 140
        return dict(x=x, y=y, s=GUY_SPOT[2], rot=lerp(0, -170, p), key=K(GUY, "thief_fly", "scared", 0.8))
    if t < T_LAND:  # hoher Bogen ans Ende der Schlange
        p = seg(t, T_FLY, T_LAND)
        pe = ease_io(p)
        x0, y0 = FRIEDA[0], 1300
        x = (1 - pe) ** 2 * x0 + 2 * (1 - pe) * pe * 700 + pe ** 2 * LAND[0]
        y = (1 - pe) ** 2 * y0 + 2 * (1 - pe) * pe * 200 + pe ** 2 * LAND[1]
        return dict(x=x, y=y, s=lerp(GUY_SPOT[2], LAND[2], pe), rot=lerp(-170, -360, pe), trail=True,
                    key=K(GUY, "thief_fly", "scared", 0.8))
    p = seg(t, T_LAND, T_LAND + 0.45)
    sq = round(1 - 0.25 * math.sin(p * math.pi), 2) if p < 1 else 1.0
    return dict(x=LAND[0], y=LAND[1], s=LAND[2], rot=0, squash=sq,
                key=K(GUY, "b_stand", "shock" if t < T_LAND + 1.2 else "sad"))


FRIEDA_D = 200  # Kopf-Einheit bei Szenen-Skalierung 1.0
FEET = 2.867    # Füße liegen 2,867 D unter dem Nackenpunkt


@lru_cache(maxsize=8)
def basket(cuke):
    bk = Image.new("RGBA", (190, 190), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bk)
    bd.arc([30, 0, 160, 140], 180, 360, fill=(150, 95, 45), width=12)
    if cuke:
        rot_paste(bk, capsule(42, 150, (60, 150, 50), None), 110, 70, -28)
    rot_paste(bk, capsule(8, 110, (215, 218, 228), None), 50, 48, -20)
    paste_c(bk, sphere(22, (255, 150, 190), None, 0.5), 32, 2)
    paste_c(bk, sphere(62, (247, 140, 182), None, 0.35), 58, 82)
    bd.rounded_rectangle([10, 70, 180, 180], radius=24, fill=(196, 132, 64))
    for j in range(4):
        bd.line([(14, 92 + j * 24), (176, 92 + j * 24)], fill=(160, 100, 45), width=5)
    return bk


def frieda_state(t):
    """pose, expr, mouth, mirror, basket?"""
    m = round(speaking("fr0", t) * 0.8, 1)
    if T_GRAB <= t < T_THROW:
        return "oma_grab", "glare", 0.0, False, False
    if T_THROW <= t < T_FLY + 0.35:
        return "oma_throw", "strain", 0.0, False, False
    if T_CUKE - 0.15 <= t < T_CUKE + 0.45:
        return "oma_offer", "smile", 0.0, False, False
    if line_on("fr0", t, 0.2):
        return "oma_stand", "smile", m, False, True
    if line_on("frS", t, 0.3):
        return "oma_stand", "smirk", round(speaking("frS", t) * 0.8, 1), False, True
    if line_on("fr6", t, 0.3):
        return "oma_point", "smirk", round(speaking("fr6", t) * 0.8, 1), False, True
    if line_on("kas4", t, 0):
        return "oma_stand", "smirk", 0.0, False, True
    if T_GUY_IN0 + 1.0 < t < T_LINE["typ1"]:
        return "oma_stand", "neutral", 0.0, False, True
    if T_LINE["typ1"] <= t < T_GRAB:
        return "oma_stand", "warm", 0.0, False, True
    if T_FLY + 0.35 <= t < T_CUKE:
        return "oma_stand", "proud", 0.0, False, True
    return "oma_stand", "smile", 0.0, False, True


@lru_cache(maxsize=200)
def frieda_sprite(D, pose, expr, m, mirror=False, items=(), blink=False, wink=False, knit_phase=0.0, who="oma",
                  gl=0.03):
    im, (nx, ny), sc = fchars.person(who, D, pose, expr=expr, mouth=m, gl=gl, items=items, blink=blink,
                                     knit_phase=knit_phase)
    if wink:  # nur das (vom Betrachter aus) rechte Auge zu
        cl, _, _ = fchars.person(who, D, pose, expr=expr, mouth=m, gl=gl, items=items, blink=True,
                                 knit_phase=knit_phase)
        diff = np.abs(np.asarray(im).astype(np.int16) - np.asarray(cl).astype(np.int16)).sum(axis=2) > 6
        diff[:, : int(nx)] = False
        mask = Image.fromarray((diff * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9)).filter(
            ImageFilter.GaussianBlur(2))
        im = Image.composite(cl, im, mask)
    if abs(sc - 1) > 0.01:
        im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
        nx, ny = nx * sc, ny * sc
    if mirror:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
        nx = im.width - nx
    return im, nx, ny


def draw_frieda(frame, t, x, y, s, rot=0.0):
    pose, expr, m, mirror, has_basket = frieda_state(t)
    D = int(round(FRIEDA_D * s))
    im, nx, ny = frieda_sprite(D, pose, expr, m, mirror)
    feet_y = ny + FEET * D
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, center=(nx, feet_y))
    paste_c(frame, im, x - nx + im.width / 2, y - feet_y + im.height / 2)
    if has_basket:
        hx, hy = x - 0.6 * D, y - FEET * D + 1.3 * D
        paste_c(frame, basket(t < T_CUKE), hx - 6 * s, hy + 50 * s, scale=s * 0.95)


def frieda_rot(t):
    if T_GRAB + 0.35 <= t < T_FLY + 0.5:
        return 10 * math.sin(seg(t, T_GRAB + 0.35, T_FLY + 0.5) * math.pi)
    return 0.0


def clap_pose(t, i, kid=False):
    c = math.sin((t - T_CLAP0) * 16 + i * 1.3) > 0
    return ("kid_" if kid else "") + ("clap_b" if c else "clap_a")


def cash_key(t):
    m = max(speaking(l, t) for l in ("kas0", "kas2", "kas3", "kas4", "kas1"))
    if cards_on(t):
        return K("kasse", "b_hold", "laugh", 0.5)
    if T_CLAP0 < t < T_CLAP1:
        return K("kasse", clap_pose(t, 7), "laugh", 0.5)
    if line_on("kas0", t, 0):
        return K("kasse", "c_wave", "smile", m)
    if T_GRAB <= t < T_LAND:
        return K("kasse", "pass_shock", "shock", 0.8)
    if line_on("kas2", t, 0) or line_on("kas3", t, 0) or line_on("kas4", t, 0):
        return K("kasse", "b_stand", "warm", m)
    if T_LINE["typ0"] < t < T_GRAB:
        return K("kasse", "b_stand", "neutral", m)
    return K("kasse", "b_stand", "smile", m)


CARDS = {"pass1": "10", "pass2": "10", "girl": "9,5", "kasse": "10"}
MUSK_END = (935, 872, 0.36)


def cust_pos(who, x, y, s, t):
    if who != "musk1" or t < T_MUSK0:
        return x, y, s
    p = ease_io(seg(t, T_MUSK0, T_MUSK1))
    bob = abs(math.sin(t * 12)) * 10 * s if 0 < p < 1 else 0
    return lerp(x, MUSK_END[0], p), lerp(y, MUSK_END[1], p) - bob, lerp(s, MUSK_END[2], p)


def cards_on(t):
    return T_CARDS <= t < T_CARDS_END


def cust_key(who, t, i):
    kid = who in KIDS
    if who == "musk1":
        if T_GRAB < t < T_LAND:
            return K(who, "musk_shock", "shock", 0.8)
        if T_LAND <= t < T_BACK1A:
            return K(who, "b_stand", "scared", speaking("mk1", t))
        if t >= T_BACK1A:
            return K(who, "b_stand", "sad")
    if who in CARDS and cards_on(t):
        return K(who, "kid_reach" if kid else "b_hold", "laugh", 0.5)
    if who == "pass1" and line_on("k2a", t, 0.3):
        return K(who, "b_point", "glare", speaking("k2a", t))
    if T_GRAB < t < T_LAND:
        return K(who, "kid_cheer" if kid else "pass_shock", "shock", 0.8)
    if T_CLAP0 + i * 0.05 < t < T_CLAP1:
        return K(who, clap_pose(t, i, kid), "laugh", 0.5)
    if T_GUY_IN1 < t < T_GRAB:
        return K(who, None, "sad" if kid else "glare")
    if who == "pass2" and t >= T_LAND:
        return K(who, None, "smirk")
    return K(who, None, "neutral")


# ------------------------------------------------------------------ camera (world shots)
CAM_KEYS = [  # t, zoom, cx, cy
    (0.0, 1.0, 540, 1150), (1.5, 1.0, 540, 1150), (3.4, 1.12, 480, 1360), (6.0, 1.12, 480, 1360),
    (6.9, 1.1, 760, 1320), (9.3, 1.16, 470, 1360), (12.0, 1.16, 470, 1360), (13.8, 1.22, 450, 1330),
    (14.6, 1.42, 450, 1260),
    (T_CONF_B, 1.32, 400, 1260), (T_CONF_B + 1.35, 1.0, 560, 1100), (T_SLOW_END, 1.0, 560, 1100),
    (T_BACK1A, 1.0, 560, 1100), (T_BACK1B, 1.22, 420, 1380), (T_FLASH_A, 1.28, 400, 1360),
    (T_FLASH_B, 1.12, 470, 1330), (T_CUKE + 0.7, 1.22, 380, 1400), (T_CLOSE2A, 1.3, 360, 1380),
]


def camera(t):
    for (t0, z0, x0, y0), (t1, z1, x1, y1) in zip(CAM_KEYS, CAM_KEYS[1:]):
        if t0 <= t < t1:
            p = ease_io(seg(t, t0, t1))
            z, cx, cy = lerp(z0, z1, p), lerp(x0, x1, p), lerp(y0, y1, p)
            break
    else:
        _, z, cx, cy = CAM_KEYS[-1]
    hw, hh = W / (2 * z), H / (2 * z)
    return z, min(max(cx, hw), W - hw), min(max(cy, hh), H - hh)


def to_screen(cam, x, y):
    z, cx, cy = cam
    return (x - cx) * z + W / 2, (y - cy) * z + H / 2


# ------------------------------------------------------------------ extra UI
@lru_cache(maxsize=4)
def stamp(text, size, col):
    im = text_img(text, size, col, F_BLACK, stroke=int(size * 0.13), stroke_fill=(30, 26, 40), max_w=1000)
    return im.rotate(-8, resample=Image.BICUBIC, expand=True)


def bubble_at(frame, lid, text, ax, ay, t, size=62):
    """Sprechblase über einem Kopf (Bildschirm-Koordinaten), innerhalb der TikTok-Safe-Zone."""
    b = bubble(text, "left", size)
    bw = b.width
    x = min(max(ax + bw * 0.5 - 70, bw / 2 + 30), W - bw / 2 - 110)
    tail = "left" if ax < x else "right"
    if tail == "right":
        x = min(max(ax - bw * 0.5 + 70, bw / 2 + 30), W - bw / 2 - 110)
    y = max(ay - b.height / 2 - 10, 260)
    t0 = T_LINE[lid] - 0.08
    t1 = t0 + LINES[lid]["speech"] + 0.5
    if not (t0 <= t <= t1):
        return
    p = ease_back(seg(t, t0, t0 + 0.22))
    a = 1 - seg(t, t1 - 0.15, t1)
    paste_c(frame, bubble(text, tail, size), x, y, scale=max(0.05, p), alpha=a)


TEXT = {l: LINES[l].get("display", LINES[l]["text"]).replace(" … ", "… ") for l in LINES}


# ------------------------------------------------------------------ Gags: Wertungstafel, Energy-Drink
@lru_cache(maxsize=8)
def score_card(txt):
    im = Image.new("RGBA", (190, 250), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([86, 120, 104, 250], radius=6, fill=(150, 110, 70))
    d.rounded_rectangle([8, 14, 182, 150], radius=16, fill=(30, 26, 40))
    d.rounded_rectangle([2, 6, 176, 142], radius=16, fill=(255, 255, 255), outline=(30, 26, 40), width=6)
    d.text((89, 76), txt, font=font(F_BLACK, 78 if len(txt) < 3 else 60), fill=(220, 40, 50), anchor="mm")
    return im


def frieda_hand_r(fx, s=FRIEDA[2]):
    D = FRIEDA_D * s
    return fx + 0.6 * D, FRIEDA[1] - FEET * D + 1.25 * D


def can_draw(frame, t, fx):
    """Die Dose fliegt beim Wurf weg, Frieda fängt sie blind – später kommt sie aufs Band."""
    if t < T_GRAB or t >= T_CUKE + 6:
        return
    D = SER_D * GUY_SPOT[2]
    c = can_sprite(int(D))
    if t < T_CATCH:
        p = seg(t, T_GRAB, T_CATCH)
        x0, y0 = GUY_SPOT[0] - 0.58 * D, GUY_SPOT[1] - 2.9 * D + 1.18 * D
        x1, y1 = frieda_hand_r(FRIEDA[0])
        x = lerp(x0, x1, p)
        y = (1 - p) ** 2 * y0 + 2 * (1 - p) * p * 420 + p ** 2 * (y1 - 0.12 * D)
        rot_paste(frame, c, x, y, p * 900)
    elif t < T_CUKE:
        pose = frieda_state(t)[0]
        if pose == "oma_stand":
            x, y = frieda_hand_r(fx)
            paste_c(frame, c, x, y - 0.12 * D)
    else:
        p = ease_io(seg(t, T_CUKE, T_CUKE + 0.45))
        x0, y0 = frieda_hand_r(fx)
        x = lerp(x0, 680, p) - max(0.0, t - T_CUKE - 0.5) * 140
        y = lerp(y0, 1610, p) - math.sin(p * math.pi) * 70
        if x > 200:
            rot_paste(frame, c, x, y, lerp(0, 90, p) if p < 1 else 90)


# ------------------------------------------------------------------ world shot
def world(t, with_guy=True):
    frame = background().copy()
    gs = guy_state(t) if with_guy else None
    flying = gs is not None and (T_GRAB + 0.2 <= t < T_LAND)
    items = []
    for i, (who, x, y, s) in enumerate(QUEUE):
        x, y, s = cust_pos(who, x, y, s, t)
        items.append((y, ("c", who, x, y, s, i)))
    if gs and not flying:
        items.append((gs["y"], ("g",)))
    items.append((CASH[1], ("cash",)))
    items.append((FRIEDA[1], ("frieda",)))
    k0 = k0_state(t)
    if k0:
        items.append((k0[1], ("k0",)))
    items.sort(key=lambda z: z[0])
    fx = FRIEDA[0] - 40 * ease_io(seg(t, T_CUKE - 0.3, T_CUKE + 0.2))
    for _, it in items:
        if it[0] == "c":
            _, who, x, y, s, i = it
            hop = abs(math.sin((t - T_CLAP0) * 9 + i)) * 10 * s if T_CLAP0 < t < T_CLAP1 else 0
            draw_series(frame, cust_key(who, t, i), x, y - hop, s)
        elif it[0] == "g":
            draw_series(frame, gs["key"], gs["x"], gs["y"], gs["s"], gs["rot"], squash=gs.get("squash", 1.0))
        elif it[0] == "cash":
            draw_series(frame, cash_key(t), *CASH)
        elif it[0] == "k0":
            draw_series(frame, k0[3], k0[0], k0[1], k0[2])
        else:
            draw_frieda(frame, t, fx, FRIEDA[1], FRIEDA[2], frieda_rot(t))
    # Wertungstafeln wie bei Olympia
    if cards_on(t):
        holders = [(w, x, y, s) for (w, x, y, s) in QUEUE if w in CARDS] + [("kasse",) + CASH]
        for k, (w, x, y, s) in enumerate(holders):
            q = ease_back(seg(t, T_CARDS + k * 0.12, T_CARDS + k * 0.12 + 0.3))
            if q <= 0.02:
                continue
            D = SER_D * s
            kid = w in KIDS
            hx = x + (0.95 if kid else 0.8) * D
            hy = y - (2.25 if kid else 2.9) * D + (-0.25 if kid else -0.55) * D
            paste_c(frame, score_card(CARDS[w]), hx, hy - 0.75 * D, scale=max(0.05, q * max(s, 0.62) * 1.35),
                    rot=4 * math.sin(t * 3 + k))
    draw_counter(frame, t)
    can_draw(frame, t, fx)
    if t >= T_CUKE:
        p = ease_io(seg(t, T_CUKE, T_CUKE + 0.4))
        x = lerp(fx - 220, 600, p)
        y = lerp(1500, 1640, p) - math.sin(p * math.pi) * 90
        x -= max(0.0, t - T_CUKE - 0.5) * 140
        rot_paste(frame, capsule(42, 150, (60, 150, 50), None), max(x, 200), y, lerp(-28, 90, p))
    if gs and flying:
        if gs.get("trail"):
            for k in (3, 2, 1):
                g2 = guy_state(t - k * 0.05)
                if g2:
                    draw_series(frame, g2["key"], g2["x"], g2["y"], g2["s"], g2["rot"], alpha=0.12 * (4 - k))
        draw_series(frame, gs["key"], gs["x"], gs["y"], gs["s"], gs["rot"])
    return frame, gs


def world_shot(t):
    frame, gs = world(t)
    cam = camera(t)
    z, cx, cy = cam
    shake = 0
    if T_LAND <= t < T_LAND + 0.3:
        shake = 12 * (1 - seg(t, T_LAND, T_LAND + 0.3))
    frame = zoom_frame(frame, z, cx + math.sin(t * 90) * shake, cy + math.cos(t * 70) * shake)
    slow = seg(t, T_GRAB, T_GRAB + 0.15) * (1 - seg(t, T_SLOW_END - 0.15, T_SLOW_END))
    tense = seg(t, T_PUSH, T_PUSH + 0.3)
    frame = grade(frame, max(slow * 0.9, tense * 0.5 * (t < T_GRAB)))
    speed_lines(frame, t, slow * seg(t, T_THROW, T_FLY))
    if slow > 0.02:
        paste_c(frame, slowmo_badge(), 540, 330, scale=0.6 + 0.4 * ease_back(seg(t, T_GRAB, T_GRAB + 0.25)),
                alpha=slow * (0.75 + 0.25 * (int(t * 4) % 2)))
    ipp_end = T_IPPON_END if T_IPPON_END else T_CARDS + 0.7
    if T_IPPON <= t < ipp_end:
        q = seg(t, T_IPPON, T_IPPON + 0.25)
        a = 1 - seg(t, ipp_end - 0.35, ipp_end)
        paste_c(frame, stamp("IPPON!", 190, (255, 70, 70)), 540, 560, scale=2.2 - 1.2 * ease_out(q), alpha=a)
    if T_CLAP0 < t < T_CLAP1 + 0.4:
        rng = random.Random(3)
        for i in range(5):
            t0 = T_CLAP0 + rng.uniform(0, 1.2)
            q = seg(t, t0, t0 + 0.9)
            if 0 < q < 1:
                paste_c(frame, emoji("👏", 110), rng.uniform(160, 880), rng.uniform(900, 1400) - q * 300,
                        alpha=math.sin(q * math.pi), rot=rng.uniform(-20, 20))
    if t < T_TITLE_END:
        a = 1 - seg(t, T_TITLE_END - 0.3, T_TITLE_END)
        paste_c(frame, title_full(), 540, 330, scale=max(0.05, ease_back(seg(t, 0.1, 0.45))), alpha=a)

    def head(x, y, s, who="adult", frieda=False):
        if frieda:
            return to_screen(cam, x, y - (FEET * FRIEDA_D * s + 1.35 * FRIEDA_D * s))
        return to_screen(cam, *head_top(x, y, s, who))
    sp = {"kas0": head(*CASH), "kas2": head(*CASH), "kas3": head(*CASH), "kas1": head(*CASH),
          "kas4": head(*CASH), "fr0": head(*FRIEDA, frieda=True), "fr6": head(*FRIEDA, frieda=True),
          "k2a": head(*QUEUE[0][1:]), "mk1": head(*cust_pos("musk1", *QUEUE[1][1:], t))}
    if gs:
        sp["typ0"] = sp["typ1"] = sp["typ1b"] = sp["typL"] = head(gs["x"], gs["y"], gs["s"])
    sp["frS"] = head(*FRIEDA, frieda=True)
    sizes = {"typ1": 54, "typ1b": 52, "typL": 52, "frS": 96, "typ0": 52, "k2a": 58, "kas3": 58, "mk1": 50}
    for lid, (ax, ay) in sp.items():
        bubble_at(frame, lid, TEXT[lid], ax, ay, t, sizes.get(lid, 62))
    return frame


# ------------------------------------------------------------------ close-ups
@lru_cache(maxsize=6)
def blurred_world(t, z, cx, cy, blur=18, with_guy=True):
    f, _ = world(t, with_guy)
    return zoom_frame(f, z, cx, cy).filter(ImageFilter.GaussianBlur(blur))


def flash(frame, t, t0, dur=0.12):
    fl = 1 - seg(t, t0, t0 + dur)
    if fl > 0:
        frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * fl))))


def red_tension(frame, amt):
    if amt <= 0.01:
        return frame
    arr = np.asarray(frame.convert("RGB")).astype(np.float32)
    arr = arr * (1 - 0.25 * amt) + np.array((150, 20, 30)) * 0.25 * amt
    arr = arr * (1 - vign()[..., None] * 1.4 * amt)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")


CONF_SHOTS = []  # (t0, t1, wer, Zeile) – wird unten aus T_LINE gebaut


def conf_shot(t):
    """Schuss/Gegenschuss: Frieda <-> Drängler, bevor sie ihn wirft."""
    for t0, t1, who, lid in CONF_SHOTS:
        if t0 <= t < t1:
            break
    p = seg(t, t0, t1)
    if who == "frieda":
        frame = blurred_world(5.0, 1.45, 560, 1250, 18, False).copy()
        expr = {"fr1": "warm", "fr4": "glare", "fr5": "smirk", "fr1b": "neutral", "fr7": "smirk"}.get(lid, "warm")
        m = round(speaking(lid, t) * 0.8, 1)
        gl = 0.12 if (lid == "fr5" and t > T_LINE["fr5"] + 0.6) else 0.03   # Brillen-Blitzer
        im, nx, ny = frieda_sprite(470, "oma_stand", expr, m, gl=gl)
        s = lerp(1.0, 1.06, p) if lid != "fr5" else lerp(1.0, 1.16, ease_in(p))
        im = im.resize((int(im.width * s), int(im.height * s)), Image.BICUBIC)
        nx, ny = nx * s, ny * s
        paste_c(frame, im, 560 - nx + im.width / 2, 1010 - ny + im.height / 2)
        bubble_at(frame, lid, TEXT[lid], 420, 470, t, {"fr4": 70, "fr7": 62, "fr1b": 74}.get(lid, 84))
        frame = grade(frame, 0.35)
        if lid == "fr5":
            frame = red_tension(frame, 0.5 * p)
    else:
        frame = blurred_world(5.0, 1.45, 330, 1250, 18, False).copy()
        if lid in ("typ2", "typ2b", "typ6"):
            key = K(GUY, "g_film" if GUY_LIVE else "g_shrug", "smirk", speaking(lid, t), shades=True, can=True,
                    phone=GUY_LIVE)
            s, rot = lerp(1.0, 1.05, p), 0
        else:  # Brille ab, Faust, beugt sich bedrohlich vor
            key = K(GUY, "b_hold", "glare", speaking(lid, t))
            s = lerp(1.05, 1.32, ease_io(p))
            rot = -4 * ease_io(p)
        D = 470
        im, nx, ny, _ = series_sprite(key, D)
        im = im.resize((int(im.width * s), int(im.height * s)), Image.BICUBIC)
        nx, ny = nx * s, ny * s
        if rot:
            im = im.rotate(rot, resample=Image.BICUBIC, center=(nx, ny))
        shake = 6 * math.sin(t * 60) * p if lid == "typ5" else 0
        paste_c(frame, im, 520 - nx + im.width / 2 + shake, 1050 - ny + im.height / 2)
        bubble_at(frame, lid, TEXT[lid], 560, 430, t, 92 if lid == "typ5" else 64)
        frame = grade(frame, 0.35)
        if lid == "typ5":
            frame = red_tension(frame, 0.3 + 0.6 * p)
    flash(frame, t, t0, 0.06)
    return frame


def closeup_end(t):
    frame = blurred_world(T_CUKE + 2.0, 1.5, 520, 1250).copy()
    p = ease_out(seg(t, T_CLOSE, T_CLOSE + 0.5))
    m = speaking("fr2", t)
    wink = T_WINK - 0.05 <= t < T_WINK + 0.45
    expr = "smirk" if t >= T_WINK - 0.05 else "smile"
    D = 430
    im, nx, ny = frieda_sprite(D, "oma_knit_stand", expr, round(m * 0.8, 1), False, (("knit", (0.0, 1.1)),),
                               False, wink, round((t * 1.5) % 1, 1))
    s = lerp(1.08, 1.0, p)
    if abs(s - 1) > 0.005:
        im = im.resize((int(im.width * s), int(im.height * s)), Image.BICUBIC)
        nx, ny = nx * s, ny * s
    im = im.rotate(lerp(-4, 0, p), resample=Image.BICUBIC, center=(nx, ny + 3 * D))
    paste_c(frame, im, 540 - nx + im.width / 2, 860 + 40 * (1 - p) - ny + im.height / 2)
    if wink:
        q = seg(t, T_WINK, T_WINK + 0.45)
        paste_c(frame, emoji("✨", int(130 + 60 * math.sin(q * math.pi))), 770, 610, alpha=math.sin(q * math.pi))
    bubble_at(frame, "fr2", TEXT["fr2"], 420, 470, t, 84)
    if t >= T_END_TXT:
        q = ease_back(seg(t, T_END_TXT, T_END_TXT + 0.35))
        paste_c(frame, end_text(), 540, 1430, scale=max(0.05, q))
    flash(frame, t, T_CLOSE if t < T_BACK2A else T_BACK2B)
    return frame


# ------------------------------------------------------------------ Ende der Schlange
def back_shot(t):
    frame = blurred_world(T_BACK1A + 1.5, 2.2, 700, 790, 14, False).copy()
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([120, 1850, 980, 1990], fill=(60, 40, 60, 70))
    frame.alpha_composite(sh.filter(ImageFilter.GaussianBlur(30)))
    second = t >= T_BACK2A
    m3 = speaking("k3a", t)
    k3 = K("pass2", "b_point" if line_on("k3a", t, 0) else "b_stand", "smirk", m3, mirror=True)
    draw_series(frame, k3, 320, 2050, 1.75)
    mt = max(speaking("typ3", t), speaking("typ4", t), speaking("typ7", t))
    if second:
        key, wob = K(GUY, "g_film" if GUY_LIVE else "g_phone", "scared" if t > T_LINE["tel"] else "sad", mt, phone=True), 0
    else:
        key, wob = K(GUY, "b_stand", "shock" if mt < 0.05 else "scared", mt), 4 * math.sin(t * 5)
    draw_series(frame, key, 770, 2080, 1.75, rot=wob)
    if not second:
        for i in range(4):
            a = t * 4 + i * math.tau / 4
            paste_c(frame, emoji("⭐", 60), 770 + math.cos(a) * 130, 700 + math.sin(a) * 30)
    bubble_at(frame, "k3a", TEXT["k3a"], 320, 760, t, 62)
    bubble_at(frame, "typ3", TEXT["typ3"], 770, 660, t, 66)
    bubble_at(frame, "typ4", TEXT["typ4"], 770, 660, t, 66)
    bubble_at(frame, "typ7", TEXT["typ7"], 770, 660, t, 64)
    bubble_at(frame, "tel", "📱 " + TEXT["tel"] if False else TEXT["tel"], 820, 620, t, 70)
    flash(frame, t, T_BACK1A if not second else T_BACK2A, 0.08)
    return frame


# ------------------------------------------------------------------ Rückblende 1974
@lru_cache(maxsize=1)
def dojo_bg():
    img = gradient(W, H, (236, 222, 190), (200, 170, 120))
    d = ImageDraw.Draw(img)
    for i in range(0, W, 120):  # Holzwand
        d.line([(i, 0), (i, 1100)], fill=(190, 150, 100), width=4)
    d.rectangle([0, 1100, W, H], fill=(120, 150, 90))
    for r in range(6):  # Tatami
        y0 = 1100 + r * 140
        for c in range(-1, 6):
            x0 = c * 260 + (130 if r % 2 else 0)
            d.rounded_rectangle([x0 + 6, y0 + 6, x0 + 254, y0 + 134], radius=10,
                                fill=(150, 170, 90) if (r + c) % 2 else (196, 186, 110))
    ban = capsule(860, 170, (200, 40, 40), None, radius=30)
    paste_c(img, ban, 540, 330)
    d.text((540, 300), "DEUTSCHE MEISTERSCHAFT", font=font(F_BLACK, 46), fill=(255, 240, 220), anchor="mm")
    d.text((540, 362), "JUDO · DAMEN · 1974", font=font(F_BLACK, 40), fill=(255, 210, 90), anchor="mm")
    return img


def sepia(frame, amt=1.0, t=0.0):
    arr = np.asarray(frame.convert("RGB")).astype(np.float32)
    lum = arr @ np.array([0.3, 0.59, 0.11], np.float32)
    sep = np.stack([lum * 1.07 + 20, lum * 0.92 + 10, lum * 0.72], axis=2)
    arr = arr * (1 - amt) + sep * amt
    rng = np.random.default_rng(int(t * 30))
    arr += rng.normal(0, 10, arr.shape[:2])[..., None] * amt
    arr = arr * (1 - vign()[..., None] * 1.3 * amt)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")


def flashback(t):
    p = seg(t, T_FLASH_A, T_FLASH_B)
    frame = dojo_bg().copy()
    # Publikum unten
    rng = random.Random(11)
    for i in range(9):
        x = 60 + i * 120 + rng.uniform(-20, 20)
        up = abs(math.sin(t * 8 + i)) * 30
        paste_c(frame, sphere(150, (90, 70, 60), None, 0.2), x, 1900 - up)
        paste_c(frame, capsule(46, 160, (90, 70, 60), None), x + 70, 1760 - up, rot=-20)
    im, nx, ny = frieda_sprite(250, "young_trophy", "laugh", round(abs(math.sin(t * 6)) * 0.4, 1), False,
                               (("trophy", (0.7, -0.55)),), who="young")
    z = lerp(1.0, 1.1, ease_io(p))
    im = im.resize((int(im.width * z), int(im.height * z)), Image.BICUBIC)
    paste_c(frame, im, 520 - nx * z + im.width / 2, 1010 - ny * z + im.height / 2)
    # Konfetti
    for i in range(40):
        r2 = random.Random(i)
        x = r2.uniform(0, W)
        y = (r2.uniform(-400, 1900) + (t - T_FLASH_A) * r2.uniform(180, 320)) % 2000 - 80
        ImageDraw.Draw(frame).rectangle([x, y, x + 16, y + 9], fill=r2.choice([(255, 220, 80), (240, 80, 80),
                                                                               (255, 255, 255)]))
    frame = sepia(frame, 0.85, t)
    # Kamerablitze
    for tb in (T_FLASH_A + 0.5, T_FLASH_A + 1.9, T_FLASH_A + 3.1):
        fl = 1 - seg(t, tb, tb + 0.15)
        if 0 < fl < 1:
            frame.alpha_composite(Image.new("RGBA", (W, H), (255, 250, 235, int(170 * fl))))
    # Stempel "1974"
    if t > T_FLASH_A + 0.4:
        q = seg(t, T_FLASH_A + 0.4, T_FLASH_A + 0.65)
        paste_c(frame, stamp("1974", 170, (255, 214, 60)), 540, 1560, scale=2.0 - ease_out(q), alpha=1)
    bubble_at(frame, "fr3", TEXT["fr3"], 300, 560, t, 56)
    # weiche Ein-/Ausblendung
    a_in = 1 - seg(t, T_FLASH_A, T_FLASH_A + 0.25)
    a_out = seg(t, T_FLASH_B - 0.25, T_FLASH_B)
    fl = max(a_in, a_out)
    if fl > 0:
        frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * fl))))
    return frame


# ------------------------------------------------------------------ dispatcher
CONF_SHOTS[:] = [
    (T_CONF_A, T_LINE["typ2"] - 0.15, "frieda", "fr1"),
    (T_LINE["typ2"] - 0.15, T_LINE["fr4"] - 0.2, "typ", "typ2"),
    (T_LINE["fr4"] - 0.2, T_LINE["typ5"] - 0.25, "frieda", "fr4"),
    (T_LINE["typ5"] - 0.25, T_LINE["fr5"] - 0.2, "typ", "typ5"),
    (T_LINE["fr5"] - 0.2, T_CONF_B, "frieda", "fr5"),
]


def render_frame(fi):
    t = fi / FPS
    if T_CONF_A <= t < T_CONF_B:
        return conf_shot(t)
    if T_BACK1A <= t < T_BACK1B or T_BACK2A <= t < T_BACK2B:
        return back_shot(t)
    if T_FLASH_A <= t < T_FLASH_B:
        return flashback(t)
    if t >= T_CLOSE:
        return closeup_end(t)
    f = world_shot(t)
    if t >= T_CONF_B:
        flash(f, t, T_CONF_B, 0.1)
    if T_BACK1B <= t:
        flash(f, t, T_BACK1B, 0.08)
    if T_FLASH_B <= t:
        flash(f, t, T_FLASH_B, 0.2)
    return f


def _rgb(fi):
    return np.asarray(render_frame(fi).convert("RGB")).tobytes()


# ------------------------------------------------------------------ UI elements
@lru_cache(maxsize=32)
def bubble(text, tail="left", size=62, max_w=780):
    f = font(F_INTER, size)
    words, lines, cur = text.split(), [], ""
    for w in words:
        tt = (cur + " " + w).strip()
        if cur and f.getlength(tt) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = tt
    lines.append(cur)
    tw = max(f.getlength(l) for l in lines)
    lh = size * 1.18
    pw, ph = int(tw + 80), int(size * 0.55 + lh * len(lines))
    rad = min(ph / 2, size * 0.85)
    im = Image.new("RGBA", (pw + 20, ph + 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([10, 14, pw + 10, ph + 14], radius=rad, fill=(30, 26, 40))
    d.rounded_rectangle([4, 4, pw + 4, ph + 4], radius=rad, fill=(255, 255, 255), outline=(30, 26, 40), width=6)
    tx = 70 if tail == "left" else pw - 70
    d.polygon([(tx - 26, ph), (tx + 26, ph), (tx + (-30 if tail == "left" else 30), ph + 58)], fill=(255, 255, 255))
    d.line([(tx - 26, ph + 2), (tx + (-30 if tail == "left" else 30), ph + 58), (tx + 26, ph + 2)], fill=(30, 26, 40),
           width=6)
    for k, l in enumerate(lines):
        d.text((pw / 2 + 4, 4 + ph / 2 + (k - (len(lines) - 1) / 2) * lh), l, font=f, fill=(30, 26, 40), anchor="mm")
    return im


def draw_bubble(frame, lid, text, x, y, t, tail="left", size=62):
    t0 = T_LINE[lid] - 0.08
    t1 = t0 + LINES[lid]["speech"] + 0.5
    if not (t0 <= t <= t1):
        return
    p = ease_back(seg(t, t0, t0 + 0.22))
    a = 1 - seg(t, t1 - 0.15, t1)
    paste_c(frame, bubble(text, tail, size), x, y, scale=max(0.05, p), alpha=a)


@lru_cache(maxsize=8)
def title_img(text, size, col=(255, 255, 255), stroke=(30, 26, 40)):
    return text_img(text, size, col, F_BLACK, stroke=int(size * 0.16), stroke_fill=stroke, max_w=1000)


@lru_cache(maxsize=1)
def title_full():
    t = title_img("Frieda geht einkaufen", 76)
    e = emoji("🛒", 96)
    im = Image.new("RGBA", (t.width + e.width + 10, max(t.height, e.height) + 10), (0, 0, 0, 0))
    im.alpha_composite(t, (0, (im.height - t.height) // 2))
    im.alpha_composite(e, (t.width - 10, (im.height - e.height) // 2))
    return im


@lru_cache(maxsize=1)
def slowmo_badge():
    im = Image.new("RGBA", (420, 110), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, 419, 109], radius=55, fill=(30, 26, 40))
    d.ellipse([34, 36, 72, 74], fill=(255, 60, 70))
    d.text((240, 56), "ZEITLUPE", font=font(F_BLACK, 50), fill=(255, 255, 255), anchor="mm")
    return im


def speed_lines(frame, t, amt):
    if amt <= 0.01:
        return
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    rng = random.Random(int(t * 30))
    for _ in range(26):
        a = rng.uniform(0, math.tau)
        r0 = rng.uniform(620, 760)
        r1 = r0 + rng.uniform(260, 520)
        cx, cy = 560, 1000
        d.line([(cx + math.cos(a) * r0, cy + math.sin(a) * r0 * 1.5),
                (cx + math.cos(a) * r1, cy + math.sin(a) * r1 * 1.5)],
               fill=(255, 255, 255, int(170 * amt)), width=rng.randint(4, 10))
    frame.alpha_composite(ov)


def grade(frame, amt):
    """Cool slow-motion grade + vignette."""
    if amt <= 0.01:
        return frame
    arr = np.asarray(frame.convert("RGB")).astype(np.float32)
    lum = arr.mean(axis=2, keepdims=True)
    arr = arr * (1 - 0.35 * amt) + lum * 0.35 * amt
    arr = arr * (1 - 0.12 * amt) + np.array((70, 90, 200)) * 0.12 * amt
    v = vign()
    arr = arr * (1 - v[..., None] * amt)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")


@lru_cache(maxsize=1)
def vign():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.7)) ** 2)
    return np.clip((v - 0.6) * 1.2, 0, 0.6)


@lru_cache(maxsize=1)
@lru_cache(maxsize=1)
def end_text():
    return text_img("Das ist Frieda.", 118, (255, 214, 60), F_BLACK, stroke=18, stroke_fill=(30, 26, 40),
                    max_w=1000)


# ------------------------------------------------------------------ audio
def tone(f, dur, a=0.005, dcy=0.25, kind="sin", f_end=None):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    fr = f if f_end is None else np.linspace(f, f_end, n)
    ph = 2 * np.pi * np.cumsum(np.full(n, fr) if np.isscalar(fr) else fr) / SR
    w = np.sin(ph) if kind == "sin" else (2 * (ph / (2 * np.pi) % 1) - 1)
    env = np.minimum(1, tt / a) * np.exp(-tt / dcy)
    return w * env


def ssum(*sigs):
    out = np.zeros(max(len(x) for x in sigs))
    for x in sigs:
        out[:len(x)] += x
    return out


def lowpass(x, alpha):
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += alpha * (x[i] - acc)
        y[i] = acc
    return y


def lp_fast(x, k):
    ker = np.ones(k) / k
    return np.convolve(x, ker, mode="same")


def build_audio(path):
    import wave
    n = int(TOTAL * SR)
    mix = np.zeros(n)
    rng = np.random.default_rng(5)
    tt = np.arange(n) / SR

    def add(sig, t0, g=1.0):
        i = int(t0 * SR)
        if i >= n or i + len(sig) <= 0:
            return
        if i < 0:
            sig, i = sig[-i:], 0
        j = min(n, i + len(sig))
        mix[i:j] += sig[: j - i] * g

    def noise(dur):
        return rng.standard_normal(int(dur * SR))

    def env_win(a, b, fade=0.15):
        return np.clip((tt - a) / fade, 0, 1) * np.clip((b - tt) / fade, 0, 1)

    # --- Musik: fröhlicher Pluck-Loop, 128 bpm
    beat = 60 / 128
    music = np.zeros(n)
    mel = [72, 76, 79, 76, 74, 77, 81, 77, 72, 76, 79, 84, 83, 79, 77, 74]
    bass = [48, 48, 53, 53, 55, 55, 48, 48]
    k, tb = 0, 0.0
    while tb < TOTAL:
        i = int(tb * SR)

        def put(sig, g):
            j = min(n, i + len(sig))
            music[i:j] += sig[: j - i] * g
        f = 440 * 2 ** ((mel[k % 16] - 69) / 12)
        put(ssum(tone(f, 0.35, 0.003, 0.12), 0.3 * tone(f * 2, 0.2, 0.003, 0.06)), 0.16)
        if k % 2 == 0:
            fb = 440 * 2 ** ((bass[(k // 2) % 8] - 69) / 12)
            put(tone(fb, 0.4, 0.004, 0.18), 0.22)
            put(tone(110, 0.15, 0.001, 0.05, f_end=45), 0.35)
        else:
            hh = rng.standard_normal(int(0.05 * SR)) * np.exp(-np.arange(int(0.05 * SR)) / (0.01 * SR))
            put(np.diff(hh, prepend=0), 0.05)
        k += 1
        tb += beat / 2
    on = np.ones(n)
    on *= 1 - env_win(T_PUSH, T_LAND + 0.15, 0.12)          # Spannung + Zeitlupe: Musik weg
    on *= 1 - env_win(T_FLASH_A - 0.1, T_FLASH_B, 0.2)      # Rückblende: eigene Atmo
    duck = np.ones(n)
    for lid in LINES:
        t0 = T_LINE[lid]
        duck *= 1 - 0.55 * env_win(t0 - 0.1, t0 + LINES[lid]["speech"] + 0.15, 0.1)
    on *= np.clip((TOTAL - tt) / 0.8, 0, 1)
    mix += music * on * duck

    # --- Supermarkt-Atmo
    amb = lp_fast(rng.standard_normal(n), 60) * 0.25 + 0.01 * np.sin(2 * np.pi * 100 * tt)
    amb *= 1 - env_win(T_FLASH_A, T_FLASH_B, 0.2)
    mix += amb * 0.35
    for tb in (-1.9, -1.2, -0.6):
        add(tone(1900, 0.12, 0.002, 0.05), T_K0_LEAVE + tb, 0.12)     # Kunde vor Frieda wird abkassiert
    add(tone(1400, 0.08, 0.002, 0.04), T_K0_LEAVE - 0.55, 0.08)

    # --- Schritte
    for tb in np.arange(T_K0_LEAVE, T_K0_LEAVE + 1.5, 0.23):
        add(lp_fast(noise(0.06), 8) * np.exp(-np.arange(int(0.06 * SR)) / 600), tb, 0.35)
    for tb in np.arange(T_GUY_IN0, T_GUY_IN1, 0.24):
        add(lp_fast(noise(0.06), 8) * np.exp(-np.arange(int(0.06 * SR)) / 600), tb, 0.5)
    add(tone(2600, 0.05, 0.001, 0.01), T_GUY_IN1, 0.2)   # Dose klackt
    # Empörtes Raunen
    add(lp_fast(noise(0.9), 40) * np.sin(np.linspace(0, np.pi, int(0.9 * SR))), T_LINE["k2a"] - 0.5, 0.6)

    # --- Spannung: "Dun-dun" + Drone
    add(ssum(tone(98, 0.9, 0.005, 0.5), tone(196, 0.6, 0.005, 0.3) * 0.4), T_PUSH, 0.5)
    add(ssum(tone(92, 1.0, 0.005, 0.6), tone(184, 0.6, 0.005, 0.3) * 0.4), T_PUSH + 0.45, 0.5)
    L = int((T_GRAB - T_PUSH) * SR)
    add(np.sin(2 * np.pi * 55 * np.arange(L) / SR) * np.linspace(0, 1, L) * 0.3, T_PUSH, 0.4)
    for c0, _, _, _ in CONF_SHOTS:  # Schnitt-Whoosh je Einstellung
        add(lp_fast(noise(0.2), 6) * np.linspace(0, 1, int(0.2 * SR)), c0 - 0.15, 0.15)
    for tb in np.arange(T_CONF_A + 0.3, T_GRAB - 0.2, 0.85):  # Herzschlag
        add(tone(55, 0.18, 0.004, 0.08), tb, 0.55)
        add(tone(50, 0.18, 0.004, 0.08), tb + 0.22, 0.4)
    add(tone(1200, 0.06, 0.001, 0.02), T_LINE["typ5"] - 0.2, 0.25)            # Brille ab: Klick
    add(ssum(tone(70, 0.9, 0.004, 0.5), tone(140, 0.5, 0.004, 0.3) * 0.4), T_LINE["typ5"] - 0.2, 0.6)
    add(ssum(tone(2637, 0.5, 0.002, 0.25), 0.5 * tone(3520, 0.4, 0.002, 0.2)), T_LINE["fr5"] + 0.6, 0.12)  # Blitzer

    # --- Zeitlupe: Griff, Schwung, Flug, Landung
    add(tone(80, 0.5, 0.002, 0.3, f_end=40), T_GRAB, 0.6)
    add(lp_fast(noise(0.12), 4) * np.exp(-np.arange(int(0.12 * SR)) / 1500), T_GRAB + 0.32, 0.6)
    L = int((T_LAND - T_THROW) * SR)
    add(lp_fast(rng.standard_normal(L), 25) * np.sin(np.linspace(0, np.pi, L)) ** 1.5 * 3.0, T_THROW, 0.9)
    add(tone(60, 0.25, 0.005, 0.12), T_GRAB + 0.1, 0.5)
    add(tone(60, 0.25, 0.005, 0.12), T_FLY + 0.4, 0.5)
    add(tone(60, 0.25, 0.005, 0.12), T_FLY + 1.2, 0.5)
    add(tone(300, 1.4, 0.05, 0.8, f_end=110) * 0.3, T_FLY, 0.4)
    bo = tone(220, 0.5, 0.003, 0.25, f_end=420) * (1 + 0.4 * np.sin(2 * np.pi * 14 * np.arange(int(0.5 * SR)) / SR))
    add(bo, T_LAND, 0.35)
    add(tone(90, 0.2, 0.002, 0.08, f_end=50), T_LAND, 0.6)
    # IPPON: Gong
    gong = ssum(tone(130, 2.5, 0.004, 1.2), 0.6 * tone(262, 2.0, 0.004, 0.9), 0.35 * tone(347, 1.6, 0.004, 0.7),
                0.2 * tone(521, 1.2, 0.004, 0.5))
    add(gong, T_IPPON, 0.45)

    # --- Wertungstafeln: Gameshow-Ding, Dose gefangen, Muskelprotz-Schritte
    for k in range(4):
        add(ssum(tone(1318, 0.25, 0.002, 0.12), 0.5 * tone(1976, 0.2, 0.002, 0.1)), T_CARDS + k * 0.12 + 0.1, 0.12)
    add(ssum(tone(900, 0.08, 0.001, 0.03), tone(450, 0.12, 0.001, 0.06)), T_CATCH, 0.35)
    for tb in np.arange(T_MUSK0, T_MUSK1, 0.22):
        add(lp_fast(noise(0.07), 8) * np.exp(-np.arange(int(0.07 * SR)) / 700), tb, 0.6)
    add(tone(1900, 0.14, 0.002, 0.08), T_BEEP + 0.45, 0.2)   # Dose wird gescannt
    # --- Applaus + "Wooo"
    L = int((T_CLAP1 - T_CLAP0 + 0.6) * SR)
    ap = np.zeros(L)
    for _ in range(220):
        i = rng.integers(0, L - 3000)
        ap[i:i + 2400] += rng.standard_normal(2400) * np.exp(-np.arange(2400) / 300)
    ap = np.diff(ap, prepend=0)
    ap *= np.clip(np.arange(L) / (0.15 * SR), 0, 1) * np.clip((L - np.arange(L)) / (0.6 * SR), 0, 1)
    add(ap, T_CLAP0, 0.18)
    add(lp_fast(noise(0.8), 30) * np.sin(np.linspace(0, np.pi, int(0.8 * SR))), T_CLAP0 + 0.1, 0.5)
    # benommen: Vögelchen
    for r in range(3):
        for i in range(3):
            add(tone(2400 + i * 300, 0.12, 0.003, 0.05, f_end=2900 + i * 300), T_BACK1A + 0.3 + r * 1.4 + i * 0.18,
                0.07)

    # --- Rückblende: Whoosh, Knistern, Jubel, Kamerablitze
    add(lp_fast(noise(0.4), 5) * np.linspace(0, 1, int(0.4 * SR)), T_FLASH_A - 0.35, 0.3)
    L = int((T_FLASH_B - T_FLASH_A) * SR)
    crack = np.zeros(L)
    idx = rng.integers(0, L, 400)
    crack[idx] = rng.uniform(-1, 1, 400)
    add(lp_fast(crack, 3) * 1.5 + lp_fast(rng.standard_normal(L), 4) * 0.03, T_FLASH_A, 0.5)
    cheer = lp_fast(rng.standard_normal(L), 18) * (0.6 + 0.4 * np.sin(np.linspace(0, 9, L)) ** 2)
    cheer *= np.clip(np.arange(L) / (0.3 * SR), 0, 1) * np.clip((L - np.arange(L)) / (0.4 * SR), 0, 1)
    add(cheer, T_FLASH_A, 0.9)
    for tb in (T_FLASH_A + 0.5, T_FLASH_A + 1.9, T_FLASH_A + 3.1):
        add(np.diff(lp_fast(noise(0.05), 2), prepend=0) * np.exp(-np.arange(int(0.05 * SR)) / 300), tb, 0.6)
    # nostalgische Fanfare
    for i, f in enumerate((523, 659, 784, 1047)):
        add(tone(f, 0.5, 0.01, 0.3, kind="saw") * 0.15, T_FLASH_A + 0.4 + i * 0.12, 0.35)

    # --- Gurke, Scanner, Kasse
    add(tone(500, 0.1, 0.002, 0.04, f_end=250), T_CUKE + 0.38, 0.3)
    add(tone(1900, 0.14, 0.002, 0.08), T_BEEP, 0.2)
    add(ssum(tone(2093, 0.25, 0.002, 0.12), tone(2637, 0.4, 0.002, 0.2)), T_LINE["kas1"] - 0.25, 0.12)  # Ka-ching
    # --- Close-up: Whoosh + Zwinker-Pling + Schluss-Akkord
    add(lp_fast(noise(0.25), 6) * np.linspace(0, 1, int(0.25 * SR)), T_CLOSE - 0.22, 0.25)
    add(lp_fast(noise(0.25), 6) * np.linspace(0, 1, int(0.25 * SR)), T_BACK2A - 0.2, 0.2)
    add(ssum(tone(1568, 0.6, 0.002, 0.3), 0.5 * tone(2349, 0.6, 0.002, 0.25)), T_WINK, 0.22)
    add(ssum(tone(523, 0.6, 0.003, 0.35), tone(659, 0.6, 0.003, 0.35), tone(784, 0.8, 0.003, 0.45)), T_END_TXT,
        0.14)

    # --- Stimmen
    for lid, l in LINES.items():
        with wave.open(l["wav"]) as wf:
            v = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).astype(np.float64) / 32768
        add(v * 1.15, T_LINE[lid] - l["lead"])

    mix = np.tanh(mix * 1.1) * 0.92
    fade = np.clip(tt / 0.05, 0, 1) * np.clip((TOTAL - tt) / 0.3, 0, 1)
    pcm = (mix * fade * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        d = BUILD / "stills"
        d.mkdir(parents=True, exist_ok=True)
        for s in sys.argv[2:]:
            fi = int(float(s) * FPS)
            render_frame(fi).convert("RGB").save(d / f"f_{float(s):05.2f}.png")
            print(d / f"f_{float(s):05.2f}.png")
        return
    wav = BUILD / "mix.wav"
    build_audio(wav)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r",
           str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt",
           "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(min(4, os.cpu_count()), maxtasksperchild=40) as pool:
        for i, b in enumerate(pool.imap(_rgb, range(NF), chunksize=4)):
            p.stdin.write(b)
            if i % 30 == 0:
                print(f"frame {i}/{NF}", flush=True)
    p.stdin.close()
    p.wait()
    print("->", OUT)


if __name__ == "__main__":
    main()
