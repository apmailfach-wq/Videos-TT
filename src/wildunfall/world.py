"""Top-down night world: forest, country road, car, deer, person + a real-time light map."""
import math
import random
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ueberleben"))
from draw import Pen, SS, W, H, rgba, lerp, clamp01, ease_out, ease_in, ease_io  # noqa: E402,F401

OUTL = (10, 12, 16)
GROUND = (34, 52, 38)
CAR = (150, 166, 182)
CAR_D = (104, 118, 134)
CAR_L = (205, 218, 230)
SHIRT = (255, 196, 52)
HAIR = (70, 44, 30)
DEER = (156, 102, 60)
DEER_D = (112, 70, 40)
VEST = (210, 255, 60)

ROAD_L, ROAD_R = 280, 800
LANE_R = 670


# ------------------------------------------------------------------ forest
def _tile_trees(ty):
    r = random.Random(ty * 7919 + 13)
    out = []
    for side in (-1, 1):
        for _ in range(9):
            rad = r.uniform(80, 165)
            if side < 0:
                x = r.uniform(-900, ROAD_L - 70 - rad * 0.2)
            else:
                x = r.uniform(ROAD_R + 70 + rad * 0.2, 1980)
            y = ty * 500 + r.uniform(0, 500)
            kind = r.choices(["pine", "oak", "birch"], [0.45, 0.4, 0.15])[0]
            out.append((x, y, rad, kind, r.random()))
    return out


CRASH_TREE = (1010, -3745, 150, "oak", 0.4)


def _keep(t):
    x, y = t[0], t[1]
    if abs(x - CRASH_TREE[0]) < 230 and abs(y - CRASH_TREE[1]) < 230:
        return False
    if abs(x - 1120) < 160 and -3330 < y < -2980:  # clearing where the deer gather at the end
        return False
    if x < ROAD_L and abs(y + 3080) < 110 and x > -60:  # deer path out of the forest
        return False
    return True


@lru_cache(maxsize=64)
def tiles(ty):
    t = [x for x in _tile_trees(ty) if _keep(x)]
    if ty == -8:
        t.append(CRASH_TREE)
    return tuple(t)


PALETTE = {
    "pine": [(22, 58, 46), (30, 76, 58), (52, 104, 78)],
    "oak": [(110, 58, 26), (156, 88, 34), (206, 136, 58)],
    "oak2": [(78, 70, 30), (118, 104, 40), (170, 152, 70)],
    "birch": [(120, 96, 30), (176, 140, 40), (226, 196, 84)],
}


def lumpy(cx, cy, r, seed, n=26, amp=0.12):
    rr = random.Random(seed)
    ph = [rr.uniform(0, 6.28) for _ in range(3)]
    pts = []
    for i in range(n):
        a = i / n * 2 * math.pi
        k = 1 + amp * (math.sin(a * 5 + ph[0]) * 0.6 + math.sin(a * 3 + ph[1]) * 0.4 + math.sin(a * 7 + ph[2]) * 0.3)
        pts.append((cx + math.cos(a) * r * k, cy + math.sin(a) * r * k))
    return pts


def draw_tree_shadow(pen, t):
    x, y, r, kind, s = t
    pen.ell(x + r * 0.35, y + r * 0.45, r * 1.02, fill=(0, 0, 0, 95), ol=None, n=30)


