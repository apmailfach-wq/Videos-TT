"""All shots of the video. Every shot is fn(lt, dur, T) -> RGBA frame (lt = local time, T = global time)."""
import math
import random
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from core import (BG0, BG1, BLUE, F_BLACK, F_BOLD, F_HAND, F_INTER, F_INTER_B, F_MONO, H, MAGENTA, RED, TEAL, W,
                  WHITE, YELLOW, capsule, clamp01, draw_char, ease_back, ease_in, ease_io, ease_out, emoji,
                  extrude_text, font, glitch, glow_dot, gradient, hand_pos, lerp, mixc, paste_c, perspective_card,
                  radial, sphere, text_img, zoom_frame)

CTX = {"mouth": lambda who, T: 0.0}


def M(who, T):
    return CTX["mouth"](who, T)


def blink(T, seed):
    return (T * 1.0 + seed * 0.37) % 3.1 < 0.12


# ------------------------------------------------------------------ cached backgrounds
@lru_cache(maxsize=None)
def bg_dark(top=BG0, bottom=BG1):
    return gradient(W, H, top, bottom)


@lru_cache(maxsize=None)
def city_img(width=2400, height=1400, seed=3, day=0.0):
    rnd = random.Random(seed)
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for layer, (col, hmin, hmax, wmin, wmax) in enumerate([((30, 20, 60), 300, 700, 120, 220),
                                                           ((18, 14, 40), 450, 1000, 140, 260)]):
        x = -50
        while x < width:
            bw = rnd.randint(wmin, wmax)
            bh = rnd.randint(hmin, hmax)
            top = height - bh
            d.rectangle([x, top, x + bw, height], fill=col + (255,))
            # neon rooftop line
            nc = rnd.choice([TEAL, MAGENTA, YELLOW])
            if rnd.random() < 0.5:
                d.rectangle([x, top, x + bw, top + 5], fill=nc + (255,))
            for wy in range(top + 30, height - 20, 46):
                for wx in range(x + 18, x + bw - 24, 34):
                    if rnd.random() < 0.38:
                        c = rnd.choice([(255, 210, 120), (120, 240, 255), (255, 120, 220), (255, 230, 160)])
                        d.rectangle([wx, wy, wx + 16, wy + 24], fill=c + (230,))
            x += bw + rnd.randint(4, 30)
    return im


@lru_cache(maxsize=None)
def stars_img(seed=5):
    rnd = random.Random(seed)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for _ in range(140):
        x, y, r = rnd.uniform(0, W), rnd.uniform(0, H * 0.6), rnd.uniform(1, 3)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, rnd.randint(80, 220)))
    return im


@lru_cache(maxsize=None)
def living_room():
    im = gradient(W, H, (30, 14, 54), (14, 8, 30))
    d = ImageDraw.Draw(im)
    # window with city
    d.rounded_rectangle([90, 260, 560, 820], radius=20, fill=(10, 10, 30), outline=(80, 60, 140), width=10)
    city = city_img(1200, 600, seed=8).resize((460, 230))
    im.alpha_composite(city, (95, 585))
    # TV glowing (football pitch)
    d.rounded_rectangle([600, 330, 1020, 600], radius=16, fill=(10, 10, 14))
    d.rectangle([620, 350, 1000, 580], fill=(20, 160, 70))
    d.line([(810, 350), (810, 580)], fill=WHITE, width=4)
    d.ellipse([770, 425, 850, 505], outline=WHITE, width=4)
    paste_c(im, radial(700, (40, 255, 140), 0.35), 810, 470)
    # sofa
    im.alpha_composite(capsule(980, 260, (120, 30, 110), MAGENTA, radius=60), (50, 1270))
    im.alpha_composite(capsule(1000, 240, (150, 40, 140), MAGENTA, radius=70), (40, 1420))
    # floor glow
    d.rectangle([0, 1640, W, H], fill=(16, 8, 30))
    paste_c(im, radial(1200, TEAL, 0.18), 540, 1700)
    return im


@lru_cache(maxsize=None)
def pub_room():
    im = gradient(W, H, (40, 16, 10), (14, 6, 4))
    d = ImageDraw.Draw(im)
    # shelves with backlit bottles
    for row in range(3):
        y = 260 + row * 190
        d.rectangle([60, y + 140, 1020, y + 152], fill=(90, 50, 30))
        for k in range(12):
            x = 90 + k * 78
            c = [(40, 160, 90), (150, 80, 30), (200, 200, 220), (120, 30, 40)][(k + row) % 4]
            im.alpha_composite(capsule(46, 120, c, TEAL, radius=20, spec=0.6), (x, y + 20))
    paste_c(im, radial(1400, TEAL, 0.18), 540, 560)
    # neon sign
    sign = text_img("KNEIPE", 120, MAGENTA, F_BLACK, glow=MAGENTA)
    paste_c(im, sign, 540, 180)
    # bar counter
    im.alpha_composite(capsule(1180, 300, (110, 60, 30), YELLOW, radius=40, spec=0.4), (-50, 1500))
    return im


@lru_cache(maxsize=None)
def bathroom():
    im = gradient(W, H, (10, 30, 40), (6, 14, 22))
    d = ImageDraw.Draw(im)
    for y in range(0, H, 120):
        d.line([(0, y), (W, y)], fill=(20, 60, 70), width=3)
    for x in range(0, W, 120):
        d.line([(x, 0), (x, H)], fill=(20, 60, 70), width=3)
    # mirror
    d.rounded_rectangle([110, 300, 970, 1450], radius=60, fill=(20, 40, 56), outline=(200, 220, 230), width=14)
    for k in range(7):
        x = 160 + k * 127
        paste_c(im, glow_dot(120, YELLOW), x, 270)
        d.ellipse([x - 22, 248, x + 22, 292], fill=(255, 240, 200))
    return im


def football(d=420, rot=0.0):
    ball = sphere(d, (245, 245, 250), TEAL, 0.5).copy()
    dr = ImageDraw.Draw(ball)
    c = d / 2
    r = d * 0.17
    pts = []
    for k in range(5):
        a = math.radians(rot + 72 * k - 90)
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    dr.polygon(pts, fill=(25, 25, 35))
    for k in range(5):
        a = math.radians(rot + 72 * k - 90)
        px, py = c + d * 0.38 * math.cos(a), c + d * 0.38 * math.sin(a)
        pp = [(px + r * 0.8 * math.cos(math.radians(rot + 72 * j + 90 + 72 * k)),
               py + r * 0.8 * math.sin(math.radians(rot + 72 * j + 90 + 72 * k))) for j in range(5)]
        dr.polygon(pp, fill=(25, 25, 35))
        dr.line([pts[k], (c + d * 0.3 * math.cos(a), c + d * 0.3 * math.sin(a))], fill=(60, 60, 70), width=3)
    mask = Image.new("L", ball.size, 0)
    ImageDraw.Draw(mask).ellipse([1, 1, d - 2, d - 2], fill=255)
    ball.putalpha(Image.fromarray(np.minimum(np.array(ball.getchannel("A")), np.array(mask))))
    # re-apply shading over the patches
    shade = sphere(d, (255, 255, 255), None, 0.0)
    arr = np.array(ball).astype(np.float32)
    sh = np.array(shade.convert("L")).astype(np.float32) / 255
    arr[..., :3] *= (0.45 + 0.65 * sh[..., None])
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


