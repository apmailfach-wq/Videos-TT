"""Kulissen für Folge 2: Schulhof (Tischtennisplatte, Sandkasten) und Klassenzimmer (Tafel- und Klassenblick)."""
import math
import random
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "omafrieda"))
from gfx import F_BLACK, F_HAND, H, W, ell, font, glow, gradient, limb, poly, rrect, soft_shadow  # noqa: E402

K = 2

# ------------------------------------------------------------------ Schulhof
TABLE = (470, 1250)
SAND = (265, 1540)


@lru_cache(maxsize=1)
def yard_static():
    c = gradient(W * K, H * K, [(0, (110, 180, 245)), (0.16, (170, 215, 250)), (0.161, (196, 92, 70)),
                                (0.51, (176, 80, 60)), (0.511, (178, 178, 186)), (1.0, (150, 150, 160))])
    d = ImageDraw.Draw(c)
    # Ziegelfugen
    for y in range(310, 980, 22):
        d.line([(0, y * K), (W * K, y * K)], fill=(160, 70, 52), width=K)
        off = 0 if (y // 22) % 2 else 30
        for x in range(off, W, 60):
            d.line([(x * K, y * K), (x * K, (y + 22) * K)], fill=(160, 70, 52), width=K)
    # Dach + Schild
    rrect(c, -20 * K, 290 * K, 1100 * K, 330 * K, 10 * K, (90, 90, 100), amb=0.5, spec=0.2)
    rrect(c, 330 * K, 350 * K, 750 * K, 430 * K, 14 * K, (250, 250, 245), amb=0.8, spec=0.1)
    d.text((540 * K, 392 * K), "SCHULE", font=font(F_BLACK, 52 * K), fill=(40, 70, 140), anchor="mm")
    # Fenster
    for row in range(2):
        for col in range(5):
            if row == 1 and col == 2:
                continue
            x0 = 60 + col * 200
            y0 = 470 + row * 260
            rrect(c, x0 * K, y0 * K, (x0 + 150) * K, (y0 + 190) * K, 10 * K, (245, 245, 245), amb=0.8)
            g = gradient(int(130 * K), int(170 * K), [(0, (150, 210, 250)), (1, (90, 150, 210))])
            c.alpha_composite(g, (int((x0 + 10) * K), int((y0 + 10) * K)))
            d.line([((x0 + 75) * K, (y0 + 10) * K), ((x0 + 75) * K, (y0 + 180) * K)], fill=(245, 245, 245), width=4 * K)
    # Tür
    rrect(c, 470 * K, 730 * K, 610 * K, 985 * K, 12 * K, (60, 110, 170), amb=0.5, spec=0.2)
    d.ellipse([585 * K, 850 * K, 597 * K, 862 * K], fill=(240, 200, 60))
    # Baum rechts
    rrect(c, 950 * K, 820 * K, 985 * K, 1150 * K, 10 * K, (110, 76, 50), amb=0.5)
    for dx, dy, r in ((0, 0, 130), (-90, 60, 90), (80, 70, 95)):
        ell(c, (968 + dx) * K, (760 + dy) * K, r * K, r * 0.9 * K, (70, 150, 75), amb=0.5, spec=0.08)
    # Hüpfkästchen
    for k in range(5):
        y0 = 1640 + k * 0
        x0 = 640 + k * 80
        d.rectangle([x0 * K, 1700 * K, (x0 + 76) * K, 1780 * K], outline=(255, 255, 255), width=4 * K)
        d.text(((x0 + 38) * K, 1740 * K), str(k + 1), font=font(F_BLACK, 40 * K), fill=(255, 230, 80), anchor="mm")
    rnd = random.Random(3)
    for _ in range(3000):
        x, y = rnd.uniform(0, W), rnd.uniform(990, H)
        d.point((x * K, y * K), fill=(140, 140, 150))
    # Sandkasten
    sx, sy = SAND
    soft_shadow(c, sx * K, (sy + 95) * K, 230 * K, 30 * K, 0.35)
    rrect(c, (sx - 215) * K, (sy - 110) * K, (sx + 215) * K, (sy + 90) * K, 14 * K, (160, 106, 60), amb=0.5,
          spec=0.15)
    ell(c, sx * K, (sy - 20) * K, 195 * K, 90 * K, (240, 214, 150), amb=0.7, spec=0.05)
    for _ in range(500):
        x, y = rnd.uniform(sx - 180, sx + 180), rnd.uniform(sy - 95, sy + 55)
        d.point((x * K, y * K), fill=(205, 175, 115))
    rrect(c, (sx + 90) * K, (sy - 70) * K, (sx + 150) * K, (sy - 10) * K, 10 * K, (230, 60, 60), amb=0.5, spec=0.3)
    # Tischtennisplatte
    tx, ty = TABLE
    soft_shadow(c, tx * K, (ty + 110) * K, 240 * K, 26 * K, 0.4)
    for lx in (tx - 150, tx + 150):
        rrect(c, (lx - 8) * K, (ty + 20) * K, (lx + 8) * K, (ty + 110) * K, 6 * K, (70, 70, 80), amb=0.5)
    poly(c, [((tx - 175) * K, (ty - 45) * K), ((tx + 175) * K, (ty - 45) * K), ((tx + 215) * K, (ty + 30) * K),
             ((tx - 215) * K, (ty + 30) * K)], (36, 126, 90), radius=8 * K, amb=0.6, spec=0.2)
    rrect(c, (tx - 215) * K, (ty + 26) * K, (tx + 215) * K, (ty + 44) * K, 6 * K, (26, 96, 70), amb=0.5)
    d = ImageDraw.Draw(c)
    d.polygon([((tx - 170) * K, (ty - 41) * K), ((tx + 170) * K, (ty - 41) * K), ((tx + 208) * K, (ty + 26) * K),
               ((tx - 208) * K, (ty + 26) * K)], outline=(250, 250, 250), width=3 * K)
    d.line([(tx * K, (ty - 41) * K), (tx * K, (ty + 26) * K)], fill=(250, 250, 250), width=2 * K)
    d.rectangle([(tx - 195) * K, (ty - 14) * K, (tx + 195) * K, (ty - 2) * K], fill=(40, 40, 46))
    d.line([((tx - 195) * K, (ty - 14) * K), ((tx + 195) * K, (ty - 14) * K)], fill=(250, 250, 250), width=3 * K)
    return c


@lru_cache(maxsize=1)
def sand_front():
    """Vordere Sandkastenkante + Sandhügel (verdeckt die Beine des Rowdys)."""
    sx, sy = SAND
    w, h = 470, 200
    im = Image.new("RGBA", (w * K, h * K), (0, 0, 0, 0))
    ox, oy = sx - w / 2, sy - 60
    ell(im, (sx - ox) * K, (sy + 5 - oy) * K, 170 * K, 55 * K, (236, 208, 142), amb=0.7, spec=0.05)
    rrect(im, (sx - 215 - ox) * K, (sy + 40 - oy) * K, (sx + 215 - ox) * K, (sy + 90 - oy) * K, 12 * K,
          (160, 106, 60), amb=0.5, spec=0.15)
    return im, (ox, oy)


def draw_sand_front(f, v):
    im, (ox, oy) = sand_front()
    sx, sy = v.p(ox, oy)
    sc = v.z / K
    im2 = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.BILINEAR)
    from gfx import paste_c
    paste_c(f, im2, sx + im2.width / 2, sy + im2.height / 2)


