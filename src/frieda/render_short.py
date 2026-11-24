"""TikTok-Fassung (45 s) von "Frieda an der Kasse" – mit Livestream-, Aura- und Gen-Z-Gags.

Aufbau:
  0–2,3 s   Cold Open: Wurf in Zeitlupe, Freeze am höchsten Punkt + Hook-Text, Rückspulen
  2,3–9 s   Typ kommt live streamend rein ("Chat, guckt mal – ich skip die ganze Schlange.") und drängelt sich vor:
            "Ihr seid aber zu viele. Ich zahl schnell – ich hab keine Zeit!"
  9–27 s    Gespräch mit Frieda ("… ich bin achtzig …" – "Was willst du machen – noch mehr Achtzigjährige holen?
            Ha ha ha!") bis "Sonst … das hier."
  26–32 s   Wurf, IPPON, +1000 AURA / −1000 AURA, Chat eskaliert (Zuschauer 1,9k -> 48,9k), Wertungstafeln
  32–38 s   Frieda: "Skill issue." – Energy-Drink-Callback – "Mit Karte oder bar?"
  38–45 s   "Mit Stil." + Zwinkern – Typ hinten: "Chat … ich wurde grad von 'ner Oma gefaltet." – Chat: "Frieda?! Bro … lauf! 💀"
            – "Das ist Frieda." – harter Schnitt

Nutzt alle Figuren/Sets aus render.py und überschreibt nur Zeitleiste + Overlays.
python3 tts.py && python3 render_short.py            -> ../../frieda-supermarkt-kurz.mp4
python3 render_short.py preview 1 4 12 29.5 32 43.5
"""
import os
import subprocess
import sys
import wave
from functools import lru_cache
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw

import render as R
from core import F_BLACK, F_INTER, F_INTER_B, W, H, FPS, emoji, font, glitch, paste_c, text_img

OUT = R.ROOT / "frieda-supermarkt-kurz.mp4"
S0 = 2.3              # Ende Cold Open – hier beginnt die Geschichte
FREEZE = 0.35         # Freeze-Frame ab hier
REW0 = 1.85           # Rückspulen
END_TXT = 43.75
T_AURA = 29.95
T_BOOM = 31.95        # Vine-Boom auf "Skill issue."

OFF = 999.0           # Zeilen/Szenen, die in dieser Fassung fehlen
R.GUY_LIVE = True
R.T_LINE.update({k: OFF for k in R.LINES})
R.T_LINE.update({
    "typL": 2.5, "typ1c": 5.0,
    "fr1b": 9.25, "fr7": 10.95, "typ8": 15.5, "fr4": 19.55, "typ5": 23.1, "fr5": 25.6,
    "frS": 31.95, "kas4": 33.45, "fr6": 35.2, "kas1": 36.7,
    "fr2": 38.45, "typ7": 40.25,
})
R.T_K0_LEAVE = -10.0
R.T_GUY_IN0, R.T_GUY_IN1 = 2.3, 4.6
R.T_PUSH = 8.6
R.T_CONF_A, R.T_CONF_B = 9.1, 26.75
R.T_GRAB, R.T_THROW, R.T_FLY, R.T_LAND, R.T_SLOW_END = 26.75, 27.3, 27.65, 29.25, 29.6
R.T_IPPON = 29.35
R.T_IPPON_END = 30.1
R.T_CARDS, R.T_CARDS_END = 30.85, 31.95
R.T_CLAP0, R.T_CLAP1 = 29.6, 31.95
R.T_MUSK0, R.T_MUSK1 = OFF, OFF + 1
R.T_CATCH = R.T_LAND + 0.3
R.T_BACK1A, R.T_BACK1B = OFF, OFF + 1
R.T_FLASH_A, R.T_FLASH_B = OFF, OFF + 1
R.T_CUKE, R.T_BEEP = 32.95, 33.3
R.T_CLOSE2A = R.T_CLOSE = 38.25
R.T_WINK = 39.5
R.T_BACK2A, R.T_BACK2B = 40.05, 45.0
R.T_END_TXT = OFF
R.T_TITLE_END = 0.0
R.TOTAL = 45.0
R.NF = int(R.TOTAL * FPS)
R.CAM_KEYS[:] = [
    (0.0, 1.12, 560, 1330), (S0, 1.12, 640, 1330), (4.6, 1.16, 470, 1360), (8.0, 1.25, 450, 1320),
    (R.T_CONF_A, 1.35, 450, 1280),
    (R.T_CONF_B, 1.32, 400, 1260), (R.T_CONF_B + 1.2, 1.0, 560, 1100), (R.T_CARDS_END, 1.0, 560, 1100),
    (R.T_LINE["frS"] + 0.9, 1.22, 520, 1250), (R.T_CUKE + 0.6, 1.22, 380, 1400), (R.T_CLOSE, 1.3, 360, 1380),
]
L = R.T_LINE
R.CONF_SHOTS[:] = [
    (R.T_CONF_A, L["fr7"] - 0.15, "frieda", "fr1b"),
    (L["fr7"] - 0.15, L["typ8"] - 0.2, "frieda", "fr7"),
    (L["typ8"] - 0.2, L["fr4"] - 0.15, "typ", "typ8"),
    (L["fr4"] - 0.15, L["typ5"] - 0.25, "frieda", "fr4"),
    (L["typ5"] - 0.25, L["fr5"] - 0.2, "typ", "typ5"),
    (L["fr5"] - 0.2, R.T_CONF_B, "frieda", "fr5"),
]
T_PEAK = R.T_FLY + 0.55 * (R.T_LAND - R.T_FLY)

