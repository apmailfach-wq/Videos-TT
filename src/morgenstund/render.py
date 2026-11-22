"""Short test: 'Morgenstund hat Gold im Mund' - 2-panel split screen, dark glowing stick figures, no voice.

Top: early riser gets up at 06:00 and gets things done. Bottom: snoozer hits snooze until 07:45, panic.
Red digital clock between the panels, proverb as punchline, end card "1 oder 2?", seamless loop.

    python3 render.py               # -> ../../morgenstund-video.mp4
    python3 render.py preview 1 4 9 11 14
"""
import math
import os
import subprocess
import sys
import wave
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pfennig"))
import render as R  # noqa: E402  (shared helpers: figure, fonts, emoji, bubbles, sounds)

from render import (WHITE, GOLD, RED, DIM, F_K, F_B, F_M, font, c01, ease_out, ease_io,  # noqa: E402
                    emoji, bubble_img, text_c, piano, boom, tick, clink, env)

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "morgenstund"
BUILD.mkdir(parents=True, exist_ok=True)
W, H, FPS = 1080, 1920, 30
TOTAL = 16.0
PW, PH = 1000, 640
PY = [300, 1060]               # panel tops
FLOOR = 560
T_RING, T_OFF, T_SNOOZE = 1.0, 1.8, 2.1
T_RUN0, T_RUN1 = 2.6, 8.0      # clock 06:00 -> 07:45
T_PANIC, T_REV, T_END = 8.1, 10.2, 12.6
LOOP = 0.35


def clock_min(t):
    if t < T_RING:
        return 359
    if t < T_RUN0:
        return 360
    if t < T_RUN1:
        u = (t - T_RUN0) / (T_RUN1 - T_RUN0)
        return 360 + int(105 * (0.35 * u + 0.65 * ease_io(u)))
    return 465 + (1 if t > T_PANIC + 0.8 else 0)


def snoozes():
    """Times the snoozer's alarm rings again (every 10 clock minutes)."""
    out, last = [], 360
    t = T_RUN0
    while t < T_RUN1:
        m = clock_min(t)
        if m // 10 > last // 10:
            out.append(t)
            last = m
        t += 1 / 120
    return out


SNOOZE = snoozes()


# ------------------------------------------------------------------ room
def sky_col(t):
    m = clock_min(t)
    u = c01((m - 360) / 90)
    night, dawn, day = np.array([22, 28, 60]), np.array([250, 150, 90]), np.array([255, 200, 120])
    c = night + (dawn - night) * c01(u * 2) if u < 0.5 else dawn + (day - dawn) * c01(u * 2 - 1)
    return tuple(int(v) for v in c)


