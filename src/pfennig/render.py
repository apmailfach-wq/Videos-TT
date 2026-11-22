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
TOTAL = 28.5

F_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_K = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_M = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"

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
    # little window with moon
    d.rounded_rectangle([840, 30, 960, 120], radius=8, fill=(30, 38, 70), outline=(60, 70, 110), width=3)
    d.line([900, 30, 900, 120], fill=(60, 70, 110), width=3)
    d.line([840, 75, 960, 75], fill=(60, 70, 110), width=3)
    return im


def draw_row(frame, r, t):
    x0, y0 = 40, ROW_Y[r]
    frame.alpha_composite(row_panel(r), (x0, y0))
    ss = 2
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
        n = int(t * 60)
        l1 = "3 FREUNDE. JEDEN TAG 5 € ÜBRIG."
        l2 = "WER HAT NACH 30 JAHREN AM MEISTEN?"
        text_c(d, 175, l1[:n], font(F_K, 50), WHITE, 2)
        text_c(d, 235, l2[:max(0, n - len(l1))], font(F_B, 32), GOLD, 3)
    else:
        p = t - T_REV
        lines = [("WER DEN PFENNIG", WHITE), ("NICHT EHRT,", WHITE), ("IST DES TALERS", GOLD), ("NICHT WERT.", GOLD)]
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
    frame.alpha_composite(Image.new("RGBA", (W, H), (8, 10, 20, int(242 * p))))
    if p < 1:
        return
    d = ImageDraw.Draw(frame)
    q = t - T_END - 0.4
    a1 = c01(q / 0.3)
    if a1 > 0:
        f = font(F_K, 150)
        d.text((W / 2, 820), "SEI", font=f, fill=WHITE, anchor="ms")
        d.text((W / 2, 980), "NR. 3.", font=f, fill=GOLD, anchor="ms")
    if q > 0.6:
        text_c(d, 1120, "Wer bist du – 1, 2 oder 3?", font(F_B, 46), WHITE, 0)
        text_c(d, 1185, "Schreib's in die Kommentare.", font(F_M, 40), DIM, 0)
    if q > 1.0:
        text_c(d, 1400, "* Beispiel: 5 € pro Tag, 30 Jahre, 7 % Rendite p. a.", font(F_M, 26), DIM, 0)
        text_c(d, 1440, "Keine Anlageberatung.", font(F_M, 26), DIM, 0)


# ------------------------------------------------------------------ frame
BG = None


def init():
    global BG
    y = np.linspace(0, 1, H)[:, None]
    g = np.array([10, 12, 24]) + (np.array([16, 19, 36]) - np.array([10, 12, 24])) * y[..., None]
    BG = Image.fromarray(np.repeat(g, W, axis=1).astype(np.uint8), "RGB").convert("RGBA")


def render_frame(fi):
    t = fi / FPS
    fr = BG.copy()
    intro = [ease_out((t - 0.15 - r * 0.15) / 0.4) for r in range(3)]
    for r in range(3):
        if intro[r] > 0:
            draw_row(fr, r, t)
            if intro[r] < 1:
                fr.alpha_composite(Image.new("RGBA", (1000, ROW_H), (10, 12, 24, int(255 * (1 - intro[r])))),
                                   (40, ROW_Y[r]))
    draw_header(fr, t)
    draw_end(fr, t)
    # flash at reveal
    f = 1 - c01((t - T_REV) / 0.35)
    if 0 < f < 1 and t >= T_REV:
        fr.alpha_composite(Image.new("RGBA", (W, H), (255, 235, 180, int(120 * f))))
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
    mix = mus * 0.5 + sfx
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
    out = ROOT / "pfennig-video.mp4"
    nf = int(TOTAL * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(aud), "-af", "loudnorm=I=-14:TP=-1.5", "-c:v", "libx264", "-preset", "medium",
           "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", "-t", f"{TOTAL:.3f}", str(out)]
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
