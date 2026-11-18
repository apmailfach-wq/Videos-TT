"""All camera set-ups. Each shot fn(t, d) -> 1080x1920 RGBA image (local time t of duration d)."""
import math
import random

import numpy as np

from draw import (Pen, W, H, OUT, SKIN, SHIRT, SHIRT_D, CAR, CAR_D, CAR_L, GLASS, RED, RED_D, TEAL, LAMP,
                  WATER_TOP, WATER_BOT, NIGHT_TOP, NIGHT_BOT, rgba, lerp, clamp01, ease_out, ease_in, ease_io,
                  god_rays, specks, bubble, bubble_burst, bubble_column, wave_line, car_side, car_front, head,
                  person, hand, hammer)

INTERIOR_TOP = (30, 34, 46)
INTERIOR_BOT = (12, 14, 20)


def wob(t, f=1.0, a=1.0, ph=0.0):
    return a * (math.sin(t * f * 6.283 + ph) * 0.6 + math.sin(t * f * 2.9 * 6.283 + ph * 1.7) * 0.4)


# ================================================================ HOOK: bridge
def sky_city(pen, t, horizon=700):
    r = random.Random(11)
    pen.ell(860, 260, 70, fill=(230, 235, 210), ol=None)
    pen.ell(860, 260, 120, fill=(230, 235, 210, 25), ol=None)
    for i in range(16):
        x = -300 + i * 110 + r.uniform(-20, 20)
        hgt = r.uniform(80, 300)
        pen.rect(x, horizon - hgt, x + r.uniform(60, 110), horizon + 40, (12, 18, 34), None)
        for k in range(int(hgt // 40)):
            if r.random() < 0.45:
                pen.rect(x + 14, horizon - hgt + 18 + k * 40, x + 30, horizon - hgt + 32 + k * 40, (255, 210, 120, 150),
                         None)
    for i in range(70):
        x = r.uniform(-300, 1400)
        y = r.uniform(-300, horizon - 320)
        pen.ell(x, y, 2.5, fill=(220, 230, 255, 120 + int(80 * math.sin(t * 5 + i))), ol=None, n=6)


def river(pen, t, y0, x0=-500, x1=1600, lights=True):
    pen.poly([(x0, y0), (x1, y0), (x1, 3200), (x0, 3200)], (10, 54, 62), None)
    pen.poly([(x0, y0 + 160), (x1, y0 + 160), (x1, 3200), (x0, 3200)], (6, 36, 46), None)
    for k in range(9):
        pts = wave_line(x0, x1, y0 + 14 + k * 42, 5 + k, t, k=0.02, speed=2 + k * 0.2, phase=k)
        pen.line(pts, (70, 170, 170, 130 - k * 12), 4, cap=False)
    if lights:
        for lx in (180, 520, 880):
            for k in range(6):
                yy = y0 + 20 + k * 36
                ww = 40 + 20 * math.sin(t * 6 + k + lx)
                pen.rect(lx - ww, yy, lx + ww, yy + 8, (255, 210, 120, 110 - k * 15), None)


def rain(pen, t, n=70, seed=2, col=(170, 200, 230, 70)):
    r = random.Random(seed)
    for i in range(n):
        x = (r.uniform(-300, 1400) - t * 300) % 1700 - 300
        y = (r.uniform(-300, 2200) + t * 2400) % 2500 - 300
        pen.line([(x, y), (x - 14, y + 70)], col, 3, cap=False)


def railing(pen, y, x0, x1, gap=None, col=(120, 128, 140)):
    def keep(x):
        return gap is None or not (gap[0] < x < gap[1])
    for x in range(int(x0), int(x1), 70):
        if keep(x):
            pen.rect(x - 7, y - 90, x + 7, y, col, OUT, 4)
    for yy in (y - 90, y - 50):
        if gap is None:
            pen.rect(x0, yy - 8, x1, yy + 8, col, OUT, 4)
        else:
            pen.rect(x0, yy - 8, gap[0], yy + 8, col, OUT, 4)
            pen.rect(gap[1], yy - 8, x1, yy + 8, col, OUT, 4)


def debris(pen, t, ox, oy, n=14, seed=8, speed=1.0, col=(120, 128, 140), g=900, spread=700):
    r = random.Random(seed)
    for i in range(n):
        vx = r.uniform(-1, 1) * spread
        vy = r.uniform(-1.0, 0.2) * spread
        L = r.uniform(30, 120)
        tt = t * speed
        x = ox + vx * tt
        y = oy + vy * tt + g * tt * tt
        a = r.uniform(0, 360) + tt * r.uniform(-500, 500)
        pen.push(x, y, a)
        pen.rect(-L / 2, -7, L / 2, 7, col, OUT, 4)
        pen.pop()


def sparks(pen, t, ox, oy, n=26, seed=12, life=0.5):
    r = random.Random(seed)
    for i in range(n):
        a = r.uniform(-math.pi, 0.2)
        sp = r.uniform(400, 1300)
        age = t
        if age > life * r.uniform(0.5, 1):
            continue
        x, y = ox + math.cos(a) * sp * age, oy + math.sin(a) * sp * age + 900 * age * age
        pen.line([(x, y), (x - math.cos(a) * 40, y - math.sin(a) * 40)], (255, 220, 90, 230), 5)


def shot_bridge(t, d):
    # slow-motion after impact
    tt = t if t < 0.14 else 0.14 + (t - 0.14) * 0.32
    cam = (540, 820 + 120 * ease_io(t), 1.0 + 0.16 * t, lerp(-3, 3, t))
    pen = Pen(cam, NIGHT_TOP, (20, 44, 60))
    sky_city(pen, t)
    river(pen, t, 1420)
    for px in (140, 940):
        pen.rect(px - 70, 780, px + 70, 1500, (34, 40, 52), OUT, 8)
        pen.rect(px - 70, 780, px - 40, 1500, (46, 54, 68), None)
    for lx in (-120, 300, 760, 1180):
        pen.rect(lx - 6, 520, lx + 6, 700, (60, 66, 80), OUT, 3)
        pen.ell(lx, 515, 16, fill=LAMP, ol=OUT, w=3)
        pen.ell(lx, 515, 60, fill=(255, 210, 120, 40), ol=None)
    broke = t > 0.1
    cy = 600 + 520 * ease_in(clamp01((tt - 0.12) / 0.3)) + 60 * tt
    cs = lerp(0.42, 0.72, ease_out(clamp01(tt / 0.35)))
    cr = lerp(0, -16, clamp01((tt - 0.1) / 0.3))
    if not broke:
        car_front(pen, 560, 640, 0.42, 0, face="panic")
    pen.rect(-300, 700, 1400, 800, (48, 56, 70), OUT, 8)
    pen.rect(-300, 770, 1400, 800, (30, 36, 46), None)
    railing(pen, 700, -300, 1400, gap=(360, 760) if broke else None)
    if broke:
        car_front(pen, 560, cy, cs, cr, face="panic", sy=lerp(1, 0.86, clamp01(tt / 0.3)))
        debris(pen, tt + 0.02, 560, 650, n=16, speed=1.0)
        sparks(pen, tt, 380, 640)
        sparks(pen, tt, 740, 640, seed=13)
    rain(pen, t)
    return pen.finish()


def shot_fall_side(t, d):
    cam = (540 + 40 * t, 760 + 420 * t, 1.02 + 0.1 * t, lerp(5, -4, t))
    pen = Pen(cam, NIGHT_TOP, (22, 48, 64))
    sky_city(pen, t, horizon=1250)
    pen.rect(-600, 160, 1800, 280, (48, 56, 70), OUT, 8)
    pen.rect(-600, 250, 1800, 280, (30, 36, 46), None)
    railing(pen, 160, -600, 1800, gap=(150, 420))
    pen.rect(860, 280, 1000, 1700, (34, 40, 52), OUT, 8)
    river(pen, t, 1600)
    x = lerp(300, 560, t)
    y = lerp(520, 1180, t) + 90 * t * t
    car_side(pen, x, y, 0.95, lerp(28, 52, t), inside=lambda p: head(p, 60, -86, 26, "panic", (1, 0)))
    debris(pen, 0.35 + t * 0.32, 300, 260, n=10, seed=21, speed=1.0)
    rain(pen, t + 1)
    return pen.finish()


# ================================================================ underwater impact
def underwater_bg(pen, t, surface=None):
    if surface is not None:
        pen.poly([(-600, -800), (1700, -800)] + [tuple(p) for p in wave_line(1700, -600, surface, 14, t, k=0.01)][::1],
                 (90, 200, 190), None)
        pen.line(wave_line(-600, 1700, surface, 14, t, k=0.01), (210, 255, 245), 10, cap=False)
        pen.ell(540, surface - 40, 520, 140, (170, 240, 225, 90), None)
    god_rays(pen, t, y0=(surface or -200) if surface is not None else -200)
    specks(pen, t)


def shot_under_entry(t, d):
    cam = (540, 900 + 60 * t, 1.0 + 0.08 * t, lerp(-4, 3, t))
    pen = Pen(cam, WATER_TOP, WATER_BOT)
    underwater_bg(pen, t, surface=300)
    k = ease_out(clamp01(t / 0.9))
    cy = lerp(220, 980, k)
    bubble_column(pen, t, 540, cy - 100, n=26, height=700, rmax=22, wobble=60)
    car_front(pen, 540, cy, lerp(0.55, 1.15, k), lerp(14, -10, k), face="panic")
    bubble_burst(pen, t, 540, 330, n=90, spread=1100, rise=300, rmax=46)
    return pen.finish()


def shot_under_impact(t, d):
    sh = 30 * (1 - t * 0.5)
    cam = (540 + wob(t, 7, sh), 1000 + wob(t, 6, sh, 1), 1.0 + 0.1 * t, wob(t, 2, 4))
    pen = Pen(cam, (16, 92, 96), WATER_BOT)
    underwater_bg(pen, t + 1)
    k = ease_in(clamp01(t / 0.95))
    car_front(pen, 540, lerp(820, 1120, k), lerp(1.3, 3.6, k), lerp(-8, 16, k), face="panic")
    bubble_burst(pen, t, 540, 1000, n=110, seed=7, spread=1600, rise=200, rmin=14, rmax=90, life=1.2)
    return pen.finish()


# ================================================================ interior (choice / variant A)
def water_level(T):
    # inside water rises: 4s floor -> 8s chest -> 14s neck
    if T < 8:
        return lerp(1700, 1200, ease_io((T - 4) / 4))
    return lerp(1200, 1040, clamp01((T - 8) / 6))


def window_outside(pen, t, x0, y0, x1, y1, lights=True, col=(12, 70, 74)):
    pen.rrect(x0, y0, x1, y1, 60, col, None)
    r = random.Random(4)
    for i in range(16):
        bx = x0 + 40 + r.random() * (x1 - x0 - 80)
        by = y1 - 30 - ((t * 260 * (0.6 + r.random()) + r.random() * (y1 - y0)) % (y1 - y0 - 60))
        bubble(pen, bx + 10 * math.sin(t * 5 + i), by, 5 + 14 * r.random(), 0.8)
    pen.poly([(x0 + 60, y0), (x0 + 200, y0), (x0 + 60, y1)], (120, 220, 210, 25 if lights else 10), None)
    pen.rrect(x0, y0, x1, y1, 60, None, (40, 44, 54), 28)
    pen.rrect(x0 - 14, y0 - 14, x1 + 14, y1 + 14, 70, None, OUT, 6)


def inside_water(pen, t, level, x0=-600, x1=1700):
    surf = [tuple(p) for p in wave_line(x0, x1, level, 12, t, k=0.014, speed=3)]
    pen.poly(surf + [(x1, 3000), (x0, 3000)], (22, 130, 132, 140), None)
    pen.line(surf, (190, 255, 240, 220), 7, cap=False)
    r = random.Random(6)
    for i in range(14):
        bx = r.uniform(x0 + 400, x1 - 400)
        by = level + 60 + ((-t * 200 + r.random() * 900) % 900)
        bubble(pen, bx, by, 4 + 10 * r.random(), 0.7)


def interior(pen, t, T, level, lights=1.0, expr="panic", look=None, arms=1.0):
    pen.rect(-600, -600, 1700, 400, (20, 22, 30), None)
    pen.ell(640, 390, 60, 20, rgba(LAMP, 255 * lights) if lights > 0.1 else (60, 60, 50), OUT, 5)
    if lights > 0.1:
        pen.ell(640, 420, 360, 220, (255, 220, 140, int(22 * lights)), None)
    window_outside(pen, t, 70, 440, 1010, 990, lights > 0.1)
    pen.rect(-600, 990, 1700, 2600, (38, 42, 54), None)
    pen.line([(-600, 1010), (1700, 1010)], (60, 66, 80), 10, cap=False)
    pen.rrect(640, 650, 840, 1700, 50, (56, 40, 48), OUT, 8)
    pen.rrect(650, 560, 820, 720, 40, (64, 46, 54), OUT, 8)
    sw = math.sin(t * 9)
    look = look or (math.sin(T * 4.3), -0.2)
    person(pen, 470, 1100, 1.18, ang=3 * math.sin(t * 5),
           la=(150 + 25 * sw * arms, 30), ra=(-150 + 25 * sw * arms, -30), ll=(-60, 60), rl=(-50, 60), expr=expr,
           look=look)
    pen.limb([(590, 980), (380, 1330)], (44, 46, 54), 30, 5)
    pen.rrect(560, 1300, 650, 1360, 10, (30, 30, 36), OUT, 5)
    pen.rect(590, 1318, 620, 1342, RED, None)
    pen.poly([(-600, 1180), (230, 1180), (330, 2600), (-600, 2600)], (28, 30, 40), OUT, 8)
    pen.ell(190, 1160, 36, 170, None, (26, 28, 34), 26)
    pen.line([(190, 1160), (40, 1400)], (26, 28, 34), 26)
    inside_water(pen, t, level)


def shot_interior_wide(t, d, T):
    cam = (540, 1000 + 40 * t, 1.0 + 0.08 * t, lerp(-3, 2, t / d))
    pen = Pen(cam, INTERIOR_TOP, INTERIOR_BOT)
    interior(pen, t, T, water_level(T))
    return pen.finish()


def shot_interior_close(t, d, T):
    cam = (480, 950, 1.65 + 0.15 * t / d, lerp(6, -4, t / d))
    pen = Pen(cam, INTERIOR_TOP, INTERIOR_BOT)
    interior(pen, t, T, water_level(T), look=(0.1 * math.sin(t * 2), 0.2))
    return pen.finish()


def shot_interior_low(t, d, T):
    lv = water_level(T)
    cam = (520, lv - 260 + 20 * math.sin(t * 3), 1.4 + 0.12 * t / d, lerp(-8, -2, t / d), -1)
    pen = Pen(cam, INTERIOR_TOP, INTERIOR_BOT)
    interior(pen, t, T, lv, look=(-0.2, 0.1))
    for i in range(6):
        bubble(pen, 300 + i * 140, lv + 140 + 40 * math.sin(t * 3 + i) - t * 90, 26 + 8 * (i % 3), 0.8)
    return pen.finish()


def shot_door_handle(t, d, T):
    yanks = (0.15, 0.55, 0.92, 1.28)
    pull = 0.0
    for y in yanks:
        a = t - y
        if 0 <= a < 0.3:
            pull = max(pull, math.sin(a / 0.3 * math.pi))
    cam = (540 + 18 * pull, 980 + 8 * pull, 1.0 + 0.12 * t / d, lerp(-5, 5, t / d))
    pen = Pen(cam, (40, 44, 56), (18, 20, 28))
    window_outside(pen, t, -100, 120, 1180, 560)
    pen.rect(-600, 560, 1700, 2600, (42, 46, 58), None)
    pen.line([(-600, 580), (1700, 580)], (64, 70, 86), 12, cap=False)
    pen.rrect(-200, 1180, 1300, 1330, 40, (34, 36, 46), OUT, 8)
    for yy in (760, 1500, 1620):
        pen.line([(-200, yy), (1300, yy)], (56, 62, 76), 4, cap=False)
    pen.rrect(330, 820, 760, 1020, 50, (16, 18, 24), OUT, 8)
    # door seam glows red: it does not move
    pen.line([(1040, 560), (1040, 2600)], rgba(RED, 120 + 120 * pull), 10, cap=False)
    pen.push(400, 920, -26 * pull)
    pen.rrect(0, -26, 330, 26, 22, (190, 198, 210), OUT, 7)
    pen.line([(20, -12), (300, -12)], (240, 245, 250), 5)
    pen.pop()
    hand(pen, 620 - 40 * pull, 950 + 70 * pull, 1.25, ang=-26 * pull + 8, curl=1.0)
    if pull > 0.2:
        for k in range(3):
            pen.arc(600, 980, 330 + k * 40, 120, 160, (255, 255, 255, int(160 * pull)), 7)
    inside_water(pen, t, water_level(T) + 150)
    return pen.finish()


PRESSURE_ARROWS = [(-1, 0.0), (-1, 0.35), (-1, -0.35), (0, -1), (0, 1), (-0.7, -0.7), (-0.7, 0.7)]


def shot_outside_pressure(t, d, T):
    cam = (520 + 60 * t / d, 1000, 1.05 + 0.15 * t / d, lerp(-4, 3, t / d))
    pen = Pen(cam, (14, 80, 86), WATER_BOT)
    god_rays(pen, t + 3, n=6, alpha=18)
    specks(pen, t + 2)

    def inside(p):
        head(p, 70, -86, 24, "panic", (-1, 0))
        p.limb([(40, -60), (14, -94)], SHIRT, 10, 4)

    car_side(pen, 540, 1060, 1.55, -4, lights=False, inside=inside, door_glow=0.6 + 0.4 * math.sin(t * 12))
    puls = 0.5 + 0.5 * math.sin(t * 10)
    dx_, dy_ = 540 + 1.55 * 75, 1060 - 1.55 * 40
    for i, (ax, ay) in enumerate([(-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1), (0, 1)]):
        L = 220
        off = 260 + 40 * puls
        n = math.hypot(ax, ay)
        sx, sy = dx_ + ax / n * off, dy_ + ay / n * off
        pen.arrow(sx, sy, sx - ax / n * L, sy - ay / n * L, 46, RED, OUT, 7)
    bubble_column(pen, t, 760, 900, n=10, height=900, rmax=12)
    return pen.finish()


def shot_topdown(t, d, T):
    cam = (520, 1000, 1.0 + 0.1 * t / d, lerp(8, -6, t / d))
    pen = Pen(cam, (12, 70, 78), (4, 28, 38))
    for k in range(6):
        rr = ((t * 160 + k * 160) % 960)
        pen.ell(540, 1000, 400 + rr, 600 + rr, None, (90, 200, 190, int(60 * (1 - rr / 960))), 5)
    specks(pen, t, n=40, drift=(30, 0))
    # car from above
    pen.rrect(360, 480, 760, 1560, 140, CAR, OUT, 10)
    pen.poly([(400, 700), (720, 700), (690, 820), (430, 820)], rgba(GLASS, 220), OUT, 6)
    pen.rrect(420, 820, 700, 1300, 50, CAR_L, OUT, 6)
    pen.poly([(430, 1300), (690, 1300), (710, 1400), (410, 1400)], rgba(GLASS, 220), OUT, 6)
    pen.ell(490, 950, 62, fill=(46, 30, 24), ol=OUT, w=6)
    pen.ell(490, 990, 110, 46, SHIRT, OUT, 6)
    # door (hinge at front) tries to open, gets slammed shut
    push = 0.5 + 0.5 * math.sin(t * 7)
    ang = 7 * push
    pen.push(360, 840, ang)
    pen.rrect(-24, 0, 6, 300, 8, CAR_D, OUT, 6)
    pen.pop()
    pen.arrow(470, 1000, 395, 1000, 22, (255, 255, 255), OUT, 5)
    pul = 30 * math.sin(t * 9)
    for yy in (850, 990, 1130):
        pen.arrow(-60 + pul, yy, 300 + pul, yy, 64, RED, OUT, 8)
    pen.arrow(140, 640, 330, 820, 54, RED, OUT, 8)
    pen.arrow(140, 1340, 330, 1170, 54, RED, OUT, 8)
    return pen.finish()


def shot_dark(t, d, T):
    flick = 1.0 if t < 0.2 else (0.0 if t > 0.55 else (1.0 if int(t * 30) % 3 == 0 else 0.0))
    cam = (520, 1000, 1.25 + 0.25 * t / d, lerp(-2, -9, t / d))
    pen = Pen(cam, INTERIOR_TOP, INTERIOR_BOT)
    interior(pen, t, T, water_level(T), lights=flick, expr="panic", look=(0, -0.4), arms=0.4)
    return pen.finish()


# ================================================================ variant B
def shot_belt(t, d, T):
    cam = (540, 1000, lerp(1.35, 1.05, ease_out(t / d)), lerp(12, -6, ease_out(t / d)))
    pen = Pen(cam, (44, 40, 52), (16, 14, 22))
    pen.rrect(-200, 300, 1300, 2300, 120, (58, 42, 50), OUT, 8)
    for x in range(-100, 1300, 160):
        pen.line([(x, 300), (x, 2300)], (70, 52, 62), 6, cap=False)
    rel = clamp01((t - 0.32) / 0.5)
    k = ease_out(rel)
    # strap + tongue (flies out after release)
    tx, ty = lerp(560, 980, k), lerp(1000, 420, k)
    pen.limb([(1400, -200), (tx + 60, ty - 60)], (50, 52, 60), 120, 7)
    pen.push(tx, ty, -45 + 200 * k)
    pen.rrect(-60, -40, 120, 40, 12, (200, 205, 215), OUT, 7)
    pen.rrect(-30, -16, 70, 16, 8, (40, 42, 50), None)
    pen.pop()
    if 0 < rel < 0.6:
        for i in range(4):
            pen.line([(tx - 120 - i * 40, ty + 120 + i * 30), (tx - 260 - i * 40, ty + 260 + i * 30)],
                     (255, 255, 255, int(200 * (1 - rel / 0.6))), 8)
    # buckle
    pen.rrect(330, 940, 650, 1260, 50, (26, 26, 32), OUT, 8)
    press = clamp01(1 - abs(t - 0.28) / 0.12)
    pen.rrect(390, 1010 + 10 * press, 590, 1090 + 10 * press, 18, RED if press < 0.5 else (255, 90, 90), OUT, 6)
    pen.limb([(490, 1260), (490, 1600)], (50, 52, 60), 110, 7)
    hand(pen, lerp(260, 380, clamp01(t / 0.25)) - 60 * k, lerp(1380, 1180, clamp01(t / 0.25)) + 80 * k, 1.1,
         ang=-60, curl=0.9, thumb_out=0.2)
    if 0.25 < t < 0.45:
        for a in range(0, 360, 45):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            pen.line([(490 + ca * 200, 1050 + sa * 200), (490 + ca * 280, 1050 + sa * 280)], (255, 255, 255), 10)
    return pen.finish()


def shot_window_down(t, d, T):
    cam = (lerp(480, 600, t / d), 960, 1.05 + 0.1 * t / d, lerp(3, -3, t / d))
    pen = Pen(cam, INTERIOR_TOP, INTERIOR_BOT)
    x0, y0, x1, y1 = 60, 360, 1020, 1300
    wl = 760 + 30 * math.sin(t * 3)
    pen.rrect(x0, y0, x1, y1, 70, (10, 20, 40), None)
    pen.ell(820, 480, 50, fill=(230, 235, 210), ol=None)
    pen.poly([tuple(p) for p in wave_line(x0, x1, wl, 14, t, k=0.02, speed=3)] + [(x1, y1), (x0, y1)], (16, 96, 100), None)
    pen.line(wave_line(x0, x1, wl, 14, t, k=0.02, speed=3), (190, 255, 240), 6, cap=False)
    k = ease_io(clamp01((t - 0.1) / 0.75))
    gtop = lerp(y0 + 10, y1 + 40, k)
    if gtop < y1:
        pen.rect(x0 + 20, gtop, x1 - 20, y1, rgba(GLASS, 150), OUT, 5)
        pen.line([(x0 + 120, gtop + 40), (x0 + 260, gtop + 200)], (230, 250, 255, 120), 14)
    pen.rrect(x0, y0, x1, y1, 70, None, (40, 44, 54), 30)
    pen.rect(-600, y1, 1700, 2600, (38, 42, 54), OUT, 8)
    pen.line([(-600, y1 + 20), (1700, y1 + 20)], (64, 70, 86), 14, cap=False)
    if gtop > wl:
        flow = clamp01((gtop - wl) / 300)
        for i in range(5):
            xx = x0 + 120 + i * 180 + 20 * math.sin(t * 8 + i)
            pen.poly([(xx - 40, y1 - 10), (xx + 40, y1 - 10), (xx + 70 + 30 * flow, y1 + 500 * flow),
                      (xx - 70 - 30 * flow, y1 + 500 * flow)], (40, 170, 170, 150), None)
    pen.rrect(700, 1500, 960, 1620, 30, (30, 32, 40), OUT, 7)
    pen.rrect(760, 1520 + 20 * k, 900, 1590 + 10 * k, 16, (70, 74, 86), OUT, 5)
    hand(pen, 720, 1600 + 10 * k, 1.0, ang=-30, curl=0.7)
    return pen.finish()


def shot_squeeze(t, d, T):
    k = ease_io(t / d)
    cam = (520, lerp(1040, 900, k), 1.0 + 0.08 * k, lerp(-3, 4, k))
    pen = Pen(cam, (16, 88, 94), WATER_BOT)
    god_rays(pen, t + 5, n=6, alpha=20)
    specks(pen, t + 4)
    wig = math.sin(t * 16) * (1 - k)

    def inside(p):
        py = lerp(40, -110, ease_io(clamp01(t / 1.0))) + lerp(0, -170, ease_in(clamp01((t - 1.0) / 0.5)))
        p.push(80, py, -25 + 18 * wig)
        person(p, 0, 0, 0.5, la=(-170 + 20 * wig, 0), ra=(170 - 20 * wig, 0), ll=(10, 0), rl=(-10, 0),
               expr="determined", look=(0, -1))
        p.pop()

    car_side(pen, 520, 1250 + 120 * k, 2.3, -6, lights=False, front_open=1.0, inside=inside)
    bubble_column(pen, t, 640, 900, n=18, height=800, rmax=14, wobble=30)
    return pen.finish()


def shot_swim_up(t, d, T):
    k = t / d
    cam = (540, 1000 - 220 * k, 1.0 + 0.06 * k, lerp(-6, 6, k))
    pen = Pen(cam, (70, 170, 160), (2, 10, 18))
    pen.ell(540, -200, 700, 380, (170, 240, 220, 120), None)
    pen.ell(540, -200, 420, 230, (230, 255, 240, 140), None)
    for i in range(9):
        a = math.radians(-150 + i * 15 + 5 * math.sin(t + i))
        pen.poly([(540, -150), (540 + math.cos(a - 0.05) * 2600, -150 - math.sin(a - 0.05) * -2600),
                  (540 + math.cos(a + 0.05) * 2600, -150 - math.sin(a + 0.05) * -2600)], (180, 250, 230, 22), None)
    specks(pen, t + 6, drift=(0, 60))
    pen.ell(540, 2100 + 200 * k, 380, 120, (4, 10, 16), OUT, 6)
    s = lerp(1.25, 0.8, k)
    kick = math.sin(t * 10)
    py = lerp(1250, 700, k)
    stroke = math.sin(t * 7)
    person(pen, 540, py, s * 1.3, ang=6 * math.sin(t * 5), la=(150 + 30 * stroke, 30), ra=(-150 - 30 * stroke, -30),
           ll=(25 * kick, 20), rl=(-25 * kick, -20), silhouette=(8, 34, 44))
    bubble_column(pen, t, 540, py - 300 * s, n=16, height=800, rmax=16, wobble=24)
    return pen.finish()


def shot_surface(t, d, T):
    sl = 980
    bob = 18 * math.sin(t * 4)
    cam = (540, 980 + bob, 1.08 - 0.05 * t, lerp(-5, 2, t))
    pen = Pen(cam, NIGHT_TOP, (24, 50, 66))
    sky_city(pen, t, horizon=sl - 80)
    pen.rect(-600, 600, 1800, 660, (48, 56, 70), OUT, 6)
    railing(pen, 600, -600, 1800, gap=(300, 520))
    up = ease_out(clamp01((t - 0.15) / 0.5))
    py = lerp(1800, 1160, up)
    # underwater half
    pen.rect(-600, sl, 1800, 3000, (12, 84, 90, 255), None)
    pen.rect(-600, sl + 300, 1800, 3000, (4, 34, 44, 200), None)
    person(pen, 540, py, 2.0, la=(-120, -30), ra=(120, 30), ll=(15, 10), rl=(-15, -10),
           expr="gasp" if up > 0.5 else "determined", look=(0, -0.2), wet=True)
    pen.rect(-600, sl, 1800, 3000, (20, 120, 120, 90), None)
    pen.line(wave_line(-600, 1800, sl, 12, t, k=0.015, speed=3), (200, 255, 245), 9, cap=False)
    if up > 0.05:
        r = random.Random(3)
        for i in range(34):
            a = r.uniform(-math.pi * 0.95, -math.pi * 0.05)
            sp = r.uniform(300, 900)
            age = max(0.0, t - 0.25)
            x, y = 540 + math.cos(a) * sp * age, sl + math.sin(a) * sp * age + 1400 * age * age
            if y < sl + 10:
                pen.ell(x, y, 8 + 10 * r.random(), fill=(200, 255, 250, 220), ol=OUT, w=3, n=12)
        for k in range(3):
            rr = ((t - 0.25) * 500 + k * 120)
            if rr > 0:
                pen.ell(540, sl, rr, rr * 0.18, None, (220, 255, 250, max(0, int(200 - rr * 0.3))), 6)
    return pen.finish()


def bokeh(pen, t, seed=5, n=14):
    r = random.Random(seed)
    for i in range(n):
        x = r.uniform(-200, 1300) + 20 * math.sin(t + i)
        y = r.uniform(200, 1100)
        c = r.choice([(255, 210, 120), (120, 230, 220), (255, 160, 90)])
        rr = r.uniform(18, 55)
        pen.ell(x, y, rr, fill=rgba(c, 38), ol=rgba(c, 60), w=3)


def shot_breath(t, d, T):
    bob = 22 * math.sin(t * 3.5)
    cam = (540, 1000 + bob, 1.0 + 0.08 * t, 4 * math.sin(t * 2))
    pen = Pen(cam, NIGHT_TOP, (20, 46, 60))
    bokeh(pen, t)
    pen.rrect(250, 1150, 830, 1800, 180, SHIRT, OUT, 10)
    head(pen, 540, 900, 290, "gasp" if t < 0.55 else "relief", look=(0, 0), blink=1.0 if t > 0.6 else 0, wet=True)
    for i in range(3):
        a = t - 0.1 - i * 0.12
        if a > 0:
            pen.ell(540 + 60 * a + i * 30, 1060 - 260 * a, 50 + 120 * a, 40 + 80 * a,
                    (220, 235, 245, max(0, int(120 - a * 140))), None)
    r = random.Random(2)
    for i in range(10):
        x = 540 + r.uniform(-240, 240)
        y = 800 + r.uniform(-160, 240) + 120 * t * r.random()
        pen.ell(x, y, 7, 11, (200, 245, 255, 230), OUT, 3, n=12)
    wl = 1260
    pen.poly([tuple(p) for p in wave_line(-600, 1700, wl, 16, t, k=0.012, speed=3)] + [(1700, 3000), (-600, 3000)],
             (14, 96, 102, 235), None)
    pen.line(wave_line(-600, 1700, wl, 16, t, k=0.012, speed=3), (200, 255, 245), 9, cap=False)
    for k in range(4):
        rr = 320 + ((t * 200 + k * 110) % 440)
        pen.ell(540, wl + 10, rr, rr * 0.12, None, (190, 255, 240, int(160 * (1 - (rr - 320) / 440))), 5)
    return pen.finish()


# ================================================================ bonus: stuck window
def shot_stuck(t, d, T):
    cam = (540 + wob(t, 3, 10), 960 + wob(t, 4, 8, 2), 1.12, wob(t, 1.5, 3))
    pen = Pen(cam, INTERIOR_TOP, INTERIOR_BOT)
    x0, y0, x1, y1 = 60, 300, 1020, 1200
    wl = lerp(700, 560, t)
    pen.rrect(x0, y0, x1, y1, 70, (10, 20, 40), None)
    pen.poly([tuple(p) for p in wave_line(x0, x1, wl, 12, t, k=0.02, speed=3)] + [(x1, y1), (x0, y1)], (16, 96, 100), None)
    pen.line(wave_line(x0, x1, wl, 12, t, k=0.02, speed=3), (190, 255, 240), 6, cap=False)
    jit = 3 * math.sin(t * 60)
    pen.rect(x0 + 20, y0 + 10 + jit, x1 - 20, y1, rgba(GLASS, 150), OUT, 5)
    pen.line([(x0 + 120, y0 + 60), (x0 + 260, y0 + 220)], (230, 250, 255, 120), 14)
    pen.rrect(x0, y0, x1, y1, 70, None, (40, 44, 54), 30)
    pen.rect(-600, y1, 1700, 2600, (38, 42, 54), OUT, 8)
    presses = [0.12, 0.38, 0.62, 0.84]
    p = max([clamp01(1 - abs(t - x) / 0.08) for x in presses])
    flash = int(t * 8) % 2 == 0
    pen.rrect(560, 1420, 900, 1580, 34, (30, 32, 40), OUT, 7)
    pen.rrect(620, 1450 + 18 * p, 840, 1540 + 10 * p, 18, RED if flash else (90, 30, 34), OUT, 5)
    hand(pen, 600, 1560 + 18 * p, 1.1, ang=-35, curl=0.6)
    if flash:
        pen.rrect(560, 1420, 900, 1580, 34, None, rgba(RED, 220), 12)
    inside_water(pen, t, 1700 - 80 * t)
    return pen.finish()


def shot_hammer_grab(t, d, T):
    k = ease_io(t / d)
    cam = (lerp(380, 700, k), lerp(1060, 940, k), 1.1 + 0.15 * k, lerp(10, -12, k))
    pen = Pen(cam, (42, 46, 58), (16, 18, 24))
    pen.rect(-600, -600, 1800, 2700, (40, 44, 56), None)
    for yy in (700, 1460):
        pen.line([(-600, yy), (1800, yy)], (58, 64, 78), 8, cap=False)
    pen.rrect(160, 880, 460, 1240, 30, (28, 30, 38), OUT, 7)
    grab = clamp01((t - 0.2) / 0.15)
    swing = ease_in(clamp01((t - 0.4) / 0.55))
    hx = lerp(310, 760, swing)
    hy = lerp(1060, 820, swing)
    ha = lerp(-90, -200, swing)
    if swing > 0.05:
        for i in range(4):
            pen.arc(560, 1180, 420 + i * 40, -110, -150 + 40 * (1 - swing), (255, 255, 255, int(130 * swing)), 10)
    hammer(pen, hx, hy, 1.2, ha)
    hand(pen, lerp(-80, hx, grab), lerp(1500, hy + 60, grab), 1.15, ang=lerp(-40, ha + 90, grab), curl=0.3 + 0.7 * grab)
    return pen.finish()


CRACKS = None


def crack_paths():
    global CRACKS
    if CRACKS is None:
        r = random.Random(17)
        CRACKS = []
        for i in range(14):
            a = math.radians(180 + i * (90 / 13)) + r.uniform(-0.05, 0.05)
            pts = [(0.0, 0.0)]
            L = 0
            while L < 1400:
                L += r.uniform(80, 160)
                aa = a + r.uniform(-0.25, 0.25)
                pts.append((math.cos(aa) * L, math.sin(aa) * L))
            CRACKS.append(pts)
    return CRACKS


def shot_corner(t, d, T):
    hit = 0.32
    sh = 26 * math.exp(-max(0, t - hit) * 6) if t > hit else 0
    cam = (620 + wob(t, 8, sh), 1000 + wob(t, 7, sh, 1), lerp(1.0, 1.12, t / d), lerp(-6, -2, t / d))
    pen = Pen(cam, (10, 20, 40), (12, 70, 80))
    pen.poly([tuple(p) for p in wave_line(-600, 1800, 1050, 16, t, k=0.015, speed=3)] + [(1800, 3000), (-600, 3000)],
             (16, 96, 100), None)
    cx, cy = 900, 1500
    pen.rect(-600, 200, cx, cy, rgba(GLASS, 140), None)
    pen.line([(-200, 500), (100, 900)], (230, 250, 255, 110), 20)
    pen.rect(cx, -600, 1800, 2700, (40, 44, 54), OUT, 8)
    pen.rect(-600, cy, cx, 2700, (40, 44, 54), OUT, 8)
    if t > hit:
        g = ease_out(clamp01((t - hit) / 0.35))
        for path in crack_paths():
            n = max(2, int(len(path) * g))
            pts = [(cx - 40 + x, cy - 40 + y) for x, y in path[:n]]
            pen.line(pts, (240, 250, 255, 230), 6)
        for rr in (60, 140, 240):
            if rr < 300 * g:
                pen.arc(cx - 40, cy - 40, rr, 180, 270, (240, 250, 255, 200), 5)
    else:
        pr = 120 + 20 * math.sin(t * 30)
        pen.ell(cx - 40, cy - 40, pr, None, RED, 10)
        pen.line([(cx - 40 - pr - 40, cy - 40), (cx - 40 - pr + 40, cy - 40)], RED, 10)
        pen.line([(cx - 40, cy - 40 - pr - 40), (cx - 40, cy - 40 - pr + 40)], RED, 10)
    k = ease_in(clamp01(t / hit))
    back = clamp01((t - hit) / 0.3)
    ha = lerp(-160, -135, k) - 20 * back
    hx = lerp(500, cx + 40, k) - 120 * back
    hy = lerp(900, cy - 40, k) - 120 * back
    hammer(pen, hx, hy, 1.3, ha + 180)
    hand(pen, hx - 300 * math.cos(math.radians(ha + 180)) * 0.95, hy - 300 * math.sin(math.radians(ha + 180)) * 0.95,
         1.2, ang=ha + 180, curl=1.0)
    if abs(t - hit) < 0.06:
        pen.ell(cx - 40, cy - 40, 260, fill=(255, 255, 255, 200), ol=None)
    return pen.finish()


SHARDS = None


def shards():
    global SHARDS
    if SHARDS is None:
        r = random.Random(23)
        SHARDS = []
        for i in range(46):
            x, y = r.uniform(-500, 900), r.uniform(200, 1500)
            pts = [(r.uniform(-60, 60), r.uniform(-60, 60)) for _ in range(3)]
            SHARDS.append((x, y, pts, r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-300, 300), r.uniform(0.5, 2.2)))
    return SHARDS


def shot_shatter(t, d, T):
    cam = (540, 960, 1.0 + 0.1 * t, lerp(-3, 5, t))
    pen = Pen(cam, (6, 14, 30), (12, 64, 76))
    pen.ell(820, 400, 60, fill=(230, 235, 210), ol=None)
    pen.poly([tuple(p) for p in wave_line(-600, 1800, 1150, 16, t, k=0.015, speed=2)] + [(1800, 3000), (-600, 3000)],
             (14, 90, 96), None)
    pen.line(wave_line(-600, 1800, 1150, 16, t, k=0.015, speed=2), (190, 255, 240), 7, cap=False)
    ts = t * 0.45 + 0.05
    for (x, y, pts, vx, vy, rot, sc) in shards():
        dx, dy = x - 900, y - 1500
        s = sc * (1 + ts * 2.2)
        px = 540 + (x - 540) * (1 + ts * 1.6) + vx * 160 * ts + dx * 0.2 * ts
        py = 960 + (y - 960) * (1 + ts * 1.6) + vy * 160 * ts + dy * 0.2 * ts
        pen.push(px, py, rot * ts, s)
        pen.poly(pts, (170, 220, 240, 150), (240, 252, 255), 3)
        pen.line([pts[0], pts[1]], (255, 255, 255), 3)
        pen.pop()
        if math.sin(t * 20 + x) > 0.85:
            pen.ell(px, py, 10 * s, fill=(255, 255, 255, 230), ol=None, n=8)
    return pen.finish()


# ================================================================ ending
def shot_portrait(t, d, T, tight=False):
    k = t / d
    if tight:
        cam = (540 + 10 * k, 800, lerp(1.18, 1.3, k), lerp(3, -2, k))
    else:
        cam = (540, 840, lerp(1.0, 1.08, k), lerp(-2, 1, k))
    bob = 10 * math.sin(T * 2.2)
    pen = Pen(cam, (6, 10, 24), (12, 40, 52))
    bokeh(pen, T * 0.6, seed=9, n=16)
    pen.rrect(200, 1220 + bob, 880, 2000, 220, SHIRT, OUT, 10)
    pen.line([(300, 1420 + bob), (780, 1420 + bob)], SHIRT_D, 8)
    blink = 1.0 if 27.15 < T < 27.27 or 29.1 < T < 29.2 else 0.0
    brow = 6 + 10 * clamp01((T - 27.6) / 0.4)
    head(pen, 540, 900 + bob, 300, "sly" if T > 28 else "neutral", look=(0, 0), blink=blink, brow=brow, wet=True)
    wl = 1540
    pen.poly([tuple(p) for p in wave_line(-600, 1700, wl, 14, T, k=0.012, speed=2)] + [(1700, 3000), (-600, 3000)],
             (12, 86, 94, 235), None)
    pen.line(wave_line(-600, 1700, wl, 14, T, k=0.012, speed=2), (190, 255, 240), 8, cap=False)
    return pen.finish()
