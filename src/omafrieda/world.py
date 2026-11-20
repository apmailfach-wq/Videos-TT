"""Kulissen + Einstellungen (Shots) für 'Oma Frieda Faust – Folge 1'."""
import math
import random
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from chars import bonbon_sprite, handbag, person, pigeon
from gfx import (F_BLACK, F_HAND, F_INTER, H, W, blur, clamp01, ease_io, ease_out, ell, emoji, font, glow, grade,
                 gradient, lerp, limb, mixc, paste_c, poly, rrect, soft_shadow, text_img, vignette)

# wird von render.py gesetzt: Mundöffnung je Sprecher-Gruppe zur globalen Zeit T
MOUTH = {"fn": lambda who, T: 0.0}


def mouth(who, T):
    return MOUTH["fn"](who, T)


def blink(T, seed=0):
    return ((T * 1000 + seed * 977) % 3100) < 110


# ------------------------------------------------------------------ Kamera / Statische Hintergründe
class View:
    def __init__(self, z=1.0, cx=W / 2, cy=H / 2, shake=(0.0, 0.0)):
        if z >= 1:
            cx = min(max(cx, W / (2 * z)), W - W / (2 * z))
            cy = min(max(cy, H / (2 * z)), H - H / (2 * z))
        self.z, self.cx, self.cy = z, cx, cy
        self.sh = shake

    def p(self, x, y):
        return ((x - self.cx) * self.z + W / 2 + self.sh[0], (y - self.cy) * self.z + H / 2 + self.sh[1])


def view_bg(static, K, v, blur_r=0.0):
    w, h = W / v.z, H / v.z
    x0 = (v.cx - v.sh[0] / v.z) - w / 2
    y0 = (v.cy - v.sh[1] / v.z) - h / 2
    box = (x0 * K, y0 * K, (x0 + w) * K, (y0 + h) * K)
    img = static.transform((W, H), Image.EXTENT, box, resample=Image.BILINEAR)
    if blur_r > 0.3:
        img = img.filter(ImageFilter.GaussianBlur(blur_r))
    return img


def actor(frame, v, who, D, pose, x, y, rot=0.0, flip=False, center=False, alpha=1.0, **kw):
    """Zeichnet eine Figur. (x, y) = Nacken (Weltkoordinaten) oder Sprite-Mitte, wenn center=True."""
    im, (nx, ny), sc = person(who, D * v.z, pose, **kw)
    if flip:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    sx, sy = v.p(x, y)
    Dz = D * v.z
    if center:
        paste_c(frame, im, sx, sy, sc, alpha, rot)
    else:
        paste_c(frame, im, sx, sy + (im.height / 2 - ny) * sc, sc, alpha, rot)
    return Dz


# ------------------------------------------------------------------ PARK
FOUNT = (380, 1120)
BENCH_X = 800
SEAT_Y = 1150
OMA_D = 118
OMA_NECK = (BENCH_X, SEAT_Y - 1.25 * OMA_D)


def _tree(c, x, y, r, K, col):
    rrect(c, (x - r * 0.12) * K, y * K, (x + r * 0.12) * K, (y + r * 1.4) * K, r * 0.1 * K, (110, 76, 50), amb=0.5)
    for dx, dy, rr in ((0, -0.2, 1.0), (-0.6, 0.25, 0.75), (0.6, 0.2, 0.8), (0.0, 0.45, 0.7)):
        ell(c, (x + dx * r) * K, (y + dy * r) * K, rr * r * K, rr * r * 0.92 * K, col, amb=0.5, spec=0.08,
            radius=rr * r * K * 0.6)


