"""All shots. Every shot is fn(lt, dur, T) -> RGBA frame (W x H). lt = local time in shot, T = global time."""
import math
import random
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from chars import (CAR_COL, ORANGE, bike, car_side, head, person, person_layer, phone_broken, star, wheel_closeup)
from core import (BLUE, F_BLACK, F_BOLD, F_HAND, F_INTER, F_INTER_B, H, MAGENTA, RED, TEAL, W, WHITE, YELLOW,
                  capsule, clamp01, ease_back, ease_in, ease_io, ease_out, emoji, extrude_text, font, glitch,
                  glow_dot, gradient, lerp, mixc, paste_c, radial, sphere, text_img)
from core import zoom_frame as _zoom


def zoom_frame(img, z, cx=None, cy=None):
    """Camera zoom that never shows the area outside the frame."""
    if z < 1.0005:
        return img
    cx = img.width / 2 if cx is None else cx
    cy = img.height / 2 if cy is None else cy
    hw, hh = img.width / z / 2, img.height / z / 2
    cx = min(max(cx, hw), img.width - hw)
    cy = min(max(cy, hh), img.height - hh)
    return _zoom(img, z, cx, cy)

CTX = {"mouth": lambda who, T: 0.0}
GREEN = (60, 220, 120)


def M(who, T):
    return CTX["mouth"](who, T)


def blink(T, seed):
    return (T + seed * 0.37) % 3.3 < 0.11


# ------------------------------------------------------------------ backgrounds
PW = 3600
GROUND = 1150   # building base / sidewalk top
LANE = 1262     # bike lane top
ROAD = 1336     # road top


@lru_cache(maxsize=None)
def street_pano():
    im = gradient(PW, H, (96, 170, 235), (255, 222, 190))
    d = ImageDraw.Draw(im)
    rnd = random.Random(11)
    # sun + clouds
    paste_c(im, radial(900, (255, 240, 200), 0.8), 2600, 260)
    for k in range(9):
        cx, cy = rnd.uniform(0, PW), rnd.uniform(120, 420)
        for j in range(4):
            paste_c(im, radial(int(rnd.uniform(160, 260)), (255, 255, 255), 0.85, 1.2), cx + j * 90, cy +
                    rnd.uniform(-20, 20))
    pastel = [(240, 214, 170), (205, 225, 235), (238, 190, 170), (220, 230, 200), (245, 235, 215), (200, 200, 225),
              (250, 205, 140)]
    shops = {1: ("BÄCKEREI", "🥨", (200, 120, 40)), 3: ("APOTHEKE", None, (30, 150, 80)),
             5: ("KIOSK", "📰", (40, 90, 170)), 7: ("BÄCKEREI", "🥐", (200, 120, 40)),
             9: ("CAFÉ", "☕", (130, 60, 40))}
    x, i = -40, 0
    while x < PW:
        bw = rnd.randint(380, 520)
        bh = rnd.randint(720, 930)
        top = GROUND - bh
        col = pastel[i % len(pastel)]
        d.rectangle([x, top, x + bw, GROUND], fill=col)
        d.rectangle([x, top, x + 10, GROUND], fill=mixc(col, (0, 0, 0), 0.12))
        # roof
        d.polygon([(x - 10, top), (x + bw + 10, top), (x + bw - 40, top - 110), (x + 40, top - 110)],
                  fill=(120, 70, 60) if i % 2 else (80, 80, 96))
        if i % 3 == 0:
            d.rectangle([x + bw * 0.25, top - 90, x + bw * 0.4, top + 10], fill=(160, 90, 70))
        # cornices
        for yy in range(top + 20, GROUND - 260, 170):
            d.rectangle([x, yy, x + bw, yy + 10], fill=mixc(col, (255, 255, 255), 0.4))
        # windows
        nwin = 3 if bw < 460 else 4
        gap = bw / nwin
        for yy in range(top + 60, GROUND - 300, 170):
            for k in range(nwin):
                wx = x + gap * k + gap * 0.26
                ww = gap * 0.48
                d.rectangle([wx - 6, yy - 6, wx + ww + 6, yy + 106], fill=(250, 250, 245))
                d.rectangle([wx, yy, wx + ww, yy + 100], fill=(70, 110, 150))
                d.line([(wx + ww / 2, yy), (wx + ww / 2, yy + 100)], fill=(250, 250, 245), width=5)
                d.line([(wx + 6, yy + 8), (wx + ww * 0.35, yy + 8)], fill=(170, 210, 240), width=6)
                if rnd.random() < 0.3:
                    d.rectangle([wx - 10, yy + 106, wx + ww + 10, yy + 124], fill=(170, 60, 60))
                    for f in range(4):
                        d.ellipse([wx + f * ww / 4, yy + 92, wx + f * ww / 4 + 22, yy + 114],
                                  fill=rnd.choice([(255, 80, 120), (255, 220, 60), (240, 120, 200)]))
        # ground floor
        gy = GROUND - 240
        if i in shops:
            name, icon, sc = shops[i]
            d.rectangle([x + 20, gy, x + bw - 20, GROUND], fill=(60, 60, 70))
            d.rectangle([x + 40, gy + 70, x + bw - 40, GROUND - 10], fill=(150, 200, 225))
            d.rectangle([x + 10, gy - 70, x + bw - 10, gy + 10], fill=sc)
            t = text_img(name, 50, WHITE, F_BLACK, max_w=bw)
            paste_c(im, t, x + bw / 2, gy - 30)
            if icon:
                paste_c(im, emoji(icon, 90), x + bw - 70, gy - 30)
            if name == "APOTHEKE":
                d.rectangle([x + 50, gy - 160, x + 110, gy - 100], fill=(220, 30, 40))
            # awning stripes
            for k in range(int(bw / 50)):
                d.polygon([(x + 10 + k * 50, gy + 10), (x + 35 + k * 50, gy + 10), (x + 30 + k * 50, gy + 60),
                           (x + 15 + k * 50, gy + 60)], fill=WHITE if k % 2 else sc)
        else:
            d.rectangle([x + bw * 0.4, gy + 30, x + bw * 0.6, GROUND], fill=(110, 70, 50))
            d.ellipse([x + bw * 0.4, gy - 20, x + bw * 0.6, gy + 70], fill=(110, 70, 50))
        x += bw
        i += 1
    # sidewalk, bike lane, curb, road
    d.rectangle([0, GROUND, PW, LANE], fill=(200, 196, 190))
    for xx in range(0, PW, 90):
        d.line([(xx, GROUND), (xx - 30, LANE)], fill=(180, 176, 170), width=3)
    d.rectangle([0, LANE, PW, ROAD], fill=(196, 80, 70))
    for xx in range(200, PW, 900):
        d.ellipse([xx - 50, LANE + 18, xx - 10, ROAD - 18], outline=WHITE, width=5)
        d.ellipse([xx + 10, LANE + 18, xx + 50, ROAD - 18], outline=WHITE, width=5)
        d.line([(xx - 30, (LANE + ROAD) / 2), (xx, LANE + 22), (xx + 30, (LANE + ROAD) / 2)], fill=WHITE, width=5)
    d.rectangle([0, ROAD - 10, PW, ROAD + 8], fill=(235, 235, 235))
    d.rectangle([0, ROAD + 8, PW, H], fill=(64, 66, 74))
    for xx in range(0, PW, 260):
        d.rectangle([xx, 1690, xx + 140, 1706], fill=(240, 240, 240))
    # trees + signs
    for xx in range(150, PW, 700):
        d.rectangle([xx - 14, GROUND - 200, xx + 14, GROUND + 40], fill=(100, 70, 50))
        for j in range(5):
            paste_c(im, sphere(int(rnd.uniform(170, 240)), (60, 150, 70), (160, 255, 150), 0.1),
                    xx + rnd.uniform(-90, 90), GROUND - 300 + rnd.uniform(-90, 50))
    for xx in (1050, 2750):
        d.rectangle([xx - 7, GROUND - 280, xx + 7, GROUND + 60], fill=(140, 145, 150))
        d.ellipse([xx - 70, GROUND - 420, xx + 70, GROUND - 280], fill=WHITE, outline=(220, 30, 40), width=22)
        d.text((xx, GROUND - 350), "30", font=font(F_BLACK, 66), fill=(20, 20, 20), anchor="mm")
    return im


