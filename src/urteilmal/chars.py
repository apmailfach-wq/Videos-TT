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
    "richard": dict(skin=(236, 196, 166), head=(122, 162), jaw=0.86, eye_dx=50, eye_dy=-6,
                    body=(32, 32, 40), body_w=330, hair=(168, 168, 172)),
    "klaus": dict(skin=(226, 176, 138), head=(128, 154), jaw=0.92, eye_dx=52, eye_dy=-8,
                  body=(128, 22, 44), body_w=360, hair=(24, 22, 28)),
    "horst": dict(skin=(244, 190, 160), head=(150, 142), jaw=1.0, eye_dx=54, eye_dy=-10,
                  body=(150, 196, 236), body_w=420, hair=(150, 120, 96)),
    "dennis": dict(skin=(240, 204, 178), head=(124, 150), jaw=0.9, eye_dx=50, eye_dy=-6,
                   body=(30, 150, 90), body_w=330, hair=(110, 72, 40)),
    "sabine": dict(skin=(246, 206, 180), head=(120, 146), jaw=0.84, eye_dx=50, eye_dy=-4,
                   body=(250, 170, 200), body_w=320, hair=(244, 214, 120)),
}

# Augenlid-Höhe (0 offen … 1 zu) und Brauen (innen, außen) in Welt-Pixeln (positiv = höher)
EXPR = {
    "neutral": dict(lid=0.15, brow=(0, 0), mouth="flat"),
    "deadpan": dict(lid=0.5, brow=(-2, -2), mouth="flat"),
    "brow": dict(lid=0.45, brow=(-2, -2), brow_r=(18, 22), mouth="flat"),
    "tired": dict(lid=1.0, brow=(10, -8), mouth="frown"),
    "shock": dict(lid=0.0, brow=(22, 20), mouth="o", pupil=0.6),
    "twitch": dict(lid=0.5, brow=(-6, 6), mouth="flat", twitch=True),
    "shout": dict(lid=0.0, brow=(-14, 12), mouth="frown"),
    "upset": dict(lid=0.05, brow=(-10, 8), mouth="frown"),
    "disgust": dict(lid=0.35, brow=(-12, 4), mouth="wavy"),
    "nervous": dict(lid=0.0, brow=(14, -6), mouth="wavy", pupil=0.7),
    "bored": dict(lid=0.55, brow=(0, 0), mouth="chew"),
    "smug": dict(lid=0.4, brow=(4, 10), mouth="smirk"),
    "dramatic": dict(lid=0.0, brow=(12, 18), mouth="grin"),
    "outraged": dict(lid=0.0, brow=(-16, 10), mouth="frown"),
    "proud": dict(lid=0.3, brow=(8, 8), mouth="smile"),
    "longing": dict(lid=0.1, brow=(16, 4), mouth="o", pupil=1.15),
    "innocent": dict(lid=0.2, brow=(14, 8), mouth="smile"),
}

