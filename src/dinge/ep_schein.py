"""Folge 1 – Der 50-Euro-Schein (müder, alter Veteran)."""
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

from chars import bill, trading_card
from core import (over, F_BODY, F_HAND, F_HEAD, H, INK, RED, W, WHITE, YELLOW, clamp01, ease_back, ease_out, font, glow,
                  paste, radial, shadowed, ss_image, vgrad)

TL = None
LABELS = {
    "druck": ("KAPITEL 1", "DIE GEBURT"),
    "karte": ("STATION 1", "GEBURTSTAGSKARTE"),
    "matratze": ("2019 – 2021", "DIE MATRATZE"),
    "wasch": ("60 GRAD", "WASCHMASCHINE"),
    "karte2": ("LETZTE WOCHE", "GEBURTSTAGSKARTE"),
}


# ------------------------------------------------------------------ backgrounds (static, cached)
@lru_cache(maxsize=None)
def bg(key):
    if key in ("hook", "cta", "punch"):
        im = radial(W, H, W / 2, 900, 1100, (70, 52, 40), (10, 8, 8))
    elif key == "druck":
        im = vgrad(W, H, (16, 26, 44), (6, 10, 18))
        d = ImageDraw.Draw(im)
        for r in range(9):          # faint sheet of uncut bills
            for c in range(3):
                x, y = 40 + c * 350, 520 + r * 160
                d.rounded_rectangle([x, y, x + 320, y + 140], radius=10, outline=(40, 60, 90), width=3)
                d.text((x + 16, y + 10), "50", font=font(F_HEAD, 34), fill=(40, 60, 90))
    elif key in ("karte", "karte2"):
        im = vgrad(W, H, (255, 214, 220), (250, 190, 150))
        d = ImageDraw.Draw(im)
        rnd = random.Random(2)
        for _ in range(60):
            x, y = rnd.uniform(0, W), rnd.uniform(0, H)
            d.rectangle([x, y, x + 14, y + 22], fill=rnd.choice([(255, 255, 255), (255, 120, 140), (120, 200, 255)]))
        card = card_tile(key == "karte2")
        im.paste(card, (int(W / 2 - card.width / 2), 520), card)
    elif key == "matratze":
        im = vgrad(W, H, (14, 20, 46), (4, 6, 14))
        d = ImageDraw.Draw(im)
        d.rectangle([700, 560, 960, 820], fill=(26, 36, 70), outline=(60, 70, 110), width=8)  # window
        d.line([830, 560, 830, 820], fill=(60, 70, 110), width=6)
        d.line([700, 690, 960, 690], fill=(60, 70, 110), width=6)
        d.ellipse([740, 590, 810, 660], fill=(240, 236, 200))
        d.ellipse([758, 584, 822, 648], fill=(26, 36, 70))
    elif key == "wasch":
        im = vgrad(W, H, (200, 214, 224), (150, 166, 180))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([60, 480, 1020, 1720], radius=40, fill=(238, 240, 242), outline=(120, 130, 140), width=6)
        d.rounded_rectangle([100, 520, 980, 640], radius=16, fill=(210, 214, 220))
        d.rounded_rectangle([680, 545, 940, 615], radius=10, fill=(20, 30, 30))
        d.text((810, 580), "60°  1400", font=font(F_HEAD, 34), fill=(80, 255, 160), anchor="mm")
        for k in range(4):
            d.ellipse([140 + k * 70, 560, 180 + k * 70, 600], fill=(170, 176, 186))
        d.ellipse([140, 720, 940, 1520], fill=(160, 166, 176), outline=(110, 116, 126), width=10)
        d.ellipse([190, 770, 890, 1470], fill=(70, 120, 170))
    else:
        im = Image.new("RGB", (W, H), (20, 20, 20))
    return im.convert("RGBA")