@lru_cache(maxsize=2)
def park_static(K=2):
    rnd = random.Random(3)
    c = gradient(W * K, H * K, [(0, (84, 165, 245)), (0.3, (140, 200, 250)), (0.46, (210, 236, 252)),
                                (0.461, (130, 200, 95)), (0.7, (104, 182, 80)), (1.0, (78, 156, 64))])
    g = glow(int(900 * K), (255, 240, 190), 1.8, 0.9)
    c.alpha_composite(g, (int(880 * K - g.width / 2), int(220 * K - g.height / 2)))
    ell(c, 880 * K, 220 * K, 70 * K, 70 * K, (255, 250, 225), amb=1.0, spec=0.0)
    for (x, y, s) in ((180, 260, 1.0), (620, 150, 0.8), (980, 420, 0.7)):
        for dx, dy, rr in ((0, 0, 70), (-70, 15, 50), (75, 12, 55), (35, -30, 55)):
            ell(c, (x + dx * s) * K, (y + dy * s) * K, rr * s * K, rr * s * 0.8 * K, (255, 255, 255), amb=0.85,
                spec=0.0)
    # Bäume hinten
    cols = [(64, 140, 74), (84, 160, 84), (56, 124, 66), (96, 170, 90)]
    for i in range(9):
        x = -40 + i * 145 + rnd.randint(-30, 30)
        _tree(c, x, 690 + rnd.randint(-40, 30), 110 + rnd.randint(-20, 30), K, cols[i % 4])
    rrect(c, -40 * K, 835 * K, 1120 * K, 905 * K, 30 * K, (60, 130, 64), amb=0.5, spec=0.05)
    # Rasen-Textur
    d = ImageDraw.Draw(c)
    for _ in range(9000):
        x = rnd.uniform(0, W)
        y = rnd.uniform(900, H)
        l = 6 + (y - 900) / 60
        col = (90, 170, 70, 120) if rnd.random() < 0.5 else (150, 215, 110, 110)
        d.line([(x * K, y * K), ((x + rnd.uniform(-2, 2)) * K, (y - l) * K)], fill=col, width=max(1, int(K)))
    # Platz um den Brunnen + Weg
    pl = Image.new("RGBA", c.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(pl)
    pd.polygon([(470 * K, 905 * K), (650 * K, 905 * K), (1080 * K, 1380 * K), (1080 * K, 1760 * K), (700 * K, 1260 * K)],
               fill=(226, 206, 168))
    pd.ellipse([(FOUNT[0] - 480) * K, (FOUNT[1] - 150) * K, (FOUNT[0] + 560) * K, (FOUNT[1] + 260) * K],
               fill=(232, 213, 176))
    pl = pl.filter(ImageFilter.GaussianBlur(3 * K))
    c.alpha_composite(pl)
    for _ in range(2500):
        x, y = rnd.uniform(0, W), rnd.uniform(960, 1500)
        dx, dy = (x - FOUNT[0] - 40) / 520, (y - FOUNT[1] - 55) / 205
        if dx * dx + dy * dy < 1:
            s = rnd.uniform(1, 2.5)
            d.ellipse([x * K, y * K, (x + s) * K, (y + s) * K], fill=(190, 170, 135, 140))
    # Blumenbeete
    for (bx, by) in ((110, 1760), (1000, 1880), (60, 1010)):
        ell(c, bx * K, by * K, 170 * K, 70 * K, (70, 140, 60), amb=0.5)
        for _ in range(40):
            fx, fy = bx + rnd.uniform(-150, 150), by + rnd.uniform(-55, 40)
            col = rnd.choice([(255, 80, 90), (255, 210, 60), (255, 140, 190), (250, 250, 250)])
            r = rnd.uniform(7, 12)
            d.ellipse([(fx - r) * K, (fy - r) * K, (fx + r) * K, (fy + r) * K], fill=col)
            d.ellipse([(fx - 3) * K, (fy - 3) * K, (fx + 3) * K, (fy + 3) * K], fill=(255, 230, 120))
    # Laterne
    rrect(c, 1010 * K, 760 * K, 1028 * K, 1150 * K, 8 * K, (40, 46, 52), amb=0.5, spec=0.4)
    rrect(c, 990 * K, 720 * K, 1048 * K, 780 * K, 14 * K, (40, 46, 52), amb=0.5, spec=0.4)
    ell(c, 1019 * K, 750 * K, 18 * K, 18 * K, (255, 240, 200), amb=1.0)
    # Brunnen
    fx, fy = FOUNT
    soft_shadow(c, fx * K, (fy + 125) * K, 330 * K, 40 * K, 0.35)
    rrect(c, (fx - 300) * K, (fy - 10) * K, (fx + 300) * K, (fy + 118) * K, 50 * K, (206, 200, 194), amb=0.5,
          spec=0.12, radius=40 * K)
    ell(c, fx * K, fy * K, 304 * K, 80 * K, (226, 221, 214), amb=0.55, spec=0.15, radius=30 * K)
    ell(c, fx * K, (fy + 2) * K, 270 * K, 60 * K, (74, 160, 222), amb=0.65, spec=0.35, radius=25 * K)
    d = ImageDraw.Draw(c)
    for k in range(5):
        y = fy - 30 + k * 13
        d.arc([(fx - 220 + k * 18) * K, (y - 10) * K, (fx + 220 - k * 18) * K, (y + 10) * K], 200, 340,
              fill=(200, 235, 255, 170), width=int(3 * K))
    rrect(c, (fx - 28) * K, 950 * K, (fx + 28) * K, (fy + 5) * K, 14 * K, (210, 204, 198), amb=0.5, spec=0.15)
    ell(c, fx * K, 955 * K, 122 * K, 32 * K, (222, 216, 208), amb=0.55, spec=0.15)
    ell(c, fx * K, 952 * K, 104 * K, 20 * K, (80, 166, 225), amb=0.65, spec=0.3)
    rrect(c, (fx - 12) * K, 900 * K, (fx + 12) * K, 950 * K, 8 * K, (210, 204, 198), amb=0.5, spec=0.2)
    ell(c, fx * K, 898 * K, 20 * K, 20 * K, (222, 216, 208), amb=0.55, spec=0.3)
    # Bank
    bx = BENCH_X
    soft_shadow(c, bx * K, (SEAT_Y + 120) * K, 250 * K, 30 * K, 0.35)
    wood = (176, 112, 62)
    for y0 in (975, 1015, 1055):
        rrect(c, (bx - 215) * K, y0 * K, (bx + 215) * K, (y0 + 28) * K, 12 * K, wood, amb=0.5, spec=0.15)
    for sx in (-1, 1):
        rrect(c, (bx + sx * 185 - 9) * K, 960 * K, (bx + sx * 185 + 9) * K, (SEAT_Y + 115) * K, 8 * K, (52, 54, 60),
              amb=0.45, spec=0.4)
    rrect(c, (bx - 225) * K, (SEAT_Y - 22) * K, (bx + 225) * K, (SEAT_Y + 8) * K, 12 * K, mixc(wood, (255, 255, 255), 0.08),
          amb=0.55, spec=0.15)
    rrect(c, (bx - 225) * K, (SEAT_Y + 6) * K, (bx + 225) * K, (SEAT_Y + 26) * K, 8 * K, (140, 86, 46), amb=0.45)
    for sx in (-1, 1):
        rrect(c, (bx + sx * 205 - 10) * K, (SEAT_Y + 20) * K, (bx + sx * 205 + 10) * K, (SEAT_Y + 118) * K, 8 * K,
              (52, 54, 60), amb=0.45, spec=0.4)
        d.arc([(bx + sx * 215 - 40) * K, (SEAT_Y - 80) * K, (bx + sx * 215 + 40) * K, (SEAT_Y + 10) * K],
              180 if sx < 0 else 270, 270 if sx < 0 else 360, fill=(52, 54, 60), width=int(10 * K))
    return c


@lru_cache(maxsize=1)
def fountain_front(K=2):
    """Vordere Brunnenwand als eigene Ebene (um den Dieb 'im Wasser' sitzen zu lassen)."""
    full = park_static(K)
    fx, fy = FOUNT
    box = (int((fx - 310) * K), int((fy + 8) * K), int((fx + 310) * K), int((fy + 125) * K))
    crop = full.crop(box)
    m = Image.new("L", crop.size, 0)
    md = ImageDraw.Draw(m)
    md.rectangle([0, 0, crop.width, crop.height], fill=255)
    # obere Kante: elliptischer Vorderrand des Beckens
    md.ellipse([(-4) * K, (-8 - 80 - 8) * K, (620 + 4) * K, (-8 + 80 - 4) * K], fill=0)
    md.rectangle([0, 0, crop.width, int(2 * K)], fill=0)
    ring = Image.new("L", crop.size, 0)
    ImageDraw.Draw(ring).ellipse([(310 - 304) * K, (-8 - 80) * K, (310 + 304) * K, (-8 + 80) * K], fill=255)
    inner = Image.new("L", crop.size, 0)
    ImageDraw.Draw(inner).ellipse([(310 - 272) * K, (-6 - 62) * K, (310 + 272) * K, (-6 + 62) * K], fill=255)
    ring_np = np.clip(np.asarray(ring, np.int16) - np.asarray(inner, np.int16), 0, 255).astype(np.uint8)
    m = Image.fromarray(np.maximum(np.asarray(m), ring_np))
    crop.putalpha(m)
    return crop, box


def draw_fountain_front(frame, v, K=2):
    crop, box = fountain_front(K)
    x0, y0 = box[0] / K, box[1] / K
    sx, sy = v.p(x0, y0)
    sc = v.z / K
    im = crop.resize((max(1, int(crop.width * sc)), max(1, int(crop.height * sc))), Image.BILINEAR)
    frame.alpha_composite(im, (int(sx), int(sy))) if sx >= 0 and sy >= 0 else paste_c(
        frame, im, sx + im.width / 2, sy + im.height / 2)


def water_jet(frame, v, T, frozen=False):
    d = ImageDraw.Draw(frame, "RGBA")
    fx = FOUNT[0]
    tt = T if not frozen else 0.37
    for k in range(26):
        ph = (tt * 1.6 + k / 26) % 1.0
        side = -1 if k % 2 else 1
        spread = 40 + (k % 5) * 12
        x = fx + side * spread * ph
        y = 900 - 70 * (4 * ph * (1 - ph)) + 55 * ph * ph
        r = (4 + (k % 3)) * v.z
        sx, sy = v.p(x, y)
        d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(220, 240, 255, 200))
    # Überlauf der Schale
    for k in range(18):
        ph = (tt * 1.3 + k / 18) % 1.0
        side = -1 if k % 2 else 1
        x = fx + side * (100 + 25 * ph)
        y = 960 + 150 * ph * ph
        sx, sy = v.p(x, y)
        r = 3.5 * v.z
        d.ellipse([sx - r, sy - r * 1.6, sx + r, sy + r * 1.6], fill=(215, 238, 255, 170))


