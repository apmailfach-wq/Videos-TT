"""'Dein Leben ist ein Game' – motivation short for kids & teens (≈31 s, 1080x1920, 30 fps).

Flat 2D cartoon look, one big word on screen in sync with the narrator, a new picture every 2–3 s,
8-bit music with XP / level-up sounds.

  python3 tts.py                 # narration + word timings -> build/levelup/voice
  python3 render.py              # -> ../../levelup-dein-leben-ist-ein-game.mp4
  python3 render.py still 1.0 7  # preview stills -> build/levelup/
"""
import json, math, subprocess, sys, wave
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "levelup"
OUT = ROOT / "levelup-dein-leben-ist-ein-game.mp4"
W, H, FPS, S = 1080, 1920, 30, 2          # S: supersampling factor
LINES = json.loads((BUILD / "voice" / "lines.json").read_text())
GAP = [0.35, 0.3, 0.35, 0.4, 0.3, 0.45, 0.3, 0.55, 0.5, 0.0]
END_HOLD = 1.4

# ------------------------------------------------------------------ timeline
SCENES = []          # (start, dur, line)
_t = 0.0
for i, ln in enumerate(LINES):
    d = ln["words"][-1]["end"] + GAP[i] + (END_HOLD if i == len(LINES) - 1 else 0)
    SCENES.append((_t, d, i)); _t += d
DUR = _t
N = int(math.ceil(DUR * FPS))

KEYWORDS = {"game", "level", "1", "xp", "stärker", "schneller", "besser", "fehler", "up", "aufhörst", "weiter", "level-ups", "scheiterst", "nicht", "nur"}


def words_abs():
    out = []
    for (st, d, i) in SCENES:
        ws = LINES[i]["words"]
        merged = []
        for w in ws:
            t = w["text"].strip(" .,!?…:")
            if merged and t == "P" and merged[-1]["text"] == "X":
                merged[-1]["text"] = "XP"; merged[-1]["end"] = w["end"]; continue
            if t:
                merged.append({"text": t, "start": w["start"], "end": w["end"]})
        for k, w in enumerate(merged):
            nxt = merged[k + 1]["start"] if k + 1 < len(merged) else w["end"] + GAP[i] * 0.8
            out.append({"text": w["text"], "a": st + w["start"], "b": st + max(nxt, w["end"]), "scene": i})
    return out


WORDS = words_abs()
WORDS[0]["a"] = 0.0

# ------------------------------------------------------------------ helpers
def font(name, size):
    return ImageFont.truetype(str(ROOT / "fonts" / name), int(size * S))


F_BLACK = lambda s: font("Unbounded_900Black.ttf", s)
F_BOLD = lambda s: font("Unbounded_700Bold.ttf", s)
clamp = lambda x, a=0.0, b=1.0: max(a, min(b, x))
lerp = lambda a, b, k: a + (b - a) * k


def sstep(a, b, x):
    k = clamp((x - a) / (b - a)); return k * k * (3 - 2 * k)


def back(k):  # overshoot ease
    k = clamp(k); c = 1.9; return 1 + (c + 1) * (k - 1) ** 3 + c * (k - 1) ** 2


def P(*v):
    return tuple(int(round(x * S)) for x in v)


def rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def grad(top, bot):
    a = np.linspace(0, 1, H * S)[:, None, None]
    arr = (np.array(rgb(top))[None, None] * (1 - a) + np.array(rgb(bot))[None, None] * a).astype(np.uint8)
    return Image.fromarray(np.repeat(arr, W * S, axis=1), "RGB").convert("RGBA")


@lru_cache(maxsize=32)
def bg_burst(c1, c2, rot10):
    img = Image.new("RGBA", (W * S, H * S), rgb(c1) + (255,)); d = ImageDraw.Draw(img)
    cx, cy, R = W * S / 2, H * S * 0.55, H * S * 1.2
    rot = rot10 / 10.0
    for k in range(24):
        a0 = rot + k * 2 * math.pi / 24; a1 = a0 + math.pi / 24
        d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)), (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=rgb(c2) + (255,))
    v = Image.new("L", (W * S, H * S), 0); vd = ImageDraw.Draw(v)
    vd.ellipse([cx - W * S * 0.9, cy - H * S * 0.55, cx + W * S * 0.9, cy + H * S * 0.55], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(220))
    dark = Image.new("RGBA", img.size, (10, 6, 30, 255))
    return Image.composite(img, dark, v.point(lambda x: int(90 + x * 0.65)))


@lru_cache(maxsize=8)
def bg_grad(top, bot):
    return grad(top, bot)