# Flugbahn Rowdy: von vor Oma über die Platte in den Sandkasten
FP0, FP1, FP2 = (650, 1235), (480, 520), (270, 1470)


def fly_pos(s):
    s = min(max(s, 0.0), 1.0)
    x = (1 - s) ** 2 * FP0[0] + 2 * (1 - s) * s * FP1[0] + s * s * FP2[0]
    y = (1 - s) ** 2 * FP0[1] + 2 * (1 - s) * s * FP1[1] + s * s * FP2[1]
    return x, y


def fly_rot(s):
    return -10 - 340 * s


def sand_puff(f, v, dt, seed=4):
    if dt < 0 or dt > 1.5:
        return
    rnd = random.Random(seed)
    lay = Image.new("RGBA", f.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx, cy = SAND[0], SAND[1] - 40
    for k in range(40):
        ang = math.radians(rnd.uniform(-170, -10))
        sp = rnd.uniform(150, 520)
        x = cx + math.cos(ang) * sp * dt
        y = cy + math.sin(ang) * sp * dt + 700 * dt * dt
        r = rnd.uniform(14, 40) * v.z * (1 + dt)
        sx, sy = v.p(x, y)
        a = int(190 * max(0.0, 1 - dt / 1.2))
        d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(232, 205, 150, a))
    f.alpha_composite(lay.filter(ImageFilter.GaussianBlur(3)))


