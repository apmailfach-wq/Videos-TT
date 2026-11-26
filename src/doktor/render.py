"""Render doktor-video.mp4 (1080x1920, 30 fps): the doctor joke as a cartoon sketch.

Scene: doctor's office (wall clock, ECG monitor, desk). Patient (left) asks how long
he has left, the doctor (right) fires questions, a med-card fills up with red "НЕТ"
stamps, the heart monitor speeds up, the doctor takes off her glasses (dramatic sting,
slow push-in), delivers the punchline -> flatline, hairs fly off, "СМЫСЛА НЕТ" stamp,
then a share CTA. Mouths are lip-synced to the voice amplitude.

    python3 tts.py && python3 render.py            # -> ../../doktor-video.mp4
    python3 render.py preview 1 5 9 13 16          # stills -> build/doktor/stills/
"""
import json
import math
import os
import subprocess
import sys
import wave
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from script import LINES, TXT, BUILD_NAME, VIDEO_NAME

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / BUILD_NAME
OUT = ROOT / os.environ.get("VIDEO_OUT", VIDEO_NAME)
W, H, FPS, SR = 1080, 1920, 30, 44100
SS = 2  # supersampling

F_HEAD = str(ROOT / "fonts" / "Unbounded_900Black.ttf")
F_HAND = str(ROOT / "fonts" / "Caveat_700Bold.ttf")
F_CAP = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_BOLD = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"

INK = (28, 30, 36)
WALL = (196, 226, 219)
WALL_D = (176, 210, 203)
FLOOR = (222, 196, 160)
FLOOR_D = (204, 176, 140)
DESK = (150, 104, 70)
DESK_D = (120, 80, 52)
SKIN = (255, 214, 180)
SKIN_D = (236, 186, 150)
COAT = (250, 250, 252)
COAT_D = (214, 220, 228)
HAIR_DOC = (110, 62, 40)
SHIRT = (64, 150, 214)
SHIRT_D = (44, 118, 178)
PANTS = (60, 64, 84)
RED = (232, 54, 64)
YEL = (255, 222, 40)
GREEN = (60, 240, 120)
PAT_COL = (40, 170, 230)
DOC_COL = (240, 70, 120)


@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, int(size))


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):
    return 1 - (1 - clamp01(x)) ** 3


