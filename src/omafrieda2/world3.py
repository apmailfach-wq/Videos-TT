"""Realistischer Schulhof für Folge 2 (neu): Betonbau, Asphalt mit Rissen, Graffiti, Fahrradständer,
Dixi-Klos (Tür öffnet/schließt, FREI/BESETZT) und ein Zettel 'Toiletten defekt'."""
import math
import random
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "omafrieda"))
from gfx import (F_BLACK, F_HAND, F_INTER, H, W, ell, font, gradient, limb, paste_c, poly, rrect,  # noqa: E402
                 soft_shadow)

K = 2
GROUND_Y = 1010


@lru_cache(maxsize=1)
def yard3_static():
    rnd = random.Random(11)
    c = gradient(W * K, H * K, [(0, (150, 190, 228)), (0.12, (196, 214, 232)), (0.121, (196, 190, 178)),
                                (0.525, (186, 180, 168)), (0.526, (112, 112, 116)), (1.0, (92, 92, 98))])
    d = ImageDraw.Draw(c)
    # Wolken
    for (x, y, s) in ((160, 90, 1.0), (700, 60, 0.8)):
        for dx, dy, rr in ((0, 0, 70), (-70, 15, 50), (75, 12, 55)):
            ell(c, (x + dx * s) * K, (y + dy * s) * K, rr * s * K, rr * s * 0.6 * K, (246, 248, 252), amb=0.9)
    # Bäume hinter dem Gebäude
    for x in (40, 1040):
        for dx, dy, r in ((0, 0, 120), (60, 40, 90)):
            ell(c, (x + dx) * K, (250 + dy) * K, r * K, r * K, (88, 128, 80), amb=0.55, spec=0.05)
    # Gebäude: Betonfassade mit Fensterbändern
    rrect(c, -20 * K, 228 * K, 1100 * K, 262 * K, 6 * K, (120, 118, 114), amb=0.6, spec=0.1)
    for row, y0 in enumerate((320, 600)):
        rrect(c, 0, (y0 - 14) * K, W * K, (y0 + 214) * K, 4 * K, (150, 146, 138), amb=0.7)
        for k in range(8):
            x0 = 10 + k * 134
            g = gradient(124 * K, 190 * K, [(0, (120, 150, 175)), (0.5, (160, 185, 205)), (1, (90, 110, 130))])
            c.alpha_composite(g, (int(x0 * K), int(y0 * K)))
            d.rectangle([x0 * K, y0 * K, (x0 + 124) * K, (y0 + 190) * K], outline=(70, 72, 76), width=4 * K)
            d.line([(x0 * K, (y0 + 60) * K), ((x0 + 124) * K, (y0 + 60) * K)], fill=(70, 72, 76), width=3 * K)
            d.polygon([((x0 + 10) * K, (y0 + 185) * K), ((x0 + 40) * K, (y0 + 185) * K), ((x0 + 110) * K, (y0 + 65) * K),
                       ((x0 + 80) * K, (y0 + 65) * K)], fill=(230, 240, 250, 40))
    # Eingang
    rrect(c, 420 * K, 860 * K, 660 * K, 1012 * K, 6 * K, (80, 84, 92), amb=0.6, spec=0.2)
    for x0 in (430, 545):
        g = gradient(105 * K, 140 * K, [(0, (120, 140, 160)), (1, (70, 85, 100))])
        c.alpha_composite(g, (x0 * K, 868 * K))
    rrect(c, 400 * K, 840 * K, 680 * K, 866 * K, 4 * K, (60, 60, 66), amb=0.6)
    d.text((540 * K, 824 * K), "GESAMTSCHULE", font=font(F_INTER, 30 * K), fill=(60, 60, 66), anchor="mm")
    # Fugen / Flecken
    arr = np.asarray(c).astype(np.int16)
    noise = np.random.default_rng(1).normal(0, 6, (H * K, W * K)).astype(np.int16)
    arr[..., :3] = np.clip(arr[..., :3] + noise[..., None], 0, 255)
    c = Image.fromarray(arr.astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(c)
    # Graffiti unten an der Wand
    tags = [((60, 900), (220, 60, 150), "YO"), ((240, 930), (60, 160, 220), "K1D"), ((720, 915), (250, 170, 40), "8B")]
    for (x, y), col, txt in tags:
        g = Image.new("RGBA", (300 * K, 120 * K), (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        gd.text((10 * K, 10 * K), txt, font=font(F_BLACK, 70 * K), fill=col + (210,), stroke_width=4 * K,
                stroke_fill=(30, 30, 30, 210))
        g = g.rotate(rnd.uniform(-8, 8), resample=Image.BICUBIC)
        c.alpha_composite(g, (x * K, (y - 40) * K))
    # Zettel "Toiletten defekt"
    paper = Image.new("RGBA", (230 * K, 160 * K), (250, 250, 244, 255))
    pd = ImageDraw.Draw(paper)
    pd.text((115 * K, 45 * K), "Toiletten defekt!", font=font(F_HAND, 34 * K), fill=(200, 30, 30), anchor="mm")
    pd.text((115 * K, 95 * K), "Bitte Dixi", font=font(F_HAND, 30 * K), fill=(30, 30, 30), anchor="mm")
    pd.text((115 * K, 130 * K), "benutzen →", font=font(F_HAND, 30 * K), fill=(30, 30, 30), anchor="mm")
    pd.rectangle([95 * K, 0, 135 * K, 12 * K], fill=(230, 230, 200, 200))
    paper = paper.rotate(-4, expand=True, resample=Image.BICUBIC)
    sh = Image.new("RGBA", paper.size, (0, 0, 0, 0))
    sh.putalpha(paper.getchannel("A").point(lambda v: int(v * 0.35)))
    c.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)), (712 * K, 702 * K))
    c.alpha_composite(paper, (700 * K, 690 * K))
    # Asphalt: Körnung, Risse, Gullydeckel, Blätter
    arr = np.asarray(c).astype(np.int16)
    gy = GROUND_Y * K
    n2 = np.random.default_rng(2).normal(0, 10, (H * K - gy, W * K)).astype(np.int16)
    arr[gy:, :, :3] = np.clip(arr[gy:, :, :3] + n2[..., None], 0, 255)
    c = Image.fromarray(arr.astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(c)
    for _ in range(7):
        x, y = rnd.uniform(50, 1030), rnd.uniform(1080, 1880)
        pts = [(x, y)]
        for _ in range(6):
            x += rnd.uniform(-40, 40)
            y += rnd.uniform(5, 35)
            pts.append((x, y))
        d.line([(px * K, py * K) for px, py in pts], fill=(60, 60, 64), width=2 * K)
    ell(c, 190 * K, 1760 * K, 70 * K, 22 * K, (80, 80, 86), amb=0.6, spec=0.2)
    for k in range(5):
        d.line([(140 * K, (1752 + k * 4) * K), (240 * K, (1752 + k * 4) * K)], fill=(60, 60, 66), width=K)
    for _ in range(40):
        x, y = rnd.uniform(0, W), rnd.uniform(1050, H)
        col = rnd.choice([(170, 110, 40), (200, 150, 50), (140, 90, 40)])
        d.ellipse([x * K, y * K, (x + 14) * K, (y + 7) * K], fill=col)
    # ausgeblichene Spielfeldlinie
    d.arc([-300 * K, 1350 * K, 1380 * K, 2400 * K], 200, 340, fill=(200, 200, 190), width=6 * K)
    # Fahrradständer links
    for k in range(4):
        x = 30 + k * 70
        d.arc([x * K, 980 * K, (x + 50) * K, 1080 * K], 180, 360, fill=(160, 165, 170), width=6 * K)
    for k, col in enumerate(((200, 40, 40), (40, 90, 180))):
        bx = 50 + k * 110
        for wx in (bx, bx + 80):
            d.ellipse([(wx - 32) * K, (1010) * K, (wx + 32) * K, (1074) * K], outline=(30, 30, 34), width=5 * K)
        d.line([(bx * K, 1042 * K), ((bx + 40) * K, 1005 * K), ((bx + 80) * K, 1042 * K)], fill=col, width=6 * K)
        d.line([((bx + 40) * K, 1005 * K), ((bx + 34) * K, 985 * K)], fill=col, width=6 * K)
    return c


# ------------------------------------------------------------------ Dixi-Klo (3/4-Ansicht, Tür auf der linken Seite)
DIXI = [dict(fx=900, G=1505, s=1.0), dict(fx=690, G=1335, s=0.82)]


@lru_cache(maxsize=64)
def dixi_layers(i, door_q, red):
    """Gibt (back, front, origin) zurück; door_q 0..6 (0 = zu, 6 = ganz offen)."""
    p = DIXI[i]
    s = p["s"]
    fw, sw, h, rec = 110 * s, 160 * s, 330 * s, 35 * s
    pad = 120 * s
    Wd, Hd = int((fw + sw + pad * 2) * K), int((h + rec + 70 * s + pad) * K)
    ox, oy = p["fx"] - sw - pad, p["G"] - h - rec - 60 * s
    X = lambda x: (x - ox) * K  # noqa
    Y = lambda y: (y - oy) * K  # noqa
    fx, G = p["fx"], p["G"]
    blue, blue2 = (38, 104, 186), (30, 86, 160)
    back = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0))
    front = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0))
    soft_shadow(back, X(fx - sw * 0.4), Y(G + 6), sw * 0.9 * K, 22 * s * K, 0.45)
    # Seitenwand (links) mit Türöffnung
    side = [(X(fx - sw), Y(G - rec)), (X(fx), Y(G)), (X(fx), Y(G - h)), (X(fx - sw), Y(G - rec - h * 0.94))]
    poly(back, side, blue2, radius=8 * K, amb=0.55, spec=0.1)
    # dunkles Innere
    m = 0.1
    def door_pt(u, v):  # u: 0 links (hinten) .. 1 rechts (vorne); v: 0 unten .. 1 oben
        x = fx - sw + sw * u
        yb = (G - rec) + rec * u
        yt = (G - rec - h * 0.94) + (h * 0.94 - h + rec) * u + 0  # Oberkante
        yt = (G - rec - h * 0.94) * (1 - u) + (G - h) * u
        return X(x), Y(yb + (yt - yb) * v)
    opening = [door_pt(0.12, 0.03), door_pt(0.9, 0.03), door_pt(0.9, 0.82), door_pt(0.12, 0.82)]
    ImageDraw.Draw(back).polygon(opening, fill=(28, 30, 36))
    # Klobrille im Inneren
    cx, cy = door_pt(0.55, 0.2)
    ell(back, cx, cy, 34 * s * K, 14 * s * K, (225, 225, 230), amb=0.7)
    ell(back, cx, cy, 20 * s * K, 7 * s * K, (40, 40, 46), amb=0.6)
    # Vorderwand
    fr = [(X(fx), Y(G)), (X(fx + fw), Y(G - rec * 0.5)), (X(fx + fw), Y(G - h - rec * 0.4)), (X(fx), Y(G - h))]
    poly(front, fr, blue, radius=8 * K, amb=0.6, spec=0.15)
    fd = ImageDraw.Draw(front)
    fd.text(((X(fx) + X(fx + fw)) / 2, Y(G - h * 0.55)), "WC", font=font(F_BLACK, int(40 * s * K)),
            fill=(250, 250, 250), anchor="mm")
    for k in range(4):
        yy = G - h * 0.9 + k * 10 * s
        fd.line([(X(fx + 15 * s), Y(yy)), (X(fx + fw - 15 * s), Y(yy - 3 * s))], fill=(20, 50, 100), width=int(3 * s * K))
    # Dach
    roof = [(X(fx - sw - 8 * s), Y(G - rec - h * 0.94 - 4 * s)), (X(fx), Y(G - h - 6 * s)),
            (X(fx + fw + 8 * s), Y(G - h - rec * 0.4 - 6 * s)), (X(fx + fw * 0.4), Y(G - h - rec * 1.3 - 30 * s)),
            (X(fx - sw * 0.6), Y(G - rec - h - 40 * s))]
    poly(front, roof, (238, 240, 244), radius=10 * K, amb=0.7, spec=0.2)
    # Rahmen um die Türöffnung (liegt vor der Figur)
    frame_pts = [door_pt(0.08, 0.0), door_pt(0.94, 0.0), door_pt(0.94, 0.86), door_pt(0.08, 0.86)]
    fd.line(frame_pts + [frame_pts[0]], fill=(24, 70, 140), width=int(8 * s * K), joint="curve")
    # Tür
    ang = door_q / 6.0  # 0 zu .. 1 offen
    if ang < 0.98:
        hinge_b, hinge_t = door_pt(0.12, 0.03), door_pt(0.12, 0.82)
        far_b, far_t = door_pt(0.9, 0.03), door_pt(0.9, 0.82)
        # offene Tür klappt zur Kamera nach links
        open_b = (hinge_b[0] - 110 * s * K * ang, hinge_b[1] + 30 * s * K * ang)
        open_t = (hinge_t[0] - 110 * s * K * ang, hinge_t[1] + 18 * s * K * ang)
        eb = (far_b[0] + (open_b[0] - far_b[0]) * ang, far_b[1] + (open_b[1] - far_b[1]) * ang)
        et = (far_t[0] + (open_t[0] - far_t[0]) * ang, far_t[1] + (open_t[1] - far_t[1]) * ang)
        door = [hinge_b, eb, et, hinge_t]
        poly(front, door, (44, 116, 200), radius=6 * K, amb=0.6, spec=0.2)
        if ang < 0.3:
            hx, hy = door_pt(0.8, 0.42)
            rrect(front, hx - 22 * s * K, hy - 12 * s * K, hx + 22 * s * K, hy + 12 * s * K, 4 * K,
                  (210, 40, 40) if red else (40, 170, 70), amb=0.8)
            ImageDraw.Draw(front).text((hx, hy), "BESETZT" if red else "FREI", font=font(F_BLACK, int(7 * s * K)),
                                       fill=(255, 255, 255), anchor="mm")
    else:
        hinge_b, hinge_t = door_pt(0.12, 0.03), door_pt(0.12, 0.82)
        door = [hinge_b, (hinge_b[0] - 110 * s * K, hinge_b[1] + 30 * s * K),
                (hinge_t[0] - 110 * s * K, hinge_t[1] + 18 * s * K), hinge_t]
        poly(front, door, (44, 116, 200), radius=6 * K, amb=0.6, spec=0.2)
    return back, front, (ox, oy)


