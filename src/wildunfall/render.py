"""'Überlebst du das?' Folge 3 – Wildunfall. Top-down night look, voiceover + word captions.

python3 tts.py                  # voice -> build/wildunfall/
python3 render.py               # -> ../../wildunfall-folge3.mp4
python3 render.py preview 3 9   # stills -> build/wildunfall/stills
"""
import json
import math
import os
import random
import subprocess
import sys
import wave
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from scipy.interpolate import PchipInterpolator

import world as WD
from world import Pen, W, H, SS, lerp, clamp01, ease_out, ease_in, ease_io

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "wildunfall"
OUTFILE = ROOT / os.environ.get("VIDEO_OUT", "wildunfall-folge3.mp4")
FPS = 30
F_BLACK = str(ROOT / "fonts" / "Nunito_900Black.ttf")
F_XB = str(ROOT / "fonts" / "Nunito_800ExtraBold.ttf")
F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

VOICE = json.loads((BUILD / "voice.json").read_text())
LINES = {l["key"]: l for l in VOICE["lines"]}
TOTAL = round(VOICE["total"] * FPS) / FPS
NFRAMES = int(round(TOTAL * FPS))

WHITE = (255, 255, 255)
YELLOW = (255, 206, 40)
RED = (255, 72, 72)
CYAN = (70, 220, 255)
ORANGE = (255, 160, 40)
GREEN = (90, 230, 120)
NAVY = (14, 24, 44)


def W_(key, word, occ=0):
    """global time of a word inside a line"""
    l = LINES[key]
    n = 0
    for w in l["words"]:
        if w["w"].lower().startswith(word.lower()):
            if n == occ:
                return l["start"] + w["s"]
            n += 1
    raise KeyError((key, word))


def ST(key):
    return LINES[key]["start"]


def EN(key):
    return LINES[key]["end"]


# ================================================================== motion
A_KEYS = [(0.0, 670, 0, 0), (2.6, 670, -1690, 0), (3.5, 670, -2275, 0), (5.6, 670, -2560, 0), (7.3, 670, -2770, 0),
          (8.0, 610, -2890, -18), (8.8, 470, -3060, -32), (10.4, 440, -3105, -30), (11.2, 470, -3290, 40),
          (12.0, 610, -3460, 150), (12.7, 770, -3580, 290), (13.2, 875, -3650, 410), (13.6, 888, -3660, 416),
          (40.0, 888, -3660, 416)]
_AT = np.array([k[0] for k in A_KEYS])
AX = PchipInterpolator(_AT, [k[1] for k in A_KEYS])
AY = PchipInterpolator(_AT, [k[2] for k in A_KEYS])
AH = PchipInterpolator(_AT, [k[3] for k in A_KEYS])
T_IMPACT = 13.2
T_RW0, T_RW1 = 14.9, 16.5
B_START, B_Y0, B_V = 16.5, -1575.0, 200.0
T_BRAKE = W_("bremse", "Voll") + 0.15
T_STOP = T_BRAKE + 4.75
Y_BRAKE = B_Y0 - B_V * (T_BRAKE - B_START)
Y_STOP = Y_BRAKE - B_V * (T_STOP - T_BRAKE) / 2


def rewind_time(T):
    return T_RW0 - ease_io((T - T_RW0) / (T_RW1 - T_RW0)) * (T_RW0 - 2.42)


def a_state(Ta):
    h = float(AH(Ta))
    steer = float(np.clip((AH(Ta + 0.05) - AH(Ta - 0.05)) * 1.2, -32, 32))
    return dict(x=float(AX(Ta)), y=float(AY(Ta)), h=h, steer=steer, brake=0.0, high=1.0, hazard=0.0,
                damage=clamp01((Ta - T_IMPACT) / 0.15), on=1.0 if Ta < T_IMPACT else 0.55, door=0.0, run="A", ta=Ta)


def b_y(T):
    if T < T_BRAKE:
        return B_Y0 - B_V * (T - B_START)
    if T < T_STOP:
        tau = T - T_BRAKE
        a = B_V / (T_STOP - T_BRAKE)
        return Y_BRAKE - (B_V * tau - 0.5 * a * tau * tau)
    return Y_STOP


def car_state(T):
    if T < T_RW0:
        return a_state(T)
    if T < T_RW1:
        return a_state(rewind_time(T))
    t_abl = W_("bremse", "abblenden")
    t_haz = W_("danach", "Warnblinker")
    haz = 0.0
    if T >= t_haz:
        haz = 1.0 if ((T - t_haz) % 0.72) < 0.36 else 0.0
    door = clamp01((T - (W_("danach", "Warnweste") - 0.25)) / 0.3)
    return dict(x=670.0, y=b_y(T), h=0.0, steer=0.0, brake=1.0 if T_BRAKE <= T < T_STOP + 0.3 else (0.5 if T >= T_STOP else 0.0),
                high=1 - clamp01((T - t_abl) / 0.3), hazard=haz, damage=0.0, on=1.0, door=door, run="B", ta=T)


def walk(t, t0, t1, p0, p1):
    k = clamp01((t - t0) / (t1 - t0))
    return lerp(p0[0], p1[0], k), lerp(p0[1], p1[1], k), k


