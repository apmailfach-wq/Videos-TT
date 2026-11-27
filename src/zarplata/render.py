"""Render the salary-vs-life physics run to a 1080x1920 / 60 fps TikTok video.

    python3 render.py                 # search a dramatic seed, render ../../zarplata-video.mp4
    python3 render.py seed 0          # render a given seed
    python3 render.py preview 0 3 9   # stills (seconds) -> build/zarplata/stills
    LANG_VIDEO=de python3 render.py   # German texts
"""
import math
import multiprocessing as mp
import os
import random
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import sim
import sfx
from texts import LANG, T, money

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "fonts"
BUILD = ROOT / "build" / ("zarplata" if LANG == "ru" else f"zarplata_{LANG}")
W, H, FPS = 1080, 1920, sim.FPS
F_BLACK = str(FONTS / "Unbounded_900Black.ttf")
F_BOLD = str(FONTS / "Unbounded_700Bold.ttf")
F_HAND = str(FONTS / "Caveat_700Bold.ttf")
F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

BG_TOP = (14, 12, 34)
BG_BOT = (30, 10, 46)
WALLC = (70, 80, 130)
HUD_H = 300
BALL_SCREEN_Y = 900
END_HOLD = 7.0          # seconds of ending sequence after the ball lands


# ----------------------------------------------------------------- helpers
def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_back(x):
    x = clamp01(x)
    c = 1.9
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def rgb(c, a=1.0):
    return (c[0] / 255, c[1] / 255, c[2] / 255, a)


def mix(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, size)


@lru_cache(maxsize=4096)
def text_sprite(text, size, color=(255, 255, 255), stroke=0, stroke_color=(0, 0, 0),
                path=F_BLACK, spacing=0.1):
    f = font(path, size)
    lines = text.split("\n")
    boxes = [f.getbbox(l, stroke_width=stroke) for l in lines]
    lh = int(size * (1 + spacing))
    w = max(b[2] - b[0] for b in boxes) + 8
    h = lh * (len(lines) - 1) + (boxes[-1][3]) + stroke * 2 + 8
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, (l, b) in enumerate(zip(lines, boxes)):
        lw = b[2] - b[0]
        d.text(((w - lw) / 2 - b[0], i * lh + 4), l, font=f, fill=color + (255,),
               stroke_width=stroke, stroke_fill=stroke_color + (255,))
    bb = im.getbbox()
    return im.crop(bb) if bb else im


def fit_sprite(text, max_w, max_size, **kw):
    size = max_size
    while size > 10:
        sp = text_sprite(text, size, **kw)
        if sp.width <= max_w:
            return sp
        size -= 2
    return text_sprite(text, size, **kw)