def stars(img, t, seed, n=70, col=(255, 255, 255)):
    d = ImageDraw.Draw(img); r = np.random.default_rng(seed)
    for _ in range(n):
        x, y, s = r.uniform(0, W), r.uniform(0, H * 0.75), r.uniform(1.5, 4.5)
        a = int(140 + 115 * math.sin(t * r.uniform(1, 4) + r.uniform(0, 6)))
        d.ellipse(P(x - s, y - s, x + s, y + s), fill=col + (max(0, a),))


def rrect(d, box, r, fill, outline=None, width=0):
    d.rounded_rectangle(P(*box), radius=int(r * S), fill=fill, outline=outline, width=int(width * S))


def text_c(d, xy, txt, f, fill, stroke=0, stroke_fill=(20, 14, 40), anchor="mm"):
    d.text(P(*xy), txt, font=f, fill=fill, anchor=anchor, stroke_width=int(stroke * S), stroke_fill=stroke_fill)


def shadow_ellipse(img, cx, y, w, a=90):
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.ellipse(P(cx - w, y - w * 0.18, cx + w, y + w * 0.18), fill=(0, 0, 0, a))
    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(10 * S)))


# ------------------------------------------------------------------ the character
SKIN = (246, 200, 160)


def char_layer(pose="idle", mood="happy", hood=(47, 111, 219), hair=(52, 34, 26), t=0.0, blink=True):
    """Character on its own layer (local units, feet at bottom centre). Returns (img, feet_xy_in_px)."""
    Wl, Hl = 420, 700
    img = Image.new("RGBA", (Wl * S, Hl * S), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    cx, fy = Wl / 2, Hl - 20
    dark = tuple(int(c * 0.72) for c in hood)
    # legs + shoes
    for sx in (-1, 1):
        rrect(d, (cx + sx * 34 - 22, fy - 150, cx + sx * 34 + 22, fy - 10), 18, (34, 42, 70, 255))
        rrect(d, (cx + sx * 34 - 32 + sx * 6, fy - 26, cx + sx * 34 + 32 + sx * 6, fy + 4), 14, (245, 245, 250, 255))
    # arms (behind/in front of body depending on pose)
    def arm(side, ang, length=128):
        sx, sy = cx + side * 78, fy - 290
        ex, ey = sx + math.sin(ang) * length * side, sy + math.cos(ang) * length
        d.line(P(sx, sy, ex, ey), fill=dark + (255,), width=int(34 * S))
        d.ellipse(P(sx - 17, sy - 17, sx + 17, sy + 17), fill=dark + (255,))
        d.ellipse(P(ex - 21, ey - 21, ex + 21, ey + 21), fill=SKIN + (255,))
    wave = math.sin(t * 9) * 0.35
    angles = {"idle": (0.25, 0.25), "wave": (0.25, 2.6 + wave), "up": (2.55 + wave * 0.3, 2.55 - wave * 0.3),
              "sad": (0.08, 0.08), "point": (0.25, 1.55), "fall": (2.2, 1.6)}[pose]
    # body (hoodie)
    rrect(d, (cx - 92, fy - 320, cx + 92, fy - 130), 46, hood + (255,))
    rrect(d, (cx - 50, fy - 220, cx + 50, fy - 168), 20, dark + (255,))          # pocket
    for sx in (-1, 1):
        d.line(P(cx + sx * 16, fy - 312, cx + sx * 20, fy - 262), fill=(240, 240, 245, 255), width=int(6 * S))
    arm(-1, angles[0]); arm(1, angles[1])
    # head
    hy = fy - 420
    d.ellipse(P(cx - 92, hy - 98, cx + 92, hy + 92), fill=SKIN + (255,))
    d.ellipse(P(cx - 104, hy - 6, cx - 78, hy + 26), fill=SKIN + (255,)); d.ellipse(P(cx + 78, hy - 6, cx + 104, hy + 26), fill=SKIN + (255,))
    # hair: spiky cap
    pts = [(cx - 98, hy - 6), (cx - 104, hy - 60), (cx - 70, hy - 108), (cx - 40, hy - 92), (cx - 18, hy - 128), (cx + 12, hy - 98),
           (cx + 44, hy - 124), (cx + 66, hy - 88), (cx + 100, hy - 70), (cx + 98, hy - 10), (cx + 70, hy - 52), (cx + 20, hy - 60), (cx - 40, hy - 50), (cx - 76, hy - 30)]
    d.polygon([P(*p) for p in pts], fill=hair + (255,))
    # face
    bl = blink and (t % 3.1) < 0.12
    for sx in (-1, 1):
        ex = cx + sx * 36
        if bl:
            d.line(P(ex - 16, hy + 10, ex + 16, hy + 10), fill=(30, 24, 30, 255), width=int(5 * S))
        else:
            d.ellipse(P(ex - 20, hy - 14, ex + 20, hy + 30), fill=(255, 255, 255, 255))
            py = hy + (12 if mood != "up" else 4)
            d.ellipse(P(ex - 11, py - 11, ex + 11, py + 11), fill=(30, 24, 40, 255))
            d.ellipse(P(ex - 5, py - 9, ex + 1, py - 3), fill=(255, 255, 255, 255))
        if mood == "sad":
            d.line(P(ex - 18, hy - 30 + sx * 6, ex + 18, hy - 30 - sx * 6), fill=hair + (255,), width=int(7 * S))
        else:
            d.arc(P(ex - 20, hy - 44, ex + 20, hy - 20), 200, 340, fill=hair + (255,), width=int(7 * S))
    d.ellipse(P(cx - 70, hy + 34, cx - 44, hy + 50), fill=(255, 150, 150, 120)); d.ellipse(P(cx + 44, hy + 34, cx + 70, hy + 50), fill=(255, 150, 150, 120))
    if mood in ("happy", "up"):
        d.chord(P(cx - 34, hy + 22, cx + 34, hy + 74), 0, 180, fill=(120, 30, 40, 255))
        d.chord(P(cx - 22, hy + 50, cx + 22, hy + 74), 180, 360, fill=(240, 110, 120, 255))
    elif mood == "sad":
        d.arc(P(cx - 26, hy + 52, cx + 26, hy + 84), 200, 340, fill=(90, 40, 40, 255), width=int(7 * S))
    elif mood == "o":
        d.ellipse(P(cx - 14, hy + 40, cx + 14, hy + 72), fill=(120, 30, 40, 255))
    return img, (cx, fy)


def put_char(img, x, y, scale=1.0, rot=0.0, alpha=1.0, **kw):
    lay, (fx, fy) = char_layer(**kw)
    if scale != 1.0:
        lay = lay.resize((max(1, int(lay.width * scale)), max(1, int(lay.height * scale))), Image.LANCZOS); fx *= scale; fy *= scale
    if rot:
        # rotate around the feet
        L = max(lay.width, lay.height)
        big = Image.new("RGBA", (2 * L, 2 * L), (0, 0, 0, 0))
        big.alpha_composite(lay, (int(L - fx * S), int(L - fy * S)))
        lay = big.rotate(rot, resample=Image.BICUBIC, center=(L, L)); fx, fy = L / S, L / S
    if alpha < 1:
        lay.putalpha(lay.split()[3].point(lambda v: int(v * alpha)))
    img.alpha_composite(lay, (int(x * S - fx * S), int(y * S - fy * S)))


def badge(img, x, y, txt, scale=1.0, col=(255, 210, 63), fg=(40, 24, 10)):
    if scale <= 0.02:
        return
    d = ImageDraw.Draw(img); f = F_BOLD(34 * scale)
    w = d.textlength(txt, font=f) / S + 40 * scale; h = 62 * scale
    rrect(d, (x - w / 2, y - h / 2 + 5 * scale, x + w / 2, y + h / 2 + 5 * scale), h / 2, (0, 0, 0, 90))
    rrect(d, (x - w / 2, y - h / 2, x + w / 2, y + h / 2), h / 2, col + (255,), (255, 255, 255, 255), 4 * scale)
    text_c(d, (x, y + 1), txt, f, fg + (255,))


def xpbar(img, x, y, w, k, label="XP"):
    d = ImageDraw.Draw(img)
    rrect(d, (x - w / 2, y - 26, x + w / 2, y + 26), 26, (20, 16, 40, 230), (255, 255, 255, 255), 5)
    if k > 0.01:
        rrect(d, (x - w / 2 + 8, y - 18, x - w / 2 + 8 + (w - 16) * clamp(k), y + 18), 18, (90, 230, 120, 255))
    text_c(d, (x - w / 2 - 50, y), label, F_BOLD(34), (255, 255, 255, 255), 4)


def pop_text(img, x, y, txt, f, col, k, stroke=8):
    d = ImageDraw.Draw(img)
    text_c(d, (x, y), txt, f, col + (int(255 * k),), stroke, (20, 14, 40, int(255 * k)))


def confetti(img, t, seed, x0, y0, n=60, spread=520):
    d = ImageDraw.Draw(img); r = np.random.default_rng(seed)
    cols = [(255, 210, 63), (255, 90, 120), (90, 230, 120), (90, 170, 255), (200, 120, 255)]
    for _ in range(n):
        vx, vy = r.uniform(-1, 1) * spread, -r.uniform(500, 1100)
        x = x0 + vx * t; y = y0 + vy * t + 900 * t * t
        a = r.uniform(0, 6) + t * r.uniform(4, 10); s = r.uniform(10, 18)
        c = cols[r.integers(0, len(cols))]
        pts = [(x + math.cos(a + q) * s, y + math.sin(a + q) * s * 0.5) for q in (0, 1.6, 3.14, 4.7)]
        d.polygon([P(*p) for p in pts], fill=c + (255,))


def gamepad(d, x, y, s=1.0, col=(60, 60, 80)):
    rrect(d, (x - 170 * s, y - 70 * s, x + 170 * s, y + 70 * s), 70 * s, col + (255,), (255, 255, 255, 255), 5 * s)
    for (ox, oy) in [(-100, 0)]:
        rrect(d, (x + (ox - 36) * s, y - 12 * s, x + (ox + 36) * s, y + 12 * s), 6 * s, (230, 230, 240, 255))
        rrect(d, (x + (ox - 12) * s, y - 36 * s, x + (ox + 12) * s, y + 36 * s), 6 * s, (230, 230, 240, 255))
    for (ox, oy, c) in [(90, -24, (255, 90, 120)), (130, 8, (90, 230, 120)), (50, 8, (90, 170, 255)), (90, 40, (255, 210, 63))]:
        d.ellipse(P(x + (ox - 16) * s, y + (oy - 16) * s, x + (ox + 16) * s, y + (oy + 16) * s), fill=c + (255,))


# ------------------------------------------------------------------ scenes (τ = time in scene, D = scene length)
def ground(img, col, y=1500):
    d = ImageDraw.Draw(img)
    d.ellipse(P(-300, y - 60, W + 300, y + 900), fill=rgb(col) + (255,))


def sc0(img, τ, D, t):   # hook: life as a game – a game screen with PRESS START, you pop in
    img.alpha_composite(bg_burst("#3a0f6b", "#5a1a9a", int(t * 2) % 63))
    stars(img, t, 1)
    k = back((τ + 0.12) / 0.4)
    cx, cy = 540, 1060
    w, h = 820 * k, 700 * k
    if k < 0.05:
        return
    d = ImageDraw.Draw(img)
    rrect(d, (cx - w / 2 - 30, cy - h / 2 - 30, cx + w / 2 + 30, cy + h / 2 + 30), 64, (30, 22, 60, 255), (255, 255, 255, 255), 7)
    # screen content on its own layer, clipped to rounded corners
    sw, sh = int(w * S), int(h * S)
    scr = bg_grad("#1b6fd6", "#7fdcff").resize((sw, sh))
    sd = ImageDraw.Draw(scr)
    sd.ellipse((-sw * 0.2, sh * 0.72, sw * 1.2, sh * 1.9), fill=(90, 200, 110, 255))
    sub = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    sub.alpha_composite(scr, P(cx - w / 2, cy - h / 2))
    if τ > 0.3:
        put_char(sub, cx, cy + h / 2 - 0.13 * h, 0.62 * k * back((τ - 0.3) / 0.35), t=t, pose="wave", mood="happy")
    m = Image.new("L", (W * S, H * S), 0)
    ImageDraw.Draw(m).rounded_rectangle(P(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=int(40 * S), fill=255)
    sub.putalpha(Image.composite(sub.split()[3], Image.new("L", sub.size, 0), m))
    img.alpha_composite(sub)
    d = ImageDraw.Draw(img)
    text_c(d, (cx - w / 2 + 110, cy - h / 2 + 52), "LVL 1", F_BOLD(32 * k), (255, 255, 255, 255), 4)
    for i in range(3):
        hx = cx + w / 2 - 60 - i * 56; hy = cy - h / 2 + 52
        d.polygon([P(hx, hy + 18), P(hx - 22, hy - 4), P(hx - 12, hy - 18), P(hx, hy - 8), P(hx + 12, hy - 18), P(hx + 22, hy - 4)], fill=(255, 80, 110, 255))
    if (t * 2.2) % 1 < 0.62 and τ > 0.5:
        pop_text(img, cx, cy + h / 2 + 90, "PRESS START", F_BLACK(54), (255, 210, 63), 1, 8)


def sc1(img, τ, D, t):   # you are level 1
    img.alpha_composite(bg_grad("#2b1a6e", "#e55d87"))
    stars(img, t, 2, 40)
    ground(img, "#3b2a7a", 1420)
    shadow_ellipse(img, 540, 1440, 120)
    put_char(img, 540, 1440, 1.0, t=t, pose="idle", mood="happy")
    badge(img, 540, 860, "LVL 1", 1.4 * back((τ - 0.5) / 0.35))
    xpbar(img, 590, 1610, 640, 0.03)


RIVALS = [((222, 64, 64), "LVL 37"), ((40, 170, 110), "LVL 64"), ((140, 70, 210), "LVL 99")]


def sc2(img, τ, D, t):   # the others look stronger, faster, better
    img.alpha_composite(bg_burst("#14234f", "#1c3170", int(t * 3) % 63))
    ground(img, "#22305f", 1460)
    shadow_ellipse(img, 170, 1480, 70)
    put_char(img, 170, 1480, 0.55, t=t, pose="idle", mood="o")
    badge(img, 170, 1100, "LVL 1", 0.9)
    trig = [w["a"] - SCENES[2][0] for w in WORDS if w["scene"] == 2 and w["text"].lower() in ("stärker", "schneller", "besser")]
    trig = (trig + [0.8, 1.6, 2.4])[:3]
    for k, ((col, lvl), tr, x) in enumerate(zip(RIVALS, trig, (430, 680, 920))):
        e = back((τ - tr + 0.15) / 0.35)
        if e <= 0.01:
            continue
        sc = 0.9 + 0.12 * k
        shadow_ellipse(img, x, 1490, 100 * sc)
        put_char(img, x, 1490 + (1 - e) * 600, sc, t=t + k, pose="point" if k == 1 else "up" if k == 2 else "idle", mood="happy", hood=col, hair=(30, 22, 20))
        badge(img, x, 1490 - 700 * sc - 30, lvl, e)
        if k == 1:  # speed lines for "schneller"
            d = ImageDraw.Draw(img)
            for j in range(5):
                yy = 1060 + j * 70; d.line(P(x + 120, yy, x + 260, yy), fill=(255, 255, 255, int(170 * e)), width=int(7 * S))


def sc3(img, τ, D, t):   # ...but they started at level 1 too (flashback: they shrink)
    img.alpha_composite(bg_grad("#ffb36b", "#f05a7e"))
    ground(img, "#d0486e", 1470)
    k = sstep(0.4, 1.4, τ)
    for (col, lvl), x in zip(RIVALS, (240, 540, 840)):
        sc = 1.0 - 0.5 * k
        shadow_ellipse(img, x, 1490, 100 * sc)
        put_char(img, x, 1490, sc, t=t + x, pose="idle", mood="happy", hood=col, hair=(30, 22, 20))
        badge(img, x, 1490 - 700 * sc - 30, lvl if k < 0.5 else "LVL 1", 1.0, col=(255, 255, 255) if k >= 0.5 else (255, 210, 63))
    # rewind icon
    d = ImageDraw.Draw(img); a = int(255 * (1 - sstep(1.2, 1.8, τ)))
    for ox in (-40, 40):
        d.polygon([P(540 + ox + 40, 900), P(540 + ox - 40, 950), P(540 + ox + 40, 1000)], fill=(255, 255, 255, a))


def sc4(img, τ, D, t):   # every mistake gives you XP – you trip and fall
    img.alpha_composite(bg_grad("#0f3d5c", "#28a7a0"))
    ground(img, "#1d6b6a", 1440)
    fall = sstep(0.25, 0.75, τ)
    d = ImageDraw.Draw(img)
    rrect(d, (470, 1420, 580, 1470), 18, (120, 90, 70, 255))           # the stone you trip over
    shadow_ellipse(img, 700, 1450, 130)
    put_char(img, 700, 1450, 1.0, rot=82 * fall, t=t, pose="fall" if fall > 0.2 else "idle", mood="o" if fall > 0.2 else "happy")
    gains = [(1.0, "+10 XP"), (1.5, "+25 XP"), (2.0, "+50 XP")]
    xp = 0.03
    for k, (tt, txt) in enumerate(gains):
        if τ > tt:
            u = τ - tt; xp += 0.2 * sstep(0, 0.3, u)
            pop_text(img, 360 + k * 190, 1100 - u * 160, txt, F_BLACK(54), (255, 210, 63), 1 - sstep(0.7, 1.2, u))
    xpbar(img, 590, 1610, 640, xp)


def sc5(img, τ, D, t):   # get up again: LEVEL UP!
    trig = next((w["a"] - SCENES[5][0] for w in WORDS if w["scene"] == 5 and w["text"].lower() == "level"), 2.6)
    lu = τ - trig
    if lu > 0:
        img.alpha_composite(bg_burst("#ff9a1f", "#ffd23f", int(t * 6) % 63))
    else:
        img.alpha_composite(bg_grad("#0f3d5c", "#28a7a0")); ground(img, "#1d6b6a", 1440)
    up = sstep(0.4, 1.5, τ)
    cxp = lerp(700, 540, up)
    shadow_ellipse(img, cxp, 1450, 130)
    put_char(img, cxp, 1450 - (abs(math.sin(lu * 8)) * 60 if lu > 0 else 0), 1.0, rot=82 * (1 - up), t=t,
             pose="up" if lu > 0 else ("idle" if up > 0.6 else "fall"), mood="up" if lu > 0 else "happy")
    xpbar(img, 590, 1610, 640, 0.63 + 0.37 * sstep(0, 0.3, lu) if lu < 0.5 else sstep(0.5, 1.2, lu) * 0.2)
    if lu > 0:
        confetti(img, lu, 5, 540, 1000)
        e = back(lu / 0.35)
        pop_text(img, 540, 470, "LEVEL UP!", F_BLACK(118 * e), (255, 255, 255), 1, 12)
        badge(img, 560, 1450 - 760, "LVL 2", 1.3 * back((lu - 0.2) / 0.3), col=(90, 230, 120))


def sc6(img, τ, D, t):   # you don't lose when you fail: GAME OVER gets crossed out -> NOCH MAL!
    img.alpha_composite(bg_grad("#0a0a14", "#2a0a1a"))
    d = ImageDraw.Draw(img)
    g = 8 * math.sin(t * 40) if τ < 0.9 else 0
    for off, col in ((-g, (0, 255, 255, 160)), (g, (255, 0, 80, 160)), (0, (255, 60, 80, 255))):
        text_c(d, (540 + off, 1000), "GAME", F_BLACK(150), col)
        text_c(d, (540 - off, 1170), "OVER", F_BLACK(150), col)
    k = sstep(0.9, 1.25, τ)
    if k > 0:
        d.line(P(140, 1220, 140 + 800 * k, 940 - 0 * k), fill=(90, 230, 120, 255), width=int(34 * S))
    if τ > 1.35:
        e = back((τ - 1.35) / 0.35)
        pop_text(img, 540, 1400, "NOCH MAL!", F_BLACK(96 * e), (90, 230, 120), 1, 10)


def sc7(img, τ, D, t):   # you only lose when you stop playing: the controller drops, the screen goes grey
    grey = sstep(1.2, 2.4, τ)
    img.alpha_composite(bg_grad("#1d1b3a", "#3a3566"))
    d = ImageDraw.Draw(img)
    y = 1050 + 520 * sstep(0.3, 1.0, τ) ** 2
    rot = 25 * sstep(0.3, 1.0, τ)
    lay = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0)); gamepad(ImageDraw.Draw(lay), 540, y, 1.3)
    img.alpha_composite(lay.rotate(rot, center=P(540, y), resample=Image.BICUBIC))
    if grey > 0:
        g = img.convert("L").convert("RGBA")
        img.alpha_composite(Image.blend(img, g, grey))
        d = ImageDraw.Draw(img)
        text_c(d, (540, 950), "GAME OVER", F_BLACK(110), (200, 200, 210, int(255 * grey)))


