"""Render boss-fight-handy.mp4 – 'BOSS FIGHT #1: Du vs. dein Handy'.

Recognizable series format: arcade fighting game. HP bars, round card,
announcer voice, projectiles + damage numbers, combo counter, K.O. + level up,
'next boss' teaser. Reuses the sticker look, captions and the phone character
from src/handy2 (its timeline globals are swapped for this script's lines).

    python3 tts.py && python3 render.py
    python3 render.py preview 2 10 30
"""
import json
import math
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
from lines import LINES  # noqa: E402

sys.path.insert(0, str(ROOT / "src" / "handy2"))
import render as base  # noqa: E402  (handy2 renderer: stickers, captions, phone character)
from gfx import W, H, FPS, F_HEAD, F_BODY, WHITE, c01, ease_out, ease_back, lerp, font, kid  # noqa: E402

BUILD = ROOT / "build" / "bossfight"
OUT = ROOT / "boss-fight-handy.mp4"
BLACK, PINK, YELLOW = base.BLACK, (255, 60, 170), (255, 225, 40)
GREEN, RED, CYAN = (70, 230, 110), (255, 60, 60), (80, 230, 255)

# ------------------------------------------------------------------ timeline (patched into base)
TIM = json.loads((BUILD / "timings.json").read_text())
GAP = {"hook": 0.25, "crit": 0.3, "special": 0.2, "lose": 0.25, "ko": 0.6, "cta": 1.3}
CLIP, OFF, DUR, _t = [], [], [], 0.0
for (k, _, _), tm in zip(LINES, TIM):
    a = max(0.0, tm["words"][0]["start"] - 0.06)
    b = min(tm["duration"], tm["words"][-1]["end"] + 0.14)
    CLIP.append((a, b))
    OFF.append(_t)
    DUR.append((b - a) + GAP.get(k, 0.14))
    _t += DUR[-1]
TOTAL = _t
NFRAMES = int(math.ceil(TOTAL * FPS))
for name, val in dict(TIM=TIM, LINES=LINES, KEYS=[l[0] for l in LINES], WHO=[l[1] for l in LINES],
                      CLIP=CLIP, OFF=OFF, DUR=DUR, TOTAL=TOTAL, NFRAMES=NFRAMES, BUILD=BUILD).items():
    setattr(base, name, val)
KEYS, WHO = base.KEYS, base.WHO
at, s0 = base.at, base.s0


def T(k, w, occ=0):
    return s0(k) + at(k, w, occ)


# ------------------------------------------------------------------ fight events
# (impact time, target, damage, projectile emoji)
HITS = [
    (T("combo", "Push"), "you", 12, "🔔"),
    (T("combo", "Reel"), "you", 14, "📱"),
    (T("combo", "Reel", 1), "you", 16, "📱"),
    (T("crit", "Drei"), "you", 24, "🌙"),
    (T("crit", "Zwei"), "you", 22, "🪫"),
    (T("attacks", "Schublade"), "boss", 25, "🗄️"),
    (T("attacks", "Training"), "boss", 25, "💪"),
    (T("attacks", "Lernen"), "boss", 25, "📚"),
    (T("attacks", "bauen"), "boss", 25, "🧱"),
]
HEAL_T = T("special", "Spezialattacke")
KO_T = s0("ko")
YOU = (290, 1720)          # feet
BOSS = (800, 1380)         # body centre
FLY = 0.38


def hp(who, t):
    v = 100.0
    for ti, tg, d, _ in HITS:
        if tg == who:
            v -= d * ease_out((t - ti) / 0.35)
    if who == "you":
        v += 50 * ease_out((t - HEAL_T) / 0.8)
    return max(0.0, min(100.0, v))


def last_hit(t, who):
    best = None
    for ti, tg, d, e in HITS:
        if tg == who and ti <= t:
            best = (ti, d)
    return best


