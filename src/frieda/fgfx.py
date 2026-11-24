"""Grafik-Werkzeuge: weiches 'aufgeblasenes' 3D-Shading für beliebige Formen, Text, Emoji, Kamera."""
import math
import random
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "fonts"
W, H, FPS = 1080, 1920, 30

F_BLACK = str(FONTS / "Unbounded_900Black.ttf")
F_BOLD = str(FONTS / "Unbounded_700Bold.ttf")
F_HAND = str(FONTS / "Caveat_700Bold.ttf")
F_INTER = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_INTER_B = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
YELLOW = (255, 214, 40)


@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, int(size))


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def lerp(a, b, t):
    return a + (b - a) * t


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = clamp01(x)
    return x ** 3


def ease_io(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def ease_back(x, s=1.7):
    x = clamp01(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def mixc(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def darker(c, f=0.7):
    return tuple(int(v * f) for v in c[:3])


# ------------------------------------------------------------------ soft 3D shader
KEY = np.array([1.06, 1.0, 0.9], np.float32)     # warme Sonne
AMB = np.array([0.92, 0.92, 1.0], np.float32)   # kühles Himmelslicht


def inflate(mask, color, radius=None, light=(-0.55, -0.75), amb=0.42, spec=0.22, shine=26, rim=0.0,
            rim_col=(255, 240, 210), flat=0.0, key=None, ambc=None):
    """mask: float32 HxW in 0..1. Gibt RGBA-Array zurück, schattiert wie ein weiches, aufgeblasenes Objekt."""
    h, w = mask.shape
    if radius is None:
        radius = max(3, min(h, w) * 0.22)
    b = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), max(0.5, radius * 0.75), borderType=cv2.BORDER_CONSTANT)
    hgt = np.sqrt(np.clip(b, 0, 1))
    gy, gx = np.gradient(hgt)
    k = radius * 1.5 * (1 - flat)
    nx, ny, nz = -gx * k, -gy * k, np.ones_like(hgt)
    n = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / n, ny / n, nz / n
    L = np.array([light[0], light[1], 0.8], np.float32)
    L /= np.linalg.norm(L)
    lam = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    Hv = L + np.array([0, 0, 1], np.float32)
    Hv /= np.linalg.norm(Hv)
    sp = np.clip(nx * Hv[0] + ny * Hv[1] + nz * Hv[2], 0, 1) ** shine
    base = np.array(color[:3], np.float32)
    kk = KEY if key is None else np.array(key, np.float32)
    aa = AMB if ambc is None else np.array(ambc, np.float32)
    col = base[None, None, :] * (amb * aa[None, None, :] + (1 - amb) * lam[..., None] * kk[None, None, :])
    col *= (0.82 + 0.18 * np.clip(b * 2 - 0.2, 0, 1))[..., None]  # weiche Kantenverdunklung (AO)
    col += 255 * spec * sp[..., None]
    if rim > 0:
        edge = np.clip(1 - nz, 0, 1) ** 1.6
        side = np.clip(0.5 + nx * 0.8 - ny * 0.2, 0, 1)
        col += (np.array(rim_col, np.float32) - col) * (edge * side * rim)[..., None]
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = np.clip(col, 0, 255).astype(np.uint8)
    out[..., 3] = (np.clip(mask, 0, 1) * 255).astype(np.uint8)
    return out


def shape_mask(w, h, draw_fn, ss=2):
    """draw_fn(ImageDraw, scale) zeichnet weiß auf L-Maske; supersampled für weiche Kanten."""
    m = Image.new("L", (w * ss, h * ss), 0)
    draw_fn(ImageDraw.Draw(m), ss)
    m = m.resize((w, h), Image.LANCZOS)
    return np.asarray(m, np.float32) / 255.0


def blob(canvas, bbox, draw_fn, color, radius=None, **kw):
    """Zeichnet eine weich schattierte Form. bbox=(x0,y0,x1,y1) auf canvas; draw_fn(d, s, ox, oy) erhält
    einen Offset, damit man in Canvas-Koordinaten zeichnen kann."""
    x0, y0, x1, y1 = [int(round(v)) for v in bbox]
    pad = 4
    x0 -= pad; y0 -= pad; x1 += pad; y1 += pad
    w, h = max(2, x1 - x0), max(2, y1 - y0)
    m = shape_mask(w, h, lambda d, s: draw_fn(d, s, x0, y0))
    arr = inflate(m, color, radius, **kw)
    canvas.alpha_composite(Image.fromarray(arr, "RGBA"), (x0, y0))


def ell(canvas, cx, cy, rx, ry, color, **kw):
    blob(canvas, (cx - rx, cy - ry, cx + rx, cy + ry),
         lambda d, s, ox, oy: d.ellipse([(cx - rx - ox) * s, (cy - ry - oy) * s, (cx + rx - ox) * s,
                                         (cy + ry - oy) * s], fill=255),
         color, kw.pop("radius", min(rx, ry) * 0.75), **kw)


def poly(canvas, pts, color, radius=None, **kw):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if radius is None:
        radius = min(max(xs) - min(xs), max(ys) - min(ys)) * 0.3
    blob(canvas, (min(xs), min(ys), max(xs), max(ys)),
         lambda d, s, ox, oy: d.polygon([((x - ox) * s, (y - oy) * s) for x, y in pts], fill=255),
         color, radius, **kw)


def rrect(canvas, x0, y0, x1, y1, r, color, radius=None, **kw):
    blob(canvas, (x0, y0, x1, y1),
         lambda d, s, ox, oy: d.rounded_rectangle([(x0 - ox) * s, (y0 - oy) * s, (x1 - ox) * s, (y1 - oy) * s],
                                                  radius=r * s, fill=255),
         color, radius if radius is not None else min(x1 - x0, y1 - y0) * 0.3, **kw)


def limb(canvas, p1, p2, width, color, **kw):
    """Weiche Röhre (Arm/Bein) von p1 nach p2."""
    (x1, y1), (x2, y2) = p1, p2
    r = width / 2

    def fn(d, s, ox, oy):
        d.line([((x1 - ox) * s, (y1 - oy) * s), ((x2 - ox) * s, (y2 - oy) * s)], fill=255, width=int(width * s))
        for x, y in ((x1, y1), (x2, y2)):
            d.ellipse([(x - r - ox) * s, (y - r - oy) * s, (x + r - ox) * s, (y + r - oy) * s], fill=255)

    blob(canvas, (min(x1, x2) - r, min(y1, y2) - r, max(x1, x2) + r, max(y1, y2) + r), fn, color,
         kw.pop("radius", r * 0.8), **kw)


def limb3(canvas, p1, p2, p3, width, color, **kw):
    """Zweigliedrige Röhre (Schulter-Ellbogen-Hand) als eine Form."""
    pts = [p1, p2, p3]
    r = width / 2
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]

    def fn(d, s, ox, oy):
        d.line([((x - ox) * s, (y - oy) * s) for x, y in pts], fill=255, width=int(width * s), joint="curve")
        for x, y in pts:
            d.ellipse([(x - r - ox) * s, (y - r - oy) * s, (x + r - ox) * s, (y + r - oy) * s], fill=255)

    blob(canvas, (min(xs) - r, min(ys) - r, max(xs) + r, max(ys) + r), fn, color, kw.pop("radius", r * 0.8), **kw)