def sc8(img, τ, D, t):   # so press... CONTINUE
    trig = next((w["a"] - SCENES[8][0] for w in WORDS if w["scene"] == 8 and w["text"].lower() == "weiter"), 2.0)
    pr = τ - trig
    img.alpha_composite(bg_burst("#14234f", "#1c3170", 3) if pr < 0 else bg_burst("#13a85b", "#2fd47a", int(t * 6) % 63))
    d = ImageDraw.Draw(img)
    rrect(d, (170, 640, 910, 1460), 50, (20, 16, 40, 235), (255, 255, 255, 255), 6)
    text_c(d, (540, 760), "PAUSE", F_BLACK(84), (255, 255, 255, 255))
    rrect(d, (240, 880, 840, 1030), 40, (90, 90, 110, 255))
    text_c(d, (540, 955), "AUFGEBEN", F_BOLD(54), (200, 200, 210, 255))
    press = 1 - 0.08 * math.exp(-max(pr, 0) * 12) if pr > 0 else 1
    glow = 0.5 + 0.5 * math.sin(t * 6)
    bw = 300 * press
    rrect(d, (540 - bw, 1110, 540 + bw, 1300), 50, (90, 230, 120, 255) if pr < 0 else (255, 210, 63, 255), (255, 255, 255, int(150 + 105 * glow)), 7)
    text_c(d, (540, 1205), "WEITER ▶", F_BLACK(66), (20, 40, 20, 255))
    # finger/cursor moving to the button
    k = sstep(0.4, max(0.5, trig - 0.1), τ)
    fx, fy = 900 - 300 * k, 1600 - 330 * k
    d.polygon([P(fx, fy), P(fx + 26, fy + 80), P(fx + 44, fy + 52), P(fx + 80, fy + 92), P(fx + 98, fy + 76), P(fx + 62, fy + 36), P(fx + 96, fy + 22)], fill=(255, 255, 255, 255), outline=(20, 14, 40, 255), width=int(5 * S))
    if pr > 0:
        confetti(img, pr, 8, 540, 1200, 80, 650)