def deer_states(T):
    """list of dicts (x, y, h, phase, moving, head, scale, lift, glow_base)"""
    out = []
    if T < T_RW1:
        Ta = T if T < T_RW0 else rewind_time(T)
        if Ta < 2.6:
            out.append(dict(x=130, y=-3080, h=90, phase=0, moving=0, head=0, scale=1, lift=0, gb=0))
        elif Ta < 3.5:
            x, y, k = walk(Ta, 2.6, 3.5, (130, -3080), (650, -3080))
            out.append(dict(x=x, y=y, h=90, phase=Ta * 16, moving=1, head=0, scale=1, lift=0, gb=0))
        elif Ta < 10.5:
            out.append(dict(x=650, y=-3080, h=90, phase=0, moving=0, head=65 * ease_out((Ta - 3.5) / 0.4), scale=1,
                            lift=0, gb=0))
        else:
            x, y, k = walk(Ta, 10.5, 11.6, (650, -3080), (1250, -3050))
            out.append(dict(x=x, y=y, h=95, phase=Ta * 18, moving=1, head=0, scale=1, lift=abs(math.sin(k * math.pi * 3)),
                            gb=0))
        return out
    t_jump = W_("mehr", "springt")
    if T < B_START + 0.9:
        x, y, k = walk(T, B_START, B_START + 0.9, (130, -3080), (650, -3080))
        out.append(dict(x=x, y=y, h=90, phase=T * 16, moving=1, head=0, scale=1, lift=0, gb=0))
    elif T < t_jump:
        out.append(dict(x=650, y=-3080, h=90, phase=0, moving=0, head=65 * ease_out((T - B_START - 1.0) / 0.4), scale=1,
                        lift=0, gb=0))
    else:
        x, y, k = walk(T, t_jump, t_jump + 0.9, (650, -3080), (1120, -3160))
        head = 0 if k < 1 else 100 * ease_io((T - t_jump - 1.2) / 0.6)
        out.append(dict(x=x, y=y, h=90 - 10 * k, phase=T * 18, moving=1 - k * (k >= 1), head=head, scale=1,
                        lift=abs(math.sin(k * math.pi * 2)) * (k < 1), gb=0.5 * (k >= 1)))
    t_more = W_("mehr", "Oft")
    for (dt, y0, end, sc) in ((0.0, -3110, (1210, -3250), 0.95), (0.45, -3190, (1060, -3310), 0.72)):
        a = t_more + dt
        if T < a:
            out.append(dict(x=-160, y=y0, h=90, phase=0, moving=0, head=0, scale=sc, lift=0, gb=0))
            continue
        x, y, k = walk(T, a, a + 1.35, (-160, y0), end)
        head = 0 if k < 1 else 110 * ease_io((T - a - 1.6) / 0.6)
        out.append(dict(x=x, y=y, h=90 - 8 * k, phase=T * 17, moving=1 if k < 1 else 0, head=head, scale=sc,
                        lift=abs(math.sin(k * math.pi * 3)) * (k < 1), gb=0.5 * (k >= 1)))
    return out


def person_state(T):
    t0 = W_("danach", "Warnweste")
    t_tri = W_("danach", "Warndreieck")
    t_pol = W_("danach", "Polizei")
    if T < t0 or T < B_START:
        return None
    cy = Y_STOP
    p_door = (585, cy - 20)
    p_back = (590, cy + 480)
    p_mid = (560, cy + 230)
    if T < t_tri:
        x, y, k = walk(T, t0, t_tri, p_door, p_back)
        return dict(x=x, y=y, h=180, phase=T * 10, walking=1, phone=False)
    if T < t_tri + 0.35:
        return dict(x=p_back[0], y=p_back[1], h=180, phase=0, walking=0, phone=False)
    if T < t_pol:
        x, y, k = walk(T, t_tri + 0.35, t_pol, p_back, p_mid)
        return dict(x=x, y=y, h=0, phase=T * 10, walking=1 if k < 1 else 0, phone=False)
    return dict(x=p_mid[0], y=p_mid[1], h=-20, phase=0, walking=0, phone=True)


# ================================================================== camera
def seg_target(mode, p, T, car, deers):
    d0 = deers[0] if deers else dict(x=650, y=-3080)
    if mode == "follow":
        z = p.get("z", 1.0) * ZK
        return car["x"] * 0.4 + 540 * 0.6, car["y"] + 60 / z + p.get("off", 0), z
    if mode == "car":
        z = p.get("z", 1.0) * ZK
        return car["x"], car["y"] + p.get("off", 0), z
    if mode == "deer":
        return d0["x"], d0["y"] + 60, p.get("z", 1.7)
    if mode == "frame":
        dy = abs(car["y"] - d0["y"])
        z = float(np.clip(1000 / (dy + 470), 0.68, 1.45))
        return (car["x"] + d0["x"]) / 2 * 0.55 + 540 * 0.45, (car["y"] + d0["y"]) / 2 + 30 / z, z
    return p["x"], p["y"], p["z"] * ZK


ZK = 1.22
SEGS = None


def build_segs():
    return [
        (0.0, "follow", dict(z=1.02, off=0)),
        (2.55, "frame", {}),
        (W_("reh", "Reh") - 0.05, "deer", dict(z=1.8)),
        (W_("reh", "Direkt") - 0.1, "frame", {}),
        (8.9, "car", dict(z=1.3, off=-130)),
        (10.45, "follow", dict(z=0.9, off=-60)),
        (13.15, "car", dict(z=1.25, off=-40)),
        (T_RW0, "follow", dict(z=1.0)),
        (B_START, "frame", {}),
        (W_("mehr", "springt") - 0.1, "point", dict(x=760, y=-3030, z=0.8)),
        (ST("knallt") + 0.3, "point", dict(x=660, y=-2870, z=0.64)),
        (ST("danach"), "car", dict(z=1.0, off=260)),
        (ST("merk"), "point", dict(x=650, y=-2830, z=0.68)),
        (ST("frage") - 0.1, "point", dict(x=1110, y=-3440, z=1.7)),
    ]


