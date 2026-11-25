"""Characters + props for the ALLTAG KLAR accident video (soft-3D bean look, consistent in every shot)."""
import math
import random
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fuehrerschein"))
import core  # noqa: E402
from core import (BLUE, CHAR, F_BLACK, F_BOLD, F_INTER, MAGENTA, RED, TEAL, WHITE, YELLOW, arm_sprite, aa,  # noqa
                  capsule, clamp01, font, glow_dot, lerp, mixc, paste_c, radial, shaded_capsule, sphere)

ORANGE = (255, 140, 40)
CAR_COL = (70, 110, 170)
CAR_RIM = (150, 210, 255)

# Autofahrer (~40): orange polo, dark hair with grey temples, stubble, a bit chubby
CHAR["auto"] = dict(shirt=(214, 92, 30), rim=ORANGE, hair=(58, 44, 36), skin=(236, 184, 150), beard=False,
                    bald=False, accent=ORANGE)
# Radfahrer (~35): sporty jersey, helmet
CHAR["radler"] = dict(shirt=(16, 160, 150), rim=TEAL, hair=(40, 28, 20), skin=(226, 170, 132), beard=True,
                      bald=False, accent=TEAL)
CHAR["cop2"] = dict(CHAR["cop"])

SHIRT_W = {"auto": 340, "radler": 290, "cop2": 300}


