"""'Wer den Pfennig nicht ehrt ...' - wordless 3-row stick-figure time-lapse (1080x1920, 30 fps).

Three friends have 5 EUR left every day: 1 spends it, 2 puts it in a piggy bank, 3 invests it (money tree).
Day counter runs to 30 years, then the proverb lands as punchline + "Wer bist du - 1, 2 oder 3?".
No voiceover: synthesized piano/beat bed + coin/tick SFX.

    python3 render.py                 # -> ../../pfennig-video.mp4
    python3 render.py preview 1 5 12 19 22 26
"""
import math
import os
import subprocess
import sys
import wave
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "pfennig"
BUILD.mkdir(parents=True, exist_ok=True)
W, H, FPS = 1080, 1920, 30
TOTAL = 29.8

F_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_K = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_M = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

BUBBLES = {   # row: [(start, end, text)]
    0: [(1.9, 3.9, "Gönn dir!"), (8.0, 10.4, "Ist doch nur 'n Kaffee."), (14.0, 16.0, "Nächsten Monat spar ich."),
        (18.6, 99, "Wo ist mein Geld hin?!")],
    1: [(3.2, 5.2, "Für schlechte Zeiten."), (12.0, 14.2, "Läuft doch!")],
    2: [(4.5, 6.6, "Für mein Zukunfts-Ich."), (9.0, 11.2, "Langweilig … egal."),
        (18.9, 99, "Jetzt arbeitet das Geld!")],
}


@lru_cache(maxsize=32)
def bubble_img(text):
    f = ImageFont.truetype(F_B, 30)
    tw = f.getlength(text)
    w, h = int(tw + 44), 64
    im = Image.new("RGBA", (w, h + 18), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h], radius=18, fill=(250, 250, 255))
    d.polygon([(24, h - 2), (52, h - 2), (18, h + 16)], fill=(250, 250, 255))
    d.text((w / 2, h / 2 + 1), text, font=f, fill=(20, 22, 36), anchor="mm")
    return im


@lru_cache(maxsize=8)
def emoji(ch, size):
    f = ImageFont.truetype(F_EMOJI, 109)
    im = Image.new("RGBA", (200, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((100, 80), ch, font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox())
    sc = size / max(im.size)
    return im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)

WHITE = (236, 242, 255)
GOLD = (255, 196, 60)
GREEN = (70, 200, 120)
RED = (235, 90, 90)
DIM = (120, 132, 160)

T_DAY1, T_M1, T_Y5, T_Y30 = 6.5, 11.0, 15.5, 20.5
T_REV, T_END = 20.7, 24.6
RATE = 1.07 ** (1 / 365) - 1


@lru_cache(maxsize=None)
def font(p, s):
    return ImageFont.truetype(p, s)


def c01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):
    return 1 - (1 - c01(x)) ** 3


def ease_io(x):
    x = c01(x)
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------ simulation
KNOTS = [(T_DAY1, 1), (T_M1, 30), (T_Y5, 1825), (T_Y30, 10950)]


def day(t):
    if t <= KNOTS[0][0]:
        return 1.0
    for (ta, da), (tb, db) in zip(KNOTS, KNOTS[1:]):
        if t <= tb:
            u = ease_io((t - ta) / (tb - ta)) * 0.6 + 0.4 * (t - ta) / (tb - ta)
            return math.exp(math.log(da) + (math.log(db) - math.log(da)) * u)
    return float(KNOTS[-1][1])


def bal(row, t):
    d = int(day(t))
    if t < 2.3 + row * 1.25 + 0.9 and t < T_DAY1:   # day 1: counter jumps when the first coin lands
        d = 0
    if row == 0:
        return 0
    if row == 1:
        return 5 * d
    return 5 * ((1 + RATE) ** d - 1) / RATE


def cycles(t):
    x = t - T_DAY1
    return 1.2 * x + 0.24 * x * x


def spawns():
    """Times at which each row throws a coin."""
    out = {0: [], 1: [], 2: []}
    for r in range(3):
        out[r].append(2.3 + r * 1.25)
    k, t = 1, T_DAY1
    while t < T_Y30 - 0.3:
        if cycles(t) >= k:
            for r in range(3):
                out[r].append(t + 0.07 * r)
            k += 1
        t += 1 / 240
    return out


SPAWN = spawns()
FLY = 0.55


def fmt_eur(v):
    return f"{int(round(v)):,}".replace(",", ".") + " €"


def label_day(t):
    d = int(day(t))
    if d < 365:
        return f"TAG {d}"
    return f"JAHR {d // 365}" if d // 365 < 30 else "JAHR 30"