@lru_cache(maxsize=None)
def ball_cached(d, rot_q):
    return football(d, rot_q)


def car_side(color, rim, w=760, facing=1, doors_open=0.0, driver=None, T=0.0):
    h = int(w * 0.42)
    im = Image.new("RGBA", (w + 80, h + 120), (0, 0, 0, 0))
    body = capsule(w, int(h * 0.55), color, rim, radius=int(h * 0.22), spec=0.5)
    cab = capsule(int(w * 0.56), int(h * 0.5), mixc(color, (20, 20, 30), 0.25), rim, radius=int(h * 0.2))
    im.alpha_composite(cab, (40 + int(w * 0.2), 30))
    d = ImageDraw.Draw(im)
    # windows
    d.rounded_rectangle([40 + w * 0.24, 50, 40 + w * 0.48, 30 + h * 0.42], radius=18, fill=(30, 50, 80))
    d.rounded_rectangle([40 + w * 0.5, 50, 40 + w * 0.72, 30 + h * 0.42], radius=18, fill=(30, 50, 80))
    if driver:
        pass
    im.alpha_composite(body, (40, int(h * 0.42)))
    for fx in (0.2, 0.8):
        wx = 40 + w * fx
        whl = sphere(int(h * 0.38), (20, 20, 26), (90, 90, 110), 0.3)
        im.alpha_composite(whl, (int(wx - whl.width / 2), int(h * 0.42 + h * 0.55 - whl.height * 0.45)))
        d.ellipse([wx - h * 0.08, h * 0.97 - h * 0.08 + h * 0.0, wx + h * 0.08, h * 0.97 + h * 0.08],
                  fill=(160, 160, 170))
    # lights
    paste_c(im, glow_dot(120, (255, 250, 200)), 40 + w - 10, h * 0.62)
    paste_c(im, glow_dot(90, RED), 50, h * 0.62)
    if facing < 0:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im


@lru_cache(maxsize=8)
def car_cached(color, rim, w, facing):
    return car_side(color, rim, w, facing)


def car_rear(color, rim, w=420, brake=False):
    h = int(w * 0.7)
    im = Image.new("RGBA", (w + 120, h + 80), (0, 0, 0, 0))
    im.alpha_composite(capsule(int(w * 0.8), int(h * 0.45), mixc(color, (20, 20, 30), 0.25), rim, radius=50),
                       (60 + int(w * 0.1), 10))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([60 + w * 0.18, 30, 60 + w * 0.82, h * 0.38], radius=26, fill=(25, 40, 70))
    im.alpha_composite(capsule(w, int(h * 0.55), color, rim, radius=60, spec=0.5), (60, int(h * 0.35)))
    for sx in (0.12, 0.88):
        c = (255, 40, 40) if brake else (150, 20, 30)
        paste_c(im, glow_dot(200 if brake else 110, c), 60 + w * sx, h * 0.55)
        d.rounded_rectangle([60 + w * sx - 40, h * 0.5, 60 + w * sx + 40, h * 0.6], radius=10, fill=c)
    d.rounded_rectangle([60 + w * 0.36, h * 0.66, 60 + w * 0.64, h * 0.76], radius=6, fill=(230, 230, 230))
    d.text((60 + w * 0.5, h * 0.71), "SV·2026", font=font(F_BOLD, 20), fill=(20, 20, 30), anchor="mm")
    for sx in (0.1, 0.9):
        d.rounded_rectangle([60 + w * sx - 40, h * 0.85, 60 + w * sx + 40, h * 1.02], radius=12, fill=(14, 14, 18))
    return im


def speed_lines(frame, T, color=WHITE, n=26, cx=W / 2, cy=H * 0.45, seed=1):
    d = ImageDraw.Draw(frame)
    rnd = random.Random(seed)
    for i in range(n):
        a = rnd.uniform(0, math.tau)
        sp = rnd.uniform(0.8, 1.6)
        r0 = ((T * 900 * sp + rnd.uniform(0, 1400)) % 1400) + 200
        r1 = r0 + rnd.uniform(80, 260)
        d.line([(cx + math.cos(a) * r0, cy + math.sin(a) * r0), (cx + math.cos(a) * r1, cy + math.sin(a) * r1)],
               fill=color + (rnd.randint(60, 160),), width=rnd.randint(2, 6))


def police_lights(frame, T, strength=1.0):
    ph = (T * 4) % 2
    c = BLUE if ph < 1 else RED
    a = (0.5 + 0.5 * math.sin(T * 25)) * strength
    paste_c(frame, radial(1800, c, 0.55 * a, 1.4), W * (0.25 if ph < 1 else 0.75), H * 0.3)


# ------------------------------------------------------------------ HOOK
def shot_ball(lt, dur, T):
    f = bg_dark((6, 10, 26), (10, 30, 30)).copy()
    # stadium lights
    for x in (150, 540, 930):
        paste_c(f, radial(700, (200, 255, 240), 0.25), x, 120)
    # net perspective grid
    d = ImageDraw.Draw(f)
    for i in range(-12, 13):
        d.line([(540 + i * 90, 0), (540 + i * 40, 1500)], fill=(220, 240, 255, 70), width=3)
    for j in range(16):
        y = j * 100
        d.line([(0, y), (W, y + 30)], fill=(220, 240, 255, 60), width=3)
    p = lt / dur
    size = int(lerp(240, 980, ease_in(p)))
    rot = int(lt * 40 / 5) * 5 % 360
    ball = ball_cached(min(size, 980), rot)
    by = lerp(1500, 860, ease_out(p))
    paste_c(f, ball, 540 + math.sin(lt * 2) * 30, by)
    speed_lines(f, T, (255, 255, 255), 18, 540, by)
    return f


CONF = [(random.Random(i).uniform(-1, 1), random.Random(i * 3).uniform(-1.3, -0.2),
         random.Random(i * 7).choice([TEAL, MAGENTA, YELLOW, WHITE]), random.Random(i * 11).uniform(0, 360))
        for i in range(160)]


def confetti(f, lt, cx, cy, spread=1.0):
    d = ImageDraw.Draw(f)
    for vx, vy, c, r0 in CONF:
        x = cx + vx * 1300 * lt * spread
        y = cy + (vy * 1500 * lt + 1600 * lt * lt) * spread
        a = math.radians(r0 + lt * 400)
        s = 16
        pts = [(x + math.cos(a) * s, y + math.sin(a) * s * 0.5), (x - math.sin(a) * s * 0.5, y + math.cos(a) * s),
               (x - math.cos(a) * s, y - math.sin(a) * s * 0.5), (x + math.sin(a) * s * 0.5, y - math.cos(a) * s)]
        d.polygon(pts, fill=c)


def shot_net_boom(lt, dur, T):
    f = bg_dark((10, 10, 30), (30, 10, 40)).copy()
    paste_c(f, radial(1600, YELLOW, 0.5 * (1 - clamp01(lt / 0.6))), 540, 820)
    ball = ball_cached(980, 0)
    paste_c(f, ball, 540, 860, 1.0 + lt * 0.3, 1 - clamp01(lt / 0.35))
    confetti(f, lt + 0.05, 540, 860)
    txt = text_img("GESTERN HAT DEUTSCHLAND GEWONNEN.", 92, WHITE, F_BLACK, stroke=6, glow=TEAL, max_w=900)
    a = clamp01((lt - 0.1) / 0.15)
    paste_c(f, glitch(txt, T, 0.6 if lt < 0.3 else 0.15), 540, 1350, 1.0 + 0.1 * (1 - ease_out(lt / 0.3)), a)
    return f