def street(cam_x, zoom=1.0, zy=None):
    p = street_pano()
    cam_x = int(max(0, min(PW - W, cam_x)))
    f = p.crop((cam_x, 0, cam_x + W, H))
    if zoom != 1.0:
        f = zoom_frame(f, zoom, W / 2, zy if zy is not None else 1300)
    return f


@lru_cache(maxsize=None)
def bg_dark(top=(12, 10, 28), bottom=(30, 12, 50)):
    return gradient(W, H, top, bottom)


@lru_cache(maxsize=None)
def asphalt():
    rnd = np.random.default_rng(3)
    a = rnd.normal(70, 14, (H // 2, W // 2)).clip(0, 255).astype(np.uint8)
    im = Image.fromarray(a).resize((W, H), Image.BILINEAR).convert("RGBA")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 1250, W, 1300], fill=(235, 235, 235))
    return im


@lru_cache(maxsize=None)
def park_bg():
    im = gradient(W, H, (120, 190, 240), (250, 230, 200))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 1100, W, H], fill=(90, 170, 80))
    d.rectangle([0, 1100, W, 1130], fill=(70, 140, 60))
    rnd = random.Random(4)
    for xx in (60, 330, 760, 1020):
        d.rectangle([xx - 20, 700, xx + 20, 1120], fill=(100, 70, 50))
        for j in range(6):
            paste_c(im, sphere(int(rnd.uniform(200, 280)), (60, 150, 70), (160, 255, 150), 0.1),
                    xx + rnd.uniform(-120, 120), 600 + rnd.uniform(-120, 80))
    d.polygon([(380, H), (700, H), (560, 1100), (520, 1100)], fill=(210, 190, 150))
    return im


def bench(frame, cx, y, w=900):
    d = ImageDraw.Draw(frame)
    for k in range(3):
        d.rounded_rectangle([cx - w / 2, y + k * 44, cx + w / 2, y + k * 44 + 32], radius=10, fill=(150, 90, 50),
                            outline=(110, 60, 30), width=4)
    d.rounded_rectangle([cx - w / 2 - 20, y + 150, cx + w / 2 + 20, y + 190], radius=12, fill=(160, 100, 60))
    for sx in (-1, 1):
        d.rectangle([cx + sx * (w / 2 - 60) - 16, y + 180, cx + sx * (w / 2 - 60) + 16, y + 420], fill=(40, 40, 46))


# ------------------------------------------------------------------ fx helpers
def speed_lines(frame, T, color=WHITE, n=26, cx=W / 2, cy=H * 0.45, seed=1):
    d = ImageDraw.Draw(frame)
    rnd = random.Random(seed)
    for i in range(n):
        a = rnd.uniform(0, math.tau)
        sp = rnd.uniform(0.8, 1.6)
        r0 = ((T * 900 * sp + rnd.uniform(0, 1400)) % 1400) + 250
        r1 = r0 + rnd.uniform(80, 260)
        d.line([(cx + math.cos(a) * r0, cy + math.sin(a) * r0), (cx + math.cos(a) * r1, cy + math.sin(a) * r1)],
               fill=color + (rnd.randint(70, 170),), width=rnd.randint(3, 7))


def burst_bg(c1=(250, 230, 40), c2=(255, 140, 30), n=40):
    f = Image.new("RGBA", (W, H), c1 + (255,))
    d = ImageDraw.Draw(f)
    for i in range(n):
        a = i / n * math.tau
        d.polygon([(540, 900), (540 + math.cos(a) * 1800, 900 + math.sin(a) * 1800),
                   (540 + math.cos(a + 0.06) * 1800, 900 + math.sin(a + 0.06) * 1800)], fill=c2)
    return f


@lru_cache(maxsize=None)
def burst_cached(kind="yellow"):
    if kind == "red":
        return burst_bg((200, 30, 50), (150, 10, 40))
    if kind == "teal":
        return burst_bg((10, 140, 140), (0, 100, 110))
    if kind == "orange":
        return burst_bg((240, 120, 30), (200, 80, 20))
    return burst_bg()


def pop_text(frame, txt, x, y, lt, t0=0.0, size=110, col=YELLOW, glow=RED, rot=0, stroke=8, dur_in=0.22):
    if lt < t0:
        return
    im = text_img(txt, size, col, F_BLACK, stroke=stroke, glow=glow)
    p = clamp01((lt - t0) / dur_in)
    paste_c(frame, im, x, y, 0.2 + 0.8 * ease_back(p, 2.6), rot=rot)


def stamp(frame, txt, x, y, lt, t0=0.0, size=86, col=RED, rot=-10, sub=None, w=None):
    if lt < t0:
        return
    f = font(F_BLACK, size)
    lines = txt.split("\n")
    tw = int(max(f.getlength(l) for l in lines)) + 80
    th = int(size * 1.15 * len(lines)) + 60 + (int(size * 0.5) if sub else 0)
    im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([6, 6, tw - 6, th - 6], radius=18, outline=col, width=10, fill=(255, 255, 255, 40))
    for i, l in enumerate(lines):
        d.text((tw / 2, 30 + size * 0.55 + i * size * 1.15), l, font=f, fill=col, anchor="mm")
    if sub:
        d.text((tw / 2, th - 30 - size * 0.2), sub, font=font(F_BOLD, int(size * 0.36)), fill=col, anchor="mm")
    p = clamp01((lt - t0) / 0.18)
    sc = 2.2 - 1.2 * ease_out(p)
    paste_c(frame, im, x, y, sc, alpha=0.3 + 0.7 * p, rot=rot)


def label(frame, txt, x, y, col=YELLOW, size=46, fg=(15, 15, 25)):
    f = font(F_BLACK, size)
    tw = f.getlength(txt)
    d = ImageDraw.Draw(frame)
    d.rounded_rectangle([x - tw / 2 - 26, y - size * 0.75, x + tw / 2 + 26, y + size * 0.75], radius=size * 0.6,
                        fill=col)
    d.text((x, y), txt, font=f, fill=fg, anchor="mm")


def arrow(frame, x0, y0, x1, y1, col=YELLOW, w=16):
    d = ImageDraw.Draw(frame)
    d.line([(x0, y0), (x1, y1)], fill=col, width=w)
    a = math.atan2(y1 - y0, x1 - x0)
    L = w * 3
    d.polygon([(x1 + math.cos(a) * L * 0.6, y1 + math.sin(a) * L * 0.6),
               (x1 + math.cos(a + 2.4) * L, y1 + math.sin(a + 2.4) * L),
               (x1 + math.cos(a - 2.4) * L, y1 + math.sin(a - 2.4) * L)], fill=col)


def shake(lt, amt=18, decay=0.35, f=55):
    k = max(0.0, 1 - lt / decay)
    return math.sin(lt * f) * amt * k, math.cos(lt * f * 1.3) * amt * k


def offset(frame, dx, dy):
    """Camera shake: shift inside a slightly zoomed frame so no border shows."""
    if abs(dx) < 0.5 and abs(dy) < 0.5:
        return frame
    z = 1.0 + 2.2 * max(abs(dx) / W, abs(dy) / H) + 0.01
    return zoom_frame(frame, z, W / 2 - dx, H / 2 - dy)


def police_lights(frame, T, strength=1.0):
    ph = (T * 4) % 2
    c = BLUE if ph < 1 else RED
    a = (0.5 + 0.5 * math.sin(T * 25)) * strength
    paste_c(frame, radial(1700, c, 0.5 * a, 1.4), W * (0.2 if ph < 1 else 0.8), H * 0.3)