def pigeons(frame, v, T, flock, scare_t=None):
    """flock: Liste (x, y, size, facing, seed). Nach scare_t fliegen sie auf."""
    for i, (x, y, s, f, seed) in enumerate(flock):
        if scare_t is not None and T >= scare_t:
            dt = T - scare_t
            fx = x + f * (180 + seed * 20) * dt + f * 60 * dt * dt
            fy = y - (420 + seed * 30) * dt
            img = pigeon(int(s * v.z), int((T * 14 + seed) % 4), f)
            paste_c(frame, img, *v.p(fx, fy))
        else:
            peck = 1 if ((T * 2.2 + seed * 0.37) % 1.0) < 0.35 else 0
            img = pigeon(int(s * v.z), -1, f, peck)
            sx, sy = v.p(x, y)
            soft_shadow(frame, sx, sy + s * 0.75 * v.z, s * 0.5 * v.z, s * 0.12 * v.z, 0.3)
            paste_c(frame, img, sx, sy)


FLOCK = [(560, 1290, 60, 1, 1), (660, 1330, 58, -1, 2), (500, 1370, 62, 1, 3), (720, 1395, 56, -1, 4),
         (610, 1440, 60, 1, 5)]


# ------------------------------------------------------------------ Flugbahn des Diebs
P0, P1, P2 = (610, 990), (470, 380), (410, 1060)