def draw_room(d, ss, t, panel):
    S = lambda v: int(v * ss)  # noqa: E731
    # back wall / floor
    d.rounded_rectangle([0, 0, S(PW), S(PH)], radius=S(28), fill=(24, 28, 50))
    d.rectangle([0, S(FLOOR), S(PW), S(PH)], fill=(18, 20, 38))
    d.line([S(30), S(FLOOR), S(PW - 30), S(FLOOR)], fill=(48, 54, 90), width=S(3))
    # window with sky + sun/moon
    sc = sky_col(t)
    d.rounded_rectangle([S(600), S(110), S(860), S(330)], radius=S(8), fill=sc, outline=(60, 70, 110), width=S(5))
    m = clock_min(t)
    u = c01((m - 360) / 105)
    if u < 0.25:
        d.ellipse([S(800), S(140), S(830), S(170)], fill=(235, 240, 255))
    sy = 330 - 170 * u
    if u > 0.05:
        d.ellipse([S(700), S(sy - 30), S(760), S(sy + 30)], fill=(255, 230, 150))
    d.line([S(730), S(110), S(730), S(330)], fill=(60, 70, 110), width=S(5))
    d.line([S(600), S(220), S(860), S(220)], fill=(60, 70, 110), width=S(5))
    # door
    d.rectangle([S(890), S(250), S(970), S(FLOOR)], fill=(40, 46, 78), outline=(60, 70, 110), width=S(4))
    d.ellipse([S(900), S(400), S(912), S(412)], fill=GOLD)
    # bed
    d.rounded_rectangle([S(60), S(440), S(440), S(500)], radius=S(10), fill=(54, 62, 104))
    d.rectangle([S(60), S(380), S(80), S(FLOOR)], fill=(70, 78, 120))
    d.rectangle([S(430), S(430), S(450), S(FLOOR)], fill=(70, 78, 120))
    d.rounded_rectangle([S(90), S(408), S(180), S(445)], radius=S(14), fill=(200, 206, 230))
    # nightstand + alarm clock
    d.rectangle([S(470), S(470), S(560), S(FLOOR)], fill=(46, 52, 88))
    ring = alarm_ringing(t, panel)
    jx = math.sin(t * 90) * 5 if ring else 0
    cx, cy = 515 + jx, 440
    d.ellipse([S(cx - 26), S(cy - 26), S(cx + 26), S(cy + 26)], fill=(230, 80, 80) if ring else (120, 130, 170))
    d.ellipse([S(cx - 18), S(cy - 18), S(cx + 18), S(cy + 18)], fill=(240, 244, 255))
    for bx in (-20, 20):
        d.ellipse([S(cx + bx - 9), S(cy - 36), S(cx + bx + 9), S(cy - 20)], fill=(230, 80, 80) if ring else (120, 130, 170))
    d.line([S(cx), S(cy), S(cx), S(cy - 12)], fill=(30, 30, 40), width=S(3))
    d.line([S(cx), S(cy), S(cx + 9), S(cy)], fill=(30, 30, 40), width=S(3))
    if ring:
        for k in (1, 2):
            r = 36 + k * 14 + (t * 60) % 14
            d.arc([S(cx - r), S(cy - r), S(cx + r), S(cy + r)], 200, 340, fill=(255, 120, 120), width=S(3))
    # desk + laptop (under the window)
    d.rectangle([S(600), S(440), S(840), S(458)], fill=(70, 78, 120))
    d.rectangle([S(615), S(458), S(630), S(FLOOR)], fill=(60, 68, 108))
    d.rectangle([S(810), S(458), S(825), S(FLOOR)], fill=(60, 68, 108))
    lit = panel == 0 and t > 3.4
    d.polygon([(S(690), S(440)), (S(770), S(440)), (S(760), S(380)), (S(700), S(380))],
              fill=(150, 200, 255) if lit else (60, 68, 108))


def alarm_ringing(t, panel):
    if T_RING <= t < (T_OFF if panel == 0 else T_SNOOZE):
        return True
    if panel == 1:
        return any(s <= t < s + 0.35 for s in SNOOZE) or (T_RUN1 - 0.1 <= t < T_PANIC + 0.3)
    return False


def lying(d, ss, x, mood, t, arm=0.0):
    """Person in bed: head on pillow, blanket over the body, optional arm reaching to the alarm."""
    S = lambda v: int(v * ss)  # noqa: E731
    d.rounded_rectangle([S(160), S(415), S(430), S(470)], radius=S(26), fill=(90, 100, 160))
    hx, hy = 150, 412
    d.ellipse([S(hx - 27), S(hy - 27), S(hx + 27), S(hy + 27)], fill=WHITE)
    fc = (24, 26, 44)
    d.line([S(hx - 13), S(hy - 4), S(hx - 3), S(hy - 4)], fill=fc, width=S(3))
    d.line([S(hx + 5), S(hy - 4), S(hx + 15), S(hy - 4)], fill=fc, width=S(3))
    d.line([S(hx - 6), S(hy + 11), S(hx + 8), S(hy + 11)], fill=fc, width=S(3))
    if arm > 0:
        ex = 230 + (500 - 230) * arm
        d.line([S(220), S(425), S(ex), S(425 - 10 * arm)], fill=WHITE, width=S(8))


