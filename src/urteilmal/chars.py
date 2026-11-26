"""2D-Comic-Figuren für URTEIL MAL! – gezeichnet mit Pillow (2x Supersampling, kräftige Konturen, Cel-Shading)."""
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
F_HAND = str(ROOT / "fonts" / "Caveat_700Bold.ttf")
F_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"

SS = 2                       # Supersampling
SW, SH = 720, 1400           # Sprite-Größe in Welt-Pixeln
HX, HY = 360, 300            # Kopfmitte im Sprite
INK = (34, 24, 30)
OUT = 7                      # Konturbreite (Welt-Pixel)


def S(v):
    return int(round(v * SS))


def P(pts):
    return [(S(x), S(y)) for x, y in pts]


def box(cx, cy, rx, ry):
    return [S(cx - rx), S(cy - ry), S(cx + rx), S(cy + ry)]


def darker(c, f=0.78):
    return tuple(int(v * f) for v in c[:3])


def lighter(c, f=0.25):
    return tuple(int(v + (255 - v) * f) for v in c[:3])


@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, size)


# ------------------------------------------------------------------ Figuren-Definitionen
CHARS = {
    "richard": dict(skin=(234, 182, 148), head=(120, 168), jaw=0.9, eye_dx=50, eye_dy=-4,
                    body=(28, 28, 34), body_w=360, hair=(206, 206, 212), brow=(70, 66, 66)),
    "klaus": dict(skin=(226, 168, 124), head=(126, 160), jaw=0.97, eye_dx=50, eye_dy=-10,
                  body=(34, 44, 86), body_w=370, hair=(112, 66, 36), brow=(70, 40, 24)),
    "horst": dict(skin=(238, 184, 152), head=(130, 160), jaw=0.97, eye_dx=46, eye_dy=-22,
                  body=(134, 180, 234), body_w=440, hair=(104, 66, 40), brow=(70, 44, 30)),
    "dennis": dict(skin=(240, 204, 178), head=(124, 150), jaw=0.9, eye_dx=50, eye_dy=-6,
                   body=(30, 150, 90), body_w=270, hair=(110, 72, 40)),
    "sabine": dict(skin=(246, 206, 180), head=(120, 146), jaw=0.84, eye_dx=50, eye_dy=-4,
                   body=(250, 170, 200), body_w=320, hair=(244, 214, 120)),
}

# Augenlid-Höhe (0 offen … 1 zu) und Brauen (innen, außen) in Welt-Pixeln (positiv = höher)
EXPR = {
    "neutral": dict(lid=0.15, brow=(0, 0), mouth="flat"),
    "deadpan": dict(lid=0.45, brow=(-12, 2), mouth="flat"),
    "brow": dict(lid=0.45, brow=(-2, -2), brow_r=(18, 22), mouth="flat"),
    "tired": dict(lid=1.0, brow=(10, -8), mouth="frown"),
    "shock": dict(lid=0.0, brow=(22, 20), mouth="o", pupil=0.6),
    "twitch": dict(lid=0.5, brow=(-6, 6), mouth="flat", twitch=True),
    "shout": dict(lid=0.0, brow=(-14, 12), mouth="frown"),
    "upset": dict(lid=0.05, brow=(-10, 8), mouth="frown"),
    "disgust": dict(lid=0.35, brow=(-12, 4), mouth="wavy"),
    "nervous": dict(lid=0.0, brow=(14, -6), mouth="wavy", pupil=0.7),
    "bored": dict(lid=0.55, brow=(0, 0), mouth="chew"),
    "smug": dict(lid=0.35, brow=(4, 10), brow_r=(16, 26), mouth="smirk"),
    "dramatic": dict(lid=0.0, brow=(12, 18), mouth="grin"),
    "outraged": dict(lid=0.0, brow=(-16, 10), mouth="frown"),
    "proud": dict(lid=0.3, brow=(8, 8), mouth="smile"),
    "longing": dict(lid=0.2, brow=(14, 4), mouth="o", pupil=1.1),
    "innocent": dict(lid=0.2, brow=(14, 8), mouth="smile"),
    "guilty": dict(lid=0.35, brow=(20, -4), mouth="wavy", pupil=0.9),
    "puzzled": dict(lid=0.25, brow=(10, 6), mouth="flat", pupil=0.95),
}

DEFAULT_EXPR = {"richard": "deadpan", "klaus": "smug", "horst": "puzzled", "dennis": "upset", "sabine": "bored"}


