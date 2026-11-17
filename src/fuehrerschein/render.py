"""Render fuehrerschein-video.mp4 (1080x1920, 30 fps): shot schedule, captions, lip sync, sound design."""
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
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shots as S  # noqa: E402
from core import (BLUE, F_INTER, FPS, H, MAGENTA, ROOT, TEAL, W, WHITE, YELLOW, bloom, clamp01, ease_out, font,
                  paste_c, vignette_img, zoom_frame)  # noqa: E402

BUILD = ROOT / "build" / "fuehrerschein"
OUT = ROOT / "fuehrerschein-video-neon.mp4"
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
        if w["text"].strip(".,:!?…").startswith(word):
            if n == occ:
                return st(i) + w["start"]
            n += 1
    raise KeyError((i, word))


# ------------------------------------------------------------------ schedule
def build_schedule():
    sch = []

    def add(fn, a, b, punch=True, whoosh=True):
        sch.append(dict(fn=fn, a=a, b=b, punch=punch, whoosh=whoosh))

    add(S.shot_ball, 0.0, 1.15, punch=False, whoosh=False)
    add(S.shot_net_boom, 1.15, st("hook2"), punch=False, whoosh=False)
    add(S.shot_bluelight, st("hook2"), st("hook2") + 1.45, punch=False, whoosh=False)
    add(S.shot_license, st("hook2") + 1.45, en("hook2") + 0.05)
    a = en("hook2") + 0.05
    add(S.shot_drone, a, a + 0.65)
    add(S.shot_rafael_party, a + 0.65, st("kla1") + 0.05)
    add(S.shot_klaus_party, st("kla1") + 0.05, st("kla1") + 1.55)
    add(S.shot_split_party, st("kla1") + 1.55, en("kla1") - 0.1)
    add(lambda lt, d, T: S.zoom_frame(S.rafael_room(lt, T, cam=2.2 + lt, joint=True, smoke=1.0, s=1.35), 1.08),
        en("kla1") - 0.1, st("night"))
    add(S.shot_timelapse, st("night"), st("night") + 1.7)
    add(S.shot_xray_r, st("night") + 1.7, st("night") + 3.0)
    add(S.shot_xray_k, st("night") + 3.0, st("raf2") - 0.7)
    add(S.shot_alarm, st("raf2") - 0.7, st("raf2"))
    mr, mk = S.shot_mirror("rafael"), S.shot_mirror("klaus")
    mid_r = (st("raf2") + en("raf2")) / 2
    add(mr, st("raf2"), mid_r)
    add(lambda lt, d, T: S.zoom_frame(mr(lt, d, T), 1.25, 540, 760), mid_r, st("kla2"))
    mid_k = (st("kla2") + en("kla2")) / 2
    add(mk, st("kla2"), mid_k)
    add(lambda lt, d, T: S.zoom_frame(mk(lt, d, T), 1.25, 640, 820), mid_k, st("wirk") - 0.1)
    add(S.shot_doors, st("wirk") - 0.1, st("wirk") + 1.2)
    add(S.shot_key, st("wirk") + 1.2, st("wirk") + 1.95)
    a = st("wirk") + 1.95
    b = st("pol1") - 0.15
    seg = (b - a) / 4
    add(S.shot_chase, a, a + seg)
    add(S.shot_cockpit, a + seg, a + 2 * seg)
    add(S.shot_drone_top, a + 2 * seg, a + 3 * seg)
    add(S.shot_traffic_light, a + 3 * seg, b)
    add(S.shot_windshield, b, b + 0.8)
    add(S.shot_cop_pan, b + 0.8, st("pol2") - 0.1)
    add(S.shot_freeze, st("pol2") - 0.1, st("pol2") + 0.75)
    add(S.shot_breath, st("pol2") + 0.75, st("f1") - 0.1)
    # facts: (stamp, bg) per sub-shot; long ones get a second background (card stays settled)
    facts = [("thc", "faces", st("f1") - 0.1, wd("f1", "Milliliter")),
             ("thc", "cop", wd("f1", "Milliliter"), wd("f1", "Eine") - 0.05),
             ("wait", "car", wd("f1", "Eine") - 0.05, st("f2") - 0.1),
             ("fine", "faces", st("f2") - 0.1, wd("f2", "500") - 0.05 if False else wd("f2", "beim")),
             ("fine", "cop", wd("f2", "beim"), wd("f2", "zwei") - 0.05),
             ("points", "plain", wd("f2", "zwei") - 0.05, wd("f2", "und") - 0.05),
             ("ban", "car", wd("f2", "und") - 0.05, st("f3") - 0.1),
             ("crime", "cop", st("f3") - 0.1, wd("f3", "Straftat") - 0.6),
             ("crime", "faces", wd("f3", "Straftat") - 0.6, st("f4") - 0.1),
             ("mix", "plain", st("f4") - 0.1, wd("f4", "mindestens") - 0.1),
             ("mix", "faces", wd("f4", "mindestens") - 0.1, st("f5") - 0.1),
             ("zero", "car", st("f5") - 0.1, wd("f5", "null") - 0.2),
             ("zero", "plain", wd("f5", "null") - 0.2, st("kla3") - 0.25)]
    prev = None
    for key, bgk, x0, x1 in facts:
        fn = S.shot_fact(key, bgk)
        if key == prev:
            base = fn
            fn = (lambda b: (lambda lt, d, T: b(lt + 1.0, d, T)))(base)  # already stamped -> settled card
        add(fn, x0, x1)
        prev = key
    add(S.shot_roadside, st("kla3") - 0.25, st("raf3") - 0.05)
    add(S.shot_faces, st("raf3") - 0.05, st("bus") - 0.1)
    add(S.shot_bus, st("bus") - 0.1, st("cta") - 0.1)
    tl = [st("cta"), wd("cta", "Und"), wd("cta", "Ab")]
    add(lambda lt, d, T: S.shot_cta(lt, d, T, tl), st("cta") - 0.1, TOTAL)
    return sch


