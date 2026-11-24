"""Frieda an der Supermarktkasse – 3D-Spielzeug-Look, 1080x1920, 30 fps, ~10,6 s.

python3 tts.py && python3 render.py            -> ../../frieda-supermarkt.mp4
python3 render.py preview 1 4.6 5.5 7.5 9.6    -> build/frieda/stills/
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
from core import (F_BLACK, F_INTER, W, H, FPS, capsule, clamp01, ease_back, ease_io, ease_out, emoji, font,  # noqa
                  lerp, mixc, paste_c, sphere, text_img, zoom_frame)

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "frieda"
OUT = Path(os.environ.get("VIDEO_OUT", ROOT / "frieda-supermarkt.mp4"))
SR = 48000

# ------------------------------------------------------------------ timeline (seconds)
T_LINE = {"typ1": 1.30, "fr1": 3.50, "kas1": 7.35, "fr2": 8.85}
T_GRAB, T_THROW, T_FLY, T_LAND, T_SLOW_END = 4.30, 4.75, 5.15, 6.20, 6.55
T_CLAP0, T_CLAP1 = 6.45, 7.70
T_CUKE = 6.95
T_CLOSE = 8.55
T_WINK = 9.55
T_END_TXT = 9.75
TOTAL = 11.0
NF = int(TOTAL * FPS)

LINES = {l["id"]: l for l in json.loads((BUILD / "lines.json").read_text())}

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
    "frieda": dict(body=(232, 214, 182), hair=(246, 246, 250), legs=SKIN, shoes=(150, 60, 70)),
    "typ": dict(body=(250, 196, 30), hair=(92, 56, 32), legs=(60, 90, 160), shoes=(240, 240, 245)),
    "kasse": dict(body=(40, 190, 170), hair=(150, 70, 40), legs=(40, 60, 90), shoes=(40, 40, 50)),
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
    if who == "frieda":
        # red flower skirt
        sk = Image.new("RGBA", (int(320 * k), int(190 * k)), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sk)
        sd.rounded_rectangle([40 * k, 0, 280 * k, 80 * k], radius=30 * k, fill=(214, 40, 52))
        sd.polygon([(40 * k, 30 * k), (280 * k, 30 * k), (318 * k, 176 * k), (2 * k, 176 * k)], fill=(214, 40, 52))
        sd.rounded_rectangle([0, 150 * k, 320 * k, 188 * k], radius=18 * k, fill=(214, 40, 52))
        rng = random.Random(4)
        for _ in range(16):
            x, y = rng.uniform(30, 290) * k, rng.uniform(30, 170) * k
            for a in range(5):
                px, py = x + math.cos(a * 1.256) * 9 * k, y + math.sin(a * 1.256) * 9 * k
                sd.ellipse([px - 6 * k, py - 6 * k, px + 6 * k, py + 6 * k], fill=(255, 235, 240))
            sd.ellipse([x - 5 * k, y - 5 * k, x + 5 * k, y + 5 * k], fill=(255, 205, 40))
        # simple shading on skirt
        sh = Image.new("RGBA", sk.size, (60, 0, 20, 0))
        g = np.linspace(0, 70, sk.width)[None, :].repeat(sk.height, 0)
        sh.putalpha(Image.fromarray(g.astype(np.uint8)).point(lambda v: v) )
        sk_a = sk.getchannel("A")
        shade = Image.new("RGBA", sk.size, (0, 0, 0, 0))
        shade.paste(sh, (0, 0), Image.fromarray(np.minimum(np.asarray(sk_a), g.astype(np.uint8))))
        sk.alpha_composite(shade)
        paste_c(im, sk, cx, fy - 200 * k)
    # body
    bw, bh = 260 * k, 270 * k
    body = capsule(int(bw), int(bh), c["body"], None, radius=int(bw * 0.4))
    by = body_top + bh / 2
    paste_c(im, body, cx, by)
    if who == "frieda":
        d.polygon([(cx - 46 * k, body_top + 18 * k), (cx + 46 * k, body_top + 18 * k), (cx, body_top + 130 * k)],
                  fill=(255, 250, 244))
        d.line([(cx, body_top + 130 * k), (cx, body_top + 250 * k)], fill=(190, 168, 136), width=int(5 * k))
        for i in range(3):
            y = body_top + (150 + i * 36) * k
            paste_c(im, sphere(int(20 * k), (160, 120, 90), None, 0.5), cx + 14 * k, y)
        # pocket with pink knitting
        d.rounded_rectangle([cx + 40 * k, body_top + 150 * k, cx + 110 * k, body_top + 215 * k], radius=10 * k,
                            fill=(214, 196, 162))
        paste_c(im, sphere(int(64 * k), (250, 110, 180), None, 0.35), cx + 76 * k, body_top + 148 * k)
        for a in (-24, 18):
            nd = capsule(int(9 * k), int(110 * k), (220, 220, 230), None)
            rot_paste(im, nd, cx + 76 * k + a * 1.2 * k, body_top + 110 * k, a)
        for a in (-1, 1):  # stitches
            d.arc([cx + 52 * k, body_top + (120 + a * 8) * k, cx + 100 * k, body_top + (170 + a * 8) * k], 200, 340,
                  fill=(220, 70, 150), width=int(4 * k))
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
    if who == "frieda" or c.get("style") == "bun":
        paste_c(im, sphere(int(130 * k), c["hair"] if who == "frieda" else c["hair"], None, 0.3), hx, hy - D * 0.55)
    if c.get("style") == "long" or who == "kasse":
        hairback = capsule(int(D * 1.02), int(D * 1.05), c["hair"], None)
        paste_c(im, hairback, hx, hy + D * 0.12)
    for sx in (-1, 1):
        paste_c(im, sphere(int(D * 0.2), mixc(SKIN, (230, 140, 120), 0.3), None, 0.1), hx + sx * D * 0.48, hy + D * 0.06)
    paste_c(im, sphere(int(D), SKIN, None, 0.22), hx, hy)
    d = ImageDraw.Draw(im)
    st = c.get("style", who)
    if who == "frieda":
        d.chord([hx - D * 0.52, hy - D * 0.56, hx + D * 0.52, hy + D * 0.26], 180, 360, fill=c["hair"])
        for sx in (-1, 1):
            d.ellipse([hx + sx * D * 0.42 - D * 0.1, hy - D * 0.2, hx + sx * D * 0.42 + D * 0.1, hy + D * 0.08],
                      fill=c["hair"])
        # hair strands
        for a in range(-3, 4):
            d.arc([hx - D * 0.4 + a * D * 0.08, hy - D * 0.5, hx + a * D * 0.08 + D * 0.1, hy - D * 0.05], 200, 280,
                  fill=(215, 215, 225), width=int(3 * k))
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
        eyes(d, hx, ey, D, eye, (60, 140, 230) if who == "frieda" else (70, 45, 30))
    if who == "frieda":
        gold = (222, 170, 40)
        for sx in (-1, 1):
            x = hx + sx * D * 0.17
            d.ellipse([x - D * 0.12, ey - D * 0.12, x + D * 0.12, ey + D * 0.12], outline=gold, width=int(7 * k))
        d.arc([hx - D * 0.06, ey - D * 0.06, hx + D * 0.06, ey + D * 0.04], 200, 340, fill=gold, width=int(6 * k))
    paste_c(im, sphere(int(D * 0.13), mixc(SKIN, (235, 130, 110), 0.35), None, 0.35), hx, ey + D * 0.1)
    mouth(ImageDraw.Draw(im), hx, ey + D * 0.25, D, m, smirk=(who == "typ"))
    if who == "frieda":
        # pearl necklace
        for i in range(11):
            a = math.pi * (0.15 + 0.7 * i / 10)
            px, py = hx + math.cos(a) * D * 0.3, body_top + 8 * k + math.sin(a) * D * 0.18
            paste_c(im, sphere(int(24 * k), (250, 246, 238), None, 0.7), px, py)
    # held items
    if item == "basket":
        x, y = hand_l
        bk = Image.new("RGBA", (int(190 * k), int(190 * k)), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bk)
        bd.arc([30 * k, 0, 160 * k, 140 * k], 180, 360, fill=(150, 95, 45), width=int(12 * k))
        if cuke:
            cu = capsule(int(42 * k), int(150 * k), (60, 150, 50), None)
            rot_paste(bk, cu, 110 * k, 70 * k, -28)
        bd.rounded_rectangle([10 * k, 70 * k, 180 * k, 180 * k], radius=24 * k, fill=(196, 132, 64))
        for j in range(4):
            bd.line([(14 * k, (92 + j * 24) * k), (176 * k, (92 + j * 24) * k)], fill=(160, 100, 45), width=int(5 * k))
        paste_c(im, bk, x - 10 * k, y + 50 * k)
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
FRIEDA = (420, 1650, 0.95)
CASH = (150, 1620, 0.82)
GUY_SPOT = (770, 1690, 0.98)
QUEUE = [("k1", 680, 1360, 0.70), ("k2", 470, 1180, 0.57), ("k3", 650, 1040, 0.47), ("k4", 500, 940, 0.39)]
LAND = (720, 870, 0.34)


def guy_state(t):
    """Returns dict(x, y, s, rot, key, trail)."""
    if t < 0.55:
        return None
    if t < 1.35:  # strolls in from the right
        p = ease_out(seg(t, 0.55, 1.35))
        bob = abs(math.sin(t * 14)) * 14 * (1 - p)
        return dict(x=lerp(1250, GUY_SPOT[0], p), y=GUY_SPOT[1] - bob, s=GUY_SPOT[2], rot=0,
                    key=("typ", 1.0, 10, -25, 0.0, "open", "can"))
    if t < T_GRAB + 0.2:
        m = speaking("typ1", t)
        ar = -25 - 15 * math.sin(t * 3) if line_on("typ1", t, 0) else -25
        return dict(x=GUY_SPOT[0], y=GUY_SPOT[1], s=GUY_SPOT[2], rot=0,
                    key=("typ", 1.0, 10 if t < 3.4 else 40, int(ar), round(m, 1), "open", "can"))
    if t < T_FLY:  # lifted over Frieda's hip (slow-mo)
        p = ease_io(seg(t, T_GRAB + 0.2, T_FLY))
        x = lerp(GUY_SPOT[0], 470, p)
        y = lerp(GUY_SPOT[1], 1180, p) - math.sin(p * math.pi) * 120
        return dict(x=x, y=y, s=GUY_SPOT[2], rot=lerp(0, 170, p),
                    key=("typ", 1.0, 120, -120, 0.9, "open", "can"))
    if t < T_LAND:  # big arc to the back of the queue
        p = seg(t, T_FLY, T_LAND)
        pe = ease_io(p)
        x0, y0, s0 = 470, 1180, GUY_SPOT[2]
        x = (1 - pe) ** 2 * x0 + 2 * (1 - pe) * pe * 640 + pe ** 2 * LAND[0]
        y = (1 - pe) ** 2 * y0 + 2 * (1 - pe) * pe * 180 + pe ** 2 * LAND[1]
        s = lerp(s0, LAND[2], ease_io(p))
        return dict(x=x, y=y, s=s, rot=lerp(170, 360, pe), trail=True,
                    key=("typ", 1.0, 150, -150, 0.9, "open", "can"))
    # landed softly, a little dazed
    p = seg(t, T_LAND, T_LAND + 0.45)
    sq = 1 - 0.28 * math.sin(p * math.pi) if p < 1 else 1.0
    eye = "dazed" if t < T_LAND + 1.6 else "open"
    return dict(x=LAND[0], y=LAND[1], s=LAND[2], rot=0,
                key=("typ", 1.0, 25, -25, 0.0, eye, "can", True, round(sq, 2)))


def frieda_key(t, R=1.0):
    m = max(speaking("fr1", t), speaking("fr2", t))
    eye = "open"
    if line_on("fr1", t, 0.2):
        eye = "happy"
    al, ar = 8, -8
    item = "basket"
    cuke = t < T_CUKE
    if T_GRAB <= t < T_FLY + 0.3:
        p = seg(t, T_GRAB, T_GRAB + 0.4)
        ar = -lerp(8, 80, ease_out(p))
        if t > T_GRAB + 0.45:
            q = seg(t, T_GRAB + 0.45, T_FLY)
            ar = -lerp(80, 170, ease_io(q))
            al = lerp(8, 40, q)
        eye = "closed" if t > T_THROW else "open"
    elif T_FLY + 0.3 <= t < T_CUKE:
        ar = -lerp(170, 12, ease_out(seg(t, T_FLY + 0.3, T_FLY + 0.8)))
        al = lerp(40, 8, ease_out(seg(t, T_FLY + 0.3, T_FLY + 0.8)))
        eye = "happy"
    elif T_CUKE <= t < T_CUKE + 0.6:
        ar = -lerp(12, 55, math.sin(seg(t, T_CUKE - 0.1, T_CUKE + 0.6) * math.pi))
    return ("frieda", R, int(al), int(ar), round(m, 1), eye, item, cuke)


def frieda_rot(t):
    if T_GRAB + 0.35 <= t < T_FLY + 0.5:
        p = seg(t, T_GRAB + 0.35, T_FLY + 0.5)
        return 14 * math.sin(p * math.pi)
    return 0.0


def cash_key(t):
    m = speaking("kas1", t)
    eye = "happy" if T_CLAP0 < t < T_CLAP1 else "open"
    al, ar = 10, -10
    if T_CLAP0 < t < T_CLAP1:
        c = abs(math.sin((t - T_CLAP0) * 16))
        al, ar = int(-30 - 20 * c), int(30 + 20 * c)
    return ("kasse", 1.0, al, ar, round(m, 1), eye)


def cust_key(who, t, i):
    al, ar, eye, m = 8, -8, "open", 0.0
    if T_FLY < t < T_LAND:
        m, eye = 0.8, "open"
        al, ar = 40, -40
    if T_CLAP0 + i * 0.05 < t < T_CLAP1:
        c = abs(math.sin((t - T_CLAP0 + i * 0.3) * 16))
        al, ar = int(-28 - 18 * c), int(28 + 18 * c)
        eye, m = "happy", 0.6
    return (who, 1.0, al, ar, m, eye)


# ------------------------------------------------------------------ UI elements
@lru_cache(maxsize=32)
def bubble(text, tail="left", size=62):
    f = font(F_INTER, size)
    tw = f.getlength(text)
    pw, ph = int(tw + 80), int(size * 1.7)
    im = Image.new("RGBA", (pw + 20, ph + 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([10, 14, pw + 10, ph + 14], radius=ph / 2, fill=(30, 26, 40))
    d.rounded_rectangle([4, 4, pw + 4, ph + 4], radius=ph / 2, fill=(255, 255, 255), outline=(30, 26, 40), width=6)
    tx = 70 if tail == "left" else pw - 70
    d.polygon([(tx - 26, ph), (tx + 26, ph), (tx + (-30 if tail == "left" else 30), ph + 58)], fill=(255, 255, 255),
              outline=None)
    d.line([(tx - 26, ph + 2), (tx + (-30 if tail == "left" else 30), ph + 58), (tx + 26, ph + 2)], fill=(30, 26, 40),
           width=6)
    d.text((pw / 2 + 4, ph / 2 + 6), text, font=f, fill=(30, 26, 40), anchor="mm")
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


# ------------------------------------------------------------------ frame rendering
def world(t):
    frame = background().copy()
    gs = guy_state(t)
    flying = gs is not None and (T_GRAB + 0.2 <= t < T_LAND)
    items = []
    for i, (who, x, y, s) in enumerate(QUEUE):
        items.append((y, ("c", who, x, y, s, i)))
    if gs and not flying:
        items.append((gs["y"], ("g",)))
    items.sort(key=lambda z: z[0])
    for _, it in items:
        if it[0] == "c":
            _, who, x, y, s, i = it
            hop = abs(math.sin((t - T_CLAP0) * 9)) * 10 * s if T_CLAP0 < t < T_CLAP1 else 0
            draw_person(frame, cust_key(who, t, i), x, y - hop, s)
        else:
            draw_person(frame, gs["key"], gs["x"], gs["y"], gs["s"], gs["rot"])
    # cashier + Frieda behind the counter
    draw_person(frame, cash_key(t), *CASH)
    fx = FRIEDA[0] - 50 * ease_io(seg(t, T_CUKE - 0.3, T_CUKE + 0.2))
    draw_person(frame, frieda_key(t), fx, FRIEDA[1], FRIEDA[2], frieda_rot(t))
    draw_counter(frame, t)
    # cucumber travelling to the belt, then towards the scanner
    if t >= T_CUKE:
        p = ease_io(seg(t, T_CUKE, T_CUKE + 0.4))
        x = lerp(fx - 120, 520, p)
        y = lerp(1560, 1630, p) - math.sin(p * math.pi) * 90
        x -= max(0.0, t - T_CUKE - 0.5) * 120
        cu = capsule(42, 150, (60, 150, 50), None)
        rot_paste(frame, cu, max(x, 200), y, lerp(-28, 90, p))
    if gs and flying:
        if gs.get("trail"):
            for k in (3, 2, 1):
                g2 = guy_state(t - k * 0.05)
                if g2:
                    draw_person(frame, g2["key"], g2["x"], g2["y"], g2["s"], g2["rot"], alpha=0.12 * (4 - k))
        if t < T_FLY:  # guy goes over Frieda's hip: in front of the counter
            draw_person(frame, gs["key"], gs["x"], gs["y"], gs["s"], gs["rot"])
        else:
            draw_person(frame, gs["key"], gs["x"], gs["y"], gs["s"], gs["rot"])
    return frame, gs


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
def blurred_bg():
    t = T_CLAP1 + 0.3
    f, _ = world(t)
    f = zoom_frame(f, 1.5, 420, 1250)
    return f.filter(ImageFilter.GaussianBlur(18))


def closeup(t):
    frame = blurred_bg().copy()
    p = ease_out(seg(t, T_CLOSE, T_CLOSE + 0.5))
    m = speaking("fr2", t)
    eye = "wink" if T_WINK - 0.05 <= t < T_WINK + 0.45 else "open"
    ar = -8
    if t > T_WINK - 0.25:  # finger-gun / thumbs gesture
        ar = -int(lerp(8, 135, ease_back(seg(t, T_WINK - 0.25, T_WINK + 0.05))))
    key = ("frieda", 2.3, 8, ar, round(m, 1), eye, None)
    s = lerp(1.1, 1.0, p)
    draw_person(frame, key, 540, 2090 + 40 * (1 - p), s * 1.0, rot=lerp(-4, 0, p))
    # wink sparkle
    if eye == "wink":
        q = seg(t, T_WINK, T_WINK + 0.45)
        sp = emoji("✨", int(130 + 60 * math.sin(q * math.pi)))
        paste_c(frame, sp, 790, 830, alpha=math.sin(q * math.pi))
    draw_bubble(frame, "fr2", "Mit Stil.", 300, 330, t, "right", 84)
    if t >= T_END_TXT:
        q = ease_back(seg(t, T_END_TXT, T_END_TXT + 0.35))
        paste_c(frame, end_text(), 540, 1500, scale=max(0.05, q))
    # flash on the cut
    fl = 1 - seg(t, T_CLOSE, T_CLOSE + 0.12)
    if fl > 0:
        frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(255 * fl))))
    return frame


@lru_cache(maxsize=1)
def end_text():
    return text_img("Das ist Frieda.", 118, (255, 214, 60), F_BLACK, stroke=18, stroke_fill=(30, 26, 40),
                    max_w=1000)


def render_frame(fi):
    t = fi / FPS
    if t >= T_CLOSE:
        return closeup(t)
    frame, gs = world(t)
    # camera: gentle push-in on the dialogue, wide for the throw, push to the belt for the cashier
    z = 1.0
    cx, cy = 540, 1300
    if t < T_GRAB:
        z = 1.0 + 0.10 * ease_io(seg(t, 1.0, 2.2)) + 0.06 * ease_io(seg(t, 3.3, 3.8))
        cx, cy = 560, 1420
    elif t < T_SLOW_END:
        z = 1.16 - 0.16 * ease_io(seg(t, T_GRAB, T_FLY + 0.2))
        cx, cy = 560, lerp(1420, 1100, ease_io(seg(t, T_GRAB, T_FLY + 0.2)))
    elif t < T_CUKE:
        z, cx, cy = 1.0, 540, 1100
    else:
        q = ease_io(seg(t, T_CUKE, T_CUKE + 0.6))
        z, cx, cy = lerp(1.0, 1.22, q), lerp(540, 330, q), lerp(1100, 1380, q)
    shake = 0
    if T_LAND <= t < T_LAND + 0.25:
        shake = 10 * (1 - seg(t, T_LAND, T_LAND + 0.25))
    hw, hh = W / (2 * z), H / (2 * z)
    cx, cy = min(max(cx, hw), W - hw), min(max(cy, hh), H - hh)
    frame = zoom_frame(frame, z, cx + math.sin(t * 90) * shake, cy + math.cos(t * 70) * shake)
    slow = seg(t, T_GRAB, T_GRAB + 0.15) * (1 - seg(t, T_SLOW_END - 0.15, T_SLOW_END))
    frame = grade(frame, slow * 0.9)
    speed_lines(frame, t, slow * seg(t, T_THROW, T_FLY))
    if slow > 0.02:
        paste_c(frame, slowmo_badge(), 540, 300, scale=0.6 + 0.4 * ease_back(seg(t, T_GRAB, T_GRAB + 0.25)),
                alpha=slow * (0.75 + 0.25 * (int(t * 4) % 2)))
    # applause emojis
    if T_CLAP0 < t < T_CLAP1 + 0.4:
        rng = random.Random(3)
        for i in range(9):
            t0 = T_CLAP0 + rng.uniform(0, 0.8)
            q = seg(t, t0, t0 + 0.9)
            if 0 < q < 1:
                paste_c(frame, emoji("👏", 110), rng.uniform(180, 900), rng.uniform(800, 1300) - q * 300,
                        alpha=math.sin(q * math.pi), rot=rng.uniform(-20, 20))
    # title
    if t < 2.6:
        a = 1 - seg(t, 2.3, 2.6)
        sc = ease_back(seg(t, 0.1, 0.45))
        paste_c(frame, title_full(), 540, 270, scale=max(0.05, sc), alpha=a)
    # dialogue bubbles (screen space)
    draw_bubble(frame, "typ1", "Sorry Oma, ich hab nur eine Sache.", 560, 620, t, "right", 50)
    draw_bubble(frame, "fr1", "Ich auch.", 330, 760, t, "left", 76)
    draw_bubble(frame, "kas1", "Mit Karte oder bar?", 430, 600, t, "left", 64)
    return frame


def _rgb(fi):
    return np.asarray(render_frame(fi).convert("RGB")).tobytes()


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
    n = int(TOTAL * SR)
    mix = np.zeros(n)
    rng = np.random.default_rng(5)

    def add(sig, t0, g=1.0):
        i = int(t0 * SR)
        if i >= n:
            return
        j = min(n, i + len(sig))
        mix[i:j] += sig[: j - i] * g

    # --- music: bouncy pluck loop, 128 bpm, ducked in slow-mo
    bpm = 128
    beat = 60 / bpm
    music = np.zeros(n)
    mel = [72, 76, 79, 76, 74, 77, 81, 77, 72, 76, 79, 84, 83, 79, 77, 74]
    bass = [48, 48, 53, 53, 55, 55, 48, 48]
    k = 0
    tb = 0.0
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
            put(tone(110, 0.15, 0.001, 0.05, f_end=45), 0.35)  # kick
        else:
            hh = rng.standard_normal(int(0.05 * SR)) * np.exp(-np.arange(int(0.05 * SR)) / (0.01 * SR))
            put(np.diff(hh, prepend=0), 0.05)
        k += 1
        tb += beat / 2
    tt = np.arange(n) / SR
    duck = np.ones(n)
    duck *= 1 - 0.95 * np.clip((tt - T_GRAB) / 0.15, 0, 1) * np.clip((T_LAND + 0.1 - tt) / 0.15, 0, 1)
    for lid in LINES:
        t0 = T_LINE[lid]
        t1 = t0 + LINES[lid]["speech"]
        duck *= 1 - 0.55 * np.clip((tt - t0 + 0.1) / 0.1, 0, 1) * np.clip((t1 + 0.15 - tt) / 0.15, 0, 1)
    duck *= np.clip((TOTAL - tt) / 0.6, 0, 1)
    mix += music * duck

    # --- store ambience
    amb = lp_fast(rng.standard_normal(n), 60) * 0.25 + 0.01 * np.sin(2 * np.pi * 100 * tt)
    mix += amb * 0.4 * np.clip(1 - (tt > T_CLOSE) * 0.6, 0, 1)
    for tb in (0.7, 2.4):
        add(tone(1900, 0.12, 0.002, 0.05), tb, 0.12)  # distant scanner beeps

    # --- footsteps of the guy
    for tb in np.arange(0.6, 1.35, 0.19):
        add(lp_fast(rng.standard_normal(int(0.06 * SR)), 8) * np.exp(-np.arange(int(0.06 * SR)) / 600), tb, 0.5)
    # slurp/can click when he arrives
    add(tone(2600, 0.05, 0.001, 0.01), 1.32, 0.2)

    # --- slow-mo: deep whoosh, sleeve grab, big swish, heartbeat
    add(tone(80, 0.5, 0.002, 0.3, f_end=40), T_GRAB, 0.6)
    grab = lp_fast(rng.standard_normal(int(0.12 * SR)), 4) * np.exp(-np.arange(int(0.12 * SR)) / 1500)
    add(grab, T_GRAB + 0.32, 0.6)
    L = int((T_LAND - T_THROW) * SR)
    sw = lp_fast(rng.standard_normal(L), 25)
    env = np.sin(np.linspace(0, np.pi, L)) ** 1.5
    add(sw * env * 3.0, T_THROW, 0.9)
    add(tone(60, 0.25, 0.005, 0.12), T_GRAB + 0.1, 0.5)
    add(tone(60, 0.25, 0.005, 0.12), T_FLY + 0.35, 0.5)
    add(tone(300, 1.0, 0.05, 0.6, f_end=120) * 0.3, T_FLY, 0.4)  # descending "wuuu"
    # soft landing: boing
    bo = tone(220, 0.5, 0.003, 0.25, f_end=420) * (1 + 0.4 * np.sin(2 * np.pi * 14 * np.arange(int(0.5 * SR)) / SR))
    add(bo, T_LAND, 0.35)
    add(tone(90, 0.2, 0.002, 0.08, f_end=50), T_LAND, 0.6)
    # dazed tweets
    for i in range(3):
        add(tone(2400 + i * 300, 0.12, 0.003, 0.05, f_end=2900 + i * 300), T_LAND + 0.4 + i * 0.18, 0.08)

    # --- applause
    L = int((T_CLAP1 - T_CLAP0 + 0.6) * SR)
    ap = np.zeros(L)
    for _ in range(140):
        i = rng.integers(0, L - 3000)
        ap[i:i + 2400] += rng.standard_normal(2400) * np.exp(-np.arange(2400) / 300)
    ap = np.diff(ap, prepend=0)
    env = np.clip(np.arange(L) / (0.15 * SR), 0, 1) * np.clip((L - np.arange(L)) / (0.5 * SR), 0, 1)
    add(ap * env, T_CLAP0, 0.18)
    # "Wooo"
    add(lp_fast(rng.standard_normal(int(0.8 * SR)), 30) * np.sin(np.linspace(0, np.pi, int(0.8 * SR))), T_CLAP0 + 0.1, 0.5)

    # --- cucumber on the belt + scanner beep
    add(tone(500, 0.1, 0.002, 0.04, f_end=250), T_CUKE + 0.38, 0.3)
    add(tone(1900, 0.14, 0.002, 0.08), 7.25, 0.18)
    # --- cut whoosh + wink "pling"
    add(lp_fast(rng.standard_normal(int(0.25 * SR)), 6) * np.linspace(0, 1, int(0.25 * SR)), T_CLOSE - 0.22, 0.25)
    add(tone(1568, 0.6, 0.002, 0.3) + 0.5 * tone(2349, 0.6, 0.002, 0.25), T_WINK, 0.22)
    add(ssum(tone(523, 0.5, 0.003, 0.3), tone(659, 0.5, 0.003, 0.3), tone(784, 0.6, 0.003, 0.35)), T_END_TXT, 0.14)

    # --- voices
    import wave
    for lid, l in LINES.items():
        with wave.open(l["wav"]) as wf:
            v = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).astype(np.float64) / 32768
        add(v * 1.15, T_LINE[lid] - l["lead"])

    mix = np.tanh(mix * 1.1) * 0.92
    pcm = (mix * 32767).astype(np.int16)
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