def draw_person(d, ss, t, panel):
    if panel == 0:
        if t < T_OFF:
            lying(d, ss, 150, 0, t, arm=c01((t - T_RING - 0.4) / 0.3))
        elif t < 2.5:                       # sits up in bed (blanket hides the legs)
            R.figure(d, 200, 505, ss, arm_f=20, arm_b=-20, mood=0.4)
            S = lambda v: int(v * ss)  # noqa: E731
            d.rounded_rectangle([S(120), S(400), S(430), S(510)], radius=S(26), fill=(90, 100, 160))
        else:                               # walks to the desk and works
            u = ease_io((t - 2.5) / 0.9)
            x = 300 + (650 - 300) * u
            bob = abs(math.sin(t * 14)) * 6 if u < 1 else 0
            typing = 30 + 10 * math.sin(t * 25) if u >= 1 else 15
            mood = 0.5 if t < T_PANIC else 1.0
            R.figure(d, x, FLOOR - bob, ss, arm_f=typing, arm_b=-15 if u < 1 else 25, mood=mood,
                     arms_up=ease_out((t - T_REV) / 0.4) * 0.9 if t > T_REV else 0)
            S = lambda v: int(v * ss)  # noqa: E731
            if u >= 1:   # desk front hides legs
                d.rectangle([S(600), S(440), S(840), S(458)], fill=(70, 78, 120))
    else:
        if t < T_PANIC:
            hit = 0.0
            if T_SNOOZE - 0.3 < t < T_SNOOZE + 0.2:
                hit = 1 - abs(t - T_SNOOZE) / 0.3
            for s in SNOOZE:
                if s + 0.05 < t < s + 0.45:
                    hit = max(hit, 1 - abs(t - s - 0.25) / 0.2)
            lying(d, ss, 150, 0, t, arm=c01(hit))
            if t > T_SNOOZE + 0.6:          # zzz
                for k in range(3):
                    ph = (t * 0.7 + k / 3) % 1
                    d.text((int((170 + 30 * ph + k * 6) * ss), int((380 - 70 * ph) * ss)), "z",
                           font=font(F_K, int((26 + 14 * ph) * ss)), fill=(200, 210, 255, int(255 * (1 - ph))))
        else:                               # panic: jumps up and runs to the door
            u = ease_io((t - T_PANIC - 0.9) / 0.8)
            x = 300 + (930 - 300) * u
            bob = abs(math.sin(t * 22)) * 10
            R.figure(d, x, FLOOR - bob, ss, arm_f=60 * math.sin(t * 22), arm_b=-60 * math.sin(t * 22), mood=-1,
                     arms_up=0.9 if t < T_PANIC + 0.9 else 0)
            if t > T_PANIC + 0.2:           # sweat drop
                S = lambda v: int(v * ss)  # noqa: E731
                d.ellipse([S(x + 30), S(FLOOR - 300), S(x + 42), S(FLOOR - 282)], fill=(130, 200, 255))


BUBBLES = {
    0: [(T_OFF + 0.05, 3.3, "Los geht's!"), (4.8, 6.6, "Sport, Lernen, Kaffee – fertig!"), (T_PANIC, T_REV, "Läuft.")],
    1: [(T_SNOOZE + 0.05, 3.9, "Nur noch 5 Minuten …"), (5.0, 6.3, "… nur noch 5."), (T_PANIC, T_REV, "07:45?! MIST!")],
}
LABELS = [("1 · FRÜHAUFSTEHER", GOLD), ("2 · SNOOZER", RED)]


