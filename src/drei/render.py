"""Render drei-handys.mp4 – dark minimal 'three people' format (no voice, text + ambient score).

Three stacked rooms: AUSREDE, MOTIVATION, DISZIPLIN (gold). Every night at 22:00 all three
phones light up; only DISZIPLIN puts it away every night and gets up every morning.
Day counter 1 -> 365, window shows night/morning, door opens into light.

    python3 render.py            # -> ../../drei-handys.mp4
    python3 render.py preview 3 12 30
"""
import math
import random
import subprocess
import sys
import wave
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent.parent
BUILD = ROOT / "build" / "drei"
BUILD.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "drei-handys.mp4"
W, H, FPS, S = 1080, 1920, 30, 2
F_TXT = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
F_BIG = str(ROOT / "fonts" / "Unbounded_900Black.ttf")
RED = (255, 184, 48)        # signature gold for DISZIPLIN
LABEL_COLS = [(150, 140, 200), (80, 210, 200), (255, 184, 48)]   # Ausrede violet, Motivation teal, Disziplin gold
WHITE = (245, 245, 245)
BLUE = (90, 160, 255)

ROWS = [("AUSREDE", 960), ("MOTIVATION", 1330), ("DISZIPLIN", 1700)]   # label, platform y
BED_X = 300                    # pillow / head x
DOOR_X = 960

# ------------------------------------------------------------------ timeline
INTRO = 2.8                    # hook card
DAYS = [(1, 9.0), (2, 4.5), (3, 5.0), (7, 1.9), (21, 1.9), (66, 1.9), (150, 1.9), (365, 6.0)]
DSTART = []
_t = INTRO
for d, L in DAYS:
    DSTART.append(_t)
    _t += L
OUTRO0 = _t
TOTAL = OUTRO0 + 7.0
NFRAMES = int(math.ceil(TOTAL * FPS))


def c01(x):
    return min(max(x, 0.0), 1.0)


def ease(x):
    x = c01(x)
    return x * x * (3 - 2 * x)


def day_at(t):
    """(index, day number, phase 0..1) – before intro end: day 1 phase 0."""
    for i in range(len(DAYS) - 1, -1, -1):
        if t >= DSTART[i]:
            return i, DAYS[i][0], c01((t - DSTART[i]) / DAYS[i][1])
    return 0, 1, 0.0


def mot_gets_up(day):
    return day in (1, 2)


def state(who, t):
    """Pose of a person: dict(pose, x, k (transition 0..1), phone (bool), alpha)."""
    if t >= OUTRO0:
        if who == 2:
            return dict(pose="gone")
        return dict(pose="lie", phone=True, alpha=0.55 if who == 0 else 0.8)
    i, day, p = day_at(t)
    night_off = 0.18                       # when phones are put away
    alpha = 1.0 - (0.45 * i / (len(DAYS) - 1) if who == 0 else 0)   # AUSREDE fades over the year
    if who == 2 or (who == 1 and mot_gets_up(day)):
        if p < 0.5:
            return dict(pose="lie", phone=p < (0.22 if who == 2 else night_off + 0.05), alpha=alpha)
        if p < 0.6:
            return dict(pose="sit", k=ease((p - 0.5) / 0.1), alpha=alpha)
        k = (p - 0.6) / 0.28
        if k < 1:
            return dict(pose="walk", x=BED_X + 150 + (DOOR_X - BED_X - 150) * ease(k), k=k, alpha=alpha)
        return dict(pose="gone")
    if who == 1:                            # MOTIVATION: sits up, then falls back + scrolls
        if 0.55 < p < 0.75 and day == 3:
            return dict(pose="sit", k=1.0, alpha=alpha)
        return dict(pose="lie", phone=not (night_off < p < 0.3), alpha=alpha)
    return dict(pose="lie", phone=True, alpha=alpha)       # AUSREDE: always scrolling