# ------------------------------------------------------------------ drawing primitives (ss = supersample)
def figure(d, x, floor, ss, arm_f=15, arm_b=-15, head=(0, 0), col=WHITE, w=8, arms_up=0.0):
    S = lambda v: v * ss  # noqa: E731
    hip = (x, floor - 110)
    sh = (x, floor - 215)
    hd = (x + head[0], floor - 250 + head[1])
    lw = int(w * ss)
    for lx in (-26, 26):
        d.line([S(hip[0]), S(hip[1]), S(x + lx), S(floor)], fill=col, width=lw)
    d.line([S(hip[0]), S(hip[1]), S(sh[0]), S(sh[1])], fill=col, width=lw)
    for a in (arm_f, arm_b):
        a = a + (170 - a) * arms_up * (1 if a >= 0 else 1)
        r = math.radians(a)
        el = (sh[0] + math.sin(r) * 50, sh[1] + math.cos(r) * 50)
        hd2 = (el[0] + math.sin(r) * 48, el[1] + math.cos(r) * 48)
        d.line([S(sh[0]), S(sh[1]), S(el[0]), S(el[1]), S(hd2[0]), S(hd2[1])], fill=col, width=lw, joint="curve")
        for p in (el, hd2):
            d.ellipse([S(p[0] - w / 2), S(p[1] - w / 2), S(p[0] + w / 2), S(p[1] + w / 2)], fill=col)
    for p in (hip, sh, (x - 26, floor), (x + 26, floor)):
        d.ellipse([S(p[0] - w / 2), S(p[1] - w / 2), S(p[0] + w / 2), S(p[1] + w / 2)], fill=col)
    d.ellipse([S(hd[0] - 27), S(hd[1] - 27), S(hd[0] + 27), S(hd[1] + 27)], fill=col)


def coin(d, x, y, ss, r=17, a=255):
    S = lambda v: int(v * ss)  # noqa: E731
    d.ellipse([S(x - r), S(y - r), S(x + r), S(y + r)], fill=(200, 140, 20, a))
    d.ellipse([S(x - r + 3), S(y - r + 3), S(x + r - 3), S(y + r - 3)], fill=GOLD + (a,))
    d.text((S(x), S(y + 1)), "€", font=font(F_K, S(20)), fill=(170, 110, 10, a), anchor="mm")


def cup(d, x, y, ss, a, kind):
    S = lambda v: int(v * ss)  # noqa: E731
    col = (236, 242, 255, a)
    if kind == 0:   # coffee to go
        d.polygon([(S(x - 32), S(y - 70)), (S(x + 32), S(y - 70)), (S(x + 24), S(y)), (S(x - 24), S(y))], fill=col)
        d.rectangle([S(x - 36), S(y - 82), S(x + 36), S(y - 68)], fill=(180, 120, 80, a))
        d.rectangle([S(x - 30), S(y - 50), S(x + 30), S(y - 30)], fill=(180, 120, 80, a))
        for i in (-12, 8):
            d.arc([S(x + i - 8), S(y - 120), S(x + i + 8), S(y - 90)], 90, 270, fill=(200, 210, 230, int(a * 0.6)),
                  width=S(4))
    else:           # shopping bag
        d.rounded_rectangle([S(x - 40), S(y - 80), S(x + 40), S(y)], radius=S(6), fill=(235, 110, 150, a))
        d.arc([S(x - 20), S(y - 108), S(x + 20), S(y - 64)], 180, 360, fill=col, width=S(6))


def piggy(d, x, y, ss, s):
    S = lambda v: int(v * ss)  # noqa: E731
    P, Pd = (244, 150, 178), (214, 112, 145)
    bw, bh = 95 * s, 68 * s
    cy = y - 22 * s - bh
    for lx in (-0.55, -0.2, 0.25, 0.6):
        d.rounded_rectangle([S(x + lx * bw - 9 * s), S(cy + bh * 0.6), S(x + lx * bw + 9 * s), S(y)], radius=S(4 * s),
                            fill=Pd)
    d.ellipse([S(x - bw), S(cy - bh), S(x + bw), S(cy + bh)], fill=P)
    d.polygon([(S(x + bw * 0.35), S(cy - bh * 0.8)), (S(x + bw * 0.6), S(cy - bh * 1.25)),
               (S(x + bw * 0.7), S(cy - bh * 0.6))], fill=Pd)
    d.ellipse([S(x + bw * 0.85), S(cy - 20 * s), S(x + bw * 1.18), S(cy + 22 * s)], fill=Pd)
    for o in (-7, 7):
        d.ellipse([S(x + bw * 1.0 - 3 * s), S(cy + o * s - 4 * s), S(x + bw * 1.0 + 3 * s), S(cy + o * s + 4 * s)],
                  fill=(150, 60, 90))
    d.ellipse([S(x + bw * 0.55), S(cy - bh * 0.35), S(x + bw * 0.55 + 12 * s), S(cy - bh * 0.35 + 12 * s)],
              fill=(60, 30, 40))
    d.rounded_rectangle([S(x - 26 * s), S(cy - bh + 10 * s), S(x + 26 * s), S(cy - bh + 18 * s)], radius=S(4),
                        fill=(150, 60, 90))
    d.arc([S(x - bw - 30 * s), S(cy - 20 * s), S(x - bw + 6 * s), S(cy + 16 * s)], 90, 300, fill=Pd, width=S(5 * s))


def bill(d, x, y, ss, rot, s=1.0, a=255):
    S = lambda v: v * ss  # noqa: E731
    w, h = 34 * s, 18 * s
    c, si = math.cos(rot), math.sin(rot)
    pts = [(x + c * px - si * py, y + si * px + c * py) for px, py in [(-w, -h), (w, -h), (w, h), (-w, h)]]
    d.polygon([(S(px), S(py)) for px, py in pts], fill=(60, 170, 90, a), outline=(30, 110, 55, a))
    d.ellipse([S(x - 7 * s), S(y - 7 * s), S(x + 7 * s), S(y + 7 * s)], fill=(130, 220, 150, a))