# ------------------------------------------------------------------ heads
@lru_cache(maxsize=256)
def head(who, expr="neutral", inj=0, d=260):
    """expr: neutral angry pain shock tired smug; inj (auto): 0 none, 1 bump+cut, 2 bump+plaster."""
    c = CHAR[who]
    pad = 70
    S = d + pad * 2
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    hw = d if who != "auto" else int(d * 1.06)
    skin = c["skin"]
    ear = sphere(int(d * 0.2), mixc(skin, (200, 120, 100), 0.25), c["rim"], 0.1)
    cx, cy = S / 2, S / 2
    im.alpha_composite(ear, (int(cx - hw / 2 - d * 0.06), int(pad + d * 0.42)))
    im.alpha_composite(ear, (int(cx + hw / 2 - d * 0.14), int(pad + d * 0.42)))
    hd = aa(core.shaded_ellipse(hw, d, skin, c["rim"], spec=0.25))
    im.alpha_composite(hd, (int(cx - hw / 2), pad))
    dr = ImageDraw.Draw(im)
    x0, x1 = cx - hw / 2, cx + hw / 2
    if who == "auto":
        # receding hair: side tufts + thin top, grey temples, stubble
        dr.chord([x0 - 4, pad - 8, x1 + 4, pad + d * 0.5], 195, 345, fill=c["hair"])
        dr.ellipse([cx - d * 0.22, pad + d * 0.02, cx + d * 0.22, pad + d * 0.2], fill=skin)  # Geheimratsecken
        for sx in (-1, 1):
            xa = cx + sx * hw * 0.44
            dr.ellipse([xa - d * 0.045, pad + d * 0.26, xa + d * 0.045, pad + d * 0.42], fill=(120, 112, 106))
        dr.chord([x0 + d * 0.08, pad + d * 0.42, x1 - d * 0.08, pad + d * 1.0], 15, 165, fill=(70, 55, 50, 90))
    elif who == "radler":
        dr.chord([x0 + d * 0.12, pad + d * 0.4, x1 - d * 0.12, pad + d * 1.0], 10, 170, fill=(60, 42, 30, 175))
    # eyes
    ex, ey = d * 0.18, cy - d * 0.02
    brow = mixc(c["hair"], (20, 20, 20), 0.5)
    lw = max(3, int(d * 0.032))
    for sx in (-1, 1):
        x = cx + sx * ex
        if expr == "pain":
            dr.line([(x - d * 0.07, ey - d * 0.05), (x + sx * 0.0 + d * 0.0, ey), (x - d * 0.07 * -1, ey - d * 0.05)],
                    fill=(30, 20, 25), width=lw)
            pts = [(x - sx * d * 0.07, ey - d * 0.06), (x + sx * d * 0.05, ey), (x - sx * d * 0.07, ey + d * 0.06)]
            dr.line(pts, fill=(30, 20, 25), width=lw + 1, joint="curve")
            dr.line([(x - d * 0.09, ey - d * 0.15 - sx * 0), (x + d * 0.09, ey - d * 0.12)][::sx], fill=brow,
                    width=lw)
            continue
        ew, eh = (0.085, 0.105) if expr == "shock" else (0.075, 0.09)
        dr.ellipse([x - d * ew, ey - d * eh, x + d * ew, ey + d * eh], fill=WHITE)
        pr = 0.03 if expr == "shock" else 0.042
        dr.ellipse([x - d * pr + d * 0.008, ey - d * pr, x + d * pr + d * 0.008, ey + d * pr], fill=(25, 25, 35))
        dr.ellipse([x + d * 0.016, ey - d * 0.035, x + d * 0.036, ey - d * 0.015], fill=WHITE)
        if expr == "tired":
            dr.chord([x - d * 0.09, ey - d * 0.12, x + d * 0.09, ey + d * 0.06], 180, 360, fill=skin)
            dr.line([(x - d * 0.085, ey - d * 0.03), (x + d * 0.085, ey - d * 0.03)], fill=(70, 45, 40), width=lw)
        if expr == "smug":
            dr.chord([x - d * 0.09, ey - d * 0.12, x + d * 0.09, ey + d * 0.03], 180, 360, fill=skin)
        # brows
        by = ey - d * 0.14
        if expr == "angry":
            dr.line([(x - sx * d * 0.1, by - d * 0.04), (x + sx * d * 0.07, by + d * 0.03)][::1], fill=brow,
                    width=lw + 2)
        elif expr == "shock":
            dr.arc([x - d * 0.09, by - d * 0.08, x + d * 0.09, by + d * 0.03], 200, 340, fill=brow, width=lw)
        elif expr == "tired":
            dr.line([(x - d * 0.08, by + d * 0.02), (x + d * 0.08, by + d * 0.02)], fill=brow, width=lw)
        else:
            dr.line([(x - d * 0.08, by), (x + d * 0.08, by)], fill=brow, width=lw)
    nose = sphere(int(d * (0.14 if who == "auto" else 0.12)), mixc(skin, (220, 120, 100), 0.35), None, 0.3)
    im.alpha_composite(nose, (int(cx - nose.width / 2), int(cy + d * 0.03)))
    if who == "radler":
        # bike helmet (teal/white, vents) + sunglasses on top
        dr.chord([x0 - 14, pad - 46, x1 + 14, pad + d * 0.56], 180, 360, fill=(240, 244, 248))
        dr.chord([x0 - 14, pad - 46, x1 + 14, pad + d * 0.56], 180, 360, outline=TEAL, width=8)
        for k in range(4):
            vx = x0 + hw * (0.22 + 0.19 * k)
            dr.rounded_rectangle([vx - d * 0.045, pad - d * 0.06, vx + d * 0.045, pad + d * 0.12], radius=10,
                                 fill=(20, 120, 115))
        dr.rectangle([x0 - 14, pad + d * 0.17, x1 + 14, pad + d * 0.22], fill=TEAL)
        for sx in (-1, 1):
            x = cx + sx * d * 0.17
            dr.rounded_rectangle([x - d * 0.12, pad - d * 0.02, x + d * 0.12, pad + d * 0.1], radius=12,
                                 fill=(20, 20, 30), outline=(255, 120, 40), width=3)
        # chin strap
        dr.line([(x0 + d * 0.06, pad + d * 0.45), (cx - d * 0.25, pad + d * 0.92)], fill=(30, 30, 40), width=5)
        dr.line([(x1 - d * 0.06, pad + d * 0.45), (cx + d * 0.25, pad + d * 0.92)], fill=(30, 30, 40), width=5)
    if who == "cop2":
        dr.chord([x0 - 8, pad - 40, x1 + 8, pad + d * 0.5], 180, 360, fill=(22, 36, 90))
        dr.rectangle([x0 - 8, pad + d * 0.16, x1 + 8, pad + d * 0.25], fill=(15, 22, 60))
        dr.ellipse([cx - d * 0.06, pad + d * 0.02, cx + d * 0.06, pad + d * 0.14], fill=YELLOW)
        dr.chord([x0 + d * 0.05, pad + d * 0.18, x1 - d * 0.05, pad + d * 0.38], 0, 180, fill=(10, 14, 36))
        # moustache: the man has seen everything
        dr.rounded_rectangle([cx - d * 0.19, cy + d * 0.15, cx + d * 0.19, cy + d * 0.24], radius=d * 0.05,
                             fill=(70, 50, 40))
    if who == "auto" and inj:
        # forehead bump (upper left) + small cut / plaster
        bx, by = cx - d * 0.12, pad + d * 0.2
        bump = sphere(int(d * 0.2), (225, 110, 110), (255, 160, 160), 0.5)
        paste_c(im, radial(int(d * 0.42), (220, 40, 60), 0.55), bx, by)
        paste_c(im, bump, bx, by)
        if inj == 1:
            dr.line([(bx - d * 0.05, by - d * 0.01), (bx + d * 0.04, by + d * 0.02)], fill=(150, 10, 25),
                    width=max(4, int(d * 0.025)))
            dr.ellipse([bx + d * 0.03, by + d * 0.03, bx + d * 0.05, by + d * 0.07], fill=(170, 10, 30))
        else:
            pl = Image.new("RGBA", (int(d * 0.24), int(d * 0.09)), (0, 0, 0, 0))
            pd = ImageDraw.Draw(pl)
            pd.rounded_rectangle([0, 0, pl.width - 1, pl.height - 1], radius=int(d * 0.03), fill=(242, 205, 170))
            pd.rectangle([pl.width * 0.35, 2, pl.width * 0.65, pl.height - 3], fill=(250, 235, 215))
            paste_c(im, pl, bx, by + d * 0.01, rot=25)
            paste_c(im, pl, bx, by + d * 0.01, rot=-25)
    return im