def sc9(img, τ, D, t):   # outro: follow
    img.alpha_composite(bg_burst("#3a0f6b", "#5a1a9a", int(t * 2) % 63))
    stars(img, t, 9)
    shadow_ellipse(img, 540, 1500, 120)
    put_char(img, 540, 1500, 1.0, t=t, pose="wave", mood="happy")
    d = ImageDraw.Draw(img)
    p = 1 + 0.05 * math.sin(t * 7)
    rrect(d, (540 - 250 * p, 1610 - 70 * p, 540 + 250 * p, 1610 + 70 * p), 70 * p, (255, 44, 85, 255), (255, 255, 255, 255), 6)
    text_c(d, (540, 1612), "+ FOLGEN", F_BLACK(56 * p), (255, 255, 255, 255))


SCENE_FNS = [sc0, sc1, sc2, sc3, sc4, sc5, sc6, sc7, sc8, sc9]


# ------------------------------------------------------------------ big synced word
def caption(img, t):
    cur = [w for w in WORDS if w["a"] <= t < w["b"]]
    if not cur:
        return
    w = cur[-1]; txt = w["text"].upper()
    if w["scene"] == 5 and w["text"].lower() in ("level", "up"):
        return                     # the big LEVEL UP! takes this spot
    k = back((t - w["a"]) / 0.14)
    key = w["text"].lower() in KEYWORDS
    size = 150 if len(txt) <= 6 else 128 if len(txt) <= 9 else 104
    d = ImageDraw.Draw(img)
    f = F_BLACK(size * (0.75 + 0.25 * k))
    col = (255, 210, 63, 255) if key else (255, 255, 255, 255)
    y = 470
    text_c(d, (540 + 6, y + 10), txt, f, (0, 0, 0, 120), 12, (0, 0, 0, 120))
    text_c(d, (540, y), txt, f, col, 12, (20, 14, 40, 255))


