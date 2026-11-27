"""Rendert 'Schafft es mein Gehalt bis zum Urlaub?' als TikTok-Video (1080x1920, 60 fps).

    python3 render.py                   # besten Seed suchen + ../../gehalt-video.mp4
    python3 render.py seed 10           # bestimmten Seed rendern
    SEED=10 python3 render.py preview 2 12 end   # Standbilder -> build/gehalt/stills
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

import sfx
import sim
from daten import BRUTTO, CATEGORIES, CHAPTERS, ITEMS, POCKETS, T, eur, eur_short

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "fonts"
BUILD = ROOT / "build" / "gehalt"
W, H, FPS = 1080, 1920, sim.FPS
F_BLACK = str(FONTS / "Unbounded_900Black.ttf")
F_BOLD = str(FONTS / "Unbounded_700Bold.ttf")
F_HAND = str(FONTS / "Caveat_700Bold.ttf")
F_INTER = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_INTER_B = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

BG_TOP = (13, 14, 34)
BG_BOT = (28, 12, 44)
WALLC = (72, 84, 138)
HUD_H = 440
BALL_SCREEN_Y = 1010
END_HOLD = 9.2
NETTO = BRUTTO + sum(v[2] for v in ITEMS.values() if v[3] == "abzug")


# ------------------------------------------------------------------ helpers
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
def text_sprite(text, size, color=(255, 255, 255), stroke=0, stroke_color=(0, 0, 0), path=F_BLACK):
    f = font(path, size)
    lines = text.split("\n")
    lh = int(size * 1.12)
    boxes = [f.getbbox(l or " ", stroke_width=stroke) for l in lines]
    w = max(b[2] - b[0] for b in boxes) + 8
    h = lh * (len(lines) - 1) + boxes[-1][3] + stroke * 2 + 10
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, (l, b) in enumerate(zip(lines, boxes)):
        d.text(((w - (b[2] - b[0])) / 2 - b[0], i * lh + 4), l, font=f, fill=color + (255,),
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


@lru_cache(maxsize=128)
def emoji_sprite(ch, size):
    f = ImageFont.truetype(F_EMOJI, 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), ch, font=f, embedded_color=True)
    bb = im.getbbox()
    im = im.crop(bb) if bb else im
    return im.resize((size, max(1, int(size * im.height / im.width))), Image.LANCZOS)


def paste_c(img, sp, cx, cy, alpha=1.0, scale=1.0, angle=0.0):
    if scale != 1.0:
        sp = sp.resize((max(1, int(sp.width * scale)), max(1, int(sp.height * scale))), Image.BICUBIC)
    if angle:
        sp = sp.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        sp = sp.copy()
        sp.putalpha(sp.getchannel("A").point(lambda v: int(v * alpha)))
    img.alpha_composite(sp, (int(cx - sp.width / 2), int(cy - sp.height / 2)))


def paste_l(img, sp, x, cy, alpha=1.0):
    paste_c(img, sp, x + sp.width / 2, cy, alpha)


def paste_r(img, sp, x, cy, alpha=1.0):
    paste_c(img, sp, x - sp.width / 2, cy, alpha)


# ----------------------------------------------------------------- the run
def score_run(r):
    if r["result"] != "urlaub":
        return None
    dur = r["n_frames"] / FPS
    keys = {h[2]["key"] for h in r["hits"]}
    left = r["money"] / 100
    s = 0.0
    s += max(0, 60 - left / 6)                 # wenig übrig = spannend
    s += 2.5 * len(keys)
    s += 8 if {"miete", "strom", "handy"} <= keys else 0
    s += 6 if "zahnarzt" in keys else 0
    s += 6 if "pfand" in keys else 0
    s += 10 if "erstattung" in keys else 0
    s += 6 if "nachzahlung" in keys else 0
    s -= abs(dur - 33) * 1.5
    return s


def _score(seed):
    r = sim.run(seed)
    return seed, score_run(r), r["money"], r["n_frames"] / FPS


def pick_seed(n=500):
    with mp.get_context("fork").Pool(os.cpu_count()) as p:
        res = p.map(_score, range(n))
    res = [r for r in res if r[1] is not None]
    res.sort(key=lambda r: -r[1])
    for s, sc, m, d in res[:8]:
        print(f"seed {s}: {m / 100:.2f} € übrig, {d:.1f}s, score {sc:.1f}")
    return res[0][0]


class Run:
    def __init__(self, seed):
        r = sim.run(seed, record=True, tail=END_HOLD)
        self.seed, self.result, self.final_money = seed, r["result"], r["money"]
        self.lv, self.frames = r["level"], r["frames"]
        self.n = len(self.frames)
        self.land = next((i for i, fr in enumerate(self.frames)
                          if any(e[1] == "pocket" for e in fr["events"])), self.n - 1)
        self.events = [(i, e[1], e[2]) for i, fr in enumerate(self.frames) for e in fr["events"]]
        self.hit_events = [e for e in self.events if e[1] == "hit"]
        self.break_frames = {p["idx"]: f for f, t, p in self.events if t == "break"}
        self.hit_frames = {}
        for f, _, p in self.hit_events:
            self.hit_frames.setdefault(p["idx"], []).append(f)
        barrier_keys = [k for k, v in ITEMS.items() if v[3] == "abzug"]
        self.netto_frame = max(f for f, _, p in self.hit_events if p["key"] in barrier_keys)
        cam, c = [], 0.0
        for i, fr in enumerate(self.frames):
            target = min(max(-700.0, fr["by"] - BALL_SCREEN_Y), sim.LEVEL_END - 1600)
            c = target if i == 0 else c + (target - c) * 0.12
            cam.append(c)
        self.cam = cam
        disp, d = [], float(BRUTTO)
        for fr in self.frames:
            d += (fr["money"] - d) * 0.2
            if abs(fr["money"] - d) < 20:
                d = fr["money"]
            disp.append(d)
        self.disp = disp
        self.trail = [(fr["bx"], fr["by"]) for fr in self.frames]
        # chapter entry frames
        self.chapters = []
        for y0, title in CHAPTERS:
            f0 = next((i for i, fr in enumerate(self.frames) if fr["by"] >= y0), None)
            if f0 is not None:
                self.chapters.append((max(f0, 0), title))
        # totals per category for the statement
        self.totals = {c: 0 for c, _ in CATEGORIES}
        for _, _, p in self.hit_events:
            self.totals[ITEMS[p["key"]][3]] += p["cost"]
        self.stamp_times = (0.3, 1.2, 1.6, 1.9, 2.2, 2.5, 2.8, 3.4, 6.2, 7.5)


# --------------------------------------------------------------- drawing
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


def shaded_circle(ctx, x, y, r, color, outline=None, lw=None):
    g = cairo.RadialGradient(x - r * 0.35, y - r * 0.4, r * 0.1, x, y, r)
    g.add_color_stop_rgb(0, *[v / 255 for v in mix(color, (255, 255, 255), 0.5)])
    g.add_color_stop_rgb(0.55, *[v / 255 for v in color])
    g.add_color_stop_rgb(1, *[v / 255 for v in mix(color, (0, 0, 0), 0.45)])
    ctx.set_source(g)
    ctx.arc(x, y, r, 0, 2 * math.pi)
    ctx.fill_preserve()
    ctx.set_source_rgba(*rgb(outline or mix(color, (0, 0, 0), 0.6)))
    ctx.set_line_width(lw or max(2.5, r * 0.09))
    ctx.stroke()


def bar(ctx, x, y, w, h, col, r=12):
    g = cairo.LinearGradient(0, y, 0, y + h)
    g.add_color_stop_rgb(0, *[v / 255 for v in mix(col, (255, 255, 255), 0.3)])
    g.add_color_stop_rgb(1, *[v / 255 for v in mix(col, (0, 0, 0), 0.35)])
    ctx.set_source(g)
    rrect(ctx, x, y, w, h, r)
    ctx.fill_preserve()
    ctx.set_source_rgba(*rgb(mix(col, (0, 0, 0), 0.6)))
    ctx.set_line_width(4)
    ctx.stroke()


def eyes(ctx, x, y, r, angry=True, look=(0, 0.5), scared=0.0):
    ex, ey, er = r * 0.33, -r * 0.2, r * 0.18 * (1 + 0.4 * scared)
    for s in (-1, 1):
        cx, cy = x + s * ex, y + ey
        ctx.set_source_rgb(1, 1, 1)
        ctx.arc(cx, cy, er, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_source_rgb(0.07, 0.06, 0.12)
        ctx.arc(cx + look[0] * er * 0.35, cy + look[1] * er * 0.35, er * (0.55 - 0.2 * scared), 0, 2 * math.pi)
        ctx.fill()
        if angry:
            ctx.set_line_width(max(3, r * 0.08))
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)
            ctx.move_to(cx - s * er * 1.3, cy - er * 1.7)
            ctx.line_to(cx + s * er * 0.9, cy - er * 0.9)
            ctx.stroke()


def mouth(ctx, x, y, r, mood):
    ctx.set_source_rgb(0.05, 0.12, 0.08)
    ctx.set_line_width(max(2.5, r * 0.08))
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


def draw_bg(ctx, cam):
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgb(0, *[v / 255 for v in BG_TOP])
    g.add_color_stop_rgb(1, *[v / 255 for v in BG_BOT])
    ctx.set_source(g)
    ctx.paint()
    ctx.set_line_width(1.5)
    ctx.set_source_rgba(1, 1, 1, 0.04)
    y = -(cam % 90)
    while y < H:
        ctx.move_to(0, y)
        ctx.line_to(W, y)
        y += 90
    for x in range(0, W, 90):
        ctx.move_to(x + 0.5, 0)
        ctx.line_to(x + 0.5, H)
    ctx.stroke()


def flash_of(run, idx, f, dur=0.35):
    hs = [h for h in run.hit_frames.get(idx, []) if h <= f]
    return (max(0.0, 1 - (f - hs[-1]) / (dur * FPS)) if hs else 0.0), len(hs)


def world(ctx, run, f, cam, shake):
    fr = run.frames[f]
    lv = run.lv
    t = f / FPS
    ox, oy = shake[0], -cam + shake[1]
    ctx.save()
    ctx.translate(ox, oy)
    top, bot = cam - 250, cam + H + 250
    spr = []          # (sprite, x, y, angle, alpha) world coords

    def vis(y, pad=250):
        return top - pad < y < bot + pad

    # chapter headings in the world
    for y0, title in CHAPTERS[1:]:
        if vis(y0 + 90):
            spr.append((text_sprite(title, 46, color=(150, 160, 230)), 540, y0 + 90, 0, 0.55))

    # chute backdrop
    if vis(1100, 800):
        ctx.set_source_rgba(0.35, 0.55, 1.0, 0.07)
        ctx.rectangle(395, 640, 290, 920)
        ctx.fill()

    # pockets
    for name, x0, x1, col in lv.pockets:
        y0 = sim.POCKET_TOP
        if not vis(y0, 700):
            continue
        g = cairo.LinearGradient(0, y0 - 60, 0, sim.LEVEL_END)
        g.add_color_stop_rgba(0, *rgb(col, 0.04))
        g.add_color_stop_rgba(1, *rgb(col, 0.6 if name == "urlaub" else 0.38))
        ctx.set_source(g)
        ctx.rectangle(x0, y0 - 60, x1 - x0, sim.LEVEL_END - y0 + 60)
        ctx.fill()
        title, sub, emo = POCKETS[name]
        cx = (x0 + x1) / 2
        spr.append((emoji_sprite(emo, 84), cx, sim.LEVEL_END - 300, 0, 1.0))
        spr.append((fit_sprite(title, x1 - x0 - 30, 48 if name == "urlaub" else 40,
                                color=(255, 236, 150) if name == "urlaub" else (255, 255, 255),
                                stroke=3, stroke_color=mix(col, (0, 0, 0), 0.6)), cx, sim.LEVEL_END - 195, 0, 1.0))
        spr.append((fit_sprite(sub, x1 - x0 - 30, 28, color=(235, 235, 255), path=F_BOLD),
                    cx, sim.LEVEL_END - 140, 0, 0.9))

    # static walls
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

    for idx, ob in enumerate(lv.obstacles):
        x, y, ang = fr["obs"][idx]
        if not vis(y):
            continue
        label, _, cost, cat, emo = ITEMS[ob.key]
        flash, nh = flash_of(run, idx, f)
        used = nh >= ob.max_hits and ob.max_hits < 50
        col = mix(ob.color, (90, 90, 112), 0.65) if used else ob.color
        if flash:
            col = mix(col, (255, 255, 255), flash * 0.8)

        if ob.kind == "barrier":
            bf = run.break_frames.get(idx)
            w_, h_ = ob.extra["w"], ob.extra["h"]
            amt = text_sprite(eur(cost), 30, color=(255, 120, 130), stroke=3, stroke_color=(0, 0, 0))
            lab = fit_sprite(label, 330, 26, color=(205, 220, 255), stroke=3, stroke_color=(0, 0, 0))
            a_lab = 0.45 if (bf is not None and f > bf) else 1.0
            spr.append((emoji_sprite(emo, 46), 215, y - 34, 0, a_lab))
            spr.append((lab, 218, y + 18, 0, a_lab))
            spr.append((amt, 862, y, 0, a_lab))
            # connector lines
            ctx.set_source_rgba(0.6, 0.7, 1, 0.25 * a_lab)
            ctx.set_line_width(2)
            ctx.move_to(385, y)
            ctx.line_to(395 + 4, y)
            ctx.stroke()
            if bf is None or f < bf:
                pulse = 0.5 + 0.5 * math.sin(t * 10 + idx)
                ctx.set_source_rgba(0.45, 0.65, 1, 0.25 + 0.2 * pulse)
                rrect(ctx, x - w_ / 2 - 6, y - h_ / 2 - 6, w_ + 12, h_ + 12, 10)
                ctx.fill()
                bar(ctx, x - w_ / 2, y - h_ / 2, w_, h_, col if not flash else (255, 255, 255), 8)
            else:  # shards falling
                age = (f - bf) / FPS
                if age < 1.0:
                    rng = random.Random(idx)
                    for k in range(8):
                        sx = x - w_ / 2 + (k + 0.5) * w_ / 8
                        vx = rng.uniform(-160, 160)
                        sy = y + rng.uniform(-60, 60) * age + 900 * age * age
                        ctx.save()
                        ctx.translate(sx + vx * age, sy)
                        ctx.rotate(rng.uniform(-6, 6) * age)
                        ctx.set_source_rgba(0.6, 0.75, 1, 1 - age)
                        ctx.rectangle(-w_ / 16, -h_ / 2, w_ / 8 - 3, h_)
                        ctx.fill()
                        ctx.restore()

        elif ob.kind == "spinner":
            L, Th = ob.extra["length"], ob.extra["thick"]
            ctx.save()
            ctx.translate(x, y)
            ctx.rotate(ang)
            if flash:
                ctx.set_source_rgba(*rgb(ob.color, 0.35 * flash))
                rrect(ctx, -L / 2 - 20, -Th / 2 - 20, L + 40, Th + 40, Th / 2 + 20)
                ctx.fill()
            bar(ctx, -L / 2, -Th / 2, L, Th, col)
            ctx.restore()
            ctx.set_source_rgba(0.9, 0.9, 0.96, 1)
            ctx.arc(x, y, 16, 0, 2 * math.pi)
            ctx.fill()
            txt = f"{T['paid']}" if used else f"{label}  {eur_short(cost)}"
            sp = fit_sprite(txt, L - 50, 30, color=(255, 255, 255), stroke=3, stroke_color=(50, 0, 10))
            a = ((-math.degrees(ang) + 90) % 180) - 90
            spr.append((sp, x, y, a, 1.0))
            spr.append((emoji_sprite(emo, 54), x, y - 70 if not used else y - 60, 0, 0.5 if used else 1.0))

        elif ob.kind in ("peg", "bonus"):
            r = ob.extra["r"]
            if ob.kind == "bonus":
                if not used:
                    glow_circle(ctx, x, y, r, ob.color, 0.35 + 0.25 * (0.5 + 0.5 * math.sin(t * 6)))
                if flash:
                    glow_circle(ctx, x, y, r, ob.color, 0.8 * flash, 3.0)
                shaded_circle(ctx, x, y, r, col)
                spr.append((emoji_sprite(emo, int(r * 1.05)), x, y - r * 0.12, 0, 0.5 if used else 1.0))
                spr.append((fit_sprite(label, 300, 26, color=(190, 255, 215), stroke=3, stroke_color=(0, 60, 30)),
                            x, y - r - 34, 0, 0.5 if used else 1.0))
                spr.append((text_sprite(eur_short(cost, True), 26, color=(255, 255, 255), stroke=3,
                                        stroke_color=(0, 70, 30)), x, y + r + 24, 0, 0.5 if used else 1.0))
            else:
                if flash:
                    glow_circle(ctx, x, y, r, (255, 120, 100), 0.8 * flash, 2.6)
                ctx.set_source_rgba(1, 1, 1, 0.13)
                ctx.arc(x, y, r + 7, 0, 2 * math.pi)
                ctx.fill()
                shaded_circle(ctx, x, y, r, (250, 248, 240) if not flash else (255, 190, 190),
                              outline=(150, 150, 175), lw=3)
                spr.append((emoji_sprite(emo, int(r * 1.45)), x, y, 0, 1.0))

        elif ob.kind == "enemy":
            r = ob.extra["r"]
            if flash:
                glow_circle(ctx, x, y, r, ob.color, 0.7 * flash, 2.0)
            shaded_circle(ctx, x, y, r, col)
            eyes(ctx, x, y - r * 0.05, r, angry=True)
            dark = ob.key == "zahnarzt"
            spr.append((fit_sprite(label, int(r * 1.8), 24, color=(30, 40, 70) if dark else (255, 255, 255),
                                   stroke=0 if dark else 2, stroke_color=mix(ob.color, (0, 0, 0), 0.6)),
                        x, y + r * 0.38, 0, 1.0))
            spr.append((emoji_sprite(emo, int(r * 0.7)), x, y - r - r * 0.25, 0, 1.0))
            spr.append((text_sprite(eur_short(cost), 24, color=(255, 120, 130), stroke=3, stroke_color=(0, 0, 0)),
                        x, y + r + 20, 0, 1.0))

        elif ob.kind == "piston":
            w_, h_ = ob.extra["w"], ob.extra["h"]
            if flash:
                ctx.set_source_rgba(*rgb(ob.color, 0.4 * flash))
                rrect(ctx, x - w_ / 2 - 18, y - h_ / 2 - 18, w_ + 36, h_ + 36, 26)
                ctx.fill()
            bar(ctx, x - w_ / 2, y - h_ / 2, w_, h_, col, 14)
            ctx.save()
            rrect(ctx, x - w_ / 2, y - h_ / 2, w_, h_, 14)
            ctx.clip()
            ctx.set_source_rgba(0, 0, 0, 0.16)
            for k in range(-20, 20):
                sx = x - w_ / 2 + k * 36
                ctx.move_to(sx, y + h_ / 2)
                ctx.line_to(sx + 18, y + h_ / 2)
                ctx.line_to(sx + 18 + h_, y - h_ / 2)
                ctx.line_to(sx + h_, y - h_ / 2)
                ctx.close_path()
            ctx.fill()
            ctx.restore()
            txt = T["paid"] if used else label
            spr.append((fit_sprite(txt, w_ - 40, 28, color=(255, 255, 255), stroke=3, stroke_color=(70, 0, 15)),
                        x, y - 8, 0, 1.0))
            spr.append((text_sprite(eur_short(cost), 20, color=(255, 225, 225), path=F_BOLD), x, y + 20, 0,
                        0.5 if used else 1.0))
            spr.append((emoji_sprite(emo, 50), x, y - h_ / 2 - 30, 0, 0.5 if used else 1.0))

    # ball trail + ball
    bx, by, br = fr["bx"], fr["by"], fr["br"]
    trail = run.trail[max(0, f - 14):f + 1]
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    for i in range(1, len(trail)):
        k = i / len(trail)
        ctx.set_source_rgba(0.2, 1.0, 0.55, 0.28 * k)
        ctx.set_line_width(br * 1.6 * k)
        ctx.move_to(*trail[i - 1])
        ctx.line_to(*trail[i])
        ctx.stroke()
    frac = clamp01(fr["money"] / NETTO)
    bcol = mix((255, 70, 70), sim.GREEN, clamp01((frac - 0.05) * 1.8))
    glow_circle(ctx, bx, by, br, bcol, 0.55, 2.5)
    shaded_circle(ctx, bx, by, br, bcol, outline=(10, 60, 30))
    if f > 1:
        vx, vy = bx - run.frames[f - 1]["bx"], by - run.frames[f - 1]["by"]
        n = math.hypot(vx, vy) + 1e-6
        look = (vx / n, vy / n)
    else:
        look = (0, 1)
    recent = any(f - 25 < e[0] <= f and e[2]["cost"] < -1500 for e in run.hit_events)
    mood = 1.0 if recent else clamp01(1 - frac * 1.4)
    if f >= run.land and run.result == "urlaub":
        mood = 0.0
    eyes(ctx, bx, by, br, angry=False, look=look, scared=mood)
    mouth(ctx, bx, by, br, mood)
    spr.append((text_sprite(T["salary"], 26, color=(210, 255, 225), stroke=4, stroke_color=(0, 45, 22)),
                bx, by - br - 28, 0, 1.0))
    ctx.restore()
    return [(sp, x + ox, y + oy, a, al) for sp, x, y, a, al in spr]


# --------------------------------------------------------------- particles
def particles(run, f):
    out = []
    for ef, typ, p in run.events:
        age = (f - ef) / FPS
        if typ == "hit" and 0 <= age < 1.1:
            rng = random.Random(ef * 7919 + int(p["x"]))
            gain = p["cost"] > 0
            n = 8 + min(26, int(abs(p["cost"]) / 2500))
            for _ in range(n):
                a = rng.uniform(0, 2 * math.pi)
                sp = rng.uniform(250, 900)
                vx, vy = math.cos(a) * sp, math.sin(a) * sp - (300 if gain else 100)
                life = 1 - age / 1.1
                coin = gain or rng.random() < 0.45
                out.append(("coin" if coin else "spark", p["x"] + vx * age, p["y"] + vy * age + 1300 * age * age,
                            rng.uniform(5, 11) * life, (255, 215, 60) if coin else p["color"], life, a + age * 8))
        elif typ == "pocket" and 0 <= age < 4.0 and p["name"] == "urlaub":
            rng = random.Random(4242)
            for i in range(170):
                side = -1 if i % 2 else 1
                a = -math.pi / 2 - side * rng.uniform(-0.15, 0.7)
                sp = rng.uniform(900, 1900)
                aa = age - rng.uniform(0, 0.4)
                if aa < 0:
                    continue
                drag = math.exp(-2.2 * aa)
                x = 540 + side * 300 + math.cos(a) * sp * (1 - drag) / 2.2 + 40 * math.sin(aa * 5 + i)
                y = p["y"] + math.sin(a) * sp * (1 - drag) / 2.2 + 260 * aa * aa
                col = rng.choice([(255, 80, 170), (255, 214, 50), (40, 230, 120), (60, 150, 255), (255, 255, 255)])
                out.append(("conf", x, y, rng.uniform(8, 14), col, clamp01(1.4 - aa / 3), aa * rng.uniform(4, 12) + i))
    return out


def draw_particles(ctx, parts, cam, shake):
    for kind, x, y, s, col, life, rot in parts:
        sx, sy = x + shake[0], y - cam + shake[1]
        if not (-50 < sy < H + 50):
            continue
        ctx.save()
        ctx.translate(sx, sy)
        if kind == "spark":
            ctx.set_source_rgba(*rgb(col, life))
            ctx.arc(0, 0, s, 0, 2 * math.pi)
            ctx.fill()
        elif kind == "coin":
            ctx.scale(abs(math.cos(rot)) * 0.9 + 0.1, 1)
            ctx.set_source_rgba(1, 0.84, 0.24, life)
            ctx.arc(0, 0, s * 1.3, 0, 2 * math.pi)
            ctx.fill()
            ctx.set_source_rgba(0.75, 0.55, 0.05, life)
            ctx.set_line_width(2)
            ctx.arc(0, 0, s * 0.8, 0, 2 * math.pi)
            ctx.stroke()
        else:
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
        if 0 <= age < 0.4 and p["cost"] < -1500:
            amp = min(26, 3 + abs(p["cost"]) / 3500) * (1 - age / 0.4) ** 2
            sx += amp * math.sin(ef * 1.7 + age * 70)
            sy += amp * math.cos(ef * 2.3 + age * 63)
    return sx, sy


# --------------------------------------------------------------------- HUD
def money_color(v):
    frac = v / NETTO
    if frac > 0.45:
        return (90, 255, 150)
    if frac > 0.15:
        return (255, 214, 50)
    return (255, 70, 80)


def hud(img, run, f):
    fi = min(f, run.n - 1)
    fr = run.frames[fi]
    d = ImageDraw.Draw(img)
    img.alpha_composite(Image.new("RGBA", (W, HUD_H), (8, 7, 22, 225)), (0, 0))
    d.line([(0, HUD_H), (W, HUD_H)], fill=(255, 255, 255, 45), width=2)
    disp = run.disp[fi]
    is_netto = f >= run.netto_frame + 30
    col = money_color(disp) if is_netto else (235, 240, 255)
    lab = text_sprite(T["netto"] if is_netto else T["brutto"], 28, color=(170, 180, 230), path=F_BOLD)
    paste_c(img, lab, W / 2, 52)
    recent = [e for e in run.hit_events if 0 <= f - e[0] < 12]
    pop = 1.0 + (0.1 * (1 - (f - recent[-1][0]) / 12) if recent else 0)
    paste_c(img, text_sprite(eur(max(disp, -99999)), 92, color=col, stroke=5, stroke_color=(0, 0, 0)),
            W / 2, 128, scale=pop)

    # Kontoauszug: last 3 bookings
    booked = [e for e in run.hit_events if e[0] <= f][-3:][::-1]
    y0 = 212
    box = Image.new("RGBA", (W - 140, 3 * 46 + 6), (0, 0, 0, 0))
    ImageDraw.Draw(box).rounded_rectangle([0, 0, box.width - 1, box.height - 1], radius=18,
                                          fill=(255, 255, 255, 22))
    img.alpha_composite(box, (70, y0 - 24))
    for i, (ef, _, p) in enumerate(booked):
        age = (f - ef) / FPS
        slide = ease_out(age / 0.25) if i == 0 else 1.0
        a = (1.0, 0.7, 0.45)[i] * clamp01(age / 0.15 if i == 0 else 1)
        y = y0 + i * 46
        _, name, cost, cat, emo = ITEMS[p["key"]]
        x_off = (1 - slide) * -60
        paste_c(img, emoji_sprite(emo, 30), 110 + x_off, y, alpha=a)
        paste_l(img, text_sprite(name, 28, color=(225, 230, 255), path=F_INTER), 140 + x_off, y, alpha=a)
        paste_r(img, text_sprite(eur(cost, True), 28, color=(120, 255, 160) if cost > 0 else (255, 110, 120),
                                 path=F_INTER_B), W - 100 + x_off, y, alpha=a)
    # month progress
    y = 395
    prog = clamp01((fr["by"] - 300) / (sim.POCKET_TOP + 150 - 300))
    day = 1 + int(prog * 30)
    paste_l(img, text_sprite(f"{day}. {T['month']}", 28, color=(235, 235, 255), path=F_BOLD), 70, y)
    x0, x1 = 300, 920
    d.rounded_rectangle([x0, y - 9, x1, y + 9], radius=9, fill=(40, 40, 72, 255))
    d.rounded_rectangle([x0, y - 9, x0 + max(18, (x1 - x0) * prog), y + 9], radius=9,
                        fill=(money_color(disp) if is_netto else (150, 170, 255)) + (255,))
    cx = x0 + (x1 - x0) * prog
    d.ellipse([cx - 15, y - 15, cx + 15, y + 15], fill=(255, 255, 255, 255))
    paste_c(img, emoji_sprite("🏝", 52), x1 + 52, y - 4)

    # hit popups (amount + name)
    for ef, typ, p in run.hit_events:
        age = (f - ef) / FPS
        if not (0 <= age < 1.3):
            continue
        cost = p["cost"]
        gain = cost > 0
        size = 44 + min(40, int(abs(cost) / 2200))
        amt = text_sprite(eur(cost, True), size, color=(120, 255, 160) if gain else (255, 80, 90),
                          stroke=5, stroke_color=(0, 0, 0))
        nm = text_sprite(ITEMS[p["key"]][1], 28, color=(255, 255, 255), stroke=4, stroke_color=(0, 0, 0), path=F_BOLD)
        wmax = max(amt.width, nm.width)
        sx = min(max(p["x"], wmax / 2 + 30), W - wmax / 2 - 30)
        sy = max(p["y"] - run.cam[ef] - 80 - 140 * ease_out(age / 1.3), HUD_H + 70)
        sc = max(0.05, ease_back(age / 0.25) if age < 0.25 else 1.0)
        al = clamp01((1.3 - age) / 0.35)
        paste_c(img, amt, sx, sy, alpha=al, scale=sc)
        paste_c(img, nm, sx, sy + size * 0.75 + 8, alpha=al, scale=sc)


@lru_cache(maxsize=64)
def _vig(color, a):
    yy, xx = np.mgrid[0:H // 4, 0:W // 4]
    r = np.sqrt(((xx - W / 8) / (W / 8)) ** 2 + ((yy - H / 8) / (H / 8)) ** 2)
    alpha = (np.clip((r - 0.55) / 0.6, 0, 1) ** 1.5 * a).astype(np.uint8)
    arr = np.zeros((H // 4, W // 4, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3] = color[0], color[1], color[2], alpha
    return Image.fromarray(arr, "RGBA").resize((W, H), Image.BILINEAR)


def vignette(color, a):
    return _vig(color, max(0, min(255, a // 10 * 10)))


def flashes(img, run, f):
    red = green = 0.0
    for ef, typ, p in run.hit_events:
        age = (f - ef) / FPS
        if 0 <= age < 0.45:
            k = 1 - age / 0.45
            if p["cost"] <= -5000:
                red = max(red, k * min(1, abs(p["cost"]) / 60000 + 0.35))
            elif p["cost"] > 0:
                green = max(green, k * (1 if p["cost"] > 1000 else 0.5))
    if red > 0.02:
        img.alpha_composite(vignette((255, 30, 50), int(150 * red)))
    if green > 0.02:
        img.alpha_composite(vignette((40, 255, 120), int(130 * green)))


# ---------------------------------------------------------------- overlays
def badge(img, text, cy, k, bg=(255, 214, 50), fg=(20, 15, 30), size=40):
    sp = text_sprite(text, size, color=fg)
    card = Image.new("RGBA", (sp.width + 70, sp.height + 40), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([0, 0, card.width - 1, card.height - 1], radius=card.height // 2,
                                           fill=bg + (255,))
    paste_c(card, sp, card.width / 2, card.height / 2)
    paste_c(img, card, W / 2, cy, scale=max(0.05, k))


def overlays(img, run, f):
    t = f / FPS
    # hook
    if t < 3.2:
        a = clamp01((3.2 - t) / 0.35)
        img.alpha_composite(Image.new("RGBA", (W, 400), (0, 0, 0, int(165 * a))), (0, HUD_H + 2))
        rows = [(T["hook0"], 70, (255, 255, 255)), (T["hook1"], 62, (90, 255, 150)),
                (T["hook2"], 76, (255, 214, 50))]
        y = HUD_H + 75
        for i, (txt, size, col) in enumerate(rows):
            k = ease_back((t - i * 0.2) / 0.35)
            if k > 0:
                paste_c(img, fit_sprite(txt, W - 160, size, color=col, stroke=6, stroke_color=(0, 0, 0)),
                        W / 2, y, alpha=a, scale=max(0.05, k))
            y += size + 34
        paste_c(img, fit_sprite(T["foot"], W - 120, 22, color=(200, 200, 230), path=F_INTER), W / 2, y + 6,
                alpha=a * clamp01((t - 0.8) / 0.3))
    # chapter badge
    elif f < run.land:
        for cf, title in run.chapters[1:]:
            age = (f - cf) / FPS
            if 0 <= age < 2.0:
                k = ease_back(age / 0.3) if age < 1.7 else 1 - (age - 1.7) / 0.3
                badge(img, title, HUD_H + 70, k, size=38)
    # NETTO stamp after the payroll deductions
    age = (f - run.netto_frame) / FPS - 0.45
    if 0 <= age < 1.8:
        k = ease_back(age / 0.3)
        a = clamp01((1.8 - age) / 0.3)
        card = Image.new("RGBA", (760, 250), (0, 0, 0, 0))
        dd = ImageDraw.Draw(card)
        dd.rounded_rectangle([6, 6, 753, 243], radius=30, outline=(90, 255, 150, 255), width=10,
                             fill=(10, 30, 20, 220))
        paste_c(card, text_sprite(T["netto_stamp"], 60, color=(90, 255, 150)), 380, 78)
        paste_c(card, text_sprite(eur(NETTO), 74, color=(255, 255, 255)), 380, 170)
        paste_c(img, card, W / 2, 760, alpha=a, scale=max(0.05, k), angle=-6)
        sub = fit_sprite(f"{eur(NETTO - BRUTTO)} weg, bevor du was gekauft hast", W - 140, 30,
                         color=(255, 200, 200), stroke=4, stroke_color=(0, 0, 0), path=F_BOLD)
        paste_c(img, sub, W / 2, 935, alpha=a * clamp01((age - 0.3) / 0.3))
    fr = run.frames[min(f, run.n - 1)]
    if fr["slow"] and f < run.land:
        k = 0.5 + 0.5 * math.sin(t * 9)
        paste_c(img, fit_sprite(T["comeon"], W - 160, 52, color=(255, 255, 255), stroke=5,
                                stroke_color=(0, 0, 0)), W / 2, HUD_H + 70, scale=1 + 0.05 * k)
        img.alpha_composite(vignette((0, 0, 0), 120))
    if f >= run.land:
        ending(img, run, (f - run.land) / FPS)


def ending(img, run, e):
    ok = run.result == "urlaub"
    if e > 0.25:
        img.alpha_composite(Image.new("RGBA", (W, H), (5, 4, 15, int(195 * clamp01((e - 0.25) / 0.5)))))
    if e > 0.3:
        k = ease_back((e - 0.3) / 0.4)
        y = 560 if e < 1.0 else 560 - 230 * ease_out((e - 1.0) / 0.4)
        paste_c(img, fit_sprite(T["made_it"] if ok else T["broke"], W - 120, 120, color=(255, 214, 50),
                                stroke=8, stroke_color=(60, 30, 0)), W / 2, y,
                scale=max(0.05, k), angle=math.sin(e * 5) * 2.5)
    # receipt
    if e > 1.1:
        k = ease_out((e - 1.1) / 0.45)
        rw, rh = 900, 700
        rc = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
        d = ImageDraw.Draw(rc)
        d.rounded_rectangle([0, 0, rw - 1, rh - 1], radius=26, fill=(250, 248, 240, 255))
        for zx in range(0, rw, 30):   # zigzag bottom edge
            d.polygon([(zx, rh - 14), (zx + 15, rh), (zx + 30, rh - 14)], fill=(5, 4, 15, 0))
        paste_c(rc, text_sprite(T["statement"], 34, color=(30, 30, 50)), rw / 2, 52)
        d.line([(40, 92), (rw - 40, 92)], fill=(30, 30, 50, 255), width=3)
        lines = [(T["brutto_line"], BRUTTO, "")]
        for cat, name in CATEGORIES:
            if run.totals[cat]:
                lines.append((name, run.totals[cat], cat))
        y = 140
        shown = 0
        for i, (name, val, cat) in enumerate(lines):
            if e < 1.5 + i * 0.3:
                break
            shown += 1
            colv = (30, 30, 50) if not cat else ((20, 150, 70) if val > 0 else (210, 40, 60))
            paste_l(rc, text_sprite(name, 34, color=(40, 40, 60), path=F_INTER), 50, y)
            paste_r(rc, text_sprite(eur(val, bool(cat)), 36, color=colv, path=F_INTER_B), rw - 50, y)
            y += 70
        y_sum = 140 + 70 * len(lines) + 10
        if e > 1.5 + len(lines) * 0.3:
            d.line([(40, y_sum - 40), (rw - 40, y_sum - 40)], fill=(30, 30, 50, 255), width=3)
            paste_l(rc, text_sprite(T["rest"], 34, color=(30, 30, 50), path=F_INTER_B), 50, y_sum + 10)
            cnt = clamp01((e - 1.6 - len(lines) * 0.3) / 0.8)
            val = run.final_money + (1 - ease_out(cnt)) * 20000
            paste_r(rc, text_sprite(eur(val), 46, color=(210, 40, 60), path=F_INTER_B), rw - 50, y_sum + 10)
            paste_c(rc, fit_sprite(T["foot"], rw - 80, 20, color=(120, 120, 140), path=F_INTER), rw / 2, rh - 60)
        img.alpha_composite(rc.crop((0, 0, rw, int(rh * k)) if k < 1 else (0, 0, rw, rh)),
                            (int((W - rw) / 2), 450))
    t_punch = 1.9 + 7 * 0.3 + 0.9
    if e > t_punch:
        k = ease_back((e - t_punch) / 0.4)
        paste_c(img, fit_sprite(T["punch"], W - 100, 86, color=(255, 255, 255), stroke=4, stroke_color=(0, 0, 0),
                                path=F_HAND), W / 2, 1235, scale=max(0.05, k), angle=-4)
    t_cta = t_punch + 1.3
    if e > t_cta:
        k = ease_back((e - t_cta) / 0.4)
        cw = W - 120
        card = Image.new("RGBA", (cw, 300), (0, 0, 0, 0))
        ImageDraw.Draw(card).rounded_rectangle([0, 0, cw - 1, 299], radius=40, fill=(255, 214, 50, 255))
        paste_c(card, fit_sprite(T["cta1"], cw - 80, 58, color=(20, 15, 30)), cw / 2, 70)
        paste_c(card, fit_sprite(T["cta2"], cw - 80, 70, color=(20, 15, 30)), cw / 2, 155)
        paste_c(card, fit_sprite(T["cta3"], cw - 100, 30, color=(70, 50, 20), path=F_BOLD), cw / 2, 240)
        paste_c(img, card, W / 2, 1460, scale=max(0.05, k))


# ------------------------------------------------------------------ frame
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
    flashes(img, run, f)
    hud(img, run, f)
    overlays(img, run, f)
    return img.convert("RGB")


RUN = None


def _worker(args):
    i, a, b, path = args
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(a, b):
        p.stdin.write(render_frame(RUN, f).tobytes())
    p.stdin.close()
    p.wait()
    return path


def render_video(run, out):
    global RUN
    RUN = run
    BUILD.mkdir(parents=True, exist_ok=True)
    nw = os.cpu_count() or 1
    bounds = [run.n * k // nw for k in range(nw + 1)]
    jobs = [(i, bounds[i], bounds[i + 1], str(BUILD / f"part{i}.mp4")) for i in range(nw)]
    with mp.get_context("fork").Pool(nw) as pool:
        parts = pool.map(_worker, jobs)
    lst = BUILD / "parts.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    wav = BUILD / "sfx.wav"
    sfx.build(run, str(wav), FPS)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(wav),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)],
                   check=True)
    print("wrote", out, f"({run.n / FPS:.1f}s, seed {run.seed}, {run.result}, {eur(run.final_money)} übrig)")


def main():
    args = sys.argv[1:]
    out = Path(os.environ.get("VIDEO_OUT", ROOT / "gehalt-video.mp4"))
    if args and args[0] == "preview":
        seed = int(os.environ.get("SEED", "-1"))
        run = Run(pick_seed() if seed < 0 else seed)
        d = BUILD / "stills"
        d.mkdir(parents=True, exist_ok=True)
        for s in args[1:]:
            if s == "end":
                f = run.n - 1
            elif s.startswith("L"):
                f = min(run.land + int(float(s[1:]) * FPS), run.n - 1)
            else:
                f = min(int(float(s) * FPS), run.n - 1)
            render_frame(run, f).save(d / f"still_{s}.png")
        print("duration", round(run.n / FPS, 1), "land", round(run.land / FPS, 1), run.result, eur(run.final_money))
        return
    seed = int(args[1]) if args and args[0] == "seed" else pick_seed()
    print("using seed", seed)
    render_video(Run(seed), out)


if __name__ == "__main__":
    main()
