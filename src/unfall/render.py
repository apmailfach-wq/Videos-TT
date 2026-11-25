"""Render unfall-video.mp4 (1080x1920, 30 fps): shot schedule, captions, lip sync, sound design."""
import json
import math
import os
import subprocess
import sys
import wave
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scenes as S  # noqa: E402
from chars import ORANGE  # noqa: E402
from core import (F_BLACK, F_INTER, FPS, H, ROOT, TEAL, W, WHITE, YELLOW, bloom, clamp01, ease_out, font,  # noqa
                  paste_c, vignette_img, zoom_frame)

BUILD = ROOT / "build" / "unfall"
OUT = ROOT / os.environ.get("VIDEO_OUT", "unfall-video.mp4")
TL = json.loads((BUILD / "timeline.json").read_text())
LINES = {l["id"]: l for l in TL["lines"]}
TOTAL = TL["total"]
NFRAMES = int(math.ceil(TOTAL * FPS))
SR = 48000


def st(i):
    return LINES[i]["start"]


def en(i):
    return LINES[i]["start"] + LINES[i]["speech"]


def wd(i, word, occ=0):
    n = 0
    for w in LINES[i]["words"]:
        if w["text"].strip(".,:!?…").lower().startswith(word.lower()):
            if n == occ:
                return st(i) + w["start"]
            n += 1
    raise KeyError((i, word))


# ------------------------------------------------------------------ schedule
def build_schedule():
    sch = []

    def add(fn, a, b, punch=True, whoosh=True, dark=False, logo=True):
        sch.append(dict(fn=fn, a=a, b=b, punch=punch, whoosh=whoosh, dark=dark, logo=logo))

    L = st("e1")
    add(S.shot_cold, 0.0, L, punch=False, whoosh=False, logo=False)
    add(S.shot_drive, L, st("e2"), punch=False, whoosh=False)
    a = st("e2")
    add(S.shot_cyclist, a, a + 0.45)
    add(S.shot_impact, a + 0.45, a + 0.8, whoosh=False)
    add(S.shot_horn, a + 0.8, a + 1.4, whoosh=False)
    t_gp = wd("e2", "Großprojekt")
    add(S.shot_fly, a + 1.4, t_gp - 0.05, punch=False)
    add(lambda lt, d, T: S.shot_land(lt, d, T, 0.12), t_gp - 0.05, st("r1") - 0.05)
    # r1: hard cuts on every word
    add(S.shot_phone, st("r1") - 0.05, wd("r1", "Fahrrad") - 0.05)
    add(S.shot_wheel, wd("r1", "Fahrrad") - 0.05, wd("r1", "Hand", 1) - 0.05)
    add(S.shot_shoulder, wd("r1", "Hand", 1) - 0.05, wd("r1", "Totalschaden") - 0.05)
    add(S.shot_total, wd("r1", "Totalschaden") - 0.05, st("a1") - 0.05)
    add(S.shot_dent, st("a1") - 0.05, wd("a1", "Meine") - 0.05)
    add(S.shot_driver_close, wd("a1", "Meine") - 0.05, wd("a1", "Ich") - 0.05)
    add(S.shot_broetchen, wd("a1", "Ich") - 0.05, st("e3") - 0.05)
    times = [wd("e3", "Handy"), wd("e3", "Fahrrad"), wd("e3", "Schulter"), wd("e3", "Stirn")]
    t_w = wd("e3", "Willkommen")
    add(lambda lt, d, T: S.shot_museum(lt, d, T, times, t_w), st("e3") - 0.05, st("r2") - 0.05)
    marks = [("📱 HANDY", wd("r2", "Handy")), ("🚲 FAHRRAD", wd("r2", "Fahrrad")),
             ("💪 SCHULTER", wd("r2", "Schulter"))]
    add(S.shot_argue("r2", marks), st("r2") - 0.05, st("a2") - 0.05)
    add(S.shot_argue("a2a"), st("a2") - 0.05, wd("a2", "Soll") - 0.05)
    add(S.shot_argue("a2b"), wd("a2", "Soll") - 0.05, st("r3") - 0.03)
    add(S.shot_punch_close("radler", "SIE SIND SCHULD!"), st("r3") - 0.03, st("a3") - 0.03)
    add(S.shot_punch_close("auto", "VORS AUTO GEFAHREN!"), st("a3") - 0.03, en("a3") + 0.05)
    add(lambda lt, d, T: S.shot_brawl(lt, d, T), en("a3") + 0.05, st("e4"))
    t_sv = wd("e4", "Strafverfahren")
    arr = st("p1") - 0.75
    add(lambda lt, d, T: S.shot_cost(lt, d, T, t_sv), st("e4"), arr, punch=False, whoosh=False)
    add(S.shot_police_arrive, arr, st("p1"))
    add(S.shot_cop, st("p1"), st("a4") - 0.05)
    add(S.shot_shout, st("a4") - 0.05, en("r4") + 0.05)
    add(lambda lt, d, T: S.shot_cop(lt, d, T, look=False), en("r4") + 0.05, en("p2") + 0.05)
    add(S.shot_both_point, en("p2") + 0.05, st("e5") - 0.05)
    t_u = wd("e5", "Urlaub")
    add(lambda lt, d, T: S.shot_vacation(lt, d, T, t_u), st("e5") - 0.05, st("j0") - 0.05)
    add(S.shot_gavel, st("j0") - 0.05, st("j1") - 0.05, dark=True, logo=False)
    add(S.shot_law(["s7"], [st("j1") - 0.05], S.law_extra_s7), st("j1") - 0.05, st("j2") - 0.05, dark=True)
    add(S.shot_law(["achtung", "mitv"], [st("j2") - 0.05, wd("j2", "Auch") - 0.05], S.law_extra_mitv),
        st("j2") - 0.05, st("j3") - 0.05, dark=True)
    add(S.shot_law(["ersatz", "schmerz"], [st("j3") - 0.05, wd("j3", "Und") - 0.05], S.law_extra_ersatz),
        st("j3") - 0.05, st("j4") - 0.05, dark=True)
    add(S.shot_law(["s223"], [st("j4") - 0.05], S.law_extra_223), st("j4") - 0.05, st("a5") - 0.05, dark=True)
    t_drei = wd("r5", "drei")
    add(lambda lt, d, T: S.shot_bench(lt, d, T, t_drei), st("a5") - 0.05, st("e6") - 0.05)
    counters = [("5 SCHÄDEN", wd("e6", "Fünf")), ("3 STREITPARTEIEN", wd("e6", "drei"))]
    t_p = wd("e6", "Papierkram") - 0.3
    add(lambda lt, d, T: S.shot_paper(lt, d, T, counters, t_p), st("e6") - 0.05, st("cta") - 0.05, punch=False)
    tl = [wd("cta", "Wer", 0), wd("cta", "Wer", 1), wd("cta", "Wer", 2)]
    t_c = wd("cta", "Schreib")
    add(lambda lt, d, T: S.shot_cta(lt, d, T, tl, t_c), st("cta") - 0.05, TOTAL, logo=False)
    return sch