def draw_tree(pen, t, sway=0.0):
    x, y, r, kind, s = t
    if kind == "oak" and s > 0.55:
        kind = "oak2"
    c0, c1, c2 = PALETTE[kind]
    dx = sway * r * 0.04
    seed = int(x * 31 + y * 17)
    if kind == "pine":
        for k, (rad, col) in enumerate(((r, c0), (r * 0.72, c1), (r * 0.42, c2))):
            pts = []
            n = 20
            for i in range(n * 2):
                a = i / (n * 2) * 2 * math.pi + s
                rr = rad * (1.0 if i % 2 == 0 else 0.86)
                pts.append((x + dx * k + math.cos(a) * rr - k * r * 0.06, y + math.sin(a) * rr - k * r * 0.08))
            pen.poly(pts, col, OUTL, 4)
        pen.ell(x - r * 0.12, y - r * 0.14, r * 0.12, fill=c2, ol=None, n=10)
    else:
        pen.poly(lumpy(x, y, r, seed), c0, OUTL, 5)
        pen.poly(lumpy(x - r * 0.1 + dx, y - r * 0.12, r * 0.74, seed + 1), c1, None)
        pen.poly(lumpy(x - r * 0.26 + dx, y - r * 0.3, r * 0.4, seed + 2), c2, None)
        rr = random.Random(seed)
        for _ in range(5):
            a = rr.uniform(0, 6.28)
            d = rr.uniform(0.2, 0.75) * r
            pen.ell(x + math.cos(a) * d, y + math.sin(a) * d, r * 0.13, fill=rgba(c2, 150), ol=None, n=10)


def ground_detail(pen, y0, y1):
    for ty in range(int(math.floor(y0 / 300)), int(math.ceil(y1 / 300)) + 1):
        r = random.Random(ty * 104729 + 3)
        for _ in range(14):
            x = r.uniform(-900, 1980)
            if ROAD_L - 40 < x < ROAD_R + 40:
                continue
            y = ty * 300 + r.uniform(0, 300)
            c = r.choice([(70, 52, 30, 70), (20, 34, 24, 90), (90, 70, 34, 60), (40, 66, 44, 80)])
            pen.ell(x, y, r.uniform(40, 120), r.uniform(25, 70), fill=c, ol=None, ang=r.uniform(0, 180), n=16)
        for _ in range(10):  # fallen leaves on the verge
            side = r.choice((-1, 1))
            x = (ROAD_L - r.uniform(5, 60)) if side < 0 else (ROAD_R + r.uniform(5, 60))
            y = ty * 300 + r.uniform(0, 300)
            pen.ell(x, y, 8, 5, fill=r.choice([(190, 110, 40), (160, 80, 30), (200, 150, 60)]), ol=None,
                    ang=r.uniform(0, 180), n=8)


def road(pen, y0, y1, skids=()):
    pen.rect(ROAD_L - 40, y0, ROAD_L, y1, (74, 70, 62), None)
    pen.rect(ROAD_R, y0, ROAD_R + 40, y1, (74, 70, 62), None)
    pen.rect(ROAD_L, y0, ROAD_R, y1, (46, 48, 54), None)
    for ty in range(int(math.floor(y0 / 240)), int(math.ceil(y1 / 240)) + 1):
        r = random.Random(ty * 7 + 1)
        for _ in range(22):
            pen.ell(r.uniform(ROAD_L + 6, ROAD_R - 6), ty * 240 + r.uniform(0, 240), r.uniform(2, 6),
                    fill=(90, 92, 98, 70) if r.random() < 0.6 else (24, 26, 30, 90), ol=None, n=6)
        # tyre polish in both lanes
    for lx in (410, 670):
        pen.rect(lx - 70, y0, lx - 40, y1, (40, 42, 48, 120), None)
        pen.rect(lx + 40, y0, lx + 70, y1, (40, 42, 48, 120), None)
    for (x, ya, yb) in skids:
        pen.line([(x, ya), (x, yb)], (16, 16, 18, 190), 16, cap=False)
    pen.rect(ROAD_L + 14, y0, ROAD_L + 26, y1, (226, 226, 214), None)
    pen.rect(ROAD_R - 26, y0, ROAD_R - 14, y1, (226, 226, 214), None)
    k0 = int(math.floor(y0 / 240))
    for k in range(k0, int(math.ceil(y1 / 240)) + 1):
        pen.rect(534, k * 240, 546, k * 240 + 110, (226, 226, 214), None)


def posts(y0, y1):
    out = []
    for k in range(int(math.floor(y0 / 330)), int(math.ceil(y1 / 330)) + 1):
        out.append((ROAD_L - 70, k * 330 + 40, -1))
        out.append((ROAD_R + 70, k * 330 + 200, 1))
    return out