def camera(T, car, deers):
    global SEGS
    if SEGS is None:
        SEGS = build_segs()
    idx = 0
    for i, s in enumerate(SEGS):
        if T >= s[0]:
            idx = i
    t0, mode, p = SEGS[idx]
    x, y, z = seg_target(mode, p, T, car, deers)
    blend = 0.55 if mode != "deer" else 0.35
    if idx > 0 and T - t0 < blend:
        _, m2, p2 = SEGS[idx - 1]
        x2, y2, z2 = seg_target(m2, p2, T, car, deers)
        k = ease_io((T - t0) / blend)
        x, y, z = lerp(x2, x, k), lerp(y2, y, k), lerp(z2, z, k)
    rot = 2.2 * math.sin(T * 0.33) + 1.2 * math.sin(T * 0.71 + 1)
    if 8.9 <= T < 10.45:
        rot += 4 * ease_io((T - 8.9) / 0.5)
    sh = shake(T)
    if sh > 0:
        r = random.Random(int(T * FPS))
        x += r.uniform(-sh, sh) / z
        y += r.uniform(-sh, sh) / z
    return x, y, z, rot


def shake(T):
    a = 0.0
    for t0, amp, dur in ((T_IMPACT, 34, 0.7), (W_("reh", "Reh"), 6, 0.3), (W_("bremse", "Voll"), 5, 0.4)):
        if t0 <= T < t0 + dur:
            a = max(a, amp * (1 - (T - t0) / dur) ** 2)
    return a


# ================================================================== world render
def skid_marks(car):
    marks = []
    if car["run"] == "A":
        Ta = car["ta"]
        if Ta > 7.5:
            pts = {(-58, 74): [], (58, 74): []}
            for t in np.arange(7.5, min(Ta, T_IMPACT) + 1e-3, 0.04):
                x, y, h = float(AX(t)), float(AY(t)), math.radians(float(AH(t)))
                for (ox, oy), lst in pts.items():
                    lst.append((x + math.cos(h) * ox - math.sin(h) * oy, y + math.sin(h) * ox + math.cos(h) * oy))
            marks = [v for v in pts.values() if len(v) > 1]
    else:
        T = car["ta"]
        if T > T_BRAKE:
            yb = car["y"]
            marks = [[(x, Y_BRAKE + 74), (x, yb + 74)] for x in (612, 728)]
    return marks


def draw_world(cam, T, car, deers, person, emissive_only=False):
    pen = Pen(cam, WD.GROUND, WD.GROUND)
    cx, cy, z, rot = cam
    span = 1250 / z
    y0, y1 = cy - span, cy + span
    WD.ground_detail(pen, y0, y1)
    WD.road(pen, y0, y1)
    for m in skid_marks(car):
        pen.line(m, (14, 14, 16, 170), 15, cap=False)
    ps = WD.posts(y0, y1)
    WD.draw_posts(pen, ps)
    t_tri = W_("danach", "Warndreieck")
    if car["run"] == "B" and T >= t_tri:
        WD.triangle(pen, 640, Y_STOP + 520, ease_out((T - t_tri) / 0.25))
    for d in deers:
        WD.deer(pen, d["x"], d["y"], d["h"], d["phase"], d["moving"], d["head"], d["scale"], d["lift"])
    WD.car(pen, car["x"], car["y"], car["h"], car["steer"], car["damage"], door=car["door"])
    if person:
        WD.person_top(pen, person["x"], person["y"], person["h"], person["phase"], person["walking"], person["phone"])
    trees = []
    for ty in range(int(math.floor(y0 / 500)) - 1, int(math.ceil(y1 / 500)) + 1):
        trees.extend(WD.tiles(ty))
    for t in trees:
        WD.draw_tree_shadow(pen, t)
    sway_c = 0.0
    if car["run"] == "A" and car["ta"] > T_IMPACT:
        sway_c = math.sin((car["ta"] - T_IMPACT) * 18) * math.exp(-(car["ta"] - T_IMPACT) * 2.5) * 3
    for t in sorted(trees, key=lambda q: q[2]):
        WD.draw_tree(pen, t, sway=(sway_c if t == WD.CRASH_TREE else 0.3 * math.sin(T * 0.8 + t[0] * 0.01)))
    # crash debris: leaves + smoke
    if car["run"] == "A" and car["ta"] > T_IMPACT:
        age = car["ta"] - T_IMPACT
        r = random.Random(5)
        for i in range(46):
            a = r.uniform(0, 6.28)
            sp = r.uniform(60, 260)
            k = 1 - math.exp(-age * 1.5)
            lx = WD.CRASH_TREE[0] - 60 + math.cos(a) * sp * k + 30 * math.sin(age * 3 + i)
            ly = WD.CRASH_TREE[1] + 40 + math.sin(a) * sp * k + 60 * age
            pen.ell(lx, ly, 10, 6, fill=r.choice([(210, 120, 40), (170, 90, 30), (230, 170, 60)]), ol=(10, 12, 16),
                    w=2, ang=a * 57 + age * 200, n=8)
        for i in range(7):
            a2 = age - i * 0.12
            if a2 <= 0:
                continue
            rr = 30 + 90 * a2
            pen.ell(car["x"] + 70 + i * 6 + a2 * 40, car["y"] - 70 - a2 * 60, rr,
                    fill=(150, 150, 160, max(0, int(110 - a2 * 50))), ol=None, n=20)
    # drifting ground fog
    r = random.Random(9)
    for i in range(7):
        fx = r.uniform(-300, 1400) + 40 * math.sin(T * 0.2 + i)
        fy = cy + r.uniform(-span, span) + 30 * T % 400
        pen.ell(fx, fy, r.uniform(260, 480), r.uniform(120, 200), fill=(170, 190, 210, 12), ol=None, n=24)
    scene = pen.finish()
    M = pen.M.copy()
    return scene, M, ps