def tree(d, x, y, ss, g, t):
    S = lambda v: v * ss  # noqa: E731
    # pot
    d.polygon([(S(x - 46), S(y - 66)), (S(x + 46), S(y - 66)), (S(x + 34), S(y)), (S(x - 34), S(y))], fill=(176, 104, 64))
    d.rectangle([S(x - 52), S(y - 78), S(x + 52), S(y - 62)], fill=(150, 84, 50))
    hgt = 20 + 110 * g
    top = y - 70 - hgt
    d.line([S(x), S(y - 70), S(x), S(top)], fill=(120, 80, 50), width=int(S(6 + 10 * g)))
    rad = 14 + 92 * g
    rng = np.random.default_rng(5)
    blobs = [(0, 0, 1.0), (-0.7, 0.35, 0.75), (0.7, 0.35, 0.75), (-0.4, -0.55, 0.7), (0.45, -0.5, 0.7)]
    for bx, by, br in blobs[:1 + int(g * 5)]:
        r = rad * br
        d.ellipse([S(x + bx * rad - r), S(top + by * rad - r), S(x + bx * rad + r), S(top + by * rad + r)],
                  fill=(46, 150, 82))
    nb = int(g ** 1.4 * 26)
    for i in range(nb):
        a = rng.random() * 2 * math.pi
        rr = rng.random() ** 0.5 * rad * 1.05
        bill(d, x + math.cos(a) * rr, top + math.sin(a) * rr * 0.9, ss, a + math.sin(t * 2 + i) * 0.15, 0.8)
    return top


# ------------------------------------------------------------------ rows
ROW_Y = [455, 850, 1245]
ROW_H = 370
PX, TX = 440, 700          # person x, target x
LABELS = ["1 · AUSGEBEN", "2 · SPARSCHWEIN", "3 · INVESTIEREN"]


@lru_cache(maxsize=3)
def row_panel(r):
    im = Image.new("RGBA", (1000, ROW_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    top = np.array([26, 30, 52]), np.array([18, 21, 38])
    arr = np.zeros((ROW_H, 1000, 4), np.uint8)
    yy = np.linspace(0, 1, ROW_H)[:, None]
    for c in range(3):
        arr[..., c] = (top[0][c] + (top[1][c] - top[0][c]) * yy).astype(np.uint8)
    arr[..., 3] = 255
    base = Image.fromarray(arr, "RGBA")
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 999, ROW_H - 1], radius=28, fill=255)
    im.paste(base, (0, 0), mask)
    d.line([40, ROW_H - 60, 960, ROW_H - 60], fill=(48, 54, 84), width=3)
    col = [RED, (150, 175, 255), GOLD][r]
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle([3, 3, 996, ROW_H - 4], radius=28, outline=col + (200,), width=4)
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(6)))
    ImageDraw.Draw(im).rounded_rectangle([1, 1, 998, ROW_H - 2], radius=28, outline=col + (120,), width=2)
    # little window with moon
    d.rounded_rectangle([840, 30, 960, 120], radius=8, fill=(30, 38, 70), outline=(60, 70, 110), width=3)
    d.line([900, 30, 900, 120], fill=(60, 70, 110), width=3)
    d.line([840, 75, 960, 75], fill=(60, 70, 110), width=3)
    return im