def notes(frame, x, y, T):
    for k in range(3):
        ph = (T * 0.8 + k / 3) % 1
        paste_c(frame, emoji("🎵", 70), x + k * 40 + math.sin(ph * 6) * 20, y - ph * 200, alpha=1 - ph)


# ------------------------------------------------------------------ COLD OPEN / SCENE 1
def fly_frame(p, T, freeze=False):
    """Cyclist flying over the hood. p 0..1 along the arc."""
    f = street(1500, 1.0)
    car = car_side(820, damage=True, driver=("auto", "shock", 1), brake=True)
    paste_c(f, car, 420, 1440)
    bk = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bike(bk, 860 + p * 120, 1640, 0.5, spin=T * 2, buckle=10, lying=True)
    f.alpha_composite(bk)
    x = lerp(900, 120, p)
    y = 1250 - math.sin(p * math.pi) * 520
    L = person_layer("radler", 0.62, (700, 900), expr="shock", mouth=0.9, arm_l=150, arm_r=150, legs=True)
    paste_c(f, L, x, y, 1.0, rot=p * 260)
    # phone flying separately
    paste_c(f, phone_broken(), lerp(820, 460, p), 1150 - math.sin(p * math.pi) * 760, 0.22, rot=p * 720)
    # glass shards
    rnd = random.Random(2)
    d = ImageDraw.Draw(f)
    for k in range(18):
        sx = lerp(740, rnd.uniform(200, 1000), p)
        sy = 1300 - math.sin(p * math.pi) * rnd.uniform(100, 600)
        d.polygon([(sx, sy), (sx + 14, sy + 6), (sx + 4, sy + 18)], fill=(220, 240, 255))
    return f


def shot_cold(lt, dur, T):
    f = fly_frame(0.5, 0.0)
    arr = np.asarray(f.convert("RGB")).astype(np.float32)
    g = arr.mean(axis=2, keepdims=True)
    arr = (arr * 0.35 + g * 0.65) * 0.72
    f = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")
    f = zoom_frame(f, 1.1 + lt * 0.05, 540, 900)
    t = text_img("WER ZAHLT", 128, WHITE, F_BLACK, stroke=10, glow=RED, max_w=1400)
    t2 = text_img("DAS ALLES?", 128, YELLOW, F_BLACK, stroke=10, glow=RED, max_w=1400)
    p = ease_back(clamp01(lt / 0.25), 2.4)
    paste_c(f, t, 540, 330, 0.3 + 0.7 * p, rot=-4)
    p2 = ease_back(clamp01((lt - 0.18) / 0.25), 2.4)
    paste_c(f, t2, 540, 500, 0.3 + 0.7 * p2, rot=-4)
    q = ease_out(clamp01((lt - 0.35) / 0.2))
    paste_c(f, emoji("🚲", 130), 330, 690, q)
    paste_c(f, text_img("VS", 90, WHITE, F_BLACK, stroke=8, glow=RED), 540, 690, q)
    paste_c(f, emoji("🚗", 130), 750, 690, q)
    if lt > dur - 0.3:
        f = glitch(f, T, 1.5)
        label(f, "ZURÜCKSPULEN", 540, 1150, WHITE, 56)
    return f


def car_driving(f, x, y, T, driver_expr="smug", inj=0, brake=False, damage=False, bounce=True):
    car = car_side(820, damage=damage, driver=("auto", driver_expr, inj), brake=brake)
    paste_c(f, car, x, y + (math.sin(T * 18) * 3 if bounce else 0))


def shot_drive(lt, dur, T):
    cam = 300 + lt * 420
    f = street(cam)
    car_driving(f, 430, 1440, T)
    notes(f, 520, 1230, T)
    # speed streaks on road
    d = ImageDraw.Draw(f)
    for k in range(6):
        y = 1560 + k * 50
        x = (900 - (lt * 2200 + k * 330) % 1400)
        d.line([(x, y), (x + 160, y)], fill=(255, 255, 255, 90), width=4)
    f = zoom_frame(f, 1.0 + lt * 0.04, 540, 1300)
    label(f, "MONTAG · 7:58 UHR", 540, 300, WHITE, 48)
    pop_text(f, "Nur kurz Brötchen holen …", 540, 430, lt, 0.4, 58, WHITE, ORANGE, stroke=6)
    if lt > 0.4:
        paste_c(f, emoji("🥐", 90), 540, 540, ease_back(clamp01((lt - 0.5) / 0.2)))
    return f


def shot_cyclist(lt, dur, T):
    cam = 1600 - lt * 300
    f = street(cam, 1.15, 1350)
    x = 640 - lt * 160
    person(f, "radler", x - 30, 1225, 0.62, expr="smug", arm_l=-40, arm_r=40, legs=True, leg_phase=T * 9,
           blink=blink(T, 2))
    d = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bike(d, x, 1650, 0.72, spin=-T * 9, crank=-T * 9)
    f.alpha_composite(d)
    label(f, "RADFAHRER · 35 · HAT VORFAHRT. GLAUBT ER.", 540, 300, TEAL, 36)
    paste_c(f, emoji("🎧", 80), x - 140, 900)
    return f


def shot_impact(lt, dur, T):
    p = ease_in(clamp01(lt / 0.25))
    f = street(1500)
    car_driving(f, lerp(150, 420, p), 1440, T, "shock", 0, brake=lt > 0.1, bounce=False)
    bx = lerp(1060, 830, p)
    d = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bike(d, bx, 1650, 0.55, spin=T * 9, crank=T * 9)
    f.alpha_composite(d)
    person(f, "radler", bx + 20, 1230, 0.5, expr="shock", mouth=0.8, arm_l=-40, arm_r=40, legs=True)
    if lt > 0.25:
        flash = Image.new("RGBA", (W, H), (255, 255, 255, int(200 * max(0, 1 - (lt - 0.25) / 0.15))))
        f.alpha_composite(flash)
        pop_text(f, "KRACH!", 640, 1000, lt, 0.25, 190, YELLOW, RED, rot=-8, stroke=12)
        dx, dy = shake(lt - 0.25, 30)
        f = offset(f, dx, dy)
    return f


@lru_cache(maxsize=None)
def cockpit_bg():
    f = gradient(W, H, (150, 200, 240), (255, 225, 195))
    s = street_pano().crop((1400, 600, 1400 + W, 600 + 1100)).resize((W, 1100))
    f.alpha_composite(s, (0, 200))
    d = ImageDraw.Draw(f)
    d.polygon([(0, 0), (W, 0), (W, 180), (0, 260)], fill=(30, 32, 40))
    d.rectangle([0, 0, 70, H], fill=(40, 42, 52))
    d.rectangle([W - 70, 0, W, H], fill=(40, 42, 52))
    d.rectangle([0, 1300, W, H], fill=(28, 28, 34))
    return f


def shot_horn(lt, dur, T):
    """Driver slams his forehead onto the steering wheel -> HUUUP."""
    f = cockpit_bg().copy()
    hit = clamp01((lt - 0.12) / 0.12)
    back = clamp01((lt - 0.38) / 0.25)
    dip = ease_in(hit) * (1 - ease_out(back) * 0.7)
    inj = 1 if lt > 0.24 else 0
    expr = "shock" if lt < 0.24 else "pain"
    person(f, "auto", 540, 980 + dip * 330, 1.25, expr=expr, inj=inj, arm_l=40, arm_r=-40, tilt=dip * 8)
    # steering wheel in the foreground
    wheel = Image.new("RGBA", (900, 900), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wheel)
    wd.ellipse([30, 30, 870, 870], outline=(30, 30, 38), width=80)
    wd.rectangle([80, 420, 820, 500], fill=(30, 30, 38))
    wd.ellipse([330, 330, 570, 570], fill=(40, 40, 50), outline=(120, 120, 140), width=6)
    paste_c(f, wheel.resize((900, 520)), 540, 1560)
    if lt > 0.24:
        paste_c(f, glow_dot(600, (255, 240, 120)), 540, 1450)
        pop_text(f, "HUUUUP!", 540, 520, lt, 0.24, 140, YELLOW, ORANGE, rot=6, stroke=12)
        for k in range(5):
            a = T * 4 + k * math.tau / 5
            star(f, 540 + math.cos(a) * 200, 760 + dip * 330 + math.sin(a) * 50, 34, YELLOW)
        dx, dy = shake(lt - 0.24, 26)
        f = offset(f, dx, dy)
    return f


