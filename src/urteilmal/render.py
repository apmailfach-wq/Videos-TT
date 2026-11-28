"""URTEIL MAL! Folge 01 – Der Döner-Skandal: rendert das 9:16-Video (1080x1920, 30 fps).

python3 audio.py                  # Tonspur + Zeitplan
python3 render.py                 # -> ../../urteil-mal-01-doener-skandal.mp4
python3 render.py preview 1 20 40 # Standbilder -> build/doener/stills/
"""
import json
import math
import os
import random
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import chars
from chars import HX, HY, INK, P, S, box
EP = os.environ.get("EP", "01")
if EP == "02":
    from timeline02 import END_LINES, LAW_CARDS, SPEAKERS
else:
    from timeline import LAW_CARDS, SPEAKERS
    END_LINES = None

ROOT = Path(__file__).resolve().parents[2]
B = ROOT / "build" / ("dauerkarte" if EP == "02" else "doener")
OUT_FILE = ROOT / ("urteil-mal-02-dauerkarten-klage.mp4" if EP == "02" else "urteil-mal-01-doener-skandal.mp4")
W, H, FPS = 1080, 1920, 30
CX = 520   # Mitte der TikTok-Safe-Zone (rechts liegen die Buttons)
WW, WH = 2160, 3840

F_UNB = str(ROOT / "fonts" / "Unbounded_900Black.ttf")
F_UNB7 = str(ROOT / "fonts" / "Unbounded_700Bold.ttf")
F_HAND = str(ROOT / "fonts" / "Caveat_700Bold.ttf")
F_INTER = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
F_INTER_B = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"

HEADS = {"richard": (1080, 900), "horst": (2000, 1600), "dennis": (560, 2480),
         "sabine": (1300, 2610), "klaus": (1760, 2440)}
if EP == "02":   # Dennis & Sabine sitzen beide auf der Klägerseite
    HEADS["dennis"] = (380, 2480)
    HEADS["sabine"] = (800, 2610)
    chars.SCARF.update({"dennis", "sabine", "horst"})
HORST_FINAL = (1500, 930)
DOENER_POS = (1470, 1196)


@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, size)


