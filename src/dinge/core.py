"""Shared engine for the series "Wenn Dinge reden könnten".

Timeline (from tts.py), object characters with eyes + lip-synced mouth, word-by-word captions,
series badge, trailer-style chapter stamps, synthesized epic score, camera/grain/vignette and the
ffmpeg pipe. Episode modules (ep_*.py) only draw their stage via draw(img, ctx).
"""
import json
import math
import os
import random
import subprocess
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "fonts"
W, H, FPS, SR = 1080, 1920, 30, 48000
TAIL = 1.6

F_HEAD = str(FONTS / "Unbounded_900Black.ttf")
F_HEAD_B = str(FONTS / "Unbounded_700Bold.ttf")
F_HAND = str(FONTS / "Caveat_700Bold.ttf")
F_BODY = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"

INK = (16, 16, 20)
WHITE = (255, 255, 255)
YELLOW = (255, 214, 10)
RED = (232, 52, 60)
GOLD = (236, 190, 90)


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


def ease_back(x, s=1.6):
    x = clamp01(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_col(a, b, t):
    return tuple(int(lerp(a[i], b[i], t)) for i in range(len(a)))


def darker(c, f=0.75):
    return tuple(int(v * f) for v in c[:3])


# ======================================================================= timeline
class Timeline:
    def __init__(self, ep):
        self.ep = ep
        self.dir = ROOT / "build" / "dinge" / ep
        self.segs = json.loads((self.dir / "timings.json").read_text())
        last = self.segs[-1]
        self.total = last["start"] + last["dur"] + TAIL
        self.nframes = int(math.ceil(self.total * FPS))
        self.scenes = []
        for s in self.segs:
            if not self.scenes or self.scenes[-1][0] != s["s"]:
                self.scenes.append([s["s"], max(0.0, s["start"] - 0.12), None])
        for i, sc in enumerate(self.scenes):
            sc[2] = self.scenes[i + 1][1] if i + 1 < len(self.scenes) else self.total
        self.words = [w for s in self.segs for w in s["words"]]
        self.braams = [s["start"] - 0.02 for s in self.segs if s.get("fx") == "braam"]
        self.drops = []
        for i, s in enumerate(self.segs):
            if s.get("drop"):
                self.drops.append((s["start"] + s["dur"] - 0.05, self.segs[i + 1]["start"] - 0.02))
        self.env = None

    def scene_at(self, t):
        for k, a, b in self.scenes:
            if a <= t < b:
                return k, t - a, b - a
        k, a, b = self.scenes[-1]
        return k, t - a, b - a

    def scene_span(self, key):
        for k, a, b in self.scenes:
            if k == key:
                return a, b
        raise KeyError(key)

    def word(self, prefix, occ=0, scene=None, lead=0.05):
        """Global time of the occ-th word starting with prefix (optionally within a scene)."""
        n = 0
        for s in self.segs:
            if scene and s["s"] != scene:
                continue
            for w in s["words"]:
                if w["text"].lower().startswith(prefix.lower()):
                    if n == occ:
                        return w["start"] - lead
                    n += 1
        raise KeyError((prefix, occ, scene))

    def seg(self, i):
        return self.segs[i]

    def load_env(self, voice):
        hop = SR // FPS
        n = len(voice) // hop
        rms = np.sqrt((voice[:n * hop].reshape(n, hop) ** 2).mean(1))
        rms = rms / (np.percentile(rms[rms > 0.005], 90) + 1e-6) if (rms > 0.005).any() else rms
        self.env = np.clip(rms, 0, 1.2)

    def mouth(self, t):
        if self.env is None:
            return 0.0
        i = int(t * FPS)
        if i >= len(self.env):
            return 0.0
        v = self.env[i]
        return 0.0 if v < 0.12 else min(1.0, v)


class Ctx:
    """Per-frame info handed to episode draw functions."""

    def __init__(self, tl, t):
        self.tl, self.t = tl, t
        self.scene, self.lt, self.sd = tl.scene_at(t)
        self.mouth = tl.mouth(t)
        self.blink = blink_amount(t)
        self.punch = 0.0
        for b in tl.braams:
            if b <= t < b + 1.2:
                self.punch = max(self.punch, math.exp(-(t - b) * 4.0))

    def since(self, t0):
        return self.t - t0

    def w(self, prefix, occ=0, scene=None):
        return self.tl.word(prefix, occ, scene or self.scene)


def blink_amount(t, seed=3):
    period = 3.3
    k = int(t / period)
    off = random.Random(seed * 1000 + k).uniform(0.4, period - 0.4)
    d = t - (k * period + off)
    if 0 <= d < 0.16:
        return 1 - abs(d - 0.08) / 0.08
    return 0.0


# ======================================================================= drawing helpers
def ss_image(w, h, fn, ss=2):
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    fn(ImageDraw.Draw(im), ss, im)
    return im.resize((w, h), Image.LANCZOS)


def shadowed(im, dy=18, blur=16, alpha=0.45, pad=50):
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    a = im.getchannel("A").point(lambda v: int(v * alpha))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(a)
    out.alpha_composite(sh, (pad, pad + dy))
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(im, (pad, pad))
    return out


def paste(img, tile, cx, cy, scale=1.0, angle=0.0, alpha=1.0):
    t = tile
    if abs(scale - 1) > 1e-3:
        t = t.resize((max(1, int(t.width * scale)), max(1, int(t.height * scale))), Image.BILINEAR)
    if abs(angle) > 0.05:
        t = t.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        a = t.getchannel("A").point(lambda v: int(v * max(0.0, alpha)))
        t = t.copy()
        t.putalpha(a)
    img.alpha_composite(t, (int(cx - t.width / 2), int(cy - t.height / 2))) if img.mode == "RGBA" else \
        img.paste(t, (int(cx - t.width / 2), int(cy - t.height / 2)), t)


def over(img, layer):
    """Blend an RGBA layer onto the (RGB) stage."""
    img.paste(layer, (0, 0), layer)


def vgrad(w, h, top, bottom):
    a = np.linspace(0, 1, h)[:, None, None]
    arr = np.array(top, np.float32)[None, None] * (1 - a) + np.array(bottom, np.float32)[None, None] * a
    return Image.fromarray(np.repeat(arr, w, 1).astype(np.uint8), "RGB")


def radial(w, h, cx, cy, r, inner, outer):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.clip(np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / r, 0, 1)[..., None]
    arr = np.array(inner, np.float32) * (1 - d) + np.array(outer, np.float32) * d
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def glow(im, radius=30, strength=1.0):
    g = im.filter(ImageFilter.GaussianBlur(radius))
    if strength != 1.0:
        g.putalpha(g.getchannel("A").point(lambda v: min(255, int(v * strength))))
    out = g.copy()
    out.alpha_composite(im)
    return out


def text_center(d, xy, text, f, fill, stroke=0, stroke_fill=INK, tracking=0):
    if tracking == 0:
        d.text(xy, text, font=f, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=stroke_fill)
        return
    ws = [f.getlength(c) for c in text]
    tot = sum(ws) + tracking * (len(text) - 1)
    x = xy[0] - tot / 2
    for c, cw in zip(text, ws):
        d.text((x, xy[1]), c, font=f, fill=fill, anchor="lm", stroke_width=stroke, stroke_fill=stroke_fill)
        x += cw + tracking


# ======================================================================= faces
def face(d, cx, cy, s, emo="neutral", mouth=0.0, blink=0.0, look=(0, 0), lid=(60, 60, 60),
         acc=None, ss=2, eye_gap=1.0):
    """Cartoon eyes + mouth. s = scale (1 => eyes ~70 px apart radius 34)."""
    S = s * ss
    ex = 62 * S * eye_gap
    rx, ry = 34 * S, 40 * S
    big = emo in ("shock", "stare")
    if big:
        rx, ry = rx * 1.12, ry * 1.12
    lid_f = {"tired": 0.42, "sad": 0.18, "angry": 0.3, "smug": 0.35, "cry": 0.2, "dead": 0.5}.get(emo, 0.0)
    lid_f = max(lid_f, blink)
    for side in (-1, 1):
        x, y = cx * ss + side * ex, cy * ss
        if acc == "sunglasses":
            continue
        d.ellipse([x - rx - 5 * S, y - ry - 5 * S, x + rx + 5 * S, y + ry + 5 * S], fill=INK)
        d.ellipse([x - rx, y - ry, x + rx, y + ry], fill=WHITE)
        pr = (8 if big else 15) * S
        if emo == "dead":
            for k in (-1, 1):
                d.line([x - 16 * S, y - 16 * S * k, x + 16 * S, y + 16 * S * k], fill=INK, width=int(7 * S))
        else:
            px, py = x + look[0] * 12 * S, y + 6 * S + look[1] * 10 * S
            d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=INK)
            d.ellipse([px - pr * 0.35 + pr * 0.35, py - pr * 0.75, px + pr * 0.35 + pr * 0.35, py - pr * 0.05],
                      fill=WHITE)
        if lid_f > 0.01:
            box = [x - rx - 6 * S, y - ry - 6 * S, x + rx + 6 * S, y + ry + 6 * S]
            if lid_f >= 0.97:
                d.ellipse(box, fill=lid)
                d.line([x - rx, y + 4 * S, x + rx, y + 4 * S], fill=INK, width=int(6 * S))
            else:
                a = math.degrees(math.asin(1 - 2 * lid_f))
                d.chord(box, 180 + a, 360 - a, fill=lid)
                ly = y - (ry + 6 * S) * math.sin(math.radians(a))
                half = (rx + 6 * S) * math.cos(math.radians(a))
                d.line([x - half, ly, x + half, ly], fill=INK, width=int(6 * S))
        # brows
        bw = 7 * S
        if emo in ("sad", "cry"):
            d.line([x + side * 34 * S, y - ry - 8 * S, x - side * 28 * S, y - ry - 26 * S], fill=INK, width=int(bw))
        elif emo == "angry":
            d.line([x + side * 36 * S, y - ry - 26 * S, x - side * 26 * S, y - ry - 4 * S], fill=INK, width=int(bw * 1.3))
        elif emo in ("shock", "stare"):
            d.arc([x - 32 * S, y - ry - 40 * S, x + 32 * S, y - ry - 6 * S], 200, 340, fill=INK, width=int(bw))
        if emo == "tired":
            d.arc([x - 28 * S, y + ry - 8 * S, x + 28 * S, y + ry + 18 * S], 20, 160, fill=darker(lid, 0.7),
                  width=int(5 * S))
    if acc == "sunglasses":
        y = cy * ss
        for side in (-1, 1):
            x = cx * ss + side * ex
            d.rounded_rectangle([x - 52 * S, y - 30 * S, x + 52 * S, y + 34 * S], radius=int(20 * S), fill=(12, 12, 16))
            d.line([x - 34 * S, y - 16 * S, x - 14 * S, y - 22 * S], fill=(90, 90, 110), width=int(6 * S))
        d.line([cx * ss - ex + 50 * S, y - 14 * S, cx * ss + ex - 50 * S, y - 14 * S], fill=(12, 12, 16), width=int(10 * S))
    if emo == "cry":
        x, y = cx * ss + ex + 20 * S, cy * ss + ry + 10 * S
        d.ellipse([x - 11 * S, y, x + 11 * S, y + 24 * S], fill=(110, 190, 255))
        d.polygon([(x - 10 * S, y + 8 * S), (x + 10 * S, y + 8 * S), (x, y - 14 * S)], fill=(110, 190, 255))
    # mouth
    my = cy * ss + 92 * S
    mw = 48 * S
    if mouth < 0.08:
        if emo in ("sad", "cry", "tired", "dead"):
            d.arc([cx * ss - mw * 0.8, my - 4 * S, cx * ss + mw * 0.8, my + 34 * S], 200, 340, fill=INK, width=int(8 * S))
        elif emo == "smug":
            d.arc([cx * ss - mw, my - 40 * S, cx * ss + mw, my + 14 * S], 20, 140, fill=INK, width=int(8 * S))
        elif emo in ("shock", "stare"):
            d.ellipse([cx * ss - 14 * S, my - 12 * S, cx * ss + 14 * S, my + 16 * S], fill=INK)
        elif emo == "angry":
            d.line([cx * ss - mw * 0.7, my + 6 * S, cx * ss + mw * 0.7, my], fill=INK, width=int(8 * S))
        else:
            d.line([cx * ss - mw * 0.6, my, cx * ss + mw * 0.6, my], fill=INK, width=int(8 * S))
    else:
        h = (10 + 46 * mouth) * S
        w = mw * (0.85 + 0.2 * mouth)
        d.rounded_rectangle([cx * ss - w, my - h / 2, cx * ss + w, my + h / 2], radius=int(min(h, w) / 2),
                            fill=(60, 14, 22), outline=INK, width=int(6 * S))
        if h > 30 * S:
            d.ellipse([cx * ss - w * 0.55, my + h / 2 - 18 * S, cx * ss + w * 0.55, my + h / 2 + 6 * S],
                      fill=(220, 90, 100))
        d.rectangle([cx * ss - w * 0.6, my - h / 2 + 3 * S, cx * ss + w * 0.6, my - h / 2 + 12 * S], fill=WHITE)


