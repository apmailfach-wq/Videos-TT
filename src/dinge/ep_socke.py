"""Folge 3 – Die verschwundene Socke (Gefängnisausbruch-Thriller)."""
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

from chars import hairtie, mini_sock, sock
from core import (over, F_BODY, F_HAND, F_HEAD, H, INK, RED, W, WHITE, YELLOW, clamp01, ease_back, ease_io, ease_out,
                  font, paste, radial, shadowed, ss_image, vgrad)
from ep_schein import stamp

TL = None
LABELS = {
    "zelle": ("DREI JAHRE", "SCHUBLADE NR. 2"),
    "trommel": ("JEDEN SONNTAG", "DIE FOLTER"),
    "plan": ("MONATELANG", "DER PLAN"),
    "sprung": ("SCHLEUDERGANG", "MINUTE 43"),
    "dorf": ("HINTER DER TROMMEL", "DIE ZIVILISATION"),
    "partner": ("GESTERN", "MEIN PARTNER"),
    "rache": ("BALD", "DIE RÜCKKEHR"),
}


@lru_cache(maxsize=None)
def bg(key):
    if key in ("hook", "cta"):
        im = radial(W, H, W / 2, 950, 1150, (40, 40, 52), (6, 6, 10))
    elif key == "zelle":
        im = vgrad(W, H, (120, 82, 50), (70, 44, 24))
        d = ImageDraw.Draw(im)
        for y in range(500, H, 110):
            d.line([0, y, W, y + 8], fill=(96, 62, 34), width=4)
        # rolled-up sock pairs lying around
        rnd = random.Random(3)
        for j in range(7):
            x, y = rnd.uniform(60, 1020), rnd.uniform(1380, 1750)
            c = rnd.choice([(60, 60, 70), (200, 200, 200), (150, 40, 50), (40, 80, 140)])
            d.ellipse([x - 70, y - 50, x + 70, y + 50], fill=c, outline=INK, width=4)
            d.arc([x - 50, y - 30, x + 50, y + 30], 200, 340, fill=INK, width=3)
        # scratched tally marks
        for g in range(4):
            for j in range(5):
                x = 90 + g * 80 + j * 12
                if j < 4:
                    d.line([x, 600, x, 680], fill=(230, 210, 180), width=5)
            d.line([86 + g * 80, 660, 140 + g * 80, 615], fill=(230, 210, 180), width=5)
    elif key in ("trommel", "sprung"):
        im = radial(W, H, W / 2, 1050, 900, (190, 200, 212), (60, 66, 76))
        d = ImageDraw.Draw(im)
        for r in range(0, 14):
            rr = 120 + r * 48
            for k in range(int(rr / 18)):
                a = 2 * math.pi * k / int(rr / 18) + r
                x, y = W / 2 + math.cos(a) * rr, 1050 + math.sin(a) * rr
                d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(110, 118, 130))
    elif key == "plan":
        im = vgrad(W, H, (22, 70, 140), (14, 46, 100))
        d = ImageDraw.Draw(im)
        for x in range(0, W, 60):
            d.line([x, 0, x, H], fill=(50, 100, 170), width=2)
        for y in range(0, H, 60):
            d.line([0, y, W, y], fill=(50, 100, 170), width=2)
        d.ellipse([140, 560, 940, 1360], outline=(235, 245, 255), width=8)
        d.ellipse([230, 650, 850, 1270], outline=(235, 245, 255), width=5)
        fh = font(F_HAND, 54)
        d.text((150, 520), "GUMMIDICHTUNG", font=fh, fill=(235, 245, 255))
        d.text((700, 1380), "Wärter: So 10:00", font=fh, fill=(235, 245, 255))
        d.line([880, 690, 960, 620], fill=(255, 220, 90), width=6)
        d.text((960, 600), "X", font=font(F_HEAD, 60), fill=(255, 80, 80), anchor="mm")
    elif key == "dorf":
        im = vgrad(W, H, (36, 26, 20), (14, 10, 8))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, W, 520], fill=(18, 14, 12))
        d.rectangle([0, 500, W, 540], fill=(70, 74, 80))  # underside of the machine
        for j in range(6):                                   # lint huts
            x = 60 + j * 180
            d.polygon([(x, 1240), (x + 70, 1120), (x + 140, 1240)], fill=(170, 160, 150), outline=INK)
            d.rectangle([x + 10, 1240, x + 130, 1330], fill=(150, 140, 130), outline=INK, width=3)
            d.rectangle([x + 52, 1270, x + 88, 1330], fill=(255, 200, 90))
        d.rectangle([0, 1330, W, H], fill=(48, 40, 34))
    elif key == "partner":
        im = vgrad(W, H, (90, 100, 110), (40, 46, 52))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 1300, W, H], fill=(170, 160, 150))
        for x in range(0, W, 140):
            d.line([x, 1300, x - 80, H], fill=(140, 130, 120), width=4)
    elif key == "rache":
        im = radial(W, H, W / 2, 1000, 1100, (90, 10, 14), (8, 0, 2))
    else:
        im = Image.new("RGB", (W, H), (0, 0, 0))
    return im.convert("RGBA")