def shot_fly(lt, dur, T):
    p = clamp01(lt / dur)
    f = fly_frame(0.08 + 0.84 * p, T)
    # slow motion styling
    f = zoom_frame(f, 1.05 + 0.08 * p, 540, 1100)
    d = ImageDraw.Draw(f)
    d.rectangle([0, 0, W, 110], fill=(0, 0, 0))
    d.rectangle([0, H - 110, W, H], fill=(0, 0, 0))
    if (T * 2) % 1 < 0.6:
        d.ellipse([250, 248, 290, 288], fill=RED)
    label(f, "ZEITLUPE 0,25×", 570, 268, WHITE, 44, (20, 20, 30))
    return f


def shot_land(lt, dur, T, t_stamp):
    f = street(1300, 1.2, 1500)
    d = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bike(d, 760, 1720, 0.5, spin=T * 3, buckle=14, lying=True)
    f.alpha_composite(d)
    L = person_layer("radler", 0.7, (800, 1000), expr="pain", arm_l=120, arm_r=130, legs=True)
    drop = ease_out(clamp01(lt / 0.2))
    paste_c(f, L, 380, lerp(1000, 1450, drop), rot=85)
    if lt > 0.2:
        pop_text(f, "PLATSCH.", 420, 1180, lt, 0.2, 90, WHITE, BLUE, rot=-6)
        dx, dy = shake(lt - 0.2, 14)
        f = offset(f, dx, dy)
    stamp(f, "AKTENZEICHEN\n4711/26", 540, 520, lt, t_stamp, 92, RED, rot=-8, sub="JURISTISCHES GROSSPROJEKT")
    return f


# ------------------------------------------------------------------ SCENE 2 damages
def shot_phone(lt, dur, T):
    f = asphalt().copy()
    paste_c(f, radial(1100, (120, 200, 255), 0.3), 540, 900)
    ph = phone_broken()
    paste_c(f, ph, 540, 900, 1.25 + lt * 0.08, rot=-14)
    if (T * 7) % 1 < 0.3:
        f = glitch(f, T, 0.6, 3)
    label(f, "EXPONAT 1: HANDY", 540, 260, YELLOW, 50)
    pop_text(f, "Modell „Spinnennetz“", 540, 1420, lt, 0.1, 60, WHITE, BLUE, stroke=6)
    return f


def shot_wheel(lt, dur, T, big=True):
    f = asphalt().copy()
    paste_c(f, radial(1300, (255, 120, 80), 0.25), 540, 920)
    wheel_closeup(f, 540, 930, 430, T, 1.0)
    # "8" ghost outline to point at the Achter
    if lt > 0.25:
        e = text_img("8", 420, (255, 255, 255, 0), F_BLACK, stroke=8, stroke_fill=YELLOW)
        paste_c(f, e, 860, 560, 0.5 + 0.1 * math.sin(T * 8), alpha=0.9, rot=12)
    label(f, "EXPONAT 2: FAHRRAD MIT ACHTER", 540, 260, YELLOW, 44)
    wob = math.sin(T * 10)
    pop_text(f, "EIERT!", 540 + wob * 40, 1430, lt, 0.15, 110, WHITE, RED, rot=wob * 10)
    return f


def shot_shoulder(lt, dur, T, expr="pain"):
    f = street(1700, 1.35, 1100)
    f = f.filter(ImageFilter.GaussianBlur(10))
    person(f, "radler", 560, 860, 1.5, expr=expr, hurt=1.0, T=T, mouth=M("radler", T) * 0.6)
    label(f, "EXPONAT 3: RECHTE SCHULTER", 540, 260, YELLOW, 44)
    if lt > 0.15:
        arrow(f, 160, 560, 280, 770, RED)
        pop_text(f, "AUA", 170, 480, lt, 0.15, 100, WHITE, RED, rot=-10)
    return f


def shot_total(lt, dur, T):
    f = burst_cached("red").copy()
    person(f, "radler", 540, 1000, 1.3, expr="pain", hurt=1.0, T=T, mouth=M("radler", T))
    # crashing chart
    d = ImageDraw.Draw(f)
    pts = []
    for k in range(12):
        x = 120 + k * 76
        y = 330 + k * 8 + (0 if k < 7 else (k - 6) ** 2 * 26) + math.sin(k * 2.1) * 30
        pts.append((x, y))
    n = max(2, int(len(pts) * clamp01(lt / 0.6)))
    d.line(pts[:n], fill=WHITE, width=14, joint="curve")
    label(f, "LEBEN AG  ▼ −99,9 %", 540, 230, WHITE, 46, RED)
    stamp(f, "TOTALSCHADEN", 540, 1440, lt, 0.35, 110, WHITE, rot=-8)
    return f


def shot_dent(lt, dur, T):
    f = street(1500, 1.0)
    car = car_side(820, damage=True)
    big = car.resize((int(car.width * 2.1), int(car.height * 2.1)), Image.BICUBIC)
    paste_c(f, big, 420 - lt * 30, 1200)
    # sparkle on scratches
    for k in range(4):
        ph = (T * 2 + k * 0.25) % 1
        star(f, 780 + k * 60, 1080 + (k % 2) * 60, 30 * math.sin(ph * math.pi), WHITE)
    label(f, "EXPONAT 4: DELLE + KRATZER", 540, 260, YELLOW, 44)
    if lt > 0.1:
        arrow(f, 980, 700, 900, 1000, RED)
    return f


def shot_driver_close(lt, dur, T, expr="angry", inj=1, tag=True):
    f = cockpit_bg().copy()
    person(f, "auto", 540, 1030, 1.4, expr=expr, inj=inj, mouth=M("auto", T), arm_l=150, arm_r=150,
           blink=blink(T, 1))
    wheel = Image.new("RGBA", (900, 900), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wheel)
    wd.ellipse([30, 30, 870, 870], outline=(30, 30, 38), width=80)
    paste_c(f, wheel.resize((900, 520)), 540, 1700)
    if tag:
        label(f, "EXPONAT 5: STIRN, NEUES DESIGN", 540, 260, YELLOW, 42)
        if lt > 0.1:
            arrow(f, 840, 420, 560, 560, RED)
    return f


def shot_broetchen(lt, dur, T):
    f = burst_cached("orange").copy()
    person(f, "auto", 540, 1140, 1.2, expr="pain", inj=1, mouth=M("auto", T), arm_l=60, arm_r=60)
    # thought bubble with Brötchen
    p = ease_back(clamp01(lt / 0.25))
    d = ImageDraw.Draw(f)
    for k, (x, y, r) in enumerate(((700, 640, 26), (760, 560, 40))):
        d.ellipse([x - r * p, y - r * p, x + r * p, y + r * p], fill=WHITE)
    bub = Image.new("RGBA", (620, 380), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bub)
    bd.ellipse([0, 0, 620, 380], fill=WHITE)
    bub.alpha_composite(emoji("🥐", 150), (110, 90))
    bub.alpha_composite(emoji("🥖", 150), (330, 100))
    paste_c(f, bub, 700, 380, p)
    label(f, "BRÖTCHEN: 0,45 €", 540, 1420, WHITE, 46, (20, 20, 30))
    return f


# ------------------------------------------------------------------ museum
EXHIBITS = [("📱", "HANDY", "Modell Spinnennetz"), ("🚲", "FAHRRAD", "Modell Brezel (Achter)"),
            ("💪", "SCHULTER", "Modell Aua"), ("🤕", "STIRN", "Modell Einhorn")]


