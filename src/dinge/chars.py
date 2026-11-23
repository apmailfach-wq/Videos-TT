"""Object characters: real-world things with simple cartoon eyes + mouth (the series' signature)."""
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

from core import F_HEAD, F_BODY, F_HAND, INK, WHITE, darker, face, font, shadowed, ss_image, q_mouth, q_blink


def F(emo, mouth, blink):
    return emo, q_mouth(mouth), q_blink(blink)


# ------------------------------------------------------------------ banknote
BILL = {50: ((236, 162, 92), (186, 110, 52)), 20: ((112, 156, 214), (62, 98, 164))}


@lru_cache(maxsize=600)
def _bill(value, emo, mouth, blink, look, wet, shadow):
    body, dark = BILL[value]
    w, h = 640, 350

    def fn(d, ss, im):
        S = ss
        d.rounded_rectangle([6 * S, 6 * S, (w - 6) * S, (h - 6) * S], radius=22 * S, fill=body, outline=INK, width=7 * S)
        d.rounded_rectangle([26 * S, 26 * S, (w - 26) * S, (h - 26) * S], radius=14 * S, outline=darker(body, 0.85),
                            width=4 * S)
        # watermark circle + star arc
        d.ellipse([60 * S, 80 * S, 230 * S, 270 * S], fill=darker(body, 0.93))
        for k in range(12):
            a = math.radians(-70 + k * 12)
            x, y = 520 * S + math.cos(a) * 70 * S, 175 * S + math.sin(a) * 120 * S
            d.ellipse([x - 7 * S, y - 7 * S, x + 7 * S, y + 7 * S], fill=(250, 220, 120))
        f = font(F_HEAD, 70 * S)
        d.text((46 * S, 30 * S), str(value), font=f, fill=dark)
        d.text(((w - 46) * S, (h - 30) * S), str(value), font=f, fill=dark, anchor="rd")
        d.text((60 * S, (h - 62) * S), "EURO", font=font(F_BODY, 26 * S), fill=dark)
        # creases (well-travelled)
        rnd = random.Random(value)
        for _ in range(5):
            x0, y0 = rnd.uniform(40, 600), rnd.uniform(20, 330)
            d.line([x0 * S, y0 * S, (x0 + rnd.uniform(-90, 90)) * S, (y0 + rnd.uniform(-60, 60)) * S],
                   fill=darker(body, 0.88), width=3 * S)
        d.line([(w * 0.5) * S, 8 * S, (w * 0.52) * S, (h - 8) * S], fill=darker(body, 0.82), width=3 * S)
        if wet:
            for k in range(7):
                x, y = rnd.uniform(60, 580), rnd.uniform(40, 300)
                d.ellipse([x * S, y * S, (x + 18) * S, (y + 24) * S], fill=(200, 230, 255, 170))
        face(d, 330, 135, 0.95, emo, mouth, blink, look, lid=dark, ss=ss)

    im = ss_image(w, h, fn)
    return shadowed(im, alpha=0.5) if shadow else im


def bill(value=50, emo="tired", mouth=0.0, blink=0.0, look=(0, 0), wet=False, shadow=True):
    return _bill(value, *F(emo, mouth, blink), look, wet, shadow)


# ------------------------------------------------------------------ deposit bottle
GLASS = (122, 66, 26)


def _bottle_shape(d, S, fill, grow=0):
    g = grow * S
    pts = []
    # right half outline from lip to bottom, mirrored
    prof = [(38, 18), (40, 40), (36, 60), (34, 200), (44, 240), (80, 290), (112, 330), (116, 360), (116, 750),
            (108, 770)]
    pts = [((150 + x) * S + g, y * S - (g if y < 30 else 0)) for x, y in prof]
    pts += [((150 - x) * S - g, y * S - (g if y < 30 else 0)) for x, y in reversed(prof)]
    if g:
        pts = [(x, y + (g if y > 700 * S else 0)) for x, y in pts]
    d.polygon(pts, fill=fill)