DEFAULT_EXPR = {"richard": "deadpan", "klaus": "smug", "horst": "neutral", "dennis": "upset", "sabine": "bored"}


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
    d.polygon(P(sh), fill=darker(col, 0.82))

    for sx in (-1, 1):
        d.line(P([(HX + sx * (bw / 2 - 30), top + 130), (HX + sx * (bw / 2 - 10), SH)]), fill=darker(col, 0.6), width=S(5))
    if name == "richard":     # Robe mit Beffchen
        d.polygon(P([(HX - 70, top + 40), (HX, top + 140), (HX + 70, top + 40)]), fill=(250, 250, 250), outline=INK, width=S(5))
        d.rectangle([S(HX - 28), S(top + 120), S(HX - 4), S(top + 230)], fill=(255, 255, 255), outline=INK, width=S(4))
        d.rectangle([S(HX + 4), S(top + 120), S(HX + 28), S(top + 230)], fill=(255, 255, 255), outline=INK, width=S(4))
        for k in range(4):
            x = HX - 120 + k * 80
            d.line(P([(x, top + 260), (x - 10, SH)]), fill=(55, 55, 66), width=S(5))
    elif name == "klaus":     # Anzug, Hemd, Krawatte, Goldnadel, Einstecktuch
        d.polygon(P([(HX - 75, top + 40), (HX, top + 230), (HX + 75, top + 40)]), fill=(250, 248, 244), outline=INK, width=S(5))
        d.polygon(P([(HX - 16, top + 50), (HX + 16, top + 50), (HX + 26, top + 240), (HX, top + 280), (HX - 26, top + 240)]),
                  fill=(36, 30, 40), outline=INK, width=S(4))
        d.rectangle([S(HX - 34), S(top + 150), S(HX + 34), S(top + 160)], fill=(240, 196, 60), outline=INK, width=S(2))
        d.line(P([(HX - 75, top + 40), (HX - 20, top + 260), (HX - 40, SH)]), fill=INK, width=S(5))
        d.line(P([(HX + 75, top + 40), (HX + 20, top + 260), (HX + 40, SH)]), fill=INK, width=S(5))
        d.polygon(P([(HX + 95, top + 200), (HX + 145, top + 190), (HX + 140, top + 215), (HX + 100, top + 222)]),
                  fill=(255, 255, 255), outline=INK, width=S(3))
    elif name == "horst":     # Hemd, kurze Krawatte, Hosenträger, Schlüssel
        d.polygon(P([(HX - 50, top + 40), (HX, top + 100), (HX + 50, top + 40)]), fill=lighter(col, 0.5), outline=INK, width=S(4))
        d.polygon(P([(HX - 14, top + 60), (HX + 14, top + 60), (HX + 20, top + 170), (HX, top + 190), (HX - 20, top + 170)]),
                  fill=(30, 50, 120), outline=INK, width=S(4))
        for sx in (-1, 1):
            d.line(P([(HX + sx * 110, top + 50), (HX + sx * 95, SH)]), fill=(60, 60, 70), width=S(18))
        d.ellipse(box(HX - 150, top + 520, 22, 22), outline=(200, 190, 120), width=S(6))
        d.rectangle([S(HX + 40), S(top + 70), S(HX + 110), S(top + 100)], fill=(240, 240, 240), outline=INK, width=S(3))
    elif name == "dennis":    # Trikot mit Kragen und Nummer
        d.polygon(P([(HX - 60, top + 40), (HX, top + 90), (HX + 60, top + 40)]), fill=(255, 255, 255), outline=INK, width=S(5))
        for k in range(3):
            x = HX - 90 + k * 90
            d.rectangle([S(x - 14), S(top + 110), S(x + 14), S(SH)], fill=lighter(col, 0.35))
        d.text((S(HX + 80), S(top + 220)), "7", font=font(F_BLACK, S(110)), fill=(255, 255, 255),
               stroke_width=S(4), stroke_fill=INK, anchor="mm")
    elif name == "sabine":
        d.line(P([(HX, top + 60), (HX, SH)]), fill=darker(col, 0.7), width=S(5))


def draw_arm(d, spec, side, pts, hand_open=False):
    col = spec["body"] if spec is not CHARS["sabine"] else spec["body"]
    d.line(P(pts), fill=INK, width=S(64), joint="curve")
    d.line(P(pts), fill=col, width=S(50), joint="curve")
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


