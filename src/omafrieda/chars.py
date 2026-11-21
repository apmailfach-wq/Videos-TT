"""Figuren im weichen 3D-Cartoon-Look: Oma Frieda Faust, Taschendieb, Typ im Bus, Muskeltypen,
junge Frieda (Judo), Passanten, Tauben + Requisiten. Alle Sprites werden gecacht."""
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from gfx import (F_BLACK, F_INTER, WHITE, darker, ell, font, glow, inflate, limb, limb3, lerp, mixc, poly,
                 rrect, shape_mask, soft_shadow)

# ------------------------------------------------------------------ Figuren-Definitionen
CFG = {
    "oma": dict(skin=(250, 211, 186), hair="oma", eye=(60, 135, 225), glasses=True, old=True, female=True,
                brow=(206, 206, 216), body="oma", lash=True),
    "young": dict(skin=(246, 206, 178), hair="curly_dark", eye=(60, 135, 225), glasses=False, old=False,
                  female=True, brow=(70, 45, 35), body="judo", lash=True),
    "thief": dict(skin=(236, 192, 160), hair="hood", eye=(110, 72, 40), glasses=False, old=False, female=False,
                  brow=(60, 42, 30), body="thief", stubble=True),
    "thief2": dict(skin=(228, 184, 152), hair="beanie", eye=(70, 110, 60), glasses=False, old=False, female=False,
                   brow=(70, 50, 35), body="thief2", stubble=True),
    "jung": dict(skin=(242, 200, 170), hair="cap", eye=(90, 120, 70), glasses=False, old=False, female=False,
                 brow=(90, 60, 35), body="jung"),
    "musk1": dict(skin=(232, 176, 132), hair="flattop", eye=(70, 120, 200), glasses=False, old=False, female=False,
                  brow=(200, 160, 70), body="musk1"),
    "musk2": dict(skin=(178, 118, 82), hair="buzz", eye=(60, 40, 25), glasses=False, old=False, female=False,
                  brow=(30, 22, 18), body="musk2", beard=True),
    "pass1": dict(skin=(244, 204, 176), hair="bob", eye=(70, 110, 60), glasses=False, old=False, female=True,
                  brow=(110, 60, 30), body="pass1", lash=True),
    "pass2": dict(skin=(205, 150, 110), hair="bald", eye=(60, 40, 25), glasses=False, old=True, female=False,
                  brow=(80, 80, 80), body="pass2"),
    # Kinder (Folge 2: Schule)
    "rowdy": dict(skin=(242, 198, 168), hair="spiky", eye=(70, 110, 60), glasses=False, old=False, female=False,
                  brow=(140, 70, 35), body="rowdy"),
    "kleiner": dict(skin=(250, 214, 190), hair="bowl", eye=(60, 135, 225), glasses=False, old=False, female=False,
                    brow=(200, 160, 80), body="kleiner"),
    "girl": dict(skin=(236, 190, 160), hair="pigtails", eye=(110, 72, 40), glasses=False, old=False, female=True,
                 brow=(90, 55, 30), body="girl", lash=True),
    "bully2": dict(skin=(232, 190, 160), hair="cap", eye=(80, 60, 40), glasses=False, old=False, female=False,
                   brow=(70, 50, 30), body="bully2"),
    "gamer": dict(skin=(190, 130, 95), hair="curly_dark", eye=(60, 40, 25), glasses=False, old=False, female=False,
                  brow=(40, 28, 20), body="gamer"),
}

HAIR_WHITE = (246, 245, 252)
GOLD = (222, 172, 58)
LIP = (150, 60, 70)
MOUTH_IN = (95, 28, 40)


# ------------------------------------------------------------------ Auge
@lru_cache(maxsize=512)
def eye_sprite(D, iris, lid_top, lid_ang, lid_bot, lookx, looky, side, skin, wide=1.0, lash=False, pupil=1.0):
    rx, ry = D * 0.098 * wide, D * 0.118 * wide
    pad = int(D * 0.06)
    w, h = int(rx * 2 + pad * 2), int(ry * 2 + pad * 2)
    cx, cy = w / 2, h / 2
    ss = 3
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    S = lambda v: v * ss  # noqa
    d.ellipse([S(cx - rx), S(cy - ry), S(cx + rx), S(cy + ry)], fill=(252, 252, 255))
    # leichte Schattierung oben im Augenweiß
    d.ellipse([S(cx - rx), S(cy - ry), S(cx + rx), S(cy - ry * 0.2)], fill=(225, 228, 238))
    d.ellipse([S(cx - rx * 0.97), S(cy - ry * 0.75), S(cx + rx * 0.97), S(cy + ry * 0.97)], fill=(252, 252, 255))
    ir = D * 0.072 * min(1.0, wide)
    ix, iy = cx + lookx * rx * 0.42, cy + looky * ry * 0.35
    d.ellipse([S(ix - ir), S(iy - ir), S(ix + ir), S(iy + ir)], fill=darker(iris, 0.55))
    d.ellipse([S(ix - ir * 0.86), S(iy - ir * 0.86), S(ix + ir * 0.86), S(iy + ir * 0.86)], fill=iris)
    d.ellipse([S(ix - ir * 0.6), S(iy - ir * 0.1), S(ix + ir * 0.75), S(iy + ir * 0.85)],
              fill=mixc(iris, (255, 255, 255), 0.35))
    pr = ir * 0.48 * pupil
    d.ellipse([S(ix - pr), S(iy - pr), S(ix + pr), S(iy + pr)], fill=(14, 14, 22))
    hr = ir * 0.3
    d.ellipse([S(ix - ir * 0.5 - hr), S(iy - ir * 0.5 - hr), S(ix - ir * 0.5 + hr), S(iy - ir * 0.5 + hr)],
              fill=(255, 255, 255))
    d.ellipse([S(ix + ir * 0.35), S(iy + ir * 0.3), S(ix + ir * 0.55), S(iy + ir * 0.5)], fill=(255, 255, 255))
    eye_mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(eye_mask).ellipse([S(cx - rx), S(cy - ry), S(cx + rx), S(cy + ry)], fill=255)
    # Lider
    lid = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(lid)
    lidc = mixc(skin, (200, 140, 120), 0.18)
    top_y = cy - ry + 2 * ry * lid_top
    ang = math.radians(lid_ang) * side
    dx = rx * 1.4
    if lid_top > 0.01:
        p1 = (cx - dx, top_y + math.tan(ang) * -dx)
        p2 = (cx + dx, top_y + math.tan(ang) * dx)
        ld.polygon([(S(cx - dx), 0), (S(cx + dx), 0), (S(p2[0]), S(p2[1])), (S(p1[0]), S(p1[1]))], fill=lidc)
        ld.line([(S(p1[0]), S(p1[1])), (S(p2[0]), S(p2[1]))], fill=(70, 40, 40), width=int(S(D * 0.016)))
    else:
        top_y = None
    if lid_bot > 0.01:
        by = cy + ry - 2 * ry * lid_bot
        ld.ellipse([S(cx - rx * 1.4), S(by), S(cx + rx * 1.4), S(by + ry * 2.4)], fill=lidc)
    lid.putalpha(ImageChops_mul(lid.getchannel("A"), eye_mask))
    im.alpha_composite(lid)
    od = ImageDraw.Draw(im)
    # Oberlidlinie / Wimpern
    if lid_top <= 0.01:
        od.arc([S(cx - rx), S(cy - ry), S(cx + rx), S(cy + ry)], 200, 340, fill=(60, 35, 35),
               width=int(S(D * 0.016)))
    if lash:
        for k in (-1, 0):
            a = math.radians(205 + 25 * (k + 1)) if side < 0 else math.radians(335 - 25 * (k + 1))
            ex, ey = cx + rx * math.cos(a), cy + ry * math.sin(a)
            if top_y is not None:
                ey = max(ey, top_y)
            od.line([(S(ex), S(ey)), (S(ex + side * D * 0.03 * (1 if side > 0 else 1)), S(ey - D * 0.025))],
                    fill=(60, 35, 35), width=int(S(D * 0.012)))
    im = im.resize((w, h), Image.LANCZOS)
    return im