def fly_pos(s):
    s = clamp01(s)
    x = (1 - s) ** 2 * P0[0] + 2 * (1 - s) * s * P1[0] + s * s * P2[0]
    y = (1 - s) ** 2 * P0[1] + 2 * (1 - s) * s * P1[1] + s * s * P2[1]
    return x, y


def fly_rot(s):
    return -15 - 330 * s


def bonbon_rain(frame, v, s_now, T, seed=11):
    """Bonbons fallen aus der Tasche des fliegenden Diebs."""
    rnd = random.Random(seed)
    for k in range(26):
        s0 = 0.22 + rnd.random() * 0.6
        if s_now < s0:
            continue
        bx, by = fly_pos(s0)
        dt = (s_now - s0) * 1.4
        vx = rnd.uniform(-160, 160)
        vy = rnd.uniform(-260, -60)
        x = bx + vx * dt + 40
        y = by + vy * dt + 900 * dt * dt - 40
        rot = int((rnd.uniform(-400, 400) * dt) // 30 * 30) % 360
        col = (235, 60, 60) if k % 3 else (250, 160, 40)
        im = bonbon_sprite(max(8, int(26 * v.z)), col, rot)
        paste_c(frame, im, *v.p(x, y))


def splash(frame, v, dt, seed=5, cx=None, cy=None, scale=1.0):
    if dt < 0 or dt > 1.6:
        return
    cx = FOUNT[0] + 30 if cx is None else cx
    cy = FOUNT[1] if cy is None else cy
    rnd = random.Random(seed)
    lay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    # Wassersäule
    if dt < 0.7:
        a = 1 - dt / 0.7
        for k in range(14):
            ang = math.radians(-90 + rnd.uniform(-50, 50))
            h = rnd.uniform(140, 330) * scale * ease_out(dt / 0.25)
            x = cx + math.cos(ang) * h * 0.6
            y = cy + math.sin(ang) * h
            r = rnd.uniform(26, 46) * scale * v.z
            sx, sy = v.p(x, y)
            d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(225, 243, 255, int(220 * a)))
    for k in range(70):
        ang = math.radians(rnd.uniform(-170, -10))
        sp = rnd.uniform(250, 720) * scale
        x = cx + math.cos(ang) * sp * dt
        y = cy + math.sin(ang) * sp * dt + 900 * dt * dt
        r = rnd.uniform(4, 10) * v.z * scale
        sx, sy = v.p(x, y)
        al = int(230 * clamp01(1.3 - dt))
        d.ellipse([sx - r, sy - r * 1.3, sx + r, sy + r * 1.3], fill=(170, 220, 255, al))
        d.ellipse([sx - r * 0.4, sy - r * 0.8, sx + r * 0.1, sy - r * 0.2], fill=(255, 255, 255, al))
    # Ring
    rr = 120 + 330 * ease_out(dt / 0.9)
    sx, sy = v.p(cx, cy + 10)
    d.ellipse([sx - rr * v.z, sy - rr * 0.22 * v.z, sx + rr * v.z, sy + rr * 0.22 * v.z],
              outline=(240, 250, 255, int(200 * clamp01(1 - dt / 0.9))), width=int(8 * v.z))
    frame.alpha_composite(lay)