SCH = build_schedule()


def shot_at(T):
    cur = SCH[0]
    for s in SCH:
        if T >= s["a"]:
            cur = s
    return cur


# ------------------------------------------------------------------ lip sync envelopes
ENV = {}


def load_envs():
    for l in TL["lines"]:
        with wave.open(l["wav"]) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        hop = SR // FPS
        n = len(a) // hop
        rms = np.sqrt(np.mean(a[: n * hop].reshape(n, hop) ** 2, axis=1))
        rms = rms / (rms.max() + 1e-6)
        ENV[l["id"]] = rms


SPK = {"rafael": "rafael", "klaus": "klaus", "polizei": "polizei"}


def mouth(who, T):
    for l in TL["lines"]:
        if l["speaker"] == who and l["start"] <= T < l["start"] + l["dur"]:
            e = ENV[l["id"]]
            i = int((T - l["start"]) * FPS)
            if 0 <= i < len(e):
                return float(np.clip(e[i] * 1.5, 0, 1))
    return 0.0


# ------------------------------------------------------------------ captions
CAP_COL = {"erz": YELLOW, "rafael": TEAL, "klaus": MAGENTA, "polizei": (110, 180, 255)}
CAP_NAME = {"rafael": "RAFAEL", "klaus": "KLAUS", "polizei": "POLIZIST"}
NO_CAPS = {"hook1", "hook2", "cta", "bus", "wirk"}


def build_caps():
    caps = []
    for l in TL["lines"]:
        if l["id"] in NO_CAPS:
            continue
        words = [dict(text=w["text"], a=l["start"] + w["start"], b=l["start"] + w["end"]) for w in l["words"]]
        script_words = l["text"].replace(" –", ",").replace("…", "").split()
        chunk, j = [], 0
        for k, w in enumerate(words):
            if chunk and (len(chunk) >= 3 or sum(len(x["text"]) for x in chunk) + len(w["text"]) > 17):
                caps.append((l, chunk))
                chunk = []
            chunk.append(w)
            j += len(w["text"].split())
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
    f = font(F_INTER, 84)
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
        d.text((x, y), w["text"], font=f, fill=col, anchor="lm", stroke_width=11, stroke_fill=(0, 0, 0))
        x += ww + sp
    return im


def draw_caps(frame, T):
    for ci, c in enumerate(CAPS):
        if c["a"] <= T < c["b"]:
            act = max([i for i, w in enumerate(c["words"]) if T >= w["a"]] or [0])
            img = cap_img(ci, act)
            p = clamp01((T - c["a"]) / 0.12)
            sc = (0.8 + 0.2 * ease_out(p) + 0.05 * math.sin(p * math.pi)) * min(1.0, 1010 / img.width)
            paste_c(frame, img, W / 2, 1600, sc)
            return


# ------------------------------------------------------------------ frame
VIG = None


def init():
    global VIG
    load_envs()
    S.CTX["mouth"] = lambda who, T: mouth(who, T)
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
    out = bloom(f, 0.85).convert("RGBA")
    out.alpha_composite(VIG)
    # white flash on hard cut to the blue light
    if abs(T - st("hook2")) < 0.08:
        out.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 160)))
    draw_caps(out, T)
    return out.convert("RGB").tobytes()


# ------------------------------------------------------------------ audio
def env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)


def tone(f, dur, a=0.002, d=0.2, kind="sin"):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(f, (n,)) if np.ndim(f) else np.full(n, f)) / SR
    w = np.sin(ph) if kind == "sin" else (2 * ((ph / (2 * np.pi)) % 1) - 1)
    return w * env(n, a, d)