@lru_cache(maxsize=None)
def museum_bg():
    f = gradient(W, H, (60, 28, 30), (24, 10, 14))
    d = ImageDraw.Draw(f)
    for x in range(0, W, 120):
        d.line([(x, 0), (x, 1400)], fill=(75, 36, 40), width=4)
    d.rectangle([0, 1400, W, H], fill=(70, 46, 30))
    for x in range(0, W, 160):
        d.line([(x, 1400), (x - 200, H)], fill=(55, 35, 22), width=4)
    for x in (270, 810):
        for y in (330, 900):
            paste_c(f, radial(560, (255, 230, 160), 0.45), x, y + 60)
    return f


def exhibit_frame(icon, title, sub, wheel_T=None):
    im = Image.new("RGBA", (440, 520), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 440, 400], fill=(200, 160, 50))
    d.rectangle([22, 22, 418, 378], fill=(240, 236, 225))
    if icon == "📱":
        ph = phone_broken().resize((120, 238))
        im.alpha_composite(ph, (160, 82))
    elif icon == "🚲" and wheel_T is not None:
        tmp = Image.new("RGBA", (440, 400), (0, 0, 0, 0))
        wheel_closeup(tmp, 220, 210, 120, wheel_T, 1.0)
        im.alpha_composite(tmp)
    else:
        e = emoji(icon, 210)
        im.alpha_composite(e, (int(220 - e.width / 2), int(200 - e.height / 2)))
    d.rounded_rectangle([40, 410, 400, 510], radius=10, fill=(30, 26, 22), outline=(200, 160, 50), width=4)
    d.text((220, 440), title, font=font(F_BLACK, 34), fill=(255, 230, 150), anchor="mm")
    d.text((220, 482), sub, font=font(F_INTER_B, 24), fill=(230, 220, 200), anchor="mm")
    return im


def shot_museum(lt, dur, T, times, t_welcome):
    f = museum_bg().copy()
    pos = [(270, 640), (810, 640), (270, 1190), (810, 1190)]
    for k, ((icon, title, sub), (x, y)) in enumerate(zip(EXHIBITS, pos)):
        if T >= times[k]:
            p = ease_back(clamp01((T - times[k]) / 0.25), 2.0)
            fr = exhibit_frame(icon, title, sub, T if icon == "🚲" else None)
            paste_c(f, fr, x, y, 0.3 + 0.62 * p, rot=(k % 2 - 0.5) * 4)
    # velvet rope
    d = ImageDraw.Draw(f)
    for x in (80, 540, 1000):
        d.rectangle([x - 10, 1500, x + 10, 1720], fill=(200, 160, 50))
        d.ellipse([x - 22, 1480, x + 22, 1524], fill=(230, 190, 70))
    d.arc([80, 1400, 540, 1640], 20, 160, fill=(170, 20, 40), width=18)
    d.arc([540, 1400, 1000, 1640], 20, 160, fill=(170, 20, 40), width=18)
    if T >= t_welcome:
        p = clamp01((T - t_welcome) / 0.3)
        sign = text_img("SCHADENSMUSEUM", 76, (255, 230, 150), F_BLACK, stroke=6, stroke_fill=(80, 50, 10),
                        glow=(255, 180, 60), max_w=1400)
        paste_c(f, sign, 540, 265, 0.4 + 0.6 * ease_back(p))
        label(f, "EINTRITT: IHRE HAFTPFLICHT", 540, 365, (255, 230, 150), 34)
    else:
        label(f, "ALLTAG KLAR PRÄSENTIERT", 540, 270, (255, 230, 150), 40)
    return zoom_frame(f, 1.0 + 0.04 * math.sin(lt * 0.8))


# ------------------------------------------------------------------ SCENE 3 argument
def two_shot(lt, T, ex_r="angry", ex_a="angry", point_r=0, point_a=0, cam=1250, zoom=1.12, hurt=True,
             polish=False, r_who_talk=True):
    f = street(cam, zoom, 1350)
    mr, ma = M("radler", T), M("auto", T)
    person(f, "auto", 300, 900, 0.95, expr=ex_a if ma < 0.05 or ex_a != "angry" else "angry", inj=1,
           mouth=ma, legs=True, point=point_a, blink=blink(T, 1),
           arm_l=(150 if polish else 15), arm_r=-15)
    person(f, "radler", 790, 920, 0.9, expr=ex_r, mouth=mr, legs=True, point=-1 if point_r else 0,
           hurt=0 if point_r else (1.0 if hurt else 0), T=T, blink=blink(T, 2))
    if polish:
        # polishing the forehead bump with a cloth
        cx, cy = 268 + math.sin(T * 22) * 22, 700
        d = ImageDraw.Draw(f)
        d.rounded_rectangle([cx - 55, cy - 26, cx + 55, cy + 26], radius=12, fill=(255, 230, 80),
                            outline=(200, 160, 30), width=4)
        for k in range(3):
            star(f, cx + 120 * math.cos(T * 5 + k * 2), cy - 60 + 50 * math.sin(T * 5 + k * 2), 22, WHITE)
    return f


def shot_argue(kind, t_marks=None):
    def fn(lt, dur, T):
        if kind == "r2":
            f = two_shot(lt, T, point_r=1)
            for k, (txt, t0) in enumerate(t_marks or []):
                if T >= t0:
                    e, word = txt.split(" ", 1)
                    q = ease_back(clamp01((T - t0) / 0.2))
                    paste_c(f, emoji(e, 70), 580, 340 + k * 100, q)
                    paste_c(f, text_img(word, 60, WHITE, F_BLACK, stroke=6, glow=TEAL), 820, 340 + k * 100, q)
            label(f, "RECHNUNG FÜR:", 790, 240, TEAL, 40)
            return zoom_frame(f, 1.0 + lt * 0.05, 700, 900)
        if kind == "a2a":
            f = two_shot(lt, T, point_a=1, ex_r="angry")
            pop_text(f, "UND MEINE REPARATUR?!", 540, 300, lt, 0.1, 64, WHITE, ORANGE)
            return zoom_frame(f, 1.0 + lt * 0.05, 400, 900)
        if kind == "a2b":
            f = two_shot(lt, T, polish=True, ex_r="shock")
            f = zoom_frame(f, 1.25, 330, 900)
            pop_text(f, "HAFTPFLICHT-POLITUR", 540, 330, lt, 0.15, 54, YELLOW, ORANGE)
            return f
        return two_shot(lt, T)
    return fn


def shot_punch_close(who, txt):
    def fn(lt, dur, T):
        f = burst_cached("teal" if who == "radler" else "orange").copy()
        if who == "radler":
            person(f, "radler", 540, 960, 1.55, expr="angry", mouth=M("radler", T), point=-1)
        else:
            person(f, "auto", 540, 960, 1.55, expr="angry", inj=1, mouth=M("auto", T), point=1)
        speed_lines(f, T, WHITE, 30, 540, 900)
        pop_text(f, txt, 540, 360, lt, 0.0, 120, WHITE, RED, rot=-5 if who == "radler" else 5, stroke=10)
        return zoom_frame(f, 1.0 + 0.12 * ease_out(clamp01(lt / 0.4)))
    return fn