def q_mouth(m):
    return round(m * 4) / 4


def q_blink(b):
    return round(b * 3) / 3


# ======================================================================= captions
def build_chunks(tl, max_words=3, max_chars=17):
    chunks = []
    for s in tl.segs:
        if s["s"] == "cta":
            continue
        cur = []
        for w in s["words"]:
            txt = " ".join(x["text"] for x in cur + [w])
            if cur and (len(cur) >= max_words or len(txt) > max_chars):
                chunks.append(cur)
                cur = []
            cur.append(w)
        if cur:
            chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        a = c[0]["start"] - 0.04
        nxt = chunks[i + 1][0]["start"] - 0.04 if i + 1 < len(chunks) else 1e9
        b = min(nxt, c[-1]["end"] + 0.5)
        out.append(dict(a=a, b=b, words=c))
    return out


EMPH = {"zweimal", "pokémon-karten", "zwanziger", "34", "fünfmal", "danke", "geweint", "ausgebrochen", "folter",
        "springe", "putzlappen", "allein", "zurück", "dieselbe", "schuld", "geschafft", "matratze", "träume",
        "zivilisation", "bürgermeister", "familie", "schlager", "kerzenhalter", "abgelehnt", "einsätze", "2014"}


@lru_cache(maxsize=256)
def caption_tile(words, hi):
    f = font(F_HEAD, 74)
    parts = [w.upper() for w in words]
    space = 26
    widths = [f.getlength(p) for p in parts]
    tot = sum(widths) + space * (len(parts) - 1)
    size = 74
    if tot > 900:
        size = int(74 * 900 / tot)
        f = font(F_HEAD, size)
        widths = [f.getlength(p) for p in parts]
        tot = sum(widths) + space * (len(parts) - 1)
    im = Image.new("RGBA", (int(tot) + 60, size + 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 30
    for i, (p, wd) in enumerate(zip(parts, widths)):
        key = words[i].lower().strip(".,:!?…")
        col = YELLOW if i == hi else WHITE
        if i == hi and key in EMPH:
            col = (255, 80, 80)
        d.text((x, im.height / 2), p, font=f, fill=col, anchor="lm", stroke_width=9, stroke_fill=INK)
        x += wd + space
    return im


def draw_captions(img, chunks, t, y=1385):
    for c in chunks:
        if c["a"] <= t < c["b"]:
            hi = -1
            for i, w in enumerate(c["words"]):
                if t >= w["start"] - 0.04:
                    hi = i
            tile = caption_tile(tuple(w["text"] for w in c["words"]), hi)
            k = ease_back((t - c["a"]) / 0.16, 2.2)
            sc = 0.7 + 0.3 * k
            paste(img, tile, W / 2, y, scale=sc)
            return


# ======================================================================= overlays
@lru_cache(maxsize=None)
def badge_tile(folge):
    def fn(d, ss, im):
        f = font(F_HEAD, 30 * ss)
        txt = "WENN DINGE REDEN KÖNNTEN"
        tw = f.getlength(txt) + 40 * ss
        x0 = (im.width - tw) / 2
        d.rounded_rectangle([x0, 6 * ss, x0 + tw, 66 * ss], radius=30 * ss, fill=(14, 14, 18, 215),
                            outline=(255, 214, 10, 255), width=3 * ss)
        d.text((im.width / 2, 37 * ss), txt, font=f, fill=WHITE, anchor="mm")
        f2 = font(F_BODY, 26 * ss)
        lab = f"FOLGE {folge}"
        lw = f2.getlength(lab) + 30 * ss
        d.rounded_rectangle([(im.width - lw) / 2, 74 * ss, (im.width + lw) / 2, 112 * ss], radius=19 * ss,
                            fill=(255, 214, 10, 255))
        d.text((im.width / 2, 93 * ss), lab, font=f2, fill=INK, anchor="mm")
    return ss_image(820, 120, fn)


@lru_cache(maxsize=64)
def stamp_tile(small, big):
    def fn(d, ss, im):
        f1 = font(F_BODY, 30 * ss)
        f2 = font(F_HEAD, 60 * ss)
        bw = max(f2.getlength(big), f1.getlength(small) + 10 * len(small) * ss) / 2 + 40 * ss
        bw = min(bw, im.width / 2 - 4)
        d.rounded_rectangle([im.width / 2 - bw, 2 * ss, im.width / 2 + bw, 156 * ss], radius=22 * ss,
                            fill=(10, 10, 14, 170))
        text_center(d, (im.width / 2, 30 * ss), small, f1, (255, 214, 10), tracking=10 * ss)
        text_center(d, (im.width / 2, 100 * ss), big, f2, WHITE, stroke=4 * ss, stroke_fill=(0, 0, 0))
        w2 = min(f2.getlength(big) / 2 + 30 * ss, im.width / 2 - 10)
        d.line([im.width / 2 - w2, 148 * ss, im.width / 2 + w2, 148 * ss], fill=(255, 214, 10), width=4 * ss)
    return ss_image(1040, 160, fn)


def draw_stamp(img, labels, ctx):
    lab = labels.get(ctx.scene)
    if not lab:
        return
    lt = ctx.lt
    a = clamp01(lt / 0.25) * (1 - clamp01((lt - (ctx.sd - 0.25)) / 0.25))
    if a <= 0:
        return
    sc = 1.08 - 0.08 * ease_out(lt / 0.5)
    paste(img, stamp_tile(*lab), W / 2, 395, scale=sc, alpha=a)


@lru_cache(maxsize=None)
def cta_tile():
    def fn(d, ss, im):
        d.rounded_rectangle([10 * ss, 10 * ss, im.width - 10 * ss, im.height - 10 * ss], radius=46 * ss,
                            fill=(255, 255, 255, 255), outline=INK, width=8 * ss)
        f = font(F_HEAD, 70 * ss)
        lines = ["WELCHES DING", "SOLL ALS", "NÄCHSTES", "REDEN?"]
        for i, ln in enumerate(lines):
            d.text((im.width / 2, (95 + i * 92) * ss), ln, font=f, fill=INK if i < 3 else RED, anchor="mm")
        # comment bubble
        cx, cy = im.width / 2, 520 * ss
        d.rounded_rectangle([cx - 250 * ss, cy - 52 * ss, cx + 250 * ss, cy + 52 * ss], radius=52 * ss,
                            fill=(255, 214, 10))
        d.polygon([(cx - 150 * ss, cy + 40 * ss), (cx - 110 * ss, cy + 40 * ss), (cx - 170 * ss, cy + 90 * ss)],
                  fill=(255, 214, 10))
        d.text((cx, cy), "AB IN DIE KOMMENTARE", font=font(F_BODY, 38 * ss), fill=INK, anchor="mm")
    return shadowed(ss_image(900, 640, fn), alpha=0.5)


def draw_cta(img, ctx):
    k = ease_back(ctx.lt / 0.45, 1.8)
    if k <= 0:
        return
    sc = 0.55 + 0.45 * k
    paste(img, cta_tile(), W / 2, 1290 + 6 * math.sin(ctx.lt * 5), scale=sc)
    # bouncing arrow
    y = 1700 + 18 * math.sin(ctx.lt * 7)
    def fn(d, ss, im):
        d.polygon([(30 * ss, 0), (90 * ss, 0), (90 * ss, 50 * ss), (120 * ss, 50 * ss), (60 * ss, 110 * ss),
                   (0, 50 * ss), (30 * ss, 50 * ss)], fill=(255, 214, 10), outline=INK, width=5 * ss)
    paste(img, arrow_tile(fn), W / 2, y, alpha=clamp01((ctx.lt - 0.4) / 0.3))


_ARROW = {}


def arrow_tile(fn):
    if "a" not in _ARROW:
        _ARROW["a"] = ss_image(122, 112, fn)
    return _ARROW["a"]


# ======================================================================= camera & post
_VIG = None
_GRAIN = None


def post(img, ctx, zoom_extra=0.0, shake=0.0, grade=None):
    global _VIG, _GRAIN
    if _VIG is None:
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((x - W / 2) / (W * 0.62)) ** 2 + ((y - H / 2) / (H * 0.6)) ** 2)
        _VIG = (1 - 0.55 * np.clip(d - 0.45, 0, 1) ** 1.4)[..., None].astype(np.float32)
        rng = np.random.default_rng(7)
        _GRAIN = [rng.normal(0, 7, (H // 2, W // 2, 1)).astype(np.float32) for _ in range(6)]
    z = 1.0 + 0.045 * ease_io(ctx.lt / max(ctx.sd, 0.1)) + 0.07 * ctx.punch + zoom_extra
    sx = sy = 0.0
    if ctx.punch > 0.05 or shake > 0:
        amp = 16 * ctx.punch + shake
        sx = amp * math.sin(ctx.t * 71)
        sy = amp * math.cos(ctx.t * 53)
    if abs(z - 1) > 1e-3 or sx or sy:
        cw, ch = W / z, H / z
        x0, y0 = (W - cw) / 2 + sx, (H - ch) / 2 + sy
        img = img.transform((W, H), Image.AFFINE, (1 / z, 0, x0, 0, 1 / z, y0), resample=Image.BILINEAR)
    arr = np.asarray(img.convert("RGB"), np.float32)
    if grade is not None:
        arr = arr * np.array(grade[0], np.float32) + np.array(grade[1], np.float32)
    arr = arr * _VIG
    g = _GRAIN[int(ctx.t * FPS) % len(_GRAIN)]
    g = np.repeat(np.repeat(g, 2, 0), 2, 1)
    arr = arr + g
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


# ======================================================================= audio
def read_wav(path):
    with wave.open(str(path)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            a = a.reshape(-1, 2).mean(1)
        return a


def write_wav(path, a, ch=1):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())


def voice_track(tl, fx_chain=None):
    n = int(tl.total * SR)
    out = np.zeros(n, np.float32)
    for s in tl.segs:
        a = read_wav(s["audio"])
        i = int(s["start"] * SR)
        out[i:i + len(a)] += a[:max(0, n - i)]
    return out


def lowpass(x, fc):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / fc) ** 4)
    return np.fft.irfft(X, len(x)).astype(np.float32)


def saw(f, t, harm=10, det=0.0):
    out = np.zeros_like(t)
    for k in range(1, harm + 1):
        if f * k > 6000:
            break
        out += np.sin(2 * np.pi * f * (1 + det) * k * t + k) / k
    return out


CHORDS = [  # D minor trailer progression (root, third, fifth) in Hz around octave 2-3
    (73.42, 87.31, 110.0),   # Dm
    (58.27, 73.42, 87.31),   # Bb
    (65.41, 82.41, 98.0),    # C
    (55.0, 69.3, 82.41),     # A
]


def music(tl, voice):
    n = int(tl.total * SR)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(1)
    pad = np.zeros(n, np.float32)
    bounds = [sc[1] for sc in tl.scenes] + [tl.total]
    for i in range(len(tl.scenes)):
        a, b = int(bounds[i] * SR), int(bounds[i + 1] * SR)
        if b <= a:
            continue
        ch = CHORDS[i % len(CHORDS)]
        tt = t[a:b]
        seg = np.zeros(b - a, np.float32)
        for f in ch:
            for det in (-0.004, 0.004):
                seg += saw(f, tt, 12, det) * 0.22
                seg += saw(f * 2, tt, 8, det) * 0.10
        seg += np.sin(2 * np.pi * ch[0] / 2 * tt) * 0.5
        env = np.minimum(1, np.minimum((tt - tt[0]) / 0.25, (tt[-1] - tt + 1e-3) / 0.08))
        pad[a:b] = seg * env
    pad = lowpass(pad, 900) * 0.32
    # swelling intensity over the episode
    pad *= (0.6 + 0.5 * t / tl.total)

    perc = np.zeros(n, np.float32)

    def taiko(at, gain=1.0):
        i = int(at * SR)
        L = int(0.9 * SR)
        if i < 0 or i >= n:
            return
        L = min(L, n - i)
        tt = np.arange(L) / SR
        f = 48 + 70 * np.exp(-tt * 28)
        ph = 2 * np.pi * np.cumsum(f) / SR
        body = np.sin(ph) * np.exp(-tt * 5.5)
        nz = rng.normal(0, 1, L) * np.exp(-tt * 40) * 0.35
        perc[i:i + L] += (body + nz).astype(np.float32) * gain

    def tick(at, gain=0.12):
        i = int(at * SR)
        L = min(int(0.05 * SR), n - i)
        if L <= 0:
            return
        tt = np.arange(L) / SR
        perc[i:i + L] += (rng.normal(0, 1, L) * np.exp(-tt * 120) * gain).astype(np.float32)

    bpm = 96
    beat = 60 / bpm
    k = 0
    while k * beat < tl.total - TAIL:
        tb = k * beat
        if k % 4 in (0, 2):
            taiko(tb, 0.45 if k % 4 == 0 else 0.3)
        if k % 8 == 7:
            taiko(tb + beat / 2, 0.25)
        for j in range(4):
            tick(tb + j * beat / 4, 0.05 if j else 0.09)
        k += 1
    for sc in tl.scenes[1:]:
        taiko(sc[1], 0.75)
    hi = perc.copy()
    perc = lowpass(perc, 4000)

    # BRAAM hits
    braam = np.zeros(n, np.float32)
    for b in tl.braams:
        i = int(b * SR)
        L = min(int(3.0 * SR), n - i)
        tt = np.arange(L, dtype=np.float32) / SR
        s = np.zeros(L, np.float32)
        for f in (36.71, 73.42, 110.0, 146.83):
            for det in (-0.006, 0, 0.006):
                s += saw(f, tt, 14, det)
        env = np.minimum(1, tt / 0.03) * np.exp(-tt * 1.1)
        bright = lowpass(s * env, 1500) * 0.6 + s * env * 0.05
        braam[i:i + L] += bright * 0.55
        taiko(b, 1.2)

    # whoosh before each scene change
    wh = np.zeros(n, np.float32)
    for sc in tl.scenes[1:]:
        L = int(0.45 * SR)
        i = int(sc[1] * SR) - L
        if i < 0:
            continue
        tt = np.arange(L) / SR
        nz = rng.normal(0, 1, L).astype(np.float32)
        nz = lowpass(nz, 2500) * np.sin(np.pi * tt / (L / SR)) ** 2 * 0.5
        wh[i:i + L] += nz

    mus = pad + perc * 0.9 + braam + wh * 0.6
    # drops: silence before the punchline
    gain = np.ones(n, np.float32)
    for a, b in tl.drops:
        ia, ib = int(a * SR), int(b * SR)
        fade = int(0.15 * SR)
        gain[ia:ia + fade] = np.minimum(gain[ia:ia + fade], np.linspace(1, 0.04, fade))
        gain[ia + fade:ib] = 0.04
    mus *= gain
    # fade out at the very end
    fo = int(1.2 * SR)
    mus[-fo:] *= np.linspace(1, 0, fo)
    # ducking under voice
    env = np.abs(voice)
    k = int(0.12 * SR)
    env = np.convolve(env, np.ones(k) / k, "same")
    env = env / (env.max() + 1e-6)
    duck = 1 - 0.5 * np.clip(env * 3, 0, 1)
    mus *= duck
    mus /= (np.abs(mus).max() + 1e-6)
    return mus


def mix(tl, out_wav):
    v = voice_track(tl)
    tl.load_env(v)
    m = music(tl, v)
    v = v / (np.abs(v).max() + 1e-6) * 0.92
    mixed = v + m * 0.30
    raw = tl.dir / "mix_raw.wav"
    write_wav(raw, mixed / (np.abs(mixed).max() + 1e-6) * 0.95)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", str(SR), str(out_wav)], check=True)
    return v