@lru_cache(maxsize=64)
def torso(who, w=None, h=330):
    c = CHAR[who]
    w = w or SHIRT_W[who]
    im = capsule(w, h, c["shirt"], c["rim"], radius=int(w * 0.38)).copy()
    d = ImageDraw.Draw(im)
    if who == "cop2":
        d.rectangle([w * 0.47, 0, w * 0.53, h], fill=(14, 24, 70))
        d.rounded_rectangle([w * 0.08, h * 0.2, w * 0.44, h * 0.3], radius=6, fill=(20, 30, 80))
        d.text((w * 0.26, h * 0.25), "POLIZEI", font=font(F_BOLD, 15), fill=(220, 230, 255), anchor="mm")
        d.ellipse([w * 0.62, h * 0.18, w * 0.78, h * 0.34], fill=YELLOW)
    elif who == "auto":
        # polo collar + buttons + tiny belly highlight
        d.polygon([(w * 0.32, 0), (w * 0.5, h * 0.13), (w * 0.4, h * 0.17)], fill=(240, 240, 240))
        d.polygon([(w * 0.68, 0), (w * 0.5, h * 0.13), (w * 0.6, h * 0.17)], fill=(240, 240, 240))
        for k in range(2):
            d.ellipse([w * 0.49, h * (0.18 + 0.08 * k), w * 0.51 + 4, h * (0.18 + 0.08 * k) + 8], fill=WHITE)
    elif who == "radler":
        d.rectangle([0, h * 0.34, w, h * 0.44], fill=(255, 210, 30))
        d.line([(w * 0.5, 0), (w * 0.5, h * 0.3)], fill=(230, 255, 250), width=5)
        d.text((w * 0.5, h * 0.62), "PRO", font=font(F_BLACK, 46), fill=(230, 255, 250), anchor="mm")
    return im