# ------------------------------------------------------------------ static scene
@lru_cache(maxsize=1)
def base():
    im = Image.new("RGB", (W * S, H * S), (10, 12, 30))
    d = ImageDraw.Draw(im)
    sc = lambda *v: [x * S for x in v]
    for label, y in ROWS:
        # platform: top face (perspective) + front face
        d.polygon(sc(90, y + 10, 990, y + 10, 950, y - 150, 130, y - 150), fill=(32, 36, 72))
        d.rectangle(sc(90, y + 10, 990, y + 70), fill=(18, 20, 46))
        # nightstand + bed
        d.rectangle(sc(130, y - 110, 210, y - 10), fill=(48, 52, 94))
        d.rectangle(sc(240, y - 90, 780, y - 10), fill=(56, 60, 106))
        d.rectangle(sc(240, y - 115, 780, y - 90), fill=(70, 74, 122))
        d.rectangle(sc(250, y - 130, 360, y - 100), fill=(106, 110, 156))           # pillow
        d.rectangle(sc(360, y - 125, 770, y - 92), fill=(84, 88, 136))           # blanket
    # door frame (bottom room)
    y = ROWS[2][1]
    d.rectangle(sc(DOOR_X - 60, y - 330, DOOR_X + 60, y), fill=(24, 26, 56))
    # window
    d.rectangle(sc(380, 440, 700, 650), fill=(16, 18, 42))
    im = im.filter(ImageFilter.GaussianBlur(1.2 * S))
    # top light cone + vignette
    lay = Image.new("L", im.size, 0)
    ImageDraw.Draw(lay).ellipse(sc(-150, -300, W + 150, 1900), fill=60)
    lay = lay.filter(ImageFilter.GaussianBlur(200 * S))
    im = Image.composite(Image.new("RGB", im.size, (44, 50, 100)), im, lay)
    return im


@lru_cache(maxsize=8)
def glow_sprite(col, r):
    g = Image.new("RGBA", (4 * r, 4 * r), col + (0,))
    ImageDraw.Draw(g).ellipse([r, r, 3 * r, 3 * r], fill=col + (170,))
    return g.filter(ImageFilter.GaussianBlur(r * 0.6))


F_EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
F_BOLD = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"


@lru_cache(maxsize=64)
def emoji(ch, size):
    im = Image.new("RGBA", (150, 150), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((75, 75), ch, font=ImageFont.truetype(F_EMOJI, 109), embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox())
    k = size / max(im.size)
    return im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)


def put_emoji(img, ch, x, y, size, scale=S):
    if size < 4:
        return
    e = emoji(ch, int(size * scale))
    img.alpha_composite(e, (int(x * scale - e.width / 2), int(y * scale - e.height / 2)))


def bubble(img, x, y, text, p, gold=False):
    """Speech bubble with tail pointing down-left to (x, y)."""
    if p <= 0.02:
        return
    d = ImageDraw.Draw(img, "RGBA")
    f = ImageFont.truetype(F_BOLD, int(36 * S * min(1, p)))
    tw = f.getlength(text) / S
    x0, y0 = x + 30, y - 110
    x1, y1 = x0 + tw + 44, y0 + 66
    bg = (255, 190, 60) if gold else (245, 245, 250)
    d.rounded_rectangle([x0 * S, y0 * S, x1 * S, y1 * S], 22 * S, fill=bg)
    d.polygon([(x0 + 24) * S, y1 * S, (x0 + 60) * S, y1 * S, x * S, (y - 20) * S], fill=bg)
    d.text(((x0 + 22) * S, (y0 + 33) * S), text, font=f, fill=(20, 18, 40), anchor="lm")


# night / morning lines (days 1-3)
SAY_NIGHT = ["Nur noch 5 Minuten…", "Ab morgen wirklich!", "HANDY WEG."]
SAY_MORNING = {0: "Snooze…", 1: {1: "Los geht's!", 2: "Okay… los.", 3: "…ab morgen."}}
DOOR_ACT = ["⚽", "🏋️", "📚", "🏃", "🎸", "📚", "⚽", "🏆"]
STATUS = [("😴", "📉"), ("😩", "📉"), ("💪", "📈")]


def put_glow(img, x, y, col, r, a=1.0):
    g = glow_sprite(col, r)
    if a < 1:
        g = g.copy()
        g.putalpha(g.split()[3].point(lambda v: int(v * a)))
    img.alpha_composite(g, (int(x * S - g.width / 2), int(y * S - g.height / 2)))


# ------------------------------------------------------------------ drawing
def text_spaced(d, x, y, s, size, fill, spacing=0.18, anchor="mm", f=F_TXT):
    fo = ImageFont.truetype(f, int(size * S))
    widths = [fo.getlength(ch) + size * S * spacing for ch in s]
    tw = sum(widths) - size * S * spacing
    cx = x * S - (tw / 2 if anchor == "mm" else 0)
    for ch, w in zip(s, widths):
        d.text((cx, y * S), ch, font=fo, fill=fill, anchor="lm")
        cx += w