@lru_cache(maxsize=32)
def emoji_sprite(ch, size):
    f = ImageFont.truetype(F_EMOJI, 109)
    im = Image.new("RGBA", (140, 140), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((5, 5), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox())
    return im.resize((size, int(size * im.height / im.width)), Image.LANCZOS)


def paste_c(img, sp, cx, cy, alpha=1.0, scale=1.0, angle=0.0):
    if scale != 1.0:
        sp = sp.resize((max(1, int(sp.width * scale)), max(1, int(sp.height * scale))), Image.BICUBIC)
    if angle:
        sp = sp.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 1.0:
        sp = sp.copy()
        sp.putalpha(sp.getchannel("A").point(lambda v: int(v * alpha)))
    img.alpha_composite(sp, (int(cx - sp.width / 2), int(cy - sp.height / 2)))


# ----------------------------------------------------------- precompute run
def pick_seed(n=400):
    """Find a run that lands in VACATION with very little money left after real drama."""
    best = None
    for s in range(n):
        r = sim.run(s)
        if r["result"] != "vacation":
            continue
        dur = r["n_frames"] / FPS
        keys = {h[2]["key"] for h in r["hits"]}
        money_track = [h[2]["money"] for h in r["hits"]]
        low = min(money_track + [sim.START_MONEY])
        bonus = "bonus" in keys
        score = 0
        score += 40 if 0 < r["money"] < 3_000 else (15 if r["money"] < 8_000 else -30)
        score += 4 * len(keys)
        score += 12 if bonus else 0
        score += 10 if "dentist" in keys else 0
        score += 8 if "food" in keys else 0
        score += 10 if low < 6_000 else 0      # nearly bankrupt at some point
        score -= abs(dur - 30) * 1.5
        print(f"seed {s}: {r['money']} left, {dur:.1f}s, keys={sorted(keys)} score={score:.1f}")
        if best is None or score > best[0]:
            best = (score, s)
    return best[1]


class Run:
    def __init__(self, seed):
        r = sim.run(seed, record=True, tail=END_HOLD)
        self.seed = seed
        self.result = r["result"]
        self.final_money = r["money"]
        self.lv = r["level"]
        self.frames = r["frames"]
        self.n = len(self.frames)
        # landing frame
        self.land = next((i for i, fr in enumerate(self.frames)
                          if any(e[1] == "pocket" for e in fr["events"])), self.n - 1)
        self.events = []        # (frame, type, payload)
        for i, fr in enumerate(self.frames):
            for e in fr["events"]:
                self.events.append((i, e[1], e[2]))
        self.hit_events = [e for e in self.events if e[1] == "hit"]
        # camera
        cam, c = [], 0.0
        for i, fr in enumerate(self.frames):
            target = min(max(-600.0, fr["by"] - BALL_SCREEN_Y), sim.LEVEL_END - 1560)
            c = target if i == 0 else c + (target - c) * 0.12
            cam.append(c)
        self.cam = cam
        # displayed money (counts down smoothly)
        disp, d = [], float(sim.START_MONEY)
        for fr in self.frames:
            d += (fr["money"] - d) * 0.18
            if abs(fr["money"] - d) < 30:
                d = fr["money"]
            disp.append(d)
        self.disp = disp
        # per-obstacle hit frames (for flashes / "paid")
        self.hit_frames = {}
        for f, _, p in self.hit_events:
            self.hit_frames.setdefault(p["idx"], []).append(f)
        # trail
        self.trail = [(fr["bx"], fr["by"]) for fr in self.frames]


# ------------------------------------------------------------- world draw
def draw_bg(ctx, cam):
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgb(0, *[v / 255 for v in BG_TOP])
    g.add_color_stop_rgb(1, *[v / 255 for v in BG_BOT])
    ctx.set_source(g)
    ctx.paint()
    # world-space grid (parallax 1)
    ctx.set_line_width(1.5)
    ctx.set_source_rgba(1, 1, 1, 0.045)
    step = 90
    y0 = -(cam % step)
    y = y0
    while y < H:
        ctx.move_to(0, y)
        ctx.line_to(W, y)
        y += step
    for x in range(0, W, step):
        ctx.move_to(x + 0.5, 0)
        ctx.line_to(x + 0.5, H)
    ctx.stroke()


def rrect(ctx, x, y, w, h, r):
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()


def glow_circle(ctx, x, y, r, color, a=0.5, k=2.4):
    g = cairo.RadialGradient(x, y, r * 0.6, x, y, r * k)
    g.add_color_stop_rgba(0, *rgb(color, a))
    g.add_color_stop_rgba(1, *rgb(color, 0))
    ctx.set_source(g)
    ctx.arc(x, y, r * k, 0, 2 * math.pi)
    ctx.fill()


def shaded_circle(ctx, x, y, r, color, outline=None):
    dark = mix(color, (0, 0, 0), 0.45)
    light = mix(color, (255, 255, 255), 0.45)
    g = cairo.RadialGradient(x - r * 0.35, y - r * 0.4, r * 0.1, x, y, r)
    g.add_color_stop_rgb(0, *[v / 255 for v in light])
    g.add_color_stop_rgb(0.55, *[v / 255 for v in color])
    g.add_color_stop_rgb(1, *[v / 255 for v in dark])
    ctx.set_source(g)
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.fill_preserve()
    ctx.set_source_rgba(*rgb(outline or mix(color, (0, 0, 0), 0.6)))
    ctx.set_line_width(max(2.0, r * 0.09))
    ctx.stroke()


def angry_eyes(ctx, x, y, r, t, ang=0.0, dark=(20, 15, 30)):
    ex = r * 0.32
    ey = -r * 0.32
    er = r * 0.16
    for s in (-1, 1):
        cx, cy = x + s * ex, y + ey
        ctx.set_source_rgb(1, 1, 1)
        ctx.arc(cx, cy, er, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgba(*rgb(dark))
        ctx.arc(cx - s * er * 0.25, cy + er * 0.2, er * 0.55, 0, 2 * math.pi)
        ctx.fill()
        # brow
        ctx.set_line_width(max(2.5, r * 0.08))
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.move_to(cx - s * er * 1.3, cy - er * 1.6)
        ctx.line_to(cx + s * er * 0.9, cy - er * 0.9)
        ctx.stroke()


def ball_face(ctx, x, y, r, mood, t, look):
    """mood 0 = happy, 1 = panic."""
    ex, ey, er = r * 0.33, -r * 0.18, r * 0.2 * (1 + 0.35 * mood)
    lx, ly = look
    for s in (-1, 1):
        cx, cy = x + s * ex, y + ey
        ctx.set_source_rgb(1, 1, 1)
        ctx.arc(cx, cy, er, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.05, 0.1, 0.08)
        pr = er * (0.55 - 0.2 * mood)
        ctx.arc(cx + lx * er * 0.35, cy + ly * er * 0.35, pr, 0, 2 * math.pi)
        ctx.fill()
    ctx.set_source_rgb(0.05, 0.15, 0.08)
    ctx.set_line_width(max(2.0, r * 0.08))
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    my = y + r * 0.35
    if mood < 0.35:
        ctx.arc(x, my - r * 0.12, r * 0.28, 0.15 * math.pi, 0.85 * math.pi)
        ctx.stroke()
    elif mood < 0.7:
        ctx.move_to(x - r * 0.22, my)
        ctx.line_to(x + r * 0.22, my)
        ctx.stroke()
    else:
        ctx.save()
        ctx.translate(x, my)
        ctx.scale(1, 1.3)
        ctx.arc(0, 0, r * 0.15, 0, 2 * math.pi)
        ctx.restore()
        ctx.fill()


def world(ctx, run, f, cam, shake):
    fr = run.frames[f]
    lv = run.lv
    t = f / FPS
    oy = -cam + shake[1]
    ox = shake[0]
    ctx.save()
    ctx.translate(ox, oy)
    top, bot = cam - 200, cam + H + 200
    sprites = []        # (sprite, x, y, angle, alpha) in screen coords later

    def vis(y, pad=300):
        return top - pad < y < bot + pad

    # pockets
    for name, x0, x1, col in lv.pockets:
        y0 = sim.POCKET_TOP
        if not vis(y0, 600):
            continue
        g = cairo.LinearGradient(0, y0, 0, sim.LEVEL_END)
        g.add_color_stop_rgba(0, *rgb(col, 0.05))
        g.add_color_stop_rgba(1, *rgb(col, 0.55 if name == "vacation" else 0.35))
        ctx.set_source(g)
        ctx.rectangle(x0, y0 - 40, x1 - x0, sim.LEVEL_END - y0 + 40)
        ctx.fill()
        size = 46 if name == "vacation" else 30
        sp = fit_sprite(T[name], x1 - x0 - 40, size, color=(255, 255, 255) if name != "vacation" else (255, 236, 150),
                        stroke=3, stroke_color=mix(col, (0, 0, 0), 0.6))
        sprites.append((sp, (x0 + x1) / 2, sim.LEVEL_END - 150, 0, 1.0))
        if name == "vacation":
            sprites.append((emoji_sprite("🏖", 90), (x0 + x1) / 2, sim.LEVEL_END - 270, 0, 1.0))
    # payday sign

    # stage banners (world text)
    banners = [(2050, T["tax"], (255, 170, 80))]
    for y, txt, col in banners:
        if vis(y):
            sprites.append((text_sprite(txt, 64, color=col, stroke=0), 540, y, 0, 0.35))

    # static segments
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for a, b, r in lv.statics:
        if not (vis(a[1]) or vis(b[1]) or (a[1] < top and b[1] > bot)):
            continue
        ctx.set_source_rgba(*rgb(WALLC))
        ctx.set_line_width(r * 2)
        ctx.move_to(*a)
        ctx.line_to(*b)
        ctx.stroke()
        ctx.set_source_rgba(1, 1, 1, 0.18)
        ctx.set_line_width(max(2, r * 0.5))
        ctx.move_to(*a)
        ctx.line_to(*b)
        ctx.stroke()

    # obstacles
    for idx, ob in enumerate(lv.obstacles):
        x, y, ang = fr["obs"][idx]
        if ob.kind not in ("enemy",) and not vis(y):
            continue
        if ob.kind == "enemy" and not vis(y):
            continue
        hits = [hf for hf in run.hit_frames.get(idx, []) if hf <= f]
        flash = 0.0
        if hits:
            flash = max(0.0, 1 - (f - hits[-1]) / (0.35 * FPS))
        used = ob.hits and len(hits) >= ob.max_hits and ob.max_hits < 50
        col = ob.color
        if used:
            col = mix(col, (90, 90, 110), 0.65)
        if flash:
            col = mix(col, (255, 255, 255), flash * 0.8)
        if ob.kind == "spinner":
            L, Th = ob.extra["length"], ob.extra["thick"]
            ctx.save()
            ctx.translate(x, y)
            ctx.rotate(ang)
            if flash:
                ctx.set_source_rgba(*rgb(ob.color, 0.35 * flash))
                rrect(ctx, -L / 2 - 20, -Th / 2 - 20, L + 40, Th + 40, Th / 2 + 20)
                ctx.fill()
            g = cairo.LinearGradient(0, -Th / 2, 0, Th / 2)
            g.add_color_stop_rgb(0, *[v / 255 for v in mix(col, (255, 255, 255), 0.3)])
            g.add_color_stop_rgb(1, *[v / 255 for v in mix(col, (0, 0, 0), 0.35)])
            ctx.set_source(g)
            rrect(ctx, -L / 2, -Th / 2, L, Th, 12)
            ctx.fill_preserve()
            ctx.set_source_rgba(*rgb(mix(col, (0, 0, 0), 0.6)))
            ctx.set_line_width(4)
            ctx.stroke()
            ctx.restore()
            # hub
            ctx.set_source_rgba(*rgb((220, 220, 240)))
            ctx.arc(x, y, 14, 0, 2 * math.pi)
            ctx.fill()
            label = T["paid"] if used else T[ob.key]
            sp = fit_sprite(label, L - 60, 30, color=(255, 255, 255), stroke=2, stroke_color=(60, 0, 10))
            a = -math.degrees(ang)
            # keep text upright-ish
            a = ((a + 90) % 180) - 90
            sprites.append((sp, x, y, a, 1.0))
        elif ob.kind in ("peg", "bonus"):
            r = ob.extra["r"]
            if ob.kind == "bonus" and not used:
                pulse = 0.5 + 0.5 * math.sin(t * 6)
                glow_circle(ctx, x, y, r, ob.color, 0.35 + 0.25 * pulse)
            if flash:
                glow_circle(ctx, x, y, r, ob.color, 0.8 * flash, 3.0)
            shaded_circle(ctx, x, y, r, col)
            if ob.kind == "bonus":
                lab = T[ob.key]
                sp = fit_sprite(lab, 260, 26, color=(200, 255, 220), stroke=3, stroke_color=(0, 60, 30))
                sprites.append((sp, x, y - r - 28, 0, 0.5 if used else 1.0))
                sp2 = text_sprite(money(ob.cost, sign=True), 22, color=(255, 255, 255), stroke=2,
                                  stroke_color=(0, 70, 30))
                sprites.append((sp2, x, y, 0, 0.5 if used else 1.0))
        elif ob.kind == "enemy":
            r = ob.extra["r"]
            if flash:
                glow_circle(ctx, x, y, r, ob.color, 0.7 * flash, 2.0)
            shaded_circle(ctx, x, y, r, col)
            angry_eyes(ctx, x, y, r, t)
            dark = ob.key == "dentist"
            sp = fit_sprite(T[ob.key], int(r * 1.85), 30,
                            color=(30, 40, 70) if dark else (255, 255, 255),
                            stroke=0 if dark else 2, stroke_color=mix(ob.color, (0, 0, 0), 0.6))
            sprites.append((sp, x, y + r * 0.3, 0, 1.0))
            if ob.key == "dentist":
                sprites.append((emoji_sprite("🦷", 46), x, y - r - 20, 0, 1.0))
        elif ob.kind in ("piston", "gate"):
            w_, h_ = ob.extra["w"], ob.extra["h"]
            if flash:
                ctx.set_source_rgba(*rgb(ob.color, 0.4 * flash))
                rrect(ctx, x - w_ / 2 - 18, y - h_ / 2 - 18, w_ + 36, h_ + 36, 26)
                ctx.fill()
            g = cairo.LinearGradient(0, y - h_ / 2, 0, y + h_ / 2)
            g.add_color_stop_rgb(0, *[v / 255 for v in mix(col, (255, 255, 255), 0.3)])
            g.add_color_stop_rgb(1, *[v / 255 for v in mix(col, (0, 0, 0), 0.35)])
            ctx.set_source(g)
            rrect(ctx, x - w_ / 2, y - h_ / 2, w_, h_, 14)
            ctx.fill_preserve()
            ctx.set_source_rgba(*rgb(mix(col, (0, 0, 0), 0.6)))
            ctx.set_line_width(4)
            ctx.stroke()
            # hazard stripes
            ctx.save()
            rrect(ctx, x - w_ / 2, y - h_ / 2, w_, h_, 14)
            ctx.clip()
            ctx.set_source_rgba(0, 0, 0, 0.18)
            for k in range(-20, 20):
                sx = x - w_ / 2 + k * 36
                ctx.move_to(sx, y + h_ / 2)
                ctx.line_to(sx + 18, y + h_ / 2)
                ctx.line_to(sx + 18 + h_, y - h_ / 2)
                ctx.line_to(sx + h_, y - h_ / 2)
                ctx.close_path()
            ctx.fill()
            ctx.restore()
            sp = fit_sprite(T[ob.key], w_ - 40, 32, color=(255, 255, 255), stroke=3, stroke_color=(70, 0, 15))
            sprites.append((sp, x, y, 0, 1.0))

    # ball trail
    bx, by, br = fr["bx"], fr["by"], fr["br"]
    trail = run.trail[max(0, f - 14):f + 1]
    for i in range(1, len(trail)):
        k = i / len(trail)
        ctx.set_source_rgba(0.2, 1.0, 0.55, 0.28 * k)
        ctx.set_line_width(br * 1.6 * k)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.move_to(*trail[i - 1])
        ctx.line_to(*trail[i])
        ctx.stroke()
    # ball
    frac = clamp01(fr["money"] / sim.START_MONEY)
    bcol = mix((255, 70, 70), sim.GREEN, clamp01(frac * 1.6))
    glow_circle(ctx, bx, by, br, bcol, 0.55, 2.6)
    shaded_circle(ctx, bx, by, br, bcol, outline=(10, 60, 30))
    if f > 1:
        vx = fr["bx"] - run.frames[f - 1]["bx"]
        vy = fr["by"] - run.frames[f - 1]["by"]
        n = math.hypot(vx, vy) + 1e-6
        look = (vx / n, vy / n)
    else:
        look = (0, 1)
    recent = [e for e in run.hit_events if f - 25 < e[0] <= f and e[2]["cost"] < 0]
    mood = clamp01(1 - frac * 1.3) if not recent else 1.0
    if f >= run.land and run.result == "vacation":
        mood = 0.0
    ball_face(ctx, bx, by, br, mood, t, look)
    # money tag above ball
    tag = text_sprite(T["salary"], 24, color=(210, 255, 225), stroke=3, stroke_color=(0, 50, 25))
    sprites.append((tag, bx, by - br - 26, 0, 1.0))

    ctx.restore()
    return [(sp, x + ox, y + oy, a, al) for sp, x, y, a, al in sprites]


# --------------------------------------------------------------- effects
def particles(run, f):
    """Analytic particles: sparks / coins per hit, confetti on landing."""
    out = []
    for ef, typ, p in run.events:
        age = (f - ef) / FPS
        if typ == "hit":
            if not (0 <= age < 1.1):
                continue
            rng = random.Random(ef * 7919 + int(p["x"]))
            n = 10 + min(24, int(abs(p["cost"]) / 1500))
            gain = p["cost"] > 0
            for _ in range(n):
                a = rng.uniform(0, 2 * math.pi)
                sp = rng.uniform(250, 900)
                vx, vy = math.cos(a) * sp, math.sin(a) * sp - (300 if gain else 100)
                x = p["x"] + vx * age
                y = p["y"] + vy * age + 1300 * age * age
                life = 1 - age / 1.1
                col = (255, 215, 60) if gain or rng.random() < 0.4 else p["color"]
                out.append(("coin" if col == (255, 215, 60) else "spark", x, y, rng.uniform(5, 11) * life, col, life,
                            a + age * 8))
        elif typ == "pocket":
            if not (0 <= age < 4.0) or p["name"] != "vacation":
                continue
            rng = random.Random(4242)
            for i in range(160):
                side = -1 if i % 2 else 1
                x0 = 540 + side * 300
                a = -math.pi / 2 + side * rng.uniform(-0.15, 0.7) * -1
                sp = rng.uniform(900, 1900)
                d = rng.uniform(0, 0.4)
                aa = age - d
                if aa < 0:
                    continue
                vx, vy = math.cos(a) * sp, math.sin(a) * sp
                drag = math.exp(-2.2 * aa)
                x = x0 + vx * (1 - drag) / 2.2 + 40 * math.sin(aa * 5 + i)
                y = p["y"] + vy * (1 - drag) / 2.2 + 260 * aa * aa
                col = rng.choice([(255, 80, 170), (255, 214, 50), (40, 230, 120), (60, 150, 255), (255, 255, 255)])
                out.append(("conf", x, y, rng.uniform(8, 14), col, clamp01(1.4 - aa / 3), aa * rng.uniform(4, 12) + i))
    return out


def draw_particles(ctx, parts, cam, shake):
    for kind, x, y, s, col, life, rot in parts:
        sx, sy = x + shake[0], y - cam + shake[1]
        if not (-50 < sy < H + 50):
            continue
        if kind == "spark":
            ctx.set_source_rgba(*rgb(col, life))
            ctx.arc(sx, sy, s, 0, 2 * math.pi)
            ctx.fill()
        elif kind == "coin":
            ctx.save()
            ctx.translate(sx, sy)
            ctx.scale(abs(math.cos(rot)) * 0.9 + 0.1, 1)
            ctx.set_source_rgba(1, 0.84, 0.24, life)
            ctx.arc(0, 0, s * 1.3, 0, 2 * math.pi)
            ctx.fill()
            ctx.set_source_rgba(0.75, 0.55, 0.05, life)
            ctx.set_line_width(2)
            ctx.arc(0, 0, s * 0.8, 0, 2 * math.pi)
            ctx.stroke()
            ctx.restore()
        else:
            ctx.save()
            ctx.translate(sx, sy)
            ctx.rotate(rot)
            ctx.scale(1, abs(math.sin(rot * 1.3)) * 0.8 + 0.2)
            ctx.set_source_rgba(*rgb(col, life))
            ctx.rectangle(-s / 2, -s / 4, s, s / 2)
            ctx.fill()
            ctx.restore()


def camera_shake(run, f):
    sx = sy = 0.0
    for ef, typ, p in run.hit_events:
        age = (f - ef) / FPS
        if 0 <= age < 0.4 and p["cost"] < 0:
            amp = min(26, 4 + abs(p["cost"]) / 1200) * (1 - age / 0.4) ** 2
            sx += amp * math.sin(ef * 1.7 + age * 70)
            sy += amp * math.cos(ef * 2.3 + age * 63)
    return sx, sy


# ------------------------------------------------------------------- HUD
def money_color(frac):
    if frac > 0.5:
        return (90, 255, 150)
    if frac > 0.2:
        return (255, 214, 50)
    return (255, 70, 80)


def hud(img, run, f):
    fr = run.frames[min(f, run.n - 1)]
    d = ImageDraw.Draw(img)
    # top band
    band = Image.new("RGBA", (W, HUD_H), (8, 6, 20, 215))
    img.alpha_composite(band, (0, 0))
    d.line([(0, HUD_H), (W, HUD_H)], fill=(255, 255, 255, 40), width=2)
    disp = run.disp[min(f, run.n - 1)]
    frac = clamp01(disp / sim.START_MONEY)
    col = money_color(frac)
    recent = [e for e in run.hit_events if 0 <= f - e[0] < 12]
    pop = 1.0 + (0.12 * (1 - (f - recent[-1][0]) / 12) if recent else 0)
    lab = text_sprite(T["salary"], 30, color=(180, 190, 230), stroke=0, path=F_BOLD)
    paste_c(img, lab, W / 2, 62)
    m = text_sprite(money(max(disp, 0)), 104, color=col, stroke=5, stroke_color=(0, 0, 0))
    paste_c(img, m, W / 2, 150, scale=pop)
    # progress bar to vacation
    x0, x1, y = 130, 900, 250
    prog = clamp01((fr["by"] - 330) / (sim.POCKET_TOP + 150 - 330))
    d.rounded_rectangle([x0, y - 9, x1, y + 9], radius=9, fill=(40, 40, 70, 255))
    d.rounded_rectangle([x0, y - 9, x0 + max(18, (x1 - x0) * prog), y + 9], radius=9, fill=col + (255,))
    d.ellipse([x0 + (x1 - x0) * prog - 16, y - 16, x0 + (x1 - x0) * prog + 16, y + 16],
              fill=(255, 255, 255, 255), outline=col + (255,), width=4)
    paste_c(img, emoji_sprite("🏖", 54), x1 + 50, y - 4)
    # damage popups (screen space near hit point)
    cam = run.cam[min(f, run.n - 1)]
    for ef, typ, p in run.hit_events:
        age = (f - ef) / FPS
        if not (0 <= age < 1.3):
            continue
        gain = p["cost"] > 0
        size = 46 + min(40, int(abs(p["cost"]) / 900))
        sp = text_sprite(money(p["cost"], sign=True), size,
                         color=(120, 255, 160) if gain else (255, 80, 90), stroke=5, stroke_color=(0, 0, 0))
        sx = min(max(p["x"], sp.width / 2 + 30), W - sp.width / 2 - 30)
        sy = p["y"] - run.cam[ef] - 70 - 140 * ease_out(age / 1.3)
        sy = max(sy, HUD_H + 50)
        sc = ease_back(age / 0.25) if age < 0.25 else 1.0
        paste_c(img, sp, sx, sy, alpha=clamp01((1.3 - age) / 0.35), scale=max(0.05, sc))


def red_flash(img, run, f):
    best = 0.0
    green = 0.0
    for ef, typ, p in run.hit_events:
        age = (f - ef) / FPS
        if 0 <= age < 0.45:
            k = (1 - age / 0.45)
            if p["cost"] <= -5000:
                best = max(best, k * min(1, abs(p["cost"]) / 20000 + 0.35))
            elif p["cost"] > 1000:
                green = max(green, k)
    if best > 0.02:
        img.alpha_composite(vignette((255, 30, 50), int(150 * best)))
    if green > 0.02:
        img.alpha_composite(vignette((40, 255, 120), int(130 * green)))


@lru_cache(maxsize=64)
def _vig(color, a):
    yy, xx = np.mgrid[0:H // 4, 0:W // 4]
    dx = (xx - W / 8) / (W / 8)
    dy = (yy - H / 8) / (H / 8)
    r = np.sqrt(dx * dx + dy * dy)
    alpha = (np.clip((r - 0.55) / 0.6, 0, 1) ** 1.5 * a).astype(np.uint8)
    arr = np.zeros((H // 4, W // 4, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3] = color[0], color[1], color[2], alpha
    return Image.fromarray(arr, "RGBA").resize((W, H), Image.BILINEAR)


def vignette(color, a):
    return _vig(color, max(0, min(255, a // 10 * 10)))


def overlays(img, run, f):
    t = f / FPS
    # hook
    if t < 2.8:
        a = clamp01((2.8 - t) / 0.35)
        lines = [(T["hook1"], 64, (255, 255, 255)), (T["hook2"], 92, (90, 255, 150)),
                 (T["hook3"], 76, (255, 214, 50))]
        y = 490
        bg = Image.new("RGBA", (W, 330), (0, 0, 0, int(150 * a)))
        img.alpha_composite(bg, (0, HUD_H + 2))
        for i, (txt, size, col) in enumerate(lines):
            k = ease_back((t - i * 0.18) / 0.35)
            if k <= 0:
                y += size + 28
                continue
            sp = fit_sprite(txt, W - 180, size, color=col, stroke=6, stroke_color=(0, 0, 0))
            paste_c(img, sp, W / 2, y - 120, alpha=a, scale=max(0.05, k))
            y += size + 28
    fr = run.frames[min(f, run.n - 1)]
    if fr["slow"] and f < run.land:
        k = 0.5 + 0.5 * math.sin(t * 9)
        sp = fit_sprite(T["comeon"], W - 160, 54, color=(255, 255, 255), stroke=5, stroke_color=(0, 0, 0))
        paste_c(img, sp, W / 2, 420, scale=1 + 0.06 * k)
        img.alpha_composite(vignette((0, 0, 0), 120))
    # ending
    if f >= run.land and run.result == "vacation":
        e = (f - run.land) / FPS
        if e > 0.25:
            dim = Image.new("RGBA", (W, H), (5, 4, 15, int(170 * clamp01((e - 0.25) / 0.5))))
            img.alpha_composite(dim)
        if e > 0.3:
            k = ease_back((e - 0.3) / 0.4)
            sp = fit_sprite(T["made_it"], W - 100, 130, color=(255, 214, 50), stroke=8, stroke_color=(60, 30, 0))
            wob = math.sin(e * 5) * 3
            paste_c(img, sp, W / 2, 600, scale=max(0.05, k), angle=wob)
        if e > 1.1:
            k = ease_back((e - 1.1) / 0.35)
            sp = text_sprite(T["left"], 44, color=(220, 225, 255), stroke=0, path=F_BOLD)
            paste_c(img, sp, W / 2, 790, alpha=clamp01((e - 1.1) / 0.3))
            cnt = clamp01((e - 1.2) / 1.0)
            # dramatic count-down to the real remainder
            shown = sim.START_MONEY * 0 + run.final_money + (1 - ease_out(cnt)) * 9000
            sp = text_sprite(money(shown), 140, color=(255, 80, 90), stroke=7, stroke_color=(0, 0, 0))
            paste_c(img, sp, W / 2, 920, scale=max(0.05, k))
        if e > 2.8:
            k = ease_back((e - 2.8) / 0.4)
            sp = text_sprite(T["punch"], 82, color=(255, 255, 255), stroke=4, stroke_color=(0, 0, 0), path=F_HAND)
            paste_c(img, sp, W / 2, 1090, scale=max(0.05, k), angle=-4)
        if e > 4.2:
            k = ease_back((e - 4.2) / 0.4)
            card = Image.new("RGBA", (W - 120, 380), (0, 0, 0, 0))
            ImageDraw.Draw(card).rounded_rectangle([0, 0, W - 121, 379], radius=40, fill=(255, 214, 50, 255))
            paste_c(card, fit_sprite(T["cta1"], W - 200, 62, color=(20, 15, 30)), (W - 120) / 2, 90)
            paste_c(card, fit_sprite(T["cta2"], W - 200, 80, color=(20, 15, 30)), (W - 120) / 2, 190)
            paste_c(card, fit_sprite(T["cta3"], W - 220, 30, color=(70, 50, 20), path=F_BOLD), (W - 120) / 2, 300)
            paste_c(img, card, W / 2, 1380, scale=max(0.05, k))
            bounce = abs(math.sin(e * 6)) * 24
            paste_c(img, emoji_sprite("👇", 100), W / 2, 1640 + bounce, alpha=clamp01((e - 4.4) / 0.3))


# --------------------------------------------------------------- frame
def render_frame(run, f):
    cam = run.cam[f]
    shake = camera_shake(run, f)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    ctx = cairo.Context(surf)
    draw_bg(ctx, cam)
    sprites = world(ctx, run, f, cam, shake)
    draw_particles(ctx, particles(run, f), cam, shake)
    surf.flush()
    buf = np.ndarray((H, W, 4), np.uint8, surf.get_data())
    img = Image.fromarray(buf[..., [2, 1, 0, 3]].copy(), "RGBA")
    for sp, x, y, a, al in sprites:
        if -200 < y < H + 200:
            paste_c(img, sp, x, y, alpha=al, angle=a)
    red_flash(img, run, f)
    hud(img, run, f)
    overlays(img, run, f)
    return img.convert("RGB")


# --------------------------------------------------------------- output
RUN = None


def _worker(args):
    i, a, b, path = args
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
           "-crf", "18", "-pix_fmt", "yuv420p", path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(a, b):
        p.stdin.write(render_frame(RUN, f).tobytes())
        if (f - a) % 300 == 0:
            print(f"  worker {i}: {f - a}/{b - a}", flush=True)
    p.stdin.close()
    p.wait()
    return path


def render_video(run, out):
    global RUN
    RUN = run
    BUILD.mkdir(parents=True, exist_ok=True)
    nw = max(1, os.cpu_count() or 1)
    bounds = [run.n * k // nw for k in range(nw + 1)]
    jobs = [(i, bounds[i], bounds[i + 1], str(BUILD / f"part{i}.mp4")) for i in range(nw)]
    with mp.get_context("fork").Pool(nw) as pool:
        parts = pool.map(_worker, jobs)
    lst = BUILD / "parts.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    wav = BUILD / "sfx.wav"
    sfx.build(run, str(wav), FPS)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-i", str(wav), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", str(out)], check=True)
    print("wrote", out, f"({run.n / FPS:.1f}s, seed {run.seed}, {run.result}, {run.final_money} left)")


def main():
    args = sys.argv[1:]
    default_out = ROOT / ("zarplata-video.mp4" if LANG == "ru" else f"zarplata-video-{LANG}.mp4")
    out = Path(os.environ.get("VIDEO_OUT", default_out))
    if args and args[0] == "preview":
        seed = int(os.environ.get("SEED", "-1"))
        seed = pick_seed() if seed < 0 else seed
        run = Run(seed)
        d = BUILD / "stills"
        d.mkdir(parents=True, exist_ok=True)
        for s in args[1:]:
            f = min(int(float(s) * FPS), run.n - 1) if s != "end" else run.n - 1
            render_frame(run, f).save(d / f"still_{s}.png")
            print("still", s, "->", d / f"still_{s}.png")
        print("duration", run.n / FPS, "land", run.land / FPS)
        return
    if args and args[0] == "seed":
        seed = int(args[1])
    else:
        seed = pick_seed()
    print("using seed", seed)
    render_video(Run(seed), out)


if __name__ == "__main__":
    main()