SCH = build_schedule()


def shot_at(T):
    cur = SCH[0]
    for s in SCH:
        if T >= s["a"]:
            cur = s
    return cur


# ------------------------------------------------------------------ lip sync
ENV = {}
WHO = {"auto": "auto", "radler": "radler", "polizei": "polizei"}


def load_envs():
    for l in TL["lines"]:
        with wave.open(l["wav"]) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        hop = SR // FPS
        n = len(a) // hop
        rms = np.sqrt(np.mean(a[: n * hop].reshape(n, hop) ** 2, axis=1))
        ENV[l["id"]] = rms / (rms.max() + 1e-6)


def mouth(who, T):
    for l in TL["lines"]:
        if l["speaker"] == who and l["start"] <= T < l["start"] + l["dur"]:
            e = ENV[l["id"]]
            i = int((T - l["start"]) * FPS)
            if 0 <= i < len(e):
                return float(np.clip(e[i] * 1.6, 0, 1))
    return 0.0


# ------------------------------------------------------------------ captions
CAP_COL = {"erz": YELLOW, "radler": TEAL, "auto": ORANGE, "polizei": (110, 180, 255)}
CAP_NAME = {"radler": "RADFAHRER", "auto": "AUTOFAHRER", "polizei": "POLIZIST"}
REPL = {"Paragraf": "§", "Straßenverkehrsgesetz": "StVG", "223 Strafgesetzbuch": "223 StGB",
        "Strafgesetzbuch": "StGB"}