def draw_row(frame, r, t):
    x0, y0 = 40, ROW_Y[r]
    frame.alpha_composite(row_panel(r), (x0, y0))
    ss = 2
    mood = ease_out((t - (T_Y30 - 2.6)) / 1.2)
    if mood > 0 and r == 2:
        sun = Image.new("RGBA", (1000, ROW_H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sun)
        cx, cy = TX, 120
        for k in range(14):
            a = k / 14 * 2 * math.pi + t * 0.25
            sd.polygon([(cx, cy), (cx + math.cos(a - 0.08) * 900, cy + math.sin(a - 0.08) * 900),
                        (cx + math.cos(a + 0.08) * 900, cy + math.sin(a + 0.08) * 900)],
                       fill=(255, 200, 90, int(38 * mood)))
        sd.ellipse([cx - 160, cy - 160, cx + 160, cy + 160], fill=(255, 210, 110, int(70 * mood)))
        sun = sun.filter(ImageFilter.GaussianBlur(14))
        mask = Image.new("L", sun.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, 999, ROW_H - 1], radius=28, fill=255)
        sun.putalpha(Image.fromarray((np.array(sun.getchannel("A")) * (np.array(mask) / 255)).astype(np.uint8)))
        frame.alpha_composite(sun, (x0, y0))
    lay = Image.new("RGBA", (1000 * ss, ROW_H * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    floor = ROW_H - 60
    dd = day(t)
    # window sky: day/night cycle
    ph = (dd % 1.0) if t > T_DAY1 else 0.9
    sky = (255, 200, 110) if 0.25 < ph < 0.55 else None
    if t > T_DAY1 and int(dd) % 2 == 0 and t < T_Y30:
        sky = (255, 190, 100)
    if sky:
        d.rectangle([843 * ss, 33 * ss, 897 * ss, 72 * ss], fill=sky + (150,))
    d.ellipse([925 * ss, 40 * ss, 945 * ss, 60 * ss], fill=(235, 240, 255, 220))

    rev = c01((t - T_REV) / 0.5)
    # figure pose
    throw = 0.0
    for st in SPAWN[r]:
        if st - 0.25 < t < st + 0.2:
            throw = max(throw, 1 - abs(t - st) / 0.25)
    arm_f = 15 + 85 * throw
    arms_up = 0.0
    head = (0, 0)
    if r == 2:
        arms_up = ease_out((t - T_Y30 + 1.0) / 0.6) * (0.85 + 0.1 * math.sin(t * 8))
    if r == 0 and t > T_Y30 - 1.2:
        k = ease_out((t - T_Y30 + 1.2) / 0.6)
        head = (12 * k, 10 * k)           # looks down/over to the others
    figure(d, PX, floor, ss, arm_f=arm_f, arm_b=-12, head=head, arms_up=arms_up)

    # targets
    if r == 1:
        g = c01(bal(1, t) / 54750) ** 0.5
        piggy(d, TX, floor, ss, 0.75 + 0.75 * g)
        tgt = (TX, floor - 22 - 68 * (0.75 + 0.75 * g) * 2)
    elif r == 2:
        b = bal(2, t)
        g = c01(math.log1p(b) / math.log1p(180000)) ** 1.6
        top = tree(d, TX, floor, ss, g, t)
        tgt = (TX, floor - 80)
        # flying bills when the tree is big
        if t > T_Y5:
            n = int(40 * c01((t - T_Y5) / 4))
            for i in range(n):
                life = ((t * (0.35 + 0.02 * (i % 7)) + i * 0.137) % 1.0)
                ang = i * 2.399
                bx = TX + math.cos(ang) * (80 + 300 * life)
                by = top - 40 * math.sin(ang) ** 2 - 120 * life + 160 * life * life
                if -20 < by < ROW_H and 0 < bx < 1000:
                    bill(d, bx, by, ss, ang + t * 3, 0.9, int(255 * (1 - life)))
    else:
        tgt = (TX, floor - 40)
    # coins + spent items
    hand = (PX + 70, floor - 245)
    for k, st in enumerate(SPAWN[r]):
        u = (t - st) / FLY
        if 0 <= u <= 1:
            x = hand[0] + (tgt[0] - hand[0]) * u
            y = hand[1] + (tgt[1] - hand[1]) * u - 140 * math.sin(math.pi * u)
            coin(d, x, y, ss)
        if r == 0:
            v = (t - st - FLY) / 0.7
            if 0 <= v <= 1:
                cup(d, TX + (k % 3 - 1) * 70, floor, ss, int(255 * (1 - v ** 2)), k % 2)
    lay = lay.resize((1000, ROW_H), Image.LANCZOS)
    glow = lay.filter(ImageFilter.GaussianBlur(10))
    frame.alpha_composite(glow, (x0, y0))
    frame.alpha_composite(lay, (x0, y0))
    if mood > 0 and r == 0:     # grey rain over friend 1
        rain = Image.new("RGBA", (1000, ROW_H), (40, 48, 70, int(90 * mood)))
        rd = ImageDraw.Draw(rain)
        rng = np.random.default_rng(int(t * FPS) % 7)
        for i in range(70):
            rx = (i * 61.7 + t * 40) % 1000
            ry = (i * 37.3 + t * 900) % (ROW_H + 60) - 40
            rd.line([rx, ry, rx - 8, ry + 34], fill=(170, 185, 220, int(150 * mood)), width=3)
        mask = Image.new("L", rain.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, 999, ROW_H - 1], radius=28, fill=255)
        rain.putalpha(Image.fromarray(np.minimum(np.array(rain.getchannel("A")), np.array(mask))))
        frame.alpha_composite(rain, (x0, y0))
    for (b0, b1, txt) in BUBBLES[r]:
        if b0 <= t < b1:
            p = (t - b0) / 0.25
            im = bubble_img(txt)
            sc = 0.6 + 0.4 * ease_out(p)
            if sc < 0.999:
                im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.BICUBIC)
            frame.alpha_composite(im, (int(x0 + PX + 30), int(y0 + 6)))

    # +5 € / -5 € popups when a coin lands
    for st in SPAWN[r]:
        u = (t - st - FLY) / 0.7
        if 0 <= u <= 1 and st < T_DAY1 + 3.0:
            txt, pc = ("-5 €", RED) if r == 0 else ("+5 €", GOLD if r == 2 else WHITE)
            pop = Image.new("RGBA", (160, 60), (0, 0, 0, 0))
            ImageDraw.Draw(pop).text((80, 30), txt, font=font(F_K, 40), fill=pc + (int(255 * (1 - u * u)),),
                                     anchor="mm", stroke_width=4, stroke_fill=(10, 12, 24, int(200 * (1 - u * u))))
            frame.alpha_composite(pop, (int(x0 + TX - 80), int(y0 + 150 - 80 * ease_out(u))))
    # texts
    fd = ImageDraw.Draw(frame)
    col = [DIM, WHITE, GOLD][r]
    fd.text((x0 + 36, y0 + 34), LABELS[r], font=font(F_B, 30), fill=col, anchor="lt")
    v = bal(r, t)
    bcol = [RED, WHITE, GOLD][r]
    fd.text((x0 + 36, y0 + 78), fmt_eur(v) + ("*" if r == 2 and t > T_Y5 else ""), font=font(F_K, 64), fill=bcol,
            anchor="lt")
    if r == 0 and t > 3.6:
        spent = 5 * int(day(t))
        fd.text((x0 + 36, y0 + 156), f"ausgegeben: {fmt_eur(spent)}", font=font(F_M, 28), fill=DIM, anchor="lt")
    # spotlight at reveal
    if rev > 0 and r < 2:
        ov = Image.new("RGBA", (1000, ROW_H), (6, 8, 16, int(170 * rev)))
        frame.alpha_composite(ov, (x0, y0))
    if rev > 0 and r == 2:
        d2 = ImageDraw.Draw(frame)
        d2.rounded_rectangle([x0 - 4, y0 - 4, x0 + 1004, y0 + ROW_H + 4], radius=32, outline=GOLD + (int(255 * rev),),
                             width=6)