def park_frame(T, v, oma=None, thief=None, extras=(), bg_blur=0.0, jet_frozen=False, flock_scare=None,
               flock_T=None, passers=None):
    f = view_bg(park_static(2), 2, v, bg_blur).copy()
    water_jet(f, v, T, jet_frozen)
    if passers:
        for p in passers:
            actor(f, v, **p)
    if flock_T is not None or flock_scare is not None:
        pigeons(f, v, flock_T if flock_T is not None else T, FLOCK, flock_scare)
    for e in extras:
        if e[0] == "pre":
            e[1](f, v)
    if thief and thief.get("_behind"):
        actor(f, v, **{k: val for k, val in thief.items() if k != "_behind"})
    if oma:
        actor(f, v, **oma)
    if thief and not thief.get("_behind"):
        actor(f, v, **thief)
    for e in extras:
        if e[0] == "post":
            e[1](f, v)
    return f


def oma_bench(T, **kw):
    base = dict(who="oma", D=OMA_D, pose="oma_sit_knit", x=OMA_NECK[0], y=OMA_NECK[1], expr="smile",
                look=(0.0, 0.55), items=(("knit", (0, 1.0)),), knit_phase=round((T * 2.5) % 1.0, 1),
                blink=blink(T, 1))
    base.update(kw)
    return base


def thief_fly(s, T, mouth_v=0.0, frozen=False):
    x, y = fly_pos(s)
    return dict(who="thief", D=118, pose="thief_fly", x=x, y=y, rot=fly_rot(s), center=True, expr="shock",
                mouth=mouth_v, items=(("bag", (1.35, -0.4)),))


# ------------------------------------------------------------------ BUS
@lru_cache(maxsize=1)
def bus_static(K=2):
    c = gradient(W * K, H * K, [(0, (190, 192, 200)), (0.17, (210, 212, 218)), (0.171, (236, 228, 210)),
                                (0.75, (224, 214, 194)), (0.751, (110, 116, 132)), (1.0, (80, 84, 98))])
    d = ImageDraw.Draw(c)
    for x in (200, 540, 880):
        rrect(c, (x - 120) * K, 120 * K, (x + 120) * K, 160 * K, 18 * K, (255, 252, 235), amb=0.95, spec=0.0)
    rrect(c, -20 * K, 300 * K, 1100 * K, 330 * K, 10 * K, (230, 190, 40), amb=0.5, spec=0.5)
    for x in range(100, 1050, 160):
        d.line([(x * K, 330 * K), (x * K, 400 * K)], fill=(40, 40, 46), width=int(6 * K))
        d.ellipse([(x - 22) * K, 395 * K, (x + 22) * K, 450 * K], outline=(240, 200, 40), width=int(8 * K))
    # Fenster (Inhalt dynamisch) – nur Rahmen
    for (x0, x1) in ((60, 525), (555, 1020)):
        d.rounded_rectangle([x0 * K, 470 * K, x1 * K, 900 * K], radius=34 * K, fill=(0, 0, 0, 0))
    for y in range(1460, 1920, 80):
        d.line([(0, y * K), (W * K, (y + 30) * K)], fill=(96, 100, 116), width=int(5 * K))
    rrect(c, -20 * K, 1440 * K, 1100 * K, 1460 * K, 6 * K, (240, 200, 40), amb=0.6)
    # Sitze
    for i, x in enumerate((290, 540, 790)):
        rrect(c, (x - 118) * K, 930 * K, (x + 118) * K, 1250 * K, 40 * K, (38, 86, 168), amb=0.45, spec=0.12,
              radius=40 * K)
        rrect(c, (x - 92) * K, 905 * K, (x + 92) * K, 975 * K, 26 * K, (30, 70, 140), amb=0.45, spec=0.12)
        rnd = random.Random(i)
        for _ in range(60):
            px, py = x + rnd.uniform(-100, 100), rnd.uniform(950, 1230)
            col = rnd.choice([(250, 200, 50, 160), (240, 80, 90, 150), (90, 200, 220, 150)])
            d.rectangle([px * K, py * K, (px + 7) * K, (py + 4) * K], fill=col)
        rrect(c, (x - 124) * K, 1235 * K, (x + 124) * K, 1325 * K, 30 * K, (48, 100, 190), amb=0.45, spec=0.15)
        rrect(c, (x - 100) * K, 1320 * K, (x + 100) * K, 1440 * K, 10 * K, (60, 62, 72), amb=0.45, spec=0.2)
    return c