def build_caps():
    caps = []
    for l in TL["lines"]:
        words = [dict(text=REPL.get(w["text"], w["text"]), a=l["start"] + w["start"], b=l["start"] + w["end"])
                 for w in l["words"]]
        script_words = l["text"].replace(" –", ",").replace("…", "").split()
        chunk, j = [], 0
        for w in words:
            if chunk and (len(chunk) >= 3 or sum(len(x["text"]) for x in chunk) + len(w["text"]) > 17):
                caps.append((l, chunk))
                chunk = []
            chunk.append(w)
            j += len(w["text"].split()) if w["text"] not in ("§", "StVG", "StGB", "223 StGB") else \
                (2 if w["text"] == "223 StGB" else 1)
            if j - 1 < len(script_words) and script_words[j - 1][-1] in ",.:!?":
                caps.append((l, chunk))
                chunk = []
        if chunk:
            caps.append((l, chunk))
    out = []
    for i, (l, ch) in enumerate(caps):
        nxt = caps[i + 1][1][0]["a"] if i + 1 < len(caps) else TOTAL
        out.append(dict(line=l, words=ch, a=ch[0]["a"], b=min(nxt, ch[-1]["b"] + 0.45)))
    return out


CAPS = build_caps()


@lru_cache(maxsize=4096)
def cap_img(ci, act):
    c = CAPS[ci]
    spk = c["line"]["speaker"]
    f = font(F_INTER, 86)
    sp = f.getlength(" ")
    ws = [f.getlength(w["text"]) for w in c["words"]]
    tw = sum(ws) + sp * (len(ws) - 1)
    hh = 150 + (60 if spk in CAP_NAME else 0)
    im = Image.new("RGBA", (int(tw + 80), hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    y = hh - 75
    if spk in CAP_NAME:
        tag = CAP_NAME[spk]
        tf = font(F_INTER, 34)
        tl = tf.getlength(tag)
        d.rounded_rectangle([im.width / 2 - tl / 2 - 18, 6, im.width / 2 + tl / 2 + 18, 54], radius=24,
                            fill=CAP_COL[spk])
        d.text((im.width / 2, 30), tag, font=tf, fill=(10, 10, 20), anchor="mm")
    x = 40
    for i, (w, ww) in enumerate(zip(c["words"], ws)):
        col = CAP_COL[spk] if i == act else WHITE
        d.text((x, y), w["text"], font=f, fill=col, anchor="lm", stroke_width=12, stroke_fill=(0, 0, 0))
        x += ww + sp
    return im


def draw_caps(frame, T):
    for ci, c in enumerate(CAPS):
        if c["a"] <= T < c["b"]:
            act = max([i for i, w in enumerate(c["words"]) if T >= w["a"]] or [0])
            img = cap_img(ci, act)
            p = clamp01((T - c["a"]) / 0.12)
            sc = (0.8 + 0.2 * ease_out(p) + 0.05 * math.sin(p * math.pi)) * min(1.0, 1010 / img.width)
            paste_c(frame, img, W / 2, 1610, sc)
            return


@lru_cache(maxsize=1)
def logo_img():
    f = font(F_BLACK, 34)
    t = "ALLTAG KLAR"
    tw = f.getlength(t)
    im = Image.new("RGBA", (int(tw + 120), 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, im.width - 1, 69], radius=35, fill=(15, 15, 28, 210), outline=YELLOW, width=4)
    d.text((44, 35), "§", font=font(F_INTER, 40), fill=YELLOW, anchor="mm")
    d.text((im.width / 2 + 20, 35), t, font=f, fill=WHITE, anchor="mm")
    return im


# ------------------------------------------------------------------ frame
VIG = None


def init():
    global VIG
    load_envs()
    S.CTX["mouth"] = mouth
    VIG = vignette_img()


def render_frame(fi):
    T = fi / FPS
    s = shot_at(T)
    lt = T - s["a"]
    f = s["fn"](lt, s["b"] - s["a"], T)
    if f.size != (W, H):
        f = f.resize((W, H))
    if s["punch"] and lt < 0.18:
        f = zoom_frame(f, 1 + 0.07 * (1 - ease_out(lt / 0.18)))
    out = (bloom(f, 0.85) if s["dark"] else bloom(f, 0.35, 215)).convert("RGBA")
    out.alpha_composite(VIG)
    if s["logo"]:
        paste_c(out, logo_img(), 60 + logo_img().width / 2, 150)
    draw_caps(out, T)
    return out.convert("RGB").tobytes()


# ------------------------------------------------------------------ audio
def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)


def tone(f, dur, a=0.002, d=0.2, kind="sin"):
    n = int(dur * SR)
    ph = 2 * np.pi * np.cumsum(np.full(n, f) if np.ndim(f) == 0 else f[:n]) / SR
    w = np.sin(ph) if kind == "sin" else (2 * ((ph / (2 * np.pi)) % 1) - 1)
    return w * env(n, a, d)


def noise(dur, rng):
    return rng.standard_normal(int(dur * SR))


def lowpass(x, alpha):
    from scipy.signal import lfilter  # noqa
    return lfilter([alpha], [1, alpha - 1], x)


def fx_whoosh(rng):
    n = int(0.38 * SR)
    x = noise(0.38, rng)
    u = np.linspace(0, 1, n)
    y = lowpass(x, 0.12)
    return y * np.sin(np.pi * u) ** 1.4 * 2.2


def fx_thud(rng):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * (55 + 70 * np.exp(-t * 30)) * t) * env(n, 0.001, 0.1) * 1.3 + noise(
        0.3, rng) * env(n, 0.0005, 0.015) * 0.5