@lru_cache(maxsize=None)
def card_tile(old):
    def fn(d, ss, im):
        S = ss
        d.polygon([(30 * S, 40 * S), (480 * S, 10 * S), (480 * S, 700 * S), (30 * S, 660 * S)], fill=(250, 240, 230),
                  outline=INK)
        d.polygon([(480 * S, 10 * S), (930 * S, 40 * S), (930 * S, 660 * S), (480 * S, 700 * S)],
                  fill=(255, 250, 244), outline=INK)
        d.line([480 * S, 10 * S, 480 * S, 700 * S], fill=(200, 190, 180), width=4 * S)
        fh = font(F_HEAD, 58 * S)
        d.text((255 * S, 140 * S), "ALLES", font=fh, fill=(230, 70, 110), anchor="mm")
        d.text((255 * S, 215 * S), "GUTE!", font=fh, fill=(230, 70, 110), anchor="mm")
        for k, (x, c) in enumerate([(140, (255, 110, 110)), (250, (110, 180, 255)), (360, (255, 200, 60))]):
            d.ellipse([(x - 45) * S, 300 * S, (x + 45) * S, 410 * S], fill=c, outline=INK, width=3 * S)
            d.line([x * S, 410 * S, (x + 10) * S, 600 * S], fill=INK, width=3 * S)
        fhand = font(F_HAND, 62 * S)
        age = "zum 34." if old else "zum 8."
        lines = ["Lieber Paul,", f"alles Gute {age}", "Nicht alles auf", "einmal ausgeben!", "  Dein Opa"]
        for k, ln in enumerate(lines):
            d.text((520 * S, (90 + k * 66) * S), ln, font=fhand, fill=(40, 50, 120))
    return shadowed(ss_image(960, 720, fn), alpha=0.35)


@lru_cache(maxsize=None)
def icon(kind):
    def fn(d, ss, im):
        S = ss
        if kind == "matratze":
            d.rounded_rectangle([10 * S, 50 * S, 190 * S, 130 * S], radius=18 * S, fill=(240, 240, 250), outline=INK,
                                width=6 * S)
            for x in range(30, 190, 26):
                d.line([x * S, 54 * S, x * S, 126 * S], fill=(120, 150, 210), width=6 * S)
        elif kind == "wasch":
            d.rounded_rectangle([20 * S, 10 * S, 180 * S, 180 * S], radius=18 * S, fill=(240, 240, 244), outline=INK,
                                width=6 * S)
            d.ellipse([50 * S, 50 * S, 150 * S, 150 * S], fill=(90, 150, 210), outline=INK, width=6 * S)
        elif kind == "karte":
            d.polygon([(20 * S, 30 * S), (100 * S, 20 * S), (100 * S, 170 * S), (20 * S, 160 * S)], fill=(250, 230, 235),
                      outline=INK)
            d.polygon([(100 * S, 20 * S), (180 * S, 30 * S), (180 * S, 160 * S), (100 * S, 170 * S)],
                      fill=(255, 250, 250), outline=INK)
            d.ellipse([40 * S, 70 * S, 80 * S, 110 * S], fill=(240, 80, 110))
    return shadowed(ss_image(200, 190, fn), dy=8, blur=8, pad=20)


@lru_cache(maxsize=None)
def bubble(text, w=420, h=150, jag=True):
    def fn(d, ss, im):
        S = ss
        cx, cy = w / 2 * S, h / 2 * S
        pts = []
        for k in range(24):
            a = 2 * math.pi * k / 24
            r = 1.0 if k % 2 == 0 else 0.8
            pts.append((cx + math.cos(a) * (w / 2 - 6) * S * r, cy + math.sin(a) * (h / 2 - 6) * S * r))
        d.polygon(pts, fill=(255, 255, 255), outline=INK)
        d.text((cx, cy), text, font=font(F_HEAD, 34 * S), fill=RED, anchor="mm")
    return ss_image(w, h, fn)


@lru_cache(maxsize=None)
def dream_bubble():
    def fn(d, ss, im):
        S = ss
        for (x, y, r) in [(80, 380, 22), (130, 330, 34)]:
            d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=WHITE, outline=INK, width=4 * S)
        d.ellipse([140 * S, 20 * S, 660 * S, 300 * S], fill=WHITE, outline=INK, width=5 * S)
        d.text((400 * S, 80 * S), "MEINE TRÄUME:", font=font(F_HEAD, 34 * S), fill=INK, anchor="mm")
        for k, ln in enumerate(["• ein Sparbuch", "• eine Brieftasche aus Leder", "• Weltreise"]):
            d.text((230 * S, (120 + k * 52) * S), ln, font=font(F_HAND, 50 * S), fill=(40, 50, 120))
    return ss_image(680, 420, fn)


@lru_cache(maxsize=None)
def stamp(text, col=RED, size=96):
    f = font(F_HEAD, size)
    tw = f.getlength(text)

    def fn(d, ss, im):
        S = ss
        d.rounded_rectangle([8 * S, 8 * S, im.width - 8 * S, im.height - 8 * S], radius=18 * S, outline=col, width=10 * S)
        d.text((im.width / 2, im.height / 2), text, font=font(F_HEAD, size * S), fill=col, anchor="mm")
    return ss_image(int(tw + 80), size + 70, fn)