@lru_cache(maxsize=1024)
def arm_rot(who, angle_q, sq):
    im = arm_sprite(who)
    if sq != 100:
        im = im.resize((max(1, int(im.width * sq / 100)), max(1, int(im.height * sq / 100))), Image.BICUBIC)
    w, h = im.size
    canvas = Image.new("RGBA", (w, h * 2), (0, 0, 0, 0))
    canvas.alpha_composite(im, (0, h))
    return canvas.rotate(angle_q, resample=Image.BICUBIC, expand=True)


@lru_cache(maxsize=512)
def scaled(kind, who, expr, inj, sq):
    im = head(who, expr, inj) if kind == "head" else torso(who)
    return im.resize((max(1, int(im.width * sq / 100)), max(1, int(im.height * sq / 100))), Image.BICUBIC)


def person(frame, who, cx, cy, s=1.0, arm_l=15, arm_r=-15, mouth=0.0, expr="neutral", inj=0, blink=False,
           tilt=0.0, legs=False, hurt=0.0, point=0, T=0.0, leg_phase=None):
    """cx, cy = neck. Screen-left arm is the character's RIGHT arm.
    hurt>0: left hand (screen right) clutches the right shoulder (screen left), pain glow pulses.
    point: -1/+1 points with an arm toward that screen side."""
    sq = max(10, int(round(s * 50)) * 2)
    sc = sq / 100
    tor = scaled("torso", who, "", 0, sq)
    tw, th = tor.size
    if legs:
        legc = (34, 34, 52) if who != "cop2" else (16, 22, 56)
        for i, sx in enumerate((-1, 1)):
            off = 0
            if leg_phase is not None:
                off = math.sin(leg_phase + i * math.pi) * 40 * sc
            lg = capsule(max(1, int(84 * sc)), max(1, int(250 * sc)), legc, CHAR[who]["rim"])
            paste_c(frame, lg, cx + sx * 62 * sc, cy + th * 0.9 + 110 * sc - abs(off) * 0.3)
            shoe = capsule(max(1, int(124 * sc)), max(1, int(58 * sc)), (24, 24, 28) if who != "radler" else
                           (250, 250, 250), CHAR[who]["rim"])
            paste_c(frame, shoe, cx + sx * 74 * sc, cy + th * 0.9 + 235 * sc - abs(off) * 0.3)
    sh_y = cy + 40 * sc
    if point:
        if point < 0:
            arm_l = 95
        else:
            arm_r = 95
    if hurt:
        arm_l = 4   # hurt right arm hangs limp
        arm_r = -72  # left arm reaches across to the right shoulder
    paste_c(frame, tor, cx, cy + th / 2 - 10 * sc)
    hd = scaled("head", who, expr, inj, sq)
    hx, hy = cx, cy - 110 * sc
    if tilt:
        hd = hd.rotate(tilt, resample=Image.BICUBIC)
    paste_c(frame, hd, hx, hy)
    d = ImageDraw.Draw(frame)
    D = 260 * sc
    mw = D * (0.16 + 0.06 * mouth)
    mh = D * (0.02 + 0.14 * mouth)
    my = hy + D * 0.29
    if expr in ("pain", "angry") and mouth < 0.3:
        # gritted teeth
        d.rounded_rectangle([hx - D * 0.17, my - D * 0.05, hx + D * 0.17, my + D * 0.05], radius=D * 0.03,
                            fill=WHITE, outline=(80, 30, 40), width=max(2, int(D * 0.015)))
        for k in range(1, 5):
            x = hx - D * 0.17 + k * D * 0.068
            d.line([(x, my - D * 0.05), (x, my + D * 0.05)], fill=(150, 120, 120), width=max(1, int(D * 0.008)))
        d.line([(hx - D * 0.17, my), (hx + D * 0.17, my)], fill=(150, 120, 120), width=max(1, int(D * 0.008)))
    elif mouth > 0.08 or expr == "shock":
        m = max(mouth, 0.55 if expr == "shock" else 0)
        mw = D * (0.12 + 0.06 * m)
        mh = D * (0.02 + 0.14 * m)
        d.ellipse([hx - mw, my - mh, hx + mw, my + mh], fill=(70, 20, 30))
        d.ellipse([hx - mw * 0.6, my + mh * 0.2, hx + mw * 0.6, my + mh * 0.95], fill=(230, 90, 100))
    elif expr == "smug":
        d.arc([hx - mw, my - D * 0.1, hx + mw, my + D * 0.05], 10, 120, fill=(90, 30, 40), width=max(3, int(D * 0.025)))
    elif expr == "tired":
        d.line([(hx - mw * 0.8, my), (hx + mw * 0.8, my + D * 0.01)], fill=(90, 30, 40), width=max(3, int(D * 0.025)))
    else:
        d.arc([hx - mw, my - D * 0.08, hx + mw, my + D * 0.06], 20, 160, fill=(90, 30, 40), width=max(3, int(D * 0.025)))
    if blink and expr not in ("pain",):
        for sx in (-1, 1):
            x = hx + sx * D * 0.18
            d.rectangle([x - D * 0.088, hy - D * 0.12, x + D * 0.088, hy + D * 0.08], fill=CHAR[who]["skin"])
            d.line([(x - D * 0.07, hy - D * 0.02), (x + D * 0.07, hy - D * 0.02)], fill=(60, 40, 40),
                   width=max(2, int(D * 0.015)))
    for side, ang in ((-1, arm_l), (1, arm_r)):
        img = arm_rot(who, int(round(side * ang / 3) * 3), sq)
        paste_c(frame, img, cx + side * tw * 0.42, sh_y)
    if hurt:
        px, py = cx - tw * 0.42, sh_y - 5 * sc
        pulse = 0.6 + 0.4 * math.sin(T * 9)
        paste_c(frame, radial(max(4, int(260 * sc)), (255, 40, 60), 0.75 * pulse * hurt, 1.4), px, py)
        # pain sparks
        for k in range(3):
            a = T * 3 + k * 2.1
            r = 120 * sc
            sx_, sy_ = px + math.cos(a) * r, py - 60 * sc + math.sin(a) * r * 0.5
            star(frame, sx_, sy_, 26 * sc, YELLOW)
    return dict(hand_r=(cx + tw * 0.42 + math.sin(math.radians(arm_r)) * 262 * sc,
                        sh_y + math.cos(math.radians(arm_r)) * 262 * sc), head=(hx, hy), D=D)