# ------------------------------------------------------------------ header
def text_c(d, y, txt, f, col, track=3):
    ws = [f.getlength(c) for c in txt]
    x = W / 2 - (sum(ws) + track * (len(txt) - 1)) / 2
    for c, w in zip(txt, ws):
        d.text((x, y), c, font=f, fill=col, anchor="ls")
        x += w + track


def draw_header(frame, t):
    d = ImageDraw.Draw(frame)
    if t < T_REV:
        n = int(t * 70) + 40
        l1 = "3 FREUNDE. JEDEN TAG 5 € ÜBRIG."
        l2 = "NUR EINER WIRD REICH. WER?"
        text_c(d, 175, l1[:n], font(F_K, 50), WHITE, 2)
        text_c(d, 235, l2[:max(0, n - len(l1))], font(F_B, 32), GOLD, 3)
    else:
        p = t - T_REV
        lines = [("WER DEN CENT", WHITE), ("NICHT EHRT,", WHITE), ("IST DES EUROS", GOLD), ("NICHT WERT.", GOLD)]
        for i, (ln, col) in enumerate(lines):
            a = c01((p - i * 0.35) / 0.25)
            if a > 0:
                tmp = Image.new("RGBA", (W, 90), (0, 0, 0, 0))
                text_c(ImageDraw.Draw(tmp), 70, ln, font(F_K, 66), col + (int(255 * a),), 2)
                frame.alpha_composite(tmp, (0, int(95 + i * 74 + (1 - ease_out(a)) * 20)))
    # day pill + progress
    lab = label_day(t)
    pw = 300
    d.rounded_rectangle([W / 2 - pw / 2, 300 if t < T_REV else 400, W / 2 + pw / 2, 360 if t < T_REV else 446],
                        radius=30, fill=(28, 33, 58)) if t < T_REV else None
    if t < T_REV:
        text_c(d, 344, lab, font(F_K, 38), WHITE, 3)
        prog = c01(math.log(day(t)) / math.log(10950)) if t > T_DAY1 else 0
        d.rounded_rectangle([200, 384, 880, 392], radius=4, fill=(40, 46, 76))
        d.rounded_rectangle([200, 384, 200 + 680 * prog, 392], radius=4, fill=GOLD)


def draw_end(frame, t):
    p = c01((t - T_END) / 0.4)
    if p <= 0:
        return
    frame.alpha_composite(Image.new("RGBA", (W, H), (8, 10, 20, int(246 * p))))
    if p < 1:
        return
    d = ImageDraw.Draw(frame)
    q = t - T_END - 0.4
    text_c(d, 300, "GLEICHES GELD.", font(F_K, 64), WHITE, 2)
    if q > 0.35:
        text_c(d, 385, "3 VERSCHIEDENE LEBEN.", font(F_K, 64), GOLD, 2)
    if q > 0.8:
        text_c(d, 560, "Welche Zahl bist du – ehrlich?", font(F_B, 50), WHITE, 0)
    cols = [(RED, "Ausgeber"), (WHITE, "Sparer"), (GOLD, "Investor")]
    for i, (col, lab) in enumerate(cols):
        a = (q - 1.1 - i * 0.18) / 0.3
        if a <= 0:
            continue
        cx, cy = 260 + i * 280, 800
        act = int((q - 2.0) / 0.45) % 3 == i and q > 2.0
        r = 105 * (0.4 + 0.6 * ease_out(a)) * (1.1 if act else 1.0)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(26, 30, 52), outline=col, width=10 if act else 6)
        d.text((cx, cy + 4), str(i + 1), font=font(F_K, int(120 * r / 105)), fill=col, anchor="mm")
        d.text((cx, cy + 150), lab, font=font(F_B, 34), fill=col, anchor="mm")
    if q > 1.9:
        text_c(d, 1080, "Schreib nur die Zahl in die Kommentare", font(F_B, 42), WHITE, 0)
        e = emoji("👇", 150)
        frame.alpha_composite(e, (int(W / 2 - e.width / 2), int(1130 + abs(math.sin(q * 5)) * 40)))
    if q > 1.2:
        text_c(d, 1440, "* Beispiel: 5 € pro Tag, 30 Jahre, 7 % Rendite p. a.", font(F_M, 26), DIM, 0)
        text_c(d, 1480, "Keine Anlageberatung.", font(F_M, 26), DIM, 0)