def draw_posts(pen, ps):
    for x, y, side in ps:
        pen.ell(x + 6, y + 8, 12, fill=(0, 0, 0, 90), ol=None, n=10)
        pen.rrect(x - 9, y - 9, x + 9, y + 9, 4, (236, 236, 230), OUTL, 3)
        pen.rect(x - 9, y - 3, x + 9, y + 3, (20, 20, 22), None)


# ------------------------------------------------------------------ car
def car(pen, x, y, h, steer=0.0, damage=0.0, driver=True, door=0.0):
    pen.push(x, y, h)
    pen.rrect(-56, -112, 70, 136, 44, (0, 0, 0, 110), None)
    for wx, wy, a in ((-58, -72, steer), (58, -72, steer), (-58, 74, 0), (58, 74, 0)):
        pen.push(wx, wy, a)
        pen.rrect(-11, -22, 11, 22, 6, (18, 18, 20), OUTL, 3)
        pen.pop()
    body = CAR
    pen.rrect(-58, -120, 58, 120, 44, body, OUTL, 7)
    if damage > 0:
        d = 26 * damage
        pen.poly([(-58, -96), (-30, -120 + d), (0, -112 + d * 1.3), (30, -120 + d * 0.8), (58, -94), (58, -70),
                  (-58, -70)], CAR_D, OUTL, 5)
    pen.rrect(-50, -114, 50, -62, 26, CAR_L, None)
    pen.line([(-24, -110), (-30, -64)], CAR_D, 3)
    pen.line([(24, -110), (30, -64)], CAR_D, 3)
    pen.poly([(-48, -58), (48, -58), (44, -24), (-44, -24)], (20, 32, 46), OUTL, 4)
    pen.line([(-30, -54), (-12, -28)], (190, 220, 240, 150), 4)
    pen.rrect(-46, -24, 46, 56, 12, (20, 24, 32), None)
    if driver:
        pen.ell(26, 4, 22, 26, (54, 46, 56), None)
        pen.ell(-24, 6, 26, 18, SHIRT, OUTL, 3)
        pen.line([(-42, 2), (-34, -18)], SHIRT, 9)
        pen.line([(-6, 2), (-14, -18)], SHIRT, 9)
        pen.ell(-24, -24, 16, 5, None, (30, 30, 34), 4)
        pen.ell(-24, 0, 14, fill=HAIR, ol=OUTL, w=3)
        pen.ell(-28, -4, 4, fill=(110, 76, 52), ol=None, n=8)
    pen.rrect(-46, -24, 46, 56, 12, (150, 190, 220, 50), OUTL, 4)
    pen.line([(-46, 16), (46, 16)], (90, 104, 120, 140), 4)
    pen.poly([(-44, 58), (44, 58), (48, 84), (-48, 84)], (20, 32, 46), OUTL, 4)
    pen.line([(-40, 100), (40, 100)], CAR_D, 3)
    for sx in (-1, 1):
        pen.ell(sx * 64, -44 + 4, 9, 6, CAR_D, OUTL, 3)
        pen.ell(sx * 36, -114, 14, 6, (230, 228, 210), OUTL, 2)
        pen.rrect(sx * 40 - 12, 113, sx * 40 + 12, 121, 3, (150, 20, 24), OUTL, 2)
    if door > 0:
        pen.push(-58, -30, -50 * door)
        pen.rect(-8, 0, 2, 70, CAR_D, OUTL, 3)
        pen.pop()
    if damage > 0.3:
        for a in (200, 230, 260, 300, 330):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            pen.line([(10, -40), (10 + ca * 40, -40 + sa * 18)], (230, 240, 250, 200), 2)
    pen.pop()


def car_emissive(pen, x, y, h, high=True, brake=0.0, hazard=0.0, lit=1.0):
    pen.push(x, y, h)
    for sx in (-1, 1):
        pen.ell(sx * 36, -116, 15, 7, (255, 250, 220, int(255 * lit)), None)
        tr = 0.45 + 0.55 * brake
        pen.rrect(sx * 40 - 13, 112, sx * 40 + 13, 122, 3, (255, 60, 60, int(255 * tr)), None)
        if hazard > 0:
            for (hx, hy) in ((sx * 54, -108), (sx * 54, 112)):
                pen.ell(hx, hy, 11, fill=(255, 170, 40, int(255 * hazard)), ol=None, n=12)
    pen.pop()