def figure(d, pose, y, st, t):
    a = int(255 * st.get("alpha", 1.0))
    col = (WHITE[0], WHITE[1], WHITE[2], a)
    sc = lambda *v: [x * S for x in v]
    lw = 13 * S
    if pose == "lie":
        d.ellipse(sc(BED_X - 32, y - 168, BED_X + 32, y - 104), fill=col)
        d.rectangle(sc(330, y - 140, 560, y - 100), fill=(96, 100, 148))          # body under blanket
    elif pose == "sit":
        k = st["k"]
        hx, hy = BED_X + 20 * k, y - 136 - 120 * k
        d.line(sc(hx + 5, hy + 35, BED_X + 30, y - 110), fill=col, width=lw)
        d.ellipse(sc(hx - 32, hy - 32, hx + 32, hy + 32), fill=col)
        d.line(sc(hx + 5, hy + 55, hx + 70, hy + 85), fill=col, width=lw)
    elif pose == "scroll":                  # sitting up in bed, scrolling on the phone
        hx, hy = BED_X + 20, y - 256
        d.line(sc(hx + 5, hy + 35, BED_X + 30, y - 110), fill=col, width=lw)
        d.ellipse(sc(hx - 32, hy - 32, hx + 32, hy + 32), fill=col)
        px, py = hx + 82, hy + 14
        d.line(sc(hx + 8, hy + 58, px - 6, py + 30), fill=col, width=lw)
        d.rounded_rectangle(sc(px - 22, py - 38, px + 22, py + 38), 7 * S, fill=(18, 20, 40))
        d.rectangle(sc(px - 17, py - 32, px + 17, py + 32), fill=(110, 175, 255))
        off = (t * 90) % 22
        for k in range(4):
            yy = py - 32 + ((k * 22 + off) % 64)
            if yy < py + 26:
                d.rectangle(sc(px - 12, yy, px + 12, yy + 7), fill=(225, 238, 255))
        ty = py + 18 - 14 * abs(math.sin(t * 6))              # thumb swiping
        d.ellipse(sc(px + 6, ty - 8, px + 22, ty + 8), fill=col)
    elif pose == "walk":
        x, k = st["x"], st["k"]
        sw = math.sin(k * 18) * 26
        fy = y - 20
        d.line(sc(x, fy - 120, x - sw, fy), fill=col, width=lw)
        d.line(sc(x, fy - 120, x + sw, fy), fill=col, width=lw)
        d.line(sc(x, fy - 120, x + 4, fy - 230), fill=col, width=lw)
        d.line(sc(x + 2, fy - 210, x - sw * 0.8, fy - 135), fill=col, width=lw)
        d.line(sc(x + 2, fy - 210, x + sw * 0.8, fy - 135), fill=col, width=lw)
        d.ellipse(sc(x - 32, fy - 300, x + 32, fy - 236), fill=col)


def clock_icon(d, x, y, shake):
    sc = lambda *v: [q * S for q in v]
    x += math.sin(shake * 60) * 5 * (shake > 0)
    d.ellipse(sc(x - 22, y - 22, x + 22, y + 22), outline=(180, 186, 225), width=4 * S)
    d.ellipse(sc(x - 28, y - 32, x - 12, y - 18), fill=(180, 186, 225))
    d.ellipse(sc(x + 12, y - 32, x + 28, y - 18), fill=(180, 186, 225))
    d.line(sc(x, y, x, y - 12), fill=(180, 186, 225), width=3 * S)
    d.line(sc(x, y, x + 9, y + 4), fill=(180, 186, 225), width=3 * S)