# ------------------------------------------------------------------ frame
BG = None
DOT = {}
_rng = np.random.default_rng(9)
DUST = [(float(_rng.random() * W), float(_rng.random() * H), int(_rng.choice([2, 3, 4, 6])),
         float(10 + _rng.random() * 30)) for _ in range(40)]


def init():
    global BG
    y = np.linspace(0, 1, H)[:, None]
    g = np.array([10, 12, 24]) + (np.array([16, 19, 36]) - np.array([10, 12, 24])) * y[..., None]
    arr = np.repeat(g, W, axis=1)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    glow = np.exp(-(((xx - W / 2) / 700) ** 2 + ((yy - 300) / 500) ** 2))
    arr = arr + np.array([40, 34, 70]) * glow[..., None]
    vig = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)
    arr = arr * (1 - 0.5 * np.clip(vig * 1.3, 0, 1) ** 2)[..., None]
    BG = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    for r_ in (2, 3, 4, 6):
        im = Image.new("RGBA", (r_ * 4, r_ * 4), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse([r_, r_, r_ * 3, r_ * 3], fill=(255, 220, 150, 110))
        DOT[r_] = im.filter(ImageFilter.GaussianBlur(r_ * 0.6))


def story_frame(t, ui=True):
    fr = BG.copy()
    for (px, py, pr, sp) in DUST:   # floating light dust
        y = (py - t * sp) % H
        fr.alpha_composite(DOT[pr], (int(px + math.sin(t * 0.7 + py) * 20) - pr * 2, int(y)))
    for r in range(3):
        draw_row(fr, r, t)
    if not ui:
        return fr
    if t < T_REV:
        draw_header(fr, t)
        draw_speed(fr, t)
    elif t < T_END + 0.4:
        draw_reveal(fr, t)
    draw_end(fr, t)
    return fr


def draw_speed(fr, t):
    if t < T_DAY1 + 0.3:
        return
    sp = "x10" if t < T_M1 else ("x100" if t < T_Y5 else "x1000")
    d = ImageDraw.Draw(fr)
    e = emoji("⏩", 44)
    pul = 1 + 0.08 * abs(math.sin(t * 6))
    tw = font(F_K, 34).getlength(sp)
    x = 700
    d.rounded_rectangle([x, 302, x + tw + 90, 358], radius=28, fill=(255, 196, 60))
    fr.alpha_composite(e, (x + 14, 308))
    d.text((x + 68, 331), sp, font=font(F_K, int(34 * pul)), fill=(20, 16, 8), anchor="lm")


REV_LINES = [("WER DEN", "CENT"), ("NICHT EHRT,", None), ("IST DES", "EUROS"), ("NICHT WERT.", None)]


def draw_reveal(fr, t):
    p = t - T_REV
    if p < 4.2:
        dark = Image.new("RGBA", (W, H), (6, 8, 16, int(150 * c01(p / 0.3))))
        fr.alpha_composite(dark)
    d = ImageDraw.Draw(fr)
    f = font(F_K, 104)
    for i, (a, hl) in enumerate(REV_LINES):
        q = (p - 0.15 - i * 0.42) / 0.22
        if q <= 0:
            continue
        sc = 1 + 0.6 * (1 - ease_out(q))
        tmp = Image.new("RGBA", (W, 150), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        words = a + ((" " + hl) if hl else "")
        tw = f.getlength(words)
        x = W / 2 - tw / 2
        td.text((x, 75), a, font=f, fill=WHITE, anchor="lm")
        if hl:
            hx = x + f.getlength(a + " ")
            hw = f.getlength(hl)
            td.rounded_rectangle([hx - 14, 18, hx + hw + 14, 134], radius=18, fill=GOLD)
            td.text((hx, 75), hl, font=f, fill=(20, 16, 8), anchor="lm")
        if abs(sc - 1) > 0.01:
            tmp = tmp.resize((int(W * sc), int(150 * sc)), Image.BICUBIC)
        fr.alpha_composite(tmp, (int(W / 2 - tmp.width / 2), int(200 + i * 150 - tmp.height / 2 + 75)))


# ------------------------------------------------------------------ cold-open hook
HOOK = 2.7
REW0 = 1.55


def hook_frame(tg):
    if tg < REW0:
        fr = story_frame(T_Y30 - 0.1, ui=False)
        fr = fr.filter(ImageFilter.GaussianBlur(9))
        fr.alpha_composite(Image.new("RGBA", (W, H), (6, 8, 16, 150)))
        d = ImageDraw.Draw(fr)
        text_c(d, 300, "GLEICHE 5 € AM TAG.", font(F_K, 62), WHITE, 2)
        for k, (txt, col, y, t0) in enumerate([("0 €", RED, 640, 0.0), ("178.340 €", GOLD, 1010, 0.45)]):
            q = (tg - t0) / 0.18
            if q <= 0:
                continue
            fs = 210 if k == 0 else 170
            tmp = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
            ImageDraw.Draw(tmp).text((W / 2, 150), txt, font=font(F_K, fs), fill=col, anchor="mm",
                                     stroke_width=6, stroke_fill=(10, 12, 24))
            g = tmp.filter(ImageFilter.GaussianBlur(18))
            sc = 1 + 0.8 * (1 - ease_out(q))
            for im in (g, g, tmp):
                im2 = im.resize((int(W * sc), int(300 * sc)), Image.BICUBIC) if sc > 1.01 else im
                fr.alpha_composite(im2, (int(W / 2 - im2.width / 2), int(y - im2.height / 2)))
        if tg > 0.3:
            text_c(d, 850, "VS", font(F_K, 70), DIM, 4)
        if tg > 0.9:
            text_c(d, 1300, "WIE GEHT DAS?", font(F_K, 72), WHITE, 3)
        return fr
    # rewind: story plays backwards with VHS look
    u = ease_io((tg - REW0) / (HOOK - REW0))
    st = (T_Y30 + 0.6) * (1 - u)
    fr = story_frame(st)
    a = np.array(fr.convert("RGB")).astype(np.int16)
    a[::4] = (a[::4] * 0.55).astype(np.int16)          # scanlines
    shift = int(8 + 10 * math.sin(tg * 30))
    a[..., 0] = np.roll(a[..., 0], shift, axis=1)
    a[..., 2] = np.roll(a[..., 2], -shift, axis=1)
    band = int((tg * 2300) % H)
    a[band:band + 40] = np.roll(a[band:band + 40], 30, axis=1)
    fr = Image.fromarray(a.clip(0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(fr)
    d.rounded_rectangle([W / 2 - 330, 840, W / 2 + 330, 990], radius=24, fill=(8, 10, 20, 230))
    e = emoji("⏪", 80)
    fr.alpha_composite(e, (int(W / 2 - 300), 875))
    d.text((W / 2 + 50, 915), "30 JAHRE ZURÜCK", font=font(F_K, 52), fill=WHITE, anchor="mm")
    return fr


def aberrate(fr, amt):
    a = np.array(fr.convert("RGB"))
    a[..., 0] = np.roll(a[..., 0], amt, axis=1)
    a[..., 2] = np.roll(a[..., 2], -amt, axis=1)
    return Image.fromarray(a)


BEAT = 60 / 84


def render_frame(fi):
    tg = fi / FPS
    if tg < HOOK:
        fr = hook_frame(tg)
        shake = 1 - c01(min(abs(tg - 0.02), abs(tg - 0.47)) / 0.25)
        zoom = 1 + 0.04 * shake
        dx = int(math.sin(tg * 90) * 14 * shake)
    else:
        t = tg - HOOK
        fr = story_frame(t)
        zoom, dx = 1.0, 0
        if T_DAY1 < t < T_REV:      # punch-zoom on every beat during the time-lapse
            bp = ((t - T_DAY1) % BEAT) / BEAT
            zoom += 0.018 * (1 - ease_out(bp * 3)) * c01((t - T_DAY1) / 2)
        k = 1 - c01((t - T_REV) / 0.5)
        if t >= T_REV and k > 0:
            zoom += 0.07 * k
            dx = int(math.sin(t * 80) * 22 * k)
        f = 1 - c01((t - T_REV) / 0.35)
        if 0 < f < 1 and t >= T_REV:
            fr.alpha_composite(Image.new("RGBA", (W, H), (255, 235, 180, int(130 * f))))
        if t >= T_REV and t - T_REV < 0.35:
            fr = aberrate(fr, int(14 * (1 - (t - T_REV) / 0.35))).convert("RGBA")
    if zoom > 1.001 or dx:
        zw, zh = int(W * zoom), int(H * zoom)
        fr = fr.resize((zw, zh), Image.BILINEAR)
        cx, cy = (zw - W) // 2 + dx, (zh - H) // 2
        fr = fr.crop((cx, cy, cx + W, cy + H))
    return fr.convert("RGB").tobytes()


# ------------------------------------------------------------------ sound
SR = 48000


def env(n, a, d):
    tt = np.arange(n) / SR
    return np.minimum(1, tt / max(a, 1e-4)) * np.exp(-tt / d)


def piano(f, dur, vel=1.0):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * f * k * tt) * (0.6 / k ** 1.6) * np.exp(-tt * (1.2 + k * 0.8)) for k in range(1, 6))
    return s * np.minimum(1, tt / 0.005) * vel


def clink():
    n = int(0.35 * SR)
    tt = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f * tt) * a for f, a in [(2350, 0.5), (3520, 0.3), (5110, 0.2)]) * env(n, 0.001, 0.07)