@lru_cache(maxsize=1)
def bus_window_mask(K=2):
    m = Image.new("L", (W * K, H * K), 0)
    d = ImageDraw.Draw(m)
    for (x0, x1) in ((60, 525), (555, 1020)):
        d.rounded_rectangle([(x0 + 12) * K, 482 * K, (x1 - 12) * K, 888 * K], radius=26 * K, fill=255)
    return m


@lru_cache(maxsize=1)
def city_strip():
    rnd = random.Random(8)
    w, h = 3000, 430
    c = gradient(w, h, [(0, (120, 190, 245)), (1, (200, 230, 250))])
    d = ImageDraw.Draw(c)
    x = 0
    while x < w:
        bw = rnd.randint(110, 220)
        bh = rnd.randint(150, 380)
        col = rnd.choice([(240, 170, 120), (250, 220, 150), (180, 200, 220), (230, 140, 140), (200, 220, 170)])
        d.rounded_rectangle([x, h - bh, x + bw, h + 20], radius=10, fill=col)
        for wy in range(h - bh + 20, h - 20, 46):
            for wx in range(x + 16, x + bw - 30, 40):
                d.rectangle([wx, wy, wx + 22, wy + 28], fill=(255, 250, 230) if rnd.random() < 0.3 else (90, 120, 160))
        x += bw + rnd.randint(4, 30)
    for k in range(0, w, 260):
        d.ellipse([k, h - 140, k + 120, h - 20], fill=(70, 150, 80))
        d.rectangle([k + 52, h - 40, k + 68, h], fill=(110, 80, 50))
    return c.filter(ImageFilter.GaussianBlur(1.5))


