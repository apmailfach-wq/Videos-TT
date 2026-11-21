"""Rendert 'Oma Frieda Faust – Folge 2: Oma Frieda geht zur Schule' (1080x1920, 30 fps, 35 s) inkl. Musik, Soundeffekten, Untertiteln.

python3 render.py               -> ../../oma-frieda-faust-folge-1.mp4
python3 render.py preview 1 5   -> Standbilder build/omafrieda/stills/
"""
import json
import math
import os
import subprocess
import sys
import wave
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "omafrieda"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from script import TOTAL  # noqa: E402  (vor shots2 importieren, sonst greift script.py aus Folge 1)
import shots3 as S  # noqa: E402
import world3 as W3  # noqa: E402
import world as Wd  # noqa: E402
from gfx import (F_BLACK, F_INTER, FPS, H, ROOT, W, YELLOW, clamp01, ease_back, ease_out, extrude_text, paste_c,
                 rrect, text_img)  # noqa: E402

BUILD = ROOT / "build" / "omafrieda2"
OUT = ROOT / os.environ.get("VIDEO_OUT", "oma-frieda-faust-folge-2.mp4")
TL = json.loads((BUILD / "timeline.json").read_text())
LINES = {l["id"]: l for l in TL["lines"]}
NFRAMES = int(TOTAL * FPS)
SR = 48000
GROUP = {"oma": "oma", "omaflott": "oma", "gamer": "gamer", "girl": "girl", "rowdy": "rowdy", "kleiner": "kleiner",
         "erz": "erz", "bully2": "bully2"}