# ------------------------------------------------------------------ Livestream-Overlay
CHAT = [  # (Zeit, Name, Farbe, Text)
    (2.9, "lena.k", (255, 120, 160), "wo bist du?? 😂"),
    (3.6, "max_99", (90, 170, 255), "skip die schlange bro"),
    (4.5, "jule", (120, 220, 120), "der traut sich was 💀"),
    (6.9, "tom.b", (255, 190, 60), "\"ihr seid zu viele\" 💀💀"),
    (8.0, "nina", (190, 130, 255), "Oma vs. Bro 👀"),
    (26.95, "maxi", (90, 220, 210), "WAS"),
    (29.4, "lena.k", (255, 120, 160), "💀💀💀"),
    (29.6, "tom.b", (255, 190, 60), "OMA GOAT 🐐"),
    (29.85, "jule", (120, 220, 120), "IPPON 🥋🥋"),
    (30.1, "nina", (190, 130, 255), "W Oma"),
    (30.35, "max_99", (90, 170, 255), "L Bro 😭"),
    (30.75, "kev", (255, 150, 60), "+1000 Aura fr"),
    (32.2, "lena.k", (255, 120, 160), "SKILL ISSUE 💀💀"),
    (43.15, "bro_kevin", (255, 80, 80), "Frieda?! Bro … lauf! 💀"),
    (43.55, "nina", (190, 130, 255), "Legende 🫡"),
]


def viewers(t):
    if t < R.T_IPPON:
        v = 1204 + max(0.0, t - S0) * 28
    else:
        v = 1900 + (48900 - 1900) * R.ease_out(R.seg(t, R.T_IPPON, R.T_IPPON + 1.2)) + max(0.0, t - 31) * 260
    return f"{v / 1000:.1f}k".replace(".", ",")


def shot_kind(t):
    if t < S0:
        return "cold"
    if R.T_CONF_A <= t < R.T_CONF_B:
        return "conf"
    if R.T_BACK2A <= t:
        return "back"
    if t >= R.T_CLOSE:
        return "close"
    return "world"


def is_emoji(c):
    return ord(c) > 0x2100 and c not in "…–−"


def split_emoji(text):
    parts, cur = [], ""
    for c in text:
        if c == "️":
            continue
        if is_emoji(c):
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(c)
        else:
            cur += c
    if cur:
        parts.append(cur)
    return parts


