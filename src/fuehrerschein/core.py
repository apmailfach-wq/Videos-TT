"""Shared drawing toolkit: neon 2.5D look, shaded 'soft 3D' sprites, characters, text effects."""
import math
import random
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "fonts"
W, H, FPS = 1080, 1920, 30

F_BLACK = str(FONTS / "Unbounded_900Black.ttf")
F_BOLD = str(FONTS / "Unbounded_700Bold.ttf")
F_HAND = str(FONTS / "Caveat_700Bold.ttf")
F_INTER = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_INTER_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
F_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

# neon palette
TEAL = (0, 240, 220)
MAGENTA = (255, 40, 190)
YELLOW = (255, 220, 40)
BLUE = (40, 120, 255)
RED = (255, 50, 70)
WHITE = (255, 255, 255)
BG0 = (8, 8, 20)
BG1 = (24, 10, 44)
SKIN = (238, 186, 150)
SKIN2 = (214, 160, 125)


@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, size)


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


# ------------------------------------------------------------------ canvas helpers
def gradient(w, h, top, bottom):
    y = np.linspace(0, 1, h)[:, None, None]
    arr = np.array(top, np.float32) * (1 - y) + np.array(bottom, np.float32) * y
    return Image.fromarray(np.repeat(arr, w, axis=1).astype(np.uint8), "RGB").convert("RGBA")