def shot_bluelight(lt, dur, T):
    ph = int(T * 7) % 2
    c = (20, 60, 255) if ph == 0 else (255, 30, 60)
    f = gradient(W, H, mixc(c, (0, 0, 0), 0.35), mixc(c, (0, 0, 0), 0.75))
    paste_c(f, radial(1900, mixc(c, WHITE, 0.3), 0.8, 1.2), 540 + (200 if ph else -200), 700)
    lines = ["HEUTE", "VERLIEREN", "ZWEI", "KOLLEGEN"]
    for i, ln in enumerate(lines):
        if lt > 0.05 + i * 0.25:
            im = text_img(ln, 110, WHITE, F_BLACK, stroke=6, max_w=1060)
            paste_c(f, glitch(im, T, 0.9 if (lt - i * 0.25) < 0.25 else 0.25, seed=i), 540, 640 + i * 150)
    return f


@lru_cache(maxsize=None)
def license_card():
    w, h = 820, 520
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w, h], radius=40, fill=(250, 190, 215))
    d.rounded_rectangle([0, 0, w, 110], radius=40, fill=(220, 80, 150))
    d.rectangle([0, 70, w, 110], fill=(220, 80, 150))
    d.text((40, 58), "FÜHRERSCHEIN", font=font(F_BLACK, 52), fill=WHITE, anchor="lm")
    d.rounded_rectangle([40, 150, 270, 450], radius=20, fill=(200, 210, 230))
    d.ellipse([105, 190, 205, 290], fill=(120, 130, 160))
    d.chord([75, 290, 235, 470], 180, 360, fill=(120, 130, 160))
    for i, t in enumerate(["1. MUSTERMANN", "2. KOLLEGE", "4a. 2026", "9. B"]):
        d.text((310, 190 + i * 66), t, font=font(F_BOLD, 34), fill=(90, 40, 80), anchor="lm")
    return im


def shot_license(lt, dur, T):
    ph = int(T * 7) % 2
    c = (20, 60, 255) if ph == 0 else (255, 30, 60)
    f = gradient(W, H, mixc(c, (0, 0, 0), 0.55), (6, 6, 14))
    card = license_card()
    split = ease_out((lt - 0.55) / 0.4) if lt > 0.55 else 0
    left = card.crop((0, 0, card.width // 2, card.height))
    right = card.crop((card.width // 2, 0, card.width, card.height))
    s = 0.95 + 0.06 * math.sin(lt * 3)
    paste_c(f, left, 540 - card.width / 4 - split * 120, 820 + split * 80, s, rot=split * 14)
    paste_c(f, right, 540 + card.width / 4 + split * 120, 820 + split * 120, s, rot=-split * 18)
    if split > 0:
        d = ImageDraw.Draw(f)
        x = 540
        pts = [(x, 520), (x - 30, 620), (x + 25, 720), (x - 20, 820), (x + 30, 930), (x, 1100)]
        d.line(pts, fill=WHITE + (int(255 * (1 - split)),), width=8)
    im = text_img("IHREN FÜHRERSCHEIN", 104, RED, F_BLACK, stroke=6, max_w=1000, glow=RED)
    paste_c(f, glitch(im, T, 0.8 if lt < 0.3 else 0.2, seed=3), 540, 1300, 1 + 0.15 * (1 - ease_out(lt / 0.25)))
    return f


# ------------------------------------------------------------------ SCENE 1 party
def shot_drone(lt, dur, T):
    f = bg_dark((6, 4, 20), (40, 12, 60)).copy()
    f.alpha_composite(stars_img())
    paste_c(f, sphere(170, (240, 240, 210), YELLOW, 0.2), 820, 300)
    p = ease_in(lt / dur)
    city = city_img()
    z = 1.0 + p * 2.4
    cw = int(city.width * 0.9 * z)
    ch = int(city.height * 0.9 * z)
    c2 = city.resize((cw, ch), Image.BILINEAR)
    x = W / 2 - lt * 120 * z
    y = H - ch * 0.62 + p * ch * 0.25
    paste_c(f, c2, x, y + ch / 2)
    if lt > dur * 0.55:
        # two glowing windows we dive into
        a = clamp01((lt - dur * 0.55) / (dur * 0.3))
        for k, c in enumerate((TEAL, MAGENTA)):
            paste_c(f, radial(int(500 * z), c, 0.7 * a), 340 + k * 400, 1150)
    return f


def rafael_room(lt, T, cam=0.0, s=1.25, jump=0.0, joint=False, smoke=0.0, popcorn=None):
    f = living_room().copy()
    cx = 540 + math.sin(cam) * 140
    sc = s * (1 + 0.05 * math.cos(cam))
    cy = 1020 - jump
    arm = 150 if joint else (165 if jump > 5 else 30)
    draw_char(f, "rafael", cx, cy, sc, arm_l=(165 if jump > 5 else 25), arm_r=arm, mouth=M("rafael", T),
              blink=blink(T, 1), hold=(1, "joint", arm) if joint else None)
    if popcorn is not None:
        d = ImageDraw.Draw(f)
        rnd = random.Random(4)
        for i in range(30):
            vx, vy = rnd.uniform(-500, 500), rnd.uniform(-1400, -700)
            tt = popcorn * 0.35
            x = cx + vx * tt
            y = 900 + vy * tt + 1400 * tt * tt
            r = rnd.uniform(12, 20)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 245, 210))
            d.ellipse([x - r * 0.4, y - r * 0.9, x + r * 0.6, y], fill=(255, 225, 120))
    if smoke > 0:
        hx, hy = hand_pos(cx, cy, sc, 1, 150)
        sm = smoke_ball(min(1.0, smoke))
        paste_c(f, sm, hx + 60, hy - 260 - smoke * 120, 0.8 + smoke * 0.5, min(1, smoke * 2) * 0.9)
    return f


@lru_cache(maxsize=32)
def _smoke(q):
    p = q / 20
    rnd = random.Random(2)
    im = Image.new("RGBA", (520, 520), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = []
    for i in range(24):
        a = i / 24 * math.tau
        target = (260 + math.cos(a) * 170, 260 + math.sin(a) * 170)
        start = (260 + rnd.uniform(-140, 140), 420 + rnd.uniform(-60, 60))
        pts.append((lerp(start[0], target[0], p), lerp(start[1], target[1], p)))
    for x, y in pts:
        r = 46
        d.ellipse([x - r, y - r, x + r, y + r], fill=(200, 230, 225, 110))
    if p > 0.6:
        cc = 260
        for k in range(5):
            a = math.radians(72 * k - 90)
            d.ellipse([cc + math.cos(a) * 90 - 30, cc + math.sin(a) * 90 - 30, cc + math.cos(a) * 90 + 30,
                       cc + math.sin(a) * 90 + 30], fill=(220, 255, 245, int(150 * (p - 0.6) / 0.4)))
        d.ellipse([cc - 40, cc - 40, cc + 40, cc + 40], fill=(220, 255, 245, int(150 * (p - 0.6) / 0.4)))
    return im.filter(ImageFilter.GaussianBlur(14))


def smoke_ball(p):
    return _smoke(int(clamp01(p) * 20))


def klaus_pub(lt, T, s=1.3, raise_p=1.0, low=True, beer_count=0, count_t=None, slosh=0.0):
    f = pub_room().copy()
    cx, cy = 540, 980
    arm = lerp(40, 168, ease_out(raise_p))
    draw_char(f, "klaus", cx, cy, s, arm_l=25, arm_r=arm, mouth=M("klaus", T), blink=blink(T, 2),
              hold=(1, "beer", arm))
    if slosh > 0:
        hx, hy = hand_pos(cx, cy, s, 1, arm)
        d = ImageDraw.Draw(f)
        rnd = random.Random(9)
        for i in range(18):
            vx, vy = rnd.uniform(-300, 300), rnd.uniform(-700, -300)
            tt = slosh
            x, y = hx + vx * tt, hy - 150 + vy * tt + 900 * tt * tt
            r = rnd.uniform(8, 16)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 210, 60, 220))
    if low:
        f = zoom_frame(f, 1.12, 540, 1100)
    if beer_count:
        draw_counter(f, beer_count, count_t)
    return f


def draw_counter(f, n, ct, y=300):
    p = clamp01(ct / 0.25) if ct is not None else 1
    card = Image.new("RGBA", (420, 190), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, 419, 189], radius=40, fill=(20, 10, 30, 230), outline=YELLOW, width=6)
    card.alpha_composite(emoji("🍺", 120), (30, 35))
    d.text((290, 98), f"× {n}", font=font(F_BLACK, 84), fill=YELLOW, anchor="mm")
    paste_c(f, card, 820, y, 0.6 + 0.4 * ease_back(p, 2.5), rot=-6)