@lru_cache(maxsize=600)
def _bottle(emo, mouth, blink, look, label, tag, shadow):
    w, h = 300, 790

    def fn(d, ss, im):
        S = ss
        _bottle_shape(d, S, INK, grow=7)
        _bottle_shape(d, S, GLASS)
        # glass highlights
        d.rounded_rectangle([60 * S, 340 * S, 82 * S, 730 * S], radius=10 * S, fill=(196, 140, 92))
        d.rounded_rectangle([132 * S, 40 * S, 142 * S, 200 * S], radius=5 * S, fill=(196, 140, 92))
        d.rounded_rectangle([104 * S, 10 * S, 196 * S, 46 * S], radius=12 * S, fill=(150, 84, 36), outline=INK,
                            width=5 * S)
        if label:
            d.rounded_rectangle([34 * S, 500 * S, 266 * S, 690 * S], radius=8 * S, fill=(244, 236, 214), outline=INK,
                                width=4 * S)
            d.polygon([(220 * S, 500 * S), (266 * S, 500 * S), (266 * S, 560 * S)], fill=GLASS)  # torn corner
            d.text((150 * S, 560 * S), "PFAND", font=font(F_HEAD, 40 * S), fill=(176, 40, 40), anchor="mm")
            d.text((150 * S, 630 * S), "MEHRWEG · 0,08 €", font=font(F_BODY, 21 * S), fill=(80, 70, 60), anchor="mm")
            rnd = random.Random(4)
            for _ in range(14):
                x0, y0 = rnd.uniform(40, 250), rnd.uniform(505, 685)
                d.line([x0 * S, y0 * S, (x0 + rnd.uniform(-40, 40)) * S, (y0 + rnd.uniform(-12, 12)) * S],
                       fill=(170, 160, 140), width=2 * S)
        if tag:
            d.line([120 * S, 210 * S, 150 * S, 250 * S, 180 * S, 210 * S], fill=(190, 190, 200), width=4 * S)
            d.rounded_rectangle([120 * S, 245 * S, 180 * S, 290 * S], radius=10 * S, fill=(205, 205, 215), outline=INK,
                                width=3 * S)
            d.text((150 * S, 268 * S), tag, font=font(F_BODY, 22 * S), fill=INK, anchor="mm")
        face(d, 150, 395, 0.72, emo, mouth, blink, look, lid=darker(GLASS, 0.7), ss=ss, eye_gap=0.95)

    im = ss_image(w, h, fn)
    return shadowed(im, alpha=0.5) if shadow else im


def bottle(emo="neutral", mouth=0.0, blink=0.0, look=(0, 0), label=True, tag="#49", shadow=True):
    return _bottle(*F(emo, mouth, blink), look, label, tag, shadow)


# ------------------------------------------------------------------ socks
SOCK = dict(hero=((30, 168, 158), (255, 255, 255), (232, 70, 80)),
            mayor=((222, 200, 160), (196, 170, 128), (176, 140, 96)),
            rag=((150, 150, 146), (128, 128, 124), (120, 120, 116)))


def _sock_shape(d, S, col, g=0):
    G = g * S
    d.rounded_rectangle([120 * S - G, 40 * S - G, 360 * S + G, 470 * S + G], radius=50 * S + G, fill=col)
    d.rounded_rectangle([120 * S - G, 330 * S - G, 500 * S + G, 570 * S + G], radius=118 * S + G, fill=col)