def bus_frame(T, v, actors_, blur_r=0.0, shake=0.0):
    K = 2
    base = bus_static(K).copy()
    city = city_strip()
    off = int((T * 900) % (city.width - W))
    strip = city.crop((off, 0, off + W, city.height)).resize((W * K, int(city.height * K)), Image.BILINEAR)
    win = Image.new("RGBA", base.size, (0, 0, 0, 0))
    win.paste(strip, (0, 470 * K))
    win.putalpha(bus_window_mask(K))
    base.alpha_composite(win)
    # Spiegelung
    gl = Image.new("RGBA", base.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(gl)
    for x in (120, 620):
        gd.polygon([(x * K, 888 * K), ((x + 90) * K, 888 * K), ((x + 300) * K, 482 * K), ((x + 210) * K, 482 * K)],
                   fill=(255, 255, 255, 50))
    gl.putalpha(Image.fromarray(np.minimum(np.asarray(gl.getchannel("A")), np.asarray(bus_window_mask(K)))))
    base.alpha_composite(gl)
    f = view_bg(base, K, v, blur_r).copy()
    for a in actors_:
        actor(f, v, **a)
    # Haltestangen vorne
    for x in (40, 1050):
        sx, _ = v.p(x, 0)
        if -60 < sx < W + 60:
            rrect(f, sx - 16 * v.z, 0, sx + 16 * v.z, H, 14 * v.z, (250, 200, 40), amb=0.5, spec=0.6, shine=30)
    return f


# ------------------------------------------------------------------ GYM
@lru_cache(maxsize=1)
def gym_static(K=2):
    c = gradient(W * K, H * K, [(0, (28, 30, 46)), (0.68, (52, 56, 80)), (0.681, (34, 34, 40)), (1.0, (22, 22, 26))])
    d = ImageDraw.Draw(c)
    for x in range(0, W, 180):
        d.line([(x * K, 0), (x * K, 1300 * K)], fill=(40, 44, 62), width=int(6 * K))
    # Spiegel
    rrect(c, 70 * K, 430 * K, 1010 * K, 1150 * K, 16 * K, (70, 80, 110), amb=0.7, spec=0.1, radius=10 * K)
    for x in (160, 520):
        d.polygon([(x * K, 1150 * K), ((x + 80) * K, 1150 * K), ((x + 330) * K, 430 * K), ((x + 250) * K, 430 * K)],
                  fill=(160, 180, 220, 40))
    # Neon-Schriftzug
    tg = text_img("POWER GYM", 96, (255, 150, 60), F_BLACK, stroke=0, shadow=False)
    gl = Image.new("RGBA", tg.size, (255, 120, 40, 0))
    gl.putalpha(tg.getchannel("A").filter(ImageFilter.GaussianBlur(14)))
    for im in (gl, gl, tg):
        c.alpha_composite(im.resize((im.width * K, im.height * K)), (int((540 - tg.width / 2) * K), int(230 * K)))
    # Hantelablage
    rrect(c, 80 * K, 1215 * K, 1000 * K, 1245 * K, 10 * K, (120, 124, 136), amb=0.5, spec=0.5)
    for i, x in enumerate(range(130, 980, 95)):
        col = [(220, 60, 60), (60, 140, 230), (250, 200, 50), (60, 190, 120)][i % 4]
        for sx in (-1, 1):
            ell(c, (x + sx * 28) * K, 1195 * K, 20 * K, 26 * K, col, amb=0.45, spec=0.4)
        rrect(c, (x - 26) * K, 1190 * K, (x + 26) * K, 1200 * K, 4 * K, (200, 204, 214), amb=0.5, spec=0.6)
    # Boden-Sprenkel
    rnd = random.Random(4)
    for _ in range(3000):
        x, y = rnd.uniform(0, W), rnd.uniform(1310, H)
        d.point((x * K, y * K), fill=(70, 70, 80))
    # Lichtkegel
    lc = Image.new("RGBA", c.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lc)
    ld.polygon([(450 * K, 0), (630 * K, 0), (900 * K, 1920 * K), (180 * K, 1920 * K)], fill=(255, 240, 200, 38))
    ld.ellipse([200 * K, 1600 * K, 880 * K, 1880 * K], fill=(255, 240, 200, 40))
    c.alpha_composite(lc.filter(ImageFilter.GaussianBlur(30 * K)))
    return c


def gym_frame(T, v, actors_, blur_r=0.0, pre=None, post=None):
    f = view_bg(gym_static(2), 2, v, blur_r).copy()
    if pre:
        pre(f, v)
    for a in actors_:
        actor(f, v, **a)
    if post:
        post(f, v)
    return f


# ------------------------------------------------------------------ 70er-Foto
@lru_cache(maxsize=1)
def photo_static():
    w, h = 820, 1040
    c = gradient(w, h, [(0, (200, 190, 170)), (0.66, (215, 205, 185)), (0.661, (190, 175, 140)), (1, (170, 155, 120))])
    d = ImageDraw.Draw(c)
    for x in range(0, w, 160):
        d.rectangle([x, 0, x + 18, int(h * 0.66)], fill=(150, 120, 90))
    d.rectangle([0, 120, w, 140], fill=(150, 120, 90))
    for y in range(int(h * 0.66), h, 70):
        d.line([(0, y), (w, y)], fill=(150, 135, 100), width=4)
    # Banner
    rrect(c, 90, 180, 290, 560, 10, (240, 236, 225), amb=0.7)
    d.text((190, 370), "柔道", font=font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60), fill=(40, 40, 40),
           anchor="mm") if False else None
    for k in range(3):
        d.rectangle([150, 230 + k * 110, 230, 300 + k * 110], fill=(60, 50, 50))
    im, (nx, ny), sc = person("young", 175, "young_trophy", expr="proud", mouth_kind="grin",
                              items=(("trophy", (0.7, -0.55)),))
    paste_c(c, im, 470, 400 + (im.height / 2 - ny) * sc, sc)
    g = np.asarray(c.convert("L"), np.float32)
    g = (g - 128) * 1.25 + 128
    rgb = np.stack([g * 1.05 + 8, g * 0.98 + 4, g * 0.86], axis=2)
    photo = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")
    # Rahmen
    fr = Image.new("RGBA", (w + 80, h + 200), (246, 240, 226, 255))
    fr.alpha_composite(photo, (40, 40))
    fd = ImageDraw.Draw(fr)
    fd.text((fr.width / 2, h + 120), "Frieda, 1976 – Landesmeisterin", font=font(F_HAND, 64), fill=(40, 40, 60),
            anchor="mm")
    rnd = random.Random(2)
    for _ in range(14):
        x = rnd.uniform(40, w + 40)
        fd.line([(x, 40), (x + rnd.uniform(-20, 20), h + 40)], fill=(255, 255, 255, 60), width=1)
    return fr