def render_frame(n):
    t = n / FPS
    img = base().copy().convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    sc = lambda *v: [q * S for q in v]
    i, day, p = day_at(t)
    outro = t >= OUTRO0
    morning = ease((p - 0.45) / 0.12) if not outro else 0.0
    # window: night (moon) -> morning
    sky = tuple(int(a + (b - a) * morning) for a, b in zip((14, 20, 58), (255, 170, 95)))
    d.rectangle(sc(392, 452, 688, 638), fill=sky)
    d.line(sc(540, 452, 540, 638), fill=(24, 26, 56), width=8 * S)
    if morning < 0.5:
        d.ellipse(sc(610, 480, 660, 530), fill=(230, 230, 230, int(255 * (1 - 2 * morning))))
        for k in range(12):
            r = random.Random(k)
            sx, sy = r.uniform(400, 680), r.uniform(460, 620)
            d.ellipse(sc(sx - 2, sy - 2, sx + 2, sy + 2), fill=(200, 200, 200))
    if morning > 0.2:
        sy = 640 - 70 * morning
        d.ellipse(sc(500, sy - 40, 580, sy + 40), fill=(255, 236, 170, int(255 * min(1, morning * 1.5))))
        d.rectangle(sc(392, 600, 688, 638), fill=(60, 50, 90))             # rooftops
    if morning > 0:
        put_glow(img, 540, 545, (255, 190, 110), 170, 0.6 * morning)
    # day counter + clock time
    text_spaced(d, 740, 510, f"TAG {day}", 44, (200, 204, 235), anchor="lm")
    # signature: golden year bar (day / 365)
    d.rounded_rectangle(sc(740, 600, 1000, 610), 4 * S, fill=(40, 44, 86))
    d.rounded_rectangle(sc(740, 600, 740 + max(8, 260 * day / 365), 610), 4 * S, fill=RED)
    text_spaced(d, 740, 550, "06:30" if morning > 0.5 else "22:00", 32, (130, 136, 180), anchor="lm")
    # door light (bottom room)
    y2 = ROWS[2][1]
    door = 0.0
    if not outro and p > 0.6 and DAYS[i][1] > 0:
        door = ease((p - 0.6) / 0.08) * (1 - ease((p - 0.9) / 0.08))
    if outro:
        door = ease((t - OUTRO0) / 0.8)
    if door > 0:
        d.rectangle(sc(DOOR_X - 52, y2 - 322, DOOR_X - 52 + 104 * door, y2), fill=(255, 230, 175))
        d.polygon(sc(DOOR_X - 52, y2, DOOR_X + 52, y2, DOOR_X + 60, y2 + 60, DOOR_X - 240 * door, y2 + 60),
                  fill=(255, 210, 140, int(80 * door)))
        put_glow(img, DOOR_X, y2 - 160, (255, 200, 120), 240, 0.7 * door)
        if door > 0.5:
            put_emoji(img, DOOR_ACT[min(i, len(DOOR_ACT) - 1)] if not outro else "🏆", DOOR_X, y2 - 180, 80 * door)
    # rooms: labels, clocks, phones, people
    for who, (label, y) in enumerate(ROWS):
        st = state(who, t)
        if st["pose"] == "lie" and st.get("phone"):
            st = dict(st, pose="scroll")
        dim = 0.35 if outro and who != 2 else 1.0
        ring = (not outro) and 0.5 < p < 0.62
        clock_icon(d, 170, y - 140, (t * 7) % 1 if ring else 0)
        phone_on = st.get("phone", False)
        d.rectangle(sc(150, y - 103, 186, y - 96), fill=(90, 160, 255) if phone_on else (60, 64, 100))
        if st["pose"] == "scroll":
            put_glow(img, BED_X + 70, y - 245, BLUE, 120, 0.95 * dim)
        lab_col = LABEL_COLS[who]
        if who == 2 and st["pose"] != "gone":
            put_glow(img, BED_X if st["pose"] != "walk" else st["x"], y - 160, RED, 110, 0.55)
        hx = BED_X if st["pose"] != "walk" else st["x"]
        if st["pose"] != "gone":
            ly = y - 210 if st["pose"] == "lie" else y - 330
            text_spaced(d, hx - 20, ly, label, 36, lab_col + (int(255 * dim),))
        if not outro and i <= 2:
            if 0.02 < p < 0.2 and who != 2:
                bubble(img, BED_X + 130, y - (200 if st["pose"] == "scroll" else 160), SAY_NIGHT[who], ease((p - 0.02) / 0.04), gold=who == 2)
            if 0.55 < p < 0.8 and who in SAY_MORNING:
                txt = SAY_MORNING[0] if who == 0 else SAY_MORNING[1][day]
                hy = y - 160 if st["pose"] == "lie" else y - 280
                bubble(img, (st.get("x", BED_X)) + 110, hy, txt, ease((p - 0.55) / 0.04))
        if who == 2 and not outro and 0.2 < p < 0.38:       # phone visibly goes into the drawer
            k = ease((p - 0.22) / 0.09)
            dr = 1 - abs(2 * ease((p - 0.21) / 0.15) - 1)       # drawer opens then closes
            d.rectangle(sc(132, y - 70, 208 + 40 * dr, y - 40), fill=(70, 74, 120))
            px, py = BED_X + 102 + (170 - BED_X - 102) * k, y - 242 + 187 * k
            if k < 0.98:
                d.rectangle(sc(px - 11, py - 18, px + 11, py + 18), fill=(160, 205, 255))
        if 3 <= i and not outro:                              # visible results during the time-lapse
            em, _ = STATUS[who]
            sz = 54 + (30 * i / 7 if who == 2 else 0)
            put_emoji(img, em, 880, y - 150, sz)
        if st["pose"] in ("lie", "sit", "walk", "scroll"):
            st = dict(st, alpha=st.get("alpha", 1) * dim)
            d2 = ImageDraw.Draw(img, "RGBA")
            figure(d2, st["pose"], y, st, t)
    # captions
    line1 = "UM 22 UHR LEUCHTETE BEI ALLEN DREIEN DAS HANDY."
    a0 = int(255 * c01(t / 0.8))
    text_spaced(d, W / 2, 215, "UM 22 UHR LEUCHTETE", 46, (235, 235, 240, a0), spacing=0.06)
    text_spaced(d, W / 2, 275, "BEI ALLEN DREIEN DAS HANDY.", 46, (235, 235, 240, a0), spacing=0.06)
    if t > DSTART[-1] + 0.5:
        a = int(255 * c01((t - DSTART[-1] - 0.5) / 0.8))
        text_spaced(d, W / 2, 350, "NUR EINER LEGTE ES", 46, (255, 200, 90, a), spacing=0.06)
        text_spaced(d, W / 2, 405, "JEDEN ABEND WEG.", 46, (255, 200, 90, a), spacing=0.06)
    frame = img.resize((W, H), Image.LANCZOS)
    if i == 0 and not outro:                                  # zoom onto DISZIPLIN while he puts the phone away
        z = ease((p - 0.2) / 0.05) * (1 - ease((p - 0.38) / 0.05))
        if z > 0:
            zz = 1 + 0.5 * z
            cx, cy = 540 + (400 - 540) * z, 960 + (1460 - 960) * z
            cw, ch = W / zz, H / zz
            x0 = min(max(cx - cw / 2, 0), W - cw)
            y0 = min(max(cy - ch / 2, 0), H - ch)
            frame = frame.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.BICUBIC)
            shade = Image.new("L", (1, H))
            shade.putdata([int(235 * z * max(0, 1 - yy / (H * 0.42))) for yy in range(H)])
            frame.alpha_composite(Image.merge("RGBA", [Image.new("L", (W, H), v) for v in (8, 10, 28)] + [shade.resize((W, H))]))
            if 0.26 < p < 0.4:
                q = ease((p - 0.26) / 0.03)
                ff = ImageFont.truetype(F_BIG, int(110 * max(q, 0.05)))
                ImageDraw.Draw(frame).text((W / 2, 380), "HANDY WEG.", font=ff, fill=(255, 190, 60), anchor="mm",
                                           stroke_width=6, stroke_fill=(10, 12, 30))
    if t < INTRO:                                             # hook card
        dd = ImageDraw.Draw(frame, "RGBA")
        fade = 1 - ease((t - INTRO + 0.4) / 0.4)
        dd.rectangle([0, 0, W, H], fill=(8, 10, 28, int(225 * fade)))
        fb = ImageFont.truetype(F_BIG, 104)
        for k, (txt, col, t0) in enumerate((("3 TEENS.", (255, 255, 255), 0.1), ("1 HANDY.", (120, 180, 255), 0.6),
                                             ("NUR EINER", (255, 190, 60), 1.2), ("SCHAFFT'S.", (255, 190, 60), 1.4))):
            a = int(255 * c01((t - t0) / 0.15) * fade)
            if a > 0:
                dd.text((W / 2, 690 + k * 150), txt, font=fb, fill=col + (a,), anchor="mm")
    if outro:
        lt = t - OUTRO0
        dd = ImageDraw.Draw(frame, "RGBA")
        a1 = int(230 * ease((lt - 1.2) / 0.8))
        dd.rectangle([0, 0, W, H], fill=(8, 10, 28, int(a1 * 0.8)))
        if lt > 1.4:
            f = ImageFont.truetype(F_BIG, 150)
            dd.text((W / 2, 820), "SEI DER", font=f, fill=(255, 255, 255, a1), anchor="mm")
            dd.text((W / 2, 1000), "EINE.", font=f, fill=RED + (a1,), anchor="mm")
        if lt > 3.0:
            a2 = int(255 * ease((lt - 3.0) / 0.6))
            ft = ImageFont.truetype(F_TXT, 56)
            dd.text((W / 2, 1210), "Wer bist du – 1, 2 oder 3?", font=ft, fill=(230, 230, 232, a2), anchor="mm")
            dd.text((W / 2, 1290), "Schreib's in die Kommentare.", font=ft, fill=(160, 160, 165, a2), anchor="mm")
    if t < 0.15:
        frame.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * (1 - t / 0.15)))))
    if t > TOTAL - 0.6:
        frame.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * c01((t - TOTAL + 0.6) / 0.6)))))
    return frame.convert("RGB").tobytes()