# ------------------------------------------------------------------ Lippen-Sync
def read_wav(p):
    with wave.open(str(p)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return x


ENV = {}


def load_envs():
    for l in TL["lines"]:
        x = read_wav(l["wav"])
        hop = SR // 100
        n = len(x) // hop
        e = np.sqrt(np.mean(x[:n * hop].reshape(n, hop) ** 2, axis=1))
        e = e / (e.max() + 1e-6)
        ENV[l["id"]] = e


def mouth_fn(who, T):
    for l in TL["lines"]:
        if GROUP[l["speaker"]] != who:
            continue
        dt = T - l["start"]
        if 0 <= dt < l["end"] - l["start"] + 0.1:
            e = ENV[l["id"]]
            i = int(dt * 100)
            if i < len(e):
                v = float(np.mean(e[max(0, i - 2):i + 3]))
                return [0.0, 0.35, 0.7, 1.0][min(3, int(v * 4.2))] if v > 0.12 else 0.0
    return 0.0


# ------------------------------------------------------------------ Untertitel (Wort für Wort)
NO_SUB = {"erz5"}  # erscheinen ohnehin als große Titel


def line_tokens(l):
    """Wörter mit Satzzeichen aus dem Originaltext (für die Anzeige), sonst die TTS-Wörter."""
    toks = [t for t in l["text"].split() if any(ch.isalnum() for ch in t)]
    out, pos = [], 0
    for w in l["words"]:
        n = len(w["text"].split())
        out.append(" ".join(toks[pos:pos + n]))
        pos += n
    if pos == len(toks) and all(out):
        return out
    return [w["text"] for w in l["words"]]


def build_caps():
    """Ganze kurze Sätze als Untertitel; nur sehr lange Sätze werden am Komma geteilt."""
    caps = []
    for l in TL["lines"]:
        if l["id"] in NO_SUB:
            continue
        ws = l["words"]
        toks = line_tokens(l)
        idx = list(range(len(ws)))
        sentences, cur = [], []
        for i in idx:
            cur.append(i)
            if toks[i].endswith(("?", "!", ".")):
                sentences.append(cur)
                cur = []
        if cur:
            sentences.append(cur)
        chunks = []
        for sen in sentences:
            if len(sen) <= 8:
                chunks.append(sen)
                continue
            part = []
            for i in sen:
                part.append(i)
                if toks[i].endswith(",") and len(part) >= 2:
                    chunks.append(part)
                    part = []
            if part:
                chunks.append(part)
        for k, ch in enumerate(chunks):
            a = ws[ch[0]]["start"]
            b = ws[chunks[k + 1][0]]["start"] if k + 1 < len(chunks) else l["end"] + 0.35
            caps.append(dict(words=[toks[i] for i in ch], starts=[ws[i]["start"] for i in ch], a=a, b=b,
                             spk=GROUP[l["speaker"]]))
    return caps


CAPS = []
import shots as _S1  # noqa: E402
S1_HERO = _S1.shot_hero
SUB_Y = {S.shot_hook_oma: 1400, S1_HERO: 1420, S.hero2: 1460, S.shot_eyes: 1550, S.shot_achtzig: 1450,
         S.shot_mutig_close: 1450, S.shot_80: 1450}


def sub_text(words, n):
    """Wörter bis n sichtbar; Sonderzeichen-Text für Darstellung."""
    return " ".join(words[:n])


def draw_caps(f, T, fn):
    y = SUB_Y.get(fn, 1340)
    act = [c for c in CAPS if c["a"] <= T < c["b"]]
    for c in act[-1:]:
        if True:
            n = max(1, sum(1 for s in c["starts"] if s <= T + 0.02))
            # ganzer Satz sichtbar, das gerade gesprochene Wort leuchtet gelb (Karaoke-Stil)
            txt = " ".join(c["words"])
            wi = sum(len(w.split()) for w in c["words"][:n - 1])
            im = text_img(txt, 80, (255, 255, 255), F_INTER, max_w=860, hl=(wi, (255, 222, 40)))
            sc = 1.0 + 0.08 * (1 - clamp01((T - c["a"]) / 0.12))
            paste_c(f, im, 500, y, sc)


# ------------------------------------------------------------------ Texte / Titel
def pop(T, a, dur=0.28):
    if T < a:
        return 0.0
    return ease_back((T - a) / dur, 2.4) if T - a < dur else 1.0


def overlays(f, T):
    END = S.SHOTS[-1][0]
    if T < 2.2 or T >= END:
        im = text_img("Er hat sich mit der FALSCHEN Oma angelegt 😳", 68, (255, 255, 255), F_BLACK, max_w=900,
                      hl=(5, (255, 60, 60)))
        paste_c(f, im, 500, 320, 1.0)
    if 2.4 <= T < 4.2:
        paste_c(f, text_img("⏪ Heute Morgen …", 76, (255, 255, 255), F_BLACK, max_w=900), 500, 330, pop(T, 2.4))
    if 4.8 <= T < 5.9:
        paste_c(f, text_img("80 🎂", 92, (255, 230, 70), F_BLACK), 300, 640, pop(T, 4.8), 1.0, 8)
    if 6.6 <= T < 8.4:
        paste_c(f, text_img("Vertretungslehrerin 👵📚", 62, (255, 255, 255), F_BLACK, max_w=900), 500, 330,
                pop(T, 6.6))
    if 14.75 <= T < 16.7:
        paste_c(f, text_img("Die Stricknadeln 🧶", 90, (255, 255, 255), F_BLACK, max_w=900), 500, 330, pop(T, 14.77))
    if 19.2 <= T < 21.85:
        paste_c(f, text_img("Handy weg 📵", 96, (255, 255, 255), F_BLACK), 500, 330, pop(T, 19.22))
    if 27.4 <= T < 29.6:
        paste_c(f, text_img("Große Pause 🔔", 90, (255, 255, 255), F_BLACK, max_w=900), 500, 330, pop(T, 27.45))
    if S.SWEEP_T <= T < S.SLAM_T + 0.5:
        paste_c(f, text_img("Fußfeger 🦶", 96, (255, 255, 255), F_BLACK), 500, 330, pop(T, S.SWEEP_T))
    if 47.0 <= T < 56.3:
        a = clamp01((T - 47.0) / 0.25)
        im = text_img("Echter Tipp: Wenn jemand gemobbt wird – nicht wegschauen, Lehrer holen.", 56,
                      (255, 255, 255), F_INTER, max_w=820, stroke=6)
        box = Image.new("RGBA", (im.width + 40, im.height + 16), (0, 0, 0, 0))
        ImageDraw.Draw(box).rounded_rectangle([0, 0, box.width, box.height], radius=30, fill=(20, 20, 30, 185))
        box.alpha_composite(im, (20, 4))
        paste_c(f, box, 500, 330, 1.0, a)
    if 57.9 <= T < 59.4:
        dt = T - 57.9
        s = 1.0 + 1.6 * (1 - ease_out(dt / 0.16))
        im = extrude_text("OMA FRIEDA FAUST", 112, (255, 214, 60), (170, 90, 10), depth=18, max_w=840)
        paste_c(f, im, 500, 400, s, clamp01(dt / 0.08))
    if 59.4 <= T < END:
        q = text_img("Wo geht Oma Frieda als Nächstes hin?", 70, (255, 255, 255), F_BLACK, max_w=880)
        paste_c(f, q, 500, 320, pop(T, 59.45))
        opts = [("1️⃣ Supermarkt 🛒", (255, 196, 40)), ("2️⃣ Disco 🪩", (40, 200, 190)),
                ("3️⃣ Arztpraxis 🩺", (240, 70, 170))]
        for k, (txt, col) in enumerate(opts):
            s = pop(T, 59.75 + k * 0.22)
            if s <= 0:
                continue
            wob = math.sin((T - 59.4) * 5 + k) * 1.5
            paste_c(f, option_card(txt, col), 500, 560 + k * 165, s, 1.0, wob)
        if T >= 60.55:
            pulse = 1.0 + 0.06 * math.sin((T - 60.55) * 10)
            paste_c(f, text_img("Schreib nur die Zahl! 👇", 66, (255, 230, 70), F_BLACK, max_w=880), 500, 1060,
                    pop(T, 60.55) * pulse)


_cards = {}


def option_card(txt, col):
    if txt in _cards:
        return _cards[txt]
    im = text_img(txt, 72, (255, 255, 255), F_BLACK, max_w=900, stroke=8)
    card = Image.new("RGBA", (760, 150), (0, 0, 0, 0))
    rrect(card, 6, 6, 754, 144, 60, col, amb=0.6, spec=0.25)
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([6, 6, 754, 144], radius=60, outline=(255, 255, 255), width=6)
    paste_c(card, im, 380, 80)
    _cards[txt] = card
    return card


# ------------------------------------------------------------------ Frame
def init():
    if CAPS:
        return
    load_envs()
    CAPS.extend(build_caps())
    Wd.MOUTH["fn"] = mouth_fn


def render_frame(fi):
    T = fi / FPS
    i, a, b, fn = S.shot_at(T)
    f = fn(T - a, T)
    if f.size != (W, H):
        f = f.resize((W, H))
    f = W3.natural(f, T)
    overlays(f, T)
    draw_caps(f, T, fn)
    return f.convert("RGB").tobytes()


# ------------------------------------------------------------------ Audio
def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(d, 1e-4))


