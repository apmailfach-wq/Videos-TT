"""'Überlebst du das?' Folge 2 – Auto stürzt in den Fluss. 1080x1920, 30 fps, exactly 30 s.

python3 render.py               -> ../../ueberleben-folge2.mp4
python3 render.py preview 1 5   -> stills in build/ueberleben/stills
"""
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
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import shots as S
from core import bloom  # noqa: E402
from draw import (W, H, FPS, OUT, RED, font, clamp01, lerp, ease_out, ease_in, ease_io, paste_c, zoom_frame,
                  text_img, emoji, glow_dot)

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "ueberleben"
BUILD.mkdir(parents=True, exist_ok=True)
OUTFILE = ROOT / os.environ.get("VIDEO_OUT", "ueberleben-folge2.mp4")
TOTAL = 30.0
NFRAMES = int(TOTAL * FPS)
F_CAP = "/usr/share/fonts/opentype/inter/Inter-Black.otf"


def A(f):
    return lambda t, d, T: f(t, d)


# (start, end, fn, underwater?)
SCHED = [
    (0.0, 1.0, A(S.shot_bridge), False),
    (1.0, 2.0, A(S.shot_fall_side), False),
    (2.0, 3.0, A(S.shot_under_entry), True),
    (3.0, 4.0, A(S.shot_under_impact), True),
    (4.0, 5.5, S.shot_interior_wide, False),
    (5.5, 6.8, S.shot_interior_close, False),
    (6.8, 8.0, S.shot_interior_low, False),
    (8.0, 9.5, S.shot_door_handle, False),
    (9.5, 11.0, S.shot_outside_pressure, True),
    (11.0, 12.5, S.shot_topdown, True),
    (12.5, 14.0, S.shot_dark, False),
    (14.0, 15.0, None, False),  # rewind
    (15.0, 16.0, S.shot_belt, False),
    (16.0, 17.0, S.shot_window_down, False),
    (17.0, 18.5, S.shot_squeeze, True),
    (18.5, 20.0, S.shot_swim_up, True),
    (20.0, 21.0, S.shot_surface, False),
    (21.0, 22.0, S.shot_breath, False),
    (22.0, 23.0, S.shot_stuck, False),
    (23.0, 24.0, S.shot_hammer_grab, False),
    (24.0, 25.0, S.shot_corner, False),
    (25.0, 26.0, S.shot_shatter, False),
    (26.0, 28.0, lambda t, d, T: S.shot_portrait(t, d, T, False), False),
    (28.0, 30.0, lambda t, d, T: S.shot_portrait(t, d, T, True), False),
]
CUTS = [s[0] for s in SCHED[1:]]


def shot_at(T):
    for s in SCHED:
        if s[0] <= T < s[1]:
            return s
    return SCHED[-1]


def base_scene(T):
    s = shot_at(T)
    if s[2] is None:
        return None, s
    return s[2](T - s[0], s[1] - s[0], T), s


# ---------------------------------------------------------------- survival bar
BAR_KEYS = [(0, 58), (1.6, 41), (4, 34), (8, 28), (9, 20), (11, 12), (13.2, 3), (14.0, 3), (14.95, 34), (15.1, 40),
            (16, 52), (17, 66), (18.5, 78), (20, 88), (21, 98), (22, 98), (22.6, 62), (24.2, 58), (24.5, 86),
            (25.5, 99), (26.0, 99), (26.35, 50), (30.0, 50)]


def bar_value(T):
    for (a, va), (b, vb) in zip(BAR_KEYS, BAR_KEYS[1:]):
        if a <= T <= b:
            return lerp(va, vb, ease_io((T - a) / (b - a)))
    return BAR_KEYS[-1][1]


def bar_color(v):
    if v < 30:
        return (236, 38, 44)
    if v < 60:
        return tuple(int(lerp(a, b, (v - 30) / 30)) for a, b in zip((236, 38, 44), (255, 196, 40)))
    if v < 80:
        return tuple(int(lerp(a, b, (v - 60) / 20)) for a, b in zip((255, 196, 40), (60, 220, 100)))
    return (60, 220, 100)


@lru_cache(maxsize=256)
def label_img(text, size, stroke):
    return text_img(text, size, (255, 255, 255), F_CAP, stroke=stroke, max_w=2000)