def split_screen(left, right, T, label=True):
    f = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    lw = W // 2
    lc = left.crop((W // 4, 0, W // 4 + lw, H))
    rc = right.crop((W // 4, 0, W // 4 + lw, H))
    f.paste(lc, (0, 0))
    f.paste(rc, (lw, 0))
    d = ImageDraw.Draw(f)
    d.rectangle([lw - 4, 0, lw + 4, H], fill=WHITE)
    paste_c(f, radial(200, YELLOW, 0.8), lw, H / 2)
    if label:
        for x, name, c in ((lw / 2, "RAFAEL, 30", TEAL), (lw + lw / 2, "KLAUS, 55", MAGENTA)):
            tag = text_img(name, 40, c, F_BLACK, stroke=4, glow=c)
            paste_c(f, tag, x, 230)
    return f


def shot_rafael_party(lt, dur, T):
    jump = max(0, math.sin(clamp01(lt / 0.6) * math.pi)) * 160
    joint = lt > 0.7
    smoke = (lt - 0.9) / 0.9 if lt > 0.9 else 0
    f = rafael_room(lt, T, cam=lt * 1.6, jump=jump, joint=joint, smoke=smoke, popcorn=lt if lt < 1.2 else None)
    return zoom_frame(f, 1.05 + lt * 0.05)


def shot_klaus_party(lt, dur, T):
    k = min(2, 1 + int(lt / 0.7))
    return klaus_pub(lt, T, raise_p=lt / 0.4, slosh=clamp01(lt / 0.8), beer_count=k, count_t=(lt % 0.7))


def shot_split_party(lt, dur, T):
    left = rafael_room(lt, T, cam=1.0 + lt, joint=True, smoke=0.6 + lt * 0.3, s=1.25)
    k = min(4, 3 + int(lt / 0.8))
    right = klaus_pub(lt, T, raise_p=1, low=False, slosh=clamp01((lt % 0.8) / 0.6))
    f = split_screen(left, right, T)
    draw_counter(f, k, (lt % 0.8), y=430)
    return f


# ------------------------------------------------------------------ SCENE 2 night
def shot_timelapse(lt, dur, T):
    p = lt / dur
    sky = mixc((10, 6, 30), (255, 140, 90), clamp01((p - 0.6) / 0.4))
    f = gradient(W, H, mixc(sky, (0, 0, 0), 0.4), sky)
    f.alpha_composite(stars_img()) if p < 0.6 else None
    # sun + moon arcs
    a = math.pi * (1 - clamp01(p * 1.6))
    paste_c(f, sphere(150, (240, 240, 220), YELLOW, 0.2), 540 + math.cos(a) * 420, 900 - math.sin(a) * 600)
    a2 = math.pi * (1 - clamp01((p - 0.5) * 2))
    if p > 0.5:
        paste_c(f, radial(500, (255, 200, 80), 0.9), 540 + math.cos(a2) * 420, 1000 - math.sin(a2) * 600)
    city = city_img().rotate(-p * 25, resample=Image.BILINEAR, expand=False)
    paste_c(f, city.resize((int(city.width * 0.8), int(city.height * 0.8))), 540, 1380)
    # digital clock
    mins = int(lerp(23 * 60, 30 * 60 + 30, ease_io(p)))
    hh, mm = (mins // 60) % 24, mins % 60
    clock = text_img(f"{hh:02d}:{mm:02d}", 200, YELLOW, F_MONO, glow=YELLOW)
    paste_c(f, clock, 540, 420)
    return f


def xray(who, lt, T, gauge_val):
    f = bg_dark((0, 10, 30), (0, 4, 14)).copy()
    col = TEAL if who == "rafael" else YELLOW
    # silhouette outline: draw character then make it glassy-blue
    tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_char(tmp, who, 540, 760, 1.6, arm_l=12, arm_r=12)
    a = tmp.getchannel("A")
    edge = a.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5))
    body = Image.new("RGBA", (W, H), (40, 120, 255, 0))
    body.putalpha(a.point(lambda v: int(v * 0.25)))
    f.alpha_composite(body)
    ed = Image.new("RGBA", (W, H), (120, 200, 255, 0))
    ed.putalpha(edge)
    f.alpha_composite(ed)
    # vessels
    d = ImageDraw.Draw(f)
    paths = [[(540, 620), (500, 820), (520, 1000), (480, 1180)], [(540, 620), (610, 800), (580, 980), (620, 1160)],
             [(520, 760), (380, 820), (300, 950)], [(560, 760), (700, 820), (780, 950)]]
    for pth in paths:
        d.line(pth, fill=(255, 40, 80, 230), width=16, joint="curve")
    rnd = random.Random(1 if who == "rafael" else 2)
    for i in range(46):
        pth = paths[i % len(paths)]
        u = (rnd.random() + lt * 0.35) % 1
        seg = u * (len(pth) - 1)
        k = min(int(seg), len(pth) - 2)
        fr = seg - k
        x = lerp(pth[k][0], pth[k + 1][0], fr) + rnd.uniform(-6, 6)
        y = lerp(pth[k][1], pth[k + 1][1], fr)
        if who == "rafael":
            paste_c(f, glow_dot(46, (80, 255, 120)), x, y)
            d.regular_polygon((x, y, 9), 6, fill=(150, 255, 150))
        else:
            paste_c(f, glow_dot(46, YELLOW), x, y)
            d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=(255, 250, 200), width=3)
    tag = text_img("THC" if who == "rafael" else "ALKOHOL", 64, (120, 255, 140) if who == "rafael" else YELLOW,
                   F_BLACK, glow=(120, 255, 140) if who == "rafael" else YELLOW)
    paste_c(f, tag, 540, 260)
    draw_gauge(f, 540, 1520, gauge_val, T)
    return f


def draw_gauge(f, cx, cy, val, T):
    d = ImageDraw.Draw(f)
    r = 230
    for i in range(60):
        a0 = 180 + i * 3
        c = mixc((40, 220, 120), YELLOW, i / 30) if i < 30 else mixc(YELLOW, RED, (i - 30) / 30)
        d.arc([cx - r, cy - r, cx + r, cy + r], a0, a0 + 3.2, fill=c, width=38)
    a = math.radians(180 + val * 180)
    d.line([(cx, cy), (cx + math.cos(a) * (r - 30), cy + math.sin(a) * (r - 30))], fill=WHITE, width=12)
    d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=WHITE)
    if val > 0.66 and int(T * 4) % 2 == 0:
        paste_c(f, emoji("⚠️", 110), cx + 290, cy - 120)


def shot_xray_r(lt, dur, T):
    return xray("rafael", lt, T, lerp(0.95, 0.72, ease_out(lt / dur)))


def shot_xray_k(lt, dur, T):
    return xray("klaus", lt, T, lerp(0.97, 0.7, ease_out(lt / dur)))


# ------------------------------------------------------------------ SCENE 3 morning
def shot_alarm(lt, dur, T):
    f = bg_dark((40, 20, 10), (12, 6, 20)).copy()
    paste_c(f, radial(1400, (255, 150, 60), 0.4), 540, 900)
    shake = math.sin(lt * 70) * 14
    clock = sphere(620, (230, 40, 70), MAGENTA, 0.4)
    paste_c(f, sphere(200, (220, 220, 230), YELLOW), 300 + shake, 560)
    paste_c(f, sphere(200, (220, 220, 230), YELLOW), 780 + shake, 560)
    paste_c(f, clock, 540 + shake, 960, rot=shake * 0.3)
    disp = Image.new("RGBA", (420, 180), (0, 0, 0, 0))
    ImageDraw.Draw(disp).rounded_rectangle([0, 0, 419, 179], radius=30, fill=(10, 10, 16))
    t = text_img("06:30", 130, (120, 255, 220) if int(T * 6) % 2 else (40, 120, 110), F_MONO)
    paste_c(disp, t, 210, 90)
    paste_c(f, disp, 540 + shake, 980)
    for k in range(3):
        rr = 380 + k * 70 + (lt * 300) % 70
        ImageDraw.Draw(f).arc([540 - rr, 960 - rr, 540 + rr, 960 + rr], 200, 340, fill=YELLOW + (150,), width=8)
    return zoom_frame(f, 1.0 + lt * 0.08)


def shot_mirror(who):
    def fn(lt, dur, T):
        f = bathroom().copy()
        # reflection
        draw_char(f, who, 540, 860, 1.7, arm_l=20, arm_r=(55 if who == "klaus" else 30), mouth=M(who, T),
                  glasses=(who == "rafael"), blink=blink(T, 3), hold=(1, "coffee", 55) if who == "klaus" else None,
                  tilt=math.sin(lt * 2) * 3)
        d = ImageDraw.Draw(f)
        d.line([(200, 380), (420, 600)], fill=(255, 255, 255, 50), width=40)
        d.line([(260, 380), (480, 600)], fill=(255, 255, 255, 30), width=14)
        tag = text_img("RAFAEL" if who == "rafael" else "KLAUS", 44, TEAL if who == "rafael" else MAGENTA, F_BLACK,
                       glow=TEAL if who == "rafael" else MAGENTA)
        paste_c(f, tag, 540, 1540)
        return zoom_frame(f, 1.04 + lt * 0.04, 540, 900)
    return fn


def road_bg(T, horizon=820, speed=1.0, morning=True):
    top = (255, 150, 110) if morning else (10, 10, 30)
    f = gradient(W, H, (40, 30, 90), top)
    city = city_img(seed=4)
    paste_c(f, city.resize((int(city.width * 0.6), int(city.height * 0.6))), 540 - (T * 40) % 300, horizon - 300)
    d = ImageDraw.Draw(f)
    d.polygon([(0, H), (W, H), (W * 0.58, horizon), (W * 0.42, horizon)], fill=(30, 30, 44))
    d.rectangle([0, horizon, W, horizon + 4], fill=(255, 120, 200))
    for k in range(12):
        u = ((k / 12) + T * 0.9 * speed) % 1
        y0 = horizon + (H - horizon) * u ** 2
        y1 = horizon + (H - horizon) * min(1, (u + 0.035)) ** 2
        w0 = 4 + 30 * u
        d.polygon([(540 - w0, y0), (540 + w0, y0), (540 + w0 * 1.1, y1), (540 - w0 * 1.1, y1)], fill=YELLOW)
    for side in (-1, 1):
        d.line([(540 + side * W * 0.08, horizon), (540 + side * W * 0.62, H)], fill=TEAL, width=8)
    return f


def shot_doors(lt, dur, T):
    f = road_bg(0, horizon=1100, speed=0)
    c1 = car_cached((20, 170, 160), TEAL, 600, 1)
    c2 = car_cached((190, 40, 140), MAGENTA, 600, -1)
    shake = math.sin(lt * 60) * 8 * max(0, 1 - lt / 0.3)
    paste_c(f, c1, 250, 1380 + shake, 0.78)
    paste_c(f, c2, 830, 1380 + shake, 0.78)
    # flying question mark
    q = extrude_text("?", 520, YELLOW, (150, 110, 0), depth=26, glow=YELLOW)
    p = clamp01((lt - 0.15) / 0.6)
    paste_c(f, q, lerp(-200, 540, ease_out(p)), 780 + math.sin(lt * 6) * 20, 0.6 + 0.5 * ease_back(p),
            rot=math.sin(lt * 4) * 12)
    if lt > 0.35:
        w = text_img("WIRKLICH?", 120, WHITE, F_BLACK, stroke=8, glow=MAGENTA)
        paste_c(f, w, 540, 330, ease_back(clamp01((lt - 0.35) / 0.25), 2))
    return f


def shot_key(lt, dur, T):
    f = bg_dark((14, 10, 30), (4, 4, 10)).copy()
    paste_c(f, radial(1100, TEAL, 0.25), 540, 960)
    d = ImageDraw.Draw(f)
    d.ellipse([290, 710, 790, 1210], fill=(30, 30, 40), outline=(120, 120, 140), width=14)
    d.ellipse([440, 860, 640, 1060], fill=(10, 10, 14))
    ang = -ease_out(clamp01((lt - 0.15) / 0.3)) * 75
    key = Image.new("RGBA", (300, 620), (0, 0, 0, 0))
    kd = ImageDraw.Draw(key)
    kd.rectangle([125, 260, 175, 600], fill=(200, 200, 215))
    for k in range(5):
        kd.rectangle([175, 380 + k * 40, 195, 400 + k * 40], fill=(200, 200, 215))
    key.alpha_composite(capsule(260, 280, (30, 30, 36), TEAL, radius=110), (20, 0))
    paste_c(f, key.rotate(ang, resample=Image.BICUBIC, expand=True), 540, 820)
    for k, txt in ((0, "MOTOR"), (1, "AN")):
        pass
    return zoom_frame(f, 1.15 + lt * 0.1)


# ------------------------------------------------------------------ SCENE 4 drive
def shot_chase(lt, dur, T):
    f = road_bg(T, speed=1.6)
    paste_c(f, car_rear((20, 170, 160), TEAL), 330 + math.sin(T * 3) * 10, 1380, 1.05)
    paste_c(f, car_rear((190, 40, 140), MAGENTA), 760 + math.sin(T * 3 + 1) * 10, 1350, 1.0)
    speed_lines(f, T, WHITE, 30, 540, 820)
    return f


def shot_cockpit(lt, dur, T):
    f = road_bg(T, speed=1.8)
    d = ImageDraw.Draw(f)
    d.rectangle([0, 1260, W, H], fill=(16, 14, 24))
    d.rectangle([0, 1250, W, 1270], fill=TEAL)
    # speedo
    paste_c(f, radial(380, TEAL, 0.4), 760, 1460)
    t = text_img(f"{int(48 + lt * 12)}", 110, TEAL, F_MONO, glow=TEAL)
    paste_c(f, t, 760, 1460)
    # wheel
    ang = math.sin(T * 2) * 8
    wheel = Image.new("RGBA", (760, 760), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wheel)
    wd.ellipse([20, 20, 740, 740], outline=(40, 40, 52), width=70)
    wd.ellipse([20, 20, 740, 740], outline=TEAL, width=6)
    wd.rectangle([60, 350, 700, 420], fill=(40, 40, 52))
    wd.ellipse([300, 300, 460, 460], fill=(30, 30, 40), outline=TEAL, width=6)
    paste_c(f, wheel.rotate(ang, resample=Image.BICUBIC), 380, 1620)
    speed_lines(f, T, WHITE, 20, 540, 800)
    return f


def shot_drone_top(lt, dur, T):
    f = Image.new("RGBA", (W, H), (34, 34, 46, 255))
    d = ImageDraw.Draw(f)
    d.rectangle([0, 0, 220, H], fill=(20, 60, 40))
    d.rectangle([860, 0, W, H], fill=(20, 60, 40))
    for k in range(-1, 12):
        y = (k * 200 + T * 1400) % (H + 200) - 200
        d.rectangle([535, y, 545, y + 110], fill=YELLOW)
    d.line([(225, 0), (225, H)], fill=TEAL, width=8)
    d.line([(855, 0), (855, H)], fill=TEAL, width=8)
    for x, c, rim in ((380, (20, 170, 160), TEAL), (700, (190, 40, 140), MAGENTA)):
        car = capsule(200, 380, c, rim, radius=80, spec=0.6)
        car = car.copy()
        cd = ImageDraw.Draw(car)
        cd.rounded_rectangle([30, 90, 170, 170], radius=30, fill=(30, 50, 80))
        cd.rounded_rectangle([40, 260, 160, 320], radius=24, fill=(30, 50, 80))
        paste_c(f, car, x + math.sin(T * 2 + x) * 8, 1000)
        for sx in (-60, 60):
            paste_c(f, glow_dot(160, (255, 250, 210)), x + sx, 790)
    # trees
    rnd = random.Random(2)
    for i in range(14):
        x = rnd.choice([rnd.uniform(30, 190), rnd.uniform(890, 1050)])
        y = (rnd.uniform(0, H) + T * 1400) % (H + 200) - 100
        paste_c(f, sphere(110, (30, 120, 70), TEAL, 0.1), x, y)
    return zoom_frame(f, 1.0 + 0.05 * lt)


def shot_traffic_light(lt, dur, T):
    f = road_bg(T if lt < 0.5 else T * 0.2, speed=1.0 if lt < 0.45 else 0.2)
    d = ImageDraw.Draw(f)
    d.rectangle([880, 200, 910, 1100], fill=(40, 40, 50))
    d.rounded_rectangle([800, 160, 990, 640], radius=40, fill=(20, 20, 26))
    red_on = lt > 0.15
    for k, c in enumerate([RED, YELLOW, (40, 255, 120)]):
        on = (k == 0 and red_on) or (k == 2 and not red_on)
        y = 240 + k * 145
        d.ellipse([845, y - 55, 945, y + 55], fill=c if on else mixc(c, (0, 0, 0), 0.75))
        if on:
            paste_c(f, glow_dot(360, c), 895, y)
    brake = lt > 0.45
    car = car_rear((20, 170, 160), TEAL, brake=brake)
    shake = math.sin(lt * 80) * 10 if brake else 0
    paste_c(f, car, 480 + shake, 1380 - (40 if brake else 0), 1.1, rot=(-3 if brake else 0))
    if brake:
        # skid marks + screech text
        d.line([(400, 1650), (420, H)], fill=(10, 10, 10), width=24)
        d.line([(600, 1650), (590, H)], fill=(10, 10, 10), width=24)
        s = text_img("QUIIIETSCH!", 96, YELLOW, F_BLACK, stroke=6, glow=RED)
        paste_c(f, s, 470, 900, ease_back(clamp01((lt - 0.45) / 0.2), 2.5), rot=8)
    return f


# ------------------------------------------------------------------ SCENE 5 control
def shot_windshield(lt, dur, T):
    f = bg_dark((10, 10, 24), (4, 4, 10)).copy()
    d = ImageDraw.Draw(f)
    d.polygon([(120, 500), (960, 500), (1060, 1300), (20, 1300)], fill=(20, 40, 70))
    d.polygon([(120, 500), (960, 500), (1060, 1300), (20, 1300)], outline=(160, 180, 200), width=10)
    draw_char(f, "rafael", 360, 1000, 0.9, arm_l=60, arm_r=60, worried=True, blink=False)
    draw_char(f, "klaus", 760, 1000, 0.9, arm_l=60, arm_r=60, worried=True)
    ph = (T * 4) % 2
    c = BLUE if ph < 1 else RED
    a = 0.5 + 0.5 * math.sin(T * 22)
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    paste_c(over, radial(1300, c, 0.75 * a, 1.2), 540 + (250 if ph < 1 else -250), 800)
    f.alpha_composite(over)
    d = ImageDraw.Draw(f)
    d.line([(140, 520), (330, 700)], fill=(255, 255, 255, 50), width=40)
    return zoom_frame(f, 1.05 + lt * 0.06)


def shot_cop_pan(lt, dur, T):
    p = ease_io(lt / min(dur, 1.4))
    big = Image.new("RGBA", (W, 2900), (0, 0, 0, 0))
    bg = gradient(W, 2900, (8, 8, 24), (20, 20, 40))
    big.alpha_composite(bg)
    police_lights(big, T)
    draw_char(big, "cop", 540, 1150, 2.6, arm_l=12, arm_r=12, mouth=M("polizei", T), legs=True, blink=blink(T, 5))
    y0 = lerp(2900 - H, 120, p)
    f = big.crop((0, int(y0), W, int(y0) + H))
    tag = text_img("POLIZEIKONTROLLE", 54, WHITE, F_BLACK, stroke=5, glow=BLUE)
    paste_c(f, tag, 540, 240)
    return f


def shot_freeze(lt, dur, T):
    f = Image.new("RGBA", (W, H), (250, 230, 40, 255))
    d = ImageDraw.Draw(f)
    for i in range(48):
        a = i / 48 * math.tau
        d.polygon([(540, 960), (540 + math.cos(a) * 1600, 960 + math.sin(a) * 1600),
                   (540 + math.cos(a + 0.05) * 1600, 960 + math.sin(a + 0.05) * 1600)], fill=(255, 140, 30))
    # halftone
    for y in range(0, H, 36):
        for x in range(0, W, 36):
            r = 6 + 5 * math.sin(x * 0.01 + y * 0.008)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 60))
    draw_char(f, "rafael", 300, 1050, 1.15, arm_l=150, arm_r=150, mouth=0.9, worried=True)
    draw_char(f, "klaus", 790, 1050, 1.15, arm_l=150, arm_r=150, mouth=0.9, worried=True)
    s = extrude_text("!!", 300, RED, (110, 0, 20), depth=20)
    paste_c(f, s, 540, 520, ease_back(clamp01(lt / 0.2), 3), rot=-8)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    out.alpha_composite(f)
    ImageDraw.Draw(out).rectangle([0, 0, W - 1, H - 1], outline=(0, 0, 0), width=40)
    return zoom_frame(out, 1.0 + 0.06 * ease_out(lt / 0.3))