@lru_cache(maxsize=64)
def chat_line(name, col, text):
    f_n, f_t = font(F_INTER, 40), font(F_INTER_B, 40)
    w = int(f_n.getlength(name) + f_t.getlength(text) + 200)
    im = Image.new("RGBA", (w, 72), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([8, 8, 64, 64], fill=col)
    d.text((36, 36), name[0].upper(), font=font(F_INTER, 32), fill=(255, 255, 255), anchor="mm")
    x = 78
    d.text((x, 36), name, font=f_n, fill=col + (255,), anchor="lm", stroke_width=2, stroke_fill=(0, 0, 0))
    x += f_n.getlength(name) + 14
    for part in split_emoji(text):
        if len(part) == 1 and is_emoji(part):
            e = emoji(part, 44)
            im.alpha_composite(e, (int(x), 36 - e.height // 2))
            x += e.width + 3
        else:
            d.text((x, 36), part, font=f_t, fill=(255, 255, 255), anchor="lm", stroke_width=2, stroke_fill=(0, 0, 0))
            x += f_t.getlength(part)
    bg = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(bg).rounded_rectangle([0, 0, int(x) + 22, 71], radius=36, fill=(0, 0, 0, 120))
    bg.alpha_composite(im)
    return bg.crop((0, 0, min(w, int(x) + 24), 72))


@lru_cache(maxsize=64)
def live_badge(vtxt):
    im = Image.new("RGBA", (340, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, 110, 63], radius=14, fill=(255, 40, 80))
    d.text((55, 32), "LIVE", font=font(F_BLACK, 32), fill=(255, 255, 255), anchor="mm")
    d.rounded_rectangle([120, 0, 330, 63], radius=14, fill=(0, 0, 0, 130))
    e = emoji("👁", 34)
    im.alpha_composite(e, (134, 32 - e.height // 2))
    d.text((180, 32), vtxt, font=font(F_BLACK, 32), fill=(255, 255, 255), anchor="lm")
    return im


def draw_live(frame, t):
    kind = shot_kind(t)
    if kind == "cold":
        if t >= REW0:
            return
        vtxt = viewers(T_AURA + 2)
        msgs = [m for m in CHAT if 29.4 <= m[0] <= 30.75][-4:]
    elif kind in ("world", "back"):
        vtxt = viewers(t)
        msgs = [m for m in CHAT if m[0] <= t and t - m[0] < 5.0][-4:]
    else:
        return
    paste_c(frame, live_badge(vtxt), 200, 250)
    y = 1545
    for k, (t0, name, col, text) in enumerate(reversed(msgs)):
        im = chat_line(name, col, text)
        q = 1.0 if kind == "cold" else R.ease_out(R.seg(t, t0, t0 + 0.2))
        a = 1.0 if kind == "cold" else 1 - R.seg(t, t0 + 4.4, t0 + 5.0)
        paste_c(frame, im, 36 + im.width / 2 - (1 - q) * 80, y - k * 82, alpha=max(0.0, min(1.0, q)) * a)


@lru_cache(maxsize=4)
def aura_img(txt, col, emo):
    t = text_img(txt, 78, col, F_BLACK, stroke=12, stroke_fill=(30, 26, 40))
    e = emoji(emo, 90)
    im = Image.new("RGBA", (t.width + e.width, max(t.height, e.height)), (0, 0, 0, 0))
    im.alpha_composite(t, (0, (im.height - t.height) // 2))
    im.alpha_composite(e, (t.width - 10, (im.height - e.height) // 2))
    return im


def draw_aura(frame, t):
    for t0, txt, col, emo, x, y in ((T_AURA, "+1000 AURA", (255, 214, 60), "✨", 560, 700),
                                    (T_AURA + 0.4, "−1000 AURA", (255, 70, 90), "💀", 640, 420)):
        if t0 <= t < t0 + 1.5:
            q = R.ease_back(R.seg(t, t0, t0 + 0.25))
            a = 1 - R.seg(t, t0 + 1.15, t0 + 1.5)
            paste_c(frame, aura_img(txt, col, emo), x, y - (t - t0) * 40, scale=max(0.05, q * 0.85), alpha=a)


# ------------------------------------------------------------------ Cold Open
@lru_cache(maxsize=1)
def hook_text():
    t = text_img("Er hat sich vor der falschen Oma vorgedrängelt", 74, (255, 255, 255), F_BLACK, stroke=12,
                 stroke_fill=(30, 26, 40), max_w=900)
    e = emoji("😳", 120)
    im = Image.new("RGBA", (max(t.width, 980), t.height + e.height + 10), (0, 0, 0, 0))
    im.alpha_composite(t, ((im.width - t.width) // 2, 0))
    im.alpha_composite(e, ((im.width - e.width) // 2, t.height - 10))
    return im


@lru_cache(maxsize=1)
def rewind_text():
    return text_img("Kurz vorher …", 70, (255, 255, 255), F_BLACK, stroke=10, stroke_fill=(30, 26, 40))


@lru_cache(maxsize=1)
def peak_frame():
    return R.world_shot(T_PEAK)


def cold_open(t):
    if t < FREEZE:
        frame = R.world_shot(T_PEAK - (FREEZE - t) * 0.6)
    elif t < REW0:
        frame = peak_frame().copy()
        z = 1 + 0.06 * R.ease_out(R.seg(t, FREEZE, REW0))
        frame = R.zoom_frame(frame, z, 540, 960)
        frame = R.grade(frame, 0.6)
        q = R.ease_back(R.seg(t, FREEZE + 0.05, FREEZE + 0.35))
        band = Image.new("RGBA", (W, 520), (20, 16, 30, int(150 * min(1, q))))
        frame.alpha_composite(band, (0, 1080))
        paste_c(frame, hook_text(), 540, 1340, scale=max(0.05, q))
        R.flash(frame, t, FREEZE, 0.1)
    else:
        p = R.seg(t, REW0, S0)
        frame = R.world_shot(R.lerp(T_PEAK, S0 + 0.05, R.ease_in(p)))
        frame = glitch(frame, t, 1.4)
        d = ImageDraw.Draw(frame)
        for k in range(7):
            y = (k * 290 + int(t * 4000)) % H
            d.rectangle([0, y, W, y + 10], fill=(255, 255, 255, 60))
        paste_c(frame, emoji("⏪", 150), 190, 330)
        paste_c(frame, rewind_text(), 580, 330)
    return frame


def render_frame(fi):
    t = fi / FPS
    if t < S0:
        frame = cold_open(t)
        if t < FREEZE + 0.4 or t >= REW0:
            draw_live(frame, t)
        return frame
    frame = R.render_frame(fi)
    if t < S0 + 0.12:
        R.flash(frame, t, S0, 0.12)
    draw_live(frame, t)
    draw_aura(frame, t)
    if t >= END_TXT:
        q = R.ease_back(R.seg(t, END_TXT, END_TXT + 0.3))
        paste_c(frame, R.end_text(), 540, 1260, scale=max(0.05, q))
    return frame


def _rgb(fi):
    return np.asarray(render_frame(fi).convert("RGB")).tobytes()


# ------------------------------------------------------------------ Audio
def build_audio(path):
    R.build_audio(path)
    with wave.open(str(path)) as wf:
        x = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).astype(np.float64) / 32768
    n = len(x)
    SR = R.SR
    tt = np.arange(n) / SR
    rng = np.random.default_rng(9)
    x *= np.where(tt < S0, 0.35, 1.0)

    def add(sig, t0, g=1.0):
        i = int(t0 * SR)
        if i >= n:
            return
        j = min(n, i + len(sig))
        x[i:j] += sig[: j - i] * g
    # Cold Open
    whoosh = R.lp_fast(rng.standard_normal(int(0.6 * SR)), 25) * np.sin(np.linspace(0, np.pi, int(0.6 * SR)))
    add(whoosh * 2.5, 0.0, 0.8)
    sc = rng.standard_normal(int(0.25 * SR)) * np.exp(-np.arange(int(0.25 * SR)) / 2500)
    add(R.ssum(sc * 0.6, R.tone(900, 0.25, 0.002, 0.08, f_end=200)), FREEZE, 0.6)
    add(R.tone(55, 1.4, 0.004, 0.9), FREEZE, 0.6)
    L2 = int((S0 - REW0) * SR)
    rew = R.tone(200, S0 - REW0, 0.01, 5, f_end=1800)[:L2] * 0.4 + R.lp_fast(rng.standard_normal(L2), 4) * 0.4
    add(rew, REW0, 0.6)
    # Chat-"Plopp" je Nachricht
    for t0, *_ in CHAT:
        if t0 > S0:
            add(R.ssum(R.tone(1480, 0.07, 0.001, 0.03), 0.6 * R.tone(1975, 0.06, 0.001, 0.025)), t0, 0.12)
    # Aura: Glitzer-Arpeggio + "Fail"-Posaune
    for k, f in enumerate((1047, 1319, 1568, 2093)):
        add(R.tone(f, 0.25, 0.002, 0.12), T_AURA + k * 0.05, 0.12)
    for k, f in enumerate((392, 370, 349, 311)):
        add(R.tone(f, 0.28 if k < 3 else 0.7, 0.01, 0.4, kind="saw") * 0.12, T_AURA + 0.45 + k * 0.22, 0.6)
    # Vine-Boom auf "Skill issue."
    boom = np.tanh(R.ssum(R.tone(62, 1.2, 0.002, 0.45, f_end=45), 0.5 * R.tone(124, 0.8, 0.002, 0.25)) * 2.5)
    add(boom, T_BOOM + 0.75, 0.7)
    add(R.ssum(R.tone(523, 0.5, 0.003, 0.3), R.tone(659, 0.5, 0.003, 0.3), R.tone(784, 0.6, 0.003, 0.35)),
        END_TXT, 0.14)
    fade = np.clip((R.TOTAL - tt) / 0.08, 0, 1)
    pcm = (np.tanh(x * 1.05) * 0.95 * fade * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        d = R.BUILD / "stills_kurz"
        d.mkdir(parents=True, exist_ok=True)
        for s in sys.argv[2:]:
            render_frame(int(float(s) * FPS)).convert("RGB").save(d / f"f_{float(s):05.2f}.png")
        print(d)
        return
    wav = R.BUILD / "mix_kurz.wav"
    build_audio(wav)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r",
           str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt",
           "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(min(4, os.cpu_count()), maxtasksperchild=40) as pool:
        for i, b in enumerate(pool.imap(_rgb, range(R.NF), chunksize=4)):
            p.stdin.write(b)
            if i % 60 == 0:
                print(f"frame {i}/{R.NF}", flush=True)
    p.stdin.close()
    p.wait()
    print("->", OUT)


if __name__ == "__main__":
    main()