def draw_bar(frame, T):
    v = bar_value(T)
    dv = abs(bar_value(T + 0.05) - v)
    sh = min(10, dv * 3)
    rnd = random.Random(int(T * 30))
    ox, oy = rnd.uniform(-sh, sh), rnd.uniform(-sh, sh)
    ss = 2
    bw, bh = 1080, 260
    lay = Image.new("RGBA", (bw * ss, bh * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    x0, y0, x1, y1 = 80, 168, 1000, 222
    col = bar_color(v)
    pulse = 0.5 + 0.5 * math.sin(T * 14) if v < 25 else 0
    d.rounded_rectangle([x0 * ss - 10, y0 * ss - 10, x1 * ss + 10, y1 * ss + 10], 40 * ss, fill=(0, 0, 0, 255))
    d.rounded_rectangle([x0 * ss, y0 * ss, x1 * ss, y1 * ss], 30 * ss, fill=(30, 32, 40, 255))
    fx = x0 + (x1 - x0) * clamp01(v / 100)
    if fx - x0 > 20:
        d.rounded_rectangle([x0 * ss, y0 * ss, fx * ss, y1 * ss], 30 * ss, fill=col + (255,))
        d.rounded_rectangle([(x0 + 12) * ss, (y0 + 8) * ss, (fx - 12) * ss, (y0 + 20) * ss], 8 * ss,
                            fill=(255, 255, 255, 90))
    for k in range(1, 10):
        xx = x0 + (x1 - x0) * k / 10
        d.line([(xx * ss, (y1 - 14) * ss), (xx * ss, y1 * ss)], fill=(0, 0, 0, 120), width=3 * ss)
    small = lay.reduce(ss)
    if pulse:
        g = Image.new("RGBA", small.size, (236, 38, 44, 0))
        g.putalpha(small.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda a: int(a * pulse)))
        frame.alpha_composite(g, (int(ox), int(oy)))
    frame.alpha_composite(small, (int(ox), int(oy)))
    lab = label_img("ÜBERLEBEN", 60, 9)
    frame.alpha_composite(lab, (int(60 + ox), int(70 + oy)))
    pct = "??%" if 26.35 <= T else f"{int(round(v))}%"
    pim = label_img(pct, 60, 9)
    pc = (255, 255, 255)
    frame.alpha_composite(pim, (int(1020 - pim.width + ox), int(64 + oy)))
    del pc


# ---------------------------------------------------------------- impact captions
# (t_in, t_out, y_center_of_first_line, size, lines=[[(segment, t_appear), ...], ...])
CAPS = [
    (0.12, 2.0, 1300, 118, [[("DIE MEISTEN", 0.12)], [("STERBEN HIER.", 0.42)]]),
    (4.05, 8.0, 420, 108, [[("WAS MACHST DU?", 4.05)]]),
    (8.3, 14.0, 450, 124, [[("FALSCH.", 8.3)]]),
    (9.55, 14.0, 600, 84, [[("DAS WASSER", 9.55)], [("DRÜCKT DIE TÜR ZU.", 9.85)]]),
    (14.05, 15.0, 900, 150, [[("NOCHMAL.", 14.05)]]),
    (15.05, 22.0, 450, 108, [[("GURT.", 15.05), ("FENSTER.", 16.05)], [("RAUS.", 17.05), ("SOFORT.", 18.55)]]),
    (22.05, 26.0, 450, 104, [[("FENSTER", 22.05)], [("KLEMMT?", 22.3)]]),
    (24.0, 26.0, 1420, 96, [[("IN DIE ECKE", 24.0)], [("SCHLAGEN!", 24.32)]]),
    (26.35, 30.0, 400, 112, [[("EHRLICH:", 26.35)], [("A ODER B? 👇", 26.75)]]),
    (27.6, 30.0, 640, 54, [[("Folge 3 morgen", 27.6)]]),
]


@lru_cache(maxsize=128)
def seg_img(text, size):
    stroke = max(5, size // 9)
    if "👇" in text:
        base = seg_img(text.replace("👇", "").strip(), size)
        em = emoji("👇", int(size * 1.05))
        im = Image.new("RGBA", (base.width + em.width + 10, max(base.height, em.height)), (0, 0, 0, 0))
        im.alpha_composite(base, (0, (im.height - base.height) // 2))
        im.alpha_composite(em, (base.width - 10, (im.height - em.height) // 2))
        return im
    t = text_img(text, size, (255, 255, 255), F_CAP, stroke=stroke, max_w=4000)
    sh = Image.new("RGBA", (t.width + 12, t.height + 14), (0, 0, 0, 0))
    blk = Image.new("RGBA", t.size, (0, 0, 0, 0))
    blk.putalpha(t.getchannel("A").point(lambda a: int(a * 0.75)))
    sh.alpha_composite(blk, (10, 12))
    sh.alpha_composite(t, (0, 0))
    return sh


@lru_cache(maxsize=None)
def cap_layout(ci):
    t_in, t_out, y, size, lines = CAPS[ci]
    out = []
    for li, line in enumerate(lines):
        while True:
            ims = [seg_img(s, size) for s, _ in line]
            gap = size * 0.3
            tot = sum(im.width - 40 for im in ims) + gap * (len(ims) - 1)
            if tot <= 1000 or size < 40:
                break
            size -= 4
        x = 540 - tot / 2
        for (s, ta), im in zip(line, ims):
            w = im.width - 40
            out.append((s, ta, size, x + w / 2, y + li * size * 1.12))
            x += w + gap
    return out


def impact_scale(age):
    if age < 0.08:
        return lerp(2.3, 0.88, ease_in(age / 0.08))
    if age < 0.18:
        return lerp(0.88, 1.06, ease_out((age - 0.08) / 0.1))
    if age < 0.3:
        return lerp(1.06, 1.0, ease_io((age - 0.18) / 0.12))
    return 1.0


def draw_caps(frame, T):
    for ci, (t_in, t_out, *_r) in enumerate(CAPS):
        if not (t_in <= T < t_out):
            continue
        for k, (s, ta, size, x, y) in enumerate(cap_layout(ci)):
            if T < ta:
                continue
            age = T - ta
            rnd = random.Random(int(T * FPS) * 31 + k * 7 + ci)
            amp = 26 * math.exp(-age / 0.1) + 2.2
            dx, dy = rnd.uniform(-amp, amp), rnd.uniform(-amp, amp)
            rot = (5 if (k + ci) % 2 else -5) * math.exp(-age / 0.08) + rnd.uniform(-0.6, 0.6)
            im = seg_img(s, size)
            if age < 0.1:
                g = glow_dot(int(im.width * 1.1), (255, 255, 255), 2.4)
                paste_c(frame, g.resize((int(im.width * 1.2), int(im.height * 1.6))), x, y, 1.0, 0.5 * (1 - age / 0.1))
            paste_c(frame, im, x + dx + 20, y + dy, impact_scale(age), 1.0, rot)


# ---------------------------------------------------------------- choice buttons + timer
@lru_cache(maxsize=16)
def button_img(label, state):
    ss = 2
    w, h = 900, 140
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    border = {"off": (255, 255, 255), "on": (236, 38, 44), "chosen": (255, 255, 255), "win": (255, 255, 255),
              "dim": (90, 90, 100)}[state]
    fill = {"off": (14, 16, 24, 225), "on": (40, 10, 14, 235), "chosen": (220, 32, 40, 255), "win": (40, 190, 90, 255),
            "dim": (14, 16, 24, 150)}[state]
    d.rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], 40 * ss, fill=(0, 0, 0, 255))
    d.rounded_rectangle([10 * ss, 10 * ss, (w - 10) * ss, (h - 10) * ss], 32 * ss, fill=border + (255,))
    d.rounded_rectangle([20 * ss, 20 * ss, (w - 20) * ss, (h - 20) * ss], 26 * ss, fill=fill)
    im = im.reduce(ss)
    t = text_img(label, 64, (255, 255, 255) if state != "dim" else (150, 150, 160), F_CAP, stroke=8, max_w=4000)
    im.alpha_composite(t, ((w - t.width) // 2, (h - t.height) // 2 + 2))
    if state in ("on", "chosen", "win"):
        g = Image.new("RGBA", (w + 80, h + 80), (0, 0, 0, 0))
        g.alpha_composite(im, (40, 40))
        glow = Image.new("RGBA", g.size, border + (0,))
        glow.putalpha(g.getchannel("A").filter(ImageFilter.GaussianBlur(18)))
        out = Image.new("RGBA", g.size, (0, 0, 0, 0))
        out.alpha_composite(glow)
        out.alpha_composite(g)
        return out
    p = Image.new("RGBA", (w + 80, h + 80), (0, 0, 0, 0))
    p.alpha_composite(im, (40, 40))
    return p


BTN = [("A: TÜR ÖFFNEN", 4.35, 1250), ("B: FENSTER RUNTER", 4.55, 1430)]


def draw_buttons(frame, T):
    show = 4.35 <= T < 8.35 or 14.62 <= T < 15.0
    if not show:
        return
    for i, (lab, ta, y) in enumerate(BTN):
        if T < ta and T < 14:
            continue
        age = T - ta if T < 14 else T - 14.62
        blink = int(T * 6 + i) % 2 == 0
        state = "on" if blink else "off"
        sc = impact_scale(age)
        if 7.9 <= T < 8.35:
            state = "chosen" if i == 0 else "dim"
            sc = 1.0 + (0.08 * math.sin((T - 7.9) / 0.45 * math.pi) if i == 0 else 0)
        if T >= 14.62:
            state = "win" if i == 1 else "dim"
            sc = impact_scale(age) if i == 1 else 1.0
        rnd = random.Random(int(T * FPS) + i * 3)
        j = 3 if state == "on" else 1
        paste_c(frame, button_img(lab, state), 540 + rnd.uniform(-j, j), y + rnd.uniform(-j, j), sc)


TIMER = [(4.6, "3"), (5.7, "2"), (6.8, "1")]


def draw_timer(frame, T):
    if not (4.6 <= T < 7.9):
        return
    cur = None
    for ta, dg in TIMER:
        if T >= ta:
            cur = (ta, dg)
    ta, dg = cur
    age = T - ta
    frac = 1 - clamp01(age / 1.1)
    cx, cy, R = 540, 610, 100
    hb = heart_pulse(T)
    ss = 2
    lay = Image.new("RGBA", (2 * (R + 30) * ss, 2 * (R + 30) * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    c = (R + 30) * ss
    d.ellipse([c - (R + 14) * ss, c - (R + 14) * ss, c + (R + 14) * ss, c + (R + 14) * ss], fill=(0, 0, 0, 230))
    d.ellipse([c - R * ss, c - R * ss, c + R * ss, c + R * ss], fill=(40, 6, 10, 240))
    d.arc([c - (R - 6) * ss, c - (R - 6) * ss, c + (R - 6) * ss, c + (R - 6) * ss], -90, -90 + 360 * frac,
          fill=(236, 38, 44, 255), width=16 * ss)
    lay = lay.reduce(ss)
    g = glow_dot(int(R * 3.4), (236, 38, 44), 2.0)
    paste_c(frame, g, cx, cy, 1.0 + 0.15 * hb, 0.55 + 0.3 * hb)
    paste_c(frame, lay, cx, cy, 1.0 + 0.06 * hb)
    num = text_img(dg, 150, (236, 38, 44), F_CAP, stroke=12, max_w=1000)
    paste_c(frame, num, cx, cy - 6, impact_scale(age) * (1 + 0.05 * hb))


BEATS = []
_t = 4.0
while _t < 8.1:
    BEATS.append(_t)
    _t += lerp(0.62, 0.36, (_t - 4) / 4)


def heart_pulse(T):
    v = 0.0
    for b in BEATS:
        a = T - b
        if 0 <= a < 0.4:
            v = max(v, math.exp(-a * 12) + 0.6 * math.exp(-max(0, a - 0.16) * 14) * (a > 0.16))
    return min(v, 1.0)


# ---------------------------------------------------------------- post effects
VIG = None
GRAIN = None


def init():
    global VIG, GRAIN
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.7)) ** 2)
    a = np.clip((v - 0.5) * 1.6, 0, 0.8)
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 3] = (a * 255).astype(np.uint8)
    VIG = Image.fromarray(arr, "RGBA")
    rng = np.random.default_rng(1)
    GRAIN = [rng.integers(-9, 10, (H // 2, W // 2, 1), dtype=np.int16) for _ in range(4)]


SHAKES = [(0.1, 30, 0.25), (0.95, 10, 0.2), (2.03, 34, 0.4), (3.0, 26, 1.0), (3.6, 30, 0.4), (8.15, 14, 0.15),
          (8.55, 14, 0.15), (8.92, 14, 0.15), (9.28, 14, 0.15), (12.8, 12, 0.3), (15.3, 16, 0.2), (20.3, 20, 0.3),
          (24.32, 34, 0.35), (25.0, 18, 0.3)]


def shake(T):
    a = 0.0
    for t0, amp, dur in SHAKES:
        if t0 <= T < t0 + dur:
            a = max(a, amp * (1 - (T - t0) / dur))
    for c in CUTS:
        if 0 <= T - c < 0.12:
            a = max(a, 9 * (1 - (T - c) / 0.12))
    if 4.0 <= T < 8.0:
        a = max(a, 5 * heart_pulse(T))
    return a


def grade(img, T, s):
    arr = np.asarray(img.convert("RGB")).astype(np.int16)
    if s[3]:  # underwater: push into blue-green, crush reds
        arr = (arr * np.array([0.36, 0.6, 0.68])).astype(np.int16) + np.array([0, 3, 8], np.int16)
    if 12.5 <= T < 14.0:  # lights out: everything turns blue
        k = clamp01((T - 12.85) / 0.3)
        lum = arr.mean(axis=2, keepdims=True)
        blue = lum * np.array([0.25, 0.55, 1.25]) + np.array([0, 6, 28])
        arr = (arr * (1 - k) + blue * k * 0.8).astype(np.int16)
    if 8.0 <= T < 14.0:  # danger: red pulse at the edges handled by vignette tint below
        pass
    g = GRAIN[int(T * FPS) % 4]
    g = np.repeat(np.repeat(g, 2, axis=0), 2, axis=1)
    arr = arr + g
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def red_edges(frame, amt):
    if amt <= 0.01:
        return
    r = Image.new("RGBA", (W, H), (200, 0, 10, 0))
    r.putalpha(VIG.getchannel("A").point(lambda a: int(a * amt)))
    frame.alpha_composite(r)


def chroma(frame, amt):
    if amt < 1:
        return frame
    r, g, b, a = frame.split()
    r = ImageChops.offset(r, int(amt), 0)
    b = ImageChops.offset(b, -int(amt), 0)
    return Image.merge("RGBA", (r, g, b, a))


def rewind_fx(T):
    u = (T - 14.0) / 1.0
    Ts = 13.9 - ease_in(u) * 9.6
    img, s = base_scene(Ts)
    img = grade(img, Ts, s)
    arr = np.asarray(img.convert("RGB")).astype(np.int16)
    lum = arr.mean(axis=2, keepdims=True)
    arr = (arr * 0.45 + lum * np.array([0.7, 0.8, 1.0]) * 0.55).astype(np.int16)
    arr[::4] = arr[::4] * 0.7
    rnd = random.Random(int(T * FPS))
    for _ in range(3):
        y0 = rnd.randint(0, H - 60)
        h = rnd.randint(8, 50)
        arr[y0:y0 + h] = np.roll(arr[y0:y0 + h], rnd.randint(-80, 80), axis=1) + 40
    band = int((u * 3 % 1) * H)
    arr[band:band + 40] = arr[band:band + 40] // 2 + 90
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    img = chroma(img, 10)
    img = zoom_frame(img, 1.04 + 0.02 * math.sin(T * 40), 540 + rnd.uniform(-10, 10), 960)
    d = ImageDraw.Draw(img)
    for k in range(2):
        x = 90 + k * 70
        d.polygon([(x + 60, 330), (x + 60, 410), (x, 370)], fill=(255, 255, 255), outline=(0, 0, 0), width=5)
    if int(T * 4) % 2 == 0:
        d.ellipse([280, 345, 320, 385], fill=(236, 38, 44))
    return img


BLUR_SHOTS = {0.0, 3.0, 15.0, 23.0, 24.0, 17.0}


def caustics(T, strength=1.0):
    sw, sh = 216, 384
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    a = np.sin(xx * 0.11 + np.sin(yy * 0.07 + T * 1.4) * 2.2 + T * 1.1)
    b = np.sin(yy * 0.09 + np.sin(xx * 0.08 - T * 1.2) * 2.4 - T * 0.9)
    c = np.clip(1 - np.abs(a + b) * 0.5, 0, 1) ** 7
    depth = np.clip(1.15 - yy / sh, 0.15, 1)[..., None]
    col = np.array([90, 255, 230], np.float32)
    arr = (c[..., None] * depth * col * 0.55 * strength).astype(np.uint8)
    return Image.fromarray(arr, "RGB").resize((W, H), Image.BILINEAR)


def glow(frame, strength=0.8, thresh=212):
    small = frame.convert("RGB").resize((W // 4, H // 4), Image.BILINEAR)
    arr = np.asarray(small).astype(np.float32)
    lum = arr @ np.array([0.3, 0.59, 0.11], np.float32)
    mask = np.clip((lum - thresh) / (255 - thresh), 0, 1)[..., None]
    b = Image.fromarray((arr * mask).astype(np.uint8))
    g = ImageChops.add(b.filter(ImageFilter.GaussianBlur(5)), b.filter(ImageFilter.GaussianBlur(16)))
    g = Image.fromarray((np.asarray(g).astype(np.float32) * strength).clip(0, 255).astype(np.uint8))
    return ImageChops.screen(frame.convert("RGB"), g.resize((W, H), Image.BILINEAR)).convert("RGBA")


def whip(frame, amt):
    arr = np.asarray(frame.convert("RGB")).astype(np.uint16)
    acc = arr.copy()
    k = 1
    for o in (-2, -1, 1, 2):
        acc += np.roll(arr, int(o * amt), axis=1)
        k += 1
    return Image.fromarray((acc // k).astype(np.uint8), "RGB").convert("RGBA")


def render_frame(fi):
    T = fi / FPS
    s = shot_at(T)
    if s[2] is None:
        frame = rewind_fx(T)
    else:
        img, s = base_scene(T)
        if s[0] in BLUR_SHOTS:
            img2, _ = base_scene(max(s[0], T - 0.5 / FPS))
            img = Image.blend(img, img2, 0.5)
        frame = grade(img, T, s)
        if s[3]:
            frame = ImageChops.add(frame.convert("RGB"), caustics(T, 0.32)).convert("RGBA")
        frame = glow(frame, 0.8, 222 if s[3] else 210)
        lt = T - s[0]
        if lt < 0.1 and s[0] > 0:
            frame = whip(frame, 26 * (1 - lt / 0.1))
        z = 1.0
        if lt < 0.15 and s[0] > 0:
            z = 1 + 0.08 * (1 - ease_out(lt / 0.15))
        a = shake(T)
        rnd = random.Random(fi * 13)
        if a > 0.5 or z > 1.001:
            frame = zoom_frame(frame, z + a / 400, 540 + rnd.uniform(-a, a), 960 + rnd.uniform(-a, a))
        if a > 12:
            frame = chroma(frame, a / 4)
        frame.alpha_composite(VIG)
        if 8.0 <= T < 14.0:
            red_edges(frame, 0.35 + 0.35 * math.sin(T * 9) ** 2)
        if 4.0 <= T < 8.0:
            red_edges(frame, 0.45 * heart_pulse(T))
        if abs(T - 24.32) < 0.07 or abs(T - 2.04) < 0.06 or 0.06 <= T < 0.13 or abs(T - 20.3) < 0.05:
            frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 150)))
    draw_bar(frame, T)
    draw_timer(frame, T)
    draw_buttons(frame, T)
    draw_caps(frame, T)
    return frame.convert("RGB").tobytes()


# ---------------------------------------------------------------- audio
SR = 48000


def lp(x, fc):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, fc, "low", fs=SR, output="sos"), x)


def hp(x, fc):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, fc, "high", fs=SR, output="sos"), x)


def bp(x, f0, f1):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(2, [f0, f1], "band", fs=SR, output="sos"), x)


def tvec(dur):
    return np.arange(int(dur * SR)) / SR


def envd(dur, a=0.003, d=0.2):
    t = tvec(dur)
    return np.minimum(1, t / a) * np.exp(-t / d)


def sine(f, dur, a=0.003, d=0.2):
    t = tvec(dur)
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(f, t.shape)) / SR
    return np.sin(ph) * envd(dur, a, d)


def noise(dur, rng):
    return rng.standard_normal(int(dur * SR))


def fx_hit(rng, g=1.0):
    dur = 0.7
    t = tvec(dur)
    boom = np.sin(2 * np.pi * (45 + 80 * np.exp(-t * 20)) * t) * np.exp(-t * 6)
    n = lp(noise(dur, rng), 1800) * np.exp(-t * 18) * 0.8
    return (boom + n) * g


def fx_whoosh(rng, dur=0.35):
    t = tvec(dur)
    x = bp(noise(dur, rng), 400, 3500)
    return x * np.sin(np.pi * t / dur) ** 2 * 0.8


def fx_crash(rng):
    dur = 1.6
    t = tvec(dur)
    n = hp(noise(dur, rng), 800) * np.exp(-t * 5)
    ring = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * np.exp(-t * (3 + k)) for k, f in
               enumerate((523, 811, 1307, 1922, 2650)))
    return n * 0.9 + ring * 0.18 + fx_hit(rng, 1.2)[: len(t)] if False else n * 0.9 + ring * 0.18


def fx_splash(rng):
    dur = 1.4
    t = tvec(dur)
    n = bp(noise(dur, rng), 300, 6000) * (np.minimum(1, t / 0.02) * np.exp(-t * 3.2))
    return n * 1.2


def fx_bubbles(rng, dur=1.5, rate=40):
    out = np.zeros(int(dur * SR))
    for _ in range(int(dur * rate)):
        st = rng.uniform(0, dur - 0.08)
        f0 = rng.uniform(300, 1200)
        d = rng.uniform(0.02, 0.07)
        tt = tvec(d)
        b = np.sin(2 * np.pi * (f0 * (1 + tt / d * 1.5)) * tt) * np.exp(-tt / d * 3) * rng.uniform(0.2, 0.6)
        i = int(st * SR)
        out[i:i + len(b)] += b
    return out


def fx_heart(g=1.0):
    def thump(f):
        t = tvec(0.25)
        return np.sin(2 * np.pi * (f + 40 * np.exp(-t * 30)) * t) * np.exp(-t * 18)
    a = thump(55)
    b = thump(48) * 0.7
    out = np.zeros(int(0.45 * SR))
    out[: len(a)] += a
    i = int(0.16 * SR)
    out[i:i + len(b)] += b
    return out * g


def fx_beep(f=880, dur=0.18):
    t = tvec(dur)
    return np.sign(np.sin(2 * np.pi * f * t)) * 0.3 * np.minimum(1, (dur - t) / 0.01) * np.minimum(1, t / 0.005)


def fx_clack(rng):
    t = tvec(0.12)
    return hp(noise(0.12, rng), 1500) * np.exp(-t * 60) + np.sin(2 * np.pi * 900 * t) * np.exp(-t * 50) * 0.5


def fx_groan(dur):
    t = tvec(dur)
    f = 70 + 15 * np.sin(2 * np.pi * 0.7 * t) + 6 * np.sin(2 * np.pi * 5 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sign(np.sin(ph)) * 0.4 + np.sin(ph * 2.01) * 0.3
    return lp(x, 400) * np.minimum(1, t / 0.3) * np.minimum(1, (dur - t) / 0.3)


def fx_powerdown():
    dur = 0.8
    t = tvec(dur)
    f = 900 * np.exp(-t * 4) + 40
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3) * 0.5


def fx_rewind(rng, dur=1.0):
    t = tvec(dur)
    f = 200 + 1800 * (t / dur) ** 1.5 + 60 * np.sin(2 * np.pi * 23 * t)
    saw = 2 * ((np.cumsum(f) / SR) % 1) - 1
    n = bp(noise(dur, rng), 2000, 8000) * 0.3
    return (lp(saw, 3000) * 0.5 + n) * np.minimum(1, t / 0.05)


def fx_click():
    t = tvec(0.05)
    return np.sin(2 * np.pi * 2500 * t) * np.exp(-t * 200)


def fx_motor(dur, rng, stutter=False):
    t = tvec(dur)
    f = 140 + 30 * t
    x = (2 * ((np.cumsum(f) / SR) % 1) - 1) * 0.4 + bp(noise(dur, rng), 800, 2000) * 0.15
    e = np.minimum(1, t / 0.03) * np.minimum(1, (dur - t) / 0.03)
    if stutter:
        e = e * (np.sin(2 * np.pi * 7 * t) > 0.2)
    return lp(x, 2500) * e


def fx_gasp(rng):
    dur = 0.7
    t = tvec(dur)
    n = bp(noise(dur, rng), 600, 3500)
    return n * np.sin(np.pi * np.clip(t / 0.5, 0, 1)) ** 1.5 * (1 + 0.6 * np.minimum(1, t / 0.4))


def fx_glass(rng, dur=1.6):
    out = np.zeros(int(dur * SR))
    for _ in range(90):
        st = rng.uniform(0, dur * 0.8) ** 1.6 / (dur * 0.8) ** 0.6
        f = rng.uniform(2500, 7500)
        d = rng.uniform(0.05, 0.25)
        tt = tvec(d)
        b = np.sin(2 * np.pi * f * tt) * np.exp(-tt / d * 4) * rng.uniform(0.1, 0.4)
        i = int(st * SR)
        out[i:i + len(b)] += b[: len(out) - i]
    t = tvec(dur)
    return out + hp(noise(dur, rng), 3000) * np.exp(-t * 6) * 0.6


def saw(f, dur, ph=0.0):
    t = tvec(dur)
    return 2 * ((np.cumsum(np.broadcast_to(f, t.shape)) / SR + ph) % 1) - 1


def fx_braam(rng, dur=2.2):
    t = tvec(dur)
    x = np.zeros_like(t)
    for f in (55, 55.4, 110.3, 82.4, 164.6, 41.2):
        x += saw(f, dur, rng.random())
    env = np.minimum(1, t / 0.04) * np.exp(-t * 1.3)
    from scipy.signal import butter, sosfilt
    out = np.zeros_like(x)
    blk = 2048
    for i in range(0, len(x), blk):
        fc = 180 + 1700 * np.exp(-(i / SR) * 3.0)
        sos = butter(2, fc, "low", fs=SR, output="sos")
        out[i:i + blk] = sosfilt(sos, x[i:i + blk])
    return np.tanh(out * 0.5) * env * 1.4


def fx_riser(rng, dur):
    t = tvec(dur)
    u = t / dur
    n = bp(noise(dur, rng), 500, 9000) * u ** 2.5 * 0.5
    f = 220 * 2 ** (u * 2.5)
    tone_ = np.sin(2 * np.pi * np.cumsum(f) / SR) * u ** 2 * 0.25
    sh = np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR) * u ** 3 * 0.12
    return n + tone_ + sh