def shot_breath(lt, dur, T):
    f = bg_dark((10, 6, 30), (4, 4, 10)).copy()
    police_lights(f, T, 0.6)
    draw_char(f, "klaus", 360, 1000, 1.25, arm_l=20, arm_r=60, worried=True, mouth=0.5 if lt < 0.9 else 0.1)
    dev = Image.new("RGBA", (330, 560), (0, 0, 0, 0))
    dev.alpha_composite(capsule(300, 540, (230, 230, 40), YELLOW, radius=60), (15, 10))
    dd = ImageDraw.Draw(dev)
    dd.rounded_rectangle([50, 80, 280, 230], radius=20, fill=(10, 14, 12))
    val = "0,5 ‰" if lt > 0.9 else ("…" if int(lt * 6) % 2 else "")
    col = RED if (lt > 0.9 and int(T * 5) % 2 == 0) else (255, 120, 120) if lt > 0.9 else (120, 255, 160)
    dd.text((165, 155), val, font=font(F_MONO, 60), fill=col, anchor="mm")
    dd.rectangle([150, 0, 180, 40], fill=(240, 240, 240))
    paste_c(f, dev, 780, 980, rot=-15)
    if lt > 0.9:
        big = text_img("0,5 ‰", 220, RED, F_BLACK, stroke=10, glow=RED)
        a = clamp01((lt - 0.9) / 0.2)
        if int(T * 5) % 2 == 0 or lt < 1.3:
            paste_c(f, big, 540, 420, 0.6 + 0.4 * ease_back(a, 2.5), a)
    return f