def radial(size, color, alpha=1.0, power=2.0):
    s = size
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    r = np.sqrt((xx - s / 2) ** 2 + (yy - s / 2) ** 2) / (s / 2)
    a = np.clip(1 - r, 0, 1) ** power * alpha
    arr = np.zeros((s, s, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


@lru_cache(maxsize=64)
def glow_dot(size, color, power=2.0):
    return radial(size, color, 1.0, power)


def paste_c(dst, img, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if img is None or alpha <= 0.01 or scale <= 0.01:
        return
    if rot:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    if abs(scale - 1) > 0.004:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BICUBIC)
    if alpha < 0.999:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    _paste_clip(dst, img, cx, cy)


def _paste_clip(dst, img, cx, cy):
    x0, y0 = int(cx - img.width / 2), int(cy - img.height / 2)
    sx0, sy0 = max(0, -x0), max(0, -y0)
    dx0, dy0 = max(0, x0), max(0, y0)
    w = min(img.width - sx0, dst.width - dx0)
    h = min(img.height - sy0, dst.height - dy0)
    if w <= 0 or h <= 0:
        return
    dst.alpha_composite(img.crop((sx0, sy0, sx0 + w, sy0 + h)), (dx0, dy0))


def zoom_frame(img, z, cx=None, cy=None):
    """Camera zoom around (cx, cy) keeping the frame size."""
    if abs(z - 1) < 0.002:
        return img
    cx = img.width / 2 if cx is None else cx
    cy = img.height / 2 if cy is None else cy
    w, h = img.width / z, img.height / z
    box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    return img.transform(img.size, Image.EXTENT, box, resample=Image.BILINEAR)


def bloom(frame, strength=0.9, thresh=150):
    """Cheap neon bloom: bright pixels blurred at 1/4 res and screened back."""
    small = frame.convert("RGB").resize((W // 4, H // 4), Image.BILINEAR)
    arr = np.asarray(small).astype(np.float32)
    lum = arr.max(axis=2)
    mask = np.clip((lum - thresh) / (255 - thresh), 0, 1)[..., None]
    b = Image.fromarray((arr * mask).astype(np.uint8))
    b1 = b.filter(ImageFilter.GaussianBlur(6))
    b2 = b.filter(ImageFilter.GaussianBlur(18))
    glow = ImageChops.add(b1, b2).resize((W, H), Image.BILINEAR)
    if strength != 1:
        glow = Image.fromarray((np.asarray(glow).astype(np.float32) * strength).clip(0, 255).astype(np.uint8))
    return ImageChops.screen(frame.convert("RGB"), glow)


def vignette_img():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = np.sqrt(((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H / 2) / (H * 0.75)) ** 2)
    a = np.clip((v - 0.55) * 1.4, 0, 0.75)
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


# ------------------------------------------------------------------ soft 3D shading
def shaded_ellipse(w, h, base, rim=None, light=(-0.45, -0.6), spec=0.35, rim_amt=0.9, amb=0.35):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx + 0.5 - w / 2) / (w / 2)
    ny = (yy + 0.5 - h / 2) / (h / 2)
    r2 = nx ** 2 + ny ** 2
    inside = r2 <= 1
    nz = np.sqrt(np.clip(1 - r2, 0, 1))
    return _shade(nx, ny, nz, inside, base, rim, light, spec, rim_amt, amb, w, h)


def shaded_capsule(w, h, base, rim=None, light=(-0.45, -0.6), spec=0.25, rim_amt=0.9, amb=0.35, radius=None):
    """Rounded box shaded like a soft cylinder/pillow."""
    r = radius if radius is not None else min(w, h) / 2
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    cx = np.clip(xx, r, w - r)
    cy = np.clip(yy, r, h - r)
    dx, dy = (xx - cx) / r, (yy - cy) / r
    d2 = dx ** 2 + dy ** 2
    inside = d2 <= 1
    # pillow normal: combine corner normal with broad cylinder normal
    bx = (xx - w / 2) / (w / 2)
    by = (yy - h / 2) / (h / 2)
    nx = np.clip(dx * 0.7 + bx * 0.45, -1, 1)
    ny = np.clip(dy * 0.7 + by * 0.25, -1, 1)
    nz = np.sqrt(np.clip(1 - np.clip(nx ** 2 + ny ** 2, 0, 1), 0, 1))
    return _shade(nx, ny, nz, inside, base, rim, light, spec, rim_amt, amb, w, h)


def _shade(nx, ny, nz, inside, base, rim, light, spec, rim_amt, amb, w, h):
    L = np.array([light[0], light[1], 0.75], np.float32)
    L /= np.linalg.norm(L)
    lam = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    col = np.array(base, np.float32)[None, None, :] * (amb + (1 - amb) * lam)[..., None]
    # specular
    hz = np.clip(nz * 0.9 + (nx * L[0] + ny * L[1]) * 0.6, 0, 1) ** 24
    col += 255 * spec * hz[..., None]
    if rim is not None:
        rr = np.clip(1 - nz, 0, 1) ** 2.2 * np.clip(0.4 + nx * 0.6 - ny * 0.1, 0, 1) * rim_amt
        col = col + (np.array(rim, np.float32) - col * 0.3) * rr[..., None]
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., :3] = np.clip(col, 0, 255).astype(np.uint8)
    # anti-aliased edge
    edge = np.clip((1 - np.sqrt(np.clip(nx ** 2 + ny ** 2, 0, 4))) * min(w, h) * 0.5, 0, 1) if False else inside
    arr[..., 3] = np.where(edge, 255, 0).astype(np.uint8)
    im = Image.fromarray(arr, "RGBA")
    return im


def aa(im, ss=2):
    """Smooth jagged numpy-mask edges by a supersample round-trip."""
    big = im.resize((im.width * ss, im.height * ss), Image.BICUBIC)
    a = big.getchannel("A").filter(ImageFilter.GaussianBlur(ss * 0.7))
    big.putalpha(a)
    return big.resize(im.size, Image.LANCZOS)


@lru_cache(maxsize=256)
def sphere(d, base, rim=None, spec=0.4):
    return aa(shaded_ellipse(d, d, base, rim, spec=spec))


@lru_cache(maxsize=256)
def capsule(w, h, base, rim=None, radius=None, spec=0.25):
    return aa(shaded_capsule(w, h, base, rim, radius=radius, spec=spec))


# ------------------------------------------------------------------ characters
CHAR = {
    "rafael": dict(shirt=(20, 150, 150), rim=TEAL, hair=(40, 28, 22), skin=SKIN, beard=True, bald=False,
                   accent=TEAL),
    "klaus": dict(shirt=(170, 30, 120), rim=MAGENTA, hair=(150, 150, 158), skin=(236, 176, 150), beard=False,
                  bald=True, accent=MAGENTA),
    "cop": dict(shirt=(26, 46, 110), rim=BLUE, hair=(30, 30, 34), skin=(228, 178, 146), beard=False, bald=False,
                accent=BLUE),
    "kid": dict(shirt=(230, 190, 20), rim=YELLOW, hair=(90, 50, 25), skin=(244, 196, 162), beard=False, bald=False,
                accent=YELLOW),
}


@lru_cache(maxsize=32)
def head_sprite(who, d=260, glasses=False, worried=False):
    c = CHAR[who]
    pad = 40
    im = Image.new("RGBA", (d + pad * 2, d + pad * 2), (0, 0, 0, 0))
    head = sphere(d, c["skin"], c["rim"], 0.25)
    # ears
    ear = sphere(int(d * 0.2), mixc(c["skin"], (200, 120, 100), 0.25), c["rim"], 0.1)
    im.alpha_composite(ear, (pad - int(d * 0.06), pad + int(d * 0.42)))
    im.alpha_composite(ear, (pad + d - int(d * 0.14), pad + int(d * 0.42)))
    im.alpha_composite(head, (pad, pad))
    dr = ImageDraw.Draw(im)
    cx, cy = pad + d / 2, pad + d / 2
    # hair
    if who == "klaus":
        dr.chord([pad - 4, pad + d * 0.22, pad + d * 0.26, pad + d * 0.62], 90, 270, fill=c["hair"])
        dr.chord([pad + d * 0.74, pad + d * 0.22, pad + d + 4, pad + d * 0.62], 270, 90, fill=c["hair"])
        # moustache
        dr.rounded_rectangle([cx - d * 0.2, cy + d * 0.14, cx + d * 0.2, cy + d * 0.23], radius=d * 0.05,
                             fill=(120, 120, 128))
    elif who == "kid":
        dr.chord([pad - 6, pad - 10, pad + d + 6, pad + d * 0.62], 180, 360, fill=c["hair"])
    elif who == "cop":
        pass
    else:
        # rafael: fade + quiff
        dr.chord([pad - 2, pad - 18, pad + d + 2, pad + d * 0.55], 180, 360, fill=c["hair"])
        dr.ellipse([cx - d * 0.1, pad - 30, cx + d * 0.38, pad + d * 0.2], fill=c["hair"])
    if c["beard"]:
        dr.chord([pad + d * 0.12, pad + d * 0.35, pad + d * 0.88, pad + d * 1.0], 10, 170, fill=(60, 42, 32, 170))
    # eyes
    ex = d * 0.18
    ey = cy - d * 0.02
    for sx in (-1, 1):
        x = cx + sx * ex
        dr.ellipse([x - d * 0.075, ey - d * 0.09, x + d * 0.075, ey + d * 0.09], fill=WHITE)
        dr.ellipse([x - d * 0.04 + d * 0.01, ey - d * 0.045, x + d * 0.04 + d * 0.01, ey + d * 0.045],
                   fill=(25, 25, 35))
        dr.ellipse([x - d * 0.012 + d * 0.025, ey - d * 0.04, x + d * 0.012 + d * 0.025, ey - d * 0.015],
                   fill=WHITE)
        # brows
        tilt = d * 0.04 if worried else -d * 0.01
        dr.line([(x - d * 0.08, ey - d * 0.14 + (tilt if sx < 0 else -tilt) * 0),
                 (x + d * 0.08, ey - d * 0.14 + (tilt * sx if worried else 0))],
                fill=mixc(c["hair"], (30, 30, 30), 0.5), width=max(3, int(d * 0.03)))
    # nose
    nose = sphere(int(d * 0.12), mixc(c["skin"], (220, 120, 100), 0.35), None, 0.3)
    im.alpha_composite(nose, (int(cx - d * 0.06), int(cy + d * 0.03)))
    if glasses:
        for sx in (-1, 1):
            x = cx + sx * ex
            dr.rounded_rectangle([x - d * 0.13, ey - d * 0.09, x + d * 0.13, ey + d * 0.1], radius=d * 0.04,
                                 fill=(20, 20, 30), outline=TEAL, width=max(2, int(d * 0.015)))
            dr.line([(x - d * 0.08, ey - d * 0.05), (x - d * 0.02, ey - d * 0.07)], fill=(120, 255, 240),
                    width=max(2, int(d * 0.012)))
        dr.line([(cx - d * 0.05, ey - d * 0.03), (cx + d * 0.05, ey - d * 0.03)], fill=(20, 20, 30),
                width=max(3, int(d * 0.03)))
    if who == "cop":
        # police cap
        dr.chord([pad - 8, pad - 40, pad + d + 8, pad + d * 0.5], 180, 360, fill=(22, 36, 90))
        dr.rectangle([pad - 8, pad + d * 0.16, pad + d + 8, pad + d * 0.25], fill=(15, 22, 60))
        dr.ellipse([cx - d * 0.06, pad + d * 0.02, cx + d * 0.06, pad + d * 0.14], fill=YELLOW)
        dr.chord([pad + d * 0.05, pad + d * 0.18, pad + d * 0.95, pad + d * 0.38], 0, 180, fill=(10, 14, 36))
    if who == "rafael" and False:
        pass
    return im


@lru_cache(maxsize=16)
def torso_sprite(who, w=300, h=330):
    c = CHAR[who]
    im = capsule(w, h, c["shirt"], c["rim"], radius=int(w * 0.38))
    im = im.copy()
    d = ImageDraw.Draw(im)
    if who == "cop":
        d.rectangle([w * 0.47, 0, w * 0.53, h], fill=(14, 24, 70))
        d.rounded_rectangle([w * 0.08, h * 0.2, w * 0.44, h * 0.3], radius=6, fill=(20, 30, 80))
        d.text((w * 0.26, h * 0.25), "POLIZEI", font=font(F_BOLD, 15), fill=(220, 230, 255), anchor="mm")
        d.ellipse([w * 0.62, h * 0.18, w * 0.78, h * 0.34], fill=YELLOW)
    elif who == "klaus":
        # football jersey stripes
        d.rectangle([0, h * 0.42, w, h * 0.5], fill=(255, 220, 40, 210))
        d.text((w * 0.5, h * 0.3), "4", font=font(F_BLACK, 70), fill=(255, 255, 255, 230), anchor="mm")
    elif who == "rafael":
        # hoodie strings + logo
        d.line([(w * 0.42, h * 0.05), (w * 0.4, h * 0.3)], fill=(220, 255, 250), width=5)
        d.line([(w * 0.58, h * 0.05), (w * 0.6, h * 0.3)], fill=(220, 255, 250), width=5)
        d.ellipse([w * 0.43, h * 0.45, w * 0.57, h * 0.59], outline=(220, 255, 250), width=5)
    return im


@lru_cache(maxsize=32)
def arm_sprite(who, L=250, th=78):
    c = CHAR[who]
    im = Image.new("RGBA", (th + 30, L + th), (0, 0, 0, 0))
    sleeve = capsule(th, L, c["shirt"], c["rim"])
    im.alpha_composite(sleeve, (15, 0))
    hand = sphere(int(th * 1.05), c["skin"], c["rim"], 0.2)
    im.alpha_composite(hand, (15 + (th - hand.width) // 2, L - th // 2))
    return im


@lru_cache(maxsize=512)
def arm_rot(who, angle_q, scale_q):
    im = arm_sprite(who)
    if scale_q != 100:
        im = im.resize((int(im.width * scale_q / 100), int(im.height * scale_q / 100)), Image.BICUBIC)
    # pivot = top center -> pad so pivot is image centre before rotating
    w, h = im.size
    canvas = Image.new("RGBA", (w, h * 2), (0, 0, 0, 0))
    canvas.alpha_composite(im, (0, h))
    return canvas.rotate(angle_q, resample=Image.BICUBIC, expand=True)


@lru_cache(maxsize=256)
def head_scaled(who, glasses, worried, scale_q):
    im = head_sprite(who, glasses=glasses, worried=worried)
    return im.resize((int(im.width * scale_q / 100), int(im.height * scale_q / 100)), Image.BICUBIC)


@lru_cache(maxsize=128)
def torso_scaled(who, scale_q):
    im = torso_sprite(who)
    return im.resize((int(im.width * scale_q / 100), int(im.height * scale_q / 100)), Image.BICUBIC)


def draw_char(frame, who, cx, cy, s=1.0, arm_l=15, arm_r=-15, mouth=0.0, glasses=False, worried=False,
              blink=False, tilt=0.0, hold=None, legs=False, front_arms=True):
    """cx, cy = neck position. arm angles in degrees (0 = hanging down, + = raise outward/forward)."""
    sq = max(10, int(round(s * 50)) * 2)
    sc = sq / 100
    torso = torso_scaled(who, sq)
    tw, th = torso.size
    if legs:
        legc = (30, 30, 46) if who != "cop" else (16, 22, 56)
        for sx in (-1, 1):
            lg = capsule(int(80 * sc) or 1, int(260 * sc) or 1, legc, CHAR[who]["rim"])
            paste_c(frame, lg, cx + sx * 60 * sc, cy + th * 0.92 + 120 * sc)
            shoe = capsule(int(120 * sc) or 1, int(56 * sc) or 1, (20, 20, 24), CHAR[who]["rim"])
            paste_c(frame, shoe, cx + sx * 66 * sc + sx * 10 * sc, cy + th * 0.92 + 250 * sc)
    sh_y = cy + 40 * sc
    for side, ang in ((-1, arm_l), (1, arm_r)):
        if not front_arms:
            img = arm_rot(who, int(round(side * ang / 3) * 3), sq)
            paste_c(frame, img, cx + side * tw * 0.42, sh_y)
    paste_c(frame, torso, cx, cy + th / 2 - 10 * sc)
    head = head_scaled(who, glasses, worried, sq)
    hx, hy = cx, cy - 110 * sc
    if tilt:
        head = head.rotate(tilt, resample=Image.BICUBIC)
    paste_c(frame, head, hx, hy)
    d = ImageDraw.Draw(frame)
    D = 260 * sc
    # mouth
    mw = D * (0.16 + 0.06 * mouth)
    mh = D * (0.02 + 0.14 * mouth)
    my = hy + D * 0.27
    if mouth > 0.08:
        d.ellipse([hx - mw, my - mh, hx + mw, my + mh], fill=(70, 20, 30))
        d.ellipse([hx - mw * 0.6, my + mh * 0.2, hx + mw * 0.6, my + mh * 0.95], fill=(230, 90, 100))
    else:
        if worried:
            d.arc([hx - mw, my, hx + mw, my + D * 0.12], 200, 340, fill=(90, 30, 40), width=max(3, int(D * 0.025)))
        else:
            d.arc([hx - mw, my - D * 0.08, hx + mw, my + D * 0.06], 20, 160, fill=(90, 30, 40),
                  width=max(3, int(D * 0.025)))
    if blink:
        for sx in (-1, 1):
            x = hx + sx * D * 0.18
            d.rectangle([x - D * 0.085, hy - D * 0.12, x + D * 0.085, hy + D * 0.07], fill=CHAR[who]["skin"])
            d.line([(x - D * 0.07, hy - D * 0.02), (x + D * 0.07, hy - D * 0.02)], fill=(60, 40, 40),
                   width=max(2, int(D * 0.015)))
    if front_arms:
        for side, ang in ((-1, arm_l), (1, arm_r)):
            img = arm_rot(who, int(round(side * ang / 3) * 3), sq)
            paste_c(frame, img, cx + side * tw * 0.42, sh_y)
    if hold:
        side, item, ang = hold
        a = math.radians(ang)
        L = 262 * sc
        px = cx + side * tw * 0.42 + side * math.sin(a) * L
        py = sh_y + math.cos(a) * L
        draw_item(frame, item, px, py, sc)


def hand_pos(cx, cy, s, side, ang):
    sq = max(10, int(round(s * 50)) * 2) / 100
    tw = torso_scaled("rafael", int(sq * 100)).width
    a = math.radians(ang)
    L = 262 * sq
    return cx + side * tw * 0.42 + side * math.sin(a) * L, cy + 40 * sq + math.cos(a) * L


@lru_cache(maxsize=64)
def item_sprite(item, sq):
    s = sq / 100
    if item == "beer":
        w, h = int(110 * s), int(170 * s)
        im = Image.new("RGBA", (w + 60, h + 40), (0, 0, 0, 0))
        g = capsule(w, h, (250, 190, 30), YELLOW, radius=int(18 * s), spec=0.5)
        im.alpha_composite(g, (10, 30))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([10, 10, 10 + w, 50 * s + 10], radius=20 * s, fill=(255, 250, 235))
        d.rounded_rectangle([w + 2, 60 * s, w + 50 * s, 140 * s], radius=20 * s, outline=(255, 230, 150),
                            width=max(3, int(10 * s)))
        for k in range(5):
            bx = 10 + w * (0.2 + 0.15 * k)
            d.ellipse([bx, 80 * s + k * 15 * s, bx + 9 * s, 89 * s + k * 15 * s], fill=(255, 245, 200))
        return im
    if item == "joint":
        w, h = int(170 * s), int(26 * s)
        im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.polygon([(20, 20 + h * 0.3), (20 + w, 20), (20 + w, 20 + h), (20, 20 + h * 0.7)], fill=(245, 240, 230))
        g = glow_dot(int(70 * s), (255, 120, 40))
        im.alpha_composite(g, (int(20 + w - g.width / 2), int(20 + h / 2 - g.height / 2)))
        d.ellipse([20 + w - 8 * s, 20 + 2, 20 + w + 8 * s, 20 + h - 2], fill=(255, 90, 30))
        return im
    if item == "coffee":
        w, h = int(110 * s), int(140 * s)
        im = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0))
        im.alpha_composite(capsule(w, h, (240, 240, 245), TEAL, radius=int(20 * s), spec=0.4), (10, 40))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([w, 70 * s, w + 50 * s, 140 * s], radius=20 * s, outline=(230, 230, 240),
                            width=max(3, int(10 * s)))
        for k in range(3):
            x = 30 + k * 30 * s
            d.arc([x, 0, x + 24 * s, 40 * s], 200, 340, fill=(220, 220, 230, 160), width=max(2, int(5 * s)))
        return im
    if item == "keys":
        im = Image.new("RGBA", (int(120 * s), int(120 * s)), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse([10 * s, 10 * s, 60 * s, 60 * s], outline=YELLOW, width=max(3, int(8 * s)))
        d.rectangle([50 * s, 30 * s, 110 * s, 42 * s], fill=(210, 210, 220))
        return im
    return None


def draw_item(frame, item, x, y, sc):
    im = item_sprite(item, max(10, int(sc * 100)))
    if im is not None:
        paste_c(frame, im, x, y - im.height * 0.35)


# ------------------------------------------------------------------ text
def text_img(text, size, fill=WHITE, fpath=F_BLACK, stroke=0, stroke_fill=(0, 0, 0), glow=None, max_w=980,
             align_center=True, line_gap=1.08):
    f = font(fpath, size)
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
    lh = int(size * line_gap)
    tw = int(max(f.getlength(l) for l in lines)) + stroke * 2 + 40
    th = lh * len(lines) + stroke * 2 + 40
    im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        y = 20 + stroke + i * lh + lh * 0.82
        x = tw / 2 if align_center else 20 + stroke
        d.text((x, y), ln, font=f, fill=fill, anchor="ms" if align_center else "ls", stroke_width=stroke,
               stroke_fill=stroke_fill)
    if glow:
        g = Image.new("RGBA", im.size, glow + (0,))
        g.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(size * 0.18)))
        out = Image.new("RGBA", im.size, (0, 0, 0, 0))
        out.alpha_composite(g)
        out.alpha_composite(g)
        out.alpha_composite(im)
        return out
    return im


def glitch(img, t, amount=1.0, seed=0):
    """RGB split + horizontal slice displacement."""
    if amount <= 0.01:
        return img
    rnd = random.Random(int(t * 30) * 7 + seed)
    r, g, b, a = img.split()
    off = int(14 * amount)
    r = ImageChops.offset(r, -off, 0)
    b = ImageChops.offset(b, off, 0)
    ra = ImageChops.offset(a, -off, 0)
    ba = ImageChops.offset(a, off, 0)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    red = Image.merge("RGBA", (r, Image.new("L", img.size, 0), Image.new("L", img.size, 0), ra))
    blu = Image.merge("RGBA", (Image.new("L", img.size, 0), Image.new("L", img.size, 0), b, ba))
    out.alpha_composite(red)
    out = ImageChops.add(out, blu)
    out.alpha_composite(img)
    arr = np.array(out)
    h = arr.shape[0]
    for _ in range(int(4 * amount) + 1):
        y0 = rnd.randint(0, max(1, h - 10))
        y1 = min(h, y0 + rnd.randint(4, max(5, h // 6)))
        arr[y0:y1] = np.roll(arr[y0:y1], rnd.randint(-int(40 * amount), int(40 * amount)), axis=1)
    return Image.fromarray(arr, "RGBA")


def extrude_text(text, size, front, side, depth=14, fpath=F_BLACK, max_w=960, glow=None):
    """Pseudo-3D extruded lettering."""
    base = text_img(text, size, front, fpath, max_w=max_w)
    sidei = text_img(text, size, side, fpath, max_w=max_w)
    im = Image.new("RGBA", (base.width + depth + 10, base.height + depth + 10), (0, 0, 0, 0))
    for k in range(depth, 0, -1):
        im.alpha_composite(sidei, (k, k))
    im.alpha_composite(base, (0, 0))
    if glow:
        g = Image.new("RGBA", im.size, glow + (0,))
        g.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(size * 0.2)).point(lambda v: int(v * 0.8)))
        out = Image.new("RGBA", im.size, (0, 0, 0, 0))
        out.alpha_composite(g)
        out.alpha_composite(im)
        return out
    return im


@lru_cache(maxsize=64)
def emoji(ch, size=140):
    f = ImageFont.truetype(F_EMOJI, 109)
    cw = 160 * max(1, len([c for c in ch if ord(c) > 0x2000 and c not in "\ufe0f\u200d"]))
    im = Image.new("RGBA", (cw + 20, 180), (0, 0, 0, 0))
    ImageDraw.Draw(im).text(((cw + 20) / 2, 90), ch, font=f, embedded_color=True, anchor="mm")
    bb = im.getbbox()
    im = im.crop(bb) if bb else im
    sc = size / max(im.size)
    return im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)


def perspective_card(img, tilt_x=0.0, tilt_y=0.0):
    """Fake 3D tilt of a flat card (keystone)."""
    w, h = img.size
    dx = w * 0.12 * tilt_y
    dy = h * 0.12 * tilt_x
    # quad corners in source for each dest corner (inverse mapping)
    coeffs = _find_coeffs([(0 + dx, 0 + dy), (w - dx, 0 - dy), (w + dx, h + dy), (0 - dx, h - dy)],
                          [(0, 0), (w, 0), (w, h), (0, h)])
    return img.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC)


def _find_coeffs(pa, pb):
    matrix = []
    for p1, p2 in zip(pa, pb):
        matrix.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0] * p1[0], -p2[0] * p1[1]])
        matrix.append([0, 0, 0, p1[0], p1[1], 1, -p2[1] * p1[0], -p2[1] * p1[1]])
    A = np.array(matrix, dtype=np.float64)
    B = np.array(pb, dtype=np.float64).reshape(8)
    res = np.linalg.solve(A, B)
    return res.tolist()