def fx_subdrop(dur=1.2):
    t = tvec(dur)
    f = 30 + 70 * np.exp(-t * 3)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2) * 1.2


def fx_tick(hi=True):
    t = tvec(0.06)
    f = 3200 if hi else 2400
    return (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.47 * t)) * np.exp(-t * 120) * 0.5


def pad(freqs, dur, rng):
    t = tvec(dur)
    x = np.zeros_like(t)
    for f in freqs:
        for det in (-0.6, 0.6):
            x += saw(f + det, dur, rng.random())
    return lp(x, 1200) / (len(freqs) * 2)


def reverb(x, rng, seconds=1.1, seed_off=0):
    from scipy.signal import fftconvolve
    r = np.random.default_rng(11 + seed_off)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = r.standard_normal(n) * np.exp(-t * 5.5)
    ir = lp(ir, 5000)
    ir[0] = 0
    return fftconvolve(x, ir)[: len(x)] * 0.06


def bed(total, rng):
    t = tvec(total)
    lfo = 0.65 + 0.35 * np.sin(2 * np.pi * 0.21 * t)
    L = (np.sin(2 * np.pi * 55 * t) + 0.5 * np.sin(2 * np.pi * 58.27 * t) + 0.3 * np.sin(2 * np.pi * 82.4 * t)) * lfo
    R = (np.sin(2 * np.pi * 55.2 * t) + 0.5 * np.sin(2 * np.pi * 58.0 * t) + 0.3 * np.sin(2 * np.pi * 82.6 * t)) * lfo
    grit = lp(saw(55, total) + saw(55.3, total), 260) * 0.25 * lfo
    wind = lp(noise(total, rng), 500) * 0.06
    hi = np.sin(2 * np.pi * 1244.5 * t) * 0.02 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.13 * t))
    return np.stack([L * 0.22 + grit + wind + hi, R * 0.22 + grit + wind * 0.9 + hi])