# ------------------------------------------------------------------ Körper
def draw_body(d, spec, name, pose):
    bw = spec["body_w"]
    col = spec["body"]
    top = HY + spec["head"][1] - 8
    # Hals
    d.rectangle(box(HX, top + 10, 40, 40), fill=darker(spec["skin"], 0.85))
    # Schultern / Torso
    pts = [(HX - bw / 2 + 40, top + 40), (HX + bw / 2 - 40, top + 40), (HX + bw / 2 + 20, top + 160),
           (HX + bw / 2 + 30, SH), (HX - bw / 2 - 30, SH), (HX - bw / 2 - 20, top + 160)]
    if name == "sabine":   # flauschige Teddyjacke
        d.polygon(P(pts), fill=col, outline=INK, width=S(OUT))
        for i in range(14):
            ang = i / 13
            x = HX - bw / 2 - 25 + ang * (bw + 50)
            d.ellipse(box(x, top + 70 + 40 * math.sin(ang * math.pi * 3), 26, 22), fill=lighter(col, 0.18))
    else:
        d.polygon(P(pts), fill=col, outline=INK, width=S(OUT))
    # Schattenseite
    sh = [(HX + bw / 2 - 60, top + 60), (HX + bw / 2 - 40, top + 40), (HX + bw / 2 + 20, top + 160),
          (HX + bw / 2 + 30, SH), (HX + bw / 2 - 40, SH)]
    if name != "dennis":
        d.polygon(P(sh), fill=darker(col, 0.82))

    if name != "dennis":
        for sx in (-1, 1):
            d.line(P([(HX + sx * (bw / 2 - 30), top + 130), (HX + sx * (bw / 2 - 10), SH)]), fill=darker(col, 0.6), width=S(5))
    if name == "richard":     # schwarze Robe, weißes Hemd, dunkle Krawatte, Samtbesatz
        d.polygon(P([(HX - 80, top + 36), (HX, top + 210), (HX + 80, top + 36)]), fill=(250, 250, 250), outline=INK, width=S(5))
        d.polygon(P([(HX - 40, top + 40), (HX, top + 70), (HX + 40, top + 40), (HX + 30, top + 20), (HX - 30, top + 20)]),
                  fill=(255, 255, 255), outline=INK, width=S(4))
        d.polygon(P([(HX - 16, top + 62), (HX + 16, top + 62), (HX + 24, top + 200), (HX, top + 230), (HX - 24, top + 200)]),
                  fill=(52, 56, 70), outline=INK, width=S(4))
        for sx in (-1, 1):     # Samtbesatz der Robe
            d.polygon(P([(HX + sx * 82, top + 36), (HX + sx * 120, top + 40), (HX + sx * 70, top + 330), (HX + sx * 36, top + 330),
                         (HX + sx * 8, top + 220)]), fill=(14, 14, 18), outline=INK, width=S(5))
        for k, x in enumerate((HX - 150, HX - 95, HX + 95, HX + 150)):   # Falten
            d.line(P([(x, top + 200), (x + (-14 if x < HX else 14), SH)]), fill=(66, 66, 78), width=S(5))
    elif name == "klaus":     # Navy-Anzug, weißes Hemd, knallblaue Krawatte, breite Revers
        d.polygon(P([(HX - 78, top + 34), (HX, top + 250), (HX + 78, top + 34)]), fill=(250, 250, 252), outline=INK, width=S(5))
        d.polygon(P([(HX - 18, top + 54), (HX + 18, top + 54), (HX + 28, top + 250), (HX, top + 290), (HX - 28, top + 250)]),
                  fill=(36, 96, 200), outline=INK, width=S(4))
        d.polygon(P([(HX - 18, top + 54), (HX + 18, top + 54), (HX + 12, top + 80), (HX - 12, top + 80)]), fill=(28, 74, 160), outline=INK, width=S(3))
        for sx in (-1, 1):     # Revers
            d.polygon(P([(HX + sx * 80, top + 34), (HX + sx * 128, top + 50), (HX + sx * 96, top + 150), (HX + sx * 120, top + 170),
                         (HX + sx * 30, top + 300)]), fill=(44, 56, 104), outline=INK, width=S(5))
        d.ellipse(box(HX - 60, top + 400, 9, 9), fill=(20, 24, 40), outline=INK, width=S(2))
        d.ellipse(box(HX - 60, top + 470, 9, 9), fill=(20, 24, 40), outline=INK, width=S(2))
    elif name == "horst":     # hellblaues Uniformhemd, offener Kragen, Schulterklappen, JUSTIZ-Patch
        for sx in (-1, 1):
            d.polygon(P([(HX + sx * 10, top + 40), (HX + sx * 90, top + 20), (HX + sx * 110, top + 90), (HX + sx * 20, top + 120)]),
                      fill=lighter(col, 0.3), outline=INK, width=S(5))
            d.polygon(P([(HX + sx * 120, top + 50), (HX + sx * 200, top + 70), (HX + sx * 196, top + 100), (HX + sx * 116, top + 82)]),
                      fill=darker(col, 0.8), outline=INK, width=S(4))
        d.line(P([(HX, top + 120), (HX, SH)]), fill=darker(col, 0.65), width=S(5))
        for k in range(4):
            d.ellipse(box(HX + 14, top + 170 + k * 120, 8, 8), fill=(240, 240, 240), outline=INK, width=S(2))
        d.rectangle([S(HX + 40), S(top + 190), S(HX + 190), S(top + 330)], outline=darker(col, 0.6), width=S(5))
        d.rounded_rectangle([S(HX + 46), S(top + 140), S(HX + 196), S(top + 186)], radius=S(6), fill=(22, 22, 26), outline=INK, width=S(3))
        d.text((S(HX + 121), S(top + 163)), "JUSTIZ", font=font(F_BLACK, S(30)), fill=(255, 255, 255), anchor="mm")
    elif name == "dennis":    # Fußballtrikot (kurze Ärmel, Saum) + graue Jogginghose
        hem = top + 360
        d.rectangle([S(HX - bw / 2 - 40), S(hem), S(HX + bw / 2 + 40), S(SH)], fill=(0, 0, 0, 0))
        d.polygon(P([(HX - bw / 2 - 10, hem), (HX + bw / 2 + 10, hem), (HX + bw / 2 - 6, SH), (HX + 8, SH), (HX, hem + 140),
                     (HX - 8, SH), (HX - bw / 2 + 6, SH)]), fill=(140, 140, 150), outline=INK, width=S(OUT))
        d.rectangle([S(HX - bw / 2 - 6), S(hem - 6), S(HX + bw / 2 + 6), S(hem + 30)], fill=(120, 120, 130), outline=INK, width=S(5))
        d.line(P([(HX - 20, hem + 30), (HX - 26, hem + 90)]), fill=(240, 240, 240), width=S(4))     # Kordel
        d.line(P([(HX + 20, hem + 30), (HX + 26, hem + 90)]), fill=(240, 240, 240), width=S(4))
        d.polygon(P([(HX - bw / 2 - 26, hem - 20), (HX + bw / 2 + 26, hem - 20), (HX + bw / 2 + 20, hem + 8), (HX - bw / 2 - 20, hem + 8)]),
                  fill=darker(col, 0.85), outline=INK, width=S(5))                                         # Trikot-Saum
        for sx in (-1, 1):   # lange Pulli-Ärmel mit Bündchen und Händen (rechts nur, wenn er nichts hochhält)
            if sx == 1 and pose:
                continue
            arm = [(HX + sx * (bw / 2 - 10), top + 70), (HX + sx * (bw / 2 + 40), top + 220), (HX + sx * (bw / 2 + 36), top + 380)]
            d.line(P(arm), fill=INK, width=S(66), joint="curve")
            d.line(P(arm), fill=col, width=S(52), joint="curve")
            cx_, cy_ = arm[-1]
            d.rounded_rectangle(box(cx_, cy_, 30, 14), radius=S(6), fill=darker(col, 0.8), outline=INK, width=S(4))
            d.ellipse(box(cx_, cy_ + 36, 26, 28), fill=spec["skin"], outline=INK, width=S(5))
        d.chord(box(HX, top + 36, 64, 34), 0, 180, fill=darker(col, 0.8), outline=INK, width=S(5))
        d.text((S(HX + 80), S(top + 200)), "7", font=font(F_BLACK, S(110)), fill=(255, 255, 255),
               stroke_width=S(4), stroke_fill=INK, anchor="mm")
    elif name == "sabine":
        d.line(P([(HX, top + 60), (HX, SH)]), fill=darker(col, 0.7), width=S(5))