def tick():
    n = int(0.03 * SR)
    return np.sin(2 * np.pi * 3000 * np.arange(n) / SR) * env(n, 0.0005, 0.005)


def boom():
    n = int(2.5 * SR)
    tt = np.arange(n) / SR
    return np.sin(2 * np.pi * (38 + 60 * np.exp(-tt * 8)) * tt) * env(n, 0.002, 0.7)


def make_audio(path):
    n = int((TOTAL + 0.5) * SR)
    mus = np.zeros(n)
    sfx = np.zeros(n)
    rng = np.random.default_rng(1)

    def put(buf, sig, t, g=1.0):
        i = int(max(0, t) * SR)
        sig = sig[:max(0, n - i)]
        buf[i:i + len(sig)] += sig * g

    bpm = 84
    beat = 60 / bpm
    prog = [(220.0, [220.0, 261.63, 329.63]), (174.61, [174.61, 220.0, 261.63]),
            (130.81, [261.63, 329.63, 392.0]), (196.0, [196.0, 246.94, 293.66])]
    t, i = 0.0, 0
    while t < T_REV:
        root, ch = prog[(i // 4) % 4]
        if i % 4 == 0:
            put(mus, piano(root / 2, 3.5), t, 0.5)
        arp = ch[(i * 2) % 3] * (2 if i % 2 else 1)
        put(mus, piano(arp, 1.6), t, 0.32)
        put(mus, piano(ch[(i * 2 + 1) % 3] * 2, 1.2), t + beat / 2, 0.22)
        if t > T_DAY1:     # beat comes in with the time-lapse
            k = np.sin(2 * np.pi * (45 + 90 * np.exp(-np.arange(int(0.3 * SR)) / SR * 25)) * np.arange(int(0.3 * SR)) / SR)
            put(mus, k * env(len(k), 0.001, 0.12), t, 0.6 * c01((t - T_DAY1) / 3))
            hat = np.diff(rng.standard_normal(int(0.04 * SR) + 1)) * env(int(0.04 * SR), 0.0005, 0.01)
            put(mus, hat, t + beat / 2, 0.25)
            if t > T_Y5:
                put(mus, hat, t + beat / 4, 0.15)
                put(mus, hat, t + 3 * beat / 4, 0.15)
        t += beat
        i += 1
    # riser before reveal
    rn = int(3.0 * SR)
    noise = rng.standard_normal(rn)
    rise = np.convolve(noise, np.ones(8) / 8, "same") * np.linspace(0, 1, rn) ** 2
    put(mus, rise, T_REV - 3.0, 0.12)
    put(mus, boom(), T_REV, 0.9)
    for f in (110.0, 220.0, 261.63, 329.63, 440.0):
        put(mus, piano(f, 6.0), T_REV, 0.35)
    for f in (174.61, 261.63, 349.23, 440.0):
        put(mus, piano(f, 4.0), T_END + 0.4, 0.3)
    # sfx: coins (rate-limited), ticks for the counter
    last = -1
    for r in range(3):
        for st in SPAWN[r]:
            ta = st + FLY
            if ta - last > 0.11 or r == 0 and ta < T_DAY1:
                put(sfx, clink(), ta, 0.35 if ta < T_DAY1 else 0.18)
                last = ta
    tt = T_DAY1
    while tt < T_Y30:
        put(sfx, tick(), tt, 0.25)
        tt += max(0.06, 0.35 - (tt - T_DAY1) * 0.03)
    story = mus * 0.5 + sfx
    # cold-open hook: two impacts, coin burst, tape-rewind, then the story
    hn = int(HOOK * SR)
    mix = np.zeros(hn + n)
    mix[hn:] += story
    b = boom()
    for t0 in (0.02, 0.47):
        i = int(t0 * SR)
        mix[i:i + len(b)] += b[:len(mix) - i] * 0.8
    for j in range(10):
        i = int((0.47 + j * 0.03) * SR)
        c = clink()
        mix[i:i + len(c)] += c * 0.25
    for f in (220.0, 261.63, 329.63):
        pn = piano(f, 1.6)
        i = int(0.47 * SR)
        mix[i:i + len(pn)] += pn * 0.3
    rn = int((HOOK - REW0) * SR)
    tt = np.arange(rn) / SR
    fr_ = 1400 * np.exp(-tt * 1.8) + 120
    saw = 2 * ((np.cumsum(fr_) / SR) % 1) - 1
    trem = 0.6 + 0.4 * np.sin(2 * np.pi * 22 * tt)
    rw = (saw * 0.25 + np.random.default_rng(4).standard_normal(rn) * 0.12) * trem * np.minimum(1, tt / 0.05)
    i = int(REW0 * SR)
    mix[i:i + rn] += rw * 0.7
    n = len(mix)
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.9
    fade = np.minimum(1, (n - np.arange(n)) / SR / 1.0)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * fade * 32000).astype(np.int16).tobytes())


def main():
    init()
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        (BUILD / "stills").mkdir(exist_ok=True)
        for x in sys.argv[2:]:
            Image.frombytes("RGB", (W, H), render_frame(int(float(x) * FPS))).save(BUILD / "stills" / f"t{float(x):05.1f}.png")
        return
    aud = BUILD / "audio.wav"
    make_audio(aud)
    out = ROOT / "cent-video.mp4"
    nf = int((HOOK + TOTAL) * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(aud), "-af", "loudnorm=I=-14:TP=-1.5", "-c:v", "libx264", "-preset", "medium",
           "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", "-t", f"{HOOK + TOTAL:.3f}", str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=init) as pool:
        for i, buf in enumerate(pool.imap(render_frame, range(nf), chunksize=4)):
            ff.stdin.write(buf)
            if i % 200 == 0:
                print("frame", i, "/", nf, flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", out)


if __name__ == "__main__":
    main()