def draw_panel(fr, t, panel):
    ss = 2
    lay = Image.new("RGBA", (PW * ss, PH * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    draw_room(d, ss, t, panel)
    pl = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    draw_person(ImageDraw.Draw(pl), ss, t, panel)
    pl = pl.resize((PW, PH), Image.LANCZOS)
    lay = lay.resize((PW, PH), Image.LANCZOS)
    # warm sunlight for the early riser
    if panel == 0 and t > 4.0:
        g = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
        a = int(70 * c01((t - 4.0) / 3))
        ImageDraw.Draw(g).polygon([(600, 110), (860, 110), (900, FLOOR), (420, FLOOR)], fill=(255, 200, 110, a))
        lay.alpha_composite(g.filter(ImageFilter.GaussianBlur(30)))
    lay.alpha_composite(pl.filter(ImageFilter.GaussianBlur(8)))
    lay.alpha_composite(pl)
    # panic red flash
    if panel == 1 and T_PANIC <= t < T_PANIC + 0.6 and int(t * 10) % 2 == 0:
        lay.alpha_composite(Image.new("RGBA", (PW, PH), (255, 40, 40, 60)))
    mask = Image.new("L", (PW, PH), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, PW - 1, PH - 1], radius=28, fill=255)
    x0, y0 = 40, PY[panel]
    fr.paste(lay, (x0, y0), mask)
    col = LABELS[panel][1]
    ImageDraw.Draw(fr).rounded_rectangle([x0, y0, x0 + PW - 1, y0 + PH - 1], radius=28, outline=col + (150,), width=3)
    # label chip
    d2 = ImageDraw.Draw(fr)
    txt, col = LABELS[panel]
    f = font(F_K, 34)
    tw = f.getlength(txt)
    d2.rounded_rectangle([W / 2 - tw / 2 - 24, y0 + 20, W / 2 + tw / 2 + 24, y0 + 74], radius=14, fill=(10, 12, 24),
                         outline=col, width=3)
    d2.text((W / 2, y0 + 48), txt, font=f, fill=col, anchor="mm")
    for b0, b1, txt in BUBBLES[panel]:
        if b0 <= t < b1:
            im = bubble_img(txt)
            sc = 0.6 + 0.4 * ease_out((t - b0) / 0.2)
            im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BICUBIC)
            fx = 210 if (panel == 0 and t < 2.5) or panel == 1 and t < T_PANIC else (200 if panel == 0 else 420)
            fr.alpha_composite(im, (int(x0 + fx), int(y0 + 120)))
    if T_REV <= t and panel == 1:
        fr.alpha_composite(Image.new("RGBA", (PW, PH), (6, 8, 16, int(170 * c01((t - T_REV) / 0.4)))), (x0, y0))