def tone(f, dur, a=0.005, d=0.3, harm=(1.0,), detune=0.0):
    t = np.arange(int(dur * SR)) / SR
    x = sum(h * np.sin(2 * np.pi * f * (k + 1) * t * (1 + detune)) for k, h in enumerate(harm))
    return x * env(len(t), a, d)


def noise(dur, seed=0):
    return np.random.default_rng(seed).normal(0, 1, int(dur * SR))


def lowpass(x, cutoff):
    a = 1 - math.exp(-2 * math.pi * cutoff / SR)
    y = np.zeros_like(x)
    acc = 0.0
    # vektorisiert über IIR via lfilter-Ersatz (zweimal für Steilheit)
    from itertools import accumulate  # noqa
    for _ in range(2):
        out = np.empty_like(x)
        acc = 0.0
        for i in range(0, len(x), 4096):
            seg = x[i:i + 4096]
            r = np.empty_like(seg)
            for j, v in enumerate(seg):
                acc += a * (v - acc)
                r[j] = acc
            out[i:i + 4096] = r
        x = out
    return x


def fast_lp(x, cutoff):
    """FFT-Tiefpass (schnell)."""
    X = np.fft.rfft(x)
    fr = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (fr / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def fast_bp(x, lo, hi):
    X = np.fft.rfft(x)
    fr = np.fft.rfftfreq(len(x), 1 / SR)
    X *= (1 / (1 + (fr / hi) ** 4)) * (1 - 1 / (1 + (fr / lo) ** 4))
    return np.fft.irfft(X, len(x))


def fx_scratch():
    dur = 0.42
    t = np.arange(int(dur * SR)) / SR
    rate = np.interp(t, [0, 0.1, 0.18, 0.3, 0.42], [1.0, 2.6, -1.8, 1.4, 0.2])
    ph = np.cumsum(rate) / SR
    n = noise(dur, 3)
    src = np.sin(2 * np.pi * 180 * ph) * 0.5 + np.sin(2 * np.pi * 420 * ph) * 0.3
    x = src * np.abs(rate) + fast_bp(n, 800, 4000) * 0.4 * np.abs(rate)
    return x * np.minimum(1, (dur - t) / 0.05) * 0.9


def fx_rewind():
    dur = 0.75
    t = np.arange(int(dur * SR)) / SR
    x = np.zeros_like(t)
    for k in range(9):
        f0 = 600 + 300 * k
        x += np.sin(2 * np.pi * (f0 * t + 900 * t * t)) * (0.5 + 0.5 * np.sin(2 * np.pi * 22 * t + k))
    x = x / 9 + fast_bp(noise(dur, 4), 1500, 6000) * 0.25
    return x * np.minimum(1, t / 0.03) * np.minimum(1, (dur - t) / 0.05) * 0.7


def fx_whoosh(dur=0.35, seed=0, lo=300, hi=3000):
    n = fast_bp(noise(dur, seed), lo, hi)
    t = np.arange(len(n)) / SR
    e = np.sin(np.pi * t / dur) ** 2
    return n * e * 0.6


def fx_bass(dur=1.4):
    t = np.arange(int(dur * SR)) / SR
    f = 30 + 70 * np.exp(-t * 9)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.4)
    x += fast_lp(noise(0.08, 9), 2000)[:len(t)].tolist() + [0] * 0 if False else 0
    click = np.zeros_like(t)
    click[:int(0.02 * SR)] = noise(0.02, 7) * np.linspace(1, 0, int(0.02 * SR)) * 0.6
    return np.tanh((x + click) * 1.6) * 0.95