def clamp01(x):
    return max(0.0, min(1.0, x))


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def ease_back(x, s=1.8):
    x = clamp01(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


# ------------------------------------------------------------------ Kulisse
def build_background():
    img = Image.new("RGB", (WW * 2, WH * 2), (226, 214, 190))
    d = ImageDraw.Draw(img)
    s2 = lambda v: int(v * 2)
    # Wand mit leichtem Verlauf
    for y in range(0, 2000 * 2, 8):
        t = y / 4000
        c = (int(232 - 30 * t), int(220 - 30 * t), int(196 - 30 * t))
        d.rectangle([0, y, WW * 2, y + 8], fill=c)
    # Neonröhren
    for x in (380, 1500):
        d.rounded_rectangle([s2(x), s2(40), s2(x + 300), s2(80)], radius=20, fill=(250, 252, 255), outline=INK, width=8)
    # Holzvertäfelung hinter dem Richter
    d.rectangle([s2(250), s2(170), s2(1910), s2(1300)], fill=(118, 72, 44), outline=INK, width=14)
    for k in range(9):
        x = 250 + k * (1660 / 8)
        d.line([(s2(x), s2(170)), (s2(x), s2(1300))], fill=(92, 54, 32), width=10)
    # Wappen (stilisierter Adler, gold)
    cx, cy = 1080, 420
    gold, dark = (232, 180, 60), (150, 100, 20)
    d.ellipse([s2(cx - 190), s2(cy - 190), s2(cx + 190), s2(cy + 190)], fill=(140, 30, 36), outline=INK, width=12)
    d.polygon([(s2(cx), s2(cy - 140)), (s2(cx + 60), s2(cy - 60)), (s2(cx + 160), s2(cy - 80)), (s2(cx + 110), s2(cy + 20)),
               (s2(cx + 140), s2(cy + 60)), (s2(cx + 50), s2(cy + 60)), (s2(cx), s2(cy + 150)), (s2(cx - 50), s2(cy + 60)),
               (s2(cx - 140), s2(cy + 60)), (s2(cx - 110), s2(cy + 20)), (s2(cx - 160), s2(cy - 80)), (s2(cx - 60), s2(cy - 60))],
              fill=gold, outline=dark, width=10)
    d.ellipse([s2(cx - 30), s2(cy - 120), s2(cx + 30), s2(cy - 60)], fill=gold, outline=dark, width=8)
    # Boden
    for y in range(2000 * 2, WH * 2, 8):
        t = (y - 4000) / (WH * 2 - 4000)
        c = (int(150 - 40 * t), int(160 - 40 * t), int(176 - 40 * t))
        d.rectangle([0, y, WW * 2, y + 8], fill=c)
    for k in range(-6, 14):
        x0 = 1080 + k * 260
        d.line([(s2(1080 + k * 120), s2(1950)), (s2(x0 + (x0 - 1080) * 1.4), s2(WH))], fill=(128, 138, 152), width=6)
    # Sockelleiste
    d.rectangle([0, s2(1930), WW * 2, s2(1990)], fill=(90, 56, 36), outline=INK, width=10)
    return img.resize((WW, WH), Image.LANCZOS)


def build_rail():
    y0 = 2120
    lay = Image.new("RGBA", (WW * 2, 2 * 460), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    s2 = lambda v: int(v * 2)
    yy = lambda v: int((v - y0) * 2)
    d.rectangle([s2(30), yy(2140), s2(2130), yy(2200)], fill=(120, 76, 46), outline=INK, width=12)
    for k in range(23):
        x = 70 + k * 92
        d.rectangle([s2(x), yy(2200), s2(x + 30), yy(2520)], fill=(132, 84, 52), outline=INK, width=8)
    d.rectangle([s2(30), yy(2500), s2(2130), yy(2550)], fill=(110, 70, 42), outline=INK, width=10)
    return lay.resize((WW, 460), Image.LANCZOS), y0


def build_bench():
    lay = Image.new("RGBA", (WW * 2, 2 * 820), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    y0 = 1210
    s2 = lambda v: int(v * 2)
    yy = lambda v: int((v - y0 + 40) * 2)
    d.rectangle([s2(300), yy(1250), s2(1860), yy(1975)], fill=(134, 84, 50), outline=INK, width=14)
    d.rectangle([s2(270), yy(1205), s2(1890), yy(1262)], fill=(170, 112, 70), outline=INK, width=14)
    for k in range(3):
        x = 380 + k * 500
        d.rectangle([s2(x), yy(1330), s2(x + 400), yy(1880)], outline=(96, 58, 34), width=12)
    d.rounded_rectangle([s2(880), yy(1420), s2(1280), yy(1520)], radius=20, fill=(232, 190, 80), outline=INK, width=8)
    d.text((s2(1080), yy(1470)), "RICHTER", font=font(F_UNB7, 90), fill=INK, anchor="mm")
    return lay.resize((WW, 820), Image.LANCZOS), y0 - 40


def build_legs():
    """Beine und Schuhe von Dennis, Sabine und Klaus (unter den Tischen sichtbar)."""
    y0 = 3380
    lay = Image.new("RGBA", (WW * 2, 2 * (WH - y0)), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    s2 = lambda v: int(v * 2)
    yy = lambda v: int((v - y0) * 2)
    spec = {"dennis": ((140, 140, 150), (245, 245, 245), 40), "sabine": ((70, 100, 160), (255, 255, 255), 30),
            "klaus": ((34, 44, 86), (30, 24, 22), 38)}
    for nm, (pants, shoe, lw) in spec.items():
        hx = HEADS[nm][0]
        for sx in (-1, 1):
            x = hx + sx * 46
            d.rectangle([s2(x - lw), yy(3380), s2(x + lw), yy(3770)], fill=pants, outline=INK, width=10)
            d.rounded_rectangle([s2(x - lw - 6 + sx * 10), yy(3762), s2(x + lw + 26 * sx if sx > 0 else x + lw + 6),
                                 yy(3812)], radius=22, fill=shoe, outline=INK, width=10)
            if sx < 0:
                d.rounded_rectangle([s2(x - lw - 32), yy(3762), s2(x + lw + 6), yy(3812)], radius=22, fill=shoe, outline=INK, width=10)
        if nm == "sabine":   # Teddyjacke reicht bis über die Hüfte
            d.rectangle([s2(hx - 140), yy(3380), s2(hx + 140), yy(3440)], fill=(250, 170, 200), outline=INK, width=10)
    return lay.resize((WW, WH - y0), Image.LANCZOS), y0


def build_tables():
    lay = Image.new("RGBA", (WW * 2, 2 * 900), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    y0 = 2940
    s2 = lambda v: int(v * 2)
    yy = lambda v: int((v - y0) * 2)
    for (x0, x1, label) in [(90, 1010, "KLÄGER"), (1100, 2090, "BEKLAGTE")]:
        d.rectangle([s2(x0 + 30), yy(3010), s2(x1 - 30), yy(3500)], fill=(120, 76, 46), outline=INK, width=12)
        d.rectangle([s2(x0), yy(2960), s2(x1), yy(3015)], fill=(160, 104, 64), outline=INK, width=12)
        for x in (x0 + 60, x1 - 120):
            d.rectangle([s2(x), yy(3500), s2(x + 60), yy(3830)], fill=(90, 56, 36), outline=INK, width=10)
        mx = (x0 + x1) / 2
        d.polygon([(s2(mx - 170), yy(2962)), (s2(mx + 170), yy(2962)), (s2(mx + 150), yy(2880)), (s2(mx - 150), yy(2880))],
                  fill=(250, 250, 245), outline=INK, width=8)
        d.text((s2(mx), yy(2921)), label, font=font(F_UNB7, 64), fill=INK, anchor="mm")
    return lay.resize((WW, 900), Image.LANCZOS), y0


@lru_cache(maxsize=16)
def props_layer(doener_state, gavel_up, sparkle):
    """Requisiten auf dem Richtertisch (Tasse, Hammer, Döner mit Post-it) – lokales Sprite um den Tisch."""
    x0, y0, w, h = 420, 860, 1400, 420
    img = Image.new("RGBA", (S(w), S(h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    L = lambda x, y: (x - x0, y - y0)
    # Tasse
    mx, my = L(640, 1150)
    d.rounded_rectangle(box(mx, my, 50, 58), radius=S(12), fill=(250, 250, 250), outline=INK, width=S(6))
    d.arc(box(mx + 56, my, 26, 26), 270, 90, fill=INK, width=S(10))
    d.text((S(mx), S(my)), "RUHE", font=font(F_INTER, S(20)), fill=(200, 40, 40), anchor="mm")
    # Hammer
    gx, gy = L(860, 1186)
    if gavel_up:
        d.line(P([(gx + 40, gy - 10), (gx - 40, gy - 190)]), fill=(110, 66, 36), width=S(18))
        d.rounded_rectangle(box(gx - 50, gy - 210, 60, 32), radius=S(10), fill=(140, 86, 48), outline=INK, width=S(6))
    else:
        d.line(P([(gx - 10, gy), (gx + 150, gy - 20)]), fill=(110, 66, 36), width=S(18))
        d.rounded_rectangle(box(gx - 20, gy - 8, 34, 50), radius=S(10), fill=(140, 86, 48), outline=INK, width=S(6))
    d.ellipse(box(gx - 20, gy + 26, 60, 12), fill=(90, 56, 36), outline=INK, width=S(4))
    # Döner
    dx, dy = L(*DOENER_POS)
    if doener_state in ("held", "none"):
        pass
    elif doener_state == "full":
        d.polygon(P([(dx - 70, dy - 40), (dx + 70, dy - 40), (dx + 20, dy + 40), (dx - 20, dy + 40)]),
                  fill=(205, 210, 218), outline=INK, width=S(6))
        d.chord(box(dx, dy - 40, 72, 46), 180, 360, fill=(230, 180, 110), outline=INK, width=S(6))
        for k, c in enumerate([(160, 90, 50), (80, 170, 70), (220, 60, 50), (250, 246, 230)]):
            d.ellipse(box(dx - 40 + k * 26, dy - 56 + (k % 2) * 8, 16, 12), fill=c)
    else:
        chars.prop_foil(d, dx, dy - 4, 1.0)
    if sparkle:
        for (sx, sy, r) in [(dx - 110, dy - 90, 26), (dx + 10, dy - 130, 34), (dx + 140, dy - 110, 22), (dx - 60, dy - 150, 18)]:
            d.polygon(P([(sx, sy - r), (sx + r * 0.25, sy - r * 0.25), (sx + r, sy), (sx + r * 0.25, sy + r * 0.25),
                         (sx, sy + r), (sx - r * 0.25, sy + r * 0.25), (sx - r, sy), (sx - r * 0.25, sy - r * 0.25)]),
                      fill=(255, 240, 120), outline=INK, width=S(3))
    return img.resize((w, h), Image.LANCZOS), (x0, y0)


def build_ball():
    """Schlapper Fußball mit Fanschal: der 'Vertreter' des Vereins auf dem Beklagtentisch."""
    w, h = 300, 200
    lay = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.ellipse([60, 120, 540, 390], fill=(250, 250, 250), outline=INK, width=12)
    for (x, y) in [(300, 250), (170, 210), (430, 210), (200, 330), (400, 330)]:
        d.regular_polygon((x, y, 46), 5, fill=(40, 36, 44))
    a, b = chars.SCARF_COLS
    d.rounded_rectangle([40, 300, 560, 360], radius=28, fill=a, outline=INK, width=10)
    for k in range(5):
        d.rectangle([90 + k * 100, 300, 130 + k * 100, 360], fill=b)
    d.rounded_rectangle([40, 300, 560, 360], radius=28, outline=INK, width=10)
    return lay.resize((w, h), Image.LANCZOS)


def build_folder():
    """Dicker Ordner 'BEWEISE' auf dem Klägertisch."""
    w, h = 250, 150
    lay = Image.new("RGBA", (660, 400), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for k in range(3):
        d.rectangle([20 + k * 8, 60 - k * 22, 640 - k * 8, 390 - k * 22], fill=(250, 250, 240), outline=INK, width=8)
    d.rectangle([10, 120, 650, 396], fill=(200, 40, 50), outline=INK, width=12)
    d.rounded_rectangle([170, 190, 490, 320], radius=16, fill=(255, 255, 255), outline=INK, width=8)
    d.text((330, 255), "BEWEISE", font=font(F_UNB7, 52), fill=INK, anchor="mm")
    return lay.resize((w, h), Image.LANCZOS)


# ------------------------------------------------------------------ Overlays (Ausgaberaum)
def text_wh(txt, f, stroke=0):
    b = f.getbbox(txt, stroke_width=stroke)
    return b[2] - b[0], b[3] - b[1]


def wrap(words, f, maxw):
    lines, cur = [], []
    for w_ in words:
        test = " ".join(cur + [w_])
        if cur and text_wh(test, f)[0] > maxw:
            lines.append(cur)
            cur = [w_]
        else:
            cur.append(w_)
    if cur:
        lines.append(cur)
    return lines


def chunks_for(text, f, maxw=780, max_lines=2):
    words = text.split()
    lines = wrap(words, f, maxw)
    out = []
    for i in range(0, len(lines), max_lines):
        out.append(lines[i:i + max_lines])
    return out


def draw_subtitle(img, ev, t_rel, y_center):
    f = font(F_INTER, 72)
    text = ev["text"]
    chunks = chunks_for(text, f)
    nwords = [sum(len(l) for l in c) for c in chunks]
    total_chars = sum(len(w) + 1 for w in text.split())
    dur = ev["dur"]
    # Zeit je Wort ~ Länge des Wortes
    words = text.split()
    times, acc = [], 0
    for w_ in words:
        times.append(acc / total_chars * dur)
        acc += len(w_) + 1
    k = sum(1 for tt in times if tt <= t_rel) - 1
    k = max(0, k)
    # welcher Chunk?
    idx, base = 0, 0
    for ci, n in enumerate(nwords):
        if k < base + n:
            idx = ci
            break
        base += n
    else:
        idx, base = len(chunks) - 1, sum(nwords[:-1])
    lines = chunks[idx]
    d = ImageDraw.Draw(img)
    lh = 90
    y = y_center - (len(lines) * lh) / 2
    wi = base
    for line in lines:
        widths = [text_wh(w_ + " ", f)[0] for w_ in line]
        x = CX - sum(widths) / 2
        for w_, ww in zip(line, widths):
            col = (255, 230, 60) if wi == k else (255, 255, 255)
            d.text((x, y), w_, font=f, fill=col, stroke_width=9, stroke_fill=(15, 12, 20))
            x += ww
            wi += 1
        y += lh
    # Sprecher-Label
    name, col = SPEAKERS[ev["who"]]
    if name:
        fl = font(F_UNB7, 30)
        tw, th = text_wh(name, fl)
        yl = y_center - (len(lines) * lh) / 2 - 62
        d.rounded_rectangle([CX - tw / 2 - 22, yl - 6, CX + tw / 2 + 22, yl + th + 18], radius=26, fill=col,
                            outline=(15, 12, 20), width=5)
        d.text((CX, yl + th / 2 + 6), name, font=fl, fill=(15, 12, 20), anchor="mm")


def draw_logo(img):
    d = ImageDraw.Draw(img)
    f = font(F_UNB, 40)
    d.rounded_rectangle([36, 196, 410, 270], radius=18, fill=(210, 30, 50), outline=(15, 12, 20), width=6)
    d.text((223, 233), "URTEIL MAL!", font=f, fill=(255, 255, 255), anchor="mm")


def big_text(img, lines, y, t_in, size=96, rot=-3):
    """Poppender Titeltext (Liste von (Text, Farbe))."""
    s = ease_back(t_in / 0.35)
    if s <= 0.01:
        return
    f = font(F_UNB, size)
    hs = []
    for txt, _ in lines:
        hs.append(text_wh(txt, f, 10))
    wmax = max(w_ for w_, _ in hs) + 40
    htot = sum(h_ + 24 for _, h_ in hs) + 20
    lay = Image.new("RGBA", (wmax, htot), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    yy = 10
    for (txt, col), (w_, h_) in zip(lines, hs):
        d.text((wmax / 2, yy + h_ / 2 + 6), txt, font=f, fill=tuple(col), stroke_width=10, stroke_fill=(15, 12, 20), anchor="mm")
        yy += h_ + 24
    lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC)
    nw, nh = max(1, int(lay.width * s)), max(1, int(lay.height * s))
    lay = lay.resize((nw, nh), Image.BILINEAR)
    img.paste(lay, (int(CX - nw / 2), int(y - nh / 2)), lay)


def law_card(img, y, t_in, title, sub):
    s = ease_back(t_in / 0.3)
    if s <= 0.01:
        return
    cw, ch = 860, 166
    lay = Image.new("RGBA", (cw + 20, ch + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([14, 14, cw + 14, ch + 14], radius=30, fill=(15, 12, 20))
    d.rounded_rectangle([4, 4, cw, ch], radius=30, fill=(255, 252, 240), outline=(15, 12, 20), width=6)
    d.rounded_rectangle([4, 4, 40, ch], radius=18, fill=(210, 30, 50))
    d.text((66, 58), title, font=font(F_UNB, 48), fill=(210, 30, 50), anchor="lm")
    d.text((66, 124), sub, font=font(F_INTER_B, 34), fill=(30, 26, 36), anchor="lm")
    nw, nh = int(lay.width * s), int(lay.height * s)
    if nw < 2 or nh < 2:
        return
    lay = lay.resize((nw, nh), Image.BILINEAR)
    img.paste(lay, (int(CX - nw / 2), int(y - nh / 2)), lay)


@lru_cache(maxsize=4)
def speed_lines(seed):
    rnd = random.Random(seed)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx, cy = W / 2, H * 0.36
    for _ in range(70):
        a = rnd.uniform(0, 2 * math.pi)
        r0 = rnd.uniform(620, 820)
        r1 = 1900
        wdt = rnd.uniform(0.008, 0.022)
        pts = [(cx + r0 * math.cos(a), cy + r0 * math.sin(a)),
               (cx + r1 * math.cos(a - wdt), cy + r1 * math.sin(a - wdt)),
               (cx + r1 * math.cos(a + wdt), cy + r1 * math.sin(a + wdt))]
        d.polygon(pts, fill=(255, 255, 255, 170))
    return lay


def bam(img, t_in, text="BÄM!"):
    if not (0 <= t_in <= 0.45):
        return
    s = ease_back(t_in / 0.15)
    r = 230 * s
    cx, cy = 790, 640
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    pts = []
    for i in range(24):
        a = i / 24 * 2 * math.pi
        rr = r * (1 if i % 2 else 0.62)
        pts.append((cx + rr * math.cos(a), cy + rr * 0.8 * math.sin(a)))
    d.polygon(pts, fill=(255, 220, 40), outline=(15, 12, 20), width=8)
    d.text((cx, cy), text, font=font(F_UNB, int(90 * s) + 1), fill=(210, 30, 50), stroke_width=6, stroke_fill=(15, 12, 20), anchor="mm")
    img.paste(lay, (0, 0), lay)


# ------------------------------------------------------------------ Szene
class Scene:
    def __init__(self):
        tl = json.load(open(B / "timeline.json"))
        self.total = tl["total"]
        self.events = tl["events"]
        self.bg = build_background()
        self.bench, self.bench_y = build_bench()
        self.tables, self.tables_y = build_tables()
        self.rail, self.rail_y = build_rail()
        self.legs, self.legs_y = build_legs()
        if EP == "02":
            self.ball = build_ball()
            self.folder = build_folder()
            self.folder_idx = next((i for i, ev in enumerate(self.events) if "folder" in ev.get("fx", [])), 10 ** 6)

    def event_at(self, t):
        cur = self.events[0]
        for e in self.events:
            if t >= e["start"] - 1e-6:
                cur = e
        return cur

    def camera(self, e, t):
        target, cw0, cw1 = e["cam"]
        tr = clamp01((t - e["start"]) / max(0.3, e["dur"]))
        if e.get("hook"):
            cw = cw1 + (cw0 - cw1) * (1 - ease_out((t - e["start"]) / 0.45))
        else:
            cw = cw0 + (cw1 - cw0) * ease_io(tr)
        if target in HEADS or target == "richard_horst":
            cw *= 0.95
        ch = cw * 16 / 9
        if target == "wide":
            cx, cy = WW / 2, WH / 2
        elif target == "doener":
            cx, cy = DOENER_POS[0] - 20, DOENER_POS[1] - 60
        elif target == "richard_horst":
            cx, cy = 1360, 960 + 0.16 * ch
        else:
            hx, hy = HEADS[target]
            cx, cy = hx, hy + (-0.02 if e.get("law") else 0.17) * ch
        # Shake
        sx = sy = 0
        shake_t = None
        if "shake" in e.get("fx", []):
            shake_t = t - e["start"]
        if "gavel" in e.get("fx", []):
            for bt in (0.02, 0.42):
                if 0 <= t - e["start"] - bt < 0.4:
                    shake_t = t - e["start"] - bt
        if shake_t is not None and 0 <= shake_t < 0.5:
            amp = 26 * (1 - shake_t / 0.5) * cw / 1080
            sx = amp * math.sin(shake_t * 90)
            sy = amp * math.cos(shake_t * 70)
        x0 = min(max(0, cx - cw / 2 + sx), WW - cw)
        y0 = min(max(0, cy - ch / 2 + sy), WH - ch)
        return int(x0), int(y0), int(cw), int(ch)

    def char_state(self, name, e, t, frame):
        tr = t - e["start"]
        expr = e.get("expr", {}).get(name, "")
        if e.get("expr2") and name in e["expr2"] and tr > e["dur"] * 0.45:
            expr = e["expr2"][name]
        pose = e.get("pose", {}).get(name, "")
        extra = e.get("extra", {}).get(name, "")
        mouth = 0
        if name in e.get("chew", []):
            mouth = int(t * 5) % 2
        if e.get("who") == name and "mouth" in e:
            i = int(tr * FPS)
            m = e["mouth"]
            v = m[i] if 0 <= i < len(m) else 0
            mouth = 0 if v < 0.22 else (1 if v < 0.65 else 2)
        # Blick: zum Sprecher, sonst geradeaus
        look = (0.0, 0.1)
        if e.get("who") in HEADS and e["who"] != name:
            sx_, sy_ = HEADS[e["who"]]
            mx, my = HEADS[name]
            dx, dy = sx_ - mx, sy_ - my
            n = math.hypot(dx, dy) + 1e-6
            look = (round(dx / n, 1), round(dy / n * 0.8, 1))
        if name in e.get("look", {}):
            look = tuple(e["look"][name])
        off = {"richard": 0.0, "klaus": 1.3, "horst": 2.1, "dennis": 0.7, "sabine": 1.9}[name]
        blink = ((t + off) % 3.6) < 0.11 and expr not in ("shock",)
        phase = 0
        if expr == "twitch":
            phase = int(t * 6) % 2
        elif (expr or chars.DEFAULT_EXPR[name]) == "bored":
            phase = 1 if ((t + off) % 3.0) < 0.6 else 0
        return chars.sprite(name, expr, mouth, blink, look, pose, extra, phase)

    def render(self, t, frame):
        e = self.event_at(t)
        tr = t - e["start"]
        if e.get("freeze") is None and e["id"] == "23":
            pass
        x0, y0, cw, ch = self.camera(e, t)
        base = self.bg.crop((x0, y0, x0 + cw, y0 + ch))

        def put(sp, wx, wy):
            if wx + sp.width < x0 or wx > x0 + cw or wy + sp.height < y0 or wy > y0 + ch:
                return
            base.paste(sp, (wx - x0, wy - y0), sp)

        hide = set(e.get("hide", []))
        horst_pos = HORST_FINAL if e.get("horst_final") else HEADS["horst"]
        bob = lambda nm: int(4 * math.sin(t * 2.2 + hash(nm) % 7))
        # Richter (hinter dem Tisch)
        hx, hy = HEADS["richard"]
        put(self.char_state("richard", e, t, frame), hx - HX, hy - HY + bob("r"))
        if "horst" not in hide and e.get("horst_final"):
            put(self.char_state("horst", e, t, frame), horst_pos[0] - HX, horst_pos[1] - HY)
        put(self.bench, 0, self.bench_y)
        gavel_up = "gavel" in e.get("fx", []) and not (0.0 <= tr < 0.18 or 0.4 <= tr < 0.6)
        if "gavel" in e.get("fx", []) and tr > 1.0:
            gavel_up = False
        sparkle = "sparkle_doener" in e.get("fx", []) and int(t * 6) % 2 == 0
        pl, (px, py) = props_layer(e.get("doener", "none" if EP == "02" else "full"), gavel_up, sparkle)
        put(pl, px, py)
        if "horst" not in hide and not e.get("horst_final"):
            put(self.char_state("horst", e, t, frame), horst_pos[0] - HX, horst_pos[1] - HY + bob("h"))
        put(self.rail, 0, self.rail_y)
        for nm in ("dennis", "sabine", "klaus"):
            hx, hy = HEADS[nm]
            put(self.char_state(nm, e, t, frame), hx - HX, hy - HY + bob(nm))
        put(self.legs, 0, self.legs_y)
        put(self.tables, 0, self.tables_y)
        if EP == "02":
            put(self.ball, 1290, 2800)
            if self.events.index(e) >= self.folder_idx:
                put(self.folder, 95, 2830)

        img = base.resize((W, H), Image.BILINEAR, reducing_gap=2.0 if cw > 1400 else None)

        # --- Effekte & Text
        fx = e.get("fx", [])
        if "lines" in fx and tr < 1.6:
            img.paste(speed_lines(int(t * 10) % 3), (0, 0), speed_lines(int(t * 10) % 3))
        if "gavel" in fx:
            bam(img, tr - 0.02)
            bam(img, tr - 0.42, "BÄM!!")
        if "bang" in fx:
            bam(img, tr - 0.05, "WUMMS!")
        d = ImageDraw.Draw(img)
        draw_logo(img)
        if e["id"] == "p3" or e.get("cricket_text"):
            big_text(img, [("*zirp* … *zirp*", (255, 255, 255))], 560, tr, 54, 0)
        if "big" in e:
            bg = e["big"]
            big_text(img, bg["lines"], bg.get("y", 420), tr - bg.get("at", 0) * e["dur"] + (0.4 if bg.get("instant") else 0),
                     bg.get("size", 74))
        if e.get("hook") and EP == "01":
            big_text(img, [("SCHEIDUNG", (255, 255, 255)), ("WEGEN DÖNER?!", (255, 220, 40))], 400, tr, 74)
        if e.get("law"):
            shown = [(i, c) for i, c in enumerate(LAW_CARDS) if tr >= c[0] * e["dur"]]
            for slot, (i, c) in enumerate(shown[-3:]):
                law_card(img, 350 + slot * 168, tr - c[0] * e["dur"], c[1], c[2])
            fsm = font(F_INTER_B, 30)
            d.text((CX, 1480), "Satire · Recht echt · keine Rechtsberatung", font=fsm, fill=(255, 255, 255),
                   stroke_width=4, stroke_fill=(15, 12, 20), anchor="mm")
        if e["id"] == "23" and END_LINES:
            big_text(img, END_LINES, 1000, tr, 84, -2)
        if e["id"] == "23":
            if END_LINES:
                pass
            else:
                big_text(img, [("TEAM DENNIS", (120, 200, 255)), ("oder", (255, 255, 255)), ("TEAM SABINE?", (255, 140, 200))],
                     1040, tr, 74, -2)
            if tr > 0.6:
                fsm = font(F_UNB, 36)
                d.rounded_rectangle([CX - 380, 1400, CX + 380, 1480], radius=40, fill=(210, 30, 50), outline=(15, 12, 20), width=6)
                d.text((CX, 1440), "FOLGT UNS FÜR NEUE FÄLLE!", font=fsm, fill=(255, 255, 255), anchor="mm")
        if e["id"] == "p4":
            big_text(img, [("FEIERABEND.", (255, 255, 255))], 1060, tr - 0.3, 84, 0)
        if e["id"] == "p5":
            big_text(img, [("AUCH RICHTER", (255, 255, 255)), ("HABEN HUNGER.", (255, 220, 40))], 1060, tr, 76, 0)
        if "text" in e and tr <= e["dur"] - (e.get("post", 0)):
            y_sub = 1330 if (e.get("law") or e["id"] == "23") else 1230
            draw_subtitle(img, e, tr, y_sub)
        return img


def main():
    sc = Scene()
    args = sys.argv[1:]
    if args and args[0] == "preview":
        out = B / "stills"
        out.mkdir(exist_ok=True)
        for a in args[1:]:
            t = float(a)
            sc.render(t, int(t * FPS)).save(out / f"t{t:05.1f}.png")
            print("ok", t)
        return
    n = int(sc.total * FPS)
    if args and args[0] == "part":
        k, parts = int(args[1]), int(args[2])
        a, b = n * k // parts, n * (k + 1) // parts
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
               "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
               str(B / f"part{k}.mp4")]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for i in range(a, b):
            p.stdin.write(sc.render(i / FPS, i).convert("RGB").tobytes())
            if (i - a) % 150 == 0:
                print(f"[{k}] {i - a}/{b - a}", flush=True)
        p.stdin.close()
        p.wait()
        return
    if args and args[0] == "mux":
        parts = int(args[1])
        lst = B / "parts.txt"
        lst.write_text("".join(f"file '{B / f'part{k}.mp4'}'\n" for k in range(parts)))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(B / "mix.wav"),
                        "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
                        str(OUT_FILE)], check=True)
        print("fertig:", OUT_FILE)
        return
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(B / "mix.wav"), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT_FILE)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        img = sc.render(i / FPS, i)
        p.stdin.write(img.convert("RGB").tobytes())
        if i % 150 == 0:
            print(f"{i}/{n}", flush=True)
    p.stdin.close()
    p.wait()
    print("fertig:", OUT_FILE)


if __name__ == "__main__":
    main()