def star(frame, x, y, r, col):
    d = ImageDraw.Draw(frame)
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    d.polygon(pts, fill=col, outline=(120, 80, 0))


def person_layer(who, s=1.0, size=(900, 1200), **kw):
    """Person rendered on its own transparent layer (for rotation / flying)."""
    L = Image.new("RGBA", size, (0, 0, 0, 0))
    person(L, who, size[0] / 2, size[1] * 0.36, s, **kw)
    return L


# ------------------------------------------------------------------ car
@lru_cache(maxsize=32)
def car_side(w=820, damage=False, facing=1, brake=False, police=False, driver=None):
    h = int(w * 0.42)
    im = Image.new("RGBA", (w + 120, h + 140), (0, 0, 0, 0))
    ox = 60
    col, rim = ((235, 238, 245), (120, 170, 255)) if police else (CAR_COL, CAR_RIM)
    body = capsule(w, int(h * 0.52), col, rim, radius=int(h * 0.2), spec=0.55)
    cab = capsule(int(w * 0.56), int(h * 0.52), mixc(col, (20, 20, 30), 0.25), rim, radius=int(h * 0.22))
    im.alpha_composite(cab, (ox + int(w * 0.2), 34))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([ox + w * 0.24, 54, ox + w * 0.47, 34 + h * 0.44], radius=20, fill=(40, 70, 105))
    d.rounded_rectangle([ox + w * 0.5, 54, ox + w * 0.72, 34 + h * 0.44], radius=20, fill=(40, 70, 105))
    if driver:
        hd = head(driver[0], driver[1], driver[2])
        hd = hd.resize((int(hd.width * h * 0.0021), int(hd.height * h * 0.0021)), Image.BICUBIC)
        clip = Image.new("RGBA", im.size, (0, 0, 0, 0))
        paste_c(clip, hd, ox + w * 0.6, 34 + h * 0.3)
        m = Image.new("L", im.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([ox + w * 0.5, 54, ox + w * 0.72, 34 + h * 0.44], radius=20, fill=255)
        im.paste(clip, (0, 0), Image.fromarray(np.minimum(np.array(m), np.array(clip.getchannel("A")))))
    d.line([(ox + w * 0.29, 62), (ox + w * 0.36, 34 + h * 0.38)], fill=(150, 190, 230), width=8)
    by = int(h * 0.44)
    im.alpha_composite(body, (ox, by))
    d = ImageDraw.Draw(im)
    if police:
        d.rectangle([ox + w * 0.05, by + h * 0.2, ox + w * 0.95, by + h * 0.3], fill=(20, 110, 70))
        d.text((ox + w * 0.5, by + h * 0.14), "POLIZEI", font=font(F_BLACK, int(h * 0.1)), fill=(20, 60, 140),
               anchor="mm")
        d.rounded_rectangle([ox + w * 0.36, 10, ox + w * 0.64, 40], radius=10, fill=(30, 30, 40))
    d.line([(ox + w * 0.47, by + 10), (ox + w * 0.47, by + h * 0.42)], fill=(40, 60, 100), width=4)
    d.rounded_rectangle([ox + w * 0.38, by + h * 0.12, ox + w * 0.44, by + h * 0.16], radius=4, fill=(200, 210, 230))
    d.rounded_rectangle([ox + w * 0.62, by + h * 0.12, ox + w * 0.68, by + h * 0.16], radius=4, fill=(200, 210, 230))
    for fx in (0.18, 0.82):
        wx = ox + w * fx
        whl = sphere(int(h * 0.4), (22, 22, 28), (90, 90, 110), 0.3)
        wy = by + h * 0.52 - whl.height * 0.42
        im.alpha_composite(whl, (int(wx - whl.width / 2), int(wy)))
        r = h * 0.1
        cy = wy + whl.height / 2
        d.ellipse([wx - r, cy - r, wx + r, cy + r], fill=(170, 175, 185))
    # plate + lights
    d.rounded_rectangle([ox + w - 6, by + h * 0.2, ox + w + 10, by + h * 0.32], radius=4, fill=(230, 230, 230))
    paste_c(im, glow_dot(130, (255, 250, 210)), ox + w - 4, by + h * 0.12)
    d.ellipse([ox + w - 26, by + h * 0.06, ox + w + 4, by + h * 0.18], fill=(255, 250, 220))
    paste_c(im, glow_dot(200 if brake else 90, RED), ox + 6, by + h * 0.12)
    d.rounded_rectangle([ox - 4, by + h * 0.06, ox + 18, by + h * 0.2], radius=5, fill=(255, 40, 50) if brake else
                        (150, 20, 30))
    if damage:
        # dent on the front fender/hood + scratches
        dx, dy = ox + w * 0.86, by + h * 0.12
        dent = aa(core.shaded_ellipse(int(w * 0.13), int(h * 0.16), mixc(CAR_COL, (0, 0, 0), 0.35), None,
                                      light=(0.5, 0.6), spec=0.05))
        paste_c(im, dent, dx, dy)
        d = ImageDraw.Draw(im)
        rnd = random.Random(4)
        for k in range(9):
            x0 = ox + w * rnd.uniform(0.62, 0.9)
            y0 = by + h * rnd.uniform(0.04, 0.3)
            d.line([(x0, y0), (x0 + rnd.uniform(40, 110), y0 + rnd.uniform(-12, 14))], fill=(225, 232, 240),
                   width=rnd.choice([2, 3, 4]))
    if facing < 0:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im


# ------------------------------------------------------------------ bicycle
def wheel_pts(cx, cy, R, spin, buckle=0.0, yaw=0.0, n=72):
    """3D rim projected: buckle = lateral 'Achter' wobble amplitude (px), yaw = view angle (rad)."""
    pts = []
    for k in range(n + 1):
        th = k / n * math.tau
        x = R * math.cos(th + spin)
        y = R * math.sin(th + spin)
        z = buckle * (math.sin(2 * th + 0.6) + 0.35 * math.sin(3 * th))
        X = x * math.cos(yaw) + z * math.sin(yaw)
        pts.append((cx + X, cy + y))
    return pts


def draw_wheel(d, cx, cy, R, spin, buckle=0.0, yaw=0.0, col=(30, 30, 36), spoke=(200, 205, 215), w=14):
    rim = wheel_pts(cx, cy, R, spin, buckle, yaw)
    tire = wheel_pts(cx, cy, R + w * 0.6, spin, buckle, yaw)
    d.line(tire, fill=col, width=int(w * 1.4), joint="curve")
    d.line(rim, fill=(190, 195, 205), width=max(3, int(w * 0.35)), joint="curve")
    n = len(rim) - 1
    for k in range(0, n, n // 16):
        d.line([(cx, cy), rim[k]], fill=spoke, width=max(1, int(w * 0.14)))
    d.ellipse([cx - w * 0.6, cy - w * 0.6, cx + w * 0.6, cy + w * 0.6], fill=(150, 155, 165))


def bike(frame, cx, cy, s=1.0, spin=0.0, buckle=0.0, lying=False, crank=0.0):
    """Side view bike, cx/cy = bottom bracket. Draw on a layer, optionally rotated (lying on the ground)."""
    S = 1000
    L = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    R = 190
    bb = (S / 2, S / 2 + 60)
    rw = (bb[0] - 300, bb[1] + 20)
    fw = (bb[0] + 310, bb[1] + 20)
    seat = (bb[0] - 70, bb[1] - 290)
    head_t = (bb[0] + 230, bb[1] - 260)
    draw_wheel(d, *rw, R, spin, 0)
    draw_wheel(d, *fw, R, spin * 1.0, buckle, yaw=0.0 if buckle == 0 else 0.0)
    fc = (255, 70, 60)
    for a, b in ((rw, bb), (rw, seat), (bb, seat), (bb, head_t), (seat, (head_t[0] - 10, head_t[1] + 20)),
                 (head_t, fw)):
        d.line([a, b], fill=fc, width=22)
    d.line([seat, (seat[0] - 15, seat[1] - 50)], fill=(60, 60, 70), width=16)
    d.rounded_rectangle([seat[0] - 80, seat[1] - 74, seat[0] + 50, seat[1] - 44], radius=14, fill=(25, 25, 30))
    d.line([head_t, (head_t[0] - 20, head_t[1] - 80)], fill=(60, 60, 70), width=16)
    d.line([(head_t[0] - 60, head_t[1] - 90), (head_t[0] + 40, head_t[1] - 80)], fill=(30, 30, 34), width=20)
    # crank + pedals
    for k in (0, math.pi):
        px, py = bb[0] + math.cos(crank + k) * 80, bb[1] + math.sin(crank + k) * 80
        d.line([bb, (px, py)], fill=(170, 170, 180), width=12)
        d.rounded_rectangle([px - 28, py - 8, px + 28, py + 8], radius=4, fill=(30, 30, 34))
    d.ellipse([bb[0] - 36, bb[1] - 36, bb[0] + 36, bb[1] + 36], outline=(170, 170, 180), width=8)
    if lying:
        L = L.rotate(-12, resample=Image.BICUBIC)
    paste_c(frame, L, cx, cy - 60 * s, s)
    return L


def wheel_closeup(frame, cx, cy, R, T, buckle=1.0):
    """3/4 view spinning front wheel with a clearly visible 'Achter' that wobbles while spinning."""
    spin = T * 5.0
    yaw = 0.95  # strongly angled view so the lateral buckle reads as a wobbling figure-8
    L = Image.new("RGBA", (int(R * 3), int(R * 3)), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    c = L.width / 2
    B = R * 0.26 * buckle
    # rim visible as ellipse whose shape changes with spin -> "eiern"
    rim = []
    tire = []
    for k in range(121):
        th = k / 120 * math.tau
        z = B * (math.sin(2 * (th - spin) + 0.4) + 0.3 * math.sin(3 * (th - spin)))
        x = R * math.cos(th)
        y = R * math.sin(th)
        X = x * math.cos(yaw) + z * math.sin(yaw)
        rim.append((c + X, c + y))
        Xt = (R * 1.08) * math.cos(th) * math.cos(yaw) + z * math.sin(yaw)
        tire.append((c + Xt, c + y * 1.08))
    d.line(tire, fill=(26, 26, 32), width=int(R * 0.14), joint="curve")
    d.line(rim, fill=(205, 210, 222), width=int(R * 0.05), joint="curve")
    for k in range(0, 120, 6):
        d.line([(c, c), rim[k]], fill=(190, 195, 205), width=max(2, int(R * 0.012)))
    d.ellipse([c - R * 0.08, c - R * 0.08, c + R * 0.08, c + R * 0.08], fill=(140, 145, 155))
    # fork
    d.line([(c, c), (c - R * 0.15, c - R * 1.45)], fill=(255, 70, 60), width=int(R * 0.07))
    paste_c(frame, L, cx, cy)


# ------------------------------------------------------------------ phone
@lru_cache(maxsize=4)
def phone_broken(w=420):
    h = int(w * 2.05)
    im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    im.alpha_composite(capsule(w, h, (30, 30, 36), (160, 170, 200), radius=int(w * 0.14), spec=0.5), (20, 20))
    d = ImageDraw.Draw(im)
    sx0, sy0, sx1, sy1 = 20 + w * 0.06, 20 + w * 0.08, 20 + w * 0.94, 20 + h - w * 0.08
    d.rounded_rectangle([sx0, sy0, sx1, sy1], radius=int(w * 0.09), fill=(30, 60, 120))
    # glitchy screen colours
    rnd = random.Random(9)
    for k in range(14):
        y = rnd.uniform(sy0, sy1)
        d.rectangle([sx0, y, sx1, y + rnd.uniform(6, 30)],
                    fill=rnd.choice([(255, 40, 190), (0, 240, 220), (255, 220, 40), (20, 20, 30)]))
    # spider-web cracks
    ix, iy = sx0 + (sx1 - sx0) * 0.62, sy0 + (sy1 - sy0) * 0.36
    for k in range(13):
        a = k / 13 * math.tau + rnd.uniform(-0.2, 0.2)
        pts = [(ix, iy)]
        r = 0
        x, y = ix, iy
        while r < h:
            r += rnd.uniform(40, 90)
            a += rnd.uniform(-0.3, 0.3)
            x, y = ix + math.cos(a) * r, iy + math.sin(a) * r
            pts.append((x, y))
        d.line(pts, fill=(240, 245, 255), width=3)
    for ring in (40, 95, 170):
        pts = []
        for k in range(14):
            a = k / 13 * math.tau
            rr = ring * rnd.uniform(0.8, 1.2)
            pts.append((ix + math.cos(a) * rr, iy + math.sin(a) * rr * 1.1))
        d.line(pts, fill=(230, 235, 250), width=2)
    d.ellipse([ix - 16, iy - 16, ix + 16, iy + 16], fill=(250, 250, 255))
    # clip cracks to the screen
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([sx0, sy0, sx1, sy1], radius=int(w * 0.09), fill=255)
    body = Image.new("RGBA", im.size, (0, 0, 0, 0))
    body.alpha_composite(capsule(w, h, (30, 30, 36), (160, 170, 200), radius=int(w * 0.14), spec=0.5), (20, 20))
    body.paste(im, (0, 0), mask)
    return body