def noise(dur, rng):
    return rng.standard_normal(int(dur * SR))


def lowpass(x, alpha):
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += alpha * (x[i] - acc)
        y[i] = acc
    return y


def fx_whoosh(rng):
    n = int(0.38 * SR)
    x = noise(0.38, rng)
    u = np.linspace(0, 1, n)
    a = 0.03 + 0.3 * np.sin(np.pi * u) ** 2
    y = np.empty(n)
    acc = 0.0
    for i in range(n):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y * np.sin(np.pi * u) ** 1.4 * 1.6


def fx_boom(rng):
    n = int(0.8 * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * (40 + 90 * np.exp(-t * 12)) * t) * env(n, 0.002, 0.35) * 1.2
            + lowpass(noise(0.8, rng), 0.08) * env(n, 0.001, 0.2) * 1.5)


def fx_cheer(rng):
    n = int(1.6 * SR)
    x = lowpass(noise(1.6, rng), 0.25) - lowpass(noise(1.6, rng), 0.02)
    am = 1 + 0.4 * np.sin(np.arange(n) / SR * 2 * np.pi * 6)
    return x * am * env(n, 0.15, 0.9) * 1.8


def fx_siren(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = np.where((t * 2.2) % 1 < 0.5, 660, 880)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) + 0.3 * np.sin(2 * ph)) * 0.35


def fx_glitch(rng):
    n = int(0.18 * SR)
    x = np.sign(noise(0.18, rng)) * (np.random.default_rng(1).random(n) < 0.3)
    return x * 0.35 * env(n, 0.001, 0.08)


def fx_kaching():
    hi = np.zeros(int(0.5 * SR))
    t3 = tone(3136, 0.4, d=0.1)
    hi[:len(t3)] = t3
    return (tone(1567, 0.5, d=0.18) + tone(2093, 0.5, d=0.22) * 0.8 + hi * 0.4) * 0.5


def fx_lighter(rng):
    out = lowpass(noise(0.5, rng), 0.05) * env(int(0.5 * SR), 0.05, 0.3) * 1.5
    n = int(0.12 * SR)
    out[:n] += noise(0.12, rng) * env(n, 0.001, 0.02) * 0.6
    return out


def fx_beep(f=1800, dur=0.12):
    return tone(f, dur, d=1.0) * 0.35


def fx_alarm():
    n = int(0.75 * SR)
    t = np.arange(n) / SR
    w = np.sign(np.sin(2 * np.pi * 2600 * t)) * (np.sin(2 * np.pi * 14 * t) > 0)
    return w * 0.18


def fx_thud(rng):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * (55 + 70 * np.exp(-t * 30)) * t) * env(n, 0.001, 0.1) * 1.3 + noise(
        0.3, rng) * env(n, 0.0005, 0.015) * 0.5


def fx_engine(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 55 + 15 * np.sin(t * 1.3)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (2 * ((ph / (2 * np.pi)) % 1) - 1) * 0.12 * np.minimum(1, t / 0.3)


def fx_screech(rng):
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    f = 2400 + 300 * np.sin(2 * np.pi * 9 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * 0.4 + noise(0.9, rng) * 0.15) * env(n, 0.01, 0.5)


def fx_impact(rng):
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    boing = np.sin(2 * np.pi * (300 + 200 * np.sin(2 * np.pi * 12 * t)) * t) * env(n, 0.001, 0.25) * 0.5
    th = fx_thud(rng)
    boing[:len(th)] += th
    return boing


def fx_pop():
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(700 + 1200 * t / t[-1]) / SR) * env(n, 0.002, 0.03) * 0.7


def fx_chime():
    return (tone(988, 0.9, d=0.4) + tone(784, 0.9, d=0.5)[::1] * 0.0) * 0.4


