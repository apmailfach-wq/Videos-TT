"""Render schlaf-5-phasen.mp4 (1080x1920, 30 fps) from build/schlaf/sim.npz.

Night bedroom, a puffy snoring pillow-word "SCHLAF", a hyperactive gummy word
"Nur 1 Video" that bursts into 50 TikTok balls, and an iron "03:47 UHR" block.
Usage:  python3 sim.py && python3 audio.py && python3 render.py
        python3 render.py preview 3 7 12 20 26   # stills -> build/schlaf/stills/
"""
import json
import math
import os
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim  # noqa: E402

ROOT = sim.ROOT
BUILD = sim.BUILD
FONTS = ROOT / "fonts"
W, H, FPS, NF = sim.W, sim.H, sim.FPS, sim.NF
FLOOR = sim.FLOOR

F_HEAD = str(FONTS / "Unbounded_900Black.ttf")
F_HEAD_B = str(FONTS / "Unbounded_700Bold.ttf")
F_HAND = str(FONTS / "Caveat_700Bold.ttf")
F_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_XB = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
F_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

YELLOW = (255, 214, 10)
INK = (14, 12, 26)


@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, size)


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_back(x, s=1.7):
    x = clamp01(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


# ------------------------------------------------------------------ puffy material
def puffy(mask, base, blur=12, depth=26, gloss=0.55, shine=40, amb=0.52, rim=None):
    """Turn an L mask into a soft, inflated 3D-looking RGBA sprite."""
    m = np.asarray(mask, np.float32) / 255
    hgt = np.asarray(mask.filter(ImageFilter.GaussianBlur(blur)), np.float32) / 255
    hgt = np.sqrt(np.clip(hgt, 0, 1))
    gy, gx = np.gradient(hgt)
    nx, ny, nz = -gx * depth, -gy * depth, np.ones_like(hgt)
    nl = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    nx, ny, nz = nx / nl, ny / nl, nz / nl
    L = np.array([-0.45, -0.75, 0.55]); L /= np.linalg.norm(L)
    Hh = L + np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
    dif = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    spec = np.clip(nx * Hh[0] + ny * Hh[1] + nz * Hh[2], 0, 1) ** shine
    col = np.array(base, np.float32)[None, None, :] * (amb + (1 - amb) * 1.25 * dif[..., None])
    col += 255 * gloss * spec[..., None]
    if rim is not None:   # darker edge for readability
        edge = np.clip(1 - hgt * 1.6, 0, 1)[..., None]
        col = col * (1 - 0.55 * edge) + np.array(rim, np.float32) * 0.55 * edge
    out = np.dstack([np.clip(col, 0, 255), m * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def text_mask(text, f, stroke=0, pad=30, spacing=0):
    bb = f.getbbox(text, stroke_width=stroke)
    w, h = bb[2] - bb[0] + pad * 2, bb[3] - bb[1] + pad * 2
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).text((pad - bb[0], pad - bb[1]), text, font=f, fill=255,
                            stroke_width=stroke, stroke_fill=255)
    return im


def caption(text, size, fill=(255, 255, 255), fpath=F_BLACK, stroke=9, sfill=INK, maxw=980, lh=1.12):
    """Multi-line TikTok caption with heavy outline, centered. Returns RGBA."""
    f = font(fpath, size)
    lines = text.split("\n")
    widths = [f.getlength(l) for l in lines]
    asc, desc = f.getmetrics()
    lhpx = int(size * lh)
    w = int(max(widths)) + stroke * 2 + 20
    h = lhpx * len(lines) + stroke * 2 + desc + 10
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        x = (w - widths[i]) / 2
        d.text((x, stroke + 4 + i * lhpx), l, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(im.getchannel("A").point(lambda a: a * 0.5))
    out = Image.new("RGBA", (w + 20, h + 24), (0, 0, 0, 0))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)), (10, 18))
    out.alpha_composite(im, (10, 6))
    return out