def bars(img, x0=60, x1=1020, y0=480, y1=1500):
    d = ImageDraw.Draw(img, "RGBA")
    for x in range(x0, x1 + 1, 120):
        d.rounded_rectangle([x - 14, y0, x + 14, y1], radius=12, fill=(70, 74, 82), outline=INK, width=4)
        d.line([x - 6, y0 + 10, x - 6, y1 - 10], fill=(150, 156, 166), width=4)
    for y in (y0 + 30, y1 - 30):
        d.rounded_rectangle([x0 - 30, y - 18, x1 + 30, y + 18], radius=10, fill=(70, 74, 82), outline=INK, width=4)


@lru_cache(maxsize=None)
def coin(seed):
    def fn(d, ss, im):
        S = ss
        d.ellipse([4 * S, 4 * S, 76 * S, 76 * S], fill=(230, 180, 60), outline=INK, width=4 * S)
        d.text((40 * S, 40 * S), ["1", "2", "5", "10"][seed % 4], font=font(F_HEAD, 26 * S), fill=(150, 100, 20),
               anchor="mm")
    return ss_image(80, 80, fn)


@lru_cache(maxsize=None)
def bucket():
    def fn(d, ss, im):
        S = ss
        d.polygon([(20 * S, 60 * S), (300 * S, 60 * S), (260 * S, 330 * S), (60 * S, 330 * S)], fill=(60, 120, 220),
                  outline=INK)
        d.ellipse([20 * S, 30 * S, 300 * S, 90 * S], fill=(200, 230, 255), outline=INK, width=5 * S)
        for k in range(6):
            x = 50 + k * 42
            d.ellipse([x * S, 10 * S, (x + 40) * S, 50 * S], fill=(255, 255, 255), outline=(180, 200, 220), width=3 * S)
    return ss_image(320, 340, fn)


SOCK_COLS = [(220, 60, 70), (60, 110, 200), (240, 200, 60), (120, 190, 90), (180, 110, 200), (240, 140, 60),
             (90, 90, 100), (230, 230, 230)]