def ImageChops_mul(a, b):
    return Image.fromarray((np.asarray(a, np.uint16) * np.asarray(b, np.uint16) // 255).astype(np.uint8), "L")


# ------------------------------------------------------------------ Kopf
EXPR = {
    #          lid_top lid_ang lid_bot  brow_y brow_ang wide
    "neutral": (0.12, 0, 0.05, 0.0, 0, 1.0),
    "smile":   (0.22, -6, 0.28, -0.01, -6, 1.0),
    "warm":    (0.3, -8, 0.35, 0.0, -8, 1.0),
    "glare":   (0.46, 14, 0.12, 0.05, 20, 1.0),
    "smirk":   (0.24, 6, 0.15, 0.0, 10, 1.0),
    "shock":   (0.0, 0, 0.0, -0.08, -10, 1.15),
    "arrogant": (0.42, -4, 0.05, -0.02, -6, 1.0),
    "scared":  (0.0, 0, 0.0, -0.06, -22, 1.1),
    "strain":  (0.5, 18, 0.3, 0.05, 24, 1.0),
    "sneaky":  (0.4, 10, 0.1, 0.03, 16, 1.0),
    "laugh":   (0.62, -10, 0.45, -0.04, -10, 1.0),
    "proud":   (0.2, 0, 0.12, -0.02, 0, 1.0),
    "sad":     (0.3, -16, 0.1, -0.02, -22, 1.0),
}


@lru_cache(maxsize=300)
def head(who, D, expr="neutral", mouth=0.0, blink=False, look=(0.0, 0.0), gl=0.07, brow_up=0, mouth_kind=None,
         sweat=False, wet=False):
    """Kopf-Sprite. Rückgabe: Bild, Kopfmitte (Pixel). D = Kopfdurchmesser."""
    c = CFG[who]
    skin = c["skin"]
    S = int(D * 1.9)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cx, cy = S / 2, S * 0.53
    hs = c["hair"]
    rx, ry = D * 0.49, D * 0.52
    # ---- Haare hinten
    if hs == "oma":
        HG = (226, 226, 230)
        # Dutt oben am Hinterkopf
        ell(im, cx + D * 0.02, cy - D * 0.66, D * 0.21, D * 0.18, HG, amb=0.62, spec=0.18, ambc=(0.95, 0.95, 1.0))
        # Volumen hinten/seitlich (glatt, nach hinten gekämmt)
        ell(im, cx, cy - D * 0.1, D * 0.56, D * 0.55, HG, amb=0.6, spec=0.12, ambc=(0.95, 0.95, 1.0))
    elif hs == "curly_dark":
        for k in range(15):
            a = math.radians(160 + k * (220 / 14))
            x, y = cx + math.cos(a) * D * 0.5, cy - D * 0.08 + math.sin(a) * D * 0.48
            ell(im, x, y, D * 0.17, D * 0.16, (70, 45, 32), amb=0.5, spec=0.15)
    elif hs == "hood":
        ell(im, cx, cy - D * 0.06, D * 0.68, D * 0.7, (72, 74, 84), amb=0.45, spec=0.08)
    elif hs == "bob":
        poly(im, [(cx - D * 0.58, cy + D * 0.35), (cx - D * 0.55, cy - D * 0.3), (cx, cy - D * 0.62),
                  (cx + D * 0.55, cy - D * 0.3), (cx + D * 0.58, cy + D * 0.35)], (120, 66, 34), radius=D * 0.15,
             amb=0.45)
    # ---- Ohren
    if hs not in ("hood",):
        for sx in (-1, 1):
            ell(im, cx + sx * rx * 0.98, cy + D * 0.06, D * 0.085, D * 0.12, mixc(skin, (230, 140, 120), 0.15),
                amb=0.5)
    # ---- Gesicht
    face_ry = ry
    if c.get("body", "").startswith("musk"):
        # kantiges Kinn
        poly(im, [(cx - rx, cy - ry * 0.3), (cx - rx * 0.98, cy + ry * 0.45), (cx - rx * 0.6, cy + ry * 0.98),
                  (cx + rx * 0.6, cy + ry * 0.98), (cx + rx * 0.98, cy + ry * 0.45), (cx + rx, cy - ry * 0.3),
                  (cx + rx * 0.7, cy - ry * 0.95), (cx - rx * 0.7, cy - ry * 0.95)], skin, radius=D * 0.2,
             amb=0.48, spec=0.12)
    else:
        ell(im, cx, cy, rx, face_ry, skin, amb=0.5, spec=0.12, radius=D * 0.3)
    d = ImageDraw.Draw(im)
    # Wangen
    for sx in (-1, 1):
        g = glow(int(D * 0.34), (255, 120, 130), 1.6, 0.55 if c["old"] or c["female"] else 0.25)
        im.alpha_composite(g, (int(cx + sx * D * 0.27 - g.width / 2), int(cy + D * 0.17 - g.height / 2)))
    if c.get("stubble"):
        st = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(st).chord([cx - rx * 0.85, cy - ry * 0.2, cx + rx * 0.85, cy + ry * 0.98], 15, 165,
                                 fill=(90, 70, 60, 70))
        im.alpha_composite(st)
    if c.get("beard"):
        poly(im, [(cx - rx * 0.95, cy + ry * 0.05), (cx - rx * 0.6, cy + ry * 1.12), (cx, cy + ry * 1.22),
                  (cx + rx * 0.6, cy + ry * 1.12), (cx + rx * 0.95, cy + ry * 0.05), (cx + rx * 0.5, cy + ry * 0.45),
                  (cx - rx * 0.5, cy + ry * 0.45)], (34, 24, 20), radius=D * 0.08, amb=0.5)
    # ---- Augen
    lt, la, lb, by, ba, wide = EXPR[expr]
    if blink:
        lt, lb = 0.98, 0.0
    ex, ey = D * 0.205, cy + D * 0.03
    for sx in (-1, 1):
        lt2 = lt
        if expr == "smirk" and sx < 0:
            lt2 = 0.08
        e = eye_sprite(int(D), c["eye"], round(lt2, 2), la, lb, round(look[0], 2), round(look[1], 2), sx, skin,
                       wide, c.get("lash", False), 0.8 if expr in ("shock", "scared") else 1.0)
        im.alpha_composite(e, (int(cx + sx * ex - e.width / 2), int(ey - e.height / 2)))
    # Lachfältchen
    if c["old"]:
        for sx in (-1, 1):
            x0 = cx + sx * (ex + D * 0.12)
            for k in range(3):
                yy = ey - D * 0.03 + k * D * 0.035
                d.line([(x0, yy), (x0 + sx * D * 0.05, yy + (k - 1) * D * 0.02)], fill=(215, 150, 130),
                       width=max(2, int(D * 0.009)))
        # Stirnfalten
        for k in range(2):
            yy = cy - D * 0.27 - k * D * 0.045
            d.arc([cx - D * 0.17, yy - D * 0.03, cx + D * 0.17, yy + D * 0.05], 200, 340, fill=(228, 170, 150),
                  width=max(2, int(D * 0.008)))
    # ---- Augenbrauen
    bw = max(3, int(D * 0.05))
    for sx in (-1, 1):
        bx = cx + sx * ex
        byy = ey - D * 0.15 + by * D
        ang = ba
        raise_ = 0
        if expr == "smirk" and sx < 0:
            raise_ = -D * 0.07
            ang = -14
        if brow_up and sx == brow_up:
            raise_ = -D * 0.08
            ang = -14
        tilt = math.tan(math.radians(ang)) * D * 0.08
        p_in = (bx - sx * D * 0.075, byy + raise_ + tilt)
        p_out = (bx + sx * D * 0.08, byy + raise_ - tilt * 0.4)
        p_mid = (bx + sx * D * 0.005, byy + raise_ - D * 0.03)
        d.line([p_in, p_mid, p_out], fill=c["brow"], width=bw, joint="curve")
        for p in (p_in, p_out):
            d.ellipse([p[0] - bw / 2, p[1] - bw / 2, p[0] + bw / 2, p[1] + bw / 2], fill=c["brow"])
        if hs == "oma":
            d.line([p_in, p_mid, p_out], fill=(180, 180, 195), width=max(1, bw // 4))
    # ---- Nase
    ell(im, cx, cy + D * 0.15, D * 0.075, D * 0.062, mixc(skin, (235, 130, 120), 0.28), amb=0.5, spec=0.3)
    # ---- Mund
    my = cy + D * 0.3
    kind = mouth_kind
    if kind is None:
        kind = {"smile": "smile", "warm": "smile", "smirk": "smirk", "glare": "flat", "shock": "o", "laugh": "grin",
                "arrogant": "smirk", "scared": "wavy", "strain": "teeth", "sneaky": "smirk", "proud": "smile",
                "sad": "frown"}.get(expr, "smile")
    lw = max(3, int(D * 0.022))
    if mouth > 0.06 or kind in ("o", "grin", "teeth"):
        mo = max(mouth, 0.5 if kind in ("grin", "teeth") else 0.0)
        mw = D * (0.11 + 0.05 * mo) * (1.35 if kind == "grin" else 1)
        mh = D * (0.03 + 0.11 * mo)
        if kind == "o":
            mw, mh = D * 0.09, D * (0.13 + 0.12 * mouth)
            my2 = my + D * 0.04
        else:
            my2 = my
        if kind == "teeth":
            d.rounded_rectangle([cx - D * 0.14, my - D * 0.045, cx + D * 0.14, my + D * 0.045], radius=D * 0.03,
                                fill=(250, 250, 250), outline=MOUTH_IN, width=lw)
            d.line([(cx - D * 0.13, my), (cx + D * 0.13, my)], fill=(200, 200, 205), width=max(1, lw // 2))
        else:
            if kind == "grin":
                d.chord([cx - mw, my2 - mh * 0.7, cx + mw, my2 + mh * 1.3], 0, 180, fill=MOUTH_IN)
                d.chord([cx - mw * 0.8, my2 - mh * 0.7 + 1, cx + mw * 0.8, my2 + mh * 0.25], 0, 180,
                        fill=(250, 250, 250))
                d.ellipse([cx - mw * 0.5, my2 + mh * 0.5, cx + mw * 0.5, my2 + mh * 1.25], fill=(225, 95, 105))
            else:
                d.ellipse([cx - mw, my2 - mh, cx + mw, my2 + mh], fill=MOUTH_IN)
                if mh > D * 0.05:
                    d.chord([cx - mw * 0.8, my2 - mh, cx + mw * 0.8, my2 - mh * 0.35], 0, 180,
                            fill=(250, 250, 250))
                    d.ellipse([cx - mw * 0.55, my2 + mh * 0.15, cx + mw * 0.55, my2 + mh * 0.95],
                              fill=(225, 95, 105))
    else:
        if kind == "smile":
            d.arc([cx - D * 0.13, my - D * 0.1, cx + D * 0.13, my + D * 0.05], 25, 155, fill=LIP, width=lw)
        elif kind == "smirk":
            d.line([(cx - D * 0.1, my + D * 0.02), (cx + D * 0.03, my + D * 0.02), (cx + D * 0.12, my - D * 0.03)],
                   fill=LIP, width=lw, joint="curve")
        elif kind == "flat":
            d.line([(cx - D * 0.08, my), (cx + D * 0.08, my)], fill=LIP, width=lw)
        elif kind == "frown":
            d.arc([cx - D * 0.1, my, cx + D * 0.1, my + D * 0.12], 205, 335, fill=LIP, width=lw)
        elif kind == "wavy":
            pts = [(cx - D * 0.12 + k * D * 0.04, my + (D * 0.015 if k % 2 else -D * 0.015)) for k in range(7)]
            d.line(pts, fill=LIP, width=lw, joint="curve")
    # ---- Brille (Oma)
    if c["glasses"]:
        gr = D * 0.13
        gy = ey + gl * D
        gw = max(2, int(D * 0.011))
        lens = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ldr = ImageDraw.Draw(lens)
        for sx in (-1, 1):
            gx = cx + sx * ex
            ldr.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], fill=(235, 245, 255, 38))
            ldr.line([(gx - gr * 0.55, gy - gr * 0.1), (gx - gr * 0.1, gy - gr * 0.55)], fill=(255, 255, 255, 150),
                     width=max(2, int(D * 0.018)))
        im.alpha_composite(lens)
        for sx in (-1, 1):
            gx = cx + sx * ex
            d.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], outline=(70, 55, 40), width=gw + 1)
            d.ellipse([gx - gr + 1, gy - gr + 1, gx + gr - 1, gy + gr - 1], outline=(176, 140, 72), width=max(1, gw - 1))
            d.arc([gx - gr + 2, gy - gr + 2, gx + gr - 2, gy + gr - 2], 200, 260, fill=(255, 235, 160),
                  width=max(1, gw // 2))
            d.line([(gx + sx * gr, gy - gr * 0.2), (cx + sx * rx * 0.98, ey - D * 0.02)], fill=(120, 95, 55), width=gw)
        d.arc([cx - ex + gr * 0.9, gy - gr * 0.5, cx + ex - gr * 0.9, gy + gr * 0.3], 200, 340, fill=(120, 95, 55),
              width=gw)
    # ---- Haare vorne
    if hs == "oma":
        HG = (232, 232, 236)
        poly(im, [(cx - rx * 1.06, cy - ry * 0.02), (cx - rx * 1.0, cy - ry * 0.62), (cx - rx * 0.55, cy - ry * 1.0),
                  (cx, cy - ry * 1.1), (cx + rx * 0.55, cy - ry * 1.0), (cx + rx * 1.0, cy - ry * 0.62),
                  (cx + rx * 1.06, cy - ry * 0.02), (cx + rx * 0.8, cy - ry * 0.3), (cx + rx * 0.4, cy - ry * 0.6),
                  (cx, cy - ry * 0.66), (cx - rx * 0.4, cy - ry * 0.6), (cx - rx * 0.8, cy - ry * 0.3)],
             HG, radius=D * 0.1, amb=0.62, spec=0.2, ambc=(0.95, 0.95, 1.0))
        hd = ImageDraw.Draw(im)
        for k in range(-5, 6):
            x0 = cx + k * D * 0.075
            hd.line([(x0, cy - ry * 0.64 + abs(k) * D * 0.02), (cx + k * D * 0.035, cy - ry * 1.05)],
                    fill=(185, 185, 195), width=max(1, int(D * 0.008)))
        # ein paar lose Strähnen
        for sx in (-1, 1):
            hd.arc([cx + sx * rx * 0.95 - D * 0.08, cy - D * 0.1, cx + sx * rx * 0.95 + D * 0.08, cy + D * 0.2],
                   90 if sx < 0 else 270, 270 if sx < 0 else 90, fill=(215, 215, 222), width=max(1, int(D * 0.01)))
    elif hs == "curly_dark":
        for k, xf in enumerate([-0.34, -0.2, -0.06, 0.08, 0.22, 0.36]):
            ell(im, cx + xf * D, cy + (-0.42 + abs(xf) * 0.3) * D, D * 0.11, D * 0.1, (70, 45, 32), amb=0.5)
    elif hs == "hood":
        ring = Image.new("RGBA", im.size, (0, 0, 0, 0))
        m = shape_mask(S, S, lambda dd, s: (dd.ellipse([(cx - rx * 1.22) * s, (cy - ry * 1.22) * s,
                                                         (cx + rx * 1.22) * s, (cy + ry * 1.15) * s], fill=255),
                                            dd.ellipse([(cx - rx * 0.97) * s, (cy - ry * 0.97) * s,
                                                        (cx + rx * 0.97) * s, (cy + ry * 1.3) * s], fill=0)))
        ring = Image.fromarray(inflate(m, (82, 84, 96), D * 0.06, amb=0.45, spec=0.1), "RGBA")
        im.alpha_composite(ring)
        # Haarsträhnen unter der Kapuze
        for xf in (-0.25, -0.1, 0.05, 0.2):
            d.polygon([(cx + xf * D, cy - ry * 0.95), (cx + (xf + 0.12) * D, cy - ry * 0.95),
                       (cx + (xf + 0.04) * D, cy - ry * 0.68)], fill=(60, 40, 30))
    elif hs == "cap":
        poly(im, [(cx - rx * 1.0, cy - ry * 0.2), (cx - rx * 0.9, cy - ry * 0.75), (cx, cy - ry * 1.12),
                  (cx + rx * 0.9, cy - ry * 0.75), (cx + rx * 1.0, cy - ry * 0.2), (cx, cy - ry * 0.55)],
             (110, 70, 40), radius=D * 0.1, amb=0.45)
        blob_cap = [(cx - rx * 1.02, cy - ry * 0.45), (cx - rx * 0.85, cy - ry * 1.0), (cx, cy - ry * 1.25),
                    (cx + rx * 0.85, cy - ry * 1.0), (cx + rx * 1.02, cy - ry * 0.45)]
        poly(im, blob_cap, (220, 50, 60), radius=D * 0.14, amb=0.45, spec=0.2)
        rrect(im, cx - rx * 0.35, cy - ry * 0.62, cx + rx * 0.35, cy - ry * 0.42, D * 0.05, (230, 230, 235),
              amb=0.6)
        # Kopfhörer
        d.arc([cx - rx * 1.12, cy - ry * 1.3, cx + rx * 1.12, cy + ry * 0.6], 185, 355, fill=(30, 30, 36),
              width=int(D * 0.08))
        for sx in (-1, 1):
            rrect(im, cx + sx * rx * 1.05 - D * 0.1, cy - D * 0.12, cx + sx * rx * 1.05 + D * 0.1, cy + D * 0.2,
                  D * 0.08, (40, 40, 48), amb=0.4, spec=0.35)
            ell(im, cx + sx * rx * 1.1, cy + D * 0.04, D * 0.06, D * 0.1, (240, 70, 80), amb=0.5, spec=0.3)
    elif hs == "beanie":
        poly(im, [(cx - rx * 1.04, cy - ry * 0.3), (cx - rx * 0.95, cy - ry * 0.85), (cx - rx * 0.45, cy - ry * 1.22),
                  (cx, cy - ry * 1.3), (cx + rx * 0.45, cy - ry * 1.22), (cx + rx * 0.95, cy - ry * 0.85),
                  (cx + rx * 1.04, cy - ry * 0.3)], (214, 52, 64), radius=D * 0.12, amb=0.45, spec=0.15)
        rrect(im, cx - rx * 1.06, cy - ry * 0.55, cx + rx * 1.06, cy - ry * 0.28, D * 0.06, (190, 40, 52), amb=0.45,
              spec=0.1)
        bd = ImageDraw.Draw(im)
        for k in range(-6, 7):
            x0 = cx + k * D * 0.07
            bd.line([(x0, cy - ry * 0.54), (x0, cy - ry * 0.3)], fill=(160, 30, 42), width=max(1, int(D * 0.01)))
        ell(im, cx, cy - ry * 1.32, D * 0.1, D * 0.09, (245, 245, 245), amb=0.6)
    elif hs == "flattop":
        rrect(im, cx - rx * 0.92, cy - ry * 1.32, cx + rx * 0.92, cy - ry * 0.55, D * 0.08, (245, 210, 100),
              amb=0.5, spec=0.2)
    elif hs == "buzz":
        poly(im, [(cx - rx * 0.98, cy - ry * 0.3), (cx - rx * 0.8, cy - ry * 0.85), (cx, cy - ry * 1.05),
                  (cx + rx * 0.8, cy - ry * 0.85), (cx + rx * 0.98, cy - ry * 0.3), (cx, cy - ry * 0.7)],
             (36, 28, 24), radius=D * 0.05, amb=0.5)
    elif hs == "bob":
        poly(im, [(cx - rx * 1.08, cy + ry * 0.1), (cx - rx * 0.9, cy - ry * 0.85), (cx, cy - ry * 1.12),
                  (cx + rx * 0.9, cy - ry * 0.85), (cx + rx * 1.08, cy + ry * 0.1), (cx + rx * 0.7, cy - ry * 0.4),
                  (cx - rx * 0.2, cy - ry * 0.55)], (130, 72, 36), radius=D * 0.12, amb=0.45, spec=0.15)
    elif hs == "spiky":
        col = (176, 84, 38)
        pts = [(cx - rx * 1.02, cy - ry * 0.25)]
        for k in range(9):
            u = k / 8
            ang = math.pi * (1 - u)
            bx = cx + math.cos(ang) * rx * 0.98
            byy = cy - ry * 0.25 - math.sin(ang) * ry * 0.85
            pts.append((bx, byy))
            if k < 8:
                ang2 = math.pi * (1 - (k + 0.5) / 8)
                pts.append((cx + math.cos(ang2) * rx * 1.25, cy - ry * 0.3 - math.sin(ang2) * ry * 1.2))
        pts += [(cx + rx * 1.02, cy - ry * 0.25), (cx, cy - ry * 0.55)]
        poly(im, pts, col, radius=D * 0.06, amb=0.5, spec=0.2)
        fd = ImageDraw.Draw(im)
        for (fx, fy) in ((-0.22, 0.12), (-0.28, 0.18), (-0.18, 0.2), (0.22, 0.12), (0.28, 0.18), (0.18, 0.2)):
            fd.ellipse([cx + fx * D - D * 0.012, cy + fy * D - D * 0.012, cx + fx * D + D * 0.012,
                        cy + fy * D + D * 0.012], fill=(200, 120, 80))
    elif hs == "bowl":
        poly(im, [(cx - rx * 1.06, cy + ry * 0.05), (cx - rx * 1.0, cy - ry * 0.7), (cx - rx * 0.5, cy - ry * 1.12),
                  (cx, cy - ry * 1.18), (cx + rx * 0.5, cy - ry * 1.12), (cx + rx * 1.0, cy - ry * 0.7),
                  (cx + rx * 1.06, cy + ry * 0.05), (cx + rx * 0.85, cy - ry * 0.32), (cx - rx * 0.85, cy - ry * 0.32)],
             (246, 206, 96), radius=D * 0.1, amb=0.55, spec=0.25)
    elif hs == "pigtails":
        hc = (96, 56, 30)
        for sx in (-1, 1):
            ell(im, cx + sx * rx * 1.25, cy + ry * 0.15, D * 0.17, D * 0.24, hc, amb=0.5, spec=0.15)
            ell(im, cx + sx * rx * 1.02, cy - ry * 0.3, D * 0.08, D * 0.07, (240, 70, 140), amb=0.55, spec=0.3)
        poly(im, [(cx - rx * 1.03, cy - ry * 0.05), (cx - rx * 0.95, cy - ry * 0.75), (cx - rx * 0.4, cy - ry * 1.1),
                  (cx, cy - ry * 1.14), (cx + rx * 0.4, cy - ry * 1.1), (cx + rx * 0.95, cy - ry * 0.75),
                  (cx + rx * 1.03, cy - ry * 0.05), (cx + rx * 0.6, cy - ry * 0.55), (cx, cy - ry * 0.62),
                  (cx - rx * 0.6, cy - ry * 0.55)], hc, radius=D * 0.1, amb=0.5, spec=0.2)
    elif hs == "bald":
        for sx in (-1, 1):
            ell(im, cx + sx * rx * 0.92, cy - D * 0.06, D * 0.09, D * 0.14, (200, 200, 205), amb=0.6)
    # ---- Schweiß / nass
    if sweat:
        for (xf, yf, s) in ((0.32, -0.32, 1.0), (-0.38, -0.12, 0.8), (0.42, 0.05, 0.7)):
            x, y = cx + xf * D, cy + yf * D
            r = D * 0.05 * s
            dr = Image.new("RGBA", im.size, (0, 0, 0, 0))
            dd = ImageDraw.Draw(dr)
            dd.polygon([(x, y - r * 2.2), (x - r, y), (x + r, y)], fill=(150, 210, 255, 235))
            dd.ellipse([x - r, y - r, x + r, y + r], fill=(150, 210, 255, 235))
            dd.ellipse([x - r * 0.45, y - r * 0.5, x - r * 0.05, y - r * 0.05], fill=(255, 255, 255, 240))
            im.alpha_composite(dr)
    if wet:
        wl = Image.new("RGBA", im.size, (0, 0, 0, 0))
        wd = ImageDraw.Draw(wl)
        for k in range(7):
            x = cx + (-0.4 + k * 0.13) * D
            y = cy - ry * 0.9 + (k % 3) * D * 0.08
            wd.line([(x, y), (x, y + D * 0.1)], fill=(150, 200, 255, 200), width=max(2, int(D * 0.02)))
            wd.ellipse([x - D * 0.018, y + D * 0.1, x + D * 0.018, y + D * 0.14], fill=(170, 215, 255, 230))
        im.alpha_composite(wl)
    return im, (cx, cy)


# ------------------------------------------------------------------ Requisiten
def handbag(c, x, y, D, open_=False):
    """Weiche braune Leder-Umhängetasche; (x, y) = Riemen in der Hand."""
    bw, bh = D * 0.8, D * 0.6
    top = y + D * 0.34
    dd = ImageDraw.Draw(c)
    dd.line([(x - bw * 0.36, top + D * 0.03), (x, y), (x + bw * 0.36, top + D * 0.03)], fill=(120, 66, 34),
            width=max(3, int(D * 0.06)), joint="curve")
    poly(c, [(x - bw * 0.44, top), (x + bw * 0.44, top), (x + bw * 0.52, top + bh * 0.8), (x + bw * 0.4, top + bh),
             (x - bw * 0.4, top + bh), (x - bw * 0.52, top + bh * 0.8)], (152, 84, 40), radius=D * 0.16, amb=0.45,
         spec=0.3)
    dd = ImageDraw.Draw(c)
    dd.line([(x - bw * 0.4, top + bh * 0.42), (x + bw * 0.4, top + bh * 0.42)], fill=(112, 60, 28),
            width=max(2, int(D * 0.02)))
    for sx in (-1, 1):
        ell(c, x + sx * bw * 0.36, top + D * 0.03, D * 0.035, D * 0.035, GOLD, amb=0.5, spec=0.7, shine=40)


def knitting(c, x, y, D, phase=0.0):
    """Rosa Strickschal + Nadeln; (x, y) = Kreuzungspunkt der Nadeln."""
    sw, sh = D * 0.62, D * 0.95
    rrect(c, x - sw / 2, y - D * 0.02, x + sw / 2, y + sh, D * 0.1, (247, 140, 182), radius=D * 0.12, amb=0.5)
    d = ImageDraw.Draw(c)
    for k in range(9):
        yy = y + D * 0.06 + k * sh / 10
        pts = [(x - sw / 2 + D * 0.04 + j * sw / 8, yy + (D * 0.018 if j % 2 else 0)) for j in range(8)]
        d.line(pts, fill=(222, 105, 150), width=max(2, int(D * 0.014)))
    # Fransen
    for j in range(7):
        xx = x - sw / 2 + D * 0.06 + j * (sw - D * 0.12) / 6
        d.line([(xx, y + sh), (xx + D * 0.01, y + sh + D * 0.12)], fill=(247, 140, 182), width=max(2, int(D * 0.03)))
    a = math.sin(phase * 2 * math.pi) * 8
    for sx, base in ((-1, -38), (1, 38)):
        ang = math.radians(base + a * sx)
        L = D * 0.85
        x2, y2 = x + math.sin(ang) * L * 0.5, y - math.cos(ang) * L * 0.5
        x1, y1 = x - math.sin(ang) * L * 0.3, y + math.cos(ang) * L * 0.3
        d.line([(x1, y1), (x2, y2)], fill=(180, 186, 200), width=max(3, int(D * 0.03)))
        d.line([(x1, y1), (x2, y2)], fill=(235, 240, 250), width=max(1, int(D * 0.01)))
        d.ellipse([x2 - D * 0.04, y2 - D * 0.04, x2 + D * 0.04, y2 + D * 0.04], fill=(255, 150, 190))


def dumbbell(c, x, y, D, vertical=False, label=True):
    L = D * 1.5
    if vertical:
        rrect(c, x - D * 0.05, y - L / 2, x + D * 0.05, y + L / 2, D * 0.04, (205, 210, 220), amb=0.5, spec=0.8,
              shine=40)
        for sy in (-1, 1):
            rrect(c, x - D * 0.42, y + sy * L * 0.42 - D * 0.14, x + D * 0.42, y + sy * L * 0.42 + D * 0.14,
                  D * 0.06, (38, 38, 44), amb=0.4, spec=0.4)
        return
    rrect(c, x - L / 2, y - D * 0.05, x + L / 2, y + D * 0.05, D * 0.04, (205, 210, 220), amb=0.5, spec=0.8, shine=40)
    for sx in (-1, 1):
        for k, (hw, hh) in enumerate(((0.16, 0.5), (0.12, 0.4))):
            px = x + sx * (L * 0.36 + k * D * 0.16)
            rrect(c, px - D * hw / 2, y - D * hh, px + D * hw / 2, y + D * hh, D * 0.05, (40, 40, 46), amb=0.4,
                  spec=0.4, rim=0.4)
    if label:
        d = ImageDraw.Draw(c)
        for sx in (-1, 1):
            px = x + sx * L * 0.36
            d.text((px, y), "50", font=font(F_BLACK, max(8, int(D * 0.13))), fill=(255, 210, 40), anchor="mm")


def bonbon(c, x, y, D, color=(235, 60, 60), rot=0):
    s = D
    im = Image.new("RGBA", (int(s * 1.6), int(s * 0.8)), (0, 0, 0, 0))
    w, h = im.size
    d = ImageDraw.Draw(im)
    d.polygon([(0, h * 0.15), (w * 0.3, h / 2), (0, h * 0.85)], fill=mixc(color, (255, 255, 255), 0.3))
    d.polygon([(w, h * 0.15), (w * 0.7, h / 2), (w, h * 0.85)], fill=mixc(color, (255, 255, 255), 0.3))
    ell(im, w / 2, h / 2, w * 0.26, h * 0.42, color, amb=0.5, spec=0.6, shine=30)
    if rot:
        im = im.rotate(rot, expand=True, resample=Image.BICUBIC)
    c.alpha_composite(im, (int(x - im.width / 2), int(y - im.height / 2)))


@lru_cache(maxsize=64)
def bonbon_sprite(D, color, rot):
    im = Image.new("RGBA", (int(D * 2.4), int(D * 2.4)), (0, 0, 0, 0))
    bonbon(im, im.width / 2, im.height / 2, D, color, rot)
    return im


def bonbon_bag(c, x, y, D):
    rrect(c, x - D * 0.28, y - D * 0.32, x + D * 0.28, y + D * 0.32, D * 0.06, (250, 240, 200), amb=0.6, spec=0.3)
    d = ImageDraw.Draw(c)
    d.rectangle([x - D * 0.28, y - D * 0.32, x + D * 0.28, y - D * 0.22], fill=(230, 60, 60))
    for k, (dx, dy) in enumerate(((-0.12, 0.02), (0.1, -0.04), (0.0, 0.16), (-0.13, 0.2), (0.13, 0.17))):
        bonbon(c, x + dx * D, y + dy * D, D * 0.16, (235, 70, 60) if k % 2 else (250, 160, 40))


def sandwich(c, x, y, D):
    """Pausenbrot (zwei Brotscheiben mit Salat und Käse)."""
    w, h = D * 0.55, D * 0.18
    rrect(c, x - w / 2, y + h * 0.4, x + w / 2, y + h * 1.4, D * 0.07, (214, 160, 90), amb=0.5, spec=0.15)
    poly(c, [(x - w * 0.55, y + h * 0.45), (x + w * 0.55, y + h * 0.3), (x + w * 0.5, y + h * 0.6),
             (x - w * 0.5, y + h * 0.7)], (110, 200, 80), radius=D * 0.02, amb=0.6)
    poly(c, [(x - w * 0.45, y + h * 0.2), (x + w * 0.5, y + h * 0.15), (x + w * 0.3, y + h * 0.55),
             (x - w * 0.4, y + h * 0.5)], (255, 210, 70), radius=D * 0.02, amb=0.6)
    rrect(c, x - w / 2, y - h * 0.6, x + w / 2, y + h * 0.35, D * 0.08, (226, 172, 100), amb=0.5, spec=0.2)


def backpack(c, x, y, D):
    """Kinder-Rucksack; (x, y) = Griffschlaufe oben."""
    d = ImageDraw.Draw(c)
    d.arc([x - D * 0.1, y - D * 0.06, x + D * 0.1, y + D * 0.12], 180, 360, fill=(30, 60, 120), width=max(2, int(D * 0.035)))
    rrect(c, x - D * 0.3, y + D * 0.04, x + D * 0.3, y + D * 0.72, D * 0.14, (50, 110, 210), amb=0.5, spec=0.2)
    rrect(c, x - D * 0.22, y + D * 0.38, x + D * 0.22, y + D * 0.66, D * 0.08, (240, 190, 40), amb=0.55, spec=0.2)
    d = ImageDraw.Draw(c)
    d.line([(x - D * 0.2, y + D * 0.38), (x + D * 0.2, y + D * 0.38)], fill=(40, 40, 50), width=max(1, int(D * 0.015)))
    ell(c, x + D * 0.12, y + D * 0.2, D * 0.06, D * 0.06, (250, 90, 120), amb=0.6, spec=0.3)


def phone(c, x, y, D, sock=False):
    w, h = D * 0.24, D * 0.42
    if sock:
        rrect(c, x - w * 0.7, y - h * 0.62, x + w * 0.7, y + h * 0.62, D * 0.08, (247, 140, 182), amb=0.55, spec=0.15)
        d = ImageDraw.Draw(c)
        for k in range(6):
            yy = y - h * 0.5 + k * h * 0.2
            d.line([(x - w * 0.6, yy), (x + w * 0.6, yy)], fill=(222, 105, 150), width=max(1, int(D * 0.012)))
        d.text((x, y), "MATHE", font=font(F_BLACK, max(6, int(D * 0.075))), fill=(255, 255, 255), anchor="mm")
        return
    rrect(c, x - w / 2, y - h / 2, x + w / 2, y + h / 2, D * 0.04, (30, 30, 40), amb=0.4, spec=0.5)
    d = ImageDraw.Draw(c)
    d.rounded_rectangle([x - w * 0.4, y - h * 0.42, x + w * 0.4, y + h * 0.42], radius=D * 0.02,
                        fill=(90, 200, 255))
    d.rectangle([x - w * 0.3, y - h * 0.1, x + w * 0.3, y + h * 0.1], fill=(255, 220, 60))


def trophy(c, x, y, D):
    """Pokal; (x, y) = Griff unten."""
    rrect(c, x - D * 0.3, y + D * 0.25, x + D * 0.3, y + D * 0.42, D * 0.04, (60, 50, 40), amb=0.4)
    rrect(c, x - D * 0.06, y - D * 0.2, x + D * 0.06, y + D * 0.28, D * 0.04, GOLD, amb=0.4, spec=0.6)
    d = ImageDraw.Draw(c)
    for sx in (-1, 1):
        d.arc([x + sx * D * 0.45 - D * 0.22, y - D * 0.95, x + sx * D * 0.45 + D * 0.22, y - D * 0.45],
              270 if sx > 0 else 90, 90 if sx > 0 else 270, fill=GOLD, width=int(D * 0.07))
    poly(c, [(x - D * 0.48, y - D * 1.05), (x + D * 0.48, y - D * 1.05), (x + D * 0.32, y - D * 0.45),
             (x, y - D * 0.18), (x - D * 0.32, y - D * 0.45)], GOLD, radius=D * 0.2, amb=0.4, spec=0.7, shine=30)


# ------------------------------------------------------------------ Körper
BODY = {
    # sh: Schulterbreite (halb), hip: Hüfte (halb), tl: Rumpflänge, arm: Ärmeldicke, top: Farbe Oberteil
    "oma": dict(sh=0.47, hip=0.5, tl=1.25, arm=0.26, hand=0.135, top=(228, 214, 192), leg=(236, 205, 185),
                shoe=(120, 72, 38), skirt=(178, 164, 156)),
    "judo": dict(sh=0.52, hip=0.48, tl=1.3, arm=0.3, hand=0.135, top=(250, 250, 248), leg=(250, 250, 248),
                 shoe=None, pants=(250, 250, 248)),
    "thief": dict(sh=0.56, hip=0.46, tl=1.45, arm=0.3, hand=0.14, top=(76, 78, 90), leg=(50, 80, 140),
                  shoe=(235, 235, 240), pants=(50, 80, 140)),
    "thief2": dict(sh=0.6, hip=0.5, tl=1.45, arm=0.31, hand=0.14, top=(124, 62, 176), leg=(124, 62, 176),
                   shoe=(30, 30, 34), pants=(124, 62, 176)),
    "jung": dict(sh=0.58, hip=0.48, tl=1.45, arm=0.31, hand=0.14, top=(40, 190, 170), leg=(60, 90, 150),
                 shoe=(250, 250, 250), pants=(60, 90, 150)),
    "musk1": dict(sh=1.05, hip=0.6, tl=1.55, arm=0.5, hand=0.2, top=(220, 50, 60), leg=(232, 176, 132),
                  shoe=(40, 40, 48), pants=(60, 64, 80), tank=True),
    "musk2": dict(sh=1.05, hip=0.6, tl=1.55, arm=0.5, hand=0.2, top=(30, 32, 40), leg=(178, 118, 82),
                  shoe=(240, 240, 245), pants=(80, 84, 100), tank=True),
    "pass1": dict(sh=0.48, hip=0.5, tl=1.3, arm=0.28, hand=0.13, top=(245, 140, 60), leg=(60, 70, 110),
                  shoe=(60, 40, 30), pants=(60, 70, 110)),
    "pass2": dict(sh=0.55, hip=0.52, tl=1.4, arm=0.3, hand=0.14, top=(90, 130, 90), leg=(110, 100, 90),
                  shoe=(50, 40, 30), pants=(110, 100, 90)),
    "rowdy": dict(sh=0.56, hip=0.46, tl=1.2, arm=0.29, hand=0.14, top=(222, 58, 50), leg=(60, 82, 140),
                  shoe=(245, 245, 245), pants=(60, 82, 140)),
    "kleiner": dict(sh=0.42, hip=0.38, tl=1.0, arm=0.24, hand=0.12, top=(252, 200, 60), leg=(70, 110, 200),
                    shoe=(225, 60, 60), pants=(70, 110, 200)),
    "girl": dict(sh=0.45, hip=0.42, tl=1.05, arm=0.25, hand=0.12, top=(40, 180, 170), leg=(230, 110, 160),
                 shoe=(250, 250, 250), pants=(230, 110, 160)),
    "bully2": dict(sh=0.56, hip=0.46, tl=1.3, arm=0.29, hand=0.14, top=(44, 44, 52), leg=(120, 120, 128),
                   shoe=(245, 245, 245), pants=(120, 120, 128)),
    "gamer": dict(sh=0.48, hip=0.44, tl=1.1, arm=0.27, hand=0.13, top=(80, 170, 80), leg=(110, 110, 120),
                  shoe=(30, 30, 34), pants=(110, 110, 120)),
}


def _P(nx, ny, D, p):
    return (nx + p[0] * D, ny + p[1] * D)


def person(who, D, pose, **kw):
    """Quantisiert D (für den Cache) und skaliert auf exakte Größe. Rückgabe (Bild, Nacken, Skalierung)."""
    Dq = max(16, int(round(D / 6.0)) * 6)
    kw = {k: (tuple(v) if isinstance(v, list) else v) for k, v in kw.items()}
    im, (nx, ny) = person_raw(who, Dq, pose, **kw)
    return im, (nx, ny), D / Dq


@lru_cache(maxsize=160)
def person_raw(who, D, pose, expr="neutral", mouth=0.0, blink=False, look=(0.0, 0.0), gl=0.07, brow_up=0,
           sweat=False, wet=False, items=(), head_off=(0.0, 0.0, 0.0), mouth_kind=None, knit_phase=0.0):
    """Ganze Figur als Sprite. pose = Schlüssel in POSES (oder Tupel von Overrides).
    Rückgabe (Bild, Nackenpunkt)."""
    c = CFG[who]
    b = BODY[c["body"]]
    P = pose_dict(who, pose)
    CW, CH = int(D * 4.6), int(D * 6.2)
    im = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    nx, ny = CW / 2, D * 2.0
    pt = lambda p: _P(nx, ny, D, p)  # noqa
    skin = c["skin"]
    top = b["top"]
    wet_f = 0.7 if wet else 1.0
    topc = darker(top, wet_f) if wet else top
    # --- Arme hinten
    for side in (-1, 1):
        arm = P["arms"][0 if side < 0 else 1]
        if arm[2] == "back":
            _arm(im, pt, side, b, arm, topc, skin, D)
    # --- Beine
    _legs(im, pt, b, P, D, skin, wet_f)
    # --- Rumpf
    sh, hip, tl = b["sh"], b["hip"], b["tl"]
    torso = [(-sh * 0.7, -0.02), (-sh, 0.12), (-sh * 1.02, 0.5), (-hip, tl), (hip, tl), (sh * 1.02, 0.5), (sh, 0.12),
             (sh * 0.7, -0.02)]
    poly(im, [pt(p) for p in torso], topc, radius=D * 0.22, amb=0.45, spec=0.12, rim=0.25)
    d = ImageDraw.Draw(im)
    body = c["body"]
    if body == "oma":
        # Strick-Rippen
        tex = Image.new("RGBA", im.size, (0, 0, 0, 0))
        td = ImageDraw.Draw(tex)
        for k in range(-7, 8):
            x0 = nx + k * D * 0.065
            td.line([(x0, ny + D * 0.12), (x0 + k * D * 0.004, ny + tl * D)], fill=(160, 130, 90, 60),
                    width=max(1, int(D * 0.012)))
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).polygon([pt(p) for p in torso], fill=255)
        tex.putalpha(ImageChops_mul(tex.getchannel("A"), mask))
        im.alpha_composite(tex)
        # Bluse (V) + Kragen
        poly(im, [pt((-0.2, -0.03)), pt((0.2, -0.03)), pt((0.07, 0.62)), pt((-0.07, 0.62))], (238, 230, 216),
             radius=D * 0.05, amb=0.6)
        poly(im, [pt((-0.16, -0.03)), pt((0.16, -0.03)), pt((0.0, 0.2))], skin, radius=D * 0.04, amb=0.55)
        # Strickjacken-Kante
        d.line([pt((-0.08, 0.62)), pt((-0.04, tl))], fill=darker(topc, 0.75), width=max(2, int(D * 0.025)))
        d.line([pt((0.08, 0.62)), pt((0.04, tl))], fill=darker(topc, 0.75), width=max(2, int(D * 0.025)))
        d.line([pt((-0.2, -0.03)), pt((-0.08, 0.62))], fill=darker(topc, 0.78), width=max(2, int(D * 0.03)))
        d.line([pt((0.2, -0.03)), pt((0.08, 0.62))], fill=darker(topc, 0.78), width=max(2, int(D * 0.03)))
        for k in range(4):
            x, y = pt((0.12 - k * 0.012, 0.52 + k * 0.2))
            ell(im, x, y, D * 0.05, D * 0.05, (205, 188, 160), amb=0.5, spec=0.4)
            d.ellipse([x - D * 0.01, y - D * 0.01, x + D * 0.01, y + D * 0.01], fill=(150, 130, 100))
        # Taschen
        for sx in (-1, 1):
            x, y = pt((sx * 0.3, 1.0))
            d.rounded_rectangle([x - D * 0.14, y - D * 0.08, x + D * 0.14, y + D * 0.12], radius=D * 0.03,
                                outline=darker(topc, 0.8), width=max(2, int(D * 0.018)))
    elif body == "judo":
        poly(im, [pt((-0.22, -0.04)), pt((0.22, -0.04)), pt((0.0, 0.7))], skin, radius=D * 0.06, amb=0.55)
        d.line([pt((-0.24, -0.03)), pt((0.12, 0.85))], fill=(215, 215, 210), width=int(D * 0.08))
        d.line([pt((0.24, -0.03)), pt((-0.05, 0.8))], fill=(230, 230, 225), width=int(D * 0.08))
        # schwarzer Gürtel
        rrect(im, *pt((-hip * 1.02, tl - 0.28)), *pt((hip * 1.02, tl - 0.12)), D * 0.04, (25, 25, 28), amb=0.4,
              spec=0.2)
        x, y = pt((0.08, tl - 0.2))
        limb(im, (x, y), (x - D * 0.12, y + D * 0.38), D * 0.09, (25, 25, 28), amb=0.4)
        limb(im, (x, y), (x + D * 0.14, y + D * 0.36), D * 0.09, (25, 25, 28), amb=0.4)
        ell(im, x, y, D * 0.08, D * 0.07, (30, 30, 34), amb=0.4)
    elif body == "thief":
        # Kapuzenpulli: Bauchtasche + Kordeln
        poly(im, [pt((-0.36, tl - 0.55)), pt((0.36, tl - 0.55)), pt((0.42, tl - 0.08)), pt((-0.42, tl - 0.08))],
             darker(topc, 0.88), radius=D * 0.06, amb=0.45)
        for sx in (-1, 1):
            d.line([pt((sx * 0.12, 0.02)), pt((sx * 0.14, 0.45))], fill=(200, 200, 210), width=max(2, int(D * 0.02)))
    elif body == "thief2":
        d.line([pt((0.0, 0.0)), pt((0.0, tl))], fill=(240, 240, 240), width=max(2, int(D * 0.025)))
        for sx in (-1, 1):
            d.line([pt((sx * b["sh"] * 0.98, 0.15)), pt((sx * b["hip"] * 1.0, tl - 0.05))], fill=(240, 240, 240),
                   width=max(2, int(D * 0.03)))
    elif body == "bully2":
        d.text(pt((0.0, 0.55)), "NO", font=font(F_BLACK, max(8, int(D * 0.16))), fill=(250, 250, 250), anchor="mm")
        d.text(pt((0.0, 0.78)), "RULES", font=font(F_BLACK, max(8, int(D * 0.11))), fill=(240, 70, 70), anchor="mm")
    elif body == "jung":
        poly(im, [pt((-0.2, -0.03)), pt((0.2, -0.03)), pt((0.1, tl)), pt((-0.1, tl))], (250, 250, 250),
             radius=D * 0.05, amb=0.6)
        d.line([pt((0.1, 0.0)), pt((0.12, tl))], fill=(200, 200, 200), width=max(2, int(D * 0.02)))
        d.text(pt((0.0, 0.55)), "YOLO", font=font(F_BLACK, max(8, int(D * 0.12))), fill=(240, 70, 80), anchor="mm")
    elif body.startswith("musk"):
        # Brustmuskeln + Bauch
        for sx in (-1, 1):
            ell(im, *pt((sx * 0.38, 0.38)), D * 0.36, D * 0.24, topc, amb=0.4, spec=0.25, rim=0.3)
        for k in range(3):
            for sx in (-1, 1):
                ell(im, *pt((sx * 0.13, 0.75 + k * 0.22)), D * 0.12, D * 0.09, darker(topc, 0.95), amb=0.45,
                    spec=0.2)
        # Tank-Top-Ausschnitt -> Haut zeigt sich an den Schultern
        for sx in (-1, 1):
            ell(im, *pt((sx * (sh * 0.88), 0.12)), D * 0.3, D * 0.22, skin, amb=0.45, spec=0.25)
        poly(im, [pt((-0.25, -0.04)), pt((0.25, -0.04)), pt((0.0, 0.25))], skin, radius=D * 0.06, amb=0.5)
        if body == "musk1":
            d.text(pt((0.0, 1.15)), "GYM", font=font(F_BLACK, max(8, int(D * 0.2))), fill=(255, 255, 255),
                   anchor="mm")
    elif body in ("pass1", "pass2"):
        poly(im, [pt((-0.18, -0.03)), pt((0.18, -0.03)), pt((0.0, 0.35))], skin, radius=D * 0.05, amb=0.5)
    # Hals
    ell(im, nx, ny - D * 0.02, D * 0.17, D * 0.12, skin, amb=0.45)
    if body == "oma":
        # Perlenkette
        for k in range(15):
            u = -1 + 2 * k / 14
            px, py = pt((0.2 * u, 0.0 + 0.3 * (1 - u * u)))
            ell(im, px, py, D * 0.028, D * 0.028, (250, 246, 236), amb=0.65, spec=0.8, shine=30)
    if body == "thief":
        d.arc([nx - D * 0.36, ny - D * 0.2, nx + D * 0.36, ny + D * 0.18], 10, 170, fill=(60, 62, 72),
              width=int(D * 0.07))
    # --- Items hinter den Händen
    for it in items:
        if it[0] == "bag_back":
            handbag(im, *pt(it[1]), D)
    # --- Kopf
    hx, hy = pt((head_off[0], -0.5 + head_off[1]))
    himg, (hcx, hcy) = head(who, D, expr, mouth, blink, look, gl, brow_up, mouth_kind, sweat, wet)
    if head_off[2]:
        himg = himg.rotate(head_off[2], resample=Image.BICUBIC, center=(hcx, hcy + D * 0.4))
    im.alpha_composite(himg, (int(hx - hcx), int(hy - hcy)))
    # --- Items vor dem Körper, hinter den Vorderarmen
    for it in items:
        kind = it[0]
        if kind == "knit":
            knitting(im, *pt(it[1]), D, knit_phase)
        elif kind == "bag":
            handbag(im, *pt(it[1]), D)
        elif kind == "dumbbell":
            dumbbell(im, *pt(it[1]), D * it[2], vertical=False)
        elif kind == "trophy":
            trophy(im, *pt(it[1]), D)
        elif kind == "bonbonbag":
            bonbon_bag(im, *pt(it[1]), D)
        elif kind == "sandwich":
            sandwich(im, *pt(it[1]), D)
        elif kind == "backpack":
            backpack(im, *pt(it[1]), D)
        elif kind == "phone":
            phone(im, *pt(it[1]), D, sock=False)
        elif kind == "phone_sock":
            phone(im, *pt(it[1]), D, sock=True)
    # --- Arme vorne
    for side in (-1, 1):
        arm = P["arms"][0 if side < 0 else 1]
        if arm[2] != "back":
            _arm(im, pt, side, b, arm, topc, skin, D)
    for it in items:
        kind = it[0]
        if kind == "bonbon":
            bonbon(im, *pt(it[1]), D * 0.2, (235, 60, 60), 20)
        elif kind == "dumbbell_front":
            dumbbell(im, *pt(it[1]), D * it[2], vertical=False)
    return im, (nx, ny)


def _arm(im, pt, side, b, arm, topc, skin, D):
    elbow, hand, mode = arm[0], arm[1], arm[2]
    shp = pt((side * b["sh"] * 0.92, 0.14))
    e, h = pt(elbow), pt(hand)
    sleeve_c = topc if not b.get("tank") else skin
    if mode == "point":
        # Finger zeigt zur Kamera: Hand groß
        limb3(im, shp, e, h, D * b["arm"], sleeve_c, amb=0.45, spec=0.12, rim=0.2)
        ell(im, h[0], h[1], D * b["hand"] * 1.5, D * b["hand"] * 1.4, skin, amb=0.5, spec=0.2)
        ell(im, h[0], h[1] - D * 0.05, D * b["hand"] * 0.75, D * b["hand"] * 0.75, mixc(skin, (255, 255, 255), 0.1),
            amb=0.5, spec=0.3)
        return
    limb3(im, shp, e, h, D * b["arm"], sleeve_c, amb=0.45, spec=0.12, rim=0.2)
    if b.get("tank"):
        # Bizeps
        mx, my = (shp[0] + e[0]) / 2, (shp[1] + e[1]) / 2
        ell(im, mx, my, D * b["arm"] * 0.62, D * b["arm"] * 0.55, skin, amb=0.45, spec=0.3)
    elif b["top"] != skin:
        # Ärmelbündchen
        cxx, cyy = h[0] + (e[0] - h[0]) * 0.16, h[1] + (e[1] - h[1]) * 0.16
        ell(im, cxx, cyy, D * b["arm"] * 0.46, D * b["arm"] * 0.3, darker(topc, 0.9), amb=0.5)
    S = D * b["hand"] / 0.135 * 1.25
    if mode == "finger":
        # Zeigefinger nach oben (Brille hochschieben): Hand zeigt nach oben
        hand_draw(im, h, (h[0], h[1] + D), S, skin, "finger", side)
    else:
        hand_draw(im, h, e, S, skin, mode, side)


def _pattern(im, pts, D):
    """Kleines Blümchen-/Punktmuster auf dem Rock."""
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    step = D * 0.11
    r = max(1.5, D * 0.018)
    y = min(ys)
    row = 0
    while y < max(ys):
        x = min(xs) + (step / 2 if row % 2 else 0)
        while x < max(xs):
            d.ellipse([x - r, y - r, x + r, y + r], fill=(120, 100, 85, 150))
            x += step
        y += step * 0.8
        row += 1
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    lay.putalpha(ImageChops_mul(lay.getchannel("A"), m))
    im.alpha_composite(lay)


def _legs(im, pt, b, P, D, skin, wet_f):
    lower = P["lower"]
    tl = b["tl"]
    shoe = b["shoe"]
    if lower in ("skirt_stand", "skirt_sit") and b.get("oma_pants"):
        pc = darker(b["oma_pants"], wet_f)
        if lower == "skirt_stand":
            for sx in (-1, 1):
                limb(im, pt((sx * 0.25, tl + 0.05)), pt((sx * 0.24, tl + 1.42)), D * 0.44, pc, amb=0.5, spec=0.1,
                     rim=0.15)
            rrect(im, *pt((-b["hip"], tl - 0.12)), *pt((b["hip"], tl + 0.22)), D * 0.14, pc, amb=0.5, spec=0.1)
            for sx in (-1, 1):
                ell(im, *pt((sx * 0.26, tl + 1.52)), D * 0.18, D * 0.1, shoe, amb=0.45, spec=0.35)
            d = ImageDraw.Draw(im)
            for sx in (-1, 1):
                d.line([pt((sx * 0.24, tl + 0.4)), pt((sx * 0.24, tl + 1.38))], fill=darker(pc, 0.86),
                       width=max(1, int(D * 0.012)))
        else:
            for sx in (-1, 1):
                limb(im, pt((sx * 0.27, tl + 0.4)), pt((sx * 0.27, tl + 1.1)), D * 0.34, pc, amb=0.5, spec=0.1,
                     rim=0.15)
                ell(im, *pt((sx * 0.29, tl + 1.18)), D * 0.18, D * 0.11, shoe, amb=0.45, spec=0.35)
            rrect(im, *pt((-0.6, tl - 0.12)), *pt((0.6, tl + 0.5)), D * 0.22, pc, amb=0.5, spec=0.12, rim=0.15)
            d = ImageDraw.Draw(im)
            d.line([pt((0.0, tl + 0.05)), pt((0.0, tl + 0.48))], fill=darker(pc, 0.82), width=max(1, int(D * 0.015)))
        return
    if lower in ("skirt_stand", "skirt_sit"):
        legc = b["leg"]
        if lower == "skirt_stand":
            legs = P.get("legs") or (((-0.2, tl + 0.1), (-0.21, tl + 0.85), (-0.21, tl + 1.45)),
                                     ((0.2, tl + 0.1), (0.21, tl + 0.85), (0.21, tl + 1.45)))
            for side, (hp, kn, ft) in zip((-1, 1), legs):
                _leg_natural(im, pt(kn), pt(ft), D, legc)
                shoe_draw(im, *pt(ft), D, shoe, "lace", side)
            (_, kl, _), (_, kr, _) = legs
            hem_l = (min(kl[0] - 0.45, -0.5), max(kl[1], tl + 0.85) + 0.07)
            hem_r = (max(kr[0] + 0.45, 0.5), max(kr[1], tl + 0.85) + 0.07)
            sk = [pt((-b["hip"], tl - 0.05)), pt((b["hip"], tl - 0.05)), pt(hem_r), pt(hem_l)]
            poly(im, sk, darker(b["skirt"], wet_f), radius=D * 0.18, amb=0.45, spec=0.12, rim=0.2)
            _pattern(im, sk, D)
        else:
            for sx in (-1, 1):
                _leg_natural(im, pt((sx * 0.25, tl + 0.5)), pt((sx * 0.25, tl + 1.12)), D, legc)
                shoe_draw(im, *pt((sx * 0.25, tl + 1.12)), D, shoe, "lace", sx)
            sk = [pt((-b["hip"], tl - 0.05)), pt((b["hip"], tl - 0.05)), pt((0.64, tl + 0.42)), pt((0.6, tl + 0.6)),
                  pt((-0.6, tl + 0.6)), pt((-0.64, tl + 0.42))]
            poly(im, sk, darker(b["skirt"], wet_f), radius=D * 0.18, amb=0.45, spec=0.12, rim=0.2)
            _pattern(im, sk, D)
        return
    pants = darker(b.get("pants", b["leg"]), wet_f)
    lw = 0.3 if not b.get("tank") else 0.42
    for side in (-1, 1):
        hip_p, knee, foot = P["legs"][0 if side < 0 else 1]
        limb3(im, pt(hip_p), pt(knee), pt(foot), D * lw, pants, amb=0.45, spec=0.12, rim=0.15)
        fx, fy = pt(foot)
        if shoe:
            shoe_draw(im, fx, fy, D * (1.15 if b.get("tank") else 1.0), shoe, "sneaker" if sum(shoe) > 500 else "lace",
                      side)
        else:
            shoe_draw(im, fx, fy, D, skin, "bare", side)
    if b.get("tank") or b.get("pants"):
        rrect(im, *pt((-b["hip"] * 1.02, tl - 0.15)), *pt((b["hip"] * 1.02, tl + 0.2)), D * 0.1, pants, amb=0.45,
              spec=0.12)


def _leg_natural(im, knee, ankle, D, col):
    """Unterschenkel mit Wade und schmalem Knöchel."""
    kx, ky = knee
    ax, ay = ankle
    limb(im, (kx, ky), (ax, ay - D * 0.04), D * 0.13, col, amb=0.5, spec=0.2)
    cx, cy = kx + (ax - kx) * 0.3, ky + (ay - ky) * 0.3
    ang = math.degrees(math.atan2(ax - kx, ay - ky))
    calf = Image.new("RGBA", (int(D * 0.5), int(D * 0.6)), (0, 0, 0, 0))
    ell(calf, calf.width / 2, calf.height / 2, D * 0.085, D * 0.19, col, amb=0.5, spec=0.2)
    calf = calf.rotate(ang, resample=Image.BICUBIC)
    im.alpha_composite(calf, (int(cx - calf.width / 2), int(cy - calf.height / 2)))


def shoe_draw(im, x, y, D, col, kind="lace", side=1):
    """Schuh in Vorderansicht; (x, y) = Knöchel."""
    if kind == "bare":
        ell(im, x, y + D * 0.06, D * 0.09, D * 0.075, col, amb=0.5, spec=0.2)
        d = ImageDraw.Draw(im)
        for k in range(4):
            tx = x - D * 0.06 + k * D * 0.04
            d.ellipse([tx - D * 0.018, y + D * 0.1, tx + D * 0.018, y + D * 0.135], fill=darker(col, 0.92))
        return
    # Sohle
    sole = (70, 52, 40) if kind == "lace" else (235, 235, 238)
    rrect(im, x - D * 0.14, y + D * 0.1, x + D * 0.14, y + D * 0.155, D * 0.025, sole, amb=0.5, spec=0.2)
    # Schuh-Körper: Knöchelöffnung oben, breite Kappe unten
    poly(im, [(x - D * 0.085, y - D * 0.03), (x + D * 0.085, y - D * 0.03), (x + D * 0.135, y + D * 0.07),
              (x + D * 0.13, y + D * 0.12), (x - D * 0.13, y + D * 0.12), (x - D * 0.135, y + D * 0.07)], col,
         radius=D * 0.05, amb=0.45, spec=0.35 if kind == "lace" else 0.25)
    ell(im, x, y + D * 0.09, D * 0.12, D * 0.045, mixc(col, (255, 255, 255), 0.08), amb=0.5, spec=0.4)
    d = ImageDraw.Draw(im)
    if kind == "lace":
        lc = mixc(col, (255, 240, 220), 0.35)
        for k in range(3):
            yy = y + k * D * 0.028
            d.line([(x - D * 0.04, yy), (x + D * 0.04, yy + D * 0.012)], fill=lc, width=max(1, int(D * 0.012)))
            d.line([(x + D * 0.04, yy), (x - D * 0.04, yy + D * 0.012)], fill=lc, width=max(1, int(D * 0.012)))
    else:
        d.line([(x - D * 0.12, y + D * 0.06), (x - D * 0.02, y + D * 0.03)], fill=(220, 60, 60) if sum(col) > 600
               else (240, 240, 240), width=max(2, int(D * 0.02)))


def hand_draw(im, h, e, S, skin, mode, side):
    """Natürliche Hand: Handfläche, vier Finger, Daumen; ausgerichtet am Unterarm (Ellbogen e -> Hand h)."""
    ux, uy = h[0] - e[0], h[1] - e[1]
    n = math.hypot(ux, uy) or 1.0
    ux, uy = ux / n, uy / n
    px, py = uy * (-side), -ux * (-side)          # zeigt zur Körpermitte (Daumenseite)

    def P(a, bb):
        return (h[0] + ux * a * S + px * bb * S, h[1] + uy * a * S + py * bb * S)

    fing = mixc(skin, (225, 150, 130), 0.08)
    # Handfläche als gedrehte Ellipse
    pts = []
    for k in range(18):
        t = 2 * math.pi * k / 18
        pts.append(P(0.03 + 0.11 * math.sin(t), 0.09 * math.cos(t)))
    poly(im, pts, skin, radius=S * 0.05, amb=0.5, spec=0.2)
    d = ImageDraw.Draw(im)
    if mode in ("fist", "grip"):
        for k, bb in enumerate((-0.06, -0.02, 0.02, 0.06)):
            x, y = P(0.12, bb)
            ell(im, x, y, S * 0.03, S * 0.03, fing, amb=0.5, spec=0.25)
        limb(im, P(0.0, 0.08), P(0.1, 0.03), S * 0.045, fing, amb=0.5, spec=0.25)
        return
    lens = (0.12, 0.15, 0.14, 0.11)
    if mode == "finger":
        lens = (0.05, 0.05, 0.05, 0.24)
    for k, (bb, L) in enumerate(zip((-0.058, -0.02, 0.02, 0.058), lens)):
        a0 = 0.1
        curl = 0.0
        limb(im, P(a0, bb), P(a0 + L, bb * 0.8 + curl), S * 0.043, fing, amb=0.5, spec=0.25)
        tx, ty = P(a0 + L - 0.012, bb * 0.8 + curl)
        d = ImageDraw.Draw(im)
        r = S * 0.012
        d.ellipse([tx - r, ty - r, tx + r, ty + r], fill=mixc(skin, (255, 255, 255), 0.45))
    limb(im, P(0.0, 0.085), P(0.09, 0.13), S * 0.048, fing, amb=0.5, spec=0.25)


# Arm-Format: (ellbogen, hand, modus) in Kopf-Einheiten relativ zum Nacken; modus "front"/"back"/...
STAND_LEGS = (((-0.2, 1.4), (-0.22, 2.0), (-0.24, 2.7)), ((0.2, 1.4), (0.22, 2.0), (0.24, 2.7)))
POSES = {
    "oma_sit_knit": dict(lower="skirt_sit", arms=(((-0.6, 0.85), (-0.12, 1.1), "front"),
                                                  ((0.6, 0.85), (0.12, 1.1), "front"))),
    "oma_sit_rest": dict(lower="skirt_sit", arms=(((-0.6, 0.8), (-0.3, 1.3), "front"),
                                                  ((0.6, 0.8), (0.3, 1.3), "front"))),
    "oma_sit_throw": dict(lower="skirt_sit", arms=(((-0.6, 0.85), (-0.12, 1.1), "front"),
                                                   ((0.85, 0.35), (1.15, 0.0), "front"))),
    "oma_sit_offer": dict(lower="skirt_sit", arms=(((-0.6, 0.8), (-0.3, 1.3), "front"),
                                                   ((0.75, 0.6), (1.2, 0.45), "front"))),
    "oma_sit_hold": dict(lower="skirt_sit", arms=(((-0.6, 0.8), (-0.3, 1.3), "front"),
                                                  ((0.8, 0.5), (1.15, 0.85), "front"))),
    "oma_sit_pull": dict(lower="skirt_sit", arms=(((-0.6, 0.8), (-0.3, 1.3), "front"),
                                                  ((0.8, 0.45), (1.3, 0.55), "front"))),
    "oma_sit_release": dict(lower="skirt_sit", arms=(((-0.6, 0.8), (-0.3, 1.3), "front"),
                                                     ((0.75, 0.55), (0.95, 0.15), "front"))),
    "oma_stand": dict(lower="skirt_stand", arms=(((-0.62, 0.7), (-0.6, 1.25), "front"),
                                                 ((0.62, 0.7), (0.6, 1.25), "front"))),
    "oma_stand_bag": dict(lower="skirt_stand", arms=(((-0.62, 0.7), (-0.6, 1.25), "front"),
                                                     ((0.66, 0.7), (0.62, 1.2), "front"))),
    "oma_stand_bagdown": dict(lower="skirt_stand", arms=(((-0.62, 0.7), (-0.6, 1.25), "front"),
                                                         ((0.75, 0.75), (0.85, 1.55), "front"))),
    "oma_lift": dict(lower="skirt_stand", arms=(((-0.62, 0.7), (-0.6, 1.25), "front"),
                                                ((0.95, -0.55), (0.85, -1.55), "front"))),
    "oma_lift_low": dict(lower="skirt_stand", arms=(((-0.62, 0.7), (-0.6, 1.25), "front"),
                                                    ((0.8, 0.6), (0.8, 1.2), "front"))),
    "oma_glasses": dict(lower="skirt_stand", arms=(((-0.62, 0.7), (-0.6, 1.25), "front"),
                                                   ((0.55, 0.65), (0.08, -0.22), "finger"))),
    "oma_offer": dict(lower="skirt_stand", arms=(((-0.72, 0.5), (-1.2, 0.35), "front"),
                                                 ((0.62, 0.7), (0.6, 1.25), "front"))),
    "oma_point": dict(lower="skirt_stand", arms=(((-0.62, 0.7), (-0.6, 1.25), "front"),
                                                 ((0.45, 0.55), (0.25, 0.35), "point"))),
    "oma_wave": dict(lower="skirt_stand", arms=(((-0.62, 0.7), (-0.6, 1.25), "front"),
                                                ((0.85, 0.2), (0.95, -0.45), "front"))),
    "young_trophy": dict(lower="pants", legs=STAND_LEGS, arms=(((-0.7, 0.55), (-0.6, 1.1), "front"),
                                                               ((0.85, -0.1), (0.7, -0.55), "front"))),
    "thief_fly": dict(lower="pants", legs=(((-0.2, 1.55), (-0.7, 1.95), (-0.85, 2.6)),
                                           ((0.2, 1.55), (0.6, 2.2), (0.45, 2.85))),
                      arms=(((-0.95, -0.05), (-1.3, -0.5), "front"), ((0.95, 0.0), (1.35, -0.4), "front"))),
    "thief_sneak": dict(lower="pants", legs=(((-0.2, 1.55), (-0.45, 2.05), (-0.3, 2.75)),
                                             ((0.2, 1.55), (0.5, 1.95), (0.65, 2.55))),
                        arms=(((-0.75, 0.6), (-0.45, 0.25), "front"), ((0.85, 0.55), (1.15, 0.3), "front"))),
    "thief_grab": dict(lower="pants", legs=(((-0.2, 1.55), (-0.35, 2.1), (-0.4, 2.8)),
                                            ((0.2, 1.55), (0.45, 2.1), (0.55, 2.8))),
                       arms=(((-0.8, 0.5), (-1.25, 0.75), "front"), ((-0.4, 0.6), (-1.05, 0.85), "front"))),
    "thief_pull": dict(lower="pants", legs=(((-0.2, 1.55), (-0.55, 2.05), (-0.95, 2.6)),
                                            ((0.2, 1.55), (0.4, 2.15), (0.7, 2.8))),
                       arms=(((-0.75, 0.45), (-1.3, 0.45), "front"), ((-0.4, 0.55), (-1.2, 0.6), "front"))),
    "thief_wet": dict(lower="pants", legs=(((-0.2, 1.55), (-0.55, 1.6), (-0.7, 2.15)),
                                           ((0.2, 1.55), (0.55, 1.6), (0.7, 2.15))),
                      arms=(((-0.75, 0.7), (-0.75, 1.3), "front"), ((0.75, 0.7), (0.75, 1.3), "front"))),
    "thief_take": dict(lower="pants", legs=(((-0.2, 1.55), (-0.55, 1.6), (-0.7, 2.15)),
                                            ((0.2, 1.55), (0.55, 1.6), (0.7, 2.15))),
                       arms=(((-0.75, 0.7), (-0.75, 1.3), "front"), ((0.75, 0.6), (0.95, 0.15), "front"))),
    "jung_spread": dict(lower="pants", legs=(((-0.22, 1.4), (-1.05, 1.65), (-1.15, 2.4)),
                                             ((0.22, 1.4), (1.05, 1.65), (1.15, 2.4))),
                        arms=(((-0.95, 0.15), (-1.45, -0.05), "back"), ((0.95, 0.15), (1.45, -0.05), "back"))),
    "jung_straight": dict(lower="pants", legs=(((-0.15, 1.4), (-0.18, 1.7), (-0.18, 2.4)),
                                               ((0.15, 1.4), (0.18, 1.7), (0.18, 2.4))),
                          arms=(((-0.5, 0.75), (-0.2, 1.25), "front"), ((0.5, 0.75), (0.2, 1.25), "front"))),
    "musk_laugh": dict(lower="pants", legs=(((-0.35, 1.6), (-0.4, 2.3), (-0.45, 3.0)),
                                            ((0.35, 1.6), (0.4, 2.3), (0.45, 3.0))),
                       arms=(((-1.25, 0.75), (-0.75, 1.15), "front"), ((1.25, 0.75), (0.75, 1.15), "front"))),
    "musk_point": dict(lower="pants", legs=(((-0.35, 1.6), (-0.4, 2.3), (-0.45, 3.0)),
                                            ((0.35, 1.6), (0.4, 2.3), (0.45, 3.0))),
                       arms=(((-1.25, 0.75), (-0.75, 1.15), "front"), ((1.4, 0.3), (1.6, -0.2), "front"))),
    "musk_shock": dict(lower="pants", legs=(((-0.35, 1.6), (-0.4, 2.3), (-0.45, 3.0)),
                                            ((0.35, 1.6), (0.4, 2.3), (0.45, 3.0))),
                       arms=(((-1.3, 0.4), (-0.6, -0.1), "front"), ((1.3, 0.4), (0.6, -0.1), "front"))),
    "aw_oma": dict(lower="skirt_sit", arms=(((-0.6, 0.85), (-0.25, 1.08), "front"),
                                            ((0.75, 1.05), (1.2, 0.1), "fist"))),
    "aw_oma_win": dict(lower="skirt_sit", arms=(((-0.6, 0.85), (-0.25, 1.08), "front"),
                                                ((0.9, 0.95), (1.7, 1.0), "fist"))),
    "aw_musk": dict(lower="pants", legs=(((-0.35, 1.6), (-0.4, 2.3), (-0.45, 3.0)), ((0.35, 1.6), (0.4, 2.3), (0.45, 3.0))),
                    arms=(((-1.35, 1.0), (-1.3, 0.0), "fist"), ((1.2, 0.8), (0.9, 1.1), "front"))),
    "aw_musk_lose": dict(lower="pants", legs=(((-0.35, 1.6), (-0.4, 2.3), (-0.45, 3.0)),
                                              ((0.35, 1.6), (0.4, 2.3), (0.45, 3.0))),
                         arms=(((-1.2, 0.95), (-0.65, 1.1), "fist"), ((1.25, 0.4), (1.5, -0.1), "front"))),
    "musk_run": dict(lower="pants", legs=(((-0.35, 1.6), (-0.9, 2.1), (-1.2, 2.7)), ((0.35, 1.6), (0.9, 2.0), (1.0, 2.8))),
                     arms=(((-1.3, 0.4), (-0.6, -0.1), "front"), ((1.3, 0.4), (0.6, -0.1), "front"))),
    "jung_offer": dict(lower="pants", legs=(((-0.2, 1.45), (-0.22, 2.15), (-0.24, 2.85)),
                                            ((0.2, 1.45), (0.22, 2.15), (0.24, 2.85))),
                       arms=(((-0.85, 0.5), (-1.3, 0.8), "front"), ((0.6, 0.75), (0.55, 1.35), "front"))),
    "kid_stand": dict(lower="pants", legs=(((-0.18, 1.2), (-0.2, 1.7), (-0.22, 2.2)), ((0.18, 1.2), (0.2, 1.7), (0.22, 2.2))),
                      arms=(((-0.55, 0.6), (-0.5, 1.05), "front"), ((0.55, 0.6), (0.5, 1.05), "front"))),
    "kid_desk": dict(lower="pants", legs=(((-0.18, 1.2), (-0.2, 1.7), (-0.22, 2.2)), ((0.18, 1.2), (0.2, 1.7), (0.22, 2.2))),
                     arms=(((-0.6, 0.75), (-0.3, 0.95), "front"), ((0.6, 0.75), (0.3, 0.95), "front"))),
    "kid_laugh": dict(lower="pants", legs=(((-0.18, 1.2), (-0.2, 1.7), (-0.22, 2.2)), ((0.18, 1.2), (0.2, 1.7), (0.22, 2.2))),
                      arms=(((-0.6, 0.6), (-0.15, 0.85), "front"), ((0.6, 0.6), (0.15, 0.85), "front"))),
    "kid_cheer": dict(lower="pants", legs=(((-0.18, 1.2), (-0.3, 1.7), (-0.35, 2.2)), ((0.18, 1.2), (0.3, 1.7), (0.35, 2.2))),
                      arms=(((-0.75, 0.0), (-0.7, -0.6), "front"), ((0.75, 0.0), (0.7, -0.6), "front"))),
    "kid_throw": dict(lower="pants", legs=(((-0.18, 1.2), (-0.2, 1.7), (-0.22, 2.2)), ((0.18, 1.2), (0.2, 1.7), (0.22, 2.2))),
                      arms=(((-0.6, 0.75), (-0.3, 0.95), "front"), ((0.75, 0.0), (0.55, -0.55), "front"))),
    "kid_phone": dict(lower="pants", legs=(((-0.18, 1.2), (-0.2, 1.7), (-0.22, 2.2)), ((0.18, 1.2), (0.2, 1.7), (0.22, 2.2))),
                      arms=(((-0.55, 0.7), (-0.12, 0.85), "front"), ((0.55, 0.7), (0.12, 0.85), "front"))),
    "kid_reach": dict(lower="pants", legs=(((-0.18, 1.2), (-0.2, 1.7), (-0.22, 2.2)), ((0.18, 1.2), (0.2, 1.7), (0.22, 2.2))),
                      arms=(((-0.6, 0.6), (-0.6, 1.05), "front"), ((0.7, 0.2), (0.95, -0.25), "front"))),
    "rowdy_grab": dict(lower="pants", legs=(((-0.18, 1.2), (-0.25, 1.7), (-0.3, 2.25)), ((0.18, 1.2), (0.25, 1.7), (0.3, 2.25))),
                       arms=(((-0.65, 0.7), (-0.35, 1.0), "front"), ((0.8, 0.05), (0.75, -0.5), "front"))),
    "rowdy_point": dict(lower="pants", legs=(((-0.18, 1.2), (-0.25, 1.7), (-0.3, 2.25)), ((0.18, 1.2), (0.25, 1.7), (0.3, 2.25))),
                        arms=(((-0.75, 0.35), (-1.15, 0.2), "front"), ((0.8, 0.05), (0.75, -0.5), "front"))),
    "rowdy_fly": dict(lower="pants", legs=(((-0.18, 1.25), (-0.6, 1.6), (-0.75, 2.1)), ((0.18, 1.25), (0.5, 1.8), (0.4, 2.3))),
                      arms=(((-0.85, -0.05), (-1.15, -0.45), "front"), ((0.85, 0.0), (1.2, -0.35), "front"))),
    "rowdy_sit": dict(lower="pants", legs=(((-0.18, 1.25), (-0.5, 1.3), (-0.65, 1.75)), ((0.18, 1.25), (0.5, 1.3), (0.65, 1.75))),
                      arms=(((-0.65, 0.6), (-0.7, 1.15), "front"), ((0.65, 0.6), (0.7, 1.15), "front"))),
    "rowdy_take": dict(lower="pants", legs=(((-0.18, 1.25), (-0.5, 1.3), (-0.65, 1.75)), ((0.18, 1.25), (0.5, 1.3), (0.65, 1.75))),
                       arms=(((-0.65, 0.6), (-0.7, 1.15), "front"), ((0.7, 0.55), (0.9, 0.15), "front"))),
    "oma_grab": dict(lower="skirt_stand", arms=(((-0.75, 0.45), (-1.25, 0.3), "front"),
                                                ((-0.4, 0.55), (-1.1, 0.4), "front"))),
    "oma_throw": dict(lower="skirt_stand", arms=(((-0.6, 0.0), (-0.9, -0.55), "front"),
                                                 ((0.45, 0.0), (0.2, -0.6), "front"))),
    "oma_knit_stand": dict(lower="skirt_stand", arms=(((-0.6, 0.85), (-0.12, 1.1), "front"),
                                                      ((0.6, 0.85), (0.12, 1.1), "front"))),
    "oma_catch": dict(lower="skirt_stand", arms=(((-0.6, 0.85), (-0.12, 1.1), "front"),
                                                 ((0.8, 0.3), (1.05, -0.2), "front"))),
    "oma_take_phone": dict(lower="skirt_stand", arms=(((-0.62, 0.7), (-0.6, 1.25), "front"),
                                                      ((0.75, 0.45), (1.1, 0.35), "front"))),
    "oma_show_phone": dict(lower="skirt_stand", arms=(((-0.62, 0.7), (-0.6, 1.25), "front"),
                                                      ((0.75, 0.2), (0.75, -0.25), "front"))),
    "b_stand": dict(lower="pants", legs=(((-0.18, 1.3), (-0.2, 2.0), (-0.22, 2.7)), ((0.18, 1.3), (0.2, 2.0), (0.22, 2.7))), arms=(((-0.62, 0.7), (-0.58, 1.3), "front"), ((0.62, 0.7), (0.58, 1.3), "front"))),
    "b_hold": dict(lower="pants", legs=(((-0.18, 1.3), (-0.2, 2.0), (-0.22, 2.7)), ((0.18, 1.3), (0.2, 2.0), (0.22, 2.7))), arms=(((-0.62, 0.7), (-0.58, 1.3), "front"), ((0.85, 0.05), (0.8, -0.55), "fist"))),
    "b_push": dict(lower="pants", legs=(((-0.18, 1.3), (-0.35, 1.95), (-0.45, 2.7)), ((0.18, 1.3), (0.3, 2.0), (0.3, 2.7))),
                   arms=(((0.7, 0.35), (1.1, 0.4), "front"), ((-0.1, 0.6), (0.85, 0.55), "front"))),
    "b_point": dict(lower="pants", legs=(((-0.18, 1.3), (-0.2, 2.0), (-0.22, 2.7)), ((0.18, 1.3), (0.2, 2.0), (0.22, 2.7))), arms=(((-0.8, 0.35), (-1.2, 0.2), "front"), ((0.62, 0.7), (0.58, 1.3), "front"))),
    "b_grab": dict(lower="pants", legs=(((-0.18, 1.3), (-0.2, 2.0), (-0.22, 2.7)), ((0.18, 1.3), (0.2, 2.0), (0.22, 2.7))), arms=(((-0.8, 0.45), (-1.25, 0.35), "fist"), ((0.6, 0.75), (0.2, 0.55), "fist"))),
    "b_trip": dict(lower="pants", legs=(((-0.18, 1.3), (-0.7, 1.7), (-1.1, 1.95)), ((0.18, 1.3), (-0.4, 1.85), (-0.85, 2.2))),
                   arms=(((-0.75, 0.0), (-0.7, -0.55), "front"), ((0.75, 0.0), (0.7, -0.55), "front"))),
    "b_fall": dict(lower="pants", legs=(((-0.15, 1.3), (-0.15, 2.0), (-0.12, 2.7)), ((0.15, 1.3), (0.15, 2.0), (0.12, 2.7))),
                   arms=(((-0.85, -0.05), (-1.1, -0.5), "front"), ((0.85, -0.05), (1.1, -0.5), "front"))),
    "b_run": dict(lower="pants", legs=(((-0.18, 1.3), (-0.6, 1.8), (-0.9, 2.3)), ((0.18, 1.3), (0.55, 1.75), (0.6, 2.5))),
                  arms=(((-0.75, 0.4), (-0.4, 0.0), "fist"), ((0.75, 0.6), (1.0, 1.0), "fist"))),
    "oma_ready": dict(lower="skirt_stand", legs=(((-0.2, 1.35), (-0.21, 2.1), (-0.21, 2.7)), ((0.2, 1.35), (0.21, 2.1), (0.21, 2.7))), arms=(((-0.62, 0.7), (-0.5, 1.15), "front"), ((0.62, 0.7), (0.5, 1.15), "front"))),
    "oma_grip": dict(lower="skirt_stand", legs=(((-0.2, 1.35), (-0.21, 2.1), (-0.21, 2.7)), ((0.2, 1.35), (0.21, 2.1), (0.21, 2.7))), arms=(((0.05, 0.6), (0.7, 0.5), "grip"), ((0.75, 0.3), (1.0, 0.1), "grip"))),
    "oma_step": dict(lower="skirt_stand", legs=(((-0.2, 1.35), (-0.3, 2.1), (-0.35, 2.7)), ((0.2, 1.35), (0.42, 2.05), (0.52, 2.68))),
                     arms=(((0.1, 0.6), (0.85, 0.45), "grip"), ((0.8, 0.3), (1.1, 0.15), "grip"))),
    "oma_sweep": dict(lower="skirt_stand", legs=(((-0.2, 1.35), (-0.34, 2.05), (-0.4, 2.7)), ((0.2, 1.35), (0.68, 1.95), (1.12, 2.42))),
                      arms=(((0.0, 0.7), (0.72, 0.68), "grip"), ((0.75, 0.4), (0.95, 0.38), "grip"))),
    "oma_pull": dict(lower="skirt_stand", legs=(((-0.2, 1.35), (-0.3, 2.08), (-0.34, 2.7)), ((0.2, 1.35), (0.45, 2.05), (0.6, 2.66))),
                     arms=(((-0.3, 0.8), (0.25, 1.0), "grip"), ((0.6, 0.6), (0.6, 0.85), "grip"))),
    "oma_knock": dict(lower="skirt_stand", legs=(((-0.2, 1.35), (-0.21, 2.1), (-0.21, 2.7)), ((0.2, 1.35), (0.21, 2.1), (0.21, 2.7))), arms=(((-0.62, 0.7), (-0.6, 1.25), "front"), ((0.85, 0.3), (1.1, -0.05), "fist"))),
    "oma_give_bag": dict(lower="skirt_stand", legs=(((-0.2, 1.35), (-0.21, 2.1), (-0.21, 2.7)), ((0.2, 1.35), (0.21, 2.1), (0.21, 2.7))), arms=(((-0.62, 0.7), (-0.6, 1.25), "front"), ((-0.55, 0.55), (-1.05, 0.5), "front"))),
    "pass_stand": dict(lower="pants", legs=STAND_LEGS, arms=(((-0.6, 0.7), (-0.55, 1.25), "front"),
                                                             ((0.6, 0.7), (0.55, 1.25), "front"))),
    "pass_shock": dict(lower="pants", legs=STAND_LEGS, arms=(((-0.7, 0.4), (-0.3, -0.05), "front"),
                                                             ((0.7, 0.4), (0.3, -0.05), "front"))),
}


def pose_dict(who, pose):
    if isinstance(pose, str):
        return POSES[pose]
    base = dict(POSES[pose[0]])
    for k, v in pose[1:]:
        base[k] = v
    return base


# ------------------------------------------------------------------ Taube
@lru_cache(maxsize=64)
def pigeon(size, flap=-1, facing=1, peck=0):
    """flap: -1 = sitzt, sonst Flügelphase 0..3."""
    S = int(size * 2.2)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cx, cy = S / 2, S * 0.55
    body = (150, 156, 172)
    if flap >= 0:
        tip = [-0.95, -0.35, 0.35, -0.2][flap % 4]
        for sx in (-1, 1):
            poly(im, [(cx - size * 0.15, cy - size * 0.12), (cx + size * 0.2, cy - size * 0.12),
                      (cx + sx * size * 1.05, cy + tip * size), (cx + sx * size * 0.55, cy + tip * size * 0.4 + size * 0.1)],
                 (176, 182, 198), radius=size * 0.1, amb=0.55)
    # Schwanz
    poly(im, [(cx - facing * size * 0.35, cy), (cx - facing * size * 0.85, cy + size * 0.15),
              (cx - facing * size * 0.8, cy + size * 0.32), (cx - facing * size * 0.3, cy + size * 0.2)],
         (110, 116, 130), radius=size * 0.08, amb=0.5)
    ell(im, cx, cy, size * 0.5, size * 0.34, body, amb=0.5, spec=0.2, radius=size * 0.25)
    # Flügel (gefaltet)
    if flap < 0:
        ell(im, cx - facing * size * 0.08, cy - size * 0.02, size * 0.34, size * 0.2, (170, 176, 192), amb=0.5)
        d = ImageDraw.Draw(im)
        for k in range(2):
            x = cx - facing * size * (0.05 + 0.13 * k)
            d.line([(x, cy - size * 0.12), (x - facing * size * 0.06, cy + size * 0.12)], fill=(60, 64, 76),
                   width=max(2, int(size * 0.06)))
    hx = cx + facing * size * 0.42
    hy = cy - size * 0.32 + peck * size * 0.35
    ell(im, cx + facing * size * 0.3, cy - size * 0.16 + peck * size * 0.15, size * 0.2, size * 0.2, (110, 150, 140),
        amb=0.5, spec=0.4)  # schillernder Hals
    ell(im, hx, hy, size * 0.18, size * 0.17, (140, 146, 165), amb=0.5, spec=0.25)
    d = ImageDraw.Draw(im)
    d.polygon([(hx + facing * size * 0.14, hy - size * 0.02), (hx + facing * size * 0.32, hy + size * 0.04),
               (hx + facing * size * 0.14, hy + size * 0.07)], fill=(230, 160, 70))
    d.ellipse([hx + facing * size * 0.02 - size * 0.05, hy - size * 0.07, hx + facing * size * 0.02 + size * 0.05,
               hy + size * 0.03], fill=(240, 120, 30))
    d.ellipse([hx + facing * size * 0.02 - size * 0.025, hy - size * 0.045, hx + facing * size * 0.02 + size * 0.025,
               hy + size * 0.005], fill=(20, 20, 20))
    if flap < 0:
        for sx in (-0.12, 0.1):
            d.line([(cx + sx * size, cy + size * 0.3), (cx + sx * size, cy + size * 0.5)], fill=(220, 110, 110),
                   width=max(2, int(size * 0.06)))
    return im