def draw_hair_back(d, name, spec):
    rx, ry = spec["head"]
    c = spec["hair"]
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
    if name == "richard":   # graue Haare mit Seitenscheitel
        d.chord(box(HX, HY - ry * 0.35, rx + 6, ry * 0.75), 180, 360, fill=c, outline=INK, width=S(OUT))
        d.polygon(P([(HX - rx - 6, HY - ry * 0.35), (HX - rx + 10, HY + 10), (HX - rx + 26, HY - ry * 0.3)]), fill=c, outline=INK, width=S(5))
        d.polygon(P([(HX + rx + 6, HY - ry * 0.35), (HX + rx - 10, HY + 10), (HX + rx - 26, HY - ry * 0.3)]), fill=c, outline=INK, width=S(5))
        d.line(P([(HX - 40, HY - ry * 0.98), (HX - 30, HY - ry * 0.45)]), fill=darker(c, 0.6), width=S(5))
        for k in range(3):     # Stirnfalten
            yy = HY - ry * 0.32 + k * 14
            d.arc(box(HX, yy + 20, 44 - k * 6, 14), 200, 340, fill=darker(spec["skin"], 0.7), width=S(4))
    elif name == "klaus":   # zurückgegelt
        d.chord(box(HX, HY - ry * 0.3, rx + 4, ry * 0.82), 180, 360, fill=c, outline=INK, width=S(OUT))
        for k in range(4):
            d.arc(box(HX + 20, HY - ry * 0.32, rx - 10 - k * 18, ry * 0.7 - k * 14), 200, 330, fill=(90, 90, 110), width=S(4))
    elif name == "horst":   # Glatze mit Haarkranz
        for sx in (-1, 1):
            d.polygon(P([(HX + sx * (rx + 8), HY - 40), (HX + sx * (rx - 30), HY - 60), (HX + sx * (rx - 18), HY + 40),
                         (HX + sx * (rx + 10), HY + 30)]), fill=c, outline=INK, width=S(5))
        d.ellipse(box(HX - 40, HY - ry + 40, 30, 14), fill=lighter(spec["skin"], 0.5))   # Glanz
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
    if name == "richard" and expr_name == "__glasses__":   # eckige Hornbrille
        for sx in (-1, 1):
            d.rounded_rectangle([S(HX + sx * ex - 40), S(ey - 32), S(HX + sx * ex + 40), S(ey + 30)], radius=S(8),
                                outline=(90, 52, 30), width=S(9))
        d.line(P([(HX - ex + 40, ey - 8), (HX + ex - 40, ey - 8)]), fill=(90, 52, 30), width=S(8))
    if name in ("klaus", "dennis"):   # Bartschatten
        layer = Image.new("RGBA", (S(SW), S(SH)), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.chord(box(HX, HY + ry * 0.3, rx * spec["jaw"] - 6, ry * 0.62), 0, 180, fill=(70, 60, 60, 70))
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
        d.ellipse(box(HX + sx * 70, HY + 46, 20, 12), fill=lighter((240, 140, 130), 0.2) if name != "richard" else spec["skin"])
    # Nase
    if name == "horst":
        d.ellipse(box(HX, HY + 38, 30, 26), fill=(240, 150, 130), outline=INK, width=S(6))
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
        draw_eye(d, spec, cx, cy, l2, look, ex_spec.get("pupil", 1.0))
        eyes.append((cx, cy))
    # Brauen
    bcol = darker(spec["hair"], 0.7) if name != "horst" else (200, 80, 40)
    thick = 16 if name == "richard" else 11
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
        my = HY + 118
    draw_mouth(d, spec, mk, mouth / 2.0 if mouth else 0, HX, my, teeth=(name == "klaus"))
    if name == "horst":
        draw_mustache(d, spec)
        if extra == "sauce":
            for k, (dx, dy) in enumerate([(-50, 106), (-10, 112), (30, 104), (64, 110)]):
                d.ellipse(box(HX + dx, HY + dy, 14, 10 + 4 * (k % 2)), fill=(252, 250, 236), outline=INK, width=S(3))
                d.line(P([(HX + dx, HY + dy + 8), (HX + dx, HY + dy + 26 + 6 * (k % 2))]), fill=(252, 250, 236), width=S(8))
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
        hx, hy = draw_arm(d, spec, 1, [(HX + bw / 2 - 30, top + 90), (HX + bw / 2 + 50, top - 60), (HX + bw / 2 + 40, HY - 200)])
        prop_foil(d, hx + 10, hy - 70, 1.25)
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
    elif pose == "fork_horst":
        hx, hy = draw_arm(d, spec, 1, [(HX + bw / 2 - 30, top + 100), (HX + bw / 2 + 40, top + 200), (HX + 150, top + 120)])
        prop_fork(d, hx, hy - 20)
        d.ellipse(box(hx, hy, 34, 34), fill=spec["skin"], outline=INK, width=S(6))

    return img.resize((SW, SH), Image.LANCZOS)