@lru_cache(maxsize=1)
def table_bg():
    c = gradient(W, H, [(0, (40, 26, 18)), (1, (24, 14, 10))])
    d = ImageDraw.Draw(c)
    rnd = random.Random(1)
    for y in range(0, H, 6):
        d.line([(0, y), (W, y + rnd.uniform(-4, 4))], fill=(60, 38, 26, 60), width=2)
    c.alpha_composite(vignette(0.8))
    return c


def grain(frame, T, amt=18):
    rnd = np.random.default_rng(int(T * 30))
    n = rnd.normal(0, amt, (H // 2, W // 2)).astype(np.float32)
    n = np.repeat(np.repeat(n, 2, 0), 2, 1)
    a = np.asarray(frame.convert("RGB"), np.float32) + n[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")


# ------------------------------------------------------------------ Himmel (Heldenshot / Endkarte)
@lru_cache(maxsize=2)
def hero_sky(kind="hero"):
    if kind == "hero":
        c = gradient(W, H, [(0, (40, 70, 160)), (0.45, (250, 150, 90)), (0.75, (255, 200, 120)), (1, (255, 230, 170))])
    else:
        c = gradient(W, H, [(0, (70, 30, 120)), (0.5, (200, 60, 120)), (1, (255, 150, 60))])
    return c


def rays(frame, cx, cy, T, col=(255, 240, 200), alpha=60, n=14, speed=8):
    lay = Image.new("RGBA", (W // 2, H // 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for k in range(n):
        a0 = math.radians(k * 360 / n + T * speed)
        a1 = a0 + math.radians(360 / n * 0.45)
        R = 2200
        d.polygon([(cx / 2, cy / 2), (cx / 2 + math.cos(a0) * R, cy / 2 + math.sin(a0) * R),
                   (cx / 2 + math.cos(a1) * R, cy / 2 + math.sin(a1) * R)], fill=col + (alpha,))
    lay = lay.filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
    frame.alpha_composite(lay)


def rim_glow(frame, sprite_alpha_img, pos, color=(255, 230, 170), strength=1.0):
    """Gegenlicht-Saum um eine Figur."""
    a = sprite_alpha_img.getchannel("A")
    er = a.filter(ImageFilter.MinFilter(9))
    edge = Image.fromarray(np.clip(np.asarray(a, np.int16) - np.asarray(er, np.int16), 0, 255).astype(np.uint8))
    edge = edge.filter(ImageFilter.GaussianBlur(3)).point(lambda v: min(255, int(v * 1.6 * strength)))
    g = Image.new("RGBA", a.size, color + (0,))
    g.putalpha(edge)
    frame.alpha_composite(g, pos)


def scarf(frame, x, y, D, T, toward=1):
    """Rosa Strickschal als flaches, flatterndes Band ab (x, y)."""
    n = 14
    pts = []
    for k in range(n + 1):
        u = k / n
        px = x + toward * u * D * 2.2
        py = y + u * D * 0.45 + math.sin(T * 9 - u * 6) * D * 0.2 * u
        pts.append((px, py))
    top, bot = [], []
    for k, (px, py) in enumerate(pts):
        u = k / n
        wdt = D * (0.26 - 0.06 * u) * (0.75 + 0.25 * math.cos(T * 9 - u * 6))
        top.append((px, py - wdt / 2))
        bot.append((px, py + wdt / 2))
    poly(frame, top + bot[::-1], (247, 140, 182), radius=D * 0.05, amb=0.55, spec=0.15)
    d = ImageDraw.Draw(frame)
    for k in range(1, n):
        d.line([top[k], bot[k]], fill=(222, 105, 150), width=max(2, int(D * 0.015)))
    for j in range(6):
        u = j / 5
        ex = lerp(top[-1][0], bot[-1][0], u)
        ey = lerp(top[-1][1], bot[-1][1], u)
        d.line([(ex, ey), (ex + toward * D * 0.12, ey + D * 0.03)], fill=(247, 140, 182), width=max(2, int(D * 0.03)))