def draw_arm(d, spec, side, pts, hand_open=False):
    col = spec["body"] if spec is not CHARS["sabine"] else spec["body"]
    d.line(P(pts), fill=INK, width=S(64), joint="curve")
    d.line(P(pts), fill=col, width=S(50), joint="curve")
    if spec is CHARS["dennis"]:   # Pulli-Bündchen am Handgelenk
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        L = math.hypot(x2 - x1, y2 - y1) or 1
        bx, by = x2 - (x2 - x1) / L * 34, y2 - (y2 - y1) / L * 34
        d.line(P([(bx, by), (x2 - (x2 - x1) / L * 14, y2 - (y2 - y1) / L * 14)]), fill=INK, width=S(66))
        d.line(P([(bx, by), (x2 - (x2 - x1) / L * 16, y2 - (y2 - y1) / L * 16)]), fill=darker(col, 0.8), width=S(54))
    hx, hy = pts[-1]
    d.ellipse(box(hx, hy, 34, 34), fill=spec["skin"], outline=INK, width=S(6))
    return hx, hy


# ------------------------------------------------------------------ Kopf
def head_mask(spec):
    rx, ry = spec["head"]
    m = Image.new("L", (S(SW), S(SH)), 0)
    md = ImageDraw.Draw(m)
    j = spec["jaw"]
    # Ei-Form: oben rund, unten etwas schmaler
    md.ellipse(box(HX, HY - ry * 0.12, rx, ry * 0.9), fill=255)
    md.ellipse(box(HX, HY + ry * 0.18, rx * j, ry * 0.82), fill=255)
    return m


def paste_shape(img, mask, color, shade=None):
    layer = Image.new("RGBA", img.size, color + (255,))
    img.paste(layer, (0, 0), mask)
    if shade:
        sh = ImageChops.offset(mask, -S(shade[0]), -S(shade[1]))
        crescent = ImageChops.subtract(mask, sh)
        img.paste(Image.new("RGBA", img.size, darker(color, 0.84) + (255,)), (0, 0), crescent)


