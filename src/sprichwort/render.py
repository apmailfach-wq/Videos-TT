"""Render one "Sprichwort-Check" episode (1080x1920, 30 fps).

Look: warm "Oma's kitchen" wallpaper, the proverb as a cross-stitched wall plaque that swings in,
typed headline on top, karaoke captions, fact card with counter + chart, versus cards, a truth-o-meter
with a stamp for the verdict and a big community question at the end.

    python3 tts.py geld && python3 render.py geld            # -> ../../sprichwort-01-geld.mp4
    python3 render.py geld preview 1 8 15 25 33              # stills -> build/sprichwort/geld/stills
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
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from episodes import EPISODES, CTA_Q  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EP = sys.argv[1] if len(sys.argv) > 1 else "geld"
E = EPISODES[EP]
SCENES = E["scenes"]
BUILD = ROOT / "build" / "sprichwort" / EP
FONTS = ROOT / "fonts"
W, H, FPS = 1080, 1920, 30
TAIL = 1.2

F_HEAD = str(FONTS / "Unbounded_900Black.ttf")
F_HEAD_B = str(FONTS / "Unbounded_700Bold.ttf")
F_HAND = str(FONTS / "Caveat_700Bold.ttf")
F_BODY_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_CAP = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

INK = (33, 27, 24)
GREY = (140, 124, 110)
TEAL = (22, 160, 140)
RED = (214, 58, 58)
GOLD = (236, 168, 34)
WOOD = (132, 84, 48)
WOOD_D = (96, 58, 32)
LINEN = (251, 245, 232)
PAPER = (255, 255, 255)
YELLOW = (255, 226, 0)


@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, size)


def c01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):
    return 1 - (1 - c01(x)) ** 3


def ease_io(x):
    x = c01(x)
    return x * x * (3 - 2 * x)


def ease_back(x, s=1.7):
    x = c01(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


# ------------------------------------------------------------------ timings
TIM = json.loads((BUILD / "timings.json").read_text())
KEYS = [s["key"] for s in SCENES]
OFF, _a = [], 0.0
for s in TIM:
    OFF.append(_a)
    _a += s["duration"]
TOTAL = _a + TAIL
NFRAMES = int(math.ceil(TOTAL * FPS))


def s0(k):
    return OFF[KEYS.index(k)]


def s1(k):
    i = KEYS.index(k)
    return OFF[i] + TIM[i]["duration"] + (TAIL if i == len(TIM) - 1 else 0)


def at(k, word, lead=0.05):
    if word is None:
        return s0(k)
    i = KEYS.index(k)
    for w in TIM[i]["words"]:
        if w["text"].strip(".,:!?").lower().startswith(word.lower()):
            return OFF[i] + w["start"] - lead
    print("WARN trigger not found", k, word)
    return s0(k) + 0.5


# ------------------------------------------------------------------ image helpers
def shadow(im, dy=14, blur=16, alpha=0.28, pad=40):
    out = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (40, 25, 15, 0))
    sh.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    out.alpha_composite(sh, (pad, pad + dy))
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(im, (pad, pad))
    return out


def paste_c(frame, im, cx, cy, scale=1.0, rot=0.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    if abs(scale - 1) > 0.005:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    if alpha < 0.999:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    frame.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))


@lru_cache(maxsize=64)
def emoji(ch, size=150):
    f = ImageFont.truetype(F_EMOJI, 109)
    im = Image.new("RGBA", (260, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((130, 80), ch, font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox())
    sc = size / max(im.size)
    return im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)


def wrap(text, f, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if cur and f.getlength(t) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + ([cur] if cur else [])


def parse_rich(text):
    out, hl = [], False
    for tok in text.split(" "):
        if tok.startswith("*"):
            hl, tok = True, tok[1:]
        end = "*" in tok
        tok = tok.replace("*", "")
        out.append((tok, hl))
        if end:
            hl = False
    return out


def rich_lines(text, fpath, max_w, sizes, max_lines=2):
    words = parse_rich(text)
    for size in sizes:
        f = font(fpath, size)
        sp = f.getlength(" ")
        lines, cur, cw, ok = [], [], 0, True
        for w, hl in words:
            ww = f.getlength(w)
            if ww > max_w:
                ok = False
                break
            if cur and cw + sp + ww > max_w:
                lines.append(cur)
                cur, cw = [], 0
            cw += (sp if cur else 0) + ww
            cur.append((w, hl))
        lines.append(cur)
        if ok and len(lines) <= max_lines:
            return size, lines
    return size, lines


# ------------------------------------------------------------------ background
def make_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    base = np.array([247, 238, 222], np.float32)
    stripe = (np.sin(xx / 54 * math.pi) > 0.6).astype(np.float32) * 6          # wallpaper stripes
    dots = ((((xx + 27) % 108) - 54) ** 2 + (((yy + 27) % 108) - 54) ** 2 < 30).astype(np.float32) * 10
    arr = base[None, None, :] - (stripe + dots)[..., None] * np.array([0.6, 0.8, 1.0])
    vign = np.sqrt(((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H * 0.45) / (H * 0.7)) ** 2)
    arr = arr * (1 - 0.22 * np.clip(vign, 0, 1) ** 2)[..., None]
    # header band
    band = np.clip((560 - yy) / 40, 0, 1)
    arr = arr * (1 - band[..., None]) + np.array([252, 248, 240]) * band[..., None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")


# ------------------------------------------------------------------ header
def draw_header(frame, scene, t):
    d = ImageDraw.Draw(frame)
    states = [(at(scene["key"], w), k, h) for w, k, h in scene["heads"]]
    cur = states[0]
    for s in states:
        if t >= s[0]:
            cur = s
    ts, kicker, head = cur
    first = states[0][0]
    # logo pill
    pill = "SPRICHWORT-CHECK"
    fp = font(F_HEAD, 30)
    pw = fp.getlength(pill) + 60
    d.rounded_rectangle([W / 2 - pw / 2, 70, W / 2 + pw / 2, 126], radius=28, fill=INK)
    d.text((W / 2, 99), pill, font=fp, fill=YELLOW, anchor="mm")
    # kicker (typed)
    fk = font(F_HEAD_B, 36)
    n = int((t - first) * 45)
    vis = kicker.upper()[:max(0, n)]
    d.text((W / 2, 180), vis, font=fk, fill=GREY, anchor="mm")
    if not head:
        return
    size, lines = rich_lines(head, F_HEAD, 980, range(110, 48, -4))
    fh = font(F_HEAD, size)
    p = (t - ts) * 40
    idx = 0
    y = 238 + size * 0.95 + (0 if len(lines) == 2 else size * 0.55)
    punch = 1 + 0.06 * (1 - ease_out((t - ts) / 0.25))
    layer = Image.new("RGBA", (W, 560), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for ln in lines:
        sp = fh.getlength(" ")
        full = sum(fh.getlength(w) for w, _ in ln) + sp * (len(ln) - 1)
        x = W / 2 - full / 2
        for w, hl in ln:
            col = RED if hl else INK
            if hl:
                # marker highlight behind word
                prog = c01((p - idx) / 8)
                if prog > 0:
                    ww = fh.getlength(w)
                    ld.rounded_rectangle([x - 10, y - size * 0.86, x - 10 + (ww + 20) * ease_out(prog), y + size * 0.14],
                                         radius=14, fill=(255, 220, 60))
                col = INK
            for ch in w:
                if p - idx > 0:
                    ld.text((x, y), ch, font=fh, fill=col, anchor="ls")
                x += fh.getlength(ch)
                idx += 1
            x += sp
            idx += 1
        y += size * 1.12
    if punch > 1.003:
        layer = layer.resize((int(W * punch), int(560 * punch)), Image.BICUBIC)
        layer = layer.crop((int((layer.width - W) / 2), int((layer.height - 560) / 2),
                            int((layer.width - W) / 2) + W, int((layer.height - 560) / 2) + 560))
    frame.alpha_composite(layer)


# ------------------------------------------------------------------ visuals
@lru_cache(maxsize=4)
def plaque_img(text):
    w, h = 860, 560
    ss = 2
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    S = lambda *v: [x * ss for x in v]  # noqa: E731
    d.rounded_rectangle(S(0, 0, w, h), radius=26 * ss, fill=WOOD_D)
    d.rounded_rectangle(S(10, 10, w - 10, h - 10), radius=20 * ss, fill=WOOD)
    for i in range(0, w, 22):   # wood grain
        d.line(S(i + 6, 14, i - 4, h - 14), fill=(120, 75, 42), width=2 * ss)
    d.rounded_rectangle(S(44, 44, w - 44, h - 44), radius=8 * ss, fill=LINEN)
    # linen weave
    for x in range(48, w - 44, 8):
        d.line(S(x, 46, x, h - 46), fill=(240, 232, 214), width=1)
    for y in range(48, h - 44, 8):
        d.line(S(46, y, w - 46, y), fill=(240, 232, 214), width=1)
    # cross-stitch border
    def xst(cx, cy, col, r=6):
        d.line(S(cx - r, cy - r, cx + r, cy + r), fill=col, width=3 * ss)
        d.line(S(cx - r, cy + r, cx + r, cy - r), fill=col, width=3 * ss)
    for x in range(78, w - 70, 26):
        xst(x, 76, RED)
        xst(x, h - 76, RED)
    for y in range(102, h - 90, 26):
        xst(78, y, RED)
        xst(w - 78, y, RED)
    # heart in stitches
    for (hx, hy) in [(-1, -1), (1, -1), (-2, 0), (0, 0), (2, 0), (-1, 1), (1, 1), (0, 2)]:
        xst(w / 2 + hx * 14, h - 128 + hy * 14, RED, 5)
    # text
    f = font(F_HAND, 108 * ss)
    lines = wrap(text, f, (w - 200) * ss)
    while len(lines) > 3:
        f = font(F_HAND, f.size - 8 * ss)
        lines = wrap(text, f, (w - 200) * ss)
    lh = f.size * 0.95
    y = (h * ss) / 2 - 30 * ss - lh * (len(lines) - 1) / 2
    for ln in lines:
        d.text((w * ss / 2, y), ln, font=f, fill=(44, 64, 120), anchor="mm")
        y += lh
    im = im.resize((w, h), Image.LANCZOS)
    # canvas with string + nail on top, pivot at the nail
    can = Image.new("RGBA", (w + 80, h + 260), (0, 0, 0, 0))
    cd = ImageDraw.Draw(can)
    nail = (can.width / 2, 40)
    cd.line([nail, (60, 220)], fill=(90, 70, 50), width=5)
    cd.line([nail, (can.width - 60, 220)], fill=(90, 70, 50), width=5)
    can.alpha_composite(shadow(im, pad=40), (0, 160))
    cd.ellipse([nail[0] - 14, nail[1] - 14, nail[0] + 14, nail[1] + 14], fill=(70, 70, 76))
    cd.ellipse([nail[0] - 6, nail[1] - 8, nail[0] + 2, nail[1] - 2], fill=(160, 160, 170))
    return can


def vis_plaque(frame, sc, v, t):
    st = s0(sc["key"])
    lt = t - st
    img = plaque_img(E["saying"] + ".")
    drop = ease_back(lt / 0.55, 1.3)
    swing = 9 * math.exp(-2.2 * lt) * math.cos(7 * lt) if lt > 0 else 0
    rot = swing + 0.8 * math.sin(t * 1.3)
    big = Image.new("RGBA", (img.width, img.height * 2), (0, 0, 0, 0))
    big.alpha_composite(img, (0, img.height))
    big = big.rotate(rot, center=(img.width / 2, img.height + 40), resample=Image.BICUBIC)
    nail_y = 600
    y = nail_y - 40 - (1 - drop) * 1000
    frame.alpha_composite(big, (int(W / 2 - img.width / 2), int(y - img.height)))
    # question marks pop in at "stimmt"
    tq = at(sc["key"], "stimmt")
    for i, (x, y0, r) in enumerate([(150, 1380, -18), (930, 1300, 16), (880, 700, 10)]):
        p = (t - tq - i * 0.12) / 0.35
        if p > 0:
            paste_c(frame, emoji("❓", 150), x, y0 + math.sin(t * 3 + i) * 12, ease_back(p, 2.5), r)


@lru_cache(maxsize=16)
def icon_card(ch, label):
    w, h = 300, 340
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w, h], radius=34, fill=PAPER)
    e = emoji(ch, 150)
    im.alpha_composite(e, (int(w / 2 - e.width / 2), 50))
    f = font(F_HEAD_B, 34 if len(label) < 10 else 28)
    d.text((w / 2, 270), label, font=f, fill=INK, anchor="mm")
    return shadow(im)


def vis_icons(frame, sc, v, t):
    items = v["items"]
    n = len(items)
    for i, (ch, label, word) in enumerate(items):
        p = (t - at(sc["key"], word)) / 0.4
        if p <= 0:
            continue
        x = W / 2 + (i - (n - 1) / 2) * 330
        y = 1000 + (i % 2) * 70 + math.sin(t * 2 + i) * 8
        paste_c(frame, icon_card(ch, label), x, y, ease_back(p, 2.0), (i - 1) * 4)
    # price tag with "unbezahlbar" crossed euro
    txt, word = v["stamp"]
    p = (t - at(sc["key"], word)) / 0.35
    if p > 0:
        paste_c(frame, stamp_img(txt, RED), W / 2, 1400, 1 + 1.2 * (1 - ease_out(p)), -8, c01(p * 2))


def fmt_num(n):
    return f"{n:,}".replace(",", ".")


@lru_cache(maxsize=4)
def study_card(source):
    w, h = 900, 380
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w, h], radius=30, fill=PAPER)
    d.rounded_rectangle([0, 0, w, 76], radius=30, fill=INK)
    d.rectangle([0, 40, w, 76], fill=INK)
    d.text((w / 2, 40), source, font=font(F_HEAD_B, 30), fill=YELLOW, anchor="mm")
    return im


def vis_study(frame, sc, v, t):
    k = sc["key"]
    st = s0(k)
    p = (t - st - 0.1) / 0.45
    if p <= 0:
        return
    card = study_card(v["source"]).copy()
    d = ImageDraw.Draw(card)
    t_c = at(k, v.get("count_at", "über"))
    cp = ease_out((t - t_c) / 1.1)
    num = int(round(v["number"] * cp))
    d.text((450, 205), fmt_num(num), font=font(F_HEAD, 130), fill=RED if cp >= 1 else INK, anchor="mm")
    d.text((450, 320), v["unit"], font=font(F_HEAD_B, 38), fill=GREY, anchor="mm")
    y = 820 + (1 - ease_back(p, 1.5)) * 400
    paste_c(frame, shadow(card), W / 2, y, 1.0, 0, c01(p * 2))
    ex = v.get("extra")
    if not ex:
        return
    te = at(k, ex["at"])
    pe = (t - te) / 0.4
    if pe <= 0:
        return
    if ex["type"] == "chart":
        draw_chart(frame, ex, t, te, at(k, ex["note_at"]))
    else:
        draw_people(frame, ex, t, te)


def draw_chart(frame, ex, t, te, tn):
    x0, y0, x1, y1 = 140, 1460, 960, 1060
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    a = c01((t - te) / 0.3)
    d.rounded_rectangle([90, 1020, 990, 1530], radius=30, fill=(255, 255, 255, int(235 * a)))
    d.line([x0, y1 - 10, x0, y0, x1, y0], fill=INK + (int(255 * a),), width=7)
    d.polygon([(x0 - 14, y1), (x0 + 14, y1), (x0, y1 - 24)], fill=INK)
    d.polygon([(x1 + 4, y0 - 14), (x1 + 4, y0 + 14), (x1 + 28, y0)], fill=INK)
    d.text((x0 + 20, y1 + 6), ex["y"] + " ↑", font=font(F_HEAD_B, 34), fill=INK, anchor="lt")
    d.text((x1 - 10, y0 + 22), "Einkommen →", font=font(F_HEAD_B, 30), fill=GREY, anchor="rt")
    prog = ease_io((t - te - 0.2) / 2.0)
    pts = []
    for i in range(61):
        u = i / 60
        if u > prog:
            break
        x = x0 + 30 + u * (x1 - x0 - 80)
        val = math.log(1 + 9 * u) / math.log(10)
        pts.append((x, y0 - 40 - val * (y0 - y1 - 140)))
    if len(pts) > 1:
        d.line(pts, fill=TEAL, width=14, joint="curve")
        ex_, ey = pts[-1]
        d.ellipse([ex_ - 16, ey - 16, ex_ + 16, ey + 16], fill=TEAL)
    frame.alpha_composite(lay)
    pn = (t - tn) / 0.35
    if pn > 0:
        paste_c(frame, stamp_img(ex["note"], RED, 52), 690, 1390, 1 + (1 - ease_out(pn)) * 1.2, -10, c01(pn * 2))


@lru_cache(maxsize=4)
def person(col, s=1.0):
    im = Image.new("RGBA", (120, 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([30, 0, 90, 60], fill=col)
    d.rounded_rectangle([14, 70, 106, 220], radius=40, fill=col)
    return im


def draw_people(frame, ex, t, te):
    n = ex["n"]
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([60, 1070, 1020, 1500], radius=30, fill=PAPER)
    frame.alpha_composite(shadow(lay.crop((60, 1070, 1020, 1500))), (20, 1030))
    for i in range(n):
        p = (t - te - i * 0.06) / 0.3
        if p <= 0:
            continue
        hl = i == 6 and t > te + 1.0
        img = person(TEAL if hl else (190, 180, 168))
        x = 130 + i * 91
        paste_c(frame, img, x, 1250, 0.62 * ease_back(p, 2) * (1.25 if hl else 1))
        if hl:
            paste_c(frame, emoji("❤️", 70), x, 1120 + math.sin(t * 5) * 6, ease_back((t - te - 1.0) / 0.3, 2))
    d2 = ImageDraw.Draw(frame)
    if t > te + 1.0:
        d2.text((W / 2, 1430), "1 von 10 frühen Todesfällen", font=font(F_HEAD_B, 38), fill=INK, anchor="mm")


@lru_cache(maxsize=8)
def vs_card(ch, l1, l2, dim):
    w, h = 440, 520
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w, h], radius=36, fill=PAPER)
    e = emoji(ch, 200)
    im.alpha_composite(e, (int(w / 2 - e.width / 2), 60))
    d.text((w / 2, 360), l1, font=font(F_HEAD_B, 36), fill=GREY, anchor="mm")
    d.text((w / 2, 420), l2, font=font(F_HEAD, 44 if len(l2) < 10 else 36), fill=INK, anchor="mm")
    if dim:
        ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(ov).rounded_rectangle([0, 0, w, h], radius=36, fill=(247, 238, 222, 120))
        im.alpha_composite(ov)
    return shadow(im)


def vis_versus(frame, sc, v, t):
    k = sc["key"]
    tm = at(k, v["mark_at"])
    marked = t >= tm
    for j, (side, (ch, l1, l2, word), x) in enumerate((("left", v["left"], 290), ("right", v["right"], 790))):
        p = (t - s0(k) - 0.15 - 0.35 * j) / 0.4
        if p <= 0:
            continue
        mine = v["mark"] == side
        dim = marked and not mine
        sc_ = ease_back(p, 2) * (1.08 if marked and mine else (0.92 if dim else 1))
        paste_c(frame, vs_card(ch, l1, l2, dim), x, 1060 + math.sin(t * 2 + x) * 8, sc_, -4 if side == "left" else 4)
    pv = (t - s0(k) - 0.3) / 0.3
    if pv > 0:
        f = font(F_HEAD, 70)
        im = Image.new("RGBA", (200, 140), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((100, 70), "VS", font=f, fill=RED, anchor="mm", stroke_width=8, stroke_fill=PAPER)
        paste_c(frame, im, W / 2, 1060, ease_back(pv, 3))
    if marked:
        x = 290 if v["mark"] == "left" else 790
        p = (t - tm) / 0.35
        col = RED if v.get("mark_red") else TEAL
        paste_c(frame, stamp_img(v["mark_text"].upper(), col, 44), x, 1400, 1 + (1 - ease_out(p)) * 1.2, -6,
                c01(p * 2))


@lru_cache(maxsize=16)
def stamp_img(text, col, size=64):
    f = font(F_HEAD, size)
    tw = f.getlength(text)
    w, h = int(tw + size * 1.2), int(size * 2.0)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 4, w - 4, h - 4], radius=16, outline=col, width=8, fill=(255, 255, 255, 200))
    d.text((w / 2, h / 2 + 2), text, font=f, fill=col, anchor="mm")
    # grunge
    rng = np.random.default_rng(len(text))
    a = np.array(im.getchannel("A"), np.float32)
    a *= (rng.random(a.shape) > 0.08)
    im.putalpha(Image.fromarray(a.astype(np.uint8)))
    return im


@lru_cache(maxsize=1)
def gauge_base():
    ss = 2
    R = 380
    w, h = (R * 2 + 80), R + 120
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = w / 2 * ss, (R + 40) * ss
    box = [cx - R * ss, cy - R * ss, cx + R * ss, cy + R * ss]
    d.pieslice([b + (-30 if i < 2 else 30) * ss for i, b in enumerate(box)], 180, 360, fill=PAPER)
    for a0, a1, col in [(180, 240, RED), (240, 300, GOLD), (300, 360, TEAL)]:
        d.arc(box, a0 + 1, a1 - 1, fill=col, width=70 * ss)
    f = font(F_HEAD, 30 * ss)
    for ang, txt in [(210, "MYTHOS"), (270, "HALB"), (330, "STIMMT")]:
        r = math.radians(ang)
        rr = (R - 120) * ss
        lab = Image.new("RGBA", (int(f.getlength(txt) + 20), 50 * ss), (0, 0, 0, 0))
        ImageDraw.Draw(lab).text((lab.width / 2, lab.height / 2), txt, font=f, fill=INK, anchor="mm")
        lab = lab.rotate(-(ang - 270), resample=Image.BICUBIC, expand=True)
        im.alpha_composite(lab, (int(cx + math.cos(r) * rr - lab.width / 2), int(cy + math.sin(r) * rr - lab.height / 2)))
    im = im.resize((w, h), Image.LANCZOS)
    return shadow(im), (w / 2 + 40, R + 40 + 40)


def vis_verdict(frame, sc, v, t):
    k = sc["key"]
    st = s0(k)
    p = (t - st) / 0.4
    if p <= 0:
        return
    base, (px, py) = gauge_base()
    img = base.copy()
    d = ImageDraw.Draw(img)
    tv = at(k, v["at"])
    # needle sweeps back and forth ("thinking") then settles on the verdict
    lt = t - st
    if t < tv:
        pos = 0.5 + 0.45 * math.sin(lt * 6.5)
    else:
        e = t - tv
        pos = v["pos"] + (0.5 + 0.45 * math.sin((tv - st) * 6.5) - v["pos"]) * math.exp(-5 * e) * math.cos(14 * e)
    ang = math.radians(180 + 180 * c01(pos))
    L = 330
    tip = (px + math.cos(ang) * L, py + math.sin(ang) * L)
    perp = (math.cos(ang + math.pi / 2) * 16, math.sin(ang + math.pi / 2) * 16)
    d.polygon([(px + perp[0], py + perp[1]), tip, (px - perp[0], py - perp[1])], fill=INK)
    d.ellipse([px - 34, py - 34, px + 34, py + 34], fill=INK)
    d.ellipse([px - 12, py - 12, px + 12, py + 12], fill=YELLOW)
    paste_c(frame, img, W / 2, 1020, ease_back(p, 1.6))
    ps = (t - tv - 0.25) / 0.3
    if ps > 0:
        col = RED if v["pos"] < 0.33 else (GOLD if v["pos"] < 0.67 else TEAL)
        paste_c(frame, stamp_img(v["label"], col, 100), W / 2, 1360, 1 + (1 - ease_out(ps)) * 1.6, -7, c01(ps * 2))
        if ps < 1.5:   # flash
            fl = Image.new("RGBA", (W, H), (255, 255, 255, int(110 * (1 - c01(ps)))))
            frame.alpha_composite(fl)


def vis_cta(frame, sc, v, t):
    st = s0(sc["key"])
    p = (t - st) / 0.45
    size, lines = rich_lines(CTA_Q, F_HEAD, 840, range(84, 40, -4), max_lines=4)
    f = font(F_HEAD, size)
    bh = int(len(lines) * size * 1.18 + 120)
    im = Image.new("RGBA", (960, bh + 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, 960, bh], radius=48, fill=INK)
    d.polygon([(160, bh - 2), (260, bh - 2), (150, bh + 66)], fill=INK)
    y = 60 + size * 0.9
    for ln in lines:
        sp = f.getlength(" ")
        full = sum(f.getlength(w) for w, _ in ln) + sp * (len(ln) - 1)
        x = 480 - full / 2
        for w, hl in ln:
            d.text((x, y), w, font=f, fill=YELLOW if hl else PAPER, anchor="ls")
            x += f.getlength(w) + sp
        y += size * 1.18
    paste_c(frame, shadow(im), W / 2, 330 + bh / 2 + 30, ease_back(p, 1.6))
    # mini plaque reminder + pointing finger
    pc = (t - at(sc["key"], "Schreib")) / 0.35
    if pc > 0:
        paste_c(frame, emoji("👇", 190), W / 2, 1180 + abs(math.sin(t * 5)) * -40, ease_back(pc, 2.5))
        fp = font(F_HEAD, 54)
        pill = Image.new("RGBA", (900, 130), (0, 0, 0, 0))
        pd = ImageDraw.Draw(pill)
        pd.rounded_rectangle([0, 0, 900, 130], radius=65, fill=RED)
        pd.text((450, 66), "AB IN DIE KOMMENTARE", font=fp, fill=PAPER, anchor="mm")
        paste_c(frame, shadow(pill), W / 2, 1420, ease_back(pc, 2) * (1 + 0.03 * math.sin(t * 8)))


VIS = dict(plaque=vis_plaque, icons=vis_icons, study=vis_study, versus=vis_versus, verdict=vis_verdict, cta=vis_cta)


# ------------------------------------------------------------------ captions
def build_caps():
    caps = []
    for si, sc in enumerate(TIM):
        sw = SCENES[si]["text"].replace(" –", ",").split()
        words = [dict(text=w["text"], start=OFF[si] + w["start"], end=OFF[si] + w["end"]) for w in sc["words"]]
        punct, j = set(), 0
        for i, w in enumerate(sc["words"]):
            j += len(w["text"].split())
            if j - 1 < len(sw) and sw[j - 1][-1] in ",.:!?":
                punct.add(i)
        chunk = []
        for i, w in enumerate(words):
            if chunk and (len(chunk) >= 3 or sum(len(x["text"]) for x in chunk) + len(w["text"]) > 16):
                caps.append(chunk)
                chunk = []
            chunk.append(w)
            if i in punct:
                caps.append(chunk)
                chunk = []
        if chunk:
            caps.append(chunk)
    out = []
    for i, ch in enumerate(caps):
        nxt = caps[i + 1][0]["start"] if i + 1 < len(caps) else TOTAL
        out.append(dict(words=ch, start=ch[0]["start"], end=min(nxt, ch[-1]["end"] + 0.4)))
    return out


CAPS = []


@lru_cache(maxsize=1024)
def cap_img(ci, active):
    c = CAPS[ci]
    f = font(F_CAP, 74)
    sp = f.getlength(" ")
    ws = [f.getlength(w["text"]) for w in c["words"]]
    tw = sum(ws) + sp * (len(ws) - 1)
    im = Image.new("RGBA", (int(tw + 60), 130), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 30
    for i, (w, ww) in enumerate(zip(c["words"], ws)):
        d.text((x, 65), w["text"], font=f, fill=YELLOW if i == active else PAPER, anchor="lm",
               stroke_width=10, stroke_fill=(0, 0, 0))
        x += ww + sp
    return im


def draw_caption(frame, t):
    if t >= s0("cta") - 0.05:
        return
    for ci, c in enumerate(CAPS):
        if c["start"] <= t < c["end"]:
            act = max([i for i, w in enumerate(c["words"]) if t >= w["start"]] or [0])
            img = cap_img(ci, act)
            p = c01((t - c["start"]) / 0.12)
            sc = (0.85 + 0.15 * ease_back(p, 2.0)) * min(1.0, 1000 / img.width)
            paste_c(frame, img, W / 2, 1640, sc)
            return


# ------------------------------------------------------------------ frame
BG = None


def init():
    global BG
    BG = make_bg()
    CAPS[:] = build_caps()


def scene_at(t):
    i = 0
    for j, o in enumerate(OFF):
        if t >= o:
            i = j
    return i


def render_frame(fi):
    t = fi / FPS
    si = scene_at(t)
    sc = SCENES[si]
    frame = BG.copy()
    draw_header(frame, sc, t)
    VIS[sc["vis"]["type"]](frame, sc, sc["vis"], t)
    # quick white wipe between scenes
    if si > 0:
        dt = t - OFF[si]
        if dt < 0.12:
            frame.alpha_composite(Image.new("RGBA", (W, H), (255, 250, 240, int(200 * (1 - dt / 0.12)))))
    draw_caption(frame, t)
    d = ImageDraw.Draw(frame)
    d.rounded_rectangle([40, 30, W - 40, 38], radius=4, fill=(0, 0, 0, 30))
    d.rounded_rectangle([40, 30, 40 + (W - 80) * c01(t / TOTAL), 38], radius=4, fill=RED)
    return frame.convert("RGB").tobytes()


# ------------------------------------------------------------------ sound
SR = 48000


def _env(n, a, dcy):
    tt = np.arange(n) / SR
    return np.minimum(1, tt / max(a, 1e-4)) * np.exp(-tt / dcy)


def sfx_whoosh(rng):
    n = int(0.4 * SR)
    noise = rng.standard_normal(n)
    out, y = np.zeros(n), 0.0
    for i in range(n):
        y += (0.02 + 0.35 * math.sin(math.pi * i / n) ** 2) * (noise[i] - y)
        out[i] = y
    return out * np.sin(np.pi * np.linspace(0, 1, n)) ** 1.5 * 0.9


def sfx_pop():
    n = int(0.09 * SR)
    tt = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(700 + 900 * tt / tt[-1]) / SR) * _env(n, 0.002, 0.025) * 0.6


def sfx_thud(rng):
    n = int(0.3 * SR)
    tt = np.arange(n) / SR
    return (np.sin(2 * np.pi * (55 + 90 * np.exp(-tt * 30)) * tt) * _env(n, 0.001, 0.09)
            + rng.standard_normal(n) * _env(n, 0.0005, 0.015) * 0.5)


def sfx_ding():
    n = int(0.8 * SR)
    tt = np.arange(n) / SR
    return sum(np.sin(2 * np.pi * f * tt) * a for f, a in [(1320, 0.5), (1980, 0.25), (2640, 0.12)]) * _env(n, 0.002, 0.25)


def sfx_tick():
    n = int(0.03 * SR)
    tt = np.arange(n) / SR
    return np.sin(2 * np.pi * 2400 * tt) * _env(n, 0.0005, 0.006) * 0.3


def beat_bed(dur, bpm=100):
    rng = np.random.default_rng(3)
    n = int(dur * SR)
    out = np.zeros(n)
    beat = 60 / bpm
    kn = int(0.3 * SR)
    kt = np.arange(kn) / SR
    kick = np.sin(2 * np.pi * (48 + 90 * np.exp(-kt * 25)) * kt) * _env(kn, 0.001, 0.12)
    hn = int(0.04 * SR)
    hat = np.diff(rng.standard_normal(hn + 1)) * _env(hn, 0.0005, 0.01) * 0.25
    chords = [[261.63, 329.63, 392.0], [220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 246.94, 293.66]]
    i, tb = 0, 0.0
    while tb < dur:
        a = int(tb * SR)
        if i % 4 in (0, 2):
            seg = kick[:max(0, min(kn, n - a))]
            out[a:a + len(seg)] += seg * 0.8
        h0 = int((tb + beat / 2) * SR)
        seg = hat[:max(0, min(hn, n - h0))]
        out[h0:h0 + len(seg)] += seg
        if i % 4 == 0:
            L = int(beat * 4 * SR)
            pt = np.arange(min(L, n - a)) / SR
            pad = sum(np.sin(2 * np.pi * f * pt) + 0.3 * np.sin(4 * np.pi * f * pt) for f in chords[(i // 4) % 4])
            out[a:a + len(pad)] += pad * np.minimum(1, pt / 0.3) * np.minimum(1, (L / SR - pt) / 0.3) * 0.05
        tb += beat
        i += 1
    return out * np.minimum(1, np.minimum(np.arange(n) / SR, (n - np.arange(n)) / SR / 1.5))


def make_sfx(path):
    rng = np.random.default_rng(11)
    n = int(TOTAL * SR) + SR
    out = np.zeros(n)

    def put(sig, tt):
        i = int(max(0, tt) * SR)
        sig = sig[:max(0, n - i)]
        out[i:i + len(sig)] += sig

    for sc in SCENES:
        k, v = sc["key"], sc["vis"]
        if k != SCENES[0]["key"]:
            put(sfx_whoosh(rng) * 0.6, s0(k) - 0.15)
        for w, _, _ in sc["heads"][1:]:
            put(sfx_tick() * 2, at(k, w))
        if v["type"] == "plaque":
            put(sfx_thud(rng) * 0.8, s0(k) + 0.45)
            put(sfx_pop(), at(k, "stimmt"))
        elif v["type"] == "icons":
            for _, _, w in v["items"]:
                put(sfx_pop(), at(k, w))
            put(sfx_thud(rng), at(k, v["stamp"][1]) + 0.15)
        elif v["type"] == "study":
            put(sfx_pop(), s0(k) + 0.1)
            t_c = at(k, v.get("count_at", "über"))
            for j in range(12):
                put(sfx_tick(), t_c + j * 0.08)
            put(sfx_ding() * 0.5, t_c + 1.1)
            ex = v["extra"]
            put(sfx_pop(), at(k, ex["at"]))
            if ex.get("note_at"):
                put(sfx_thud(rng), at(k, ex["note_at"]) + 0.15)
        elif v["type"] == "versus":
            put(sfx_pop(), s0(k) + 0.15)
            put(sfx_pop(), s0(k) + 0.5)
            put(sfx_thud(rng), at(k, v["mark_at"]) + 0.15)
        elif v["type"] == "verdict":
            tv = at(k, v["at"])
            for j in range(int((tv - s0(k)) / 0.12)):
                put(sfx_tick(), s0(k) + j * 0.12)
            put(sfx_thud(rng) * 1.3, tv + 0.3)
            put(sfx_ding() * 0.7, tv + 0.3)
        elif v["type"] == "cta":
            put(sfx_pop(), s0(k))
            put(sfx_pop(), at(k, "Schreib"))
    mix = out * 0.5
    bed = beat_bed(TOTAL)
    mix[:len(bed)] += bed * 0.2
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1) * 32000).astype(np.int16).tobytes())


def main():
    init()
    if len(sys.argv) > 2 and sys.argv[2] == "preview":
        (BUILD / "stills").mkdir(exist_ok=True)
        for tt in [float(x) for x in sys.argv[3:]]:
            Image.frombytes("RGB", (W, H), render_frame(int(tt * FPS))).save(BUILD / "stills" / f"t{tt:05.1f}.png")
        return
    out = ROOT / E["out"]
    lst = BUILD / "concat.txt"
    lst.write_text("".join(f"file '{s['audio']}'\n" for s in TIM))
    voice, sfx, audio = BUILD / "voice.wav", BUILD / "sfx.wav", BUILD / "mix.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-af", f"apad=pad_dur={TAIL},loudnorm=I=-16:TP=-2:LRA=11", "-ar", "48000", str(voice)], check=True)
    make_sfx(sfx)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(voice), "-i", str(sfx), "-filter_complex",
                    "[1:a]volume=0.6[s];[0:a][s]amix=inputs=2:normalize=0:duration=first,"
                    "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", str(audio)], check=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-t", f"{NFRAMES / FPS:.3f}", str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=init) as pool:
        for i, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=6)):
            ff.stdin.write(buf)
            if i % 300 == 0:
                print(f"frame {i}/{NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", out, f"{NFRAMES / FPS:.2f}s")


if __name__ == "__main__":
    main()
