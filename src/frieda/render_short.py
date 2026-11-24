"""Kurzfassung (~32 s) von "Frieda an der Kasse" – für maximale Watchtime auf TikTok.

Aufbau:
  0–2,3 s   Cold Open: Wurf in Zeitlupe, Freeze am höchsten Punkt + Hook-Text, dann Rückspulen
  2,3–14 s  Typ drängelt sich vor – "Ich auch." – kurzer Showdown ("Sonst was … Oma?" – "Sonst … das hier.")
  14–19 s   Wurf, IPPON, Wertungstafeln (9,5)
  19–27 s   Gurke + Dose aufs Band – "Den zahlt er … hinten." – "Mit Karte oder bar?" – "Mit Stil." + Zwinkern
  27–32 s   "Bro … die Oma ist Endgegner." – "Frieda?! Bro … lauf!" + "Das ist Frieda." – harter Schnitt

Nutzt alle Figuren/Sets aus render.py und überschreibt nur die Zeitleiste.
python3 tts.py && python3 render_short.py            -> ../../frieda-supermarkt-kurz.mp4
python3 render_short.py preview 0.2 1 2.1 4 9 15 18 23 29 31.5
"""
import math
import os
import subprocess
import sys
import wave
from functools import lru_cache
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw

import render as R
from core import F_BLACK, W, H, FPS, emoji, glitch, paste_c, text_img

OUT = R.ROOT / "frieda-supermarkt-kurz.mp4"
S0 = 2.3              # Ende Cold Open – hier beginnt die Geschichte
FREEZE = 0.35         # Freeze-Frame ab hier
REW0 = 1.85           # Rückspulen
END_TXT = 30.9

OFF = 999.0           # Zeilen/Szenen, die in der Kurzfassung fehlen
R.T_LINE.update({
    "kas0": OFF, "fr0": OFF, "typ0": OFF, "k2a": OFF,
    "typ1": 3.3, "fr1": 5.75, "typ2": OFF, "fr4": 6.6, "typ5": 10.2, "fr5": 12.75,
    "mk1": OFF, "k3a": OFF, "typ3": OFF, "kas2": OFF, "fr3": OFF, "kas3": OFF,
    "kas4": 19.9, "fr6": 21.65, "kas1": 23.2,
    "fr2": 25.0, "typ4": 26.8, "tel": 29.1,
})
R.T_K0_LEAVE = -10.0
R.T_GUY_IN0, R.T_GUY_IN1 = 2.3, 3.2
R.T_PUSH = 5.1
R.T_CONF_A, R.T_CONF_B = 5.6, 13.95
R.T_GRAB, R.T_THROW, R.T_FLY, R.T_LAND, R.T_SLOW_END = 13.95, 14.6, 15.1, 17.0, 17.4
R.T_IPPON = 17.1
R.T_CARDS, R.T_CARDS_END = 17.35, 19.25
R.T_CLAP0, R.T_CLAP1 = 17.4, 19.25
R.T_MUSK0, R.T_MUSK1 = OFF, OFF + 1
R.T_CATCH = R.T_LAND + 0.3
R.T_BACK1A, R.T_BACK1B = OFF, OFF + 1
R.T_FLASH_A, R.T_FLASH_B = OFF, OFF + 1
R.T_CUKE, R.T_BEEP = 19.3, 19.7
R.T_CLOSE2A = R.T_CLOSE = 24.75
R.T_WINK = 26.05
R.T_BACK2A, R.T_BACK2B = 26.6, 32.0
R.T_END_TXT = OFF
R.T_TITLE_END = 0.0
R.TOTAL = 32.0
R.NF = int(R.TOTAL * FPS)
R.CAM_KEYS[:] = [
    (0.0, 1.12, 560, 1330), (S0, 1.12, 560, 1330), (3.3, 1.16, 470, 1360), (5.0, 1.25, 450, 1320),
    (5.6, 1.35, 450, 1280),
    (R.T_CONF_B, 1.32, 400, 1260), (R.T_CONF_B + 1.35, 1.0, 560, 1100), (R.T_CARDS_END, 1.0, 560, 1100),
    (R.T_CUKE + 0.6, 1.22, 380, 1400), (R.T_CLOSE, 1.3, 360, 1380),
]
L = R.T_LINE
R.CONF_SHOTS[:] = [
    (R.T_CONF_A, L["fr4"] - 0.15, "frieda", "fr1"),
    (L["fr4"] - 0.15, L["typ5"] - 0.25, "frieda", "fr4"),
    (L["typ5"] - 0.25, L["fr5"] - 0.2, "typ", "typ5"),
    (L["fr5"] - 0.2, R.T_CONF_B, "frieda", "fr5"),
]
T_PEAK = R.T_FLY + 0.55 * (R.T_LAND - R.T_FLY)


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
def peak_frame():
    return R.world_shot(T_PEAK)


