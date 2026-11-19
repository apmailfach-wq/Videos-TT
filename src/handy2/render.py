"""Render handy-redet-mit-dir.mp4 – 'Dein Handy redet mit dir' (1080x1920, 30 fps).

Own look: neo-brutalist sticker style. Flat colour backgrounds with a halftone dot
grid, every illustration gets a thick black outline plus a hard offset shadow
(computed from the layer's alpha), the clingy phone talks in chat bubbles, the
narrator answers with tilted slam-caption stickers. Quirky beat with record-stop
gags on the punchlines.

    python3 tts.py && python3 render.py
    python3 render.py preview 2 10 30    # stills -> build/handy2/stills
"""
import json
import math
import random
import subprocess
import sys
import wave
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gfx import (W, H, FPS, S, F_HEAD, F_BODY, F_BLACK, F_EMOJI, F_HAND, SKIN, HOOD, INK, WHITE,  # noqa: E402
                 C, c01, ease_out, ease_back, lerp, font, kid, feed, dumbbell, book, bricks, clock)
from script import LINES  # noqa: E402

ROOT = HERE.parent.parent
BUILD = ROOT / "build" / "handy2"
OUT = ROOT / "handy-redet-mit-dir.mp4"

BLACK = (12, 12, 16)
ACID = (236, 255, 70)
PINK = (255, 112, 190)
CYAN = (90, 220, 255)
LIME = (120, 240, 140)
ORANGE = (255, 150, 60)
RED = (255, 70, 70)
VIOLET = (160, 120, 255)
NIGHT = (24, 22, 54)
PHONE_BODY = (40, 40, 52)
PHONE_SCREEN = (120, 225, 255)

# ------------------------------------------------------------------ timeline
TIM = json.loads((BUILD / "timings.json").read_text())
KEYS = [l[0] for l in LINES]
WHO = [l[1] for l in LINES]
GAP = {"akku": 0.55, "count": 0.25, "night": 0.5, "dreams": 0.55, "update": 0.3, "cta": 1.4}
CLIP, OFF, DUR = [], [], []
_t = 0.0
for k, tm in zip(KEYS, TIM):
    a = max(0.0, tm["words"][0]["start"] - 0.06)
    b = min(tm["duration"], tm["words"][-1]["end"] + 0.14)
    CLIP.append((a, b))
    OFF.append(_t)
    d = (b - a) + GAP.get(k, 0.16)
    DUR.append(d)
    _t += d
TOTAL = _t
NFRAMES = int(math.ceil(TOTAL * FPS))


def s0(k):
    return OFF[KEYS.index(k)]


def _tokens(i):
    toks = LINES[i][2].split()
    ws = TIM[i]["words"]
    if len(toks) == len(ws):
        return toks
    out, j = [], 0                      # greedy re-alignment by stripped prefix
    norm = lambda x: "".join(ch for ch in x.lower() if ch.isalnum())
    for w in ws:
        if j < len(toks) and norm(toks[j]).startswith(norm(w["text"])[:3]):
            out.append(toks[j]); j += 1
        else:
            out.append(w["text"])
    return out


def words_of(i):
    a = CLIP[i][0]
    return [(OFF[i] + w["start"] - a, OFF[i] + w["end"] - a, tk)
            for w, tk in zip(TIM[i]["words"], _tokens(i))]


def at(k, word, occ=0, lead=0.04):
    n = 0
    for st, en, w in words_of(KEYS.index(k)):
        if w.strip(".,!?:").lower().startswith(word.lower()):
            if n == occ:
                return st - lead - s0(k)
            n += 1
    raise KeyError((k, word))


# ------------------------------------------------------------------ backgrounds
BG = {"hook": BLACK, "stats": CYAN, "akku": ACID, "please": PINK, "count": ORANGE, "night": NIGHT,
      "offline": CYAN, "plan": LIME, "panic": RED, "dreams": VIOLET, "sad": PINK, "update": LIME,
      "cta": ACID}