def draw_emissive(cam, T, car, deers, L, M, ps, person):
    pen = Pen(cam, img=Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0)))
    for x, y, side in ps:
        lv = WD.sample_light(L, M, x, y)
        a = clamp01((lv - 0.45) / 0.8)
        col = (255, 170, 40) if side > 0 else (240, 240, 240)
        if a > 0.02:
            pen.ell(x + 9 * side, y, 7, fill=col + (int(255 * a),), ol=None, n=10)
    WD.car_emissive(pen, car["x"], car["y"], car["h"], car["high"], car["brake"], car["hazard"], car["on"])
    for d in deers:
        lv = WD.sample_light(L, M, d["x"], d["y"])
        g = max(clamp01((lv - 0.45) / 0.4) * (1 if abs(d["head"]) > 20 else 0.4), d["gb"])
        if T > ST("frage") - 0.5:
            g = max(g, 0.9)
        WD.deer_eyes(pen, d["x"], d["y"], d["h"], d["head"], d["scale"], g, d["lift"])
    if car["run"] == "B" and T >= W_("danach", "Warndreieck"):
        lv = WD.sample_light(L, M, 640, Y_STOP + 520)
        pen.poly([(640, Y_STOP + 486), (672, Y_STOP + 542), (608, Y_STOP + 542)], None, (255, 80, 80, int(255 * clamp01(lv))),
                 3)
    # world-space UI: arrows + horn rings
    t_ger = W_("fest", "Geradeaus")
    if t_ger <= T < ST("bremse") + 0.2:
        k = ease_out((T - t_ger) / 0.3)
        bob = 14 * math.sin(T * 6)
        pen.arrow(car["x"], car["y"] - 160 - bob, car["x"], car["y"] - 160 - 230 * k - bob, 34, CYAN + (255,),
                  (10, 12, 16, 255), 6)
    t_aus = W_("instinkt", "ausweichen")
    if t_aus - 0.6 <= T < 8.9:
        k = ease_out((T - t_aus + 0.6) / 0.3)
        pts = [(car["x"] - 20, car["y"] - 160), (car["x"] - 90 * k, car["y"] - 260), (car["x"] - 190 * k, car["y"] - 300)]
        pen.line(pts, (10, 12, 16, 255), 40)
        pen.line(pts, ORANGE + (255,), 26)
        pen.arrow(pts[-1][0] + 20, pts[-1][1] + 6, pts[-1][0] - 50 * k, pts[-1][1] - 6, 26, ORANGE + (255,),
                  (10, 12, 16, 255), 5)
    t_h = W_("bremse", "Hupen")
    for k in range(3):
        a = T - t_h - k * 0.22
        if 0 < a < 0.9:
            rr = 140 + a * 420
            pen.arc(car["x"], car["y"] - 120, rr, -150, -30, (255, 255, 255, int(220 * (1 - a / 0.9))), 10)
    return pen.finish()


def lights_for(T, car):
    cars = [(car["x"], car["y"], car["h"], car["high"], car["brake"], car["hazard"], car["on"])]
    pts = [(-200, -99999, 1, (0, 0, 0), 0)]
    if car["run"] == "A" and car["ta"] > T_IMPACT and int(car["ta"] * 7) % 5 == 0:
        cars = [(car["x"], car["y"], car["h"], 0.3, 0, 0, 0.25)]
    amb = (0.34, 0.38, 0.54)
    if 8.9 <= T < 10.45:
        amb = (0.26, 0.24, 0.34)
    return cars, pts, amb


# ================================================================== HUD: text helpers
@lru_cache(maxsize=None)
def fnt(path, size):
    return ImageFont.truetype(path, size)


@lru_cache(maxsize=512)
def text_im(text, size, color=WHITE, stroke=None, path=F_BLACK, shadow=True):
    f = fnt(path, size)
    stroke = stroke if stroke is not None else max(4, size // 11)
    bb = f.getbbox(text, stroke_width=stroke)
    w, h = bb[2] - bb[0] + 24, bb[3] - bb[1] + 24
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((12 - bb[0], 12 - bb[1]), text, font=f, fill=color, stroke_width=stroke, stroke_fill=(0, 0, 0))
    if not shadow:
        return im
    out = Image.new("RGBA", (w + 8, h + 10), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(4)).point(lambda a: int(a * 0.6)))
    out.alpha_composite(sh, (5, 8))
    out.alpha_composite(im, (0, 0))
    return out


@lru_cache(maxsize=8)
def emoji_im(ch, size):
    f = ImageFont.truetype(F_EMOJI, 109)
    im = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((90, 90), ch, font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox())
    s = size / max(im.size)
    return im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)