# ------------------------------------------------------------------ ambient score
SR = 44100


def make_audio():
    n = int(TOTAL * SR)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(5)
    out = np.zeros(n)
    # dark drone (Am), swelling towards day 365
    swell = np.clip((tt - DSTART[3]) / (DSTART[-1] - DSTART[3]), 0, 1)
    for f, a in ((55, 0.22), (110, 0.12), (164.8, 0.06), (220, 0.04)):
        out += a * (0.6 + 0.4 * swell) * np.sin(2 * np.pi * f * tt + np.sin(tt * 0.3))
    # piano-ish notes (sparse)
    notes = [440, 523.3, 659.3, 587.3, 523.3, 440, 392, 440]
    L = int(2.5 * SR)
    lt = np.arange(L) / SR
    for k, t0 in enumerate(np.arange(0.5, TOTAL - 3, 1.9)):
        f = notes[k % len(notes)]
        tone = (np.sin(2 * np.pi * f * lt) + 0.3 * np.sin(4 * np.pi * f * lt)) * np.exp(-lt * 2.2) * 0.16
        i = int(t0 * SR)
        out[i:i + L] += tone[:max(0, min(L, n - i))]
    # clock ticks + alarm beeps each morning, heartbeat in the montage
    tick = rng.standard_normal(int(0.01 * SR)) * 0.08
    for k in range(int(TOTAL * 2)):
        i = int(k * 0.5 * SR)
        if k * 0.5 < OUTRO0:
            out[i:i + len(tick)] += tick[:max(0, min(len(tick), n - i))]
    bl = int(0.09 * SR)
    beep = np.sign(np.sin(2 * np.pi * 1400 * np.arange(bl) / SR)) * 0.07
    for (d, L2), s0 in zip(DAYS, DSTART):
        for j in range(3 if L2 > 3 else 1):
            i = int((s0 + L2 * 0.5 + j * 0.18) * SR)
            out[i:i + bl] += beep[:max(0, min(bl, n - i))]
    kl = int(0.3 * SR)
    kt = np.arange(kl) / SR
    kick = np.sin(2 * np.pi * (45 + 60 * np.exp(-kt * 25)) * kt) * np.exp(-kt * 9)
    t0 = DSTART[3]
    while t0 < OUTRO0:
        for off in (0, 0.22):
            i = int((t0 + off) * SR)
            out[i:i + kl] += 0.45 * kick[:max(0, min(kl, n - i))]
        t0 += 0.85
    # outro hit
    bl2 = int(2.5 * SR)
    bt = np.arange(bl2) / SR
    boom = np.sin(2 * np.pi * (35 + 70 * np.exp(-bt * 6)) * bt) * np.exp(-bt * 1.5)
    i = int((OUTRO0 + 1.3) * SR)
    out[i:i + bl2] += 0.9 * boom[:max(0, min(bl2, n - i))]
    out *= np.clip(tt / 1.0, 0, 1) * np.clip((TOTAL - tt) / 1.2, 0, 1)
    out = out / np.abs(out).max() * 0.9
    p = BUILD / "score.wav"
    with wave.open(str(p), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((out * 32767).astype(np.int16).tobytes())
    return p


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        d = BUILD / "stills"
        d.mkdir(exist_ok=True)
        for a in sys.argv[2:]:
            Image.frombytes("RGB", (W, H), render_frame(int(float(a) * FPS))).save(d / f"t{float(a):05.1f}.png")
        print("stills ->", d, "total", round(TOTAL, 1))
        return
    audio = make_audio()
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", str(audio), "-af", "loudnorm=I=-14:TP=-1",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)],
                          stdin=subprocess.PIPE)
    with Pool() as pool:
        for fr in pool.imap(render_frame, range(NFRAMES), chunksize=6):
            ff.stdin.write(fr)
    ff.stdin.close()
    ff.wait()
    print("->", OUT)


if __name__ == "__main__":
    main()