@lru_cache(maxsize=16)
def bg_img(col):
    im = Image.new("RGB", (W, H), col)
    d = ImageDraw.Draw(im)
    dot = tuple(max(0, v - 28) for v in col) if sum(col) > 200 else tuple(min(255, v + 22) for v in col)
    for y in range(0, H + 40, 40):
        for x in range(0 + (20 if (y // 40) % 2 else 0), W + 40, 40):
            d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=dot)
    return im


# ------------------------------------------------------------------ sticker compositing
OFFS = [(int(round(r * math.cos(a))), int(round(r * math.sin(a))))
        for r in (3, 6) for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)]


def dilate(a):
    out = a.copy()
    h, w = a.shape
    for dx, dy in OFFS:
        sh = np.zeros_like(a)
        ys, yd = (slice(dy, h), slice(0, h - dy)) if dy >= 0 else (slice(0, h + dy), slice(-dy, h))
        xs, xd = (slice(dx, w), slice(0, w - dx)) if dx >= 0 else (slice(0, w + dx), slice(-dx, w))
        sh[ys, xs] = a[yd, xd]
        np.maximum(out, sh, out=out)
    return out


def sticker(frame, layer, shadow=(16, 16)):
    """Composite RGBA layer onto frame with black outline + hard drop shadow."""
    a = np.asarray(layer.split()[3])
    d = dilate(a)
    outl = Image.new("RGBA", (W, H), BLACK + (255,))
    outl.putalpha(Image.fromarray(d))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow_img = Image.new("RGBA", (W, H), (0, 0, 0, 110))
    shadow_img.putalpha(Image.fromarray((d.astype(np.uint16) * 110 // 255).astype(np.uint8)))
    sh.paste(shadow_img, shadow)
    frame.alpha_composite(sh)
    frame.alpha_composite(outl)
    frame.alpha_composite(layer)


def new_layer():
    im = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    return im, C(im)


def finish(im):
    return im.resize((W, H), Image.LANCZOS)


@lru_cache(maxsize=32)
def emoji(ch, size):
    f = font(F_EMOJI, 109)
    im = Image.new("RGBA", (140, 140), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((70, 70), ch, font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox())
    k = size / max(im.size)
    return im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)


def put_emoji(frame, ch, x, y, size, rot=0):
    if size < 6:
        return
    e = emoji(ch, int(size))
    if rot:
        e = e.rotate(rot, resample=Image.BICUBIC, expand=True)
    frame.alpha_composite(e, (int(x - e.width / 2), int(y - e.height / 2)))


# ------------------------------------------------------------------ the phone character
def handy(c, x, y, s=1.0, mood="happy", t=0.0, la=30, ra=-30, lel=0, rel=0, shake=0.0, screen=None,
          tear=0.0, legs=True):
    """Talking phone. (x, y) = centre of the body."""
    x += math.sin(t * 60) * shake * 10
    w, h = 300 * s, 520 * s
    # legs
    if legs:
        for sx in (-1, 1):
            c.line([(x + sx * 60 * s, y + h / 2 - 10), (x + sx * 70 * s, y + h / 2 + 90 * s)], BLACK, 16 * s)
            c.ellipse(x + sx * 80 * s, y + h / 2 + 96 * s, 34 * s, 16 * s, BLACK)
    # arms
    hands = []
    for sx, ang, el in ((-1, la, lel), (1, ra, rel)):
        px, py = x + sx * w / 2, y + 20 * s
        a = math.radians(ang)
        ex, ey = px + sx * math.sin(a) * 90 * s, py + math.cos(a) * 90 * s
        a2 = a + math.radians(el)
        hx, hy = ex + sx * math.sin(a2) * 80 * s, ey + math.cos(a2) * 80 * s
        c.line([(px, py), (ex, ey), (hx, hy)], BLACK, 16 * s)
        c.circle(hx, hy, 26 * s, WHITE)
        hands.append((hx, hy))
    # body
    c.rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, PHONE_BODY, r=50 * s)
    scol = screen or {"panic": (255, 120, 120), "sad": (150, 170, 230)}.get(mood, PHONE_SCREEN)
    c.rect(x - w / 2 + 18 * s, y - h / 2 + 18 * s, x + w / 2 - 18 * s, y + h / 2 - 18 * s, scol, r=36 * s)
    c.rect(x - 50 * s, y - h / 2 + 30 * s, x + 50 * s, y - h / 2 + 52 * s, PHONE_BODY, r=11 * s)
    # status bar
    c.rect(x + 70 * s, y - h / 2 + 34 * s, x + 110 * s, y - h / 2 + 50 * s, (60, 200, 90), r=4 * s)
    # googly eyes
    ey0 = y - 60 * s
    for sx in (-1, 1):
        ex = x + sx * 66 * s
        er = 56 * s if mood in ("please", "panic") else 48 * s
        c.circle(ex, ey0, er, WHITE)
        jig = math.sin(t * 7 + sx) * 6 * s
        pr = {"please": 30, "panic": 14, "sad": 24}.get(mood, 22) * s
        px, py = ex + jig, ey0 + (10 * s if mood == "sad" else 4 * s) + math.cos(t * 5) * 4 * s
        c.circle(px, py, pr, BLACK)
        if mood in ("please", "sad"):
            c.circle(px - pr * 0.35, py - pr * 0.4, pr * 0.32, WHITE)
            c.circle(px + pr * 0.3, py + pr * 0.25, pr * 0.15, WHITE)
        # brows
        by = ey0 - er - 16 * s
        if mood in ("please", "sad"):
            c.line([(ex - sx * 40 * s, by - 18 * s), (ex + sx * 30 * s, by + 4 * s)], BLACK, 10 * s)
        elif mood == "panic":
            c.line([(ex - 36 * s, by - 14 * s), (ex + 36 * s, by - 14 * s)], BLACK, 10 * s)
        elif mood == "sly":
            c.line([(ex - sx * 36 * s, by + 8 * s), (ex + sx * 36 * s, by - 6 * s)], BLACK, 10 * s)
        else:
            c.arc(ex, by + 30 * s, 40 * s, 230, 310, BLACK, 10 * s)
    # mouth
    my = y + 70 * s
    talk = abs(math.sin(t * 18))
    if mood == "panic":
        c.ellipse(x, my + 10 * s, 50 * s, (40 + 30 * talk) * s, BLACK)
        c.ellipse(x, my + 30 * s + 20 * talk * s, 30 * s, 14 * s, (255, 100, 120))
    elif mood == "sad":
        c.arc(x, my + 50 * s, 46 * s, 210, 330, BLACK, 10 * s)
    elif mood == "please":
        c.ellipse(x, my, 22 * s, (10 + 12 * talk) * s, BLACK)
    else:
        c.d.chord([(x - 70 * s) * S, (my - 40 * s) * S, (x + 70 * s) * S, (my + (40 + 16 * talk) * s) * S],
                  0, 180, fill=BLACK)
        c.ellipse(x, my + (24 + 6 * talk) * s, 30 * s, 10 * s, (255, 100, 120))
    # blush
    for sx in (-1, 1):
        c.ellipse(x + sx * 100 * s, y + 40 * s, 22 * s, 12 * s, (255, 140, 170))
    # tears / sweat
    if mood == "panic":
        for k, (dx, ph) in enumerate(((-140, 0), (150, 0.4), (-120, 0.7))):
            yy = y - 160 * s + ((t * 1.6 + ph) % 1) * 160 * s
            c.ellipse(x + dx * s, yy, 14 * s, 20 * s, (120, 210, 255))
    if tear > 0:
        for sx in (-1, 1):
            yy = ey0 + 50 * s + ((t * 1.2 + (sx + 1) * 0.3) % 1) * 140 * s * tear
            c.ellipse(x + sx * 66 * s, yy, 12 * s, 18 * s, (120, 210, 255))
    return hands


# ------------------------------------------------------------------ captions
def wrap(words, f, maxw):
    lines, cur = [], []
    for i, w in enumerate(words):
        test = " ".join(x for _, x in cur + [(i, w)])
        if cur and f.getlength(test) > maxw:
            lines.append(cur)
            cur = []
        cur.append((i, w))
    if cur:
        lines.append(cur)
    return lines


@lru_cache(maxsize=64)
def bubble_layout(i):
    f = font(F_BLACK, 58)
    ws = [w for _, _, w in words_of(i)]
    lines = wrap(ws, f, 760)
    return f, lines


def draw_bubble(frame, i, t):
    """Chat bubble from 'Dein Handy' – words appear as they are spoken."""
    lt = t - OFF[i]
    f, lines = bubble_layout(i)
    wt = words_of(i)
    lh = 74
    bw = max(f.getlength(" ".join(w for _, w in ln)) for ln in lines) + 80
    bh = lh * len(lines) + 56
    x0, y0 = 70, 300
    p = ease_back(lt / 0.3)
    if p <= 0:
        return
    im = Image.new("RGBA", (int(bw) + 60, int(bh) + 150), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # name tag
    nw = font(F_HEAD, 28).getlength("DEIN HANDY")
    d.rounded_rectangle([6, 0, 26 + nw + 100, 54], 27, fill=BLACK)
    d.text((26, 27), "DEIN HANDY", font=font(F_HEAD, 28), fill=PINK, anchor="lm")
    d.text((26 + nw + 16, 27), "· jetzt", font=font(F_BODY, 26), fill=(190, 190, 200), anchor="lm")
    by = 70
    d.rounded_rectangle([14, by + 10, 14 + bw, by + 10 + bh], 44, fill=BLACK)       # hard shadow
    d.rounded_rectangle([0, by, bw, by + bh], 44, fill=WHITE, outline=BLACK, width=6)
    d.polygon([(30, by + bh - 6), (8, by + bh + 46), (90, by + bh - 6)], fill=WHITE)
    d.line([(30, by + bh - 3), (8, by + bh + 46), (90, by + bh - 3)], fill=BLACK, width=6)
    for li, ln in enumerate(lines):
        x = 40
        for wi, w in ln:
            st = wt[wi][0]
            col = BLACK if t >= st else (215, 215, 222)
            if t >= st and t < wt[wi][1] + 0.1:
                col = (230, 40, 130)
            d.text((x, by + 28 + li * lh), w, font=f, fill=col, anchor="la")
            x += f.getlength(w + " ")
    if p != 1:
        im = im.resize((max(1, int(im.width * p)), max(1, int(im.height * p))), Image.BILINEAR)
    frame.alpha_composite(im, (x0, y0 - 70))


def chunks_of(i):
    """Group narrator words into 1–3 word punch chunks."""
    ws = words_of(i)
    out, cur = [], []
    for st, en, w in ws:
        if cur and len(" ".join(x for _, _, x in cur + [(0, 0, w)])) > 14:
            out.append(cur)
            cur = []
        cur.append((st, en, w))
        if w[-1] in ".,!?:" or len(cur) == 3:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


@lru_cache(maxsize=256)
def slam_img(text, hi_idx, rot):
    f = font(F_HEAD, 96)
    words = text.split(" ")
    size = 96
    while f.getlength(text) > 820 and size > 40:
        size -= 6
        f = font(F_HEAD, size)
    tw = f.getlength(text)
    pad = 34
    bw, bh = int(tw + pad * 2), int(size * 1.25 + pad * 1.4)
    im = Image.new("RGBA", (bw + 20, bh + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([14, 14, bw + 14, bh + 14], fill=BLACK)
    d.rectangle([0, 0, bw, bh], fill=WHITE, outline=BLACK, width=7)
    x = pad
    for k, w in enumerate(words):
        col = (230, 40, 130) if k == hi_idx else BLACK
        d.text((x, bh / 2 + 4), w, font=f, fill=col, anchor="lm")
        x += f.getlength(w + " ")
    return im.rotate(rot, resample=Image.BICUBIC, expand=True)


def draw_slam(frame, i, t, y=420):
    if KEYS[i] == "hook":
        y = 400
    for ci, ch in enumerate(chunks_of(i)):
        st = ch[0][0] - 0.03
        nxt = chunks_of(i)[ci + 1][0][0] - 0.03 if ci + 1 < len(chunks_of(i)) else OFF[i] + DUR[i]
        if st <= t < nxt:
            hi = 0
            for k, (ws, we, w) in enumerate(ch):
                if t >= ws - 0.03:
                    hi = k
            text = " ".join(w.rstrip(",.:") for _, _, w in ch).upper().replace("ß", "SS")
            rot = (-3, 2, -1.5, 3)[ci % 4]
            im = slam_img(text, hi, rot)
            p = c01((t - st) / 0.12)
            sc = min(lerp(1.5, 1.0, ease_out(p)), (W - 30) / im.width)
            if sc != 1:
                im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BILINEAR)
            frame.alpha_composite(im, (int(W / 2 - im.width / 2), int(y - im.height / 2)))
            return


# ------------------------------------------------------------------ scenes
# each scene: fn(c, frame_later_list, t, lt) draws into sticker layer c; returns list of
# (callable(frame)) overlays drawn after stickers (emoji etc.)
def sc_hook(c, t, lt, post):
    # giant stop sign slams in, phone screams, swiping thumb gets blocked
    p = ease_back(lt / 0.25, 3.0)
    r = 330 * p
    cx, cy = W / 2, 1020
    pts = [(cx + r * math.cos(math.radians(22.5 + k * 45)), cy + r * math.sin(math.radians(22.5 + k * 45))) for k in range(8)]
    c.poly(pts, (220, 20, 30))
    pts2 = [(cx + 0.88 * r * math.cos(math.radians(22.5 + k * 45)), cy + 0.88 * r * math.sin(math.radians(22.5 + k * 45))) for k in range(8)]
    c.poly(pts2, WHITE)
    pts3 = [(cx + 0.8 * r * math.cos(math.radians(22.5 + k * 45)), cy + 0.8 * r * math.sin(math.radians(22.5 + k * 45))) for k in range(8)]
    c.poly(pts3, (220, 20, 30))
    c.text(cx, cy, "STOPP", 112 * p, WHITE)
    handy(c, 300, 1620, s=0.55, mood="panic", t=t, la=170, ra=-170, shake=0.6)
    post.append(lambda fr: put_emoji(fr, "👆", 860, 1660 + 30 * math.sin(lt * 30), 170))
    post.append(lambda fr: put_emoji(fr, "🚫", 860, 1460, 150 * ease_back((lt - 0.3) / 0.3)))
    if lt > at("hook", "Leben"):
        post.append(lambda fr: put_emoji(fr, "⚰️", 820, 640, 130 * ease_back((lt - at("hook", "Leben")) / 0.3), rot=10))


def sc_stats(c, t, lt, post):
    handy(c, 820, 1380, s=0.62, mood="sly", t=t, la=40, ra=-130, rel=-60)
    base = 1700
    hmax = 820
    p1 = ease_out((lt - at("stats", "sieben")) / 0.9)
    p2 = ease_back((lt - at("stats", "sieben", 1)) / 0.4)
    c.rect(110, base - hmax * p1, 330, base, PINK, r=24)
    c.rect(400, base - max(14, 24 * p2), 620, base, CYAN if p2 > 0 else (0, 0, 0, 0), r=10)
    c.rect(60, base, 700, base + 16, BLACK)
    if p1 > 0.2:
        c.text(220, base - hmax * p1 + 60, "7 STD", 52, BLACK)
    c.text(220, base + 70, "HANDY", 44, WHITE)
    if lt > at("stats", "Mama"):
        c.text(510, base + 70, "MAMA", 44, WHITE)
    if p2 > 0:
        c.text(510, base - 90, "7 MIN", 52 * p2, WHITE)
        post.append(lambda fr: put_emoji(fr, "🥲", 510, base - 200, 110 * p2))


def battery(c, x, y, pct, col, s=1.0, blink=False, t=0):
    w, h = 210 * s, 400 * s
    c.rect(x - 50 * s, y - h / 2 - 34 * s, x + 50 * s, y - h / 2 + 6, BLACK, r=10 * s)
    c.rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, WHITE, r=34 * s)
    fill_h = (h - 40 * s) * pct
    if not blink or (t * 3) % 1 < 0.6:
        c.rect(x - w / 2 + 20 * s, y + h / 2 - 20 * s - max(fill_h, 16 * s), x + w / 2 - 20 * s,
               y + h / 2 - 20 * s, col, r=18 * s)


def sc_akku(c, t, lt, post):
    p = ease_back(lt / 0.4)
    battery(c, 300, 1150, 1.0 * p, (70, 220, 100), s=p)
    c.text(300, 1440, "HANDY 100%", 48, WHITE)
    handy(c, 300, 1150, s=0.32 * p, mood="happy", t=t, legs=False, la=0, ra=0) if False else None
    dz = lt > at("akku", "Du") - 0.1
    if dz:
        q = ease_back((lt - at("akku", "Du") + 0.1) / 0.35)
        battery(c, 780, 1150, 0.02 + 0.0 * q, RED, s=q, blink=lt > at("akku", "zwei"), t=t)
        c.text(780, 1440, "DU 2%", 48, RED if (t * 3) % 1 < 0.6 else WHITE)
        kid(c, 780, 1830, s=0.62 * q, la=10, ra=-10, mood="tired", bob=-4)
    post.append(lambda fr: put_emoji(fr, "😎", 300, 1140, 130 * p))
    if dz and lt > at("akku", "zwei"):
        post.append(lambda fr: put_emoji(fr, "💀", 780, 1140, 120 * ease_back((lt - at("akku", "zwei")) / 0.3)))


def sc_please(c, t, lt, post):
    z = lerp(1.0, 1.35, ease_out(lt / 3))
    handy(c, W / 2, 1280 + (z - 1) * 120, s=1.05 * z, mood="please", t=t, la=150, ra=-150, lel=60,
          rel=-60)
    post.append(lambda fr: put_emoji(fr, "🥺", 880, 1820 - 30 * math.sin(lt * 4), 130, rot=8))
    post.append(lambda fr: put_emoji(fr, "🙏", 190, 1790 + 30 * math.sin(lt * 4), 120, rot=-8))


def sc_count(c, t, lt, post):
    k = ease_out(lt / max(0.1, at("count", "Videos") + 0.2))
    n = max(1, int(round(lerp(1, 47, k))))
    c.rect(150, 860, 930, 1500, WHITE, r=50)
    c.text(W / 2, 960, "VIDEO NR.", 60, BLACK)
    c.text(W / 2, 1220, f"{n}", 300 if n < 47 else 340, (230, 40, 130) if n >= 47 else BLACK)
    c.text(W / 2, 1420, "„nur noch eins“", 64, (120, 120, 130), f=F_HAND)
    kid(c, 260, 1850, s=0.55, la=10, ra=-150, rel=-115, mood="tired", hold_phone=True, t=t)
    if n >= 47:
        post.append(lambda fr: put_emoji(fr, "🤡", 850, 1700, 170, rot=-10 + 6 * math.sin(lt * 8)))


def soap_screen(lc, x0, y0, x1, y1, tt):
    lc.d.rectangle([x0 * S, y0 * S, x1 * S, y1 * S], fill=(250, 220, 235))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + 40
    lc.rect(cx - 120, cy - 60, cx + 120, cy + 60, (180, 140, 255), r=20)
    lc.rect(cx - 120, cy - 60, cx + 120, cy - 20, (205, 180, 255), r=20)
    k = (tt * 1.6) % 1
    ky = cy - 200 + 160 * (1 - abs(1 - 2 * k))
    lc.rect(cx + 10, ky - 120, cx + 30, ky + 40, (200, 205, 215), r=4)
    lc.rect(cx + 6, ky - 200, cx + 34, ky - 110, (60, 40, 30), r=6)
    for j in range(5):
        fy = cy + 70 + ((tt * 0.8 + j * 0.2) % 1) * 160
        lc.rect(cx + 40 + j * 12 - 12, fy - 12, cx + 40 + j * 12 + 12, fy + 12, (180, 140, 255), r=4)


def sc_night(c, t, lt, post):
    for i in range(60):
        r = random.Random(i)
        x, y = r.uniform(0, W), r.uniform(700, 1900)
        a = int(140 + 110 * math.sin(t * 2 + i))
        c.circle(x, y, r.uniform(2, 5), (255, 255, 255, a))
    load = lt > at("night", "Ladebildschirm") - 0.6
    if lt < at("night", "Bruder"):
        # clock + bed + kid with phone
        c.rect(300, 760, 780, 960, BLACK, r=30)
        c.text(W / 2, 862, "03:00", 120, (255, 80, 80))
        c.rect(120, 1560, 960, 1700, (110, 90, 200), r=30)
        c.rect(120, 1500, 300, 1580, WHITE, r=30)
        kid(c, 420, 1610, s=0.8, la=10, ra=-150, rel=-115, legs="sit", mood="tired", hold_phone=True, t=t)
        c.rect(120, 1600, 960, 1760, (140, 120, 230), r=30)   # blanket
        post.append(lambda fr: put_emoji(fr, "🌙", 900, 820, 140))
    else:
        from gfx import phone
        phone(c, W / 2, 1300, 480, 860, content=soap_screen, t=lt)
        if load:
            q = ease_back((lt - at("night", "Ladebildschirm") + 0.6) / 0.4)
            c.rect(140, 1120 - 140 * q, 940, 1120 + 140 * q, WHITE, r=30)
            if q > 0.6:
                c.text(W / 2, 1060, "DEIN LEBEN LÄDT ...", 46, BLACK)
                c.rect(200, 1130, 880, 1190, (230, 230, 236), r=30)
                c.rect(200, 1130, 200 + 680 * 0.02 + 30, 1190, RED, r=30)
                c.text(W / 2, 1230, "2 %  ·  noch ca. 84 Jahre", 34, (120, 120, 130), f=F_BODY)
        post.append(lambda fr: put_emoji(fr, "🧼", 880, 800, 120, rot=10))


def sc_offline(c, t, lt, post):
    c.rect(-50, 1660, W + 50, H + 50, (40, 160, 110))
    xs = [200, 540, 880]
    for i, x in enumerate(xs):
        p = ease_back((lt - 0.2 - i * 0.35) / 0.35)
        if p <= 0:
            continue
        s = 0.92 * p
        if i == 0:
            lift = 0.5 + 0.5 * math.sin(lt * 6)
            hands = kid(c, x, 1680, s=s, la=lerp(60, 165, lift), ra=-lerp(60, 165, lift),
                        lel=lerp(-80, 0, lift), rel=lerp(-80, 0, lift), mood="determined")
            dumbbell(c, (hands[0][0] + hands[1][0]) / 2, (hands[0][1] + hands[1][1]) / 2, 0.9 * s)
        elif i == 1:
            hands = kid(c, x, 1680, s=s, la=40, ra=-40, lel=-95, rel=-95)
            book(c, x, hands[0][1] - 26 * s, s)
        else:
            bricks(c, x + 60, 1680, int(c01(lt / 3) * 12), 0.85)
            kid(c, x - 70, 1680, s=s, la=30, ra=-80 + 20 * math.sin(lt * 5), mood="happy")
    if lt > at("offline", "offline"):
        q = ease_back((lt - at("offline", "offline")) / 0.3, 2.5)
        st = Image.new("RGBA", (700, 200), (0, 0, 0, 0))
        d = ImageDraw.Draw(st)
        d.rounded_rectangle([8, 8, 692, 192], 26, outline=RED, width=14)
        d.text((350, 102), "OFFLINE", font=font(F_HEAD, 104), fill=RED, anchor="mm")
        st = st.rotate(-12, expand=True, resample=Image.BICUBIC)
        st = st.resize((max(1, int(st.width * q)), max(1, int(st.height * q))))
        post.append(lambda fr: fr.alpha_composite(st, (int(W / 2 - st.width / 2), int(1000 - st.height / 2))))
    if lt > at("offline", "Feed"):
        post.append(lambda fr: put_emoji(fr, "📵", 880, 820, 150 * ease_back((lt - at("offline", "Feed")) / 0.3)))


def sc_plan(c, t, lt, post):
    T = lambda w: at("plan", w)
    # drawer
    dx, dy = W / 2, 1520
    shut = ease_out((lt - T("Schublade")) / 0.45)
    c.rect(dx - 330, dy - 40, dx + 330, dy + 260, (170, 110, 60), r=20)
    if shut < 1:
        hy = lerp(1100, 1500, shut)
        handy(c, dx, hy, s=0.5, mood="panic", t=t, la=170, ra=-170, shake=0.3, legs=False)
    c.rect(dx - 330, dy - 40 + 120 * (1 - shut) * 0, dx + 330, dy + 260, (190, 125, 70), r=20)
    c.rect(dx - 80, dy + 90, dx + 80, dy + 120, BLACK, r=14)
    # 1 hour badge
    p = ease_back((lt - T("Eine")) / 0.35)
    if p > 0:
        c.circle(W / 2, 900, 150 * p, WHITE)
        c.text(W / 2, 880, "1 STD", 76 * p, BLACK)
        c.text(W / 2, 950, "pro Tag", 40 * p, (120, 120, 130), f=F_BODY)
    for k, (w, fn, x) in enumerate((("Training", dumbbell, 200), ("lernen", book, 540), ("bauen", None, 880))):
        q = ease_back((lt - T(w)) / 0.35)
        if q > 0:
            y = 1230 + 8 * math.sin(lt * 4 + k)
            c.circle(x, y, 120 * q, WHITE)
            if fn:
                fn(c, x, y, 1.2 * q)
            else:
                bricks(c, x, y + 60 * q, 9, 0.9 * q)


def sc_panic(c, t, lt, post):
    handy(c, W / 2, 1300, s=1.05, mood="panic", t=t, la=170, ra=-170, lel=-40, rel=40, shake=1.0)
    for k in range(8):
        a = lt * 2 + k * math.pi / 4
        x, y = W / 2 + 430 * math.cos(a), 1300 + 520 * math.sin(a)
        post.append(lambda fr, x=x, y=y, k=k: put_emoji(fr, "❤️" if k % 2 else "👍", x, y, 90))


def sc_dreams(c, t, lt, post):
    # left: like hearts frozen in a 'pause' bubble
    c.rect(80, 900, 470, 1300, WHITE, r=40)
    c.rect(200, 1010, 240, 1190, BLACK, r=8)
    c.rect(310, 1010, 350, 1190, BLACK, r=8)
    c.text(275, 1250, "LIKES: WARTEN", 32, BLACK)
    # right: kid jumping to a star
    q = c01((lt - at("dreams", "Träume")) / 0.6)
    j = abs(math.sin(lt * 5)) * 70 * q
    kid(c, 760, 1800, s=0.85, la=lerp(30, 175, q), ra=-lerp(30, 175, q), mood="happy" if q > 0 else "determined",
        legs="jump" if j > 10 else "stand", bob=j)
    post.append(lambda fr: put_emoji(fr, "❤️", 180, 860, 80))
    post.append(lambda fr: put_emoji(fr, "❤️", 400, 850, 70))
    post.append(lambda fr: put_emoji(fr, "⭐", 760, 880 - 30 * math.sin(lt * 3), 150 + 40 * q))
    if q > 0:
        post.append(lambda fr: put_emoji(fr, "🚀", 980, 1060 - 600 * q, 110, rot=20))


def sc_sad(c, t, lt, post):
    dx, dy = W / 2, 1520
    c.rect(dx - 330, dy - 40, dx + 330, dy + 260, (170, 110, 60), r=20)
    peek = ease_out(lt / 0.8)
    handy(c, dx, lerp(1560, 1330, peek), s=0.6, mood="sad", t=t, la=150, ra=-150, lel=60, rel=-60,
          tear=1.0, legs=False)
    c.rect(dx - 330, dy + 20, dx + 330, dy + 260, (190, 125, 70), r=20)
    c.rect(dx - 80, dy + 110, dx + 80, dy + 140, BLACK, r=14)
    post.append(lambda fr: put_emoji(fr, "🥹", 880, 1080, 110, rot=10))


def sc_update(c, t, lt, post):
    prog = ease_out((lt - 0.1) / max(0.5, at("update", "Version") + 0.2))
    c.rect(110, 760, 970, 1040, WHITE, r=40)
    c.text(W / 2, 830, "UPDATE: DU 2.0", 54, BLACK)
    c.rect(170, 900, 910, 960, (230, 230, 236), r=30)
    c.rect(170, 900, 170 + max(60, 740 * prog), 960, (60, 200, 100), r=30)
    c.text(W / 2, 1000, f"{int(prog * 100)} %  installiert", 36, (110, 110, 120), f=F_BODY)
    done = prog > 0.98
    kid(c, W / 2, 1820, s=1.05, la=150 if done else 30, ra=-150 if done else -30, lel=-110 if done else 0,
        rel=110 if done else 0, mood="determined" if done else "neutral")
    if done:
        for k in range(6):
            a = k * math.pi / 3 + lt
            post.append(lambda fr, a=a: put_emoji(fr, "✨", W / 2 + 330 * math.cos(a), 1400 + 300 * math.sin(a), 70))
        post.append(lambda fr: put_emoji(fr, "💪", 260, 1220, 120, rot=-12))
        post.append(lambda fr: put_emoji(fr, "🔥", 830, 1220, 120, rot=12))


def sc_cta(c, t, lt, post):
    p = ease_back(lt / 0.4)
    c.rect(100, 780 + (1 - p) * 300, 980, 1500 + (1 - p) * 300, WHITE, r=44)
    y = 780 + (1 - p) * 300
    c.text(W / 2, y + 80, "BILDSCHIRMZEIT-RANKING", 40, BLACK)
    rows = [("1.", "dein Kumpel", "11 Std"), ("2.", "du", "7 Std"), ("3.", "deine Mama", "7 Min")]
    for k, (r, n, v) in enumerate(rows):
        q = ease_back((lt - 0.4 - k * 0.25) / 0.3)
        if q <= 0:
            continue
        yy = y + 210 + k * 140
        c.rect(150, yy - 55, 930, yy + 55, (255, 236, 120) if k == 0 else (240, 240, 245), r=26)
        c.text(200, yy, r, 46, BLACK, anchor="lm")
        c.text(280, yy, n, 46 * q, BLACK, f=F_BLACK, anchor="lm")
        c.text(890, yy, v, 46, (230, 40, 130) if k == 0 else BLACK, anchor="rm")
    if lt > 0.5:
        post.append(lambda fr: put_emoji(fr, "🤡", 900, y + 140, 110, rot=12))
    if lt > at("cta", "Du"):
        q = ease_back((lt - at("cta", "Du")) / 0.3)
        c.rect(W / 2 - 300 * q, 1640 - 70 * q, W / 2 + 300 * q, 1640 + 70 * q, (230, 40, 130), r=70 * q)
        c.text(W / 2, 1640, "MARKIER IHN", 58 * q, WHITE)
        post.append(lambda fr: put_emoji(fr, "👇", W / 2 + 360, 1640 + 20 * math.sin(lt * 8), 100 * q))


SCENES = {k: globals()["sc_" + k] for k in KEYS}


# ------------------------------------------------------------------ frame
def scene_at(t):
    idx = 0
    for i, o in enumerate(OFF):
        if t >= o:
            idx = i
    return idx


def render_frame(n):
    t = n / FPS
    i = scene_at(t)
    k = KEYS[i]
    lt = t - OFF[i]
    frame = bg_img(BG[k]).copy().convert("RGBA")
    im, c = new_layer()
    post = []
    SCENES[k](c, t, lt, post)
    sticker(frame, finish(im))
    for fn in post:
        fn(frame)
    # captions
    if WHO[i] == "phone":
        draw_bubble(frame, i, t)
    else:
        draw_slam(frame, i, t)
    # cut punch: zoom-in + slight rotation snap
    if lt < 0.16 and i > 0:
        q = 1 - lt / 0.16
        z = 1 + 0.07 * q
        fr = frame.resize((int(W * z), int(H * z)), Image.BILINEAR)
        frame = fr.crop(((fr.width - W) // 2, (fr.height - H) // 2, (fr.width - W) // 2 + W, (fr.height - H) // 2 + H))
    if t < 1.0:
        q = (1 - t) ** 2
        dx, dy = int(math.sin(t * 90) * 34 * q), int(math.cos(t * 70) * 34 * q)
        frame = frame.transform((W, H), Image.AFFINE, (1, 0, dx, 0, 1, dy), fillcolor=(220, 20, 30))
        if t < 0.12:
            frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 200)))
    # punchline 'freeze' frame look: black-and-white flash
    for kk, w, occ in (("akku", "zwei", 0), ("night", "Ladebildschirm", 0), ("dreams", "nicht", 0)):
        tp = s0(kk) + at(kk, w, occ) + 0.45
        if 0 <= t - tp < 0.12:
            frame = frame.convert("L").convert("RGBA")
    d = ImageDraw.Draw(frame)
    d.rectangle([0, H - 14, int(W * t / TOTAL), H], fill=(230, 40, 130))
    d.rectangle([0, H - 14, W, H - 12], fill=BLACK)
    if t > TOTAL - 0.4:
        frame.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * c01((t - TOTAL + 0.4) / 0.4)))))
    return frame.convert("RGB").tobytes()