# ------------------------------------------------------------------ deer
def deer(pen, x, y, h, phase=0.0, moving=0.0, head=0.0, scale=1.0, lift=0.0):
    pen.push(x + lift * 30, y + lift * 40, h, scale)
    pen.ell(6, 14, 40, 86, (0, 0, 0, int(110 * (1 - lift * 0.5))), None)
    pen.pop()
    pen.push(x, y, h, scale * (1 + 0.14 * lift))
    for (lx, ly, ph) in ((-22, -34, 0), (22, -34, math.pi), (-22, 44, math.pi), (22, 44, 0)):
        sw = math.sin(phase + ph) * moving
        ex = lx + (16 if lx > 0 else -16)
        pen.line([(lx * 0.8, ly), (ex, ly + 30 * sw + 6)], (70, 44, 28), 8)
        pen.ell(ex, ly + 30 * sw + 6, 5, fill=(30, 22, 18), ol=None, n=8)
    pen.ell(0, 34, 30, 34, DEER, OUTL, 5)
    pen.ell(0, -24, 26, 32, DEER, OUTL, 5)
    pen.ell(0, 6, 23, 42, DEER, None)
    pen.crescent(0, 34, 30, 34, -9, -4, -60, 100, rgba(DEER_D, 160))
    pen.crescent(0, -24, 26, 32, -8, -4, -60, 100, rgba(DEER_D, 160))
    pen.ell(-10, -26, 9, 14, (196, 140, 92), None)
    pen.ell(-10, 30, 10, 14, (196, 140, 92), None)
    pen.ell(0, 62, 11, 8, (240, 226, 206), None)
    pen.ell(0, 69, 4, 5, (40, 30, 24), None)
    pen.push(0, -50, head)
    pen.ell(0, -12, 13, 24, DEER, OUTL, 4)
    pen.ell(0, -40, 18, 23, DEER, OUTL, 4)
    pen.ell(-5, -42, 7, 14, (186, 128, 80), None)
    pen.ell(0, -62, 9, 9, (54, 36, 28), OUTL, 3)
    for sx in (-1, 1):
        pen.ell(sx * 24, -32, 17, 9, DEER_D, OUTL, 3, ang=sx * 30)
        pen.ell(sx * 22, -32, 9, 4.5, (226, 190, 170), None, ang=sx * 30)
        pen.ell(sx * 12, -48, 4.5, fill=(10, 10, 10), ol=None, n=8)
    pen.pop()
    pen.pop()


def deer_eyes(pen, x, y, h, head=0.0, scale=1.0, glow=1.0, lift=0.0):
    if glow < 0.03:
        return
    pen.push(x, y, h, scale * (1 + 0.14 * lift))
    pen.push(0, -50, head)
    for sx in (-1, 1):
        pen.ell(sx * 12, -48, 7, fill=(220, 255, 210, int(255 * glow)), ol=None, n=10)
    pen.pop()
    pen.pop()


# ------------------------------------------------------------------ person (top-down) + triangle
def person_top(pen, x, y, h, phase=0.0, walking=0.0, phone=False):
    pen.push(x, y, h)
    pen.ell(8, 10, 34, 22, (0, 0, 0, 100), None)
    sw = math.sin(phase) * walking
    for sx in (-1, 1):
        pen.line([(sx * 26, 0), (sx * 30, -16 * sw * sx)], VEST if not phone else VEST, 11)
    pen.ell(0, 0, 32, 18, VEST, OUTL, 4)
    pen.line([(-28, -4), (28, -4)], (210, 214, 220), 5)
    pen.ell(0, 0, 14, fill=HAIR, ol=OUTL, w=3)
    if phone:
        pen.rrect(24, -26, 36, -8, 3, (20, 20, 24), OUTL, 2)
    pen.pop()


def triangle(pen, x, y, s=1.0):
    pen.push(x, y, 0, s)
    pen.poly([(0, -34), (32, 22), (-32, 22)], (230, 40, 40), OUTL, 4)
    pen.poly([(0, -16), (16, 12), (-16, 12)], (240, 240, 236), None)
    pen.pop()