def fx_braam(dur=1.8, root=55.0):
    t = np.arange(int(dur * SR)) / SR
    x = np.zeros_like(t)
    for m, g in ((1, 1.0), (1.5, 0.6), (2, 0.5), (3, 0.25)):
        for dt in (-0.004, 0.0, 0.005):
            ph = 2 * np.pi * root * m * (1 + dt) * t
            x += g * (2 * ((ph / (2 * np.pi)) % 1) - 1)
    x = fast_lp(x, 900) / 8
    e = np.minimum(1, t / 0.04) * np.exp(-t * 1.3)
    return np.tanh(x * e * 2.2) * 0.8


def fx_tension(dur=1.0):
    t = np.arange(int(dur * SR)) / SR
    f = 1400 + 500 * t / dur
    x = np.sin(2 * np.pi * np.cumsum(f * (1 + 0.01 * np.sin(2 * np.pi * 7 * t))) / SR) * (0.6 + 0.4 * np.sin(2 * np.pi * 13 * t))
    x += np.sin(2 * np.pi * 55 * t) * 0.6 + np.sin(2 * np.pi * 58 * t) * 0.4
    return x * np.minimum(1, t / 0.1) * np.minimum(1, (dur - t) / 0.08) * 0.45


def fx_splash():
    dur = 1.2
    t = np.arange(int(dur * SR)) / SR
    n = fast_lp(noise(dur, 11), 2500) * np.exp(-t * 4) * 1.4
    n += fast_bp(noise(dur, 12), 2500, 9000) * np.exp(-t * 6) * 0.5
    for k in range(10):
        st = 0.1 + k * 0.07
        bt = t - st
        m = bt > 0
        f0 = 500 + 140 * k
        n[m] += np.sin(2 * np.pi * (f0 * bt[m] + 1800 * bt[m] ** 2)) * np.exp(-bt[m] * 30) * 0.25
    return np.tanh(n) * 0.9