def pill(text, size, bg, fg, fpath=F_BLACK, padx=26, pady=14):
    f = font(fpath, size)
    bb = f.getbbox(text)
    w = bb[2] - bb[0] + padx * 2
    h = size + pady * 2
    im = Image.new("RGBA", (w + 12, h + 14), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 10, w + 6, h + 10), radius=h // 2, fill=(0, 0, 0, 110))
    d.rounded_rectangle((6, 4, w + 6, h + 4), radius=h // 2, fill=bg, outline=INK, width=4)
    d.text((6 + padx - bb[0], 4 + pady + (size - (bb[3] - bb[1])) / 2 - bb[1]), text, font=f, fill=fg)
    return im


# ------------------------------------------------------------------ sprites
S = {}


def build_sprites():
    # background: night bedroom
    yy = np.linspace(0, 1, H)[:, None]
    top, bot = np.array([12, 14, 38]), np.array([38, 26, 72])
    grad = (top + (bot - top) * yy[..., None] ** 1.2) * np.ones((1, W, 1))
    bg = Image.fromarray(grad.astype(np.uint8), "RGB")
    d = ImageDraw.Draw(bg, "RGBA")
    # window with moon
    wx0, wy0, wx1, wy1 = 90, 640, 430, 1060
    d.rounded_rectangle((wx0 - 16, wy0 - 16, wx1 + 16, wy1 + 16), 26, fill=(58, 46, 98))
    d.rounded_rectangle((wx0, wy0, wx1, wy1), 18, fill=(22, 30, 72))
    moon = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    md = ImageDraw.Draw(moon)
    md.ellipse((250, 700, 370, 820), fill=(255, 240, 190, 255))
    md.ellipse((285, 690, 400, 805), fill=(22, 30, 72, 255))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((210, 660, 410, 860), fill=(255, 230, 160, 60))
    bg.paste(glow.filter(ImageFilter.GaussianBlur(40)), (0, 0), glow.filter(ImageFilter.GaussianBlur(40)))
    bg.paste(moon, (0, 0), moon)
    d = ImageDraw.Draw(bg, "RGBA")
    d.rectangle((wx0 + (wx1 - wx0) // 2 - 6, wy0, wx0 + (wx1 - wx0) // 2 + 6, wy1), fill=(58, 46, 98))
    d.rectangle((wx0, wy0 + (wy1 - wy0) // 2 - 6, wx1, wy0 + (wy1 - wy0) // 2 + 6), fill=(58, 46, 98))
    # curtain hints
    d.polygon([(wx0 - 40, wy0 - 40), (wx0 + 40, wy0 - 40), (wx0 - 10, wy1 + 80), (wx0 - 60, wy1 + 80)],
              fill=(120, 60, 120, 200))
    d.polygon([(wx1 + 40, wy0 - 40), (wx1 - 40, wy0 - 40), (wx1 + 10, wy1 + 80), (wx1 + 60, wy1 + 80)],
              fill=(120, 60, 120, 200))
    # bed / blanket
    d.rounded_rectangle((-40, FLOOR - 30, W + 40, H + 40), 60, fill=(78, 62, 150))
    d.rounded_rectangle((-40, FLOOR - 30, W + 40, FLOOR + 10), 30, fill=(110, 92, 190))
    for i in range(7):
        x = 60 + i * 160
        d.arc((x - 120, FLOOR + 40 + (i % 2) * 40, x + 120, FLOOR + 260 + (i % 2) * 40), 200, 340,
              fill=(98, 80, 175), width=6)
    # checker pattern on blanket
    for gy in range(FLOOR + 120, H, 120):
        for gx in range(-60 + (gy // 120 % 2) * 60, W, 120):
            d.rounded_rectangle((gx, gy, gx + 50, gy + 50), 14, fill=(90, 72, 168))
    S["bg_night"] = bg
    # phone-glow variant
    gl = Image.new("RGB", (W, H), (0, 0, 0))
    g2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g2)
    gd.ellipse((-300, 300, 700, 1300), fill=(37, 244, 238, 150))
    gd.ellipse((400, 700, 1400, 1700), fill=(254, 44, 85, 150))
    g2 = g2.filter(ImageFilter.GaussianBlur(160))
    gl.paste(g2, (0, 0), g2)
    S["glow"] = gl

    # stars
    rng = np.random.default_rng(7)
    S["stars"] = [(rng.uniform(20, W - 20), rng.uniform(150, 1150), rng.uniform(1.5, 4), rng.uniform(0, 6.28))
                  for _ in range(60)]

    # pillow-word SCHLAF
    f = font(F_HEAD, 210)
    m = text_mask("SCHLAF", f, stroke=30, pad=40)
    m = m.resize((m.width, int(m.height * 1.25)), Image.LANCZOS)
    pw = Image.new("L", m.size, 0)
    pw.paste(m)
    pil = puffy(pw, (226, 214, 255), blur=22, depth=34, gloss=0.35, shine=18, amb=0.5, rim=(120, 96, 200))
    # letters slightly emphasised inside the cushion
    inner = text_mask("SCHLAF", f, stroke=0, pad=40 + 30)
    inner = inner.resize((m.width, int(inner.height * 1.25 * m.width / inner.width)), Image.LANCZOS)
    inner = inner.crop((0, (inner.height - m.height) // 2, m.width, (inner.height - m.height) // 2 + m.height))
    lines = Image.new("RGBA", m.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    ed = inner.filter(ImageFilter.FIND_EDGES).point(lambda v: 255 if v > 60 else 0)
    # cushion seam (stroke-only area) a bit darker, letters lighter -> readable word
    seam = np.clip(np.asarray(pw, np.float32) - np.asarray(inner, np.float32), 0, 255) / 255
    seam = np.asarray(Image.fromarray((seam * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5)),
                      np.float32)[..., None] / 255
    arr = np.asarray(pil).astype(np.float32)
    arr[..., :3] = arr[..., :3] * (1 - 0.28 * seam) + np.array([90, 60, 180]) * 0.28 * seam
    pil = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    lines.paste((120, 90, 210, 230), (0, 0), ed.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2)))
    pil.alpha_composite(lines)
    bbox = pil.getbbox()
    pil = pil.crop(bbox)
    S["pillow"] = pil.resize((sim.PIL_W0, sim.PIL_H0 + 30), Image.LANCZOS)
    # night cap on the S
    cap = Image.new("RGBA", (260, 230), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cap)
    cd.polygon([(20, 200), (240, 200), (60, 30)], fill=(60, 140, 255))
    cd.rounded_rectangle((10, 180, 250, 225), 22, fill=(255, 255, 255))
    for k in range(4):
        cd.ellipse((70 + k * 40, 120 - k * 18, 82 + k * 40, 132 - k * 18), fill=(255, 214, 10))
    cd.ellipse((30, 8, 82, 60), fill=(255, 255, 255))
    S["cap"] = cap.rotate(18, resample=Image.BICUBIC, expand=True)

    # rubber word "Nur 1 Video"
    f = font(F_HEAD, 104)
    m = text_mask("Nur 1 Video", f, stroke=5, pad=30)
    wd = puffy(m, (255, 96, 48), blur=6, depth=20, gloss=0.95, shine=55, amb=0.55, rim=(120, 10, 30))
    edge = m.filter(ImageFilter.MaxFilter(9))
    out = Image.new("RGBA", m.size, (0, 0, 0, 0))
    out.paste((90, 8, 28, 255), (0, 0), edge)
    out.alpha_composite(wd)
    S["word"] = out.crop(out.getbbox())

    # 50 balls
    r = np.load(BUILD / "sim.npz")["r"]
    S["balls"] = []
    for i, ri in enumerate(r):
        ss = 3
        R = int(ri * ss)
        mk = Image.new("L", (2 * R + 40, 2 * R + 40), 0)
        ImageDraw.Draw(mk).ellipse((20, 20, 20 + 2 * R, 20 + 2 * R), fill=255)
        col = sim.PALETTE[i % len(sim.PALETTE)]
        b = puffy(mk, col, blur=R // 2, depth=40, gloss=0.9, shine=60, amb=0.55,
                  rim=tuple(int(c * 0.45) for c in col))
        bd = ImageDraw.Draw(b)
        light = sum(col) > 520
        tf = font(F_BLACK, int(R * 0.5))
        tx = "TikTok"
        tw = tf.getlength(tx)
        bd.text((20 + R - tw / 2, 20 + R - R * 0.33), tx, font=tf,
                fill=INK if light else (255, 255, 255),
                stroke_width=int(R * 0.06), stroke_fill=(255, 255, 255) if light else INK)
        # tiny play triangle
        tri = R * 0.2
        cx, cy = 20 + R, 20 + R - R * 0.48
        bd.polygon([(cx - tri * 0.6, cy - tri * 0.7), (cx - tri * 0.6, cy + tri * 0.7), (cx + tri * 0.8, cy)],
                   fill=INK if light else (255, 255, 255))
        sz = (b.width // ss, b.height // ss)
        S["balls"].append(b.resize(sz, Image.LANCZOS))

    # iron block 03:47 UHR
    bw, bh = 940, 430
    mk = Image.new("L", (bw + 60, bh + 60), 0)
    ImageDraw.Draw(mk).rounded_rectangle((30, 30, 30 + bw, 30 + bh), 26, fill=255)
    blk = puffy(mk, (104, 110, 122), blur=10, depth=14, gloss=0.25, shine=12, amb=0.6, rim=(30, 32, 38))
    arr = np.asarray(blk).astype(np.float32)
    noise = np.random.default_rng(3).normal(0, 9, arr.shape[:2])
    streak = np.random.default_rng(4).normal(0, 1, (1, arr.shape[1])) * 6
    arr[..., :3] += (noise + streak)[..., None]
    blk = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    bd = ImageDraw.Draw(blk)
    for (rx, ry) in [(80, 80), (bw - 20, 80), (80, bh - 20), (bw - 20, bh - 20)]:
        rv = Image.new("L", (60, 60), 0)
        ImageDraw.Draw(rv).ellipse((14, 14, 46, 46), fill=255)
        rp = puffy(rv, (150, 156, 168), blur=5, depth=18, gloss=0.6, shine=30)
        blk.alpha_composite(rp, (rx - 30, ry - 30))
    f1 = font(F_HEAD, 190)
    f2 = font(F_HEAD_B, 74)
    for txt, ff, y in [("03:47", f1, 60), ("UHR", f2, 300)]:
        tw = ff.getlength(txt)
        x = 30 + (bw - tw) / 2
        bd.text((x, y + 4), txt, font=ff, fill=(170, 176, 188))
        bd.text((x, y - 3), txt, font=ff, fill=(28, 30, 36))
        bd.text((x, y), txt, font=ff, fill=(52, 56, 64))
    S["block"] = blk

    # captions
    S["head1"] = caption("DIE 5 PHASEN VON", 50, fill=YELLOW, fpath=F_HEAD, stroke=8)
    S["head2"] = caption("„Ich geh heute\nfrüh schlafen“", 74, fpath=F_HEAD, stroke=11, lh=1.18)
    S["phases"] = {
        1: (pill("PHASE 1", 40, YELLOW, INK), caption("Der Plan:\n„Heute schlaf ich mal früh.“", 54)),
        2: (pill("PHASE 2", 40, YELLOW, INK), caption("Die Ausnahme:\n„Nur EIN Video. Dann Schluss.“", 54)),
        3: (pill("PHASE 3", 40, YELLOW, INK), caption("Die Explosion:\n„Okay … noch eins. Und noch eins.“", 50)),
        4: (pill("PHASE 4", 40, YELLOW, INK), caption("Das Begräbnis:\n„Wo ist meine Nacht hin?!“", 54)),
        5: (pill("PHASE 5", 40, (255, 70, 80), (255, 255, 255)), caption("Die Erkenntnis.", 64)),
    }
    S["cta"] = caption("Welche Phase bist du\ngerade? 1–5 👇".replace(" 👇", ""), 60, fill=YELLOW)
    S["cta2"] = caption("Schreib die Zahl in die Kommentare", 40)
    S["z"] = [caption("z", s_, fill=(230, 225, 255), fpath=F_HAND, stroke=5, sfill=(60, 40, 120))
              for s_ in (90, 120, 150)]


D = {}


def init():
    d = np.load(BUILD / "sim.npz")
    for k in d.files:
        D[k] = d[k]
    build_sprites()


# ------------------------------------------------------------------ timeline helpers
def phase_at(t):
    split_t, impact_t = D["meta"][0], D["meta"][1]
    if t < sim.T_PH2:
        return 1, 0.0
    if t < split_t:
        return 2, sim.T_PH2
    if t < sim.T_PH4:
        return 3, split_t
    if t < impact_t + 0.7:
        return 4, sim.T_PH4
    return 5, impact_t + 0.7


def clock_at(t):
    split_t, impact_t = D["meta"][0], D["meta"][1]
    if t < split_t:
        mins = 22 * 60 + 30 + t * 1.3
    elif t < sim.T_PH4:
        u = (t - split_t) / (sim.T_PH4 - split_t)
        mins = 22 * 60 + 42 + u ** 1.6 * 110
    else:
        u = min(1.0, (t - sim.T_PH4) / (sim.T_BLOCK - 1.2 - sim.T_PH4))
        mins = 24 * 60 + 32 + u ** 1.3 * (3 * 60 + 47 - 32 - 6)
    if impact_t <= t:
        return "03:47", True
    if sim.T_BLOCK - 1.2 <= t:
        return "??:??", False
    mins = int(mins) % (24 * 60)
    return f"{mins // 60:02d}:{mins % 60:02d}", False


def paste_c(fr, im, cx, cy, scale=1.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1) > 0.01:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if alpha < 0.999:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda a: int(a * alpha)))
    fr.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


# ------------------------------------------------------------------ frame
def render_frame(fi):
    t = fi / FPS
    split_t, impact_t = D["meta"][0], D["meta"][1]
    # background + phone glow (pulses on the beat during the chaos)
    glow = 0.0
    if t >= split_t:
        beat = 0.5 + 0.5 * math.cos(2 * math.pi * (t - split_t) * 150 / 60)
        glow = min(1.0, (t - split_t) / 0.4) * (0.35 + 0.25 * beat)
        if t > sim.T_PH4:
            glow *= max(0.45, 1 - (t - sim.T_PH4) / 10)
    if t >= sim.T_BLOCK:
        glow *= max(0.0, 1 - (t - sim.T_BLOCK) / 0.3)
    bg = Image.blend(S["bg_night"], ImageChopsAdd(S["bg_night"], S["glow"]), glow) if glow > 0.01 \
        else S["bg_night"].copy()
    fr = bg.convert("RGBA")
    d = ImageDraw.Draw(fr)
    for (x, y, rr, ph) in S["stars"]:
        a = 0.5 + 0.5 * math.sin(t * 2.2 + ph)
        c = int(140 + 115 * a)
        rr2 = rr * (0.6 + 0.4 * a)
        d.ellipse((x - rr2, y - rr2, x + rr2, y + rr2), fill=(c, c, min(255, c + 20)))

    # pillow
    pw, ph, bam = D["pil"][fi]
    psp = S["pillow"]
    hh = int(ph + 30 * ph / sim.PIL_H0)
    if hh > 4:
        sh = Image.new("RGBA", (int(pw) + 120, 90), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((20, 20, sh.width - 20, 70), fill=(10, 6, 30, 150))
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        fr.alpha_composite(sh, (int(540 - sh.width / 2), FLOOR - 50))
        im = psp.resize((int(pw), hh), Image.BILINEAR)
        fr.alpha_composite(im, (int(540 - pw / 2), int(FLOOR - hh + 12)))
        # night cap sits on the "S"
        cap = S["cap"]
        cs = ph / sim.PIL_H0
        cim = cap.resize((max(1, int(cap.width * 0.8 * (pw / sim.PIL_W0))), max(1, int(cap.height * 0.8 * cs))),
                         Image.BILINEAR)
        fr.alpha_composite(cim, (int(540 - pw / 2 - 10), int(FLOOR - hh + 12 - cim.height * 0.62)))
        # sleepy face on the pillow (closed eyes while asleep, wide eyes when the balls explode)
        fy = FLOOR - hh * 0.5 + 10
        if t < split_t:
            for ex in (540 - 70, 540 + 70):
                d.arc((ex - 30, fy - 40, ex + 30, fy - 4), 20, 160, fill=(70, 50, 140), width=8)
            mo = max(4.0, 11 + 160 * (D["pil"][fi][1] / sim.PIL_H0 - 1))
            d.ellipse((540 - mo, fy + 14, 540 + mo, fy + 14 + mo * 1.4), fill=(70, 50, 140))
        elif t < sim.T_PH4 + 1.5:
            for ex in (540 - 75, 540 + 75):
                d.ellipse((ex - 30, fy - 52, ex + 30, fy + 8), fill=(255, 255, 255), outline=(70, 50, 140), width=6)
                jx = 6 * math.sin(t * 40 + ex)
                d.ellipse((ex - 10 + jx, fy - 32, ex + 10 + jx, fy - 12), fill=INK)
            d.ellipse((540 - 22, fy + 18, 540 + 22, fy + 62), fill=(70, 50, 140))
        # zZz while snoring
        if t < sim.T_DROP + 0.3:
            fade = 1 - clamp01((t - sim.T_DROP) / 0.3)
            for k in range(3):
                u = ((t / 3.2) + k / 3) % 1.0
                zx = 540 + pw * 0.38 + u * 90 + 14 * math.sin(u * 6 + k)
                zy = FLOOR - hh - 10 - u * 260
                paste_c(fr, S["z"][k], zx, zy, 0.6 + 0.6 * u, fade * min(1, u * 4) * (1 - u))

    # rubber word
    wx, wy, sx, sy, vis, sc = D["word"][fi]
    if vis > 0 and t < split_t:
        wsp = S["word"]
        s = ease_back(sc) * 0.95
        im = wsp.resize((max(1, int(wsp.width * sx * s)), max(1, int(wsp.height * sy * s))), Image.BILINEAR)
        tilt = 6 * math.sin(t * 9) if t < sim.T_DROP else 0
        if abs(tilt) > 0.3:
            im = im.rotate(tilt, resample=Image.BILINEAR, expand=True)
        fr.alpha_composite(im, (int(wx - im.width / 2), int(wy - im.height / 2)))
        # googly eyes on top (hyperactive pupils)
        ey = wy - im.height / 2 - 6
        for k, ex in enumerate((wx - 58 * sx * s, wx + 58 * sx * s)):
            er = 30 * s
            d.ellipse((ex - er, ey - er, ex + er, ey + er), fill=(255, 255, 255), outline=INK, width=5)
            if t < sim.T_DROP:
                jx = 12 * s * math.sin(t * 31 + k * 2.1)
                jy = 10 * s * math.cos(t * 27 + k)
            else:
                jx, jy = 0, 12 * s
            pr = 13 * s
            d.ellipse((ex + jx - pr, ey + jy - pr, ex + jx + pr, ey + jy + pr), fill=INK)
        if t < sim.T_DROP and sc >= 1:
            # speed / excitement marks
            for k in range(3):
                a = -2.4 + k * 0.5 + 0.15 * math.sin(t * 20)
                L1, L2 = 30, 60 + 10 * math.sin(t * 25 + k)
                cx, cy = wx + 330 * s, wy - 40
                d.line((cx + math.cos(a + 2.4) * L1, cy + math.sin(a + 2.4) * L1,
                        cx + math.cos(a + 2.4) * L2, cy + math.sin(a + 2.4) * L2), fill=YELLOW, width=7)

    # split flash
    if split_t <= t < split_t + 0.25:
        u = (t - split_t) / 0.25
        fl = Image.new("RGBA", (W, H), (255, 255, 255, int(90 * (1 - u) ** 2)))
        fr.alpha_composite(fl)
        bd = ImageDraw.Draw(fr)
        rr = 80 + 900 * ease_out(u)
        cy = FLOOR - sim.PIL_H0 - 60
        bd.ellipse((540 - rr, cy - rr * 0.6, 540 + rr, cy + rr * 0.6), outline=(255, 255, 255, int(255 * (1 - u))),
                   width=int(26 * (1 - u)) + 1)

    # balls
    if t >= split_t:
        bl = D["balls"][fi]
        for i in range(sim.NB):
            x, y, a, bsx, bsy, bv = bl[i]
            if bv <= 0 or y > H + 120:
                continue
            spr = S["balls"][i].rotate(a % 360, resample=Image.BILINEAR)
            if abs(bsx - 1) > 0.02 or abs(bsy - 1) > 0.02:
                spr = spr.resize((max(1, int(spr.width * bsx)), max(1, int(spr.height * bsy))), Image.BILINEAR)
            fr.alpha_composite(spr, (int(x - spr.width / 2), int(y - spr.height / 2)))

    # iron block
    bb, bvis = D["block"][fi]
    if bvis > 0:
        blk = S["block"]
        top = int(bb - blk.height + 30)
        if impact_t is None or t < impact_t:
            # speed lines while falling
            for k in range(9):
                lx = 120 + k * 105
                d.line((lx, top - 40 - (k % 3) * 60, lx, top - 260 - (k % 2) * 120), fill=(255, 255, 255, 120),
                       width=6)
        # shadow on what is below
        sh = Image.new("RGBA", (blk.width, 120), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rectangle((40, 30, blk.width - 40, 90), fill=(0, 0, 0, 160))
        fr.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20)), (int(540 - blk.width / 2), int(bb - 50)))
        fr.alpha_composite(blk, (int(540 - blk.width / 2), top))
        # dust burst at impact
        if t >= impact_t:
            u = (t - impact_t) / 0.9
            if u < 1:
                rng = np.random.default_rng(11)
                dd = ImageDraw.Draw(fr)
                for k in range(46):
                    side = -1 if k % 2 else 1
                    sp = rng.uniform(150, 700)
                    ang = rng.uniform(-0.6, 0.25)
                    x0 = 540 + side * rng.uniform(380, 470)
                    x = x0 + side * math.cos(ang) * sp * ease_out(u)
                    y = bb + math.sin(ang) * sp * ease_out(u) * 0.6 - 10 + 120 * u * u
                    rr = rng.uniform(16, 40) * (0.6 + u)
                    al = int(150 * (1 - u))
                    dd.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(190, 185, 205, al))

    # darkness after impact
    if impact_t is not None and t >= impact_t:
        u = clamp01((t - impact_t) / 1.2)
        fr.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(90 * u))))

    # ---------------- overlays (header, phase, clock)
    paste_c(fr, S["head1"], 540, 205)
    paste_c(fr, S["head2"], 540, 320)
    ph_n, ph_t0 = phase_at(t)
    pill_im, cap_im = S["phases"][ph_n]
    if ph_n == 5 and t >= impact_t + 2.4:
        pass
    else:
        u = (t - ph_t0) / 0.35 if ph_t0 > 0 else 1.0
        s = ease_back(u) if u < 1 else 1.0
        clk, red = clock_at(t)
        cpill = pill(clk, 40, (255, 70, 80) if red else (30, 26, 52), (255, 255, 255), fpath=F_MONO)
        if clk == "??:??" and int(t * 15) % 2:
            cpill = pill("¿¿:??", 40, (120, 30, 160), (255, 255, 255), fpath=F_MONO)
        gap = 18
        tw = pill_im.width + gap + cpill.width
        x0 = 540 - tw / 2
        paste_c(fr, pill_im, x0 + pill_im.width / 2, 470, s)
        paste_c(fr, cpill, x0 + pill_im.width + gap + cpill.width / 2, 470)
        paste_c(fr, cap_im, 540, 470 + 50 + cap_im.height / 2, s)
    if ph_n == 5 and t >= impact_t + 2.4:
        u = (t - impact_t - 2.4) / 0.35
        paste_c(fr, S["cta"], 540, 560, ease_back(u))
        paste_c(fr, S["cta2"], 540, 700, ease_out((t - impact_t - 2.9) / 0.3),
                ease_out((t - impact_t - 2.9) / 0.3))

    # screen shake
    sdx, sdy = D["shake"][fi]
    out = fr.convert("RGB")
    if abs(sdx) > 0.5 or abs(sdy) > 0.5:
        sh = Image.new("RGB", (W, H), (8, 6, 20))
        sh.paste(out, (int(sdx), int(sdy)))
        out = sh
    return out.tobytes()


def ImageChopsAdd(a, b):
    from PIL import ImageChops
    return ImageChops.screen(a, b)


def main():
    out = ROOT / "schlaf-5-phasen.mp4"
    audio = BUILD / "audio.wav"
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        init()
        (BUILD / "stills").mkdir(exist_ok=True)
        for a in sys.argv[2:]:
            fi = min(NF - 1, int(float(a) * FPS))
            Image.frombytes("RGB", (W, H), render_frame(fi)).save(BUILD / "stills" / f"s_{float(a):05.1f}.png")
        print("stills ->", BUILD / "stills")
        return
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-t", f"{NF / FPS:.3f}", str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=init) as pool:
        for i, buf in enumerate(pool.imap(render_frame, range(NF), chunksize=4)):
            ff.stdin.write(buf)
            if i % 150 == 0:
                print(f"frame {i}/{NF}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", out)


if __name__ == "__main__":
    main()
