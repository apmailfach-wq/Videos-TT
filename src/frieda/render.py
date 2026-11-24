"""Frieda an der Supermarktkasse – 3D-Spielzeug-Look, 1080x1920, 30 fps, ~46 s.

python3 tts.py && python3 render.py            -> ../../frieda-supermarkt.mp4
python3 render.py preview 2 14.9 18 22 30 40.9 44    -> build/frieda/stills/
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
from core import (F_BLACK, F_INTER, W, H, FPS, capsule, gradient, clamp01, ease_back, ease_io, ease_out, emoji, font,  # noqa
                  lerp, mixc, paste_c, sphere, text_img, zoom_frame)

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "frieda"
OUT = Path(os.environ.get("VIDEO_OUT", ROOT / "frieda-supermarkt.mp4"))
SR = 48000

# ------------------------------------------------------------------ timeline (seconds)
LINES = {l["id"]: l for l in json.loads((BUILD / "lines.json").read_text())}

T_LINE = {
    "kas0": 2.2, "fr0": 3.9, "typ0": 6.9, "k2a": 9.5, "typ1": 11.9,
    "fr1": 14.75, "typ2": 15.85,
    "k3a": 21.55, "typ3": 24.55,
    "kas2": 26.3, "fr3": 28.75,
    "kas3": 34.05, "kas1": 38.15,
    "fr2": 39.95, "typ4": 41.85,
}
T_K0_LEAVE = 3.0                      # Kunde vor Frieda geht
T_GUY_IN0, T_GUY_IN1 = 6.5, 9.4       # Drängler läuft rein (telefoniert)
T_PUSH = 13.9                         # Musik weg, Kamera drückt rein
T_CLOSE1A, T_CLOSE1B = 14.45, 15.7    # Close-up "Ich auch."
T_GRAB, T_THROW, T_FLY, T_LAND, T_SLOW_END = 16.3, 16.95, 17.45, 19.6, 20.0
T_IPPON = 19.7
T_CLAP0, T_CLAP1 = 20.0, 22.2
T_BACK1A, T_BACK1B = 21.25, 26.0      # Ende der Schlange: Herr + benommener Typ
T_FLASH_A, T_FLASH_B = 28.45, 33.0    # Rückblende 1974
T_CUKE = 33.35                        # Gurke aufs Band
T_BEEP = 33.95
T_CLOSE2A = 39.6                      # Close-up "Mit Stil."
T_WINK = 40.95
T_BACK2A, T_BACK2B = 41.6, 43.45      # Typ hinten am Handy
T_END_TXT = 43.75
T_CLOSE = T_CLOSE2A
TOTAL = 46.0
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


# ------------------------------------------------------------------ characters
PEOPLE = {
    "typ": dict(body=(250, 196, 30), hair=(92, 56, 32), legs=(60, 90, 160), shoes=(240, 240, 245)),
    "kasse": dict(body=(40, 190, 170), hair=(150, 70, 40), legs=(40, 60, 90), shoes=(40, 40, 50)),
    "k0": dict(body=(255, 160, 60), hair=(205, 205, 212), legs=(70, 70, 90), shoes=(60, 40, 30), style="short"),
    "k1": dict(body=(110, 140, 255), hair=(40, 30, 25), legs=(60, 60, 80), shoes=(30, 30, 30), style="short"),
    "k2": dict(body=(255, 120, 150), hair=(230, 170, 60), legs=(90, 70, 120), shoes=(250, 250, 250),
               style="long"),
    "k3": dict(body=(120, 210, 110), hair=(170, 170, 175), legs=(80, 70, 60), shoes=(70, 40, 30), style="bald"),
    "k4": dict(body=(190, 120, 240), hair=(60, 30, 20), legs=(50, 60, 100), shoes=(30, 30, 30), style="bun"),
}


def arm(im, R, shoulder, a_deg, L, th, color, hand=SKIN):
    """Arm hanging from shoulder; a_deg = angle from straight down (positive = to screen right)."""
    a = math.radians(a_deg)
    dx, dy = math.sin(a), math.cos(a)
    sx, sy = shoulder
    hx, hy = sx + dx * L, sy + dy * L
    sl = capsule(int(th), int(L + th * 0.4), color, None)
    rot_paste(im, sl, (sx + hx) / 2, (sy + hy) / 2, math.degrees(math.atan2(dx, dy)))
    hd = sphere(int(th * 1.0), hand, None, 0.3)
    paste_c(im, hd, hx, hy)
    return hx, hy


def eyes(d, cx, cy, D, mode, iris=(40, 30, 40)):
    ex, r = D * 0.17, D * 0.075
    for sx in (-1, 1):
        x = cx + sx * ex
        m = mode
        if mode == "wink":
            m = "open" if sx < 0 else "closed"
        if m in ("closed", "happy"):
            d.arc([x - r * 1.1, cy - r * 0.9, x + r * 1.1, cy + r * 1.2], 200, 340, fill=DARK, width=max(3, int(D * 0.025)))
        elif m == "dazed":
            d.line([(x - r, cy - r), (x + r, cy + r)], fill=DARK, width=max(3, int(D * 0.025)))
            d.line([(x - r, cy + r), (x + r, cy - r)], fill=DARK, width=max(3, int(D * 0.025)))
        else:
            d.ellipse([x - r, cy - r * 1.2, x + r, cy + r * 1.2], fill=(255, 255, 255))
            d.ellipse([x - r * 0.68, cy - r * 0.75, x + r * 0.68, cy + r * 0.75], fill=iris)
            d.ellipse([x - r * 0.34, cy - r * 0.38, x + r * 0.34, cy + r * 0.38], fill=(20, 16, 24))
            d.ellipse([x - r * 0.1 + r * 0.3, cy - r * 0.55, x + r * 0.18 + r * 0.3, cy - r * 0.25], fill=(255, 255, 255))


def mouth(d, cx, cy, D, m, smirk=False):
    w = D * 0.13
    if m > 0.08:
        h = D * 0.035 + D * 0.09 * m
        d.ellipse([cx - w * 0.8, cy - h * 0.35, cx + w * 0.8, cy + h], fill=(120, 30, 50))
        d.ellipse([cx - w * 0.45, cy + h * 0.35, cx + w * 0.45, cy + h * 0.95], fill=(240, 110, 120))
    else:
        off = D * 0.04 if smirk else 0
        d.arc([cx - w + off, cy - D * 0.07, cx + w + off, cy + D * 0.06], 20, 160 if not smirk else 120,
              fill=(150, 50, 60), width=max(3, int(D * 0.024)))


@lru_cache(maxsize=4096)
def person(who, R=1.0, al=8, ar=-8, m=0.0, eye="open", item=None, cuke=True, sq=1.0):
    """Toy figure facing camera. Returns (img, feet_x, feet_y). al/ar = arm angles (deg)."""
    c = PEOPLE[who]
    Wc, Hc = int(560 * R), int(820 * R)
    im = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, fy = Wc / 2, Hc - 30 * R
    k = R
    # legs + shoes
    for sx in (-1, 1):
        leg = capsule(int(54 * k), int(120 * k), c["legs"], None)
        paste_c(im, leg, cx + sx * 42 * k, fy - 62 * k)
        sh = capsule(int(84 * k), int(46 * k), c["shoes"], None)
        paste_c(im, sh, cx + sx * 48 * k, fy - 10 * k)
    body_top = fy - 380 * k
    # body
    bw, bh = 260 * k, 270 * k
    body = capsule(int(bw), int(bh), c["body"], None, radius=int(bw * 0.4))
    by = body_top + bh / 2
    paste_c(im, body, cx, by)
    if False:
        pass
    elif who == "typ":
        d.line([(cx - 30 * k, body_top + 20 * k), (cx - 34 * k, body_top + 100 * k)], fill=(255, 255, 255), width=int(6 * k))
        d.line([(cx + 30 * k, body_top + 20 * k), (cx + 34 * k, body_top + 100 * k)], fill=(255, 255, 255), width=int(6 * k))
        d.text((cx, body_top + 160 * k), "YOLO", font=font(F_BLACK, int(44 * k)), fill=(30, 30, 40), anchor="mm")
    elif who == "kasse":
        d.rounded_rectangle([cx - 100 * k, body_top + 70 * k, cx - 10 * k, body_top + 110 * k], radius=8 * k,
                            fill=(255, 255, 255))
        d.text((cx - 55 * k, body_top + 90 * k), "MONI", font=font(F_BLACK, int(20 * k)), fill=(30, 120, 110), anchor="mm")
    # arms
    sh_y = body_top + 70 * k
    L, th = 175 * k, 66 * k
    hand_l = arm(im, R, (cx - 118 * k, sh_y), -al, L, th, c["body"])
    hand_r = arm(im, R, (cx + 118 * k, sh_y), -ar, L, th, c["body"])
    # head
    D = 300 * k
    hx, hy = cx, body_top - 95 * k
    if c.get("style") == "bun":
        paste_c(im, sphere(int(130 * k), c["hair"], None, 0.3), hx, hy - D * 0.55)
    if c.get("style") == "long" or who == "kasse":
        hairback = capsule(int(D * 1.02), int(D * 1.05), c["hair"], None)
        paste_c(im, hairback, hx, hy + D * 0.12)
    for sx in (-1, 1):
        paste_c(im, sphere(int(D * 0.2), mixc(SKIN, (230, 140, 120), 0.3), None, 0.1), hx + sx * D * 0.48, hy + D * 0.06)
    paste_c(im, sphere(int(D), SKIN, None, 0.22), hx, hy)
    d = ImageDraw.Draw(im)
    st = c.get("style", who)
    if False:
        pass
    elif who == "typ":
        d.chord([hx - D * 0.51, hy - D * 0.56, hx + D * 0.51, hy + D * 0.2], 180, 360, fill=c["hair"])
        d.ellipse([hx - D * 0.15, hy - D * 0.68, hx + D * 0.42, hy - D * 0.3], fill=c["hair"])
    elif st == "short":
        d.chord([hx - D * 0.51, hy - D * 0.54, hx + D * 0.51, hy + D * 0.1], 180, 360, fill=c["hair"])
    elif st in ("long", "bun") or who == "kasse":
        d.chord([hx - D * 0.52, hy - D * 0.56, hx + D * 0.52, hy + D * 0.24], 180, 360, fill=c["hair"])
    elif st == "bald":
        for sx in (-1, 1):
            d.ellipse([hx + sx * D * 0.43 - D * 0.1, hy - D * 0.2, hx + sx * D * 0.43 + D * 0.1, hy + D * 0.1],
                      fill=c["hair"])
    ey = hy + D * 0.02
    # blush
    for sx in (-1, 1):
        d.ellipse([hx + sx * D * 0.28 - D * 0.08, ey + D * 0.08, hx + sx * D * 0.28 + D * 0.08, ey + D * 0.16],
                  fill=(255, 150, 150))
    if who == "typ" and eye != "dazed":
        for sx in (-1, 1):
            x = hx + sx * D * 0.18
            d.rounded_rectangle([x - D * 0.15, ey - D * 0.09, x + D * 0.15, ey + D * 0.1], radius=D * 0.06,
                                fill=(20, 20, 28))
            d.line([(x - D * 0.09, ey - D * 0.04), (x - D * 0.02, ey - D * 0.07)], fill=(170, 220, 255),
                   width=int(5 * k))
        d.line([(hx - D * 0.05, ey - D * 0.04), (hx + D * 0.05, ey - D * 0.04)], fill=(20, 20, 28), width=int(7 * k))
    else:
        eyes(d, hx, ey, D, eye, (70, 45, 30))
    paste_c(im, sphere(int(D * 0.13), mixc(SKIN, (235, 130, 110), 0.35), None, 0.35), hx, ey + D * 0.1)
    mouth(ImageDraw.Draw(im), hx, ey + D * 0.25, D, m, smirk=(who == "typ"))
    # held items
    if False:
        pass
    elif item == "phone":
        x, y = hand_r
        ph = Image.new("RGBA", (int(50 * k), int(96 * k)), (0, 0, 0, 0))
        ImageDraw.Draw(ph).rounded_rectangle([0, 0, 50 * k - 1, 96 * k - 1], radius=10 * k, fill=(30, 30, 40))
        rot_paste(im, ph, x - 18 * k, y - 10 * k, -20)
        paste_c(im, sphere(int(th), SKIN, None, 0.3), x, y)
    elif item == "bag":
        x, y = hand_l
        bg = capsule(int(120 * k), int(130 * k), (205, 160, 110), None, radius=int(14 * k)).copy()
        paste_c(bg, sphere(int(46 * k), (240, 60, 60), None, 0.4), 40 * k, 14 * k)
        paste_c(bg, capsule(int(30 * k), int(70 * k), (250, 220, 80), None), 80 * k, 10 * k)
        paste_c(im, bg, x, y + 60 * k)
        paste_c(im, sphere(int(th), SKIN, None, 0.3), x, y)
    elif item == "can":
        x, y = hand_r
        can = capsule(int(52 * k), int(110 * k), (30, 40, 70), None, radius=int(14 * k))
        can = can.copy()
        cd = ImageDraw.Draw(can)
        cd.polygon([(30 * k, 18 * k), (14 * k, 58 * k), (28 * k, 58 * k), (20 * k, 94 * k), (40 * k, 48 * k),
                    (26 * k, 48 * k)], fill=(170, 255, 40))
        paste_c(im, can, x + 4 * k, y - 34 * k)
        paste_c(im, sphere(int(th), SKIN, None, 0.3), x, y)
    if sq != 1.0:
        im = im.resize((int(Wc / sq ** 0.5), int(Hc * sq)), Image.BICUBIC)
        return im, im.width / 2, im.height - 30 * R * sq
    return im, cx, fy


@lru_cache(maxsize=4096)
def person_scaled(key, s100):
    im, fx, fy = person(*key)
    s = s100 / 100
    if abs(s - 1) > 0.005:
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    return im, fx * s, fy * s


def draw_person(frame, key, x, y, s, rot=0.0, alpha=1.0):
    im, fx, fy = person_scaled(key, int(round(s * 100)))
    if rot:
        # rotate around body centre
        cx_off, cy_off = im.width / 2 - fx, im.height / 2 - fy
        im2 = im.rotate(rot, resample=Image.BICUBIC, expand=True)
        a = math.radians(rot)
        rx = cx_off * math.cos(a) + cy_off * math.sin(a)
        ry = -cx_off * math.sin(a) + cy_off * math.cos(a)
        paste_c(frame, im2, x + rx, y + ry, alpha=alpha)
    else:
        paste_c(frame, im, x - fx + im.width / 2, y - fy + im.height / 2, alpha=alpha)


# ------------------------------------------------------------------ set
VPX, VPY = 540, 470
FLOOR_Y = 820


@lru_cache(maxsize=1)
def background():
    yy = np.linspace(0, 1, H)[:, None]
    wall = np.zeros((H, W, 3), np.float32)
    wall[:] = (np.array((255, 238, 214)) * (1 - yy[..., None]) + np.array((255, 214, 196)) * yy[..., None])
    # checker floor in perspective
    ys, xs = np.mgrid[FLOOR_Y:H, 0:W].astype(np.float32)
    z = 520.0 / (ys - VPY)
    xw = (xs - VPX) * z
    par = (np.floor(xw / 70) + np.floor(z * 6)) % 2
    c1, c2 = np.array((250, 250, 246)), np.array((120, 210, 220))
    fl = c1 * (1 - par[..., None]) + c2 * par[..., None]
    fog = np.clip((z - 0.4) / 1.2, 0, 1)[..., None] * 0.35
    fl = fl * (1 - fog) + np.array((255, 226, 206)) * fog
    wall[FLOOR_Y:] = fl
    img = Image.fromarray(wall.clip(0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img)
    # shelves on the back wall
    rng = random.Random(7)
    pal = [(255, 90, 90), (255, 190, 40), (90, 170, 255), (120, 220, 120), (255, 130, 200), (170, 120, 255),
           (255, 150, 60), (60, 200, 190)]
    for row, y in enumerate((300, 470, 640, 800)):
        d.rounded_rectangle([20, y, W - 20, y + 22], radius=8, fill=(205, 140, 90))
        x = 34
        while x < W - 80:
            kind = rng.random()
            col = rng.choice(pal)
            if kind < 0.45:
                w, h = rng.randint(60, 90), rng.randint(90, 130)
                paste_c(img, capsule(w, h, col, None, radius=14), x + w / 2, y - h / 2 + 2)
                d.rounded_rectangle([x + 10, y - h * 0.65, x + w - 10, y - h * 0.4], radius=6, fill=(255, 255, 255))
            elif kind < 0.8:
                w, h = rng.randint(44, 60), rng.randint(110, 150)
                paste_c(img, capsule(w, h, col, None), x + w / 2, y - h / 2 + 2)
                paste_c(img, capsule(w // 2, 30, mixc(col, (255, 255, 255), 0.5), None), x + w / 2, y - h + 6)
            else:
                w = rng.randint(66, 84)
                paste_c(img, sphere(w, col, None, 0.4), x + w / 2, y - w / 2 + 4)
                w += 0
            x += w + rng.randint(6, 14)
    # hanging sign
    d.rounded_rectangle([150, 1040, 170, 1500], radius=8, fill=(150, 150, 160))
    sign = capsule(260, 86, (240, 60, 70), None, radius=34)
    paste_c(img, sign, 160, 1000)
    d.text((160, 1002), "KASSE 1", font=font(F_BLACK, 40), fill=(255, 255, 255), anchor="mm")
    return img


@lru_cache(maxsize=1)
def counter_static():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # front panel
    panel = capsule(820, 330, (240, 70, 80), None, radius=40)
    paste_c(img, panel, 360, 1820)
    d.rectangle([-50, 1735, 770, 1760], fill=(255, 255, 255))
    d.text((360, 1860), "FRISCH & BUNT", font=font(F_BLACK, 52), fill=(255, 236, 236), anchor="mm")
    # belt bed
    d.rounded_rectangle([-40, 1600, 790, 1700], radius=30, fill=(90, 96, 112))
    # scanner
    d.rounded_rectangle([40, 1590, 210, 1690], radius=18, fill=(170, 178, 190))
    d.rounded_rectangle([60, 1605, 190, 1660], radius=10, fill=(60, 30, 40))
    # till
    paste_c(img, capsule(150, 120, (230, 232, 238), None, radius=20), 110, 1530)
    d.rounded_rectangle([55, 1488, 165, 1540], radius=8, fill=(30, 50, 60))
    d.text((110, 1514), "0,49", font=font(F_BLACK, 28), fill=(120, 255, 180), anchor="mm")
    return img


def draw_counter(frame, t):
    c = counter_static()
    frame.alpha_composite(c)
    d = ImageDraw.Draw(frame)
    # moving belt stripes (belt runs to the left once the cucumber is on)
    off = (max(0.0, t - T_CUKE - 0.5) * 120) % 60
    for i in range(16):
        x = 230 + i * 60 - off
        if 225 < x < 770:
            d.line([(x, 1612), (x - 8, 1690)], fill=(70, 74, 88), width=6)
    # scanner laser
    a = 0.6 + 0.4 * math.sin(t * 20)
    d.line([(68, 1632), (182, 1632)], fill=(255, int(60 * a), int(60 * a)), width=4)


# ------------------------------------------------------------------ positions (x, feet_y, scale)
FRIEDA = (575, 1645, 0.95)
CASH = (150, 1620, 0.82)
K0 = (330, 1665, 0.9)
GUY_SPOT = (300, 1695, 0.95)
QUEUE = [("k1", 790, 1360, 0.70), ("k2", 580, 1180, 0.57), ("k4", 760, 1040, 0.47), ("k3", 590, 940, 0.39)]
LAND = (800, 878, 0.34)
HEAD_TOY = 690   # Kopf-Oberkante über den Füßen (Spielzeugfiguren, Skalierung 1)


def k0_state(t):
    if t >= T_K0_LEAVE + 1.6:
        return None
    p = ease_io(seg(t, T_K0_LEAVE, T_K0_LEAVE + 1.6))
    bob = abs(math.sin(t * 13)) * 12 if 0 < p < 1 else 0
    return K0[0] - 560 * p, K0[1] - bob, K0[2], ("k0", 1.0, 8, -8, 0.0, "happy" if t < 2.0 else "open", "bag")


def guy_state(t):
    """dict(x, y, s, rot, key)"""
    if t < T_GUY_IN0:
        return None
    if t < T_GUY_IN1:  # telefoniert, läuft an der Schlange vorbei bis ganz vorne
        p = ease_io(seg(t, T_GUY_IN0, T_GUY_IN1))
        bob = abs(math.sin(t * 13)) * 14 * (1 if p < 0.97 else 0)
        m = round(speaking("typ0", t), 1)
        return dict(x=lerp(1260, GUY_SPOT[0], p), y=GUY_SPOT[1] - bob, s=GUY_SPOT[2], rot=0,
                    key=("typ", 1.0, int(10 * math.sin(t * 13)), -165, m, "open", "phone"))
    if t < T_GRAB + 0.2:
        m = round(max(speaking("typ1", t), speaking("typ2", t)), 1)
        ar = -25
        if line_on("typ1", t, 0):
            ar = int(-40 - 25 * abs(math.sin(t * 4)))
        eye = "open"
        al = 10
        if line_on("typ2", t, 0.3):
            al, ar = 35, -35
        return dict(x=GUY_SPOT[0], y=GUY_SPOT[1], s=GUY_SPOT[2], rot=0, key=("typ", 1.0, al, ar, m, eye, "can"))
    if t < T_FLY:  # wird über Friedas Hüfte gehebelt (Zeitlupe)
        p = ease_io(seg(t, T_GRAB + 0.2, T_FLY))
        x = lerp(GUY_SPOT[0], FRIEDA[0], p)
        y = lerp(GUY_SPOT[1], 1250, p) - math.sin(p * math.pi) * 140
        return dict(x=x, y=y, s=GUY_SPOT[2], rot=lerp(0, -170, p), key=("typ", 1.0, 120, -120, 0.9, "open", "can"))
    if t < T_LAND:  # hoher Bogen ans Ende der Schlange
        p = seg(t, T_FLY, T_LAND)
        pe = ease_io(p)
        x0, y0 = FRIEDA[0], 1250
        x = (1 - pe) ** 2 * x0 + 2 * (1 - pe) * pe * 700 + pe ** 2 * LAND[0]
        y = (1 - pe) ** 2 * y0 + 2 * (1 - pe) * pe * 150 + pe ** 2 * LAND[1]
        return dict(x=x, y=y, s=lerp(GUY_SPOT[2], LAND[2], pe), rot=lerp(-170, -360, pe), trail=True,
                    key=("typ", 1.0, 150, -150, 0.9, "open", "can"))
    p = seg(t, T_LAND, T_LAND + 0.45)
    sq = round(1 - 0.28 * math.sin(p * math.pi), 2) if p < 1 else 1.0
    return dict(x=LAND[0], y=LAND[1], s=LAND[2], rot=0, key=("typ", 1.0, 25, -25, 0.0, "dazed", "can", True, sq))


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
    m = round(max(speaking("fr0", t), speaking("fr1", t)) * 0.8, 1)
    if T_GRAB <= t < T_THROW:
        return "oma_grab", "glare", 0.0, False, False
    if T_THROW <= t < T_FLY + 0.35:
        return "oma_throw", "strain", 0.0, False, False
    if T_CUKE - 0.15 <= t < T_CUKE + 0.45:
        return "oma_offer", "smile", 0.0, False, False
    if line_on("fr0", t, 0.2):
        return "oma_stand", "smile", m, False, True
    if T_GUY_IN0 + 1.0 < t < T_LINE["typ1"]:
        return "oma_stand", "neutral", 0.0, False, True
    if T_LINE["typ1"] <= t < T_GRAB:
        return "oma_stand", "warm", m, False, True
    if T_FLY + 0.35 <= t < T_CUKE:
        return "oma_stand", "proud", 0.0, False, True
    return "oma_stand", "smile", 0.0, False, True


@lru_cache(maxsize=512)
def frieda_sprite(D, pose, expr, m, mirror=False, items=(), blink=False, wink=False, knit_phase=0.0, who="oma"):
    im, (nx, ny), sc = fchars.person(who, D, pose, expr=expr, mouth=m, gl=0.03, items=items, blink=blink,
                                     knit_phase=knit_phase)
    if wink:  # nur das (vom Betrachter aus) rechte Auge zu
        cl, _, _ = fchars.person(who, D, pose, expr=expr, mouth=m, gl=0.03, items=items, blink=True,
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


def cash_key(t):
    m = round(max(speaking(l, t) for l in ("kas0", "kas2", "kas3", "kas1")), 1)
    eye = "happy" if T_CLAP0 < t < T_CLAP1 else "open"
    al, ar = 10, -10
    if T_CLAP0 < t < T_CLAP1:
        c = abs(math.sin((t - T_CLAP0) * 16))
        al, ar = int(-30 - 20 * c), int(30 + 20 * c)
    elif line_on("kas0", t, 0):
        ar = -60
    return ("kasse", 1.0, al, ar, m, eye)


def cust_key(who, t, i):
    al, ar, eye, m = 8, -8, "open", 0.0
    if who == "k2" and line_on("k2a", t, 0.2):
        m = round(speaking("k2a", t), 1)
        al, ar = 8, -150  # zeigt nach hinten
    if who == "k3":
        m = round(speaking("k3a", t), 1)
    if T_GRAB < t < T_LAND:
        m, al, ar = 0.8, 40, -40
    if T_CLAP0 + i * 0.05 < t < T_CLAP1:
        c = abs(math.sin((t - T_CLAP0 + i * 0.3) * 16))
        al, ar = int(-28 - 18 * c), int(28 + 18 * c)
        eye, m = "happy", 0.6
    return (who, 1.0, al, ar, m, eye)


# ------------------------------------------------------------------ camera (world shots)
CAM_KEYS = [  # t, zoom, cx, cy
    (0.0, 1.0, 540, 1150), (1.6, 1.0, 540, 1150), (3.6, 1.12, 480, 1360),
    (6.4, 1.12, 480, 1360), (7.2, 1.1, 760, 1320), (9.4, 1.16, 470, 1360),
    (11.8, 1.16, 470, 1360), (13.4, 1.22, 450, 1330), (14.4, 1.42, 450, 1260),
    (15.7, 1.4, 330, 1270), (16.3, 1.32, 400, 1260), (17.6, 1.0, 560, 1100),
    (20.0, 1.0, 560, 1100), (21.25, 1.0, 560, 1100),
    (26.0, 1.22, 420, 1380), (28.45, 1.28, 400, 1360),
    (33.0, 1.12, 470, 1330), (34.2, 1.22, 380, 1400), (39.6, 1.3, 360, 1380),
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


TEXT = {l: LINES[l]["text"].replace(" … ", "… ") for l in LINES}


# ------------------------------------------------------------------ world shot
def world(t, with_ui=True):
    frame = background().copy()
    gs = guy_state(t)
    flying = gs is not None and (T_GRAB + 0.2 <= t < T_LAND)
    items = []
    for i, (who, x, y, s) in enumerate(QUEUE):
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
            hop = abs(math.sin((t - T_CLAP0) * 9)) * 10 * s if T_CLAP0 < t < T_CLAP1 else 0
            draw_person(frame, cust_key(who, t, i), x, y - hop, s)
        elif it[0] == "g":
            draw_person(frame, gs["key"], gs["x"], gs["y"], gs["s"], gs["rot"])
        elif it[0] == "cash":
            draw_person(frame, cash_key(t), *CASH)
        elif it[0] == "k0":
            draw_person(frame, k0[3], k0[0], k0[1], k0[2])
        else:
            draw_frieda(frame, t, fx, FRIEDA[1], FRIEDA[2], frieda_rot(t))
    draw_counter(frame, t)
    if t >= T_CUKE:
        p = ease_io(seg(t, T_CUKE, T_CUKE + 0.4))
        x = lerp(fx - 220, 520, p)
        y = lerp(1500, 1630, p) - math.sin(p * math.pi) * 90
        x -= max(0.0, t - T_CUKE - 0.5) * 140
        rot_paste(frame, capsule(42, 150, (60, 150, 50), None), max(x, 200), y, lerp(-28, 90, p))
    if gs and flying:
        if gs.get("trail"):
            for k in (3, 2, 1):
                g2 = guy_state(t - k * 0.05)
                if g2:
                    draw_person(frame, g2["key"], g2["x"], g2["y"], g2["s"], g2["rot"], alpha=0.12 * (4 - k))
        draw_person(frame, gs["key"], gs["x"], gs["y"], gs["s"], gs["rot"])
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
    tense = seg(t, T_PUSH, T_PUSH + 0.3) * (1 - seg(t, T_CLOSE1A - 0.05, T_CLOSE1A))
    frame = grade(frame, max(slow * 0.9, tense * 0.5, seg(t, 15.7, 15.8) * (1 - seg(t, T_GRAB, T_GRAB + 0.01)) * 0.5))
    speed_lines(frame, t, slow * seg(t, T_THROW, T_FLY))
    if slow > 0.02:
        paste_c(frame, slowmo_badge(), 540, 330, scale=0.6 + 0.4 * ease_back(seg(t, T_GRAB, T_GRAB + 0.25)),
                alpha=slow * (0.75 + 0.25 * (int(t * 4) % 2)))
    # IPPON!
    if T_IPPON <= t < T_BACK1A:
        q = seg(t, T_IPPON, T_IPPON + 0.25)
        sc = 2.2 - 1.2 * ease_out(q)
        a = 1 - seg(t, T_BACK1A - 0.25, T_BACK1A)
        paste_c(frame, stamp("IPPON!", 190, (255, 70, 70)), 540, 560, scale=sc, alpha=a)
    # Applaus-Emojis
    if T_CLAP0 < t < T_CLAP1 + 0.4:
        rng = random.Random(3)
        for i in range(10):
            t0 = T_CLAP0 + rng.uniform(0, 1.2)
            q = seg(t, t0, t0 + 0.9)
            if 0 < q < 1:
                paste_c(frame, emoji("👏", 110), rng.uniform(160, 880), rng.uniform(900, 1400) - q * 300,
                        alpha=math.sin(q * math.pi), rot=rng.uniform(-20, 20))
    # 0,49-Anzeige blinkt nach dem Scan
    # Titel
    if t < 2.7:
        a = 1 - seg(t, 2.4, 2.7)
        sc = ease_back(seg(t, 0.1, 0.45))
        paste_c(frame, title_full(), 540, 300, scale=max(0.05, sc), alpha=a)
    # Sprechblasen über den Köpfen
    def head(x, y, s, frieda=False):
        hy = y - (FEET * FRIEDA_D * s + 1.35 * FRIEDA_D * s if frieda else HEAD_TOY * s)
        return to_screen(cam, x, hy)
    sp = {
        "kas0": head(*CASH), "kas2": head(*CASH), "kas3": head(*CASH), "kas1": head(*CASH),
        "fr0": head(*FRIEDA, frieda=True),
        "k2a": head(*QUEUE[1][1:]),
    }
    if gs:
        sp["typ0"] = head(gs["x"], gs["y"], gs["s"])
        sp["typ1"] = sp["typ2"] = head(gs["x"], gs["y"], gs["s"])
    sizes = {"typ1": 54, "typ0": 52, "k2a": 58, "kas3": 54, "typ2": 90}
    for lid, (ax, ay) in sp.items():
        bubble_at(frame, lid, TEXT[lid], ax, ay, t, sizes.get(lid, 62))
    return frame


# ------------------------------------------------------------------ close-ups
@lru_cache(maxsize=4)
def blurred_world(t, z, cx, cy, blur=18):
    f, _ = world(t)
    return zoom_frame(f, z, cx, cy).filter(ImageFilter.GaussianBlur(blur))


def flash(frame, t, t0, dur=0.12):
    fl = 1 - seg(t, t0, t0 + dur)
    if fl > 0:
        frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * fl))))


def closeup_ich_auch(t):
    frame = blurred_world(16.0, 1.4, 470, 1250).copy()
    p = ease_out(seg(t, T_CLOSE1A, T_CLOSE1B))
    m = round(speaking("fr1", t) * 0.8, 1)
    expr = "warm"
    D = 470
    im, nx, ny = frieda_sprite(D, "oma_stand", expr, m)
    s = lerp(1.0, 1.08, p)
    im = im.resize((int(im.width * s), int(im.height * s)), Image.BICUBIC)
    nx, ny = nx * s, ny * s
    paste_c(frame, im, 560 - nx + im.width / 2, 1010 - ny + im.height / 2)
    bubble_at(frame, "fr1", TEXT["fr1"], 420, 470, t, 96)
    frame = grade(frame, 0.35)
    flash(frame, t, T_CLOSE1A, 0.08)
    return frame


def closeup_end(t):
    frame = blurred_world(36.0, 1.5, 520, 1250).copy()
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
    frame = blurred_world(23.0, 2.4, 690, 760, 14).copy()
    # Boden-Schatten
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([120, 1880, 980, 1990], fill=(60, 40, 60, 70))
    frame.alpha_composite(sh.filter(ImageFilter.GaussianBlur(30)))
    second = t >= T_BACK2A
    m3 = round(speaking("k3a", t), 1)
    draw_person(frame, ("k3", 2.0, 8, -8 if not line_on("k3a", t, 0) else -40, m3, "open"), 330, 1930, 0.72)
    mt = round(max(speaking("typ3", t), speaking("typ4", t)), 1)
    if second:
        key = ("typ", 2.0, 8, -165, mt, "open", "phone")
        wob = 0
    else:
        key = ("typ", 2.0, 25, -25, mt, "dazed", "can")
        wob = 5 * math.sin(t * 5)
    draw_person(frame, key, 760, 1960, 0.72, rot=wob)
    if not second:  # Sternchen kreisen
        for i in range(4):
            a = t * 4 + i * math.tau / 4
            paste_c(frame, emoji("⭐", 60), 760 + math.cos(a) * 130, 930 + math.sin(a) * 30)
    bubble_at(frame, "k3a", TEXT["k3a"], 330, 900, t, 62)
    bubble_at(frame, "typ3", TEXT["typ3"], 760, 860, t, 66)
    bubble_at(frame, "typ4", TEXT["typ4"], 760, 860, t, 66)
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
    bubble_at(frame, "fr3", TEXT["fr3"].replace("Neunzehnhundertvierundsiebzig", "1974"), 300, 560, t, 56)
    # weiche Ein-/Ausblendung
    a_in = 1 - seg(t, T_FLASH_A, T_FLASH_A + 0.25)
    a_out = seg(t, T_FLASH_B - 0.25, T_FLASH_B)
    fl = max(a_in, a_out)
    if fl > 0:
        frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * fl))))
    return frame


# ------------------------------------------------------------------ dispatcher
def render_frame(fi):
    t = fi / FPS
    if T_CLOSE1A <= t < T_CLOSE1B:
        return closeup_ich_auch(t)
    if T_BACK1A <= t < T_BACK1B or T_BACK2A <= t < T_BACK2B:
        return back_shot(t)
    if T_FLASH_A <= t < T_FLASH_B:
        return flashback(t)
    if t >= T_CLOSE:
        return closeup_end(t)
    f = world_shot(t)
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
    for tb in (0.6, 1.3, 1.9):
        add(tone(1900, 0.12, 0.002, 0.05), tb, 0.12)     # Kunde vor Frieda wird abkassiert
    add(tone(1400, 0.08, 0.002, 0.04), 1.95, 0.08)

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
    add(lp_fast(noise(0.25), 6) * np.linspace(0, 1, int(0.25 * SR)), T_CLOSE1A - 0.2, 0.2)  # Schnitt-Whoosh

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
           str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt",
           "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, b in enumerate(pool.imap(_rgb, range(NF), chunksize=4)):
            p.stdin.write(b)
            if i % 30 == 0:
                print(f"frame {i}/{NF}", flush=True)
    p.stdin.close()
    p.wait()
    print("->", OUT)


if __name__ == "__main__":
    main()