def fx_flutter(dur=0.9, seed=13):
    t = np.arange(int(dur * SR)) / SR
    n = fast_bp(noise(dur, seed), 300, 2500)
    am = (0.5 + 0.5 * np.sin(2 * np.pi * 17 * t)) ** 3
    return n * am * np.exp(-t * 2) * 0.8


def fx_pop():
    t = np.arange(int(0.09 * SR)) / SR
    return np.sin(2 * np.pi * (500 * t + 4000 * t * t)) * np.exp(-t * 40) * 0.5


def fx_click(seed=0):
    return fast_bp(noise(0.02, seed), 2000, 7000) * np.exp(-np.arange(int(0.02 * SR)) / SR * 300) * 0.5


def fx_chirp(seed):
    r = np.random.default_rng(seed)
    out = []
    for k in range(r.integers(2, 5)):
        d = r.uniform(0.05, 0.1)
        t = np.arange(int(d * SR)) / SR
        f0 = r.uniform(2800, 4200)
        f = f0 + r.uniform(-1500, 1500) * t / d
        out.append(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / d) ** 2)
        out.append(np.zeros(int(r.uniform(0.02, 0.06) * SR)))
    return np.concatenate(out) * 0.25


def fx_sparkle():
    out = np.zeros(int(0.8 * SR))
    for k, f in enumerate((1568, 2093, 2637, 3136)):
        s = tone(f, 0.6, 0.002, 0.25, (1, 0.3))
        i = int(k * 0.06 * SR)
        out[i:i + len(s)] += s * 0.25
    return out


def fx_thud():
    t = np.arange(int(0.35 * SR)) / SR
    return np.sin(2 * np.pi * (90 * t - 60 * t * t)) * np.exp(-t * 12) * 0.9


def fx_riser(dur=2.2):
    t = np.arange(int(dur * SR)) / SR
    n = fast_bp(noise(dur, 21), 1000, 8000) * (t / dur) ** 2 * 0.5
    f = 200 + 900 * (t / dur) ** 2
    n += np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / dur) ** 2 * 0.25
    return n


def pluck(f, dur, bright=1.0):
    t = np.arange(int(dur * SR)) / SR
    x = np.zeros_like(t)
    for h in range(1, 9):
        x += np.sin(2 * np.pi * f * h * t) * np.exp(-t * (2.5 + h * 1.8 / bright)) / h ** 1.1
    return x * np.minimum(1, t / 0.003)


def note(n):
    return 440 * 2 ** ((n - 69) / 12)