def paste(frame, im, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if im is None or alpha <= 0.01 or scale <= 0.01:
        return
    if rot:
        im = im.rotate(rot, Image.BICUBIC, expand=True)
    if abs(scale - 1) > 0.005:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    if alpha < 0.999:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    x0, y0 = int(cx - im.width / 2), int(cy - im.height / 2)
    frame.alpha_composite(im, (max(0, x0), max(0, y0)), (max(0, -x0), max(0, -y0)))


def pop(age, dur=0.16):
    if age < 0:
        return 0.0
    if age < dur:
        x = age / dur - 1
        return 1 + 2.4 * x ** 3 + 1.4 * x ** 2
    return 1.0


# ================================================================== captions (word chunks)
KEYWORDS = {"landstraße", "reh", "ausweichen", "fehler", "baum", "nochmal", "festhalten", "geradeaus", "bremsen",
            "hupen", "abblenden", "erstarren", "vorsicht", "mehr", "knallt", "warnblinker", "warnweste", "warndreieck",
            "polizei", "nicht", "instinkt", "schleudert", "weg", "fernlicht", "gefährlich"}


def build_chunks():
    chunks = []
    for key, l in LINES.items():
        if key == "frage":
            continue
        toks = []
        for w in l["words"]:
            for i, part in enumerate(w["w"].split()):
                toks.append([part, l["start"] + w["s"]])
        texts = l.get("text") or None
        cur = []
        groups = []
        for tok in toks:
            cur.append(tok)
            if len(cur) >= 3 or sum(len(t[0]) for t in cur) >= 15:
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        # attach punctuation from script to break at sentence ends
        for gi, g in enumerate(groups):
            t0 = g[0][1]
            t1 = groups[gi + 1][0][1] if gi + 1 < len(groups) else l["end"] + 0.25
            chunks.append(dict(words=[t[0] for t in g], t0=t0, t1=t1, key=key))
    for i in range(len(chunks) - 1):
        chunks[i]["t1"] = min(chunks[i]["t1"], chunks[i + 1]["t0"])
    return chunks


def regroup_by_punct():
    """re-chunk using the script text so groups never cross '.', ':' or ','"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("wild_script", Path(__file__).with_name("script.py"))
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    out = []
    for key, text, gap in script.LINES:
        if key == "frage":
            continue
        l = LINES[key]
        toks = text.split()
        times = []
        for w in l["words"]:
            for _ in w["w"].split():
                times.append(l["start"] + w["s"])
        times = (times + [times[-1]] * len(toks))[: len(toks)]
        groups, cur = [], []
        for tok, t in zip(toks, times):
            cur.append((tok, t))
            end = tok[-1] in ".:,?!"
            if end or len(cur) >= 3 or sum(len(c[0]) for c in cur) >= 15:
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        for gi, g in enumerate(groups):
            t1 = groups[gi + 1][0][1] if gi + 1 < len(groups) else l["end"] + 0.3
            out.append(dict(words=[c[0].strip(".,:") for c in g], t0=g[0][1] - 0.04, t1=t1 - 0.04, key=key))
    for i in range(len(out) - 1):
        out[i]["t1"] = min(out[i]["t1"], out[i + 1]["t0"])
    return out


CHUNKS = None


@lru_cache(maxsize=256)
def chunk_img(words, size=98):
    ims = []
    for w in words:
        kw = w.strip("?!").lower() in KEYWORDS
        ims.append(text_im(w, size, YELLOW if kw else WHITE))
    gap = int(size * 0.22)
    tw = sum(i.width for i in ims) + gap * (len(ims) - 1)
    th = max(i.height for i in ims)
    im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    x = 0
    for i in ims:
        im.alpha_composite(i, (x, th - i.height))
        x += i.width + gap
    if im.width > 1000:
        s = 1000 / im.width
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    return im


def draw_captions(frame, T):
    global CHUNKS
    if CHUNKS is None:
        CHUNKS = regroup_by_punct()
    for c in CHUNKS:
        if c["t0"] <= T < c["t1"]:
            age = T - c["t0"]
            paste(frame, chunk_img(tuple(c["words"])), 540, 372, pop(age, 0.14), min(1, age / 0.06 + 0.3))


def tags():
    return [
        (W_("intro", "Landstraße"), ST("reh"), "LANDSTRASSE · NACHTS", CYAN),
        (W_("reh", "Reh"), ST("instinkt"), "WILDWECHSEL!", RED),
        (W_("instinkt", "ausweichen"), 8.9, "AUSWEICHEN?", ORANGE),
        (W_("fehler", "Fehler"), ST("crash"), "FALSCH!", RED),
        (W_("crash", "schleudert"), W_("crash", "Baum"), "SCHLEUDERN!", RED),
        (W_("crash", "Baum"), T_RW0, "BAUM!", RED),
        (W_("fest", "Geradeaus"), ST("bremse"), "GERADEAUS", CYAN),
        (W_("bremse", "Fernlicht"), ST("mehr"), "ERSTARRT IM LICHT", CYAN),
        (W_("mehr", "springt"), W_("mehr", "Aber"), "SPRINGT WEG", GREEN),
        (W_("mehr", "Vorsicht"), W_("mehr", "Oft"), "VORSICHT!", ORANGE),
        (W_("mehr", "mehr"), ST("knallt"), "NOCH MEHR!", RED),
    ]


TAGS = None


def draw_tags(frame, T):
    global TAGS
    if TAGS is None:
        TAGS = tags()
    for t0, t1, txt, col in TAGS:
        if t0 <= T < t1:
            paste(frame, text_im(txt, 62, col, 8), 540, 486, pop(T - t0, 0.16))


# ================================================================== cards + icons
def _wheel(d, cx, cy, r, ang, grips=YELLOW, s=2):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=WHITE, width=10 * s // 2)
    for a in (ang + 90, ang + 210, ang + 330):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        d.line([(cx, cy), (cx + ca * r, cy + sa * r)], fill=WHITE, width=8 * s // 2)
    d.ellipse([cx - r * 0.24, cy - r * 0.24, cx + r * 0.24, cy + r * 0.24], fill=WHITE)
    for a in (ang + 180, ang):
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        g = r * 0.2
        d.ellipse([cx + ca * r - g, cy + sa * r - g, cx + ca * r + g, cy + sa * r + g], fill=grips)


def icon(d, kind, cx, cy, T, age, s=2):
    if kind == "wheel_jerk":
        _wheel(d, cx, cy, 52 * s, 75 * math.sin(T * 13), YELLOW, s)
    elif kind == "wheel_hold":
        _wheel(d, cx, cy, 52 * s, 1.5 * math.sin(T * 30), (90, 230, 120), s)
    elif kind == "brake":
        press = min(1, age / 0.25)
        d.rounded_rectangle([cx - 70 * s, cy + 46 * s, cx + 70 * s, cy + 58 * s], 6 * s, fill=(70, 80, 100))
        a = math.radians(-60 + 25 * press)
        px, py = cx - 20 * s, cy + 50 * s
        ex, ey = px + math.cos(a) * 80 * s, py + math.sin(a) * 80 * s
        d.line([(px, py), (ex, ey)], fill=WHITE, width=9 * s)
        d.rounded_rectangle([ex - 34 * s, ey - 10 * s, ex + 34 * s, ey + 10 * s], 6 * s, fill=RED)
        for k in range(3):
            yy = cy - 40 * s + k * 18 * s
            d.line([(cx + 50 * s, yy), (cx + 80 * s, yy + 10 * s)], fill=(255, 255, 255, 160), width=4 * s)
    elif kind == "horn":
        d.polygon([(cx - 70 * s, cy - 18 * s), (cx - 40 * s, cy - 18 * s), (cx, cy - 45 * s), (cx, cy + 45 * s),
                   (cx - 40 * s, cy + 18 * s), (cx - 70 * s, cy + 18 * s)], fill=WHITE)
        for k in range(3):
            ph = (T * 2.5 + k / 3) % 1
            r = (20 + 60 * ph) * s
            d.arc([cx + 10 * s - r, cy - r, cx + 10 * s + r, cy + r], -45, 45, fill=(70, 220, 255, int(255 * (1 - ph))),
                  width=6 * s)
    elif kind == "beam":
        k = min(1, age / 0.5)
        d.chord([cx - 70 * s, cy - 40 * s, cx - 10 * s, cy + 40 * s], 90, 270, fill=WHITE)
        d.rectangle([cx - 42 * s, cy - 40 * s, cx - 30 * s, cy + 40 * s], fill=WHITE)
        for i in range(4):
            y0 = cy - 30 * s + i * 20 * s
            tilt = lerp(0, 22, k) * s
            ln = lerp(110, 70, k) * s
            d.line([(cx - 4 * s, y0), (cx - 4 * s + ln, y0 + tilt)], fill=(70, 220, 255), width=7 * s)
    elif kind == "hazard":
        on = int(T * 2.8) % 2 == 0
        c = (255, 80, 60) if on else (120, 40, 40)
        pts = [(cx, cy - 48 * s), (cx + 56 * s, cy + 42 * s), (cx - 56 * s, cy + 42 * s)]
        d.polygon(pts, outline=c, width=10 * s)
        pts2 = [(cx, cy - 18 * s), (cx + 24 * s, cy + 24 * s), (cx - 24 * s, cy + 24 * s)]
        d.polygon(pts2, outline=c, width=7 * s)
    elif kind == "vest":
        d.polygon([(cx - 50 * s, cy - 50 * s), (cx - 18 * s, cy - 50 * s), (cx, cy - 20 * s), (cx + 18 * s, cy - 50 * s),
                   (cx + 50 * s, cy - 50 * s), (cx + 56 * s, cy + 52 * s), (cx - 56 * s, cy + 52 * s)], fill=(210, 255, 60))
        for yy in (cy + 6 * s, cy + 28 * s):
            d.rectangle([cx - 54 * s, yy, cx + 54 * s, yy + 9 * s], fill=(200, 205, 215))
    elif kind == "triangle":
        pts = [(cx, cy - 50 * s), (cx + 58 * s, cy + 44 * s), (cx - 58 * s, cy + 44 * s)]
        d.polygon(pts, fill=(235, 50, 50))
        pts2 = [(cx, cy - 20 * s), (cx + 26 * s, cy + 26 * s), (cx - 26 * s, cy + 26 * s)]
        d.polygon(pts2, fill=(245, 245, 240))
    elif kind == "phone":
        d.rounded_rectangle([cx - 40 * s, cy - 56 * s, cx + 40 * s, cy + 56 * s], 12 * s, fill=(230, 235, 245))
        d.rounded_rectangle([cx - 32 * s, cy - 44 * s, cx + 32 * s, cy + 40 * s], 6 * s, fill=(20, 30, 50))
        f = fnt(F_BLACK, 34 * s)
        d.text((cx, cy - 2 * s), "110", font=f, fill=(255, 80, 80), anchor="mm")
    elif kind == "deer":
        d.ellipse([cx - 30 * s, cy - 34 * s, cx + 30 * s, cy + 40 * s], fill=(200, 140, 80))
        for sx in (-1, 1):
            d.ellipse([cx + sx * 34 * s - 18 * s, cy - 50 * s, cx + sx * 34 * s + 18 * s, cy - 26 * s], fill=(170, 110, 60))
        d.ellipse([cx - 14 * s, cy + 20 * s, cx + 14 * s, cy + 40 * s], fill=(60, 40, 30))
        for sx in (-1, 1):
            d.ellipse([cx + sx * 14 * s - 6 * s, cy - 8 * s, cx + sx * 14 * s + 6 * s, cy + 4 * s], fill=(20, 20, 20))
    elif kind == "tree":
        d.rectangle([cx - 10 * s, cy + 10 * s, cx + 10 * s, cy + 56 * s], fill=(120, 80, 40))
        d.ellipse([cx - 50 * s, cy - 56 * s, cx + 50 * s, cy + 30 * s], fill=(60, 150, 70))
    elif kind == "no_swerve":
        d.arc([cx - 50 * s, cy - 30 * s, cx + 30 * s, cy + 70 * s], 180, 300, fill=ORANGE, width=10 * s)
        d.line([(cx - 50 * s, cy - 50 * s), (cx + 50 * s, cy + 50 * s)], fill=RED, width=12 * s)


@lru_cache(maxsize=4)
def card_base(w, h, border):
    s = 2
    im = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * s - 1, h * s - 1], 26 * s, fill=(0, 0, 0, 120))
    d.rounded_rectangle([6, 6, w * s - 7, h * s - 7], 22 * s, fill=NAVY + (238,), outline=border, width=5 * s)
    return im


def card_img(kind, title, border, T, age, w=440, h=220, bars=None):
    s = 2
    im = card_base(w, h, border).copy()
    d = ImageDraw.Draw(im)
    f = fnt(F_BLACK, 34 * s)
    d.text((w * s / 2, 38 * s), title, font=f, fill=WHITE, anchor="mm")
    icon(d, kind, w * s / 2, (h * s) / 2 + 28 * s if bars is None else (h * s) / 2 + 8 * s, T, age, s)
    if bars is not None:
        n, col = bars
        for i in range(5):
            x0 = w * s / 2 - 5 * 26 * s / 2 + i * 26 * s
            fill = col if i < n else (60, 70, 90)
            d.rounded_rectangle([x0, (h - 34) * s, x0 + 20 * s, (h - 18) * s], 4 * s, fill=fill)
    return im.reduce(s)


def cards():
    return [
        (W_("instinkt", "Lenkrad"), 8.9, "wheel_jerk", "LENKRAD REISSEN", RED),
        (W_("fest", "Lenkrad"), ST("bremse"), "wheel_hold", "LENKRAD FEST", GREEN),
        (W_("bremse", "Voll"), W_("bremse", "Hupen"), "brake", "VOLL BREMSEN", GREEN),
        (W_("bremse", "Hupen"), W_("bremse", "Und"), "horn", "HUPEN", GREEN),
        (W_("bremse", "Und"), ST("mehr") + 0.2, "beam", "ABBLENDEN", GREEN),
        (W_("danach", "Warnblinker"), W_("danach", "Warnweste"), "hazard", "WARNBLINKER", ORANGE),
        (W_("danach", "Warnweste"), W_("danach", "Warndreieck"), "vest", "WARNWESTE", ORANGE),
        (W_("danach", "Warndreieck"), W_("danach", "Polizei"), "triangle", "WARNDREIECK", ORANGE),
        (W_("danach", "Polizei"), ST("merk"), "phone", "POLIZEI RUFEN", ORANGE),
    ]


CARDS = None


def draw_cards(frame, T):
    global CARDS
    if CARDS is None:
        CARDS = cards()
    for t0, t1, kind, title, col in CARDS:
        if t0 <= T < t1:
            age = T - t0
            out = clamp01((t1 - T) / 0.12)
            paste(frame, card_img(kind, title, col, T, age), 540, 1400, 1.3 * pop(age, 0.18) * (0.9 + 0.1 * out), out)
    # comparison
    t_reh, t_baum = W_("knallt", "Reh"), W_("knallt", "Baum")
    if t_reh <= T < ST("danach"):
        a = T - t_reh
        paste(frame, card_img("deer", "REH", YELLOW, T, a, 400, 250, (2, YELLOW)), 290, 1400, 1.12 * pop(a, 0.18))
    if t_baum <= T < ST("danach"):
        a = T - t_baum
        paste(frame, card_img("tree", "BAUM", RED, T, a, 400, 250, (5, RED)), 790, 1400, 1.12 * pop(a, 0.18))
        paste(frame, text_im(">", 120, WHITE), 540, 1395, pop(a, 0.18)) if False else None


@lru_cache(maxsize=8)
def row_img(kind, label, border):
    s = 2
    w, h = 820, 118
    im = Image.new("RGBA", (w * s, h * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 4, w * s - 5, h * s - 5], 22 * s, fill=NAVY + (240,), outline=border, width=5 * s)
    icon(d, kind, 70 * s, h * s / 2, 0.0, 1.0, 1)
    f = fnt(F_BLACK, 52 * s)
    d.text((140 * s, h * s / 2 + 2 * s), label, font=f, fill=WHITE, anchor="lm")
    return im.reduce(s)


def draw_recap(frame, T):
    rows = [(W_("merk", "Nicht"), "no_swerve", "NICHT AUSWEICHEN", RED),
            (W_("merk", "Festhalten"), "wheel_hold", "FESTHALTEN", GREEN),
            (W_("merk", "Bremsen"), "brake", "BREMSEN", GREEN)]
    if not (ST("merk") <= T < ST("frage") - 0.1):
        return
    for i, (t0, kind, label, col) in enumerate(rows):
        if T >= t0:
            a = T - t0
            x = 540 + 800 * (1 - ease_out(a / 0.3))
            paste(frame, row_img(kind, label, col), x, 1180 + i * 138, 1.0, clamp01(a / 0.15))


def draw_badge(frame, T):
    if T < EN("intro") + 0.2:
        a = clamp01(T / 0.3) * clamp01((EN("intro") + 0.2 - T) / 0.25)
        im = text_im("ÜBERLEBST DU DAS? · FOLGE 3", 40, WHITE, 6)
        paste(frame, im, 540, 236, 1.0, a)


def draw_final(frame, T):
    t0 = ST("frage")
    if T < t0:
        return
    a = T - t0
    paste(frame, text_im("EHRLICH:", 74, YELLOW, 8), 540, 470, pop(a, 0.16))
    t1 = W_("frage", "Wärst")
    if T >= t1:
        b = T - t1
        paste(frame, text_im("WÄRST DU", 118, WHITE, 11), 540, 600, pop(b, 0.16))
        paste(frame, text_im("AUSGEWICHEN?", 118, WHITE, 11), 540, 730, pop(b - 0.25, 0.16))
        if b > 0.7:
            paste(frame, emoji_im("👇", 120), 540, 880 + 14 * math.sin(T * 7), pop(b - 0.7, 0.16))


def draw_rewind_label(frame, T):
    if T_RW0 <= T < T_RW1 + 0.15:
        on = int(T * 4) % 2 == 0
        im = text_im("ZURÜCKSPULEN", 54, WHITE, 6, F_BLACK)
        frame.alpha_composite(im, (150, 1532))
        if on:
            d = ImageDraw.Draw(frame)
            for k in range(2):
                x = 64 + k * 40
                d.polygon([(x + 40, 1556), (x + 40, 1604), (x, 1580)], fill=WHITE, outline=(0, 0, 0), width=4)


# ================================================================== post
VIG = None
GRAIN = None


def init():
    global VIG, GRAIN
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.sqrt(((xx - W / 2) / (W * 0.72)) ** 2 + ((yy - H / 2) / (H * 0.68)) ** 2)
    a = np.clip((v - 0.55) * 1.5, 0, 0.75)
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 3] = (a * 255).astype(np.uint8)
    VIG = Image.fromarray(arr, "RGBA")
    rng = np.random.default_rng(2)
    GRAIN = [rng.integers(-7, 8, (H // 2, W // 2, 1), dtype=np.int16) for _ in range(4)]


def glow(img, strength=0.85, thresh=200):
    small = img.resize((W // 4, H // 4), Image.BILINEAR)
    arr = np.asarray(small).astype(np.float32)
    lum = arr @ np.array([0.3, 0.59, 0.11], np.float32)
    m = np.clip((lum - thresh) / (255 - thresh), 0, 1)[..., None]
    b = Image.fromarray((arr * m).astype(np.uint8))
    g = ImageChops.add(b.filter(ImageFilter.GaussianBlur(4)), b.filter(ImageFilter.GaussianBlur(14)))
    g = Image.fromarray((np.asarray(g).astype(np.float32) * strength).clip(0, 255).astype(np.uint8))
    return ImageChops.screen(img, g.resize((W, H), Image.BILINEAR))


def render_frame(fi):
    T = fi / FPS
    car = car_state(T)
    deers = deer_states(T)
    person = person_state(T)
    cam = camera(T, car, deers)
    scene, M, ps = draw_world(cam, T, car, deers, person)
    cars, pts, amb = lights_for(T, car)
    L = WD.light_map(M, cam[2], cars, pts, amb)
    lit = Image.fromarray(WD.apply_light(scene.convert("RGB"), L), "RGB")
    em = draw_emissive(cam, T, car, deers, L, M, ps, person)
    lit = lit.convert("RGBA")
    lit.alpha_composite(em)
    img = glow(lit.convert("RGB"))
    arr = np.asarray(img).astype(np.int16)
    if 8.9 <= T < 10.45:  # freeze on the mistake: desaturate + red
        k = clamp01((T - 8.9) / 0.25) * clamp01((10.45 - T) / 0.15)
        lum = arr.mean(axis=2, keepdims=True)
        arr = (arr * (1 - k * 0.7) + lum * np.array([1.15, 0.75, 0.75]) * k * 0.7).astype(np.int16)
    if T_RW0 <= T < T_RW1:
        lum = arr.mean(axis=2, keepdims=True)
        arr = (arr * 0.4 + lum * np.array([0.75, 0.85, 1.05]) * 0.6).astype(np.int16)
        arr[::4] = (arr[::4] * 0.72).astype(np.int16)
        r = random.Random(fi)
        for _ in range(3):
            y0 = r.randint(0, H - 50)
            hh = r.randint(6, 40)
            arr[y0:y0 + hh] = np.roll(arr[y0:y0 + hh], r.randint(-70, 70), axis=1) + 35
    g = GRAIN[fi % 4]
    arr = arr + np.repeat(np.repeat(g, 2, axis=0), 2, axis=1)
    frame = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    if T_RW0 <= T < T_RW1:
        rr, gg, bb, aa = frame.split()
        frame = Image.merge("RGBA", (ImageChops.offset(rr, 8, 0), gg, ImageChops.offset(bb, -8, 0), aa))
    frame.alpha_composite(VIG)
    if T_IMPACT <= T < T_IMPACT + 0.1:
        frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(200 * (1 - (T - T_IMPACT) / 0.1)))))
    if 8.9 <= T < 10.45:
        r = Image.new("RGBA", (W, H), (210, 20, 30, 0))
        r.putalpha(VIG.getchannel("A").point(lambda a: int(a * 0.55)))
        frame.alpha_composite(r)
    draw_badge(frame, T)
    draw_captions(frame, T)
    draw_tags(frame, T)
    draw_cards(frame, T)
    draw_recap(frame, T)
    draw_rewind_label(frame, T)
    draw_final(frame, T)
    return frame.convert("RGB").tobytes()


# ================================================================== main
def main():
    init()
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        sd = BUILD / os.environ.get("STILLS", "stills")
        sd.mkdir(parents=True, exist_ok=True)
        for t in [float(x) for x in sys.argv[2:]]:
            Image.frombytes("RGB", (W, H), render_frame(int(round(t * FPS)))).save(sd / f"t{t:05.2f}.png")
        return
    import audio
    raw = BUILD / "mix_raw.wav"
    audio.build(raw, sys.modules[__name__])
    mix = BUILD / "mix.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", "48000", "-ac", "2", str(mix)], check=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(mix), "-c:v", "libx264", "-preset", "slow", "-b:v", "7M", "-maxrate", "9M", "-bufsize", "14M", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", f"{TOTAL:.3f}",
           str(OUTFILE)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=init) as pool:
        for i, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=3)):
            ff.stdin.write(buf)
            if i % 150 == 0:
                print(f"frame {i}/{NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", OUTFILE, f"{TOTAL:.2f}s")


if __name__ == "__main__":
    main()