# ------------------------------------------------------------------ audio
SR = 44100


def make_voice():
    parts = []
    for i, tm in enumerate(TIM):
        a, b = CLIP[i]
        p = BUILD / f"clip{i:02d}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tm["audio"], "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
                        "-ar", str(SR), "-ac", "1", "-af", "afade=t=in:d=0.02", str(p)], check=True)
        with wave.open(str(p)) as wf:
            x = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).astype(np.float32) / 32768
        parts.append((OFF[i], x))
    out = np.zeros(int(TOTAL * SR) + SR)
    for o, x in parts:
        j = int(o * SR)
        out[j:j + len(x)] += x
    return out[:int(TOTAL * SR)]


def make_music(n):
    tt = np.arange(n) / SR
    out = np.zeros(n)
    bpm = 118
    beat = 60 / bpm
    rng = np.random.default_rng(7)
    # marimba-ish plucks over C – Am – F – G
    prog = [[261.6, 329.6, 392.0], [220.0, 261.6, 329.6], [174.6, 220.0, 261.6], [196.0, 246.9, 293.7]]
    pattern = [0, 2, 1, 2, 0, 2, 1, 2]
    L = int(0.4 * SR)
    lt = np.arange(L) / SR
    def pluck(f, amp):
        return amp * np.exp(-lt * 9) * (np.sin(2 * np.pi * f * lt) + 0.3 * np.sin(2 * np.pi * 4 * f * lt) * np.exp(-lt * 30))
    def bass(f):
        return 0.5 * np.exp(-lt * 5) * np.sin(2 * np.pi * f / 2 * lt)
    kick_l = int(0.3 * SR)
    kt = np.arange(kick_l) / SR
    kick = np.sin(2 * np.pi * (48 + 120 * np.exp(-kt * 35)) * kt) * np.exp(-kt * 10)
    snap = rng.standard_normal(int(0.09 * SR)) * np.exp(-np.arange(int(0.09 * SR)) / SR * 45)
    snap = np.diff(snap, prepend=0)
    step = beat / 2
    k = 0
    while k * step < TOTAL:
        t0 = k * step
        i = int(t0 * SR)
        ch = prog[(k // 16) % 4]
        def add(sig, i=i):
            m = min(len(sig), n - i)
            if m > 0:
                out[i:i + m] += sig[:m]
        add(pluck(ch[pattern[k % 8]] * (2 if k % 4 == 3 else 1), 0.16))
        if k % 4 == 0:
            add(bass(ch[0]) * 0.5)
            add(0.5 * kick)
        if k % 8 == 4:
            add(0.35 * snap)
        k += 1
    # punchline record-stops: music drops out briefly, then comes back
    env = np.ones(n)
    for kk, w in (("akku", "zwei"), ("night", "Ladebildschirm"), ("dreams", "nicht"), ("count", "Videos")):
        tp = s0(kk) + at(kk, w)
        a, b = int((tp - 0.05) * SR), int((tp + 0.9) * SR)
        env[a:b] = 0.0
        # descending 'record stop' tone
        sl = int(0.35 * SR)
        st = np.arange(sl) / SR
        f = 400 * np.exp(-st * 5)
        out[a - sl // 2:a + sl - sl // 2] += 0.25 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-st * 4)[:len(out[a - sl // 2:a + sl - sl // 2])]
    ramp = np.convolve(env, np.ones(800) / 800, mode="same")
    out *= ramp
    # sfx: pop for every bubble, whoosh on cuts
    for i in range(len(KEYS)):
        j = int(OFF[i] * SR)
        if WHO[i] == "phone":
            pl = int(0.08 * SR)
            pt = np.arange(pl) / SR
            pop = 0.5 * np.sin(2 * np.pi * (500 + 900 * pt / 0.08) * pt) * np.exp(-pt * 50)
            out[j:j + pl] += pop[:max(0, min(pl, n - j))]
        if i:
            wl = int(0.25 * SR)
            wn = rng.standard_normal(wl) * np.sin(np.linspace(0, np.pi, wl)) ** 2
            wn = np.convolve(wn, np.ones(10) / 10, mode="same")
            a = max(0, j - wl // 2)
            out[a:a + wl] += 0.12 * wn[:max(0, min(wl, n - a))]
    bl = int(1.2 * SR)
    bt = np.arange(bl) / SR
    boom = np.sin(2 * np.pi * (40 + 90 * np.exp(-bt * 12)) * bt) * np.exp(-bt * 3)
    boom += 0.6 * rng.standard_normal(bl) * np.exp(-bt * 18)
    out[:bl] += 1.4 * boom
    out *= np.clip((TOTAL - tt) / 0.8, 0, 1)
    return out / max(1e-6, np.abs(out).max())


def write_wav(p, x):
    with wave.open(str(p), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        d = BUILD / "stills"
        d.mkdir(exist_ok=True)
        for a in sys.argv[2:]:
            Image.frombytes("RGB", (W, H), render_frame(int(float(a) * FPS))).save(d / f"t{float(a):05.1f}.png")
        print("stills ->", d)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "times":
        for k, o, du in zip(KEYS, OFF, DUR):
            print(f"{k:8s} {o:6.2f} {du:5.2f}")
        print("total", round(TOTAL, 2))
        return
    voice = make_voice()
    write_wav(BUILD / "voice.wav", voice / max(1e-6, np.abs(voice).max()) * 0.95)
    write_wav(BUILD / "music.wav", make_music(len(voice)) * 0.9)
    ff = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(BUILD / "voice.wav"), "-i", str(BUILD / "music.wav"),
        "-filter_complex",
        "[1:a]volume=1.0,asplit=2[v][vs];[2:a]volume=0.30[m];"
        "[m][vs]sidechaincompress=threshold=0.04:ratio=5:attack=15:release=250[md];"
        "[v][md]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]",
        "-map", "0:v", "-map", "[a]", "-t", f"{TOTAL:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(OUT)], stdin=subprocess.PIPE)
    with Pool() as pool:
        for k, fr in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=6)):
            ff.stdin.write(fr)
            if k % 300 == 0:
                print(f"{k}/{NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("->", OUT)


if __name__ == "__main__":
    main()