def music_cozy(dur):
    """Gemütliche Ukulele + Glockenspiel, C-Dur, 104 bpm."""
    bpm = 104
    beat = 60 / bpm
    out = np.zeros(int(dur * SR) + SR)
    chords = [(60, 64, 67), (65, 69, 72), (67, 71, 74), (60, 64, 67), (57, 60, 64), (65, 69, 72), (67, 71, 74),
              (60, 64, 67)]
    strum = [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
    for bar, ch in enumerate(chords):
        for k, s in enumerate(strum):
            t0 = (bar * 4 + s) * beat
            if t0 > dur:
                break
            g = 0.5 if k % 2 == 0 else 0.3
            for j, n in enumerate(ch):
                x = pluck(note(n), 0.8) * g * 0.22
                i = int((t0 + j * 0.012) * SR)
                out[i:i + len(x)] += x[:max(0, len(out) - i)]
            bx = pluck(note(ch[0] - 24), 0.9, 0.6) * 0.35
            if k % 4 == 0:
                i = int(t0 * SR)
                out[i:i + len(bx)] += bx[:max(0, len(out) - i)]
    mel = [(0, 76), (0.5, 79), (1, 81), (1.5, 79), (2, 76), (3, 72), (4, 77), (4.5, 76), (5, 74), (6, 72), (8, 76),
           (8.5, 79), (9, 84), (10, 81), (11, 79), (12, 77), (12.5, 76), (13, 74), (14, 72), (16, 76), (17, 79),
           (18, 81), (19, 79), (20, 76), (22, 72)]
    for b, n in mel:
        t0 = b * beat
        if t0 > dur:
            break
        x = tone(note(n), 0.9, 0.002, 0.35, (1, 0.0, 0.25, 0, 0.1)) * 0.16
        i = int(t0 * SR)
        out[i:i + len(x)] += x[:max(0, len(out) - i)]
    return out[:int(dur * SR)]


def tape_stop(x, dur=0.35):
    n = int(dur * SR)
    seg = x[-n:] if len(x) >= n else x
    rate = np.linspace(1.0, 0.0, len(seg)) ** 1.5
    pos = np.cumsum(rate)
    pos = pos[pos < len(seg) - 1]
    y = np.interp(pos, np.arange(len(seg)), seg)
    y *= np.linspace(1, 0, len(y))
    return np.concatenate([x[:-n], y])


def music_epic(dur, bpm=100):
    """Trailer-Trommeln + Streicher-Ostinato in d-Moll."""
    beat = 60 / bpm
    out = np.zeros(int(dur * SR) + SR)

    def put(x, t0, g=1.0):
        i = int(t0 * SR)
        if i >= len(out):
            return
        out[i:i + len(x)] += x[:len(out) - i] * g

    kick = fx_bass(0.5) * 0.9
    tom = lambda f: np.sin(2 * np.pi * np.cumsum(f * (1 + 0.6 * np.exp(-np.arange(int(0.4 * SR)) / SR * 20))) / SR) * \
        np.exp(-np.arange(int(0.4 * SR)) / SR * 8)  # noqa
    t_lo, t_hi = tom(70.0), tom(110.0)
    snare = fast_bp(noise(0.25, 31), 800, 6000) * np.exp(-np.arange(int(0.25 * SR)) / SR * 14) * 0.5
    n_beats = int(dur / beat) + 1
    for b in range(n_beats):
        t0 = b * beat
        bar_pos = b % 8
        if bar_pos in (0, 3, 6):
            put(kick, t0, 0.8)
        put(t_lo, t0 + beat * 0.5, 0.45)
        if bar_pos in (2, 6):
            put(snare, t0, 0.8)
        if bar_pos == 7:
            for k in range(4):
                put(t_hi, t0 + k * beat / 4, 0.35 + k * 0.1)
    # Ostinato
    seq = [50, 50, 53, 50, 57, 50, 53, 55]
    for b in range(n_beats * 2):
        t0 = b * beat / 2
        n = seq[b % 8] - (0 if (b // 16) % 2 == 0 else 2)
        t = np.arange(int(beat / 2 * SR)) / SR
        ph = note(n) * t
        x = (2 * (ph % 1) - 1) * np.exp(-t * 6) * 0.12
        put(x, t0)
    return out[:int(dur * SR)]


def build_audio(path):
    n = int(TOTAL * SR)
    END = S.SHOTS[-1][0]
    voice = np.zeros(n)
    for l in TL["lines"]:
        x = read_wav(l["wav"])
        g = 1.0
        if l["speaker"] == "erz":
            g = 1.05
        i = int(l["start"] * SR)
        voice[i:i + len(x)] += x[:n - i] * g
    sfx = np.zeros(n)
    mus = np.zeros(n)

    def put(buf, x, T, g=1.0):
        i = int(T * SR)
        if i >= n or i + len(x) <= 0:
            return
        if i < 0:
            x = x[-i:]
            i = 0
        buf[i:i + len(x)] += x[:n - i] * g

    # Hook
    put(sfx, fx_braam(1.6, 49), 0.0, 0.9)
    put(sfx, fx_whoosh(0.6, 1, 200, 1500), 0.0, 0.5)
    put(sfx, fx_scratch(), S.FREEZE_AT - 0.03, 1.0)
    put(sfx, fx_rewind(), 2.2, 0.9)
    quiet = {0.0, 0.9, 2.2, 2.95, 14.5, 40.1, 41.7, 42.35, 43.45, 56.3, 59.4, END}
    for k, (a, b, fn) in enumerate(S.SHOTS):
        if round(a, 2) in quiet:
            continue
        put(sfx, fx_whoosh(0.28, 40 + k, 600, 5000), a - 0.12, 0.18)
    # gemütlicher Morgen + Klassenzimmer
    cozy = tape_stop(music_cozy(13.85 - 2.95), 0.3)
    put(mus, cozy, 2.95, 0.8)
    rng = np.random.default_rng(5)
    for t0 in np.arange(3.1, 5.8, 0.55):
        put(sfx, fx_chirp(int(t0 * 100)), t0 + rng.uniform(0, 0.3), 0.4)
    put(sfx, fx_pop(), 4.8, 0.6)
    put(sfx, fx_pop(), 6.6, 0.6)
    for t0 in np.arange(6.2, 7.0, 0.09):
        put(sfx, fx_click(int(t0 * 70)), t0, 0.5)
    # Papierkügelchen
    put(sfx, fx_whoosh(0.6, 33, 800, 6000), 14.1, 0.8)
    put(sfx, fx_thud(), 14.75, 0.8)
    put(sfx, fx_bass(1.0), 14.75, 0.7)
    put(sfx, fx_sparkle(), 14.8, 0.6)
    epic = music_epic(END - 14.75)
    put(mus, epic, 14.75, 0.62)
    # Handy
    for t0 in np.arange(17.35, 18.0, 0.12):
        put(sfx, tone(880 + 220 * ((t0 * 10) % 3), 0.08, 0.002, 0.05) * 0.3, t0, 0.6)
    put(sfx, fx_whoosh(0.25, 34, 500, 4000), 18.45, 0.6)
    put(sfx, fx_pop(), 19.22, 0.6)
    # Draußen: Tritt gegen die Dixi-Tür
    for k in range(3):
        put(sfx, fx_thud(), 25.9 + k * 0.6, 0.6)
    # Pause
    t = np.arange(int(1.0 * SR)) / SR
    ring = (np.sin(2 * np.pi * 1900 * t) + 0.5 * np.sin(2 * np.pi * 2650 * t)) * (np.sin(2 * np.pi * 22 * t) > 0)
    put(sfx, ring * np.exp(-t * 1.5) * 0.4, 27.4, 1.0)
    put(sfx, fx_braam(1.6, 46), 29.6, 0.6)
    put(sfx, fx_tension(1.4), 33.2, 0.4)
    put(sfx, fx_tension(1.6), 40.1, 0.9)
    put(sfx, fx_bass(0.9), 40.1, 0.6)
    # Wurf
    put(sfx, fx_whoosh(0.25, 50, 400, 3000), S.GRIP_T, 0.7)
    put(sfx, fx_thud(), S.GRIP_T + 0.05, 0.5)
    put(sfx, fx_whoosh(0.35, 51, 300, 4000), S.STEP_T, 0.8)
    put(sfx, fx_bass(1.4), S.SWEEP_T, 1.0)
    put(sfx, fx_thud(), S.SWEEP_T, 1.0)
    tt = np.arange(int(1.1 * SR)) / SR
    drone = (np.sin(2 * np.pi * 41 * tt) + 0.5 * np.sin(2 * np.pi * 61.5 * tt)) * np.sin(np.pi * tt / 1.1) * 0.5
    put(sfx, drone, S.SWEEP_T, 0.8)
    put(sfx, fx_whoosh(1.0, 10, 80, 600), S.SWEEP_T, 0.9)
    slam = fast_lp(noise(0.4, 61), 900) * np.exp(-np.arange(int(0.4 * SR)) / SR * 12) * 2.0
    put(sfx, np.tanh(slam), S.SLAM_T, 1.0)
    put(sfx, fx_thud(), S.SLAM_T, 1.0)
    put(sfx, fx_pop(), S.SLAM_T + 0.1, 0.6)
    put(sfx, fx_pop(), 44.7, 0.4)
    put(sfx, fx_whoosh(0.5, 52, 400, 4000), S.RUN_T, 0.7)
    for k in range(6):
        put(sfx, fx_click(300 + k), S.RUN_T + k * 0.11, 0.6)
    put(sfx, np.tanh(slam), S.SLAM2_T, 0.9)
    put(sfx, fx_thud(), S.SLAM2_T, 0.9)
    # Klopfen + Bonbon
    for k in range(3):
        put(sfx, fx_thud(), 46.95 + k * 0.5, 0.5)
    put(sfx, fx_whoosh(0.4, 53, 1500, 7000), S.BONBON_T, 0.5)
    put(sfx, fx_pop(), S.BONBON_T + 0.7, 0.6)
    put(sfx, fx_sparkle(), 51.2, 0.5)
    # Held
    put(sfx, fx_braam(2.0, 55), 56.3, 0.7)
    put(sfx, fx_sparkle(), 56.8, 0.6)
    put(sfx, fx_bass(1.4), 57.9, 1.0)
    put(sfx, fx_braam(1.6, 41), 57.9, 0.9)
    # Ende
    for k in range(3):
        put(sfx, fx_pop(), 59.75 + k * 0.22, 0.7)
    put(sfx, fx_pop(), 60.55, 0.6)
    put(sfx, fx_riser(2.6), 59.8, 0.6)
    put(sfx, fx_scratch(), END, 1.0)
    # Ducking
    ve = np.abs(voice)
    k = int(0.15 * SR)
    ve = np.convolve(ve, np.ones(k) / k, mode="same")
    duck = 1 - 0.6 * np.clip(ve * 8, 0, 1)
    mix = voice * 1.25 + sfx * 0.55 + mus * 0.42 * duck
    # Musik/Effekte vor dem Loop-Punkt sauber ausblenden
    mix[-int(0.02 * SR):] *= np.linspace(1, 0, int(0.02 * SR))
    mix = mix / (np.max(np.abs(mix)) + 1e-6) * 0.92
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ------------------------------------------------------------------ main
def main():
    args = sys.argv[1:]
    if args and args[0] == "preview":
        init()
        outd = BUILD / "stills"
        outd.mkdir(exist_ok=True)
        for a in args[1:]:
            T = float(a)
            fi = int(round(T * FPS))
            Image.frombytes("RGB", (W, H), render_frame(fi)).save(outd / f"t{T:05.2f}.png")
            print("still", T)
        return
    if args and args[0] == "audio":
        init()
        build_audio(BUILD / "mix.wav")
        return
    init()
    wav = BUILD / "mix.wav"
    build_audio(wav)
    silent = BUILD / "video_noaudio.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                           f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-maxrate", "9M", "-bufsize", "18M",
                           "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
    procs = int(os.environ.get("PROCS", "4"))
    with Pool(procs, initializer=init) as pool:
        for k, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=6)):
            ff.stdin.write(buf)
            if k % 60 == 0:
                print(f"frame {k}/{NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-c:v", "copy",
                    "-af", "loudnorm=I=-14:TP=-1.0:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-shortest", "-movflags", "+faststart", str(OUT)], check=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