def cold_open(t):
    if t < FREEZE:  # die letzten Momente vor dem Freeze laufen noch in Zeitlupe
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
    else:  # Rückspulen bis zum Anfang der Geschichte
        p = R.seg(t, REW0, S0)
        src = R.lerp(T_PEAK, S0 + 0.05, R.ease_in(p))
        frame = R.world_shot(src)
        frame = glitch(frame, t, 1.4)
        d = ImageDraw.Draw(frame)
        for k in range(7):
            y = (k * 290 + int(t * 4000)) % H
            d.rectangle([0, y, W, y + 10], fill=(255, 255, 255, 60))
        paste_c(frame, emoji("⏪", 150), 170, 330)
        paste_c(frame, rewind_text(), 600, 330)
    return frame


@lru_cache(maxsize=1)
def rewind_text():
    return text_img("20 Sekunden vorher", 66, (255, 255, 255), F_BLACK, stroke=10, stroke_fill=(30, 26, 40))


@lru_cache(maxsize=1)
def end_text():
    return R.end_text()


def render_frame(fi):
    t = fi / FPS
    if t < S0:
        return cold_open(t)
    frame = R.render_frame(fi)
    if t < S0 + 0.12:
        R.flash(frame, t, S0, 0.12)
    if t >= END_TXT:
        q = R.ease_back(R.seg(t, END_TXT, END_TXT + 0.3))
        paste_c(frame, end_text(), 540, 1430, scale=max(0.05, q))
    return frame


def _rgb(fi):
    return np.asarray(render_frame(fi).convert("RGB")).tobytes()


def build_audio(path):
    R.build_audio(path)
    with wave.open(str(path)) as wf:
        x = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).astype(np.float64) / 32768
    n = len(x)
    SR = R.SR
    tt = np.arange(n) / SR
    rng = np.random.default_rng(9)
    # Cold Open: Atmo/Musik leiser, eigene Effekte
    x *= np.where(tt < S0, 0.35, 1.0)

    def add(sig, t0, g=1.0):
        i = int(t0 * SR)
        j = min(n, i + len(sig))
        x[i:j] += sig[: j - i] * g
    whoosh = R.lp_fast(rng.standard_normal(int(0.6 * SR)), 25) * np.sin(np.linspace(0, np.pi, int(0.6 * SR)))
    add(whoosh * 2.5, 0.0, 0.8)                                               # Zeitlupen-Schwung
    sc = rng.standard_normal(int(0.25 * SR)) * np.exp(-np.arange(int(0.25 * SR)) / 2500)
    add(R.ssum(sc * 0.6, R.tone(900, 0.25, 0.002, 0.08, f_end=200)), FREEZE, 0.6)  # Plattenkratzer + Freeze
    add(R.tone(55, 1.4, 0.004, 0.9), FREEZE, 0.6)                              # tiefer Schlag
    L2 = int((S0 - REW0) * SR)
    rew = R.tone(200, S0 - REW0, 0.01, 5, f_end=1800) * 0.4 + R.lp_fast(rng.standard_normal(L2), 4)[:L2] * 0.4
    add(rew, REW0, 0.6)                                                        # Rückspul-Geräusch
    add(R.ssum(R.tone(523, 0.5, 0.003, 0.3), R.tone(659, 0.5, 0.003, 0.3), R.tone(784, 0.6, 0.003, 0.35)),
        END_TXT, 0.14)
    fade = np.clip((R.TOTAL - tt) / 0.08, 0, 1)                                # harter Schnitt
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