def soft_shadow(canvas, cx, cy, rx, ry, alpha=0.35, blur=None):
    pad = int(max(rx, ry) * 0.6) + 4
    w, h = int(rx * 2 + pad * 2), int(ry * 2 + pad * 2)
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).ellipse([pad, pad, pad + rx * 2, pad + ry * 2], fill=int(255 * alpha))
    m = m.filter(ImageFilter.GaussianBlur(blur or ry * 0.6))
    sh = Image.new("RGBA", (w, h), (20, 20, 40, 0))
    sh.putalpha(m)
    canvas.alpha_composite(sh, (int(cx - w / 2), int(cy - h / 2)))


def radial(size, color, alpha=1.0, power=2.0):
    s = int(size)
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    r = np.sqrt((xx - s / 2) ** 2 + (yy - s / 2) ** 2) / (s / 2)
    a = np.clip(1 - r, 0, 1) ** power * alpha
    arr = np.zeros((s, s, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


@lru_cache(maxsize=64)
def glow(size, color, power=2.0, alpha=1.0):
    return radial(size, color, alpha, power)


def gradient(w, h, stops):
    """stops: Liste (pos 0..1, farbe)."""
    y = np.linspace(0, 1, h)
    arr = np.zeros((h, 3), np.float32)
    for c in range(3):
        arr[:, c] = np.interp(y, [s[0] for s in stops], [s[1][c] for s in stops])
    img = np.repeat(arr[:, None, :], w, axis=1)
    return Image.fromarray(img.astype(np.uint8), "RGB").convert("RGBA")


# ------------------------------------------------------------------ compositing
def paste_c(dst, img, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if img is None or alpha <= 0.01 or scale <= 0.01:
        return
    if abs(scale - 1) > 0.004:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BICUBIC)
    if rot:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    x0, y0 = int(round(cx - img.width / 2)), int(round(cy - img.height / 2))
    sx0, sy0 = max(0, -x0), max(0, -y0)
    dx0, dy0 = max(0, x0), max(0, y0)
    w = min(img.width - sx0, dst.width - dx0)
    h = min(img.height - sy0, dst.height - dy0)
    if w <= 0 or h <= 0:
        return
    dst.alpha_composite(img.crop((sx0, sy0, sx0 + w, sy0 + h)), (dx0, dy0))


def paste_at(dst, img, ax, ay, anchor, scale=1.0, alpha=1.0):
    """anchor = (fx, fy) Punkt im Sprite in Pixeln (vor Skalierung), der auf (ax, ay) landet."""
    cx = ax + (img.width / 2 - anchor[0]) * scale
    cy = ay + (img.height / 2 - anchor[1]) * scale
    paste_c(dst, img, cx, cy, scale, alpha)


def cam(img, z=1.0, cx=None, cy=None, rot=0.0):
    """Kamerazoom um (cx, cy); Bildgröße bleibt."""
    cx = img.width / 2 if cx is None else cx
    cy = img.height / 2 if cy is None else cy
    if abs(z - 1) < 0.002 and not rot and abs(cx - img.width / 2) < 0.5 and abs(cy - img.height / 2) < 0.5:
        return img
    if rot:
        img = img.rotate(rot, resample=Image.BILINEAR, center=(cx, cy))
    w, h = img.width / z, img.height / z
    if z >= 1:
        cx = min(max(cx, w / 2), img.width - w / 2)
        cy = min(max(cy, h / 2), img.height - h / 2)
    box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    return img.transform(img.size, Image.EXTENT, box, resample=Image.BILINEAR)


def blur(img, r):
    return img.filter(ImageFilter.GaussianBlur(r))


def tint(img, color, amt):
    ov = Image.new("RGBA", img.size, tuple(color) + (int(255 * amt),))
    out = img.copy()
    out.alpha_composite(ov)
    return out


def grade(img, sat=1.0, contrast=1.0, bright=1.0, warm=0.0):
    a = np.asarray(img.convert("RGB"), np.float32)
    g = a.mean(axis=2, keepdims=True)
    a = g + (a - g) * sat
    a = (a - 128) * contrast + 128
    a *= bright
    if warm:
        a[..., 0] += 18 * warm
        a[..., 2] -= 18 * warm
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")


@lru_cache(maxsize=4)
def vignette(strength=0.6, color=(0, 0, 0)):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.sqrt(((xx - W / 2) / (W * 0.72)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
    a = np.clip((v - 0.5) * 1.3, 0, 1) * strength
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


# ------------------------------------------------------------------ text
def wrap(text, f, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if cur and f.getlength(t) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


@lru_cache(maxsize=512)
def emoji(ch, size=120):
    f = ImageFont.truetype(F_EMOJI, 109)
    im = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((200, 100), ch, font=f, embedded_color=True, anchor="mm")
    bb = im.getbbox()
    im = im.crop(bb) if bb else im
    sc = size / max(1, im.height)
    return im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)


def is_emoji(tok):
    return any(ord(c) > 0x2100 for c in tok) and not any(c.isalpha() for c in tok)


@lru_cache(maxsize=512)
def text_img(text, size, fill=WHITE, fpath=F_BLACK, stroke=None, stroke_fill=BLACK, max_w=900, line_gap=1.12,
             shadow=True, hl=None):
    """Fetter weißer Text mit schwarzem Rand; Emoji-Tokens werden als Farb-Emoji gesetzt.
    hl: (wort-index, farbe) hebt ein Wort farbig hervor (gezählt über alle Tokens)."""
    f = font(fpath, size)
    stroke = int(size * 0.12) if stroke is None else stroke
    lines = wrap(text, f, max_w)
    lh = int(size * line_gap)
    sp = f.getlength(" ")

    def tok_w(t):
        return size * 1.15 if is_emoji(t) else f.getlength(t)

    widths = [sum(tok_w(t) for t in ln.split()) + sp * (len(ln.split()) - 1) for ln in lines]
    tw = int(max(widths)) + stroke * 2 + 40
    th = lh * len(lines) + stroke * 2 + 40
    im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    wi = 0
    for i, ln in enumerate(lines):
        x = (tw - widths[i]) / 2
        y = 20 + stroke + i * lh + lh * 0.8
        for t in ln.split():
            if is_emoji(t):
                e = emoji(t, int(size * 1.0))
                im.alpha_composite(e, (int(x + size * 0.07), int(y - size * 0.86)))
            else:
                c = fill
                if hl and hl[0] == wi:
                    c = hl[1]
                d.text((x, y), t, font=f, fill=c, anchor="ls", stroke_width=stroke, stroke_fill=stroke_fill)
            x += tok_w(t) + sp
            wi += 1
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        a = im.getchannel("A").filter(ImageFilter.GaussianBlur(size * 0.08)).point(lambda v: int(v * 0.55))
        sh.putalpha(a)
        out = Image.new("RGBA", (im.width, im.height + 8), (0, 0, 0, 0))
        out.alpha_composite(sh, (0, 8))
        out.alpha_composite(im, (0, 0))
        return out
    return im


def extrude_text(text, size, front, side, depth=16, fpath=F_BLACK, max_w=900, stroke=6):
    base = text_img(text, size, front, fpath, stroke=stroke, stroke_fill=(40, 20, 0), max_w=max_w, shadow=False)
    sidei = text_img(text, size, side, fpath, stroke=stroke, stroke_fill=darker(side, 0.6), max_w=max_w,
                     shadow=False)
    im = Image.new("RGBA", (base.width + depth + 10, base.height + depth + 10), (0, 0, 0, 0))
    for k in range(depth, 0, -1):
        im.alpha_composite(sidei, (k // 3, k))
    im.alpha_composite(base, (0, 0))
    return im


def pop_scale(t, dur=0.28):
    """Pop-in Skalierung (0 -> Überschwinger -> 1)."""
    if t <= 0:
        return 0.0
    return ease_back(t / dur, 2.2) if t < dur else 1.0


def rng(seed):
    return random.Random(seed)