def build_audio(path):
    rng = np.random.default_rng(7)
    n = int(TOTAL * SR)
    t = np.arange(n) / SR
    amb = bed(TOTAL, rng)
    sfx = np.zeros((2, n))
    duck_src = np.zeros(n)

    def put(sig, T, g=1.0, pan=0.0, duck=0.0):
        i = int(max(0, T) * SR)
        seg = sig[: max(0, n - i)] * g
        sfx[0, i:i + len(seg)] += seg * math.sqrt(0.5 * (1 - pan))
        sfx[1, i:i + len(seg)] += seg * math.sqrt(0.5 * (1 + pan))
        if duck:
            duck_src[i:i + len(seg)] += np.abs(seg) * duck

    # rhythmic pulse (sub kicks) - urgency in the escape section
    for a, b, step, g in ((0.0, 4.0, 0.6, 0.35), (8.0, 14.0, 0.5, 0.4), (15.0, 20.2, 0.43, 0.5), (22.0, 25.6, 0.43, 0.5)):
        p = a
        while p < b:
            put(fx_hit(rng, 0.6), p, g)
            p += step
    # cut hits + whooshes
    for k, c in enumerate(CUTS):
        put(fx_hit(rng), c, 0.75, duck=1.0)
        put(fx_whoosh(rng), c - 0.3, 0.45, pan=(-0.6 if k % 2 else 0.6))
    for x in (0.12, 0.42, 4.05, 9.55, 14.05, 15.05, 16.05, 17.05, 18.55, 22.3, 24.0, 26.35, 26.75):
        put(fx_hit(rng), x, 0.5, duck=0.6)
    # braams on the big story beats
    for x, g in ((0.07, 1.0), (8.3, 1.1), (22.05, 0.9)):
        put(fx_braam(rng), x, g, duck=1.0)
    # risers into the beats
    for a, b in ((2.9, 4.0), (6.9, 7.95), (13.0, 14.0), (24.7, 25.7)):
        put(fx_riser(rng, b - a), a, 0.9)
    for x in (2.0, 14.0, 15.0):
        put(fx_subdrop(), x, 1.0, duck=0.8)
    # hook
    put(fx_crash(rng), 0.06, 1.0, pan=0.2)
    put(fx_hit(rng), 0.06, 1.2, duck=1.0)
    put(fx_glass(rng, 0.8), 0.1, 0.4, pan=-0.3)
    put(fx_whoosh(rng, 0.9), 1.0, 0.6)
    put(fx_splash(rng), 2.0, 1.3)
    put(fx_bubbles(rng, 2.0, 90), 2.05, 0.8, pan=-0.2)
    put(fx_bubbles(rng, 1.0, 120), 3.0, 0.8, pan=0.3)
    put(fx_hit(rng), 3.0, 1.0)
    # choice: heartbeat + clock + countdown beeps
    for b in BEATS:
        put(fx_heart(), b, 1.5, duck=0.5)
    p, hi = 4.0, True
    while p < 7.9:
        put(fx_tick(hi), p, 0.5, pan=0.3 if hi else -0.3)
        p += 0.5
        hi = not hi
    for ta, _ in TIMER:
        put(fx_beep(880, 0.16), ta, 0.55)
    put(fx_beep(440, 0.4), 7.9, 0.7)
    # variant A
    for y in (0.15, 0.55, 0.92, 1.28):
        put(fx_clack(rng), 8.0 + y, 1.0, pan=-0.2)
        put(fx_hit(rng, 0.5), 8.0 + y, 0.6)
    put(fx_groan(4.5), 9.5, 0.55)
    put(fx_bubbles(rng, 3.0, 12), 9.5, 0.5)
    put(fx_powerdown(), 12.8, 0.9)
    put(fx_rewind(rng), 14.0, 0.9)
    # variant B
    put(fx_click(), 15.28, 1.0)
    put(fx_click(), 15.33, 0.8)
    put(fx_whoosh(rng, 0.3), 15.33, 0.7, pan=0.5)
    put(fx_motor(0.75, rng), 16.1, 0.8, pan=-0.3)
    put(fx_splash(rng), 16.6, 0.45)
    put(fx_whoosh(rng, 0.6), 17.1, 0.6)
    put(fx_bubbles(rng, 3.0, 30), 17.2, 0.7)
    put(fx_riser(rng, 1.7), 18.6, 0.6)
    put(fx_splash(rng), 20.25, 1.2)
    put(fx_hit(rng), 20.25, 0.8, duck=1.0)
    put(fx_gasp(rng), 20.4, 1.1)
    put(fx_gasp(rng), 21.1, 0.9)
    # bonus
    for x in (0.12, 0.38, 0.62, 0.84):
        put(fx_click(), 22.0 + x, 0.9)
        put(fx_motor(0.15, rng, stutter=True), 22.0 + x, 0.45)
    put(fx_whoosh(rng, 0.5), 23.4, 0.9, pan=0.4)
    put(fx_hit(rng), 24.32, 1.3, duck=1.0)
    put(fx_clack(rng), 24.32, 1.0)
    put(fx_glass(rng, 0.6), 24.33, 0.6)
    put(fx_glass(rng, 1.6), 25.0, 1.0, pan=-0.2)
    put(fx_glass(rng, 1.6), 25.02, 0.8, pan=0.3)

    # hope pad when surfacing (A major), tense minor elsewhere
    hope = pad((220.0, 277.2, 329.6, 440.0), 2.2, rng)
    e = np.minimum(1, tvec(2.2) / 0.4) * np.minimum(1, (2.2 - tvec(2.2)) / 0.5)
    i = int(20.25 * SR)
    for ch in (0, 1):
        sfx[ch, i:i + len(hope)] += hope * e * 0.55

    # sidechain duck of the bed
    k = int(0.12 * SR)
    denv = np.convolve(duck_src, np.ones(k) / k, mode="same")
    duck = 1 - np.clip(denv * 1.6, 0, 0.7)
    bedg = np.ones(n)
    bedg[(t >= 14.0) & (t < 15.0)] = 0.3
    bedg[(t >= 20.25) & (t < 22.0)] = 0.35
    amb = amb * duck * bedg
    wet = np.stack([reverb(sfx[0], rng, 1.2, 0), reverb(sfx[1], rng, 1.2, 1)])
    mix = amb * 0.9 + sfx * 0.75 + wet
    # underwater: everything muffled
    uw = np.zeros(n)
    for s in SCHED:
        if s[3]:
            uw[int(s[0] * SR):int(s[1] * SR)] = 1
    kk = int(0.03 * SR)
    uw = np.convolve(uw, np.ones(kk) / kk, mode="same")
    rumble = lp(noise(TOTAL, rng), 120) * 0.1
    for ch in (0, 1):
        mix[ch] = mix[ch] * (1 - uw) + (lp(mix[ch], 420) * 1.5 + rumble) * uw
    # silence before the finale
    gate = np.ones(n)
    gate[(t >= 25.7) & (t < 26.3)] = 0
    ramp = (t >= 25.62) & (t < 25.7)
    gate[ramp] = 1 - (t[ramp] - 25.62) / 0.08
    gate[t >= 26.3] = 0.75
    mix = mix * gate
    fin = np.zeros(n)
    for x in (26.35, 26.75):
        h = fx_hit(rng, 1.0)
        j = int(x * SR)
        fin[j:j + len(h)] += h[: n - j]
    for x in (27.3, 28.2, 29.1):
        h = fx_heart(1.2)
        j = int(x * SR)
        fin[j:j + len(h)] += h[: n - j]
    note = np.sin(2 * np.pi * 880 * tvec(3.6)) * np.exp(-tvec(3.6) * 0.9) * 0.08
    j = int(26.35 * SR)
    fin[j:j + len(note)] += note[: n - j]
    mix = mix + fin * 0.75
    mix = np.tanh(mix / max(1e-6, np.abs(mix).max()) * 1.6) * 0.95
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix.T * 32000).astype(np.int16).tobytes())


# ---------------------------------------------------------------- main
def main():
    init()
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        sd = BUILD / os.environ.get("STILLS", "stills")
        sd.mkdir(parents=True, exist_ok=True)
        for t in [float(x) for x in sys.argv[2:]]:
            Image.frombytes("RGB", (W, H), render_frame(int(round(t * FPS)))).save(sd / f"t{t:05.2f}.png")
        return
    raw = BUILD / "mix_raw.wav"
    build_audio(raw)
    audio = BUILD / "mix.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", "48000", "-ac", "2", str(audio)], check=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r",
           str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt",
           "yuv420p", "-profile:v", "high", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-t", f"{TOTAL:.3f}", str(OUTFILE)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=init) as pool:
        for i, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=3)):
            ff.stdin.write(buf)
            if i % 150 == 0:
                print(f"frame {i}/{NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", OUTFILE)


if __name__ == "__main__":
    main()