def draw_dixi(f, v, i, layer, door=1.0, red=False, shake=0.0):
    back, front, (ox, oy) = dixi_layers(i, int(round(min(max(door, 0.0), 1.0) * 6)), bool(red))
    im = back if layer == "back" else front
    sx, sy = v.p(ox + shake, oy)
    sc = v.z / K
    im2 = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.BILINEAR)
    paste_c(f, im2, sx + im2.width / 2, sy + im2.height / 2)


def dixi_door_center(i):
    p = DIXI[i]
    s = p["s"]
    return p["fx"] - 160 * s * 0.5, p["G"] - 18 * s - 330 * s * 0.4


def natural(f, T, amt=1.0):
    """Natürlicher Look: leicht entsättigt, weiches Licht, feines Filmkorn."""
    from gfx import grade, vignette
    f = grade(f, sat=0.93, contrast=1.04, bright=1.0, warm=0.08 * amt)
    rnd = np.random.default_rng(int(T * 30) + 7)
    n = rnd.normal(0, 5, (H // 2, W // 2)).astype(np.float32)
    n = np.repeat(np.repeat(n, 2, 0), 2, 1)
    a = np.asarray(f.convert("RGB"), np.float32) + n[..., None]
    f = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")
    f.alpha_composite(vignette(0.3))
    return f