def stamp_card(lines, accent, icon=None, w=940):
    """3D neon fact card. lines = [(text, size, color)]"""
    pad = 50
    imgs = [text_img(t, s, c, F_BLACK if s >= 60 else F_INTER, max_w=w - 120) for t, s, c in lines]
    h = sum(i.height for i in imgs) + pad * 2 + (150 if icon else 0)
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=48, fill=(14, 10, 30, 235), outline=accent, width=8)
    y = pad
    if icon:
        e = emoji(icon, 130)
        card.alpha_composite(e, ((w - e.width) // 2, y))
        y += 150
    for im in imgs:
        card.alpha_composite(im, ((w - im.width) // 2, y))
        y += im.height
    # extruded depth
    out = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    side = Image.new("RGBA", card.size, mixc(accent, (0, 0, 0), 0.6) + (255,))
    side.putalpha(card.getchannel("A"))
    for k in range(18, 0, -2):
        out.alpha_composite(side, (k, k))
    out.alpha_composite(card)
    g = Image.new("RGBA", out.size, accent + (0,))
    g.putalpha(out.getchannel("A").filter(ImageFilter.GaussianBlur(26)).point(lambda v: int(v * 0.7)))
    res = Image.new("RGBA", (out.width + 80, out.height + 80), (0, 0, 0, 0))
    res.alpha_composite(g, (40, 40))
    res.alpha_composite(out, (40, 40))
    return res


@lru_cache(maxsize=None)
def stamp_cached(key):
    S = STAMPS[key]
    return stamp_card(S["lines"], S["accent"], S.get("icon"))


STAMPS = {
    "thc": dict(icon="🌿", accent=(120, 255, 140), lines=[("THC-GRENZWERT", 52, WHITE), ("3,5 ng/ml", 130, (120, 255, 140)),
                                                         ("im Blutserum", 50, (200, 220, 230))]),
    "wait": dict(icon="⏳", accent=YELLOW, lines=[("SICHERE WARTEZEIT?", 60, WHITE), ("GIBT ES NICHT", 92, YELLOW)]),
    "fine": dict(icon="💸", accent=MAGENTA, lines=[("ab 0,5 ‰ oder 3,5 ng/ml", 48, (230, 230, 240)),
                                                  ("500 €", 170, MAGENTA), ("1. Verstoß", 46, (200, 200, 220))]),
    "points": dict(icon="📉", accent=TEAL, lines=[("+ 2 PUNKTE", 110, TEAL), ("in Flensburg", 48, (200, 220, 230))]),
    "ban": dict(icon="🚫", accent=RED, lines=[("1 MONAT", 130, RED), ("FAHRVERBOT", 92, WHITE)]),
    "crime": dict(icon="⚖️", accent=RED, lines=[("ab 0,3 ‰ + Fahrfehler", 54, WHITE), ("STRAFTAT", 112, RED),
                                                ("oder Ausfallerscheinungen", 44, (200, 200, 220))]),
    "mix": dict(icon="🌿🍺", accent=YELLOW, lines=[("CANNABIS + ALKOHOL", 64, WHITE), ("mind. 1.000 €", 120, YELLOW)]),
    "zero": dict(icon="🔰", accent=TEAL, lines=[("PROBEZEIT ODER U21", 62, WHITE), ("0,0", 200, TEAL),
                                               ("NULL TOLERANZ", 80, WHITE)]),
}


def fact_bg(kind, lt, T):
    if kind == "faces":
        f = bg_dark((20, 6, 40), (6, 4, 14)).copy()
        police_lights(f, T, 0.5)
        draw_char(f, "rafael", 260, 1560, 0.9, arm_l=150, arm_r=20, worried=True, blink=blink(T, 1))
        draw_char(f, "klaus", 820, 1560, 0.9, arm_l=20, arm_r=150, worried=True, blink=blink(T, 2))
        return f
    if kind == "car":
        f = road_bg(0, horizon=1200, speed=0, morning=True)
        police_lights(f, T, 0.8)
        paste_c(f, car_cached((20, 170, 160), TEAL, 600, 1), 300, 1520)
        paste_c(f, car_cached((190, 40, 140), MAGENTA, 600, -1), 790, 1520)
        return f
    if kind == "cop":
        f = bg_dark((8, 8, 30), (2, 2, 10)).copy()
        police_lights(f, T)
        draw_char(f, "cop", 540, 1450, 1.4, arm_l=40, arm_r=40, mouth=0.0)
        return f
    f = bg_dark((10, 4, 26), (2, 2, 8)).copy()
    police_lights(f, T, 0.7)
    return f


def shot_fact(stamp_key, bg_kind):
    def fn(lt, dur, T):
        f = fact_bg(bg_kind, lt, T)
        dim = Image.new("RGBA", (W, H), (0, 0, 0, 90))
        f.alpha_composite(dim)
        card = stamp_cached(stamp_key)
        p = clamp01(lt / 0.22)
        sc = lerp(1.7, 1.0, ease_out(p))
        tilt = math.sin(T * 1.4) * 0.12
        c2 = perspective_card(card, tilt_x=0.05, tilt_y=tilt)
        shake = (1 - clamp01((lt - 0.22) / 0.15)) * 14 * math.sin(lt * 90) if lt > 0.2 else 0
        paste_c(f, c2, 540 + shake, 820, sc * (1 + 0.03 * lt), p, rot=-3 + math.sin(T) * 1.5)
        return f
    return fn


# ------------------------------------------------------------------ SCENE 6 punchline
def shot_roadside(lt, dur, T):
    f = road_bg(0, horizon=1050, speed=0, morning=True)
    p = ease_in(clamp01(lt / 1.2))
    for x, c, rim, k in ((300, (20, 170, 160), TEAL, 0), (790, (190, 40, 140), MAGENTA, 1)):
        car = car_cached(c, rim, 600, 1 if k == 0 else -1)
        paste_c(f, car, lerp(x, 540, p), lerp(1230, 400, p), max(0.05, 1 - p * 0.95), 1 - p * 0.3,
                rot=p * 360 * (1 if k else -1))
    draw_char(f, "klaus", 700, 1260, 0.75, arm_l=10, arm_r=10, mouth=M("klaus", T), worried=True, legs=True,
              blink=blink(T, 2))
    draw_char(f, "rafael", 380, 1260, 0.75, arm_l=10, arm_r=10, mouth=M("rafael", T), worried=True, legs=True)
    return zoom_frame(f, 1.0 + 0.12 * ease_io(lt / dur), 540, 1150)


def shot_faces(lt, dur, T):
    f = road_bg(0, horizon=1350, speed=0, morning=True)
    draw_char(f, "klaus", 770, 1050, 1.5, arm_l=10, arm_r=10, mouth=M("klaus", T), worried=True,
              blink=blink(T, 2))
    draw_char(f, "rafael", 310, 1050, 1.5, arm_l=10, arm_r=10, mouth=M("rafael", T), worried=True, glasses=True)
    return zoom_frame(f, 1.0 + 0.1 * ease_io(lt / dur), 540, 900)


def bus_scene(lt, T, kid_ball_zoom=0.0):
    f = gradient(W, H, (20, 24, 50), (10, 10, 22))
    d = ImageDraw.Draw(f)
    # windows with passing lights
    d.rectangle([0, 260, W, 900], fill=(30, 40, 80))
    for k in range(8):
        x = (k * 260 - T * 600) % (W + 400) - 200
        paste_c(f, glow_dot(260, [TEAL, MAGENTA, YELLOW][k % 3]), x, 520)
    for x in (0, 360, 720, 1080):
        d.rectangle([x - 18, 260, x + 18, 900], fill=(60, 60, 80))
    d.rectangle([0, 900, W, 930], fill=YELLOW)
    # seats
    f.alpha_composite(capsule(700, 360, (40, 90, 180), BLUE, radius=60), (20, 1180))
    f.alpha_composite(capsule(330, 360, (40, 90, 180), BLUE, radius=60), (760, 1180))
    sway = math.sin(T * 2.2) * 6
    draw_char(f, "rafael", 210, 1120 + sway, 0.95, arm_l=15, arm_r=15, worried=True, glasses=False,
              blink=blink(T, 1))
    draw_char(f, "klaus", 520, 1120 + sway, 0.95, arm_l=15, arm_r=15, worried=True, blink=blink(T, 2))
    draw_char(f, "kid", 900, 1180 + sway, 0.7, arm_l=150, arm_r=20, mouth=0.35)
    paste_c(f, ball_cached(150, 0), 820, 1000 + sway)
    # handrail
    d.line([(0, 300), (W, 300)], fill=(200, 200, 210), width=14)
    sign = text_img("NACH DER PARTY: BUS, BAHN ODER TAXI", 62, WHITE, F_BLACK, stroke=6, glow=TEAL, max_w=960)
    return f, sign


def shot_bus(lt, dur, T):
    f, sign = bus_scene(lt, T)
    if lt > 0.15:
        paste_c(f, sign, 540, 1660, ease_back(clamp01((lt - 0.15) / 0.3), 2))
    return zoom_frame(f, 1.0 + 0.04 * lt)


CTA_LINES = ["Wie habt ihr den Sieg gefeiert?",
             "Und wusstet ihr, wie gefährlich Restalkohol am nächsten Morgen ist?",
             "Ab in die Kommentare! 💬"]


def shot_cta(lt, dur, T, t_lines):
    f, _ = bus_scene(lt + 4, T)
    f = f.filter(ImageFilter.GaussianBlur(10))
    f.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 120)))
    for i, (txt, tl) in enumerate(zip(CTA_LINES, t_lines)):
        if T >= tl:
            p = clamp01((T - tl) / 0.3)
            im, y = cta_block(i)
            paste_c(f, im, 540, y + math.sin(T * 2 + i) * 8, 0.3 + 0.7 * ease_back(p, 2.6), p)
    disc = text_img("Angaben ohne Gewähr, Stand 2026.", 34, (190, 190, 210), F_INTER_B)
    paste_c(f, disc, 540, 1790)
    # loop: last 0.6 s dive into the kid's ball -> matches opening frame
    end_p = clamp01((lt - (dur - 0.6)) / 0.6)
    if end_p > 0:
        zoomed = zoom_frame(bus_scene(lt, T)[0], 1 + end_p * 6, 820, 1000)
        zoomed.putalpha(int(255 * end_p))
        f.alpha_composite(zoomed)
        if end_p > 0.5:
            a = (end_p - 0.5) / 0.5
            start = shot_ball(0.0, 1.0, 0.0)
            start.putalpha(int(255 * a))
            f.alpha_composite(start)
    return f


@lru_cache(maxsize=4)
def cta_block(i):
    cols = [YELLOW, WHITE, TEAL]
    sizes = [84, 64]
    imgs = [text_img(CTA_LINES[k].upper(), sizes[k], cols[k], F_BLACK, stroke=6,
                     glow=cols[k] if k != 1 else MAGENTA, max_w=940) for k in range(2)] + [cta_pill()]
    y = 330
    centers = []
    for im in imgs:
        centers.append(y + im.height / 2)
        y += im.height + 70
    return imgs[i], centers[i]


@lru_cache(maxsize=1)
def cta_pill():
    t = text_img("AB IN DIE KOMMENTARE!", 64, WHITE, F_BLACK)
    e = emoji("💬", 100)
    w, h = t.width + e.width + 90, 170
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], radius=85, fill=MAGENTA)
    im.alpha_composite(e, (40, (h - e.height) // 2))
    im.alpha_composite(t, (e.width + 50, (h - t.height) // 2))
    return im