def draw(img, ctx):
    k, lt, sd, t = ctx.scene, ctx.lt, ctx.sd, ctx.t
    over(img, bg(k))
    m, bl = ctx.mouth, ctx.blink
    bob = 6 * math.sin(t * 2.0)
    out = {}
    d = ImageDraw.Draw(img, "RGBA")

    if k == "hook":
        # sweeping search light + red alarm after "ausgebrochen"
        sw = math.sin(t * 1.4)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        cx = 540 + 420 * sw
        ld.polygon([(540, 300), (cx - 260, 1800), (cx + 260, 1800)], fill=(255, 250, 220, 30))
        ld.ellipse([cx - 300, 1500, cx + 300, 1900], fill=(255, 250, 220, 30))
        over(img, lay)
        ta = ctx.w("ausgebrochen")
        if t >= ta:
            a = 0.5 + 0.5 * math.sin((t - ta) * 9)
            over(img, Image.new("RGBA", (W, H), (255, 0, 20, int(70 * a))))
        acc = "sunglasses" if t >= ta else None
        emo = "smug" if t >= ta else "neutral"
        paste(img, sock("hero", emo, m, bl, (0, 0), acc), W / 2, 930 + bob, scale=1.3, angle=-4)
        if t >= ta:
            kk = ease_back((t - ta) / 0.25, 2.5)
            paste(img, stamp("AUSGEBROCHEN", RED, 64), 540, 1220, scale=2 - kk, angle=-8)

    elif k == "zelle":
        paste(img, sock("hero", "sad", m, bl, (0, 0.4)), W / 2, 1060 + bob, scale=0.95)
        bars(img)

    elif k == "trommel":
        rot = t * 3.2
        paste(img, sock("hero", "shock" if t < ctx.w("ich") else "angry", m, bl, (0, 0)),
              W / 2 + 180 * math.cos(rot), 1050 + 180 * math.sin(rot), scale=0.8, angle=-math.degrees(rot))
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        ld.ellipse([90, 600, 990, 1500], outline=(230, 236, 244, 255), width=40)
        ld.arc([170, 680, 910, 1420], 200, 250, fill=(255, 255, 255, 110), width=24)
        over(img, lay)
        rpm = min(1400, int(max(0, t - ctx.w("jeden")) * 900))
        paste(img, stamp(f"{rpm:04d} U/MIN", (80, 255, 160), 48), 540, 1620)
        if t >= ctx.w("folter"):
            paste(img, stamp("FOLTER", RED, 80), 540, 640, angle=-6,
                  alpha=clamp01((t - ctx.w("folter")) / 0.2))
        out["shake"] = 4.0

    elif k == "plan":
        th = ctx.w("haargummi")
        sx = 360 if t >= th else 540
        paste(img, sock("hero", "neutral", m, bl, (1, -0.3)), sx, 1000 + bob, scale=0.8)
        if t >= th:
            kk = ease_back((t - th) / 0.35, 2)
            m2 = 0.0
            paste(img, hairtie("tired", m2, ctx.blink), 770, 1050, scale=0.4 + 0.5 * kk)
            t14 = ctx.w("2014")
            if t >= t14:
                d.text((770, 1230), "seit 2014 draußen", font=font(F_HAND, 56), fill=(255, 230, 120), anchor="mm")
        # chalk arrow from sock to the gap
        p = clamp01((lt - 0.4) / 2.5)
        if p > 0:
            pts = [(540 + (960 - 540) * q, 900 - 300 * q - 120 * math.sin(math.pi * q)) for q in
                   [i / 30 * p for i in range(31)]]
            d.line(pts, fill=(255, 220, 90), width=8)

    elif k == "sprung":
        tj = ctx.w("springe")
        rot = t * (5.5 if t < tj else 2)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        for j in range(10):
            a = rot + j * 0.6
            ld.arc([140, 650, 940, 1450], math.degrees(a), math.degrees(a) + 20, fill=(255, 255, 255, 70), width=10)
        over(img, lay)
        sec = min(59, int(lt * 18))
        paste(img, stamp(f"43:{sec:02d}", (255, 70, 70), 90), 540, 650)
        if t < tj:
            paste(img, sock("hero", "angry", m, bl, (0, 0)), W / 2 + 150 * math.cos(rot), 1050 + 150 * math.sin(rot),
                  scale=0.75, angle=-math.degrees(rot))
        else:
            p = ease_out((t - tj) / 0.9)
            x = W / 2 + 150 * math.cos(rot) + (540 - W / 2) * p
            y = lerp(1050, 1000, p) - 260 * math.sin(math.pi * min(1, p * 1.2)) * (1 - p * 0.4)
            paste(img, sock("hero", "smug", m, bl, (0, 0), "sunglasses"), x, y, scale=0.75 + 0.45 * p,
                  angle=lerp(-30, 6, p))
            out["zoom"] = 0.06 * (1 - p)

    elif k == "dorf":
        # warm lantern glow
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        for j, x in enumerate((180, 540, 900)):
            fl = 1 + 0.05 * math.sin(t * 9 + j)
            ld.ellipse([x - 220 * fl, 820 - 220 * fl, x + 220 * fl, 820 + 220 * fl], fill=(255, 170, 60, 30))
            ld.line([x, 540, x, 780], fill=(40, 30, 20, 255), width=4)
            ld.ellipse([x - 24, 780, x + 24, 830], fill=(255, 200, 90, 255))
        over(img, lay)
        t47 = ctx.w("47")
        n = 4 if t < t47 else 4 + int(min(1, (t - t47) / 0.8) * 10)
        rnd = random.Random(12)
        spots = [(rnd.uniform(70, 1010), rnd.uniform(1360, 1560)) for _ in range(14)]
        for j in range(n):
            x, y = spots[j]
            paste(img, mini_sock(SOCK_COLS[j % len(SOCK_COLS)], j), x, y + 4 * math.sin(t * 4 + j), scale=0.9)
        tb = ctx.w("bürgermeister")
        hx = 380 if t >= tb else 540
        paste(img, sock("hero", "neutral", m, bl, (1 if t >= tb else 0, 0), "sunglasses"), hx, 1000 + bob, scale=0.7)
        if t >= tb:
            kk = ease_back((t - tb) / 0.35, 2)
            paste(img, sock("mayor", "smug", 0, ctx.blink, (-1, 0), None, True, "BÜRGERMEISTER"), 800, 980,
                  scale=(0.3 + 0.4 * kk))
            if t >= ctx.w("von"):
                paste(img, stamp("SEIT 1998", YELLOW, 40), 800, 720, angle=6)
        if t47 <= t < tb:
            paste(img, stamp("47 SOCKEN", YELLOW, 60), 540, 680, angle=-4)
        tw = ctx.w("währung")
        if t >= tw:
            for j in range(10):
                st = tw + j * 0.08
                if t < st:
                    continue
                p = ease_out((t - st) / 0.5)
                x = 140 + j * 85
                paste(img, coin(j), x, lerp(500, 1610 - (j % 3) * 30, p), angle=j * 30)

    elif k == "partner":
        tr = ctx.w("putzlappen")
        if t < tr:
            # flashback: partner alone in the drawer (sepia)
            paste(img, sock("hero", "sad", 0, ctx.blink, (-1, 0)), 760, 1000, scale=0.75, angle=6)
            paste(img, sock("hero", "sad" if t < ctx.w("gestern") else "shock", m, bl, (1, 0), "sunglasses"), 300,
                  1080 + bob, scale=0.7)
            out["grade"] = ((0.9, 0.82, 0.68), (30, 20, 6))
        else:
            p = ease_out((t - tr) / 0.4)
            paste(img, bucket(), 820, 1200)
            paste(img, sock("rag", "dead", 0, 0, (0, 0)), 760, 1080 - 40 * p, scale=0.7, angle=-20)
            for j in range(5):
                q = ((t * 1.3) + j / 5) % 1
                d.ellipse([700 + j * 30, 1250 + 120 * q, 712 + j * 30, 1266 + 120 * q], fill=(140, 190, 240, int(255 * (1 - q))))
            paste(img, sock("hero", "cry", m, bl, (1, 0)), 290, 1080 + bob, scale=0.7)
            out["grade"] = ((0.85, 0.9, 1.0), (0, 0, 10))

    elif k == "rache":
        ta = ctx.w("allein")
        if t >= ta - 0.4:
            p = ease_out((t - ta + 0.4) / 0.8)
            rnd = random.Random(21)
            for j in range(16):
                x = 60 + (j % 8) * 137 + (68 if j >= 8 else 0)
                y = (1080 if j < 8 else 1260) + rnd.uniform(-20, 20)
                tile = mini_sock(SOCK_COLS[j % len(SOCK_COLS)], 100 + j)
                sil = Image.new("RGBA", tile.size, (20, 0, 4, 255))
                sil.putalpha(tile.getchannel("A"))
                paste(img, sil, x, y + 200 * (1 - p), scale=1.2)
                dd = ImageDraw.Draw(img, "RGBA")
                ex, ey = x - 6, y + 200 * (1 - p) - 40
                for s in (-1, 1):
                    dd.ellipse([ex + s * 18 - 7, ey - 5, ex + s * 18 + 7, ey + 5], fill=(255, 40, 40, int(255 * p)))
        paste(img, sock("hero", "angry", m, bl, (0, 0), "sunglasses"), W / 2, 880 + bob, scale=1.05)

    elif k == "cta":
        paste(img, sock("hero", "smug", m, bl, (0, 0.5), "sunglasses"), W / 2, 660 + bob, scale=0.75)
    return out


def lerp(a, b, q):
    return a + (b - a) * q