# ------------------------------------------------------------------ static arena
@lru_cache(maxsize=1)
def arena():
    im = Image.new("RGB", (W, H))
    g = np.linspace(0, 1, H)[:, None, None]
    top, bot = np.array([46, 10, 90.]), np.array([8, 4, 24.])
    im = Image.fromarray(np.repeat((top * (1 - g) + bot * g).astype(np.uint8), W, axis=1))
    d = ImageDraw.Draw(im, "RGBA")
    hz = 1250
    for k in range(-12, 13):                             # neon perspective floor
        d.line([(W / 2 + k * 30, hz), (W / 2 + k * 260, H)], fill=(255, 60, 170, 120), width=3)
    y, step = hz, 14
    while y < H:
        d.line([(0, y), (W, y)], fill=(255, 60, 170, 110), width=3)
        step *= 1.32
        y += step
    for cx in (140, W - 140):                            # spotlights
        d.polygon([(cx, 0), (cx - 260, hz + 300), (cx + 260, hz + 300)], fill=(255, 255, 255, 14))
    for i in range(80):
        r = np.random.default_rng(i)
        x, yy = r.uniform(0, W), r.uniform(280, hz - 40)
        d.ellipse([x - 2, yy - 2, x + 2, yy + 2], fill=(255, 255, 255, 120))
    return im