def shot_brawl(lt, dur, T, t_stamp=None):
    f = street(1250, 1.12, 1350)
    rnd = random.Random(int(T * 12))
    cx, cy = 540, 1050
    # dust cloud
    for k in range(16):
        a = k / 16 * math.tau + T * 2
        r = 220 + 40 * math.sin(T * 9 + k)
        paste_c(f, sphere(int(260 + 50 * math.sin(T * 7 + k * 1.7)), (215, 205, 190), (255, 255, 255), 0.05),
                cx + math.cos(a) * r, cy + math.sin(a) * r * 0.7)
    paste_c(f, sphere(520, (225, 215, 200), (255, 255, 255), 0.05), cx, cy)
    # heads/limbs popping out
    k = int(T * 6) % 4
    if k == 0:
        paste_c(f, head("auto", "angry", 1), cx - 230, cy - 230, 0.55, rot=20)
    elif k == 1:
        paste_c(f, head("radler", "angry", 0), cx + 240, cy - 220, 0.55, rot=-20)
    elif k == 2:
        paste_c(f, head("radler", "pain", 0), cx - 260, cy + 120, 0.5, rot=60)
    else:
        paste_c(f, head("auto", "pain", 1), cx + 250, cy + 140, 0.5, rot=-50)
    d = ImageDraw.Draw(f)
    for j in range(3):
        a = rnd.uniform(0, math.tau)
        x, y = cx + math.cos(a) * 330, cy + math.sin(a) * 260
        d.line([(cx + math.cos(a) * 200, cy + math.sin(a) * 160), (x, y)], fill=rnd.choice([(214, 92, 30),
                                                                                         (16, 160, 150)]), width=60)
        d.ellipse([x - 42, y - 42, x + 42, y + 42], fill=(236, 184, 150))
    for j in range(4):
        star(f, cx + rnd.uniform(-380, 380), cy + rnd.uniform(-330, 300), 40, YELLOW)
    words = ["ZACK!", "PAFF!", "§!?", "BOING!", "AUA!", "KLATSCH!"]
    w = words[int(T * 4) % len(words)]
    paste_c(f, text_img(w, 130, YELLOW, F_BLACK, stroke=10, glow=RED), 540 + rnd.uniform(-160, 160),
            560 + rnd.uniform(-40, 40), 1.0, rot=rnd.uniform(-15, 15))
    label(f, "SLAPSTICK – BITTE NICHT NACHMACHEN", 540, 250, WHITE, 36, RED)
    if t_stamp is not None and T >= t_stamp:
        stamp(f, "STRAFVERFAHREN?!", 540, 1480, T - t_stamp, 0.0, 84, RED, rot=-7)
    dx, dy = math.sin(T * 40) * 10, math.cos(T * 33) * 8
    return offset(f, dx, dy)


def shot_cost(lt, dur, T, t_stamp):
    f = shot_brawl(lt, dur, T, t_stamp)
    # cost-o-meter
    val = 0.25 + 0.75 * ease_io(clamp01(lt / dur))
    d = ImageDraw.Draw(f)
    d.rounded_rectangle([140, 360, 940, 460], radius=40, fill=(20, 20, 30), outline=WHITE, width=6)
    d.rounded_rectangle([152, 372, 152 + 776 * val, 448], radius=32, fill=mixc(GREEN, RED, val))
    d.text((540, 410), "KOSTEN-O-METER", font=font(F_BLACK, 40), fill=WHITE, anchor="mm", stroke_width=4,
           stroke_fill=(0, 0, 0))
    return f


# ------------------------------------------------------------------ SCENE 4 police
def shot_police_arrive(lt, dur, T):
    f = street(1250, 1.0)
    p = ease_out(clamp01(lt / dur))
    paste_c(f, car_side(820, police=True), lerp(-500, 380, p), 1440)
    # light bar
    x = lerp(-500, 380, p)
    c = BLUE if (T * 6) % 2 < 1 else RED
    paste_c(f, glow_dot(300, c), x, 1440 - 190)
    police_lights(f, T, 0.8)
    pop_text(f, "TATÜÜÜ TATAAA", 540, 400, lt, 0.1, 90, WHITE, BLUE)
    return f


def shot_cop(lt, dur, T, look=True, expr="tired", twitch=False):
    f = street(1250, 1.5, 1100).filter(ImageFilter.GaussianBlur(8))
    police_lights(f, T, 0.7)
    person(f, "cop2", 540, 900, 1.6, expr=expr, mouth=M("polizei", T), blink=blink(T, 4) and not twitch,
           arm_l=10, arm_r=-10)
    if look:
        # eyes scanning the chaos: small thumbnails pop in
        items = [("📱", 0.0), ("🚲", 0.35), ("🚗", 0.7), ("🤕", 1.0)]
        for k, (e, t0) in enumerate(items):
            if lt > t0:
                paste_c(f, emoji(e, 110), 140 + k * 266, 300, ease_back(clamp01((lt - t0) / 0.2)))
    if twitch:
        # eye twitch: right eye squeezes rhythmically
        if (T * 5) % 1 < 0.4:
            d = ImageDraw.Draw(f)
            D = 260 * 1.6
            x = 540 + D * 0.18
            y = 900 - 110 * 1.6
            d.rectangle([x - D * 0.09, y - D * 0.12, x + D * 0.09, y + D * 0.08], fill=(228, 178, 146))
            d.line([(x - D * 0.07, y - D * 0.01), (x + D * 0.07, y - D * 0.03)], fill=(60, 40, 40), width=8)
    label(f, "POLIZEIOBERMEISTER · 23 DIENSTJAHRE", 540, 1300, (110, 170, 255), 34, (10, 14, 40))
    return f


def shot_shout(lt, dur, T):
    f = street(1250, 1.2, 1350)
    police_lights(f, T, 0.5)
    ma, mr = M("auto", T), M("radler", T)
    person(f, "auto", 300, 880, 1.0, expr="angry", inj=1, mouth=ma, legs=True, point=1 if ma > 0.05 else 0)
    person(f, "radler", 790, 900, 0.95, expr="angry", mouth=mr, legs=True, point=-1 if mr > 0.05 else 0)
    return f


def shot_both_point(lt, dur, T):
    f = burst_cached().copy()
    person(f, "auto", 300, 1000, 1.05, expr="angry", inj=1, mouth=0.0, point=1)
    person(f, "radler", 790, 1010, 1.0, expr="angry", mouth=0.0, point=-1)
    s = extrude_text("ER!", 200, RED, (110, 0, 20), depth=18)
    paste_c(f, s, 300, 440, ease_back(clamp01(lt / 0.2), 3), rot=-8)
    paste_c(f, s, 790, 440, ease_back(clamp01((lt - 0.05) / 0.2), 3), rot=8)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    out.alpha_composite(f)
    ImageDraw.Draw(out).rectangle([0, 0, W - 1, H - 1], outline=(0, 0, 0), width=40)
    return zoom_frame(out, 1.0 + 0.06 * ease_out(lt / 0.3))


def shot_vacation(lt, dur, T, t_urlaub):
    f = shot_cop(lt, dur, T, look=False, twitch=True)
    if T >= t_urlaub:
        p = ease_back(clamp01((T - t_urlaub) / 0.3))
        bub = Image.new("RGBA", (700, 460), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bub)
        bd.ellipse([0, 0, 700, 460], fill=WHITE)
        bd.rectangle([120, 280, 580, 380], fill=(70, 170, 230))
        bd.ellipse([140, 230, 560, 330], fill=(250, 220, 150))
        bub.alpha_composite(emoji("🌴", 170), (380, 90))
        bub.alpha_composite(emoji("🍹", 110), (180, 160))
        paste_c(f, bub, 680, 340, p)
        stamp(f, "URLAUBSANTRAG\nGENEHMIGT", 540, 1560, T - t_urlaub, 0.35, 70, GREEN, rot=-8)
    return f


# ------------------------------------------------------------------ SCENE 5 law cards
@lru_cache(maxsize=None)
def law_bg():
    f = gradient(W, H, (10, 12, 34), (34, 12, 50))
    d = ImageDraw.Draw(f)
    for k in range(9):
        x = 60 + k * 120
        d.rectangle([x, 1400, x + 50, H], fill=(28, 22, 54))
    paste_c(f, radial(1500, (90, 60, 200), 0.35), 540, 800)
    s = text_img("§", 900, (40, 30, 80), F_BLACK)
    paste_c(f, s, 540, 1150)
    return f