def ease_io(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def ease_back(x, s=1.7):
    x = clamp01(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


# ---------------------------------------------------------------- timeline / audio
def read_wav(p):
    with wave.open(str(p)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return a


timings = json.loads((BUILD / "timings.json").read_text())
LN = []  # per line: who, text, start, end, audio, words, env
t = 0.0
for i, (meta, tm) in enumerate(zip(LINES, timings)):
    a = read_wav(tm["wav"])
    idx = np.nonzero(np.abs(a) > 0.012)[0]
    s0 = max(int(idx[0]) - int(0.02 * SR), 0)
    s1 = min(int(idx[-1]) + int(0.06 * SR), len(a))
    a = a[s0:s1]
    off = s0 / SR
    t += meta[5]
    start = t
    t += len(a) / SR
    hop = SR // FPS
    env = np.array([np.sqrt(np.mean(a[k:k + hop] ** 2)) for k in range(0, len(a), hop)])
    env = np.clip(env / (np.percentile(env, 92) + 1e-6), 0, 1.2)
    words = [{"text": w["text"], "start": start + w["start"] - off, "end": start + w["end"] - off}
             for w in tm["words"]]
    LN.append({"who": meta[0], "text": meta[1], "start": start, "end": t, "audio": a,
               "words": words, "env": env})

T_Q = [LN[1]["start"], LN[3]["start"], LN[5]["start"]]       # doctor questions
T_NO = [LN[2]["start"], LN[4]["start"], LN[6]["start"]]      # patient "нет"
T_PAUSE = LN[6]["end"]
T_GLASS0 = T_PAUSE + 0.45        # glasses removal: hand up
T_GLASS1 = T_GLASS0 + 1.25       # glasses down
T_PUNCH = LN[7]["start"]
T_PEND = LN[7]["end"]
T_FLAT = T_PEND + 0.22           # flatline
T_STAMP = T_FLAT + 0.35
T_CTA = T_FLAT + 1.75
T_END = T_CTA + 3.0
NFRAMES = int(T_END * FPS)


def bpm_at(tt):
    b = 74
    for k, tn in enumerate(T_NO):
        if tt > tn:
            b = 74 + 16 * (k + 1)
    if tt > T_PAUSE:
        b = 132
    return b


# beat times up to flatline (and a revived beat during the CTA for the loop)
BEATS = []
bt = 0.35
while bt < T_FLAT:
    BEATS.append(bt)
    bt += 60.0 / bpm_at(bt)
bt = T_CTA + 0.5
while bt < T_END:
    BEATS.append(bt)
    bt += 60.0 / 74
BEATS = np.array(BEATS)


def ecg(tt):
    """ECG trace value (-1..1) at time tt."""
    if T_FLAT <= tt < T_CTA + 0.45:
        return 0.0
    k = np.searchsorted(BEATS, tt) - 1
    if k < 0:
        return 0.0
    d = tt - BEATS[k]
    v = 0.12 * math.exp(-((d - 0.00) / 0.025) ** 2)          # P
    v -= 0.15 * math.exp(-((d - 0.07) / 0.010) ** 2)         # Q
    v += 1.00 * math.exp(-((d - 0.09) / 0.012) ** 2)         # R
    v -= 0.30 * math.exp(-((d - 0.11) / 0.012) ** 2)         # S
    v += 0.22 * math.exp(-((d - 0.26) / 0.045) ** 2)         # T
    return v


def speaking(who, tt):
    """Mouth opening 0..1 for character who at time tt."""
    for ln in LN:
        if ln["who"] == who and ln["start"] <= tt < ln["end"]:
            k = int((tt - ln["start"]) * FPS)
            return float(min(ln["env"][min(k, len(ln["env"]) - 1)], 1.0))
    return 0.0


def active_line(tt):
    for i, ln in enumerate(LN):
        if ln["start"] - 0.08 <= tt < ln["end"] + 0.25:
            return i
    return None


# ---------------------------------------------------------------- camera
DOC_HEAD = (790, 800)
PAT_HEAD = (290, 860)


def cam_at(tt):
    """(cx, cy, zoom, shake) in world coords."""
    wide = (565, 920, 1.2)

    def on(head, z, sy=1000):
        # put the head at screen (540, sy)
        return (head[0], head[1] + (960 - sy) / z, z)

    shots = [(0.0, "wide")]
    zooms_doc = [1.5, 1.6, 1.7]
    zooms_pat = [1.55, 1.75, 2.0]
    for k in range(3):
        shots.append((T_Q[k] - 0.05, ("doc", zooms_doc[k])))
        shots.append((T_NO[k] - 0.05, ("pat", zooms_pat[k])))
    shots.append((T_PAUSE + 0.05, "push"))
    shots.append((T_FLAT - 0.02, "patshock"))
    shots.append((T_CTA, "wide"))
    cur, t0 = shots[0][1], 0.0
    for ts, sh in shots:
        if tt >= ts:
            cur, t0 = sh, ts
    d = tt - t0
    shake = 0.0
    if cur == "wide":
        cx, cy, z = wide
        if tt < T_Q[0]:
            z = 1.2 + 0.08 * ease_io(tt / max(T_Q[0], 0.1))
    elif cur == "wide2":
        cx, cy, z = wide
    elif cur == "push":
        p = ease_io((tt - (T_PAUSE + 0.05)) / (T_PUNCH - T_PAUSE + 0.2))
        z = lerp(1.35, 2.35, p) + 0.12 * clamp01((tt - T_PUNCH) / 3)
        cx, cy, z = on(DOC_HEAD, z, 1010)
    elif cur == "patshock":
        z = 2.1 - 0.25 * ease_out(d / 0.25)
        cx, cy, z = on(PAT_HEAD, z, 1020)
        shake = 14 * max(0.0, 1 - d / 0.9)
    else:
        who, zz = cur
        z = zz * (1.06 - 0.06 * ease_out(d / 0.18))  # punch-in
        cx, cy, z = on(DOC_HEAD if who == "doc" else PAT_HEAD, z)
    return cx, cy, z, shake


class Cam:
    def __init__(self, cx, cy, z, sx=0.0, sy=0.0):
        self.cx, self.cy, self.z, self.sx, self.sy = cx, cy, z, sx, sy

    def p(self, x, y):
        return (((x - self.cx) * self.z + 540 + self.sx) * SS, ((y - self.cy) * self.z + 960 + self.sy) * SS)

    def s(self, v):
        return v * self.z * SS

    def box(self, x0, y0, x1, y1):
        a, b = self.p(x0, y0), self.p(x1, y1)
        return [a[0], a[1], b[0], b[1]]

    def circ(self, x, y, r):
        return self.box(x - r, y - r, x + r, y + r)


# ---------------------------------------------------------------- drawing helpers
def ell(d, c, x, y, rx, ry, fill, outline=INK, w=5):
    a, b = c.p(x - rx, y - ry), c.p(x + rx, y + ry)
    d.ellipse([a[0], a[1], b[0], b[1]], fill=fill, outline=outline, width=max(1, int(c.s(w))) if outline else 0)


def rrect(d, c, x0, y0, x1, y1, r, fill, outline=INK, w=5):
    d.rounded_rectangle(c.box(x0, y0, x1, y1), radius=c.s(r), fill=fill,
                        outline=outline, width=max(1, int(c.s(w))) if outline else 0)


def line(d, c, pts, fill=INK, w=5, joint=True):
    d.line([c.p(*q) for q in pts], fill=fill, width=max(1, int(c.s(w))), joint="curve" if joint else None)
    for q in (pts[0], pts[-1]):
        x, y = c.p(*q)
        r = c.s(w) / 2
        d.ellipse([x - r, y - r, x + r, y + r], fill=fill)


def poly(d, c, pts, fill, outline=INK, w=5):
    d.polygon([c.p(*q) for q in pts], fill=fill, outline=outline, width=max(1, int(c.s(w))) if outline else 0)


def limb(d, c, pts, col, w):
    line(d, c, pts, INK, w + 10)
    line(d, c, pts, col, w)


def text_c(d, xy, txt, f, fill, stroke=0, sfill=INK, anchor="mm"):
    d.text(xy, txt, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=sfill)


# ---------------------------------------------------------------- room
def draw_room(d, c, tt):
    d.rectangle(c.box(-1500, -2000, 2600, 1300), fill=WALL)
    # wall stripes
    for x in range(-1500, 2600, 120):
        d.rectangle(c.box(x, -2000, x + 60, 1300), fill=WALL_D)
    d.rectangle(c.box(-1500, 1300, 2600, 3500), fill=FLOOR)
    for y in (1380, 1500, 1660, 1880):
        d.rectangle(c.box(-1500, y, 2600, y + 8), fill=FLOOR_D)
    d.rectangle(c.box(-1500, 1270, 2600, 1310), fill=(240, 240, 236), outline=INK, width=int(c.s(4)))

    # wall clock (hands race during the pause: time is running out)
    cx, cy, r = 540, 470, 72
    ell(d, c, cx, cy, r, r, (252, 252, 250), INK, 7)
    for k in range(12):
        a = k / 12 * 2 * math.pi
        line(d, c, [(cx + math.sin(a) * r * 0.78, cy - math.cos(a) * r * 0.78),
                    (cx + math.sin(a) * r * 0.9, cy - math.cos(a) * r * 0.9)], INK, 4)
    speed = 0.15 if tt < T_PAUSE else (5.0 if tt < T_FLAT else 0.0)
    base = 0.15 * min(tt, T_PAUSE) + (5.0 * (min(tt, T_FLAT) - T_PAUSE) if tt > T_PAUSE else 0)
    _ = speed
    am = base * 2 * math.pi
    ah = am / 12 + 1.2
    line(d, c, [(cx, cy), (cx + math.sin(ah) * r * 0.45, cy - math.cos(ah) * r * 0.45)], INK, 8)
    line(d, c, [(cx, cy), (cx + math.sin(am) * r * 0.7, cy - math.cos(am) * r * 0.7)], RED, 5)
    ell(d, c, cx, cy, 7, 7, INK, None)

    # ECG monitor on a wall arm
    mx0, my0, mx1, my1 = 720, 400, 1010, 600
    line(d, c, [(865, 340), (865, 400)], (120, 126, 136), 14)
    rrect(d, c, mx0, my0, mx1, my1, 18, (52, 58, 68), INK, 7)
    rrect(d, c, mx0 + 16, my0 + 16, mx1 - 16, my1 - 40, 8, (14, 22, 20), None)
    flat = T_FLAT <= tt < T_CTA + 0.45
    col = (255, 70, 70) if flat else GREEN
    sx0, sx1 = mx0 + 24, mx1 - 24
    base_y = my0 + 100
    n = 70
    pts = []
    for k in range(n + 1):
        x = sx0 + (sx1 - sx0) * k / n
        ts = tt - 1.6 * (1 - k / n)
        pts.append((x, base_y - ecg(ts) * 52))
    line(d, c, pts, col, 4)
    hx, hy = pts[-1]
    ell(d, c, hx, hy, 6, 6, col, None)
    bpm = 0 if flat else bpm_at(tt)
    f = font(F_BOLD, c.s(26))
    text_c(d, c.p(mx0 + 60, my1 - 20), f"{bpm:>3}", f, col)
    beat = 0.0
    k = np.searchsorted(BEATS, tt) - 1
    if k >= 0 and not flat:
        beat = max(0.0, 1 - (tt - BEATS[k]) / 0.25)
    hr = 10 + 4 * beat
    hcx, hcy = mx0 + 115, my1 - 20
    d.polygon([c.p(hcx - hr, hcy - hr * 0.3), c.p(hcx, hcy + hr), c.p(hcx + hr, hcy - hr * 0.3)], fill=RED)
    d.ellipse(c.circ(hcx - hr * 0.5, hcy - hr * 0.35, hr * 0.55), fill=RED)
    d.ellipse(c.circ(hcx + hr * 0.5, hcy - hr * 0.35, hr * 0.55), fill=RED)
    text_c(d, c.p(mx1 - 70, my1 - 20), "BPM", font(F_BOLD, c.s(20)), (150, 160, 170))

    # diploma
    rrect(d, c, 60, 1000 - 380, 230, 1000 - 250, 4, (250, 246, 230), INK, 6)
    line(d, c, [(90, 650), (200, 650)], (190, 170, 120), 5)
    line(d, c, [(90, 675), (180, 675)], (190, 170, 120), 5)
    ell(d, c, 185, 725, 16, 16, RED, None)


def draw_desk_front(d, c):
    rrect(d, c, 520, 1110, 1120, 1150, 8, DESK, INK, 6)       # top
    rrect(d, c, 545, 1145, 1095, 1300, 6, DESK_D, INK, 6)     # front panel
    rrect(d, c, 600, 1180, 760, 1260, 6, DESK, INK, 4)
    ell(d, c, 680, 1220, 8, 8, (230, 200, 120), INK, 3)
    # props on the desk
    rrect(d, c, 950, 1040, 1000, 1112, 6, (90, 160, 220), INK, 5)  # pen cup
    line(d, c, [(962, 1040), (950, 995)], (240, 90, 90), 6)
    line(d, c, [(985, 1040), (995, 990)], (60, 60, 60), 6)
    poly(d, c, [(560, 1112), (600, 1090), (700, 1096), (690, 1112)], (255, 255, 255), INK, 4)


# ---------------------------------------------------------------- characters
def blink(tt, seed):
    p = (tt + seed) % 3.7
    return p < 0.11


def draw_doctor(d, c, tt):
    hx, hy = DOC_HEAD
    talk = speaking("doc", tt)
    bob = math.sin(tt * 9) * 3 * (talk > 0.05)
    hy += bob
    # glasses progress
    g = clamp01((tt - T_GLASS0) / (T_GLASS1 - T_GLASS0))
    glasses_on = g < 0.5
    # body / coat
    poly(d, c, [(680, 1120), (700, 930), (880, 930), (900, 1120)], COAT, INK, 6)
    poly(d, c, [(760, 930), (790, 1000), (820, 930)], (120, 200, 230), INK, 4)    # scrubs V
    line(d, c, [(745, 935), (735, 1010), (770, 1040)], (60, 70, 90), 6)          # stethoscope
    line(d, c, [(835, 935), (845, 1010), (810, 1040)], (60, 70, 90), 6)
    ell(d, c, 790, 1045, 13, 13, (190, 196, 206), INK, 4)
    rrect(d, c, 830, 980, 870, 1000, 3, (255, 255, 255), INK, 3)                  # name tag
    # neck + head
    rrect(d, c, hx - 22, hy + 70, hx + 22, hy + 125, 8, SKIN_D, INK, 5)
    ell(d, c, hx, hy - 95, 46, 40, HAIR_DOC, INK, 6)       # bun
    ell(d, c, hx, hy, 98, 104, SKIN, INK, 6)
    d.pieslice(c.circ(hx, hy - 6, 101), 180, 360, fill=HAIR_DOC, outline=INK, width=int(c.s(6)))
    poly(d, c, [(hx - 100, hy - 6), (hx - 88, hy + 50), (hx - 70, hy - 6)], HAIR_DOC, INK, 5)
    poly(d, c, [(hx + 100, hy - 6), (hx + 88, hy + 50), (hx + 70, hy - 6)], HAIR_DOC, INK, 5)
    ell(d, c, hx - 60, hy + 40, 16, 9, (255, 170, 160), None)
    ell(d, c, hx + 60, hy + 40, 16, 9, (255, 170, 160), None)
    # eyes
    ey = hy + 8
    for sx in (-1, 1):
        ex = hx + sx * 38
        if tt >= T_GLASS1 - 0.55:   # tired, half-lidded deadpan eyes
            ell(d, c, ex, ey, 20, 16, (255, 255, 255), INK, 4)
            ell(d, c, ex, ey + 4, 8, 8, INK, None)
            d.chord(c.circ(ex, ey, 22), 180, 360, fill=SKIN_D, outline=INK, width=int(c.s(4)))
            line(d, c, [(ex - 16, ey + 22), (ex + 12, ey + 24)], SKIN_D, 4)
            line(d, c, [(ex - 22, ey - 30), (ex + 22, ey - 26 + sx * 0)], INK, 6)
        elif blink(tt, 0.4):
            line(d, c, [(ex - 14, ey), (ex + 14, ey)], INK, 5)
        else:
            ell(d, c, ex, ey, 9, 11, INK, None)
            ell(d, c, ex + 3, ey - 4, 3, 3, (255, 255, 255), None)
            line(d, c, [(ex - 18, ey - 34), (ex + 18, ey - 36)], INK, 6)
    # mouth
    my = hy + 58
    if talk > 0.06:
        ell(d, c, hx, my, 18 + 6 * talk, 4 + 20 * talk, (150, 40, 50), INK, 4)
    elif tt >= T_GLASS1 - 0.55:
        line(d, c, [(hx - 20, my), (hx + 20, my)], INK, 5)           # flat mouth
    else:
        d.arc(c.circ(hx, my - 14, 20), 30, 150, fill=INK, width=int(c.s(5)))
    # arms: left arm (viewer's right) rests, right arm (viewer's left) takes off glasses
    limb(d, c, [(880, 950), (930, 1060), (880, 1105)], COAT, 30)
    ell(d, c, 872, 1105, 20, 16, SKIN, INK, 4)
    rest = (705, 1105)
    at_face = (hx - 45, hy + 20)
    hold = (640, 1060)
    if g <= 0:
        hand = rest
    elif g < 0.4:
        p = ease_io(g / 0.4)
        hand = (lerp(rest[0], at_face[0], p), lerp(rest[1], at_face[1], p))
    elif g < 0.55:
        hand = at_face
    else:
        p = ease_io((g - 0.55) / 0.45)
        hand = (lerp(at_face[0], hold[0], p), lerp(at_face[1], hold[1], p))
    elbow = (655, lerp(1060, 1010, clamp01(g * 3) if g < 0.9 else 1.0))
    limb(d, c, [(700, 950), elbow, hand], COAT, 30)
    # glasses
    if glasses_on:
        gx, gy, ga = hx, ey, 0.0
    else:
        gx, gy, ga = hand[0] + 40, hand[1] - 12, 0.0
    for sx in (-1, 1):
        ell(d, c, gx + sx * 38, gy, 30, 26, None, INK, 7) if False else None
        a, b = c.p(gx + sx * 38 - 30, gy - 26), c.p(gx + sx * 38 + 30, gy + 26)
        d.ellipse([a[0], a[1], b[0], b[1]], outline=(40, 40, 50), width=int(c.s(7)))
        # lens glare
        line(d, c, [(gx + sx * 38 - 14, gy - 12), (gx + sx * 38 - 4, gy - 18)], (255, 255, 255), 4)
    line(d, c, [(gx - 8, gy - 4), (gx + 8, gy - 4)], (40, 40, 50), 6)
    if glasses_on:
        line(d, c, [(gx - 68, gy - 6), (gx - 96, gy - 12)], (40, 40, 50), 6)
        line(d, c, [(gx + 68, gy - 6), (gx + 96, gy - 12)], (40, 40, 50), 6)
    ell(d, c, hand[0], hand[1], 21, 18, SKIN, INK, 4)


def draw_patient(d, c, tt):
    hx, hy = PAT_HEAD
    talk = speaking("pat", tt)
    nerv = sum(1 for tn in T_NO if tt > tn)
    shock = tt >= T_FLAT and tt < T_CTA
    sd = tt - T_FLAT
    jit = 0.0
    if shock:
        jit = math.sin(tt * 70) * 4 * max(0.0, 1 - sd / 1.2)
    elif nerv >= 2:
        jit = math.sin(tt * 40) * 1.5
    hx += jit
    # chair
    rrect(d, c, 170, 900, 210, 1160, 6, (90, 96, 110), INK, 5)
    rrect(d, c, 160, 1140, 430, 1175, 8, (110, 118, 134), INK, 5)
    line(d, c, [(190, 1175), (180, 1300)], INK, 10)
    line(d, c, [(400, 1175), (410, 1300)], INK, 10)
    # legs (sitting)
    limb(d, c, [(250, 1140), (380, 1140), (390, 1285)], PANTS, 38)
    limb(d, c, [(240, 1150), (350, 1150), (350, 1290)], PANTS, 38)
    ell(d, c, 405, 1295, 36, 14, INK, None)
    ell(d, c, 365, 1298, 36, 14, INK, None)
    # torso
    rrect(d, c, 215, 960, 365, 1160, 40, SHIRT, INK, 6)
    poly(d, c, [(265, 960), (290, 995), (315, 960)], (255, 255, 255), INK, 4)
    # arms: hands clutching knees, trembling
    tr = math.sin(tt * 30) * (2 + nerv)
    limb(d, c, [(240, 990), (255, 1080), (330 + tr, 1120)], SHIRT_D, 28)
    ell(d, c, 336 + tr, 1120, 19, 16, SKIN, INK, 4)
    limb(d, c, [(345, 990), (380, 1070), (395 - tr, 1118)], SHIRT_D, 28)
    ell(d, c, 400 - tr, 1118, 19, 16, SKIN, INK, 4)
    # neck + head
    rrect(d, c, hx - 18, hy + 70, hx + 18, hy + 110, 8, SKIN_D, INK, 5)
    skin = mix(SKIN, (214, 232, 200), clamp01(sd / 0.4)) if shock else SKIN
    ell(d, c, hx - 92, hy + 10, 18, 26, skin, INK, 5)
    ell(d, c, hx + 92, hy + 10, 18, 26, skin, INK, 5)
    ell(d, c, hx, hy, 92, 100, skin, INK, 6)
    # three famous hairs (fly away on the flatline)
    for k, dx in enumerate((-22, 0, 22)):
        if shock:
            fly = sd * (1 + k * 0.3)
            ox, oy = dx * 4 * fly + math.sin(fly * 6 + k) * 20, -380 * fly + 260 * fly * fly
            rot = fly * (3 + k)
        else:
            ox = oy = rot = 0.0
        bx, by = hx + dx + ox, hy - 98 + oy
        pts = []
        for j in range(8):
            u = j / 7
            px = math.sin(u * 3 + k) * 10
            py = -u * 55
            pts.append((bx + px * math.cos(rot) - py * math.sin(rot), by + px * math.sin(rot) + py * math.cos(rot)))
        line(d, c, pts, INK, 5)
    # eyes
    ey = hy - 2
    look_down = T_NO[2] - 0.1 <= tt < T_PAUSE + 0.6
    for sx in (-1, 1):
        ex = hx + sx * 34
        if shock:
            ell(d, c, ex, ey, 30, 34, (255, 255, 255), INK, 5)
            ell(d, c, ex, ey, 5, 5, INK, None)
            line(d, c, [(ex - 20, ey - 52 - 6 * sx * 0), (ex + 20, ey - 58)], INK, 6)
        elif blink(tt, 1.9 + nerv * 0.3) and not look_down:
            line(d, c, [(ex - 14, ey), (ex + 14, ey)], INK, 5)
        else:
            ell(d, c, ex, ey, 21, 25, (255, 255, 255), INK, 4)
            py = 9 if look_down else 0
            px = 6 if (not look_down and tt < T_FLAT) else 0
            ell(d, c, ex + px, ey + py, 9, 10, INK, None)
            # worried brows: inner ends up
            line(d, c, [(ex - sx * 4, ey - 44 - 4 * nerv), (ex + sx * 22, ey - 32)], INK, 6)
    # blush on "Не-ет…"
    if look_down:
        for sx in (-1, 1):
            ell(d, c, hx + sx * 52, hy + 38, 20, 11, (255, 140, 140), None)
    # sweat drops
    for k in range(nerv + (1 if tt > T_PAUSE else 0)):
        sx = (-1, 1, -1, 1)[k]
        ph = (tt * 0.8 + k * 0.37) % 1.0
        x = hx + sx * (70 + k * 6)
        y = hy - 50 + ph * 70
        poly(d, c, [(x, y - 16), (x - 10, y + 4), (x + 10, y + 4)], (150, 215, 255), None)
        ell(d, c, x, y + 4, 10, 10, (150, 215, 255), INK, 3)
    # mouth
    my = hy + 52
    if shock:
        ell(d, c, hx, my + 6, 26, 30 + 4 * math.sin(tt * 20), (110, 30, 40), INK, 5)
    elif talk > 0.06:
        ell(d, c, hx, my, 16 + 5 * talk, 4 + 22 * talk, (150, 40, 50), INK, 4)
    else:
        pts = [(hx - 22 + 44 * k / 8, my + 4 * math.sin(k * 1.6 + tt * 6)) for k in range(9)]
        line(d, c, pts, INK, 5)   # wobbly nervous mouth


# ---------------------------------------------------------------- overlays (screen space)
def wrap(txt, f, maxw, d):
    words, lines, cur = txt.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if d.textlength(test, font=f) <= maxw or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_headline(d, tt):
    if tt >= T_CTA:
        return
    f = font(F_HEAD, 50 * SS)
    lines = TXT["head"]
    y = 175 * SS
    for i, ln in enumerate(lines):
        tw = d.textlength(ln, font=f)
        pad = 26 * SS
        top = y + i * 82 * SS
        d.rounded_rectangle([540 * SS - tw / 2 - pad, top - 40 * SS, 540 * SS + tw / 2 + pad, top + 40 * SS],
                            radius=16 * SS, fill=(255, 255, 255))
        text_c(d, (540 * SS, top), ln, f, INK)


def draw_icon(d, kind, x, y, s):
    """x,y,s already in supersampled screen units."""
    if kind == 0:   # cigarette
        d.rounded_rectangle([x - 40 * s, y - 8 * s, x + 30 * s, y + 8 * s], radius=3 * s, fill=(255, 255, 255), outline=INK, width=int(3 * s))
        d.rectangle([x + 18 * s, y - 8 * s, x + 30 * s, y + 8 * s], fill=(255, 120, 40), outline=INK, width=int(3 * s))
        d.rectangle([x - 40 * s, y - 8 * s, x - 22 * s, y + 8 * s], fill=(230, 170, 90), outline=INK, width=int(3 * s))
        d.arc([x + 22 * s, y - 40 * s, x + 44 * s, y - 12 * s], 90, 270, fill=(150, 150, 160), width=int(4 * s))
    elif kind == 1:  # beer
        d.rounded_rectangle([x - 22 * s, y - 22 * s, x + 18 * s, y + 30 * s], radius=5 * s, fill=(250, 190, 40), outline=INK, width=int(3 * s))
        d.arc([x + 8 * s, y - 12 * s, x + 34 * s, y + 18 * s], 270, 90, fill=INK, width=int(5 * s))
        for k in range(3):
            d.ellipse([x - 26 * s + k * 15 * s, y - 36 * s, x - 6 * s + k * 15 * s, y - 16 * s], fill=(255, 255, 255), outline=INK, width=int(3 * s))
    else:            # heart
        r = 15 * s
        d.ellipse([x - 2 * r, y - 1.6 * r, x, y + 0.4 * r], fill=RED, outline=INK, width=int(3 * s))
        d.ellipse([x, y - 1.6 * r, x + 2 * r, y + 0.4 * r], fill=RED, outline=INK, width=int(3 * s))
        d.polygon([(x - 1.95 * r, y - 0.3 * r), (x, y + 1.9 * r), (x + 1.95 * r, y - 0.3 * r)], fill=RED)
        d.line([(x - 1.95 * r, y - 0.2 * r), (x, y + 1.9 * r), (x + 1.95 * r, y - 0.2 * r)], fill=INK, width=int(3 * s))


def stamp(img, txt, cx, cy, size, rot, alpha, scale):
    """Red rubber stamp, composited onto img (supersampled coords)."""
    f = font(F_HEAD, size * scale)
    tmp = Image.new("L", (1, 1))
    tw = ImageDraw.Draw(tmp).textlength(txt, font=f)
    pw, ph = int(tw + 60 * scale * SS / 2), int(size * scale * 1.5)
    layer = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    col = (220, 30, 45, int(235 * alpha))
    ld.rounded_rectangle([4, 4, pw - 4, ph - 4], radius=int(12 * scale), outline=col, width=max(2, int(size * scale * 0.09)))
    ld.text((pw / 2, ph / 2), txt, font=f, fill=col, anchor="mm")
    layer = layer.rotate(rot, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


def draw_card(img, d, tt):
    if tt < T_Q[0] - 0.1 or tt >= T_CTA:
        return
    p = ease_back((tt - (T_Q[0] - 0.1)) / 0.35)
    x0, y0, cw, ch = 40, 370, 480, 400
    ox = lerp(-520, 0, p)
    X = lambda v: (x0 + ox + v) * SS
    Y = lambda v: (y0 + v) * SS
    # shadow + paper
    d.rounded_rectangle([X(8), Y(10), X(cw + 8), Y(ch + 10)], radius=18 * SS, fill=(0, 0, 0, 60))
    d.rounded_rectangle([X(0), Y(0), X(cw), Y(ch)], radius=18 * SS, fill=(255, 253, 246), outline=INK, width=5 * SS)
    d.rounded_rectangle([X(cw / 2 - 70), Y(-22), X(cw / 2 + 70), Y(18)], radius=10 * SS, fill=(150, 156, 170), outline=INK, width=4 * SS)
    text_c(d, (X(cw / 2), Y(62)), TXT["card"], font(F_HEAD, (36 if len(TXT["card"]) < 10 else 30) * SS), INK)
    d.line([X(30), Y(98), X(cw - 30), Y(98)], fill=(200, 200, 210), width=3 * SS)
    labels = TXT["labels"]
    for k in range(3):
        if tt < T_Q[k]:
            continue
        ry = 160 + k * 90
        a = ease_back((tt - T_Q[k]) / 0.3)
        draw_icon(d, k, X(64), Y(ry), SS * (0.4 + 0.6 * a))
        f = font(F_HAND, 50 * SS)
        txt = labels[k]
        # handwriting reveal
        rev = clamp01((tt - T_Q[k]) / 0.45)
        n = max(1, int(round(len(txt) * rev)))
        d.text((X(118), Y(ry)), txt[:n], font=f, fill=(30, 50, 140), anchor="lm")
        d.line([X(30), Y(ry + 44), X(cw - 30), Y(ry + 44)], fill=(225, 225, 232), width=2 * SS)
        if tt >= T_NO[k]:
            sp = clamp01((tt - T_NO[k]) / 0.16)
            sc = lerp(2.0, 1.0, ease_out(sp))
            stamp(img, TXT["no"], X(cw - 82), Y(ry), (36 if len(TXT["no"]) < 4 else 30) * SS, (-12, 8, -6)[k], sp, sc)
    if tt >= T_STAMP:
        sp = clamp01((tt - T_STAMP) / 0.14)
        sc = lerp(2.6, 1.0, ease_out(sp))
        stamp(img, TXT["final"], X(cw / 2), Y(ch / 2 + 50), 46 * SS, 12, sp, sc)


def draw_caption(d, tt):
    i = active_line(tt)
    if i is not None:
        ln = LN[i]
        who = ln["who"]
        col = PAT_COL if who == "pat" else DOC_COL
        p = ease_back((tt - ln["start"] + 0.08) / 0.22)
        size = 84 if len(ln["text"]) < 20 else 74
        if i == 7:
            size = 80
        f = font(F_CAP, size * SS * (0.85 + 0.15 * p))
        lines = wrap(ln["text"].upper(), f, 960 * SS, d)
        lh = size * 1.12 * SS
        y0 = 1450 * SS - (len(lines) - 1) * lh / 2
        # speaker chip
        chip = TXT["chip_pat"] if who == "pat" else TXT["chip_doc"]
        fc = font(F_HEAD, 30 * SS)
        tw = d.textlength(chip, font=fc)
        cy = y0 - lh / 2 - 52 * SS
        d.rounded_rectangle([540 * SS - tw / 2 - 22 * SS, cy - 28 * SS, 540 * SS + tw / 2 + 22 * SS, cy + 28 * SS],
                            radius=28 * SS, fill=col, outline=INK, width=4 * SS)
        text_c(d, (540 * SS, cy), chip, fc, (255, 255, 255))
        # words, current word highlighted
        # map TTS word boundaries (may span several tokens, e.g. "Frau Doktor") to tokens
        cur_w, tok_i = set(), 0
        for w in ln["words"]:
            nt = max(1, len(w["text"].split()))
            if w["start"] - 0.05 <= tt:
                cur_w = set(range(tok_i, tok_i + nt))
            tok_i += nt
        widx = 0
        for li, l in enumerate(lines):
            tokens = l.split()
            space = d.textlength(" ", font=f)
            total = d.textlength(l, font=f)
            x = 540 * SS - total / 2
            y = y0 + li * lh
            for tok in tokens:
                fill = YEL if widx in cur_w else (255, 255, 255)
                d.text((x, y), tok, font=f, fill=fill, anchor="lm", stroke_width=9 * SS, stroke_fill=INK)
                x += d.textlength(tok, font=f) + space
                widx += 1
    # stage direction during the pause
    if T_GLASS0 - 0.2 <= tt < T_PUNCH - 0.1:
        a = clamp01((tt - T_GLASS0 + 0.2) / 0.3)
        f = font(F_HAND, 92 * SS)
        txt = TXT["stage"]
        text_c(d, (540 * SS, 1540 * SS), txt, f, (255, 255, 255, int(255 * a)), 8 * SS, (28, 30, 36, int(255 * a)))


def vignette(size):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a = np.clip((r - 0.45) / 0.75, 0, 1) ** 1.5
    return a


VIG = None


def draw_cta(img, d, tt):
    if tt < T_CTA:
        return
    p = ease_out((tt - T_CTA) / 0.3)
    d.rectangle([0, 0, W * SS, H * SS], fill=(14, 16, 22, int(170 * p)))
    s1 = ease_back((tt - T_CTA) / 0.35)
    base1 = 82
    while font(F_HEAD, base1 * SS).getlength(TXT["cta1"]) > 960 * SS:
        base1 -= 2
    f1 = font(F_HEAD, base1 * SS * (0.6 + 0.4 * s1))
    text_c(d, (540 * SS, 620 * SS), TXT["cta1"], f1, YEL, 10 * SS)
    s2 = ease_back((tt - T_CTA - 0.25) / 0.35)
    if tt > T_CTA + 0.25:
        f2 = font(F_HEAD, 54 * SS * (0.6 + 0.4 * s2))
        text_c(d, (540 * SS, 740 * SS), TXT["cta2"], f2, (255, 255, 255), 8 * SS)
    if tt > T_CTA + 0.55:
        for k in range(3):
            tk = T_CTA + 0.55 + k * 0.18
            if tt < tk:
                continue
            sk = ease_back((tt - tk) / 0.25)
            cx = (540 + (k - 1) * 290) * SS
            cy = 900 * SS
            sc = 0.5 + 0.5 * sk
            d.rounded_rectangle([cx - 125 * SS * sc, cy - 62 * SS * sc, cx + 125 * SS * sc, cy + 62 * SS * sc],
                                radius=20 * SS, fill=RED, outline=(255, 255, 255), width=6 * SS)
            text_c(d, (cx, cy), TXT["no"], font(F_HEAD, (64 if len(TXT["no"]) < 4 else 54) * SS * sc), (255, 255, 255))
    if tt > T_CTA + 1.2:
        a = clamp01((tt - T_CTA - 1.2) / 0.3)
        bob = math.sin((tt - T_CTA) * 7) * 12 * SS
        text_c(d, (540 * SS, 1090 * SS), TXT["cta3"], font(F_HAND, 96 * SS),
               (255, 255, 255, int(255 * a)), 6 * SS, (0, 0, 0, int(255 * a)))
        ax, ay = 540 * SS, 1210 * SS + bob
        d.polygon([(ax - 50 * SS, ay - 20 * SS), (ax + 50 * SS, ay - 20 * SS), (ax, ay + 45 * SS)], fill=(255, 255, 255, int(255 * a)))
        d.rectangle([ax - 18 * SS, ay - 80 * SS, ax + 18 * SS, ay - 18 * SS], fill=(255, 255, 255, int(255 * a)))


# ---------------------------------------------------------------- frame
def render_frame(fi):
    tt = fi / FPS
    cx, cy, z, shake = cam_at(tt)
    sx = math.sin(tt * 91) * shake
    sy = math.cos(tt * 77) * shake
    c = Cam(cx, cy, z, sx, sy)
    img = Image.new("RGBA", (W * SS, H * SS), WALL + (255,))
    d = ImageDraw.Draw(img, "RGBA")
    draw_room(d, c, tt)
    draw_patient(d, c, tt)
    draw_doctor(d, c, tt)
    draw_desk_front(d, c)
    # dramatic darkening during the glasses moment
    dark = 0.0
    if T_GLASS0 - 0.2 <= tt < T_FLAT:
        dark = clamp01((tt - T_GLASS0 + 0.2) / 0.6) * 0.55
    img = img.resize((W, H), Image.LANCZOS)
    if dark > 0:
        global VIG
        if VIG is None:
            VIG = vignette((W, H))
        arr = np.asarray(img).astype(np.float32)
        arr[..., :3] *= (1 - VIG * dark)[..., None]
        img = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")
    # overlays at SS for crisp text
    ov = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov, "RGBA")
    draw_headline(od, tt)
    draw_card(ov, od, tt)
    draw_caption(od, tt)
    draw_cta(ov, od, tt)
    # white flash on the flatline
    if T_FLAT <= tt < T_FLAT + 0.12:
        od.rectangle([0, 0, W * SS, H * SS], fill=(255, 255, 255, int(160 * (1 - (tt - T_FLAT) / 0.12))))
    ov = ov.resize((W, H), Image.LANCZOS)
    img.alpha_composite(ov)
    return img.convert("RGB").tobytes()


# ---------------------------------------------------------------- audio
def build_audio():
    n = int(T_END * SR) + SR
    out = np.zeros(n, np.float32)

    def add(sig, at, gain=1.0):
        k = int(at * SR)
        if k >= n:
            return
        sig = sig[: n - k]
        out[k:k + len(sig)] += sig * gain

    tt = lambda dur: np.arange(int(dur * SR)) / SR
    for ln in LN:
        add(ln["audio"], ln["start"], 1.0)
    # monitor beeps
    tb = tt(0.09)
    beep = np.sin(2 * np.pi * 1046 * tb) * np.minimum(1, (0.09 - tb) / 0.02) * np.minimum(1, tb / 0.004)
    for b in BEATS:
        add(beep, b + 0.09, 0.10)
    # flatline
    tf = tt(2.0)
    flat = np.sin(2 * np.pi * 1046 * tf) * np.minimum(1, (2.0 - tf) / 0.6) * np.minimum(1, tf / 0.005)
    add(flat, T_FLAT, 0.16)
    # stamp thuds
    tk = tt(0.25)
    rng = np.random.default_rng(3)
    thud = (np.sin(2 * np.pi * (70 + 60 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 18)
            + rng.normal(0, 1, len(tk)) * np.exp(-tk * 60) * 0.5)
    for tn in T_NO:
        add(thud, tn + 0.02, 0.35)
    add(thud, T_STAMP, 0.6)
    # whoosh on the card + CTA
    tw = tt(0.35)
    noise = rng.normal(0, 1, len(tw))
    noise = np.convolve(noise, np.ones(30) / 30, mode="same")
    wh = noise * np.sin(np.pi * tw / 0.35) ** 2
    add(wh, T_Q[0] - 0.12, 0.6)
    add(wh, T_CTA - 0.05, 0.6)
    # dramatic sting "dun dun DUUUN" during the glasses moment
    def tone(f, dur, decay):
        x = tt(dur)
        s = sum(np.sign(np.sin(2 * np.pi * f * h * x)) / h for h in (1, 2, 3)) * 0.33
        s += np.sin(2 * np.pi * f / 2 * x) * 0.8
        s = np.convolve(s, np.ones(8) / 8, mode="same")
        return s * np.exp(-x * decay) * np.minimum(1, x / 0.01)
    def timp(dur=0.8):
        x = tt(dur)
        return np.sin(2 * np.pi * (55 + 40 * np.exp(-x * 12)) * x) * np.exp(-x * 4)
    s0 = T_GLASS0 - 0.05
    add(tone(146.8, 0.4, 5), s0, 0.22)
    add(timp(), s0, 0.5)
    add(tone(155.6, 0.4, 5), s0 + 0.42, 0.22)
    add(timp(), s0 + 0.42, 0.5)
    long = tone(138.6, 1.8, 1.6) * (1 + 0.25 * np.sin(2 * np.pi * 6 * tt(1.8)))
    add(long, s0 + 0.9, 0.26)
    add(timp(1.4), s0 + 0.9, 0.7)
    # CTA ding
    td = tt(0.8)
    ding = (np.sin(2 * np.pi * 1318 * td) + 0.5 * np.sin(2 * np.pi * 1760 * td)) * np.exp(-td * 5)
    add(ding, T_CTA + 0.55, 0.12)
    add(ding, T_CTA + 0.73, 0.12)
    add(ding, T_CTA + 0.91, 0.12)
    out = out[: int(T_END * SR)]
    out /= max(1.0, np.max(np.abs(out)) / 0.95)
    p = BUILD / "mix.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    return p


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        sd = BUILD / "stills"
        sd.mkdir(parents=True, exist_ok=True)
        for s in sys.argv[2:]:
            fi = int(float(s) * FPS)
            Image.frombytes("RGB", (W, H), render_frame(fi)).save(sd / f"t{float(s):05.2f}.png")
        print("stills ->", sd)
        return
    print(f"duration {T_END:.2f}s, punch {T_PUNCH:.2f}s, flat {T_FLAT:.2f}s, frames {NFRAMES}")
    wav = build_audio()
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(wav),
                           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                           "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "44100", "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-shortest", "-movflags", "+faststart",
                           str(OUT)], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for k, fr in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=4)):
            ff.stdin.write(fr)
            if k % 60 == 0:
                print(f"frame {k}/{NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("->", OUT)


if __name__ == "__main__":
    main()