# ------------------------------------------------------------------ light map
LW, LH = W // 4, H // 4
_YY, _XX = np.mgrid[0:LH, 0:LW].astype(np.float32)
_XX = _XX * 4 + 2
_YY = _YY * 4 + 2


def to_screen(M, x, y):
    return M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2]


def light_map(M, z, cars=(), points=(), ambient=(0.34, 0.38, 0.54)):
    """cars: (x, y, h, high, brake, hazard). points: (x, y, radius_world, rgb, intensity). Returns HxW float RGB."""
    L = np.empty((LH, LW, 3), np.float32)
    L[:] = ambient
    for (x, y, h, high, brake, hazard, on) in cars:
        a = math.radians(h)
        fx, fy = math.sin(a), -math.cos(a)
        sfx, sfy = to_screen(M, x + fx, y + fy)
        cx, cy = to_screen(M, x, y)
        dfx, dfy = sfx - cx, sfy - cy
        n = math.hypot(dfx, dfy) or 1
        dfx, dfy = dfx / n, dfy / n
        rx, ry = -dfy, dfx
        if on > 0:
            px, py = cx + dfx * 112 * z, cy + dfy * 112 * z
            u = (_XX - px) * dfx + (_YY - py) * dfy
            v = (_XX - px) * rx + (_YY - py) * ry
            rng = lerp(820, 1500, high) * z
            wdt = (0.22 + 0.05 * high) * np.maximum(u, 0) + 50 * z
            cone = np.exp(-(v / wdt) ** 2 * 1.6) * np.clip(1 - u / rng, 0, 1) ** 1.3 * (u > -10)
            cone *= np.clip((u + 10 * z) / (60 * z), 0, 1)
            near = np.exp(-(((_XX - cx) ** 2 + (_YY - cy) ** 2) / (190 * z) ** 2))
            I = (cone * 2.3 + near * 0.25) * on
            L += I[..., None] * np.array([1.0, 0.9, 0.68], np.float32)
        for sx in (-1, 1):
            tx, ty = to_screen(M, x - fx * 165 + math.cos(a) * sx * 40, y - fy * 165 + math.sin(a) * sx * 40)
            rr = (60 + 80 * brake) * z
            d2 = ((_XX - tx) ** 2 + (_YY - ty) ** 2) / rr ** 2
            L += (np.exp(-d2) * (0.25 + 0.55 * brake))[..., None] * np.array([0.9, 0.08, 0.06], np.float32)
        if hazard > 0:
            for (ox, oy) in ((-54, -108), (54, -108), (-54, 112), (54, 112)):
                hx = x + math.cos(a) * ox - math.sin(a) * oy
                hy = y + math.sin(a) * ox + math.cos(a) * oy
                tx, ty = to_screen(M, hx, hy)
                d2 = ((_XX - tx) ** 2 + (_YY - ty) ** 2) / (190 * z) ** 2
                L += (np.exp(-d2) * hazard * 1.1)[..., None] * np.array([1.0, 0.55, 0.1], np.float32)
    for (x, y, rad, col, inten) in points:
        tx, ty = to_screen(M, x, y)
        d2 = ((_XX - tx) ** 2 + (_YY - ty) ** 2) / (rad * z) ** 2
        L += (np.exp(-d2) * inten)[..., None] * np.array(col, np.float32)
    return L


def sample_light(L, M, x, y):
    tx, ty = to_screen(M, x, y)
    i, j = int(ty / 4), int(tx / 4)
    if 0 <= i < LH and 0 <= j < LW:
        return float(L[i, j].mean())
    return 0.3


def apply_light(scene_rgb, L):
    L = 2.1 * np.tanh(L / 2.1)
    big = Image.fromarray(np.clip(L * 100, 0, 255).astype(np.uint8), "RGB").resize((W, H), Image.BILINEAR)
    a = np.asarray(scene_rgb, np.float32) * (np.asarray(big, np.float32) / 100.0)
    return np.clip(a, 0, 255).astype(np.uint8)