def card(title, accent, body_lines, icon=None, w=960, sub=None):
    f = font(F_INTER, 50)
    fb = font(F_INTER_B, 44)
    lines = []
    for ln in body_lines:
        words, cur = ln.split(), ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if cur and fb.getlength(t) > w - 120:
                lines.append(cur)
                cur = wd
            else:
                cur = t
        lines.append(cur)
    h = 200 + 60 * len(lines) + (80 if sub else 0)
    im = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0))
    g = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).rounded_rectangle([30, 30, w + 30, h + 30], radius=40, fill=accent + (200,))
    im.alpha_composite(g.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([30, 30, w + 30, h + 30], radius=40, fill=(16, 14, 30), outline=accent, width=8)
    tt = text_img(title, 60, accent, F_BLACK, max_w=1400)
    sc = min(1.0, (w - 240) / tt.width)
    paste_c(im, tt, 30 + w / 2 + (40 if icon else 0), 120, sc)
    if icon:
        paste_c(im, emoji(icon, 80), 110, 118)
    y = 210
    for ln in lines:
        d.text((30 + w / 2, y + 30), ln, font=fb, fill=WHITE, anchor="mm")
        y += 60
    if sub:
        d.text((30 + w / 2, y + 40), sub, font=font(F_INTER, 36), fill=mixc(accent, WHITE, 0.4), anchor="mm")
    return im


@lru_cache(maxsize=None)
def card_cached(key):
    if key == "s7":
        return card("§ 7 StVG", YELLOW, ["Der Halter des Autos kann", "für Schäden beim Betrieb", "des Fahrzeugs haften."],
                    "🚗", sub="Halterhaftung – auch ohne Verschulden möglich")
    if key == "achtung":
        return card("ABER ACHTUNG", RED, ["Wer wie viel zahlt, hängt", "von den genauen Umständen ab."], "⚠️",
                    sub="Keine Pauschal-Schuld ohne Unfalldetails!")
    if key == "mitv":
        return card("MITVERSCHULDEN?", ORANGE, ["Auch der Radfahrer kann", "mitverantwortlich sein."], "🚲",
                    sub="z. B. Vorfahrt, Licht, Tempo, Handy …")
    if key == "ersatz":
        return card("SCHADENSERSATZ", GREEN, ["Kaputtes Handy  →  kann ersetzt werden", "Fahrrad mit Achter  →  auch"],
                    "💶", sub="Grundlage: wer haftet – und zu welchem Anteil")
    if key == "schmerz":
        return card("SCHMERZENSGELD", TEAL, ["Für Verletzungen möglich –", "unter Umständen für BEIDE!"], "🤕",
                    sub="Schulter (Radfahrer)  +  Stirn (Autofahrer)")
    if key == "s223":
        return card("§ 223 StGB", MAGENTA, ["Wer bei der Rangelei vorsätzlich", "jemanden verletzt, kann sich",
                                            "wegen Körperverletzung", "strafbar machen."], "⚖️",
                    sub="Freiheitsstrafe bis 5 Jahre oder Geldstrafe")
    return None


DAMAGE_ICONS = [("🚗", "Delle"), ("📱", "Display"), ("🚲", "Achter"), ("💪", "Schulter"), ("🤕", "Stirn")]


def damage_row(f, T, t0, y=1380):
    for k, (e, name) in enumerate(DAMAGE_ICONS):
        tt = t0 + k * 0.18
        if T < tt:
            continue
        p = ease_back(clamp01((T - tt) / 0.25))
        x = 130 + k * 205
        d = ImageDraw.Draw(f)
        r = 86 * p
        d.ellipse([x - r, y - r, x + r, y + r], fill=(30, 26, 60), outline=YELLOW, width=5)
        paste_c(f, emoji(e, 96), x, y - 10, p)
        if p > 0.9:
            d.text((x, y + 112), name, font=font(F_INTER_B, 30), fill=WHITE, anchor="mm")


def shot_gavel(lt, dur, T):
    f = law_bg().copy()
    hit = clamp01((lt - 0.25) / 0.12)
    ang = lerp(-50, 10, ease_in(hit))
    gav = Image.new("RGBA", (700, 700), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gav)
    gd.rectangle([330, 300, 370, 680], fill=(140, 80, 40))
    gav.alpha_composite(capsule(360, 160, (150, 90, 45), YELLOW, radius=60), (170, 200))
    paste_c(f, gav.rotate(ang, resample=Image.BICUBIC, center=(350, 680)), 600, 820)
    gd2 = ImageDraw.Draw(f)
    gd2.ellipse([300, 1080, 780, 1170], fill=(110, 60, 30))
    if lt > 0.37:
        paste_c(f, glow_dot(700, YELLOW), 540, 1100)
        dx, dy = shake(lt - 0.37, 16)
        f = offset(f, dx, dy)
    logo = text_img("ALLTAG KLAR", 104, YELLOW, F_BLACK, stroke=8, glow=YELLOW, max_w=1400)
    paste_c(f, logo, 540, 330, ease_back(clamp01(lt / 0.3)))
    sub = text_img("Wenn Alltag vor Gericht landet!", 52, WHITE, F_INTER, stroke=4)
    paste_c(f, sub, 540, 470, ease_out(clamp01((lt - 0.3) / 0.3)))
    return f


def shot_law(keys, t_keys, extra=None):
    """keys: card keys shown in sequence at global times t_keys (stacked: newest on top)."""
    def fn(lt, dur, T):
        f = law_bg().copy()
        shown = [(k, t) for k, t in zip(keys, t_keys) if T >= t]
        if not shown:
            shown = [(keys[0], t_keys[0])]
        k, t0 = shown[-1]
        prev = shown[-2] if len(shown) > 1 else None
        if prev is not None:
            pc = card_cached(prev[0])
            paste_c(f, pc, 540, 560, 0.8, alpha=0.35, rot=-3)
        c = card_cached(k)
        p = ease_back(clamp01((T - t0) / 0.3), 1.8)
        paste_c(f, c, 540, 760 + (1 - p) * 300, 0.55 + 0.45 * p, alpha=clamp01((T - t0) / 0.15) * 0.0 + 1)
        if extra:
            extra(f, lt, T, k, T - t0)
        return f
    return fn


def law_extra_s7(f, lt, T, key, kt):
    damage_row(f, T, T - kt + 0.6)


def law_extra_mitv(f, lt, T, key, kt):
    if key == "mitv":
        # tug-of-war slider between car and bike
        d = ImageDraw.Draw(f)
        y = 1350
        d.rounded_rectangle([160, y - 20, 920, y + 20], radius=20, fill=(40, 36, 70))
        v = 0.5 + 0.35 * math.sin(T * 3.2)
        x = 160 + 760 * v
        d.ellipse([x - 44, y - 44, x + 44, y + 44], fill=YELLOW)
        d.text((x, y), "?%", font=font(F_BLACK, 30), fill=(20, 20, 30), anchor="mm")
        paste_c(f, emoji("🚗", 110), 110, y)
        paste_c(f, emoji("🚲", 110), 970, y)
    else:
        # scale (Waage) wobbling
        d = ImageDraw.Draw(f)
        a = math.sin(T * 2.5) * 0.25
        cx, cy = 540, 1300
        d.rectangle([cx - 10, cy, cx + 10, cy + 200], fill=(200, 170, 80))
        x1, y1 = cx - 300 * math.cos(a), cy - 300 * math.sin(a)
        x2, y2 = cx + 300 * math.cos(a), cy + 300 * math.sin(a)
        d.line([(x1, y1), (x2, y2)], fill=(220, 190, 90), width=14)
        for (x, y, e) in ((x1, y1, "🚗"), (x2, y2, "🚲")):
            d.line([(x, y), (x, y + 80)], fill=(220, 190, 90), width=5)
            d.chord([x - 90, y + 40, x + 90, y + 140], 0, 180, fill=(220, 190, 90))
            paste_c(f, emoji(e, 100), x, y + 40)


def law_extra_ersatz(f, lt, T, key, kt):
    if key == "ersatz":
        paste_c(f, phone_broken(), 300, 1390, 0.3, rot=-10)
        wheel_closeup(f, 780, 1390, 130, T, 1.0)
    else:
        # both injured guys side by side
        person(f, "radler", 330, 1330, 0.7, expr="pain", hurt=1, T=T)
        person(f, "auto", 760, 1330, 0.7, expr="pain", inj=2)


def law_extra_223(f, lt, T, key, kt):
    # mini brawl replay
    rnd = random.Random(int(T * 10))
    for k in range(8):
        a = k / 8 * math.tau + T * 3
        paste_c(f, sphere(150, (215, 205, 190), (255, 255, 255), 0.05), 540 + math.cos(a) * 110,
                1400 + math.sin(a) * 60)
    w = ["ZACK!", "§!?", "PAFF!"][int(T * 3) % 3]
    paste_c(f, text_img(w, 70, YELLOW, F_BLACK, stroke=6, glow=RED), 540 + rnd.uniform(-40, 40), 1300, 1.0,
            rot=rnd.uniform(-10, 10))
    stamp(f, "VORSÄTZLICH?", 860, 1180, kt, 1.4, 50, RED, rot=10)


# ------------------------------------------------------------------ SCENE 6 bench
def bench_scene(lt, T, paper=0.0, counters=None, t_drei=None, shake_head=True):
    f = park_bg().copy()
    # cop behind, shaking his head
    tilt = math.sin(T * 7) * 12 if shake_head else 0
    person(f, "cop2", 540, 760, 0.85, expr="tired", tilt=tilt, arm_l=10, arm_r=-10, blink=blink(T, 4))
    # paper stack behind (Papierkram)
    if paper > 0:
        d = ImageDraw.Draw(f)
        hgt = 680 * paper
        for k in range(int(hgt / 22)):
            y = 1380 - k * 22
            jx = math.sin(k * 1.7) * 14
            d.rectangle([140 + jx, y - 18, 940 + jx, y], fill=(250, 250, 245), outline=(200, 200, 190))
        if paper > 0.9:
            # wedding cake topper on the paper stack
            top = 1380 - hgt
            paste_c(f, emoji("👰", 120), 470, top - 70)
            paste_c(f, emoji("🤵", 120), 610, top - 70)
            label(f, "PAPIERKRAM > HOCHZEIT", 540, top - 190, WHITE, 40, (20, 20, 30))
    ma, mr = M("auto", T), M("radler", T)
    person(f, "auto", 300, 1060, 0.95, expr="tired", inj=2, mouth=ma, arm_l=10, arm_r=-150, blink=blink(T, 1))
    # ice pack on the forehead
    paste_c(f, capsule(170, 90, (90, 170, 255), WHITE, radius=40, spec=0.6), 280, 820, rot=-15)
    paste_c(f, emoji("❄️", 50), 280, 820)
    person(f, "radler", 780, 1070, 0.92, expr="pain" if mr < 0.05 else "tired", mouth=mr, hurt=1.0, T=T,
           blink=blink(T, 2))
    bench(f, 540, 1250, 980)
    if t_drei is not None and T >= t_drei:
        for k in range(3):
            p = ease_back(clamp01((T - t_drei - k * 0.12) / 0.25))
            c = Image.new("RGBA", (220, 140), (0, 0, 0, 0))
            cd = ImageDraw.Draw(c)
            cd.rounded_rectangle([0, 0, 219, 139], radius=16, fill=(250, 250, 245), outline=TEAL, width=6)
            cd.text((110, 45), "RECHTS-", font=font(F_BLACK, 30), fill=(20, 40, 60), anchor="mm")
            cd.text((110, 90), "SCHUTZ", font=font(F_BLACK, 30), fill=(20, 40, 60), anchor="mm")
            paste_c(f, c, 640 + k * 150, 420 + k * 20, p, rot=(k - 1) * 12)
        pop_text(f, "×3", 900, 300, T - t_drei, 0.3, 120, YELLOW, RED)
    if counters:
        for k, (txt, t0) in enumerate(counters):
            if T >= t0:
                p = ease_back(clamp01((T - t0) / 0.25))
                label_im = text_img(txt, 66, WHITE, F_BLACK, stroke=7, glow=MAGENTA)
                paste_c(f, label_im, 540, 250 + k * 110, 0.3 + 0.7 * p)
    return f


def shot_bench(lt, dur, T, t_drei):
    return zoom_frame(bench_scene(lt, T, t_drei=t_drei), 1.12 - lt * 0.02, 540, 1000)


def shot_paper(lt, dur, T, counters, t_paper):
    paper = ease_io(clamp01((T - t_paper) / 1.4)) if T >= t_paper else 0.0
    f = bench_scene(lt, T, paper=paper, counters=counters, shake_head=True)
    if T >= t_paper:
        rnd = random.Random(3)
        d = ImageDraw.Draw(f)
        for k in range(16):
            x = (rnd.uniform(0, W) + T * rnd.uniform(-80, 80)) % W
            y = (rnd.uniform(-300, H) + (T - t_paper) * rnd.uniform(300, 600)) % H
            a = T * rnd.uniform(1, 3) + k
            pts = [(x + 50 * math.cos(a + q), y + 36 * math.sin(a + q)) for q in (0.6, 2.5, 3.7, 5.6)]
            d.polygon(pts, fill=(255, 255, 250), outline=(180, 180, 170))
    return zoom_frame(f, 1.0 + 0.03 * lt / max(dur, 0.1), 540, 900)


# ------------------------------------------------------------------ CTA
def shot_cta(lt, dur, T, t_lines, t_comment):
    f = bg_dark((14, 10, 34), (40, 10, 50)).copy()
    paste_c(f, radial(1400, MAGENTA, 0.25), 540, 800)
    # mini faces of the three parties
    for k, (who, ex, inj) in enumerate((("auto", "angry", 2), ("cop2", "tired", 0), ("radler", "angry", 0))):
        paste_c(f, head(who, ex, inj), 220 + k * 320, 1440 + math.sin(T * 3 + k) * 12, 0.55)
    txt = [("WER ZAHLT?", YELLOW), ("WER HAFTET?", TEAL), ("WER IST SCHULD?", MAGENTA)]
    for k, ((s, col), t0) in enumerate(zip(txt, t_lines)):
        if T >= t0:
            p = ease_back(clamp01((T - t0) / 0.25), 2.2)
            im = extrude_text(s, 92, col, mixc(col, (0, 0, 0), 0.6), depth=12, glow=col, max_w=1400)
            im = im if im.width <= 1020 else im.resize((1020, int(im.height * 1020 / im.width)))
            paste_c(f, im, 540, 330 + k * 190, 0.3 + 0.7 * p * (1 + 0.03 * math.sin(T * 6 + k)))
    if T >= t_comment:
        p = ease_back(clamp01((T - t_comment) / 0.3))
        d = ImageDraw.Draw(f)
        for k, (e, name, col) in enumerate((("🚗", "AUTOFAHRER", ORANGE), ("🚲", "RADFAHRER", TEAL))):
            x = 285 + k * 510
            bw = 470 * p
            d.rounded_rectangle([x - bw / 2, 940, x + bw / 2, 1080], radius=40, fill=col)
            if p > 0.6:
                paste_c(f, emoji(e, 70), x - 165, 1010)
                d.text((x + 35, 1010), name, font=font(F_BLACK, 32), fill=(15, 15, 25), anchor="mm")
        d.text((540, 900), "Wer hat Schuld? Stimm ab:", font=font(F_INTER, 44), fill=WHITE, anchor="mm")
        pill = text_img("DEINE MEINUNG IN DIE KOMMENTARE", 38, (15, 15, 25), F_INTER, max_w=1000)
        bw = pill.width + 220
        pul = 1.0 + 0.04 * math.sin(T * 8)
        d.rounded_rectangle([540 - bw / 2, 1170, 540 + bw / 2, 1290], radius=60, fill=YELLOW)
        paste_c(f, pill, 540 + 20, 1230, pul)
        paste_c(f, emoji("💬", 70), 540 - bw / 2 + 70, 1230)
        paste_c(f, emoji("👇", 80), 540 + bw / 2 - 60, 1230 + 12 * math.sin(T * 6))
    sub = text_img("ALLTAG KLAR – Wenn Alltag vor Gericht landet!", 38, (200, 200, 230), F_INTER_B)
    paste_c(f, sub, 540, 1760)
    return f