def beat(total, stop_a, stop_b, bpm=124):
    rng = np.random.default_rng(5)
    n = int(total * SR) + SR
    out = np.zeros(n)
    beat_s = 60 / bpm
    kick_n = int(0.28 * SR)
    kt = np.arange(kick_n) / SR
    kick = np.sin(2 * np.pi * (45 + 110 * np.exp(-kt * 28)) * kt) * env(kick_n, 0.001, 0.14)
    clap = lowpass(rng.standard_normal(int(0.15 * SR)), 0.5) * env(int(0.15 * SR), 0.001, 0.05) * 0.6
    hat = np.diff(rng.standard_normal(int(0.035 * SR) + 1)) * env(int(0.035 * SR), 0.0005, 0.008) * 0.3
    bass_notes = [55.0, 55.0, 65.41, 49.0]  # A, A, C, G
    i = 0
    t = 0.0
    while t < total:
        s0 = int(t * SR)

        def put(sig, at, g=1.0):
            seg = sig[: max(0, n - at)]
            out[at:at + len(seg)] += seg * g
        put(kick, s0, 0.9)
        if i % 2 == 1:
            put(clap, s0, 0.8)
        for k in range(4):
            put(hat, s0 + int(k * beat_s / 4 * SR), 0.9 if k % 2 else 0.5)
        f = bass_notes[(i // 4) % 4]
        L = int(beat_s * SR)
        bt = np.arange(L) / SR
        bass = (np.sin(2 * np.pi * f * bt) + 0.5 * np.sin(4 * np.pi * f * bt) + 0.25 * np.sin(6 * np.pi * f * bt))
        bass *= np.minimum(1, bt / 0.01) * np.exp(-bt / 0.25) * 0.35
        put(bass, s0 + int(beat_s / 2 * SR) - L // 2 if i % 1 == 0 else s0)
        t += beat_s
        i += 1
    tt = np.arange(n) / SR
    gate = np.where((tt >= stop_a) & (tt < stop_b), 0.0, 1.0)
    return out * gate


def build_audio(path):
    rng = np.random.default_rng(7)
    n = int((TOTAL + 1) * SR)
    voice = np.zeros(n)
    for l in TL["lines"]:
        with wave.open(l["wav"]) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        i = int(l["start"] * SR)
        voice[i:i + len(a)] += a[: n - i] * 1.0
    sfx = np.zeros(n)

    def put(sig, T, g=1.0):
        i = int(max(0, T) * SR)
        seg = sig[: max(0, n - i)]
        sfx[i:i + len(seg)] += seg * g

    for s in SCH:
        if s["whoosh"]:
            put(fx_whoosh(rng), s["a"] - 0.15, 0.45)
    put(fx_boom(rng), 1.15, 0.9)
    put(fx_cheer(rng), 1.15, 0.6)
    put(fx_boom(rng), st("hook2"), 0.8)
    put(fx_siren(en("hook2") - st("hook2")), st("hook2"), 0.55)
    for x in (st("hook2"), st("hook2") + 0.45, st("hook2") + 1.45):
        put(fx_glitch(rng), x, 1.0)
    # party
    ka = st("kla1") + 0.05
    for k in range(2):
        put(fx_kaching(), ka + k * 0.7, 0.9)
    sp = st("kla1") + 1.55
    for k in range(2):
        put(fx_kaching(), sp + k * 0.8, 0.9)
    put(fx_lighter(rng), en("hook2") + 0.7 + 0.7, 0.8)
    # x-ray beeps
    t = st("night") + 1.7
    while t < st("raf2") - 0.8:
        put(fx_beep(1400, 0.1), t, 0.9)
        t += 0.45
    put(fx_alarm(), st("raf2") - 0.7, 1.0)
    put(fx_thud(rng), st("wirk") - 0.08, 1.0)
    put(fx_thud(rng), st("wirk") + 0.02, 0.9)
    put(fx_pop(), st("wirk") + 0.2, 0.8)
    put(fx_beep(900, 0.05), st("wirk") + 1.45, 0.8)
    put(fx_engine(st("pol1") - st("wirk") - 1.4), st("wirk") + 1.5, 1.0)
    seg = (st("pol1") - 0.15 - (st("wirk") + 1.95)) / 4
    put(fx_screech(rng), st("wirk") + 1.95 + 3 * seg + 0.45, 0.8)
    put(fx_siren(1.2), st("pol1") - 0.15, 0.4)
    put(fx_impact(rng), st("pol2") - 0.1, 0.9)
    put(fx_beep(2200, 0.6), st("pol2") + 0.75 + 0.9, 0.7)
    for s in SCH:
        if s["fn"].__qualname__.startswith("shot_fact") and False:
            pass
    for key_t in (st("f1") - 0.1, wd("f1", "Eine") - 0.05, st("f2") - 0.1, wd("f2", "zwei") - 0.05,
                  wd("f2", "und") - 0.05, st("f3") - 0.1, st("f4") - 0.1, st("f5") - 0.1):
        put(fx_thud(rng), key_t + 0.18, 1.0)
    put(fx_chime(), st("bus") - 0.05, 0.6)
    for x in (st("cta"), wd("cta", "Und"), wd("cta", "Ab")):
        put(fx_pop(), x, 0.9)
    music = beat(TOTAL, st("hook2"), en("hook2") + 0.05)
    # duck music under voice
    venv = np.abs(voice)
    k = int(0.15 * SR)
    venv = np.convolve(venv, np.ones(k) / k, mode="same")
    duck = 1 - np.clip(venv * 12, 0, 0.72)
    mix = voice * 1.0 + sfx * 0.55 + music[:n] * 0.27 * duck
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