# ------------------------------------------------------------------ text fx
@lru_cache(maxsize=64)
def fx_text(s, size, col, rot=-6):
    f = font(F_HEAD, size)
    l, t, r, b = f.getbbox(s, stroke_width=16)
    im = Image.new("RGBA", (r - l + 60, b - t + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((30 - l + 14, 30 - t + 14), s, font=f, fill=BLACK, stroke_width=16, stroke_fill=BLACK)
    d.text((30 - l, 30 - t), s, font=f, fill=col, stroke_width=16, stroke_fill=BLACK)
    return im.rotate(rot, resample=Image.BICUBIC, expand=True)


def put_fx(frame, s, x, y, size, col, p, rot=-6):
    if p <= 0.02:
        return
    im = fx_text(s, size, col, rot)
    k = min(p, (W - 20) / im.width)
    im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.BILINEAR)
    frame.alpha_composite(im, (int(x - im.width / 2), int(y - im.height / 2)))


# ------------------------------------------------------------------ HUD
def hud(frame, t):
    d = ImageDraw.Draw(frame)
    for who, x0, x1, name, col in (("you", 50, 470, "DU", GREEN), ("boss", 610, 1030, "HANDY · BOSS", RED)):
        v = hp(who, t) / 100
        d.rectangle([x0 + 8, 168, x1 + 8, 226], fill=BLACK)
        d.rectangle([x0, 160, x1, 218], fill=(60, 20, 30), outline=BLACK, width=6)
        low = who == "you" and v < 0.3 and (t * 4) % 1 < 0.5
        fill = YELLOW if low else col
        w = (x1 - x0 - 12) * v
        if who == "you":
            d.rectangle([x0 + 6, 166, x0 + 6 + w, 212], fill=fill)
        else:
            d.rectangle([x1 - 6 - w, 166, x1 - 6, 212], fill=fill)
        f = font(F_HEAD, 34)
        d.text((x0 if who == "you" else x1, 140), name, font=f, fill=WHITE, anchor="ls" if who == "you" else "rs",
               stroke_width=6, stroke_fill=BLACK)
        if low:
            d.text((x0 + 10, 250), "LOW HP!", font=font(F_HEAD, 30), fill=YELLOW, anchor="lm",
                   stroke_width=6, stroke_fill=BLACK)
    d.ellipse([480, 130, 600, 250], fill=YELLOW, outline=BLACK, width=7)
    d.text((540, 192), "VS", font=font(F_HEAD, 44), fill=BLACK, anchor="mm")


# ------------------------------------------------------------------ fighters
def draw_fighters(c, t, post):
    hy = hp("you", t)
    special = t >= HEAL_T
    ko = t >= KO_T
    # you
    lh = last_hit(t, "you")
    recoil = 30 * max(0, 1 - (t - lh[0]) / 0.3) if lh else 0
    if special and not ko:
        r = 210 + 25 * math.sin(t * 12)
        c.circle(YOU[0], YOU[1] - 260, r, (255, 225, 40, 255))
        c.circle(YOU[0], YOU[1] - 260, r - 40, (255, 160, 40, 255))
    attacking = any(0 <= t - (ti - FLY) < FLY + 0.15 for ti, tg, _, _ in HITS if tg == "boss")
    if ko:
        j = abs(math.sin(t * 6)) * 80
        kid(c, YOU[0], YOU[1], s=1.0, la=170, ra=-170, mood="happy", legs="jump" if j > 10 else "stand", bob=j)
    elif attacking:
        kid(c, YOU[0] + 20, YOU[1], s=1.0, la=40, ra=-95, rel=0, mood="determined")
    else:
        mood = "tired" if hy < 35 and not special else ("determined" if special else "neutral")
        kid(c, YOU[0] - recoil, YOU[1], s=1.0, la=60, ra=-60, lel=-90, rel=90, mood=mood,
            bob=4 * math.sin(t * 5))
    # boss
    bh = hp("boss", t)
    lb = last_hit(t, "boss")
    brecoil = 40 * max(0, 1 - (t - lb[0]) / 0.3) if lb else 0
    if ko:
        fall = ease_out((t - KO_T) / 0.7)
        base.handy(c, BOSS[0] + 60 * fall, BOSS[1] + 380 * fall, s=0.8 * (1 - 0.5 * fall), mood="sad", t=t,
                   la=170, ra=-170, tear=1.0, legs=fall < 0.5)
    else:
        mood = "panic" if bh < 60 else ("sly" if t < s0("special") else "happy")
        laugh = 8 * math.sin(t * 20) if KEYS[base.scene_at(t)] in ("boss", "giveup") else 0
        base.handy(c, BOSS[0] + brecoil, BOSS[1] + laugh, s=0.8, mood=mood, t=t, la=50, ra=-50,
                   lel=-70, rel=70, shake=1.0 if bh < 30 else 0)
        if KEYS[base.scene_at(t)] == "boss":
            for k in range(5):
                a = t * 2 + k * 1.26
                post.append(lambda fr, a=a: base.put_emoji(fr, "🔔", BOSS[0] + 260 * math.cos(a),
                                                            BOSS[1] - 60 + 300 * math.sin(a), 80))
    # projectiles + impacts
    for ti, tg, dmg, e in HITS:
        q = (t - (ti - FLY)) / FLY
        sx, sy = (BOSS[0] - 120, BOSS[1]) if tg == "you" else (YOU[0] + 100, YOU[1] - 330)
        ex, ey = (YOU[0], YOU[1] - 330) if tg == "you" else (BOSS[0], BOSS[1] - 40)
        if 0 <= q < 1:
            x, y = lerp(sx, ex, q), lerp(sy, ey, q) - 160 * math.sin(math.pi * q)
            post.append(lambda fr, x=x, y=y, e=e, q=q: base.put_emoji(fr, e, x, y, 130, rot=q * 360))
        dt = t - ti
        if 0 <= dt < 0.9:
            post.append(lambda fr, ex=ex, ey=ey, dt=dt: base.put_emoji(fr, "💥", ex, ey, 220 * ease_back(dt / 0.15) * (1 - c01((dt - 0.3) / 0.3))))
            post.append(lambda fr, ex=ex, ey=ey, dt=dt, dmg=dmg: put_fx(fr, f"-{dmg}", ex + 120, ey - 120 - 160 * dt, 90,
                                                                         RED if tg == "you" else YELLOW, ease_back(dt / 0.2)))


# ------------------------------------------------------------------ overlays per moment
def moments(frame, t):
    k = KEYS[base.scene_at(t)]
    if k == "hook":
        if t < T("hook", "Runde") - 0.05:
            put_fx(frame, "BOSS #1", W / 2, 800, 150, PINK, ease_back(t / 0.3))
            put_fx(frame, "DEIN HANDY", W / 2, 960, 90, WHITE, ease_back((t - 0.3) / 0.3), rot=4)
        elif t < T("hook", "Kämpft"):
            put_fx(frame, "RUNDE 1", W / 2, 860, 160, YELLOW, ease_back((t - T("hook", "Runde")) / 0.3))
        else:
            put_fx(frame, "KÄMPFT!", W / 2, 860, 170, RED, ease_back((t - T("hook", "Kämpft")) / 0.25))
    n = sum(1 for ti, tg, _, _ in HITS if tg == "you" and ti <= t < s0("giveup"))
    if n >= 2:
        put_fx(frame, f"{n}x COMBO", 300, 960, 80, CYAN, ease_back((t - [h[0] for h in HITS][n - 1]) / 0.2), rot=-10)
    if k == "crit" and t > T("crit", "Drei"):
        put_fx(frame, "KRITISCH!", W / 2, 700, 110, RED, ease_back((t - T("crit", "Drei")) / 0.25))
    if k == "special":
        put_fx(frame, "SPEZIAL-", W / 2, 690, 110, YELLOW, ease_back((t - HEAL_T) / 0.3), rot=-4)
        put_fx(frame, "ATTACKE", W / 2, 820, 120, YELLOW, ease_back((t - HEAL_T - 0.1) / 0.3), rot=-4)
    nb = sum(1 for ti, tg, _, _ in HITS if tg == "boss" and ti <= t < KO_T)
    if nb >= 2:
        put_fx(frame, f"{nb}x COMBO", 780, 760, 90, YELLOW, ease_back((t - [h[0] for h in HITS if h[1] == 'boss'][nb - 1]) / 0.2), rot=8)
    if k == "ko":
        p = ease_back((t - KO_T) / 0.3, 2.5)
        put_fx(frame, "K.O.", W / 2, 800, 300, RED, p, rot=-8)
        if t > T("ko", "Level"):
            put_fx(frame, "LEVEL UP!", W / 2, 1040, 110, GREEN, ease_back((t - T("ko", "Level")) / 0.3), rot=5)
            put_fx(frame, "+1 DISZIPLIN", W / 2, 1160, 60, WHITE, ease_back((t - T("ko", "Level") - 0.15) / 0.3), rot=5)
    if k == "cta":
        lt = t - s0("cta")
        d = ImageDraw.Draw(frame)
        p = ease_back(lt / 0.35)
        if p > 0.05:
            put_fx(frame, "NÄCHSTER BOSS:", W / 2, 690, 80, WHITE, p, rot=0)
            put_fx(frame, "???", W / 2, 900, 260, PINK, ease_back((lt - 0.25) / 0.35), rot=0)
        if t > T("cta", "Folg"):
            q = ease_back((t - T("cta", "Folg")) / 0.3)
            y = 1130
            d.rounded_rectangle([W / 2 - 300 * q + 10, y - 75 * q + 10, W / 2 + 300 * q + 10, y + 75 * q + 10], 75, fill=BLACK)
            d.rounded_rectangle([W / 2 - 300 * q, y - 75 * q, W / 2 + 300 * q, y + 75 * q], 75, fill=PINK,
                                outline=BLACK, width=7)
            if q > 0.4:
                d.text((W / 2, y), "+ FOLGEN", font=font(F_HEAD, int(64 * q)), fill=WHITE, anchor="mm")


# ------------------------------------------------------------------ frame
def render_frame(n):
    t = n / FPS
    i = base.scene_at(t)
    frame = arena().copy().convert("RGBA")
    im, c = base.new_layer()
    post = []
    draw_fighters(c, t, post)
    base.sticker(frame, base.finish(im))
    for fn in post:
        fn(frame)
    moments(frame, t)
    hud(frame, t)
    if WHO[i] == "phone":
        base.draw_bubble(frame, i, t)
    else:
        base.draw_slam(frame, i, t, y=430)
    # screen shake on impacts / KO
    shake = 0.0
    for ti, _, _, _ in HITS + [(KO_T, 0, 0, 0)]:
        if 0 <= t - ti < 0.3:
            shake = max(shake, 1 - (t - ti) / 0.3)
    if shake:
        dx, dy = int(math.sin(t * 95) * 26 * shake), int(math.cos(t * 80) * 26 * shake)
        frame = frame.transform((W, H), Image.AFFINE, (1, 0, dx, 0, 1, dy), fillcolor=BLACK)
        if shake > 0.8:
            frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 90)))
    d = ImageDraw.Draw(frame)
    d.rectangle([0, H - 14, int(W * t / TOTAL), H], fill=PINK)
    if t > TOTAL - 0.4:
        frame.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(255 * c01((t - TOTAL + 0.4) / 0.4)))))
    return frame.convert("RGB").tobytes()