def outline_mask(img, mask, width=OUT):
    from PIL import ImageFilter
    grown = mask.filter(ImageFilter.MaxFilter(2 * (S(width) // 2) + 1))
    ring = ImageChops.subtract(grown, mask)
    img.paste(Image.new("RGBA", img.size, INK + (255,)), (0, 0), ring)


def draw_eye(d, spec, cx, cy, lid, look, pupil=1.0, closed=False, rx=27, ry=31):
    skin = spec["skin"]
    if closed or lid >= 0.99:
        d.arc(box(cx, cy - 4, rx, ry * 0.6), 20, 160, fill=INK, width=S(6))
        return
    d.ellipse(box(cx, cy, rx, ry), fill=(255, 255, 255), outline=INK, width=S(5))
    px = cx + look[0] * rx * 0.45
    py = cy + look[1] * ry * 0.4
    pr = 12 * pupil
    d.ellipse(box(px, py, pr, pr), fill=INK)
    d.ellipse(box(px - pr * 0.35, py - pr * 0.35, pr * 0.3, pr * 0.3), fill=(255, 255, 255))
    if lid > 0.02:
        yline = cy - ry + 2 * ry * lid
        t = max(-1, min(1, (yline - cy) / ry))
        a1 = math.degrees(math.asin(t))
        a2 = 180 - a1
        d.chord(box(cx, cy, rx + 1, ry + 1), a2, a1 + 360, fill=skin)
        xw = rx * math.cos(math.radians(a1))
        d.line(P([(cx - xw - 3, yline), (cx + xw + 3, yline)]), fill=INK, width=S(6))


def draw_brow(d, cx, cy, side, inner, outer, color, thick=11):
    xi, xo = cx - side * 22, cx + side * 30
    d.line(P([(xi, cy - inner), (xo, cy - outer)]), fill=color, width=S(thick))


def draw_mouth(d, spec, kind, open_lv, mx, my, teeth=False, w=40):
    if open_lv > 0:
        h = 10 + 26 * open_lv
        ww = w * (0.8 + 0.25 * open_lv)
        d.ellipse(box(mx, my + h * 0.3, ww, h), fill=(110, 30, 40), outline=INK, width=S(5))
        d.ellipse(box(mx, my + h * 0.9, ww * 0.55, h * 0.35), fill=(220, 90, 100))
        if teeth:
            d.rectangle([S(mx - ww * 0.6), S(my + h * 0.3 - h + 6), S(mx + ww * 0.6), S(my + h * 0.3 - h + 18)], fill=(255, 255, 255))
        return
    if kind == "flat":
        d.line(P([(mx - w * 0.8, my), (mx + w * 0.8, my)]), fill=INK, width=S(7))
    elif kind == "frown":
        d.arc(box(mx, my + 18, w, 18), 200, 340, fill=INK, width=S(7))
    elif kind == "smile":
        d.arc(box(mx, my - 14, w, 22), 20, 160, fill=INK, width=S(7))
    elif kind == "smirk":
        d.line(P([(mx - w * 0.8, my + 4), (mx + w * 0.2, my + 4), (mx + w * 0.9, my - 12)]), fill=INK, width=S(7), joint="curve")
    elif kind == "grin":
        d.chord(box(mx, my - 6, w * 1.2, 30), 0, 180, fill=(255, 255, 255), outline=INK, width=S(6))
        d.line(P([(mx - w * 1.15, my - 6), (mx + w * 1.15, my - 6)]), fill=INK, width=S(5))
    elif kind == "o":
        d.ellipse(box(mx, my + 4, 14, 18), fill=(110, 30, 40), outline=INK, width=S(5))
    elif kind == "wavy":
        pts = [(mx - w + i * (2 * w / 6), my + (6 if i % 2 else -6)) for i in range(7)]
        d.line(P(pts), fill=INK, width=S(6), joint="curve")
    elif kind == "chew":
        d.line(P([(mx - w * 0.6, my), (mx + w * 0.6, my + 4)]), fill=INK, width=S(7))


def spiky(cx, cy, rx, ry, n, amp, a0=math.pi, a1=2 * math.pi, seed=1):
    import random as _r
    rnd = _r.Random(seed)
    pts = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        k = 1 + (amp * (0.6 + 0.4 * rnd.random()) if i % 2 else 0)
        pts.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
    return pts


def draw_hair_back(d, name, spec):
    rx, ry = spec["head"]
    c = spec["hair"]
    if name == "richard":   # wilde, zurückgekämmte graue Mähne
        pts = spiky(HX, HY - 10, rx + 26, ry + 6, 22, 0.16, math.pi * 0.86, math.pi * 2.14, 3)
        d.polygon(P(pts + [(HX + rx, HY + 60), (HX - rx, HY + 60)]), fill=c, outline=INK, width=S(OUT))
        for k in range(7):
            a = math.pi * (0.95 + k * 0.16)
            d.line(P([(HX + (rx - 10) * math.cos(a), HY - 10 + (ry - 20) * math.sin(a)),
                      (HX + (rx + 26) * math.cos(a), HY - 10 + (ry + 20) * math.sin(a))]), fill=darker(c, 0.7), width=S(4))
    elif name == "klaus":   # volle, wuschelige braune Haare
        pts = spiky(HX, HY - 34, rx + 30, ry * 0.86, 18, 0.2, math.pi * 0.92, math.pi * 2.08, 5)
        d.polygon(P(pts + [(HX + rx + 4, HY + 10), (HX - rx - 4, HY + 10)]), fill=c, outline=INK, width=S(OUT))
    elif name == "horst":   # wilde Büschel an den Seiten
        for sx in (-1, 1):
            pts = spiky(HX + sx * (rx - 6), HY - 4, 44, 84, 13, 0.25,
                        math.pi * (0.5 if sx < 0 else -0.5), math.pi * (1.5 if sx < 0 else 0.5), 7 + sx)
            d.polygon(P(pts), fill=c, outline=INK, width=S(6))
    if name == "sabine":
        d.ellipse(box(HX, HY - ry - 40, 78, 64), fill=c, outline=INK, width=S(OUT))      # Dutt
        for k in range(5):
            a = -0.6 + k * 0.3
            d.line(P([(HX + 60 * math.sin(a), HY - ry - 70), (HX + 110 * math.sin(a), HY - ry - 110 + 10 * k % 30)]),
                   fill=INK, width=S(5))
        d.ellipse(box(HX, HY - 10, rx + 16, ry + 6), fill=c, outline=INK, width=S(OUT))


def draw_hair_front(d, name, spec):
    rx, ry = spec["head"]
    c = spec["hair"]
    if name == "richard":   # nach hinten geschwungene Mähne, hohe Stirn
        d.chord(box(HX, HY - ry * 0.42, rx + 8, ry * 0.62), 180, 360, fill=c, outline=INK, width=S(OUT))
        d.rectangle([S(HX - rx + 4), S(HY - ry * 0.42 - 6), S(HX + rx - 4), S(HY - ry * 0.42 + 4)], fill=c)
        d.arc(box(HX, HY - ry * 0.42, rx + 2, 22), 0, 180, fill=INK, width=S(5))
        for k in range(6):
            x = HX - 80 + k * 32
            d.line(P([(x, HY - ry * 0.44), (x + 30, HY - ry * 0.98)]), fill=darker(c, 0.68), width=S(4))
        for k in range(3):     # Stirnfalten
            yy = HY - ry * 0.4 + k * 15
            d.arc(box(HX, yy + 20, 50 - k * 6, 12), 200, 340, fill=darker(spec["skin"], 0.68), width=S(4))
    elif name == "klaus":   # verwuschelte Tolle
        d.chord(box(HX, HY - ry * 0.4, rx + 6, ry * 0.66), 180, 360, fill=c, outline=INK, width=S(OUT))
        d.rectangle([S(HX - rx + 4), S(HY - ry * 0.4 - 6), S(HX + rx - 4), S(HY - ry * 0.4 + 4)], fill=c)
        d.polygon(P([(HX - 60, HY - ry * 0.42), (HX - 20, HY - ry * 0.25), (HX - 10, HY - ry * 0.45), (HX + 30, HY - ry * 0.3),
                     (HX + 20, HY - ry * 0.46)]), fill=c, outline=INK, width=S(5))
        d.arc(box(HX, HY - ry * 0.42, rx + 2, 18), 0, 60, fill=INK, width=S(5))
        d.arc(box(HX, HY - ry * 0.42, rx + 2, 18), 120, 180, fill=INK, width=S(5))
        for k in range(4):
            d.arc(box(HX - 40 + k * 40, HY - ry * 0.66, 40, 22), 200, 330, fill=darker(c, 0.6), width=S(4))
    elif name == "horst":   # Glatze, ein paar Haare oben, Glanz
        for k in range(4):
            x = HX - 30 + k * 18
            d.arc(box(x, HY - ry - 6, 14, 26), 180, 320, fill=c, width=S(4))
        d.ellipse(box(HX - 46, HY - ry + 46, 26, 9), fill=lighter(spec["skin"], 0.3))   # Glanz
    elif name == "dennis":  # wuschelig
        pts = []
        n = 11
        for i in range(n + 1):
            a = math.pi + i * math.pi / n
            r = (rx + 18) + (22 if i % 2 else -4)
            pts.append((HX + r * math.cos(a), HY - ry * 0.35 + (ry * 0.75 + (22 if i % 2 else 0)) * math.sin(a)))
        pts += [(HX + rx + 4, HY - ry * 0.2), (HX - rx - 4, HY - ry * 0.2)]
        d.polygon(P(pts), fill=c, outline=INK, width=S(OUT))
    elif name == "sabine":  # Pony/Strähnen
        d.chord(box(HX, HY - ry * 0.32, rx + 8, ry * 0.72), 180, 360, fill=c, outline=INK, width=S(OUT))
        d.line(P([(HX - rx + 14, HY - ry * 0.35), (HX - rx + 4, HY + 70)]), fill=c, width=S(16))


def draw_face_extras(d, name, spec, expr_name, mouth_open):
    rx, ry = spec["head"]
    ex = spec["eye_dx"]
    ey = HY + spec["eye_dy"]
    if name == "richard" and expr_name == "__glasses__":   # schmale, rechteckige Metallbrille, tief auf der Nase
        for sx in (-1, 1):
            d.rounded_rectangle([S(HX + sx * ex - 42), S(ey + 4), S(HX + sx * ex + 42), S(ey + 40)], radius=S(6),
                                outline=(40, 40, 46), width=S(6))
            d.line(P([(HX + sx * (ex + 42), ey + 12), (HX + sx * (rx - 2), ey + 4)]), fill=(40, 40, 46), width=S(5))
        d.arc(box(HX, ey + 20, 10, 8), 180, 360, fill=(40, 40, 46), width=S(5))
    if name in ("klaus", "dennis", "horst"):   # Bartschatten / Stoppeln
        layer = Image.new("RGBA", (S(SW), S(SH)), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        a = {"klaus": 60, "dennis": 70, "horst": 0}[name]
        ld.chord(box(HX, HY + ry * 0.3, rx * spec["jaw"] - 6, ry * 0.62), 0, 180, fill=(70, 50, 44, a))
        if name == "klaus":
            import random as _r
            rnd = _r.Random(4)
            for _ in range(160):
                ang = rnd.uniform(0.1, math.pi - 0.1)
                rr = rnd.uniform(0.55, 0.98)
                x = HX + (rx * spec["jaw"] - 14) * rr * math.cos(ang)
                y = HY + ry * 0.3 + ry * 0.6 * rr * math.sin(ang)
                ld.ellipse(box(x, y, 2.2, 2.2), fill=(60, 36, 24, 150))
        return layer
    return None


def draw_mustache(d, spec):
    c = (200, 80, 40)
    mx, my = HX, HY + 78
    d.polygon(P([(mx - 90, my + 40), (mx - 60, my - 8), (mx, my - 14), (mx + 60, my - 8), (mx + 90, my + 40),
                 (mx + 50, my + 20), (mx, my + 26), (mx - 50, my + 20)]), fill=c, outline=INK, width=S(6))
    for k in range(-3, 4):
        d.line(P([(mx + k * 22, my - 4), (mx + k * 26, my + 22)]), fill=darker(c, 0.75), width=S(3))


# ------------------------------------------------------------------ Requisiten
def prop_foil(d, x, y, s=1.0, empty=True):
    pts = [(x - 60 * s, y - 20 * s), (x - 20 * s, y - 70 * s), (x + 30 * s, y - 60 * s), (x + 70 * s, y - 10 * s),
           (x + 50 * s, y + 45 * s), (x, y + 30 * s), (x - 50 * s, y + 50 * s)]
    d.polygon(P(pts), fill=(205, 210, 218), outline=INK, width=S(6))
    for a, b in [((x - 30 * s, y - 30 * s), (x + 20 * s, y - 10 * s)), ((x - 10 * s, y + 10 * s), (x + 40 * s, y + 20 * s))]:
        d.line(P([a, b]), fill=(250, 250, 255), width=S(5))
    d.ellipse(box(x + 10 * s, y + 5 * s, 14 * s, 9 * s), fill=(250, 246, 230))   # Rest Knoblauchsoße


def prop_fork(d, x, y):
    d.line(P([(x, y), (x + 8, y - 170)]), fill=(200, 205, 215), width=S(12))
    for k in (-14, -4, 6, 16):
        d.line(P([(x + 8 + k, y - 165), (x + 8 + k, y - 225)]), fill=(200, 205, 215), width=S(6))
    d.line(P([(x, y), (x + 8, y - 170)]), fill=INK, width=S(2))


def prop_fork_doener(d, x, y):
    prop_fork(d, x, y)
    tx, ty = x + 8, y - 215
    d.rounded_rectangle(box(tx, ty, 46, 30), radius=S(12), fill=(178, 104, 56), outline=INK, width=S(5))   # Fleisch
    for k in range(3):
        d.line(P([(tx - 34 + k * 26, ty - 18), (tx - 26 + k * 26, ty + 18)]), fill=(130, 70, 36), width=S(4))
    d.ellipse(box(tx - 30, ty - 30, 20, 12), fill=(90, 180, 70), outline=INK, width=S(3))      # Salat
    d.ellipse(box(tx + 26, ty - 28, 16, 11), fill=(220, 60, 50), outline=INK, width=S(3))      # Tomate
    d.ellipse(box(tx + 6, ty + 26, 22, 10), fill=(250, 248, 232), outline=INK, width=S(3))     # Soße


def prop_receipt(d, x, y):
    d.rectangle([S(x - 45), S(y - 330), S(x + 45), S(y + 10)], fill=(252, 252, 246), outline=INK, width=S(5))
    for k in range(9):
        yy = y - 300 + k * 32
        d.line(P([(x - 30, yy), (x + (20 if k % 3 else 30), yy)]), fill=(120, 120, 130), width=S(4))
    d.text((S(x), S(y - 30)), "DÖNER  7,50", font=font(F_BLACK, S(18)), fill=(40, 40, 50), anchor="mm")
    d.text((S(x), S(y - 8)), "EC-KARTE S.K.", font=font(F_BLACK, S(14)), fill=(200, 40, 40), anchor="mm")


# ------------------------------------------------------------------ Figur zusammensetzen
@lru_cache(maxsize=90)
def sprite(name, expr_name="", mouth=0, blink=False, look=(0.0, 0.0), pose="", extra="", twitch_phase=0):
    spec = CHARS[name]
    ex_spec = EXPR.get(expr_name or DEFAULT_EXPR[name], EXPR["neutral"])
    img = Image.new("RGBA", (S(SW), S(SH)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    draw_hair_back(d, name, spec)
    draw_body(d, spec, name, pose)
    # Kopf mit Cel-Shading + Kontur
    m = head_mask(spec)
    rx, ry = spec["head"]
    for sx in (-1, 1):   # Ohren
        d.ellipse(box(HX + sx * (rx - 2), HY + 10, 22, 34), fill=spec["skin"], outline=INK, width=S(6))
    if name == "sabine":
        for sx in (-1, 1):
            d.ellipse(box(HX + sx * (rx + 4), HY + 78, 26, 30), outline=(232, 186, 50), width=S(8))
    outline_mask(img, m)
    paste_shape(img, m, spec["skin"], shade=(-26, -18))
    d = ImageDraw.Draw(img)
    beard = draw_face_extras(d, name, spec, expr_name, mouth)
    if beard is not None:
        img.alpha_composite(beard)
        d = ImageDraw.Draw(img)
    draw_hair_front(d, name, spec)
    # Wangenröte
    for sx in (-1, 1):
        if name == "sabine":
            d.ellipse(box(HX + sx * 70, HY + 46, 18, 10), fill=(244, 176, 170))
    # Falten / Kinn / Nasen im Stil des Referenzbildes
    if name == "richard":
        for sx in (-1, 1):
            d.arc(box(HX + sx * 54, HY + 70, 26, 50), 90 - sx * 60, 90 + sx * 60 if sx < 0 else 150, fill=darker(spec["skin"], 0.66), width=S(4))
            d.arc(box(HX + sx * 50, HY + 18, 26, 10), 20, 160, fill=darker(spec["skin"], 0.72), width=S(3))   # Tränensäcke
        d.line(P([(HX - 8, HY - 64), (HX - 4, HY - 40)]), fill=darker(spec["skin"], 0.66), width=S(4))
        d.line(P([(HX + 8, HY - 64), (HX + 4, HY - 40)]), fill=darker(spec["skin"], 0.66), width=S(4))
    if name == "klaus":
        d.line(P([(HX, HY + ry * 0.9), (HX, HY + ry * 0.78)]), fill=darker(spec["skin"], 0.6), width=S(4))   # Kinngrübchen
        for sx in (-1, 1):
            d.arc(box(HX + sx * 62, HY + 74, 18, 36), 60, 300 if sx > 0 else 120, fill=darker(spec["skin"], 0.7), width=S(4))
    if name == "horst":
        d.arc(box(HX, HY + ry * 0.98, rx * 0.62, 26), 20, 160, fill=darker(spec["skin"], 0.7), width=S(5))   # Doppelkinn
        for sx in (-1, 1):
            d.arc(box(HX + sx * 50, HY + 4, 24, 10), 20, 160, fill=darker(spec["skin"], 0.72), width=S(3))
    # Nase
    if name == "horst":     # große rote Knollennase
        d.ellipse(box(HX + 2, HY + 42, 27, 22), fill=(232, 160, 136), outline=INK, width=S(5))

    elif name == "richard":  # markante, große Nase
        d.polygon(P([(HX - 4, HY - 4), (HX - 24, HY + 54), (HX - 8, HY + 70), (HX + 24, HY + 68), (HX + 30, HY + 50), (HX + 10, HY - 4)]),
                  fill=darker(spec["skin"], 0.95), outline=INK, width=S(5))
        d.ellipse(box(HX + 12, HY + 62, 7, 4), fill=INK)
    elif name == "klaus":
        d.line(P([(HX + 6, HY - 6), (HX - 14, HY + 54), (HX + 4, HY + 64), (HX + 22, HY + 58)]), fill=INK, width=S(6), joint="curve")
    else:
        d.line(P([(HX + 4, HY + 4), (HX - 12, HY + 50), (HX + 10, HY + 56)]), fill=INK, width=S(6), joint="curve")
    # Augen
    lid = 1.0 if blink else ex_spec["lid"]
    eyes = []
    for sx in (-1, 1):
        cx = HX + sx * spec["eye_dx"]
        cy = HY + spec["eye_dy"]
        l2 = lid
        if ex_spec.get("twitch") and sx == 1:
            l2 = 0.75 if twitch_phase else 0.25
        er = (24, 27) if name == "horst" else (27, 31)
        draw_eye(d, spec, cx, cy, l2, look, ex_spec.get("pupil", 1.0), rx=er[0], ry=er[1])
        eyes.append((cx, cy))
    # Brauen
    bcol = spec.get("brow", darker(spec["hair"], 0.7))
    thick = {"richard": 20, "klaus": 13, "horst": 13}.get(name, 11)
    for (cx, cy), sx in zip(eyes, (-1, 1)):
        inner, outer = ex_spec["brow"]
        if sx == 1 and "brow_r" in ex_spec:
            inner, outer = ex_spec["brow_r"]
        if ex_spec.get("twitch") and sx == 1 and twitch_phase:
            inner, outer = -14, 0
        draw_brow(d, cx, cy - 52, sx, inner, outer, bcol, thick)
    if name == "richard" and pose != "facepalm":
        draw_face_extras(d, name, spec, "__glasses__", mouth)
    # Mund
    mk = ex_spec["mouth"]
    my = HY + 96
    if name == "horst":
        my = HY + 104
    if name == "klaus" and mk in ("smirk", "grin") and not mouth:
        # breites Haifisch-Grinsen mit vielen Zähnen
        d.chord(box(HX + 6, my - 10, 62, 40), 0, 180, fill=(255, 255, 255), outline=INK, width=S(6))
        d.line(P([(HX - 54, my - 8), (HX + 66, my - 8)]), fill=INK, width=S(4))
        for k in range(-4, 5):
            d.line(P([(HX + 6 + k * 13, my - 8), (HX + 6 + k * 12, my + 12)]), fill=(200, 200, 205), width=S(2))
    else:
        draw_mouth(d, spec, mk, mouth / 2.0 if mouth else 0, HX, my, teeth=(name == "klaus"))
    if name == "richard" and not mouth and mk == "flat":   # mürrische Mundwinkel
        for sx in (-1, 1):
            d.line(P([(HX + sx * 32, my), (HX + sx * 44, my + 12)]), fill=INK, width=S(6))
    if name == "horst" and extra == "sauce":   # Knoblauchsoße um den Mund verschmiert
        d.chord(box(HX + 4, my + 4, 56, 30), 0, 180, fill=(250, 248, 232), outline=INK, width=S(4))
        d.ellipse(box(HX - 46, my - 4, 16, 12), fill=(250, 248, 232), outline=INK, width=S(3))
        d.ellipse(box(HX + 52, my + 2, 13, 10), fill=(250, 248, 232), outline=INK, width=S(3))
        d.line(P([(HX + 20, my + 30), (HX + 22, my + 52)]), fill=(250, 248, 232), width=S(9))
        d.line(P([(HX, my - 3), (HX + 30, my - 1)]), fill=INK, width=S(5))
    if name == "sabine" and mouth == 0 and mk == "chew" and twitch_phase:
        d.ellipse(box(HX + 44, HY + 98, 18, 16), fill=(255, 140, 190), outline=INK, width=S(4))   # Kaugummiblase
    if extra == "sweat":
        for dx, dy, s in [(-rx - 6, -40, 1.0), (rx + 10, -10, 0.8), (rx - 20, -ry + 20, 0.7)]:
            x, y = HX + dx, HY + dy
            d.polygon(P([(x, y - 30 * s), (x + 16 * s, y), (x, y + 14 * s), (x - 16 * s, y)]), fill=(150, 210, 255), outline=INK, width=S(4))
    if name == "dennis" and extra == "sweat":
        for k in range(3):
            d.line(P([(HX - rx + 20 + k * 20, HY - ry * 0.25), (HX - rx + 26 + k * 20, HY - ry * 0.05)]),
                   fill=(90, 90, 140), width=S(4))

    # Arme / Gesten
    top = HY + spec["head"][1]
    bw = spec["body_w"]
    if pose == "foil_up":
        hx, hy = draw_arm(d, spec, 1, [(HX + bw / 2 - 20, top + 70), (HX + bw / 2 + 80, top - 40), (HX + bw / 2 + 60, HY - 160)])
        prop_foil(d, hx + 6, hy - 66, 1.3)
        d.ellipse(box(hx, hy, 34, 34), fill=spec["skin"], outline=INK, width=S(6))
        for k in range(3):   # Finger um die Folie
            d.arc(box(hx - 16 + k * 16, hy - 26, 10, 12), 180, 360, fill=INK, width=S(4))
        tx, ty = hx + 66, hy + 86   # Schild "BEWEISSTÜCK A" hängt an der Hand
        d.line(P([(hx + 6, hy + 20), (tx, ty - 28)]), fill=INK, width=S(3))
        ty += 18
        d.rounded_rectangle(box(tx, ty, 100, 46), radius=S(8), fill=(255, 226, 60), outline=INK, width=S(4))
        d.text((S(tx), S(ty - 18)), "BEWEISSTÜCK A:", font=font(F_BLACK, S(20)), fill=INK, anchor="mm")
        d.text((S(tx), S(ty + 16)), "LEERE DÖNERFOLIE", font=font(F_BLACK, S(17)), fill=(200, 30, 40), anchor="mm")
    elif pose == "finger":
        hx, hy = draw_arm(d, spec, 1, [(HX + bw / 2 - 30, top + 90), (HX + bw / 2 + 60, top - 20), (HX + bw / 2 + 60, HY - 90)])
        for k, (dx, ln) in enumerate([(-26, 44), (-9, 56), (9, 58), (26, 46)]):   # offene Hand
            d.line(P([(hx + dx, hy - 10), (hx + dx * 1.2, hy - 10 - ln)]), fill=INK, width=S(24))
        for k, (dx, ln) in enumerate([(-26, 44), (-9, 56), (9, 58), (26, 46)]):
            d.line(P([(hx + dx, hy - 10), (hx + dx * 1.2, hy - 10 - ln)]), fill=spec["skin"], width=S(12))
        d.line(P([(hx - 30, hy + 6), (hx - 58, hy - 18)]), fill=INK, width=S(24))
        d.line(P([(hx - 30, hy + 6), (hx - 58, hy - 18)]), fill=spec["skin"], width=S(12))
        d.ellipse(box(hx, hy, 36, 34), fill=spec["skin"], outline=INK, width=S(6))
    elif pose == "fist":
        hx, hy = draw_arm(d, spec, 1, [(HX + bw / 2 - 30, top + 90), (HX + bw / 2 + 70, top + 260), (HX + bw / 2 + 40, top + 470)])
    elif pose == "fork":
        hx, hy = draw_arm(d, spec, 1, [(HX + bw / 2 - 30, top + 100), (HX + bw / 2 + 40, top + 260), (HX + 120, top + 200)])
        prop_fork(d, hx, hy - 20)
        d.ellipse(box(hx, hy, 34, 34), fill=spec["skin"], outline=INK, width=S(6))
    elif pose == "receipt":
        hx, hy = draw_arm(d, spec, 1, [(HX + bw / 2 - 30, top + 100), (HX + bw / 2 + 60, top + 200), (HX + 150, top + 80)])
        prop_receipt(d, hx, hy - 10)
        d.ellipse(box(hx, hy, 34, 34), fill=spec["skin"], outline=INK, width=S(6))
    elif pose == "facepalm":
        hx, hy = draw_arm(d, spec, 1, [(HX + bw / 2 - 30, top + 100), (HX + 150, top + 40), (HX + 40, HY - 40)])
    elif pose == "eat":   # beißt in seinen eigenen (großen) Döner, Zettel klebt auf der Folie
        hx, hy = draw_arm(d, spec, 1, [(HX + bw / 2 - 30, top + 100), (HX + bw / 2 + 50, top + 80), (HX + 120, HY + 210)])
        g = 1.7
        dx_, dy_ = hx - 6, hy - 46 * g
        bread = (222, 170, 100)
        # Döner im Fladenbrot: breite Brottasche, Füllung oben, Folie unten
        d.chord(box(dx_, dy_ - 14 * g, 70 * g, 48 * g), 170, 370, fill=bread, outline=INK, width=S(6))       # Brotrücken
        # Fleisch
        for k in range(5):
            d.rounded_rectangle(box(dx_ - 44 * g + k * 22 * g, dy_ - 30 * g - (k % 2) * 4 * g, 14 * g, 7 * g),
                                radius=S(4), fill=(170, 96, 52), outline=INK, width=S(2))
        # Salatblätter: gewellte, hellgrüne Blätter mit Blattader
        for k in range(6):
            lx = dx_ - 56 * g + k * 22 * g
            ly = dy_ - 40 * g - (k % 2) * 6 * g
            pts = [(lx - 14 * g, ly + 8 * g)]
            for j in range(7):
                ang = math.pi + j * math.pi / 6
                rr = (13 if j % 2 else 16) * g
                pts.append((lx + rr * math.cos(ang), ly + rr * 0.8 * math.sin(ang)))
            pts.append((lx + 14 * g, ly + 8 * g))
            d.polygon(P(pts), fill=(110, 200, 80) if k % 2 else (140, 214, 96), outline=(40, 110, 40), width=S(3))
            d.line(P([(lx, ly + 6 * g), (lx + 2 * g, ly - 8 * g)]), fill=(200, 240, 170), width=S(3))
        # Tomatenscheiben und Zwiebelringe
        for k in range(3):
            tx_ = dx_ - 36 * g + k * 34 * g
            d.chord(box(tx_, dy_ - 30 * g, 11 * g, 9 * g), 180, 360, fill=(226, 60, 50), outline=INK, width=S(2))
            d.ellipse(box(tx_ - 3 * g, dy_ - 34 * g, 2.5 * g, 2 * g), fill=(255, 220, 120))
        for k in range(2):
            d.arc(box(dx_ - 18 * g + k * 40 * g, dy_ - 34 * g, 9 * g, 6 * g), 180, 360, fill=(235, 210, 235), width=S(4))
        d.chord(box(dx_, dy_ - 30 * g, 72 * g, 60 * g), 0, 180, fill=bread, outline=INK, width=S(6))           # Brot vorn
        d.polygon(P([(dx_ - 74 * g, dy_ - 4 * g), (dx_ + 74 * g, dy_ - 4 * g), (dx_ + 58 * g, dy_ + 30 * g), (dx_ - 58 * g, dy_ + 30 * g)]),
                  fill=(205, 210, 218), outline=INK, width=S(6))                                                  # Folie
        d.ellipse(box(dx_ - 62 * g, dy_ - 30 * g, 14 * g, 12 * g), fill=(200, 170, 130))                       # Bissspur
        px_, py_ = dx_ + 6 * g, dy_ + 6 * g   # Zettel mitten auf der Folie
        d.polygon(P([(px_ - 36 * g, py_ - 22 * g), (px_ + 38 * g, py_ - 20 * g), (px_ + 34 * g, py_ + 24 * g), (px_ - 38 * g, py_ + 22 * g)]),
                  fill=(255, 232, 80), outline=INK, width=S(4))
        d.text((S(px_), S(py_ - 8 * g)), "Finger weg", font=font(F_HAND, S(15 * g)), fill=(30, 30, 120), anchor="mm")
        d.text((S(px_), S(py_ + 10 * g)), "R.", font=font(F_HAND, S(17 * g)), fill=(30, 30, 120), anchor="mm")
        d.ellipse(box(hx, hy, 34, 34), fill=spec["skin"], outline=INK, width=S(6))
    elif pose == "fork_horst":
        hx, hy = draw_arm(d, spec, 1, [(HX + bw / 2 - 30, top + 100), (HX + bw / 2 + 40, top + 200), (HX + 150, top + 120)])
        prop_fork_doener(d, hx, hy - 20)
        d.ellipse(box(hx, hy, 34, 34), fill=spec["skin"], outline=INK, width=S(6))

    return img.resize((SW, SH), Image.LANCZOS)