# ------------------------------------------------------------------ scene drawing
def talk(ctx):
    return ctx.mouth


def draw(img, ctx):
    k, lt, sd, t = ctx.scene, ctx.lt, ctx.sd, ctx.t
    over(img, bg(k))
    m, bl = talk(ctx), ctx.blink
    bob = 6 * math.sin(t * 2.2)
    out = {}

    if k == "hook":
        emo = "tired"
        t2 = ctx.w("zweimal")
        if t >= t2:
            emo = "stare"
        sc = 1.38 - 0.06 * ease_out(lt / 2)
        paste(img, bill(50, emo, m, bl, (0, 0)), W / 2, 880 + bob, scale=sc, angle=2 * math.sin(t * 1.3))
        for j, (word, ic, x) in enumerate([("matratze", "matratze", 230), ("waschmaschine", "wasch", 540),
                                           ("geburtstagskarte", "karte", 850)]):
            ta = ctx.w(word)
            if t >= ta:
                kk = ease_back((t - ta) / 0.3, 2)
                paste(img, icon(ic), x, 1180 + 8 * math.sin(t * 3 + j), scale=0.3 + 0.7 * kk)
        if t >= t2:
            kk = ease_back((t - t2) / 0.25, 2.5)
            paste(img, stamp("×2"), 830, 600, scale=2.2 - 1.2 * kk, angle=-12)

    elif k == "druck":
        a = ease_out(lt / 1.0)
        # light rays
        ray = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ray)
        for j in range(9):
            ang = math.radians(90 + (j - 4) * 9 + 2 * math.sin(t + j))
            d.polygon([(540, 300), (540 + 1600 * math.cos(ang - 0.04), 300 + 1600 * math.sin(ang - 0.04)),
                       (540 + 1600 * math.cos(ang + 0.04), 300 + 1600 * math.sin(ang + 0.04))],
                      fill=(255, 230, 160, 22))
        over(img, ray)
        y = 300 + 600 * a
        paste(img, bill(50, "neutral", m, bl, (0, -0.5)), W / 2, y + bob, scale=1.1, angle=8 * (1 - a))
        td = ctx.w("träume")
        if t >= td:
            kk = ease_back((t - td) / 0.35, 1.8)
            paste(img, dream_bubble(), 560, 1090, scale=0.3 + 0.7 * kk)
        if lt < 0.6:
            out["zoom"] = 0.05 * (1 - lt / 0.6)

    elif k in ("karte", "karte2"):
        old = k == "karte2"
        t_out = ctx.w("gibt") if not old else 1e9
        t_cards = ctx.w("pokémon") if not old else 1e9
        x, y, ang = 540, 1080, -6
        if t >= t_out:
            p = ease_out((t - t_out) / 0.7)
            x, y, ang = 540 + 700 * p, 1080 - 300 * p, -6 - 40 * p
        emo = "sad" if t >= t_out else ("tired" if old else "neutral")
        paste(img, bill(50, emo, m, bl, (0.6, -0.3)), x, y + bob, scale=0.95, angle=ang)
        if t >= t_cards:
            rnd = random.Random(5)
            for j in range(14):
                st = t_cards + j * 0.05
                if t < st:
                    continue
                p = t - st
                cx = 540 + rnd.uniform(-480, 480) + 40 * math.sin(p * 2 + j)
                cy = 500 + p * rnd.uniform(500, 800) - 200
                paste(img, trading_card(j % 7), cx, cy, scale=0.9, angle=rnd.uniform(-40, 40) + p * 60)
        if old:
            t34 = ctx.w("34")
            if t >= t34:
                kk = ease_back((t - t34) / 0.3, 2)
                paste(img, stamp("34!", RED, 90), 860, 640, scale=1.8 - 0.8 * kk, angle=10)
            # grandpa's hand trembles: card shakes slightly
            out["shake"] = 1.5
        out["grade"] = ((1.0, 0.97, 0.94), (0, 0, 0)) if old else None

    elif k == "matratze":
        # mattress from the side, squashing the bill
        d = ImageDraw.Draw(img, "RGBA")
        my = 900
        d.rounded_rectangle([-40, my - 260, W + 40, my + 40], radius=60, fill=(232, 232, 244), outline=INK, width=8)
        for x in range(0, W, 46):
            d.line([x, my - 252, x, my + 32], fill=(130, 160, 220), width=10)
        d.rectangle([-40, my + 40, W + 40, H], fill=(60, 40, 30))
        d.rectangle([-40, my + 40, W + 40, my + 70], fill=(90, 60, 40))
        squash = 0.86 + 0.03 * math.sin(t * 1.7)
        b = bill(50, "stare" if t >= ctx.w("nachts") else "tired", m, bl, (0, -1))
        b2 = b.resize((int(b.width * 0.9), int(b.height * 0.9 * squash)), Image.BILINEAR)
        paste(img, b2, W / 2, my + 70 + b2.height / 2 - 60)
        tn = ctx.w("nachts")
        for j, (txt, x, y, dt) in enumerate([("DU HAST IMMER…!", 330, 590, 0.0), ("ICH?!", 790, 560, 0.6),
                                              ("#@%&!", 560, 620, 1.2)]):
            if t >= tn + dt:
                kk = ease_back((t - tn - dt) / 0.25, 2)
                paste(img, bubble(txt), x + 4 * math.sin(t * 30 + j), y, scale=0.4 + 0.6 * kk, angle=4 - 8 * (j % 2))
        out["grade"] = ((0.85, 0.9, 1.1), (0, 0, 8))

    elif k == "wasch":
        cx, cy = 540, 1120
        ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ring)
        rot = t * 2.2
        for j in range(14):    # bubbles
            a = rot * 0.7 + j * 0.45
            r = 120 + (j * 37) % 200
            x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
            d.ellipse([x - 14, y - 14, x + 14, y + 14], outline=(230, 245, 255, 200), width=4)
        over(img, ring)
        tz = ctx.w("zerfällt")
        te = ctx.w("zwanziger", 1)
        fade = clamp01((t - tz) / max(0.5, te - tz + 0.6))
        emo = "sad" if t < ctx.w("flüstert") else "cry"
        paste(img, bill(50, emo, m, bl, (0.5, 0), wet=True, shadow=False), cx + 150 * math.cos(rot),
              cy + 150 * math.sin(rot), scale=0.62, angle=-math.degrees(rot) * 0.5)
        if fade < 1:
            m2 = 0.0
            tf = ctx.w("flüstert")
            if tf + 0.5 < t < ctx.w("familie") + 0.5:
                m2 = 0.25 + 0.2 * math.sin(t * 20)
            tw = bill(20, "tired", m2, ctx.blink, (-0.5, 0), wet=True, shadow=False)
            a2 = 1 - fade
            px, py = cx + 150 * math.cos(rot + math.pi), cy + 150 * math.sin(rot + math.pi)
            paste(img, tw, px, py, scale=0.5 * (1 - 0.25 * fade), angle=-math.degrees(rot) * 0.5, alpha=a2)
            if fade > 0:
                d = ImageDraw.Draw(img, "RGBA")
                rnd = random.Random(int(t * 10))
                for _ in range(int(30 * fade)):
                    x, y = px + rnd.uniform(-140, 140), py + rnd.uniform(-90, 90)
                    d.rectangle([x, y, x + 10, y + 10], fill=(112, 156, 214, int(200 * (1 - fade))))
        # glass reflection over drum
        refl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(refl)
        dr.arc([230, 810, 850, 1430], 200, 260, fill=(255, 255, 255, 120), width=26)
        over(img, refl)
        if t >= ctx.w("hatte"):
            paste(img, stamp("R.I.P. 20 €", (240, 240, 240), 54), 540, 1600, angle=-4,
                  alpha=clamp01((t - ctx.w("hatte")) / 0.3))
        out["shake"] = 3.0

    elif k == "punch":
        rnd = random.Random(11)
        for j in range(26):
            p = lt * rnd.uniform(0.8, 1.4)
            a = rnd.uniform(0, 2 * math.pi)
            r = 120 + p * rnd.uniform(500, 900)
            paste(img, trading_card(j % 7), 540 + math.cos(a) * r, 900 + math.sin(a) * r, scale=1.0,
                  angle=rnd.uniform(-90, 90) + p * 200)
        paste(img, bill(50, "dead" if lt > 0.9 else "tired", m, bl, (0, 0)), W / 2, 900 + bob, scale=1.2)
        if lt > 0.25:
            kk = ease_back((lt - 0.25) / 0.25, 2.5)
            paste(img, stamp("SCHON WIEDER.", YELLOW, 70), 540, 1170, scale=2 - kk, angle=-6)

    elif k == "cta":
        paste(img, bill(50, "neutral", m, bl, (0, 0.6)), W / 2, 680 + bob, scale=0.85)
    return out