# ------------------------------------------------------------------ audio: chiptune + hit sfx
SR = base.SR


def make_music(n):
    tt = np.arange(n) / SR
    out = np.zeros(n)
    beat = 60 / 150
    step = beat / 4
    rng = np.random.default_rng(3)
    prog = [[220.0, 261.6, 329.6], [174.6, 220.0, 261.6], [196.0, 246.9, 293.7], [164.8, 207.7, 246.9]]
    L = int(step * SR)
    lt = np.arange(L) / SR
    sq = lambda f, a, dec: a * np.sign(np.sin(2 * np.pi * f * lt)) * np.exp(-lt * dec)
    kl = int(0.25 * SR)
    kt = np.arange(kl) / SR
    kick = np.sin(2 * np.pi * (50 + 130 * np.exp(-kt * 40)) * kt) * np.exp(-kt * 12)
    k = 0
    while k * step < TOTAL:
        i = int(k * step * SR)
        ch = prog[(k // 32) % 4]
        def add(sig, i=i):
            m = min(len(sig), n - i)
            if m > 0:
                out[i:i + m] += sig[:m]
        add(sq(ch[k % 3] * 2, 0.05, 14))                      # arpeggio
        if k % 2 == 0:
            add(sq(ch[0] / 2, 0.06, 4))                       # bass
        if k % 4 == 0:
            add(0.5 * kick)
        if k % 8 == 4:
            add(0.25 * rng.standard_normal(L) * np.exp(-lt * 40))
        k += 1
    # hits: thump + crunch; KO: big boom; music cuts out briefly at KO
    for ti, _, _, _ in HITS:
        i = int(ti * SR)
        hl = int(0.3 * SR)
        ht = np.arange(hl) / SR
        hit = np.sin(2 * np.pi * (70 + 200 * np.exp(-ht * 30)) * ht) * np.exp(-ht * 10) \
            + 0.5 * rng.standard_normal(hl) * np.exp(-ht * 30)
        out[i:i + hl] += 0.8 * hit[:max(0, min(hl, n - i))]
    a, b = int(KO_T * SR), int((KO_T + 1.2) * SR)
    env = np.ones(n)
    env[a:b] = 0.15
    out *= np.convolve(env, np.ones(600) / 600, mode="same")
    bl = int(1.4 * SR)
    bt = np.arange(bl) / SR
    boom = np.sin(2 * np.pi * (38 + 100 * np.exp(-bt * 10)) * bt) * np.exp(-bt * 2.5) + 0.5 * rng.standard_normal(bl) * np.exp(-bt * 15)
    out[a:a + bl] += 1.3 * boom[:max(0, min(bl, n - a))]
    out[:bl] += 1.0 * boom[:min(bl, n)]
    out *= np.clip((TOTAL - tt) / 0.8, 0, 1)
    return out / max(1e-6, np.abs(out).max())


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        d = BUILD / "stills"
        d.mkdir(exist_ok=True)
        for a in sys.argv[2:]:
            Image.frombytes("RGB", (W, H), render_frame(int(float(a) * FPS))).save(d / f"t{float(a):05.1f}.png")
        print("stills ->", d)
        return
    if len(sys.argv) > 1 and sys.argv[1] == "times":
        for k, o in zip(KEYS, OFF):
            print(f"{k:8s} {o:6.2f}")
        print("total", round(TOTAL, 2))
        return
    voice = base.make_voice()
    base.write_wav(BUILD / "voice.wav", voice / max(1e-6, np.abs(voice).max()) * 0.95)
    base.write_wav(BUILD / "music.wav", make_music(len(voice)) * 0.9)
    ff = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(BUILD / "voice.wav"), "-i", str(BUILD / "music.wav"),
        "-filter_complex",
        "[1:a]asplit=2[v][vs];[2:a]volume=0.32[m];"
        "[m][vs]sidechaincompress=threshold=0.04:ratio=5:attack=15:release=250[md];"
        "[v][md]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]",
        "-map", "0:v", "-map", "[a]", "-t", f"{TOTAL:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(OUT)], stdin=subprocess.PIPE)
    with Pool() as pool:
        for k, fr in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=6)):
            ff.stdin.write(fr)
    ff.stdin.close()
    ff.wait()
    print("->", OUT)


if __name__ == "__main__":
    main()