# ------------------------------------------------------------------ Klassenzimmer: Tafelblick
@lru_cache(maxsize=1)
def board_static():
    c = gradient(W * K, H * K, [(0, (238, 224, 190)), (0.76, (226, 208, 170)), (0.761, (184, 132, 82)),
                                (1.0, (150, 104, 62))])
    d = ImageDraw.Draw(c)
    for y in range(1460, H, 70):
        d.line([(0, y * K), (W * K, (y + 10) * K)], fill=(160, 112, 66), width=3 * K)
    rrect(c, 70 * K, 400 * K, 1010 * K, 1030 * K, 18 * K, (120, 84, 50), amb=0.5, spec=0.2)
    rrect(c, 95 * K, 425 * K, 985 * K, 1005 * K, 8 * K, (44, 86, 64), amb=0.8, spec=0.02)
    rrect(c, 90 * K, 1010 * K, 990 * K, 1040 * K, 8 * K, (140, 100, 60), amb=0.5)
    hand = font(F_HAND, 74 * K)
    d.text((150 * K, 520 * K), "Mathe", font=hand, fill=(240, 240, 235))
    d.text((150 * K, 620 * K), "2 + 2 = 4", font=hand, fill=(240, 240, 235))
    d.text((150 * K, 720 * K), "7 · 8 = 56", font=hand, fill=(240, 240, 235))
    # Uhr
    ell(c, 920 * K, 280 * K, 70 * K, 70 * K, (250, 250, 250), amb=0.8, spec=0.2)
    d.line([(920 * K, 280 * K), (920 * K, 235 * K)], fill=(30, 30, 30), width=6 * K)
    d.line([(920 * K, 280 * K), (955 * K, 290 * K)], fill=(30, 30, 30), width=6 * K)
    # Lehrerpult
    rrect(c, 640 * K, 1300 * K, 1040 * K, 1620 * K, 16 * K, (150, 98, 56), amb=0.5, spec=0.2)
    rrect(c, 620 * K, 1285 * K, 1060 * K, 1330 * K, 12 * K, (176, 120, 70), amb=0.55, spec=0.25)
    ell(c, 980 * K, 1255 * K, 34 * K, 32 * K, (220, 40, 50), amb=0.5, spec=0.5)
    d.line([(980 * K, 1225 * K), (985 * K, 1205 * K)], fill=(90, 60, 30), width=5 * K)
    return c


def board_text(f, v, T, a=6.0, b=6.9):
    """'Frau Faust' erscheint handschriftlich an der Tafel."""
    u = min(max((T - a) / (b - a), 0.0), 1.0)
    if u <= 0:
        return
    txt = "Frau Faust"
    n = max(1, int(len(txt) * u))
    lay = Image.new("RGBA", (520, 150), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((10, 10), txt[:n], font=font(F_HAND, 110), fill=(255, 250, 200))
    from gfx import paste_c
    sx, sy = v.p(560, 840 + 75)
    paste_c(f, lay, sx, sy, v.z)


# ------------------------------------------------------------------ Klassenzimmer: Klassenblick
@lru_cache(maxsize=1)
def class_static():
    c = gradient(W * K, H * K, [(0, (244, 232, 200)), (0.62, (232, 216, 180)), (0.621, (184, 132, 82)),
                                (1.0, (150, 104, 62))])
    d = ImageDraw.Draw(c)
    for x0 in (60, 420, 780):
        rrect(c, x0 * K, 300 * K, (x0 + 260) * K, 700 * K, 12 * K, (250, 250, 250), amb=0.8)
        g = gradient(240 * K, 380 * K, [(0, (140, 205, 250)), (1, (200, 235, 250))])
        c.alpha_composite(g, ((x0 + 10) * K, 310 * K))
        ell(c, (x0 + 130) * K, 640 * K, 110 * K, 50 * K, (90, 170, 90), amb=0.6)
        d.line([((x0 + 130) * K, 310 * K), ((x0 + 130) * K, 690 * K)], fill=(250, 250, 250), width=5 * K)
    # Buchstaben-Leiste
    for k, ch in enumerate("ABCDEFGHIJ"):
        x = 60 + k * 100
        col = [(240, 90, 90), (250, 190, 60), (80, 180, 230), (120, 200, 110)][k % 4]
        rrect(c, x * K, 160 * K, (x + 80) * K, 240 * K, 10 * K, col, amb=0.7)
        d.text(((x + 40) * K, 200 * K), ch, font=font(F_BLACK, 50 * K), fill=(255, 255, 255), anchor="mm")
    return c


def desks_front(f, v, ys=(1360,), xs=(230, 540, 850)):
    for y in ys:
        for x in xs:
            x0, y0 = v.p(x - 140, y)
            x1, y1 = v.p(x + 140, y + 220)
            rrect(f, x0, y0, x1, y1, 14 * v.z, (196, 144, 90), amb=0.55, spec=0.2)
            rrect(f, x0 - 8 * v.z, y0 - 10 * v.z, x1 + 8 * v.z, y0 + 22 * v.z, 10 * v.z, (214, 164, 104), amb=0.6,
                  spec=0.25)