@lru_cache(maxsize=900)
def _sock(kind, emo, mouth, blink, look, acc, shadow, sash):
    body, stripe, toe = SOCK.get(kind, SOCK["hero"]) if isinstance(kind, str) else kind
    w, h = 520, 600

    def fn(d, ss, im):
        S = ss
        _sock_shape(d, S, INK, 7)
        _sock_shape(d, S, body)
        # toe + heel patches
        d.pieslice([360 * S, 330 * S, 500 * S, 570 * S], 270, 90, fill=toe)
        d.rectangle([360 * S, 330 * S, 382 * S, 570 * S], fill=toe)
        d.pieslice([120 * S, 410 * S, 260 * S, 570 * S], 90, 180, fill=toe)
        # cuff ribbing
        d.rounded_rectangle([120 * S, 40 * S, 360 * S, 112 * S], radius=40 * S, fill=darker(body, 0.88))
        for x in range(140, 350, 22):
            d.line([x * S, 56 * S, x * S, 104 * S], fill=darker(body, 0.75), width=4 * S)
        for y in (128, 360):
            d.rectangle([120 * S, y * S, 360 * S, (y + 26) * S], fill=stripe)
        if kind == "mayor":
            rnd = random.Random(9)
            for _ in range(90):
                x, y = rnd.uniform(140, 480), rnd.uniform(130, 550)
                d.arc([x * S, y * S, (x + 16) * S, (y + 12) * S], 0, 180, fill=darker(body, 0.8), width=3 * S)
        if kind == "rag":
            for x in range(124, 500, 26):
                d.polygon([(x * S, 566 * S), ((x + 13) * S, 596 * S), ((x + 26) * S, 566 * S)], fill=body)
            d.line([200 * S, 180 * S, 330 * S, 470 * S], fill=darker(body, 0.8), width=5 * S)
            d.line([300 * S, 160 * S, 180 * S, 420 * S], fill=darker(body, 0.8), width=5 * S)
        face(d, 240, 238, 0.74, emo, mouth, blink, look, lid=darker(body, 0.7), acc=acc, ss=ss, eye_gap=0.95)
        if sash:
            d.polygon([(120 * S, 300 * S), (150 * S, 290 * S), (380 * S, 520 * S), (340 * S, 545 * S)],
                      fill=(200, 30, 40))
            d.text((245 * S, 420 * S), sash, font=font(F_BODY, 22 * S), fill=(255, 220, 120), anchor="mm")

    im = ss_image(w, h, fn)
    return shadowed(im, alpha=0.5) if shadow else im


def sock(kind="hero", emo="neutral", mouth=0.0, blink=0.0, look=(0, 0), acc=None, shadow=True, sash=None):
    return _sock(kind, *F(emo, mouth, blink), look, acc, shadow, sash)


@lru_cache(maxsize=64)
def mini_sock(color, seed):
    rnd = random.Random(seed)
    emo = rnd.choice(["neutral", "smug", "neutral", "shock"])
    return sock((color, (255, 255, 255), darker(color, 0.7)), emo, 0, 0,
                (rnd.uniform(-1, 1), 0), None, False).resize((156, 180), Image.LANCZOS)


# ------------------------------------------------------------------ hair tie (sidekick in the plan)
@lru_cache(maxsize=60)
def hairtie(emo="tired", mouth=0.0, blink=0.0):
    def fn(d, ss, im):
        S = ss
        d.ellipse([20 * S, 20 * S, 300 * S, 300 * S], outline=INK, width=60 * S)
        d.ellipse([28 * S, 28 * S, 292 * S, 292 * S], outline=(70, 50, 60), width=44 * S)
        face(d, 160, 140, 0.55, emo, mouth, blink, (0, 0), lid=(60, 40, 50), ss=ss)
    return ss_image(320, 320, fn)


# ------------------------------------------------------------------ props used by several scenes
@lru_cache(maxsize=32)
def trading_card(seed):
    rnd = random.Random(seed)
    col = rnd.choice([(240, 90, 70), (80, 170, 240), (110, 200, 110), (180, 120, 230), (250, 180, 60)])

    def fn(d, ss, im):
        S = ss
        d.rounded_rectangle([4 * S, 4 * S, 136 * S, 192 * S], radius=10 * S, fill=(250, 210, 40), outline=INK,
                            width=4 * S)
        d.rounded_rectangle([16 * S, 34 * S, 124 * S, 110 * S], radius=6 * S, fill=col)
        cx, cy = 70 * S, 72 * S
        pts = []
        for k in range(10):
            r = (26 if k % 2 == 0 else 11) * S
            a = math.radians(-90 + k * 36)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        d.polygon(pts, fill=(255, 250, 220))
        d.rectangle([16 * S, 14 * S, 100 * S, 26 * S], fill=(60, 50, 40))
        for y in (124, 142, 160):
            d.rectangle([16 * S, y * S, 124 * S, (y + 8) * S], fill=(230, 220, 190))
    return ss_image(140, 196, fn)
