"""Folge 2 – Die Pfandflasche (Kriegsveteranin, 49 Einsätze)."""
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

from chars import bottle
from core import (over, F_BODY, F_HAND, F_HEAD, H, INK, RED, W, WHITE, YELLOW, clamp01, ease_back, ease_io, ease_out, face,
                  font, paste, radial, shadowed, ss_image, vgrad)
from ep_schein import stamp

TL = None
LABELS = {
    "abi": ("EINSATZ 1", "ABIFEIER"),
    "festival": ("EINSATZ 12", "FESTIVAL"),
    "date": ("EINSATZ 30", "ERSTES DATE"),
    "automat": ("EINSATZ 49", "DER AUTOMAT"),
    "danke": ("VERSUCH 6", "DER AUTOMAT"),
}


@lru_cache(maxsize=None)
def bg(key):
    if key in ("hook", "cta"):
        im = radial(W, H, W / 2, 950, 1150, (58, 64, 46), (8, 10, 8))
    elif key == "punch":
        im = radial(W, H, W / 2, 900, 1100, (120, 90, 30), (20, 12, 4))
    elif key == "abi":
        im = vgrad(W, H, (60, 16, 90), (14, 4, 30))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 1560, W, 1650], fill=(240, 240, 240))
        d.text((W / 2, 1605), "ABI 2019 · WIR SIND RAUS!", font=font(F_HEAD, 46), fill=(200, 40, 120), anchor="mm")
    elif key == "festival":
        im = vgrad(W, H, (120, 130, 140), (80, 84, 90))
        d = ImageDraw.Draw(im)
        d.polygon([(40, 1180), (330, 700), (620, 1180)], fill=(236, 120, 40), outline=INK)
        d.polygon([(330, 700), (290, 1180), (370, 1180)], fill=(30, 20, 10))
        d.polygon([(0, 1150), (W, 1110), (W, H), (0, H)], fill=(96, 70, 44))
        rnd = random.Random(1)
        for _ in range(40):
            x, y = rnd.uniform(0, W), rnd.uniform(1150, H)
            d.ellipse([x, y, x + rnd.uniform(40, 140), y + rnd.uniform(12, 30)], fill=(76, 54, 34))
    elif key == "date":
        im = radial(W, H, W / 2, 900, 1100, (110, 24, 30), (16, 4, 6))
        d = ImageDraw.Draw(im)
        d.polygon([(0, 1280), (W, 1280), (W, H), (0, H)], fill=(240, 236, 230))
        for x in range(0, W, 120):
            d.rectangle([x, 1280, x + 60, H], fill=(214, 60, 60))
            d.rectangle([x + 60, 1280, x + 120, H], fill=(245, 240, 236))
    elif key in ("automat", "danke"):
        im = vgrad(W, H, (196, 204, 210), (150, 158, 166))
        d = ImageDraw.Draw(im)
        for y in range(460, H, 90):
            d.line([0, y, W, y], fill=(176, 184, 192), width=3)
        for x in range(0, W, 90):
            d.line([x, 460, x, H], fill=(176, 184, 192), width=3)
        d.rectangle([0, 1500, W, H], fill=(120, 126, 132))
    else:
        im = Image.new("RGB", (W, H), (0, 0, 0))
    return im.convert("RGBA")


@lru_cache(maxsize=60)
def machine(emo, display, ok=False):
    def fn(d, ss, im):
        S = ss
        d.rounded_rectangle([10 * S, 10 * S, 560 * S, 1050 * S], radius=30 * S, fill=(226, 230, 234), outline=INK,
                            width=8 * S)
        d.rectangle([10 * S, 10 * S, 560 * S, 110 * S], fill=(30, 140, 80))
        d.text((285 * S, 62 * S), "LEERGUT", font=font(F_HEAD, 52 * S), fill=WHITE, anchor="mm")
        # screen with face
        scr = (12, 40, 24) if ok else (30, 8, 10)
        d.rounded_rectangle([70 * S, 150 * S, 500 * S, 460 * S], radius=22 * S, fill=scr, outline=INK, width=6 * S)
        if display:
            d.text((285 * S, 410 * S), display, font=font(F_HEAD, 40 * S), fill=(90, 255, 140) if ok else (255, 70, 70),
                   anchor="mm")
        face(d, 285, 270, 1.15, emo, 0.0, 0.0, (-1, 0), lid=scr, ss=ss)
        # bottle hole
        d.ellipse([195 * S, 560 * S, 375 * S, 740 * S], fill=(40, 40, 46), outline=INK, width=8 * S)
        d.ellipse([225 * S, 590 * S, 345 * S, 710 * S], fill=(10, 10, 12))
        # receipt slot + button
        d.rounded_rectangle([170 * S, 840 * S, 400 * S, 870 * S], radius=8 * S, fill=(40, 40, 46))
        d.ellipse([240 * S, 910 * S, 330 * S, 1000 * S], fill=(40, 180, 90), outline=INK, width=6 * S)
    return shadowed(ss_image(570, 1060, fn), alpha=0.4)