def fx_crash(rng):
    n = int(1.1 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (45 + 120 * np.exp(-t * 18)) * t) * env(n, 0.001, 0.25) * 1.4
    metal = noise(1.1, rng) * env(n, 0.001, 0.18) * 0.9
    glass = np.zeros(n)
    for k in range(40):
        i = int(rng.uniform(0.02, 0.8) * SR)
        f = rng.uniform(3000, 7000)
        L = int(0.06 * SR)
        g = np.sin(2 * np.pi * f * np.arange(L) / SR) * env(L, 0.0005, 0.02) * 0.25
        glass[i:i + L] += g[: n - i]
    return body + metal + glass


def fx_screech(rng):
    n = int(0.7 * SR)
    t = np.arange(n) / SR
    f = 2300 + 300 * np.sin(2 * np.pi * 9 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * 0.4 + noise(0.7, rng) * 0.15) * env(n, 0.01, 0.4)


def fx_horn(dur=0.9):
    n = int(dur * SR)
    t = np.arange(n) / SR
    w = sum(np.sign(np.sin(2 * np.pi * f * t)) * 0.5 for f in (415, 523))
    return w * 0.22 * np.minimum(1, t / 0.01) * np.minimum(1, (dur - t) / 0.05)


def fx_bell():
    return (tone(2400, 0.8, d=0.3) + tone(3150, 0.8, d=0.25) * 0.6) * 0.35


def fx_scratch(rng):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 300 + 900 * np.abs(np.sin(2 * np.pi * 3.2 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sign(np.sin(ph)) * 0.25 + noise(0.45, rng) * 0.2) * env(n, 0.005, 0.3)


def fx_glass(rng):
    n = int(0.6 * SR)
    out = noise(0.6, rng) * env(n, 0.001, 0.05) * 0.4
    for k in range(25):
        i = int(rng.uniform(0, 0.4) * SR)
        L = int(0.05 * SR)
        g = np.sin(2 * np.pi * rng.uniform(3500, 8000) * np.arange(L) / SR) * env(L, 0.0005, 0.015) * 0.3
        out[i:i + L] += g[: n - i]
    return out


def fx_wobble(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 180 + 60 * np.sin(2 * np.pi * 6 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * 0.3 * np.minimum(1, t / 0.05) * np.minimum(1, (dur - t) / 0.1)


def fx_boing():
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    f = 200 + 250 * np.sin(2 * np.pi * 10 * t) * np.exp(-t * 4)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.18) * 0.5


def fx_pop():
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(700 + 1200 * t / t[-1]) / SR) * env(n, 0.002, 0.03) * 0.7


def fx_chime():
    return (tone(988, 0.9, d=0.4) + tone(1319, 0.9, d=0.35) * 0.6) * 0.4


def fx_kaching():
    return (tone(1567, 0.5, d=0.18) + tone(2093, 0.5, d=0.22) * 0.8) * 0.5


def fx_siren(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = np.where((t * 1.6) % 1 < 0.5, 660, 880)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) + 0.3 * np.sin(2 * ph)) * 0.35 * np.minimum(1, t / 0.2)