def draw_clock(fr, t):
    m = clock_min(t)
    txt = f"{m // 60:02d}:{m % 60:02d}"
    d = ImageDraw.Draw(fr)
    d.rounded_rectangle([W / 2 - 150, 958, W / 2 + 150, 1042], radius=18, fill=(8, 8, 14))
    blink = T_RING <= t < T_RUN0 and int(t * 4) % 2
    col = (255, 60, 60) if not blink else (120, 30, 30)
    tmp = Image.new("RGBA", (300, 84), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((150, 44), txt, font=font(F_K, 66), fill=col, anchor="mm")
    fr.alpha_composite(tmp.filter(ImageFilter.GaussianBlur(8)), (int(W / 2 - 150), 958))
    fr.alpha_composite(tmp, (int(W / 2 - 150), 958))
    if T_RUN0 < t < T_RUN1:
        e = emoji("⏩", 50)
        fr.alpha_composite(e, (int(W / 2 + 170), 975))


def draw_reveal(fr, t):
    p = t - T_REV
    fr.alpha_composite(Image.new("RGBA", (W, H), (6, 8, 16, int(120 * c01(p / 0.3)))))
    lines = [("MORGENSTUND", None), ("HAT", "GOLD"), ("IM MUND.", None)]
    f = font(F_K, 120)
    for i, (a, hl) in enumerate(lines):
        q = (p - 0.1 - i * 0.4) / 0.2
        if q <= 0:
            continue
        tmp = Image.new("RGBA", (W, 170), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        full = a + ((" " + hl) if hl else "")
        x = W / 2 - f.getlength(full) / 2
        td.text((x, 85), a, font=f, fill=WHITE, anchor="lm", stroke_width=6, stroke_fill=(8, 10, 20))
        if hl:
            hx = x + f.getlength(a + " ")
            td.rounded_rectangle([hx - 14, 22, hx + f.getlength(hl) + 14, 150], radius=18, fill=GOLD)
            td.text((hx, 85), hl, font=f, fill=(20, 16, 8), anchor="lm")
        sc = 1 + 0.6 * (1 - ease_out(q))
        if sc > 1.01:
            tmp = tmp.resize((int(W * sc), int(170 * sc)), Image.BICUBIC)
        fr.alpha_composite(tmp, (int(W / 2 - tmp.width / 2), int(720 + i * 170 - tmp.height / 2 + 85)))


def draw_end(fr, t):
    p = c01((t - T_END) / 0.35)
    if p <= 0:
        return
    fr.alpha_composite(Image.new("RGBA", (W, H), (8, 10, 20, int(246 * p))))
    if p < 1:
        return
    q = t - T_END - 0.35
    d = ImageDraw.Draw(fr)
    text_c(d, 470, "WER BIST DU –", font(F_K, 84), WHITE, 2)
    text_c(d, 575, "EHRLICH?", font(F_K, 84), GOLD, 2)
    for i, (col, lab) in enumerate([(GOLD, "Frühaufsteher"), (RED, "Snoozer")]):
        a = (q - 0.3 - i * 0.2) / 0.3
        if a <= 0:
            continue
        cx, cy = 340 + i * 400, 860
        act = q > 1.0 and int((q - 1.0) / 0.45) % 2 == i
        r = 120 * (0.4 + 0.6 * ease_out(a)) * (1.1 if act else 1)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(26, 30, 52), outline=col, width=12 if act else 7)
        d.text((cx, cy + 4), str(i + 1), font=font(F_K, int(140 * r / 120)), fill=col, anchor="mm")
        d.text((cx, cy + 175), lab, font=font(F_B, 40), fill=col, anchor="mm")
    if q > 0.8:
        text_c(d, 1180, "Schreib nur die Zahl in die Kommentare", font(F_B, 42), WHITE, 0)
        e = emoji("👇", 150)
        fr.alpha_composite(e, (int(W / 2 - e.width / 2), int(1230 + abs(math.sin(q * 5)) * 40)))


BG = None


def init():
    global BG
    R.init()
    BG = R.BG


def scene(t):
    fr = BG.copy()
    d = ImageDraw.Draw(fr)
    if t < T_REV:
        text_c(d, 165, "WECKER UM 6:00.", font(F_K, 76), WHITE, 2)
        text_c(d, 258, "NUR EINER STEHT AUF.", font(F_K, 60), GOLD, 2)
    for p in (0, 1):
        draw_panel(fr, t, p)
    draw_clock(fr, t)
    if T_REV <= t < T_END + 0.35:
        draw_reveal(fr, t)
    draw_end(fr, t)
    return fr


def render_frame(fi):
    t = fi / FPS
    fr = scene(t)
    k = 1 - c01((t - T_REV) / 0.45)
    shake = k if t >= T_REV else (1 - c01(abs(t - T_PANIC) / 0.3) if t >= T_PANIC else 0)
    if shake > 0:
        z = 1 + 0.05 * shake
        im = fr.resize((int(W * z), int(H * z)), Image.BILINEAR)
        dx = int(math.sin(t * 80) * 18 * shake)
        l, tp = (im.width - W) // 2 + dx, (im.height - H) // 2
        fr = im.crop((l, tp, l + W, tp + H))
    if t >= T_REV and t - T_REV < 0.3:
        fr.alpha_composite(Image.new("RGBA", (W, H), (255, 235, 180, int(130 * (1 - (t - T_REV) / 0.3)))))
    lp = (t - (TOTAL - LOOP)) / LOOP
    if lp > 0:
        fr = Image.blend(fr.convert("RGBA"), scene(0.0), ease_io(lp))
    return fr.convert("RGB").tobytes()


# ------------------------------------------------------------------ sound
SR = 48000


def make_audio(path):
    n = int(TOTAL * SR)
    mix = np.zeros(n)
    rng = np.random.default_rng(2)

    def add(sig, t0, g):
        i = int(max(0, t0) * SR)
        sig = sig[:max(0, n - i)]
        mix[i:i + len(sig)] += sig * g

    def beep(dur):
        m = int(dur * SR)
        tt = np.arange(m) / SR
        sq = np.sign(np.sin(2 * np.pi * 2000 * tt)) * (np.sin(2 * np.pi * 8 * tt) > 0)
        return sq * 0.25

    beat = 60 / 96
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [261.63, 329.63, 392.0], [196.0, 246.94, 293.66]]
    t, i = 0.0, 0
    while t < T_REV:
        ch = chords[(i // 4) % 4]
        add(piano(ch[i % 3] * 2, 1.2), t, 0.25)
        if i % 4 == 0:
            add(piano(ch[0] / 2, 2.5), t, 0.4)
        if t > T_RUN0:
            kn = int(0.3 * SR)
            kt = np.arange(kn) / SR
            add(np.sin(2 * np.pi * (45 + 90 * np.exp(-kt * 25)) * kt) * env(kn, 0.001, 0.12), t, 0.6)
            hn = int(0.04 * SR)
            add(np.diff(rng.standard_normal(hn + 1)) * env(hn, 0.0005, 0.01), t + beat / 2, 0.25)
        t += beat
        i += 1
    add(beep(T_SNOOZE - T_RING), T_RING, 0.6)
    for s in SNOOZE:
        add(beep(0.35), s, 0.35)
    tt = T_RUN0
    while tt < T_RUN1:
        add(tick(), tt, 0.3)
        tt += 0.12
    add(beep(T_PANIC + 0.3 - (T_RUN1 - 0.1)), T_RUN1 - 0.1, 0.6)
    add(boom(), T_PANIC, 0.5)
    add(boom(), T_REV, 1.0)
    for f in (130.81, 261.63, 329.63, 392.0, 523.25):
        add(piano(f, 4.0), T_REV, 0.35)
    for j in range(8):
        add(clink(), T_REV + 0.4 + j * 0.05, 0.2)
    for f in (174.61, 261.63, 349.23, 440.0):
        add(piano(f, 3.0), T_END + 0.35, 0.3)
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.9
    mix *= np.minimum(1, (n - np.arange(n)) / SR / 0.4)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32000).astype(np.int16).tobytes())


def main():
    init()
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        (BUILD / "stills").mkdir(exist_ok=True)
        for x in sys.argv[2:]:
            Image.frombytes("RGB", (W, H), render_frame(int(float(x) * FPS))).save(BUILD / "stills" / f"t{float(x):05.1f}.png")
        return
    aud = BUILD / "audio.wav"
    make_audio(aud)
    out = ROOT / "morgenstund-video.mp4"
    nf = int(TOTAL * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(aud), "-af", "loudnorm=I=-14:TP=-1.5", "-c:v", "libx264", "-preset", "medium",
           "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", "-t", f"{TOTAL:.3f}", str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=init) as pool:
        for buf in pool.imap(render_frame, range(nf), chunksize=4):
            ff.stdin.write(buf)
    ff.stdin.close()
    ff.wait()
    print("done", out)


if __name__ == "__main__":
    main()