@lru_cache(maxsize=None)
def receipt():
    def fn(d, ss, im):
        S = ss
        d.rectangle([0, 0, 220 * S, 330 * S], fill=(252, 252, 248), outline=(180, 180, 180), width=2 * S)
        f = font(F_BODY, 26 * S)
        for k, ln in enumerate(["LEERGUT", "--------", "1× MEHRWEG", "0,08 €", "--------", "DANKE!"]):
            d.text((110 * S, (40 + k * 48) * S), ln, font=f, fill=INK, anchor="mm")
    return ss_image(220, 330, fn)


def note_glyph(d, x, y, s, col):
    d.ellipse([x, y + 40 * s, x + 30 * s, y + 62 * s], fill=col)
    d.rectangle([x + 24 * s, y, x + 30 * s, y + 52 * s], fill=col)
    d.polygon([(x + 30 * s, y), (x + 52 * s, y + 14 * s), (x + 30 * s, y + 20 * s)], fill=col)


def draw(img, ctx):
    k, lt, sd, t = ctx.scene, ctx.lt, ctx.sd, ctx.t
    over(img, bg(k))
    m, bl = ctx.mouth, ctx.blink
    bob = 6 * math.sin(t * 2.0)
    out = {}
    d = ImageDraw.Draw(img, "RGBA")

    if k == "hook":
        rnd = random.Random(3)
        # distant flashes + drifting smoke (war memoir)
        fl = max(0.0, math.sin(t * 3.1) * math.sin(t * 1.7)) ** 6
        if fl > 0.05:
            ov = Image.new("RGBA", (W, H), (255, 150, 60, int(60 * fl)))
            over(img, ov)
        for j in range(18):
            x = (rnd.uniform(0, W) + t * rnd.uniform(20, 60)) % (W + 300) - 150
            y = rnd.uniform(500, 1700)
            r = rnd.uniform(80, 200)
            d.ellipse([x - r, y - r * 0.5, x + r, y + r * 0.5], fill=(120, 120, 110, 26))
        emo = "stare" if t < ctx.w("ich") else "tired"
        paste(img, bottle(emo, m, bl, (0, 0)), W / 2, 940 + bob, scale=1.15)
        out["grade"] = ((0.95, 1.0, 0.9), (0, 0, 0))

    elif k == "abi":
        rot = t * 1.5
        ray = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(ray)
        cols = [(255, 60, 180, 40), (60, 200, 255, 40), (255, 220, 60, 40)]
        for j in range(6):
            a = rot + j * math.pi / 3
            dr.polygon([(540, 700), (540 + 1400 * math.cos(a - 0.1), 700 + 1400 * math.sin(a - 0.1)),
                        (540 + 1400 * math.cos(a + 0.1), 700 + 1400 * math.sin(a + 0.1))], fill=cols[j % 3])
        over(img, ray)
        d.ellipse([480, 640, 600, 760], fill=(200, 200, 210), outline=INK, width=4)   # disco ball
        for j in range(5):
            d.line([480 + j * 24, 645, 480 + j * 24, 755], fill=(150, 150, 160), width=2)
        rnd = random.Random(8)
        for j in range(50):
            x = rnd.uniform(0, W) + 30 * math.sin(t * 2 + j)
            y = (rnd.uniform(0, H) + t * rnd.uniform(100, 250)) % H
            d.rectangle([x, y, x + 12, y + 18], fill=rnd.choice([(255, 80, 160), (80, 220, 255), (255, 230, 80)]))
        emo = "shock" if t >= ctx.w("nie") else "neutral"
        ang = 12 * math.sin(t * 6) if t < ctx.w("ich") else 3 * math.sin(t * 2)
        paste(img, bottle(emo, m, bl, (0, 0), tag="#1"), W / 2, 1060 + bob, scale=0.95, angle=ang)

    elif k == "festival":
        rnd = random.Random(4)
        for j in range(70):          # rain
            x = (rnd.uniform(0, W) + t * 120) % W
            y = (rnd.uniform(0, H) + t * 1400 * rnd.uniform(0.8, 1.2)) % H
            d.line([x, y, x - 10, y + 40], fill=(200, 210, 230, 120), width=3)
        for j in range(4):            # music notes from the tent
            p = (t * 0.6 + j / 4) % 1
            note_glyph(d, 300 + 180 * p + 30 * math.sin(t * 3 + j), 1000 - 420 * p, 1.4, (255, 230, 80, int(255 * (1 - p))))
        hours = min(72, 1 + int(max(0, t - ctx.w("drei")) * 14))
        paste(img, stamp(f"STUNDE {hours:02d}/72", YELLOW, 44), 780, 660, angle=4)
        paste(img, bottle("tired", m, bl, (-0.6, 0), tag="#12"), 780, 1180 + bob * 0.3, scale=0.85, angle=-14)
        # mud in front of the bottle
        d.polygon([(560, 1330), (1080, 1300), (1080, 1500), (560, 1500)], fill=(96, 70, 44))
        d.ellipse([560, 1270, 1010, 1360], fill=(96, 70, 44))
        if t >= ctx.w("ohne"):
            paste(img, stamp("OHNE PAUSE", RED, 56), 300, 880, angle=-8, alpha=clamp01((t - ctx.w("ohne")) / 0.2))

    elif k == "date":
        t_end = ctx.w("schluss")
        emo = "neutral" if t < t_end else ("sad" if t < ctx.w("schuld") else "cry")
        bx, by = W / 2, 1060
        paste(img, bottle(emo, m, bl, (0, 0), tag="#30"), bx, by, scale=0.9)
        # candle stuck in the bottle neck
        top = by - 790 * 0.9 / 2 + 12
        d.rounded_rectangle([bx - 20, top - 160, bx + 20, top + 10], radius=8, fill=(250, 246, 236), outline=INK, width=4)
        d.ellipse([bx - 26, top - 150, bx - 10, top - 100], fill=(250, 246, 236))
        if t < t_end + 0.1:
            fl = 1 + 0.12 * math.sin(t * 23) + 0.08 * math.sin(t * 37)
            glowl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glowl)
            gd.ellipse([bx - 160, top - 360, bx + 160, top - 40], fill=(255, 190, 90, 40))
            over(img, glowl)
            d.ellipse([bx - 16 * fl, top - 230 * fl + 20, bx + 16 * fl, top - 162], fill=(255, 200, 60))
            d.ellipse([bx - 8, top - 205, bx + 8, top - 168], fill=(255, 250, 220))
        else:
            p = t - t_end
            for j in range(4):
                yy = top - 170 - p * 120 - j * 40
                d.ellipse([bx - 12 + 20 * math.sin(p * 3 + j), yy - 12, bx + 12 + 20 * math.sin(p * 3 + j), yy + 12],
                          fill=(200, 200, 200, max(0, int(140 - p * 50 - j * 20))))
            kk = ease_back(p / 0.3, 2)
            paste(img, broken_heart(), 840, 760, scale=0.3 + 0.7 * kk, angle=10)
        out["grade"] = ((1.05, 0.95, 0.9), (0, 0, 0))

    elif k in ("automat", "danke"):
        ok = k == "danke" and t >= ctx.w("danke", scene="danke")
        t_sp = TL.word("spuckt", 0, "automat")
        t_5 = TL.word("fünfmal", 0, "automat") + 0.7
        rejects = 0
        mx, my = 760, 1050
        # bottle animation: 5 rejects spread between "spuckt" and end of "Fünfmal"
        bx, by, ang = 330, 1140, 0
        if k == "automat" and t >= t_sp:
            per = (t_5 - t_sp) / 5
            n = int((t - t_sp) / per)
            rejects = min(5, n + 1)
            if n < 5:
                p = ((t - t_sp) % per) / per
                if p < 0.45:
                    q = ease_io(p / 0.45)
                    bx, by, ang = lerp_xy(330, 640, q), 1140 - 130 * q, 90 * q
                else:
                    q = ease_out((p - 0.45) / 0.55)
                    bx, by, ang = 640 - 380 * q, 1010 + 130 * q - 220 * math.sin(math.pi * q), 90 + 340 * q
        if k == "danke":
            rejects = 5
        disp = "DANKE!" if ok else (f"ABGELEHNT ×{rejects}" if rejects else "")
        memo = "smug" if ok else ("angry" if rejects else "stare")
        paste(img, machine(memo, disp, ok), mx, my)
        if ok:
            p = clamp01((t - ctx.w("danke", scene="danke")) / 1.2)
            paste(img, receipt(), mx - 5, my - 115 + 260 * ease_out(p) + 165, scale=0.8)
        if k == "danke":
            bemo = "cry" if t >= ctx.w("geweint") else "shock"
            paste(img, bottle(bemo, m, bl, (1, 0), tag="#49"), 290, 1080 + bob, scale=0.8)
            if t >= ctx.w("flaschen"):
                for j in range(6):
                    p = ((t * 1.2) + j / 6) % 1
                    d.ellipse([300 + 40 * math.sin(j), 760 + 400 * p, 318 + 40 * math.sin(j), 784 + 400 * p],
                              fill=(120, 200, 255, int(255 * (1 - p))))
        else:
            emo = "sad" if t >= ctx.w("wisst") else ("shock" if rejects else "neutral")
            paste(img, bottle(emo, m, bl, (1, 0), tag="#49"), bx, by + bob, scale=0.8, angle=-ang)
        if rejects and not ok:
            out["shake"] = 4.0 if k == "automat" and t < t_5 else 0.0

    elif k == "punch":
        ray = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(ray)
        for j in range(16):
            a = t * 0.4 + j * math.pi / 8
            dr.polygon([(540, 900), (540 + 1500 * math.cos(a - 0.08), 900 + 1500 * math.sin(a - 0.08)),
                        (540 + 1500 * math.cos(a + 0.08), 900 + 1500 * math.sin(a + 0.08))], fill=(255, 220, 120, 34))
        over(img, ray)
        paste(img, bottle("cry", m, bl, (0, -0.5), tag="#49"), W / 2, 940 + bob, scale=1.05)
        # medal
        mx, my = W / 2 + 4, 940 - 790 * 1.05 / 2 + 330
        d.polygon([(mx - 40, my - 70), (mx, my), (mx + 40, my - 70)], fill=(40, 90, 200))
        d.ellipse([mx - 42, my - 10, mx + 42, my + 74], fill=(240, 196, 60), outline=INK, width=5)
        d.text((mx, my + 32), "0,08", font=font(F_BODY, 22), fill=INK, anchor="mm")
        rnd = random.Random(8)
        for j in range(40):
            x = rnd.uniform(0, W) + 30 * math.sin(t * 2 + j)
            y = (rnd.uniform(0, H) + t * rnd.uniform(100, 250)) % H
            d.rectangle([x, y, x + 12, y + 18], fill=rnd.choice([(255, 200, 60), (255, 255, 255), (255, 120, 60)]))

    elif k == "cta":
        paste(img, bottle("neutral", m, bl, (0, 0.5)), W / 2, 640 + bob, scale=0.6)
    return out


def lerp_xy(a, b, q):
    return a + (b - a) * q


@lru_cache(maxsize=None)
def broken_heart():
    def fn(d, ss, im):
        S = ss
        for side in (-1, 1):
            off = side * 14 * S
            pts = []
            for k in range(0, 181):
                a = math.radians(k * 2)
                x = 16 * math.sin(a) ** 3
                y = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
                if (x >= 0) == (side > 0):
                    pts.append((120 * S + x * 6 * S + off, 110 * S + y * 6 * S))
            zig = [(120 * S + off, 20 * S), (100 * S + off, 70 * S), (135 * S + off, 110 * S), (110 * S + off, 150 * S),
                   (120 * S + off, 210 * S)]
            d.polygon(pts + (zig[::-1] if side > 0 else zig), fill=(230, 40, 60), outline=INK)
    return ss_image(240, 230, fn)