def fx_engine(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 62 + 10 * np.sin(t * 1.3)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (2 * ((ph / (2 * np.pi)) % 1) - 1) * 0.12 * np.minimum(1, t / 0.3) * np.minimum(1, (dur - t) / 0.2)


def fx_whistle(dur):
    notes = [784, 880, 988, 880, 784, 659, 784]
    out = np.zeros(int(dur * SR))
    L = int(dur / len(notes) * SR)
    for k, f in enumerate(notes):
        seg = tone(f * 1.5, L / SR, a=0.02, d=0.5) * 0.18
        out[k * L:k * L + len(seg)] += seg[: len(out) - k * L]
    return out


def fx_gavel(rng):
    out = fx_thud(rng) * 1.2
    t = tone(320, 0.25, d=0.06) * 0.6
    out[:len(t)] += t
    return out


def beat(total, mutes, bpm=118):
    rng = np.random.default_rng(5)
    n = int(total * SR) + SR
    out = np.zeros(n)
    beat_s = 60 / bpm
    kick_n = int(0.28 * SR)
    kt = np.arange(kick_n) / SR
    kick = np.sin(2 * np.pi * (45 + 110 * np.exp(-kt * 28)) * kt) * env(kick_n, 0.001, 0.14)
    clap = lowpass(rng.standard_normal(int(0.15 * SR)), 0.5) * env(int(0.15 * SR), 0.001, 0.05) * 0.6
    hat = np.diff(rng.standard_normal(int(0.035 * SR) + 1)) * env(int(0.035 * SR), 0.0005, 0.008) * 0.3
    bass_notes = [55.0, 65.41, 49.0, 58.27]
    i, t = 0, 0.0
    while t < total:
        s0 = int(t * SR)

        def put(sig, at, g=1.0):
            seg = sig[: max(0, n - at)]
            out[at:at + len(seg)] += seg * g
        put(kick, s0, 0.85)
        if i % 2 == 1:
            put(clap, s0, 0.7)
        for k in range(2):
            put(hat, s0 + int(k * beat_s / 2 * SR), 0.8 if k else 0.4)
        f = bass_notes[(i // 4) % 4]
        L = int(beat_s * SR)
        bt = np.arange(L) / SR
        bass = (np.sin(2 * np.pi * f * bt) + 0.5 * np.sin(4 * np.pi * f * bt)) * np.minimum(1, bt / 0.01) * \
            np.exp(-bt / 0.2) * 0.35
        put(bass, s0 + int(beat_s / 2 * SR))
        t += beat_s
        i += 1
    tt = np.arange(n) / SR
    gate = np.ones(n)
    for a, b in mutes:
        gate[(tt >= a) & (tt < b)] = 0.0
    return out * gate


def build_audio(path):
    rng = np.random.default_rng(7)
    n = int((TOTAL + 1) * SR)
    voice = np.zeros(n)
    for l in TL["lines"]:
        with wave.open(l["wav"]) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        i = int(l["start"] * SR)
        voice[i:i + len(a)] += a[: n - i]
    sfx = np.zeros(n)

    def put(sig, T, g=1.0):
        i = int(max(0, T) * SR)
        seg = sig[: max(0, n - i)]
        sfx[i:i + len(seg)] += seg * g

    for s in SCH:
        if s["whoosh"]:
            put(fx_whoosh(rng), s["a"] - 0.15, 0.4)
    # cold open
    put(fx_crash(rng), 0.0, 0.6)
    put(fx_scratch(rng), st("e1") - 0.35, 1.0)
    # scene 1
    a = st("e2")
    put(fx_engine(a + 1.0 - st("e1")), st("e1"), 1.0)
    put(fx_whistle(a - st("e1")), st("e1") + 0.1, 0.8)
    put(fx_bell(), a + 0.1, 0.8)
    put(fx_screech(rng), a + 0.4, 0.9)
    put(fx_crash(rng), a + 0.45 + 0.25, 1.1)
    put(fx_thud(rng), a + 0.8 + 0.24, 1.0)
    put(fx_horn(0.7), a + 0.8 + 0.24, 1.0)
    put(fx_thud(rng), wd("e2", "Großprojekt") + 0.15, 1.2)
    put(fx_gavel(rng), wd("e2", "Großprojekt") + 0.12, 1.0)
    # damages
    put(fx_glass(rng), st("r1"), 1.0)
    put(fx_wobble(wd("r1", "Hand", 1) - wd("r1", "Fahrrad")), wd("r1", "Fahrrad"), 0.9)
    put(fx_boing(), wd("r1", "Hand", 1), 0.8)
    put(fx_thud(rng), wd("r1", "Totalschaden") + 0.3, 1.0)
    put(fx_pop(), st("a1"), 0.8)
    put(fx_boing(), wd("a1", "Meine"), 0.7)
    put(fx_pop(), wd("a1", "Ich"), 0.8)
    put(fx_chime(), st("e3"), 0.6)
    for w_ in ("Handy", "Fahrrad", "Schulter", "Stirn"):
        put(fx_pop(), wd("e3", w_), 0.9)
    put(fx_chime(), wd("e3", "Willkommen"), 0.7)
    for w_ in ("Handy", "Fahrrad", "Schulter"):
        put(fx_kaching(), wd("r2", w_), 0.6)
    # brawl
    t = en("a3") + 0.05
    k = 0
    while t < st("p1") - 0.8:
        put([fx_thud(rng), fx_boing(), fx_pop()][k % 3], t, 0.7 if k % 3 else 0.9)
        t += 0.23 + 0.07 * (k % 2)
        k += 1
    put(fx_gavel(rng), wd("e4", "Strafverfahren"), 1.0)
    put(fx_siren(st("a4") - (st("p1") - 0.75)), st("p1") - 0.75, 0.45)
    put(fx_thud(rng), en("p2") + 0.05, 1.0)
    put(fx_pop(), wd("e5", "Urlaub"), 0.9)
    put(fx_thud(rng), wd("e5", "Urlaub") + 0.35, 1.0)
    # law
    put(fx_gavel(rng), st("j0") - 0.05 + 0.37, 1.3)
    for x in (st("j1"), st("j2"), wd("j2", "Auch"), st("j3"), wd("j3", "Und"), st("j4")):
        put(fx_whoosh(rng), x - 0.15, 0.5)
        put(fx_thud(rng), x + 0.1, 0.7)
    # bench + end
    put(fx_kaching(), wd("r5", "drei"), 0.8)
    put(fx_pop(), wd("e6", "Fünf"), 0.8)
    put(fx_pop(), wd("e6", "drei"), 0.8)
    put(fx_chime(), wd("e6", "Hochzeit"), 0.7)
    for i_ in range(3):
        put(fx_pop(), wd("cta", "Wer", i_), 1.0)
    put(fx_chime(), wd("cta", "Schreib"), 0.6)
    music = beat(TOTAL, [(0, st("e1") - 0.05), (st("e2") + 0.6, wd("e2", "Großprojekt"))])
    venv = np.abs(voice)
    k = int(0.15 * SR)
    venv = np.convolve(venv, np.ones(k) / k, mode="same")
    duck = 1 - np.clip(venv * 12, 0, 0.72)
    mix = voice * 1.0 + sfx * 0.5 + music[:n] * 0.22 * duck
    fade = np.minimum(1, (n - np.arange(n)) / (0.6 * SR))
    mix *= fade
    mix /= max(1e-6, np.abs(mix).max()) / 0.95
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32000).astype(np.int16).tobytes())


def main():
    init()
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        (BUILD / "stills").mkdir(exist_ok=True)
        for t in [float(x) for x in sys.argv[2:]]:
            Image.frombytes("RGB", (W, H), render_frame(int(t * FPS))).save(BUILD / "stills" / f"t{t:05.1f}.png")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "shots":
        for s in SCH:
            print(f'{s["a"]:6.2f}-{s["b"]:6.2f} {getattr(s["fn"], "__name__", "?")}')
        return
    raw = BUILD / "mix_raw.wav"
    build_audio(raw)
    audio = BUILD / "mix.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ar", "48000", str(audio)], check=True)
    if len(sys.argv) > 1 and sys.argv[1] == "audio":
        return
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r",
           str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt",
           "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t",
           f"{NFRAMES / FPS:.3f}", "-shortest", str(OUT)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=init) as pool:
        for i, buf in enumerate(pool.imap(render_frame, range(NFRAMES), chunksize=4)):
            ff.stdin.write(buf)
            if i % 300 == 0:
                print(f"frame {i}/{NFRAMES}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", OUT, f"{NFRAMES / FPS:.2f}s")


if __name__ == "__main__":
    main()