def render_frame(i):
    t = i / FPS
    for (st, d, k) in SCENES:
        if st <= t < st + d or k == len(SCENES) - 1:
            sc = k; τ = t - st; D = d
            if st <= t < st + d:
                break
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 255))
    SCENE_FNS[sc](img, τ, D, t)
    # punch-in on every cut
    z = 1 + 0.06 * math.exp(-τ * 9)
    if z > 1.002:
        cw, ch = int(W * S / z), int(H * S / z)
        img = img.crop(((W * S - cw) // 2, (H * S - ch) // 2, (W * S - cw) // 2 + cw, (H * S - ch) // 2 + ch)).resize((W * S, H * S), Image.BICUBIC)
    caption(img, t)
    flash = math.exp(-τ * 18) * 0.5
    if flash > 0.02 and sc > 0:
        img.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, int(255 * flash))))
    return img.convert("RGB").resize((W, H), Image.LANCZOS)


# ------------------------------------------------------------------ sound: chiptune + sfx + voice
def audio():
    SR = 48000; n = int(DUR * SR) + SR; t = np.arange(n) / SR
    out = np.zeros(n)

    def place(x, at, g=1.0):
        i = int(at * SR); j = min(n, i + len(x))
        if i < n:
            out[i:j] += x[: j - i] * g

    def sq(f, d, duty=0.5, dec=6.0):
        m = int(d * SR); tt = np.arange(m) / SR
        w = np.where((tt * f) % 1 < duty, 1.0, -1.0) * np.exp(-tt * dec)
        w[: 80] *= np.linspace(0, 1, 80); return w

    def noise(d, dec):
        m = int(d * SR); return np.random.default_rng(int(d * 1e4)).uniform(-1, 1, m) * np.exp(-np.arange(m) / SR * dec)

    bpm = 124; beat = 60 / bpm; s16 = beat / 4
    prog = [(261.63, [0, 4, 7, 12]), (196.0, [0, 4, 7, 11]), (220.0, [0, 3, 7, 12]), (174.61, [0, 4, 7, 12])]
    go_a, go_b = SCENES[6][0], SCENES[8][0] + next((w["a"] - SCENES[8][0] for w in WORDS if w["scene"] == 8 and w["text"].lower() == "weiter"), 2.0)
    music = np.zeros(n)
    tt = 0.0; step = 0
    while tt < DUR:
        bar = int(tt / (beat * 4)) % 4; root, iv = prog[bar]
        silent = go_a - 0.05 <= tt < go_b - 0.02
        if not silent:
            f = root * 2 ** (iv[step % 4] / 12) * 2
            i = int(tt * SR); w = sq(f, s16 * 0.95, 0.25, 14) * 0.18; music[i:i + len(w)] += w[: n - i]
            if step % 2 == 0:
                w = sq(root / 2, s16 * 1.9, 0.5, 5) * 0.22; music[i:i + len(w)] += w[: n - i]
            if step % 4 == 0:
                m = int(0.18 * SR); k = np.sin(2 * np.pi * np.cumsum(np.linspace(150, 45, m)) / SR) * np.exp(-np.arange(m) / SR * 18) * 0.6; music[i:i + m] += k[: n - i]
            if step % 8 == 4:
                w = noise(0.12, 30) * 0.25; music[i:i + len(w)] += w[: n - i]
            if step % 2 == 1:
                w = noise(0.03, 120) * 0.08; music[i:i + len(w)] += w[: n - i]
        tt += s16; step += 1
    out += music * 0.55
    # sfx
    for (st, d, k) in SCENES[1:]:
        m = int(0.25 * SR); sw = np.random.default_rng(k).uniform(-1, 1, m) * np.sin(np.linspace(0, np.pi, m)) ** 2
        place(np.convolve(sw, np.ones(30) / 30, mode="same") * 0.25, st - 0.12)
    for tt0 in (1.0, 1.5, 2.0):   # XP coins
        a = SCENES[4][0] + tt0
        place(np.concatenate([sq(988, 0.07, 0.5, 10), sq(1319, 0.18, 0.5, 12)]) * 0.18, a)
    lv = SCENES[5][0] + next((w["a"] - SCENES[5][0] for w in WORDS if w["scene"] == 5 and w["text"].lower() == "level"), 2.6)
    for k, f in enumerate([523.3, 659.3, 784.0, 1046.5, 1318.5]):
        place(sq(f, 0.16, 0.5, 6) * 0.2, lv + k * 0.07)
    for k, f in enumerate([392, 370, 349, 262]):      # game over
        place(sq(f, 0.32 if k < 3 else 0.7, 0.5, 3) * 0.2, SCENES[6][0] + 0.05 + k * 0.28)
    place(np.concatenate([sq(1568, 0.05, 0.5, 30)]) * 0.3, go_b)          # click
    for k, f in enumerate([523.3, 784.0, 1046.5]):
        place(sq(f, 0.22, 0.5, 5) * 0.2, go_b + 0.05 + k * 0.08)
    # voice
    voice = np.zeros(n)
    for (st, d, k) in SCENES:
        with wave.open(LINES[k]["file"]) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float) / 32767
        i = int(st * SR); j = min(n, i + len(x)); voice[i:j] += x[: j - i]
    voice /= np.max(np.abs(voice)) + 1e-9
    act = np.convolve((np.abs(voice) > 0.02).astype(float), np.ones(SR // 5) / (SR // 5), mode="same")
    mix = out * (1 - 0.5 * np.clip(act * 4, 0, 1)) + voice * 0.95
    mix = mix[: int(DUR * SR)]; mix = mix / np.max(np.abs(mix)) * 0.95
    p = BUILD / "audio.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype("<i2").tobytes())
    return p


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:2] == ["still"]:
        for s in sys.argv[2:]:
            render_frame(int(float(s) * FPS)).save(BUILD / f"still_{s}.jpg", quality=90)
        return
    a = audio()
    print(f"{DUR:.2f} s, {N} frames")
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-i", str(a), "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                            "-af", "loudnorm=I=-14:TP=-1.5:LRA=9", "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", "192k", "-shortest", str(OUT)], stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for k, im in enumerate(pool.imap(render_frame, range(N), chunksize=4)):
            enc.stdin.write(im.tobytes())
            if k % 150 == 0:
                print("frame", k)
    enc.stdin.close(); enc.wait()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
