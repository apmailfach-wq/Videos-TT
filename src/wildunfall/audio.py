"""Sound design for Folge 3: voice + calm suspense score + synthesized foley, stereo."""
import math
import wave

import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000


def tv(d):
    return np.arange(int(d * SR)) / SR


def lp(x, f, o=2):
    return sosfilt(butter(o, f, "low", fs=SR, output="sos"), x)


def hp(x, f, o=2):
    return sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)


def bp(x, a, b, o=2):
    return sosfilt(butter(o, [a, b], "band", fs=SR, output="sos"), x)


def saw_f(freq, n, ph=0.0):
    return 2 * ((np.cumsum(np.broadcast_to(freq, (n,))) / SR + ph) % 1) - 1


def env(n, a, r):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.minimum(1, (n / SR - t) / max(r, 1e-4))


# ------------------------------------------------------------------ foley
def hit(rng, g=1.0, d=0.8):
    t = tv(d)
    b = np.sin(2 * np.pi * (42 + 90 * np.exp(-t * 22)) * t) * np.exp(-t * 5)
    return (b + lp(rng.standard_normal(len(t)), 1500) * np.exp(-t * 20) * 0.6) * g


def whoosh(rng, d=0.45):
    t = tv(d)
    return bp(rng.standard_normal(len(t)), 300, 3000) * np.sin(np.pi * t / d) ** 2 * 0.8


def sting(rng):
    d = 2.2
    t = tv(d)
    x = np.zeros_like(t)
    for f in (220, 233.1, 329.6, 440, 466.2):
        x += saw_f(f * (1 + 0.002 * rng.standard_normal()), len(t), rng.random())
    x = lp(x, 2400) / 5 * np.exp(-t * 1.4) * np.minimum(1, t / 0.01)
    return x + hit(rng, 1.2, d)


def screech(rng, d, f0=1150):
    t = tv(d)
    f = f0 + 140 * np.sin(2 * np.pi * 5.3 * t) + 60 * rng.standard_normal(len(t)).cumsum() / SR * 30
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    n = bp(rng.standard_normal(len(t)), 900, 4500)
    return (tone * 0.35 + n * 0.5) * env(len(t), 0.05, 0.15)


def abs_brake(rng, d):
    t = tv(d)
    am = 0.55 + 0.45 * np.sign(np.sin(2 * np.pi * 14 * t))
    f = 1300 - 500 * t / d
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25
    n = bp(rng.standard_normal(len(t)), 600, 3200) * 0.45
    fade = np.minimum(1, (d - t) / 0.3) * np.minimum(1, t / 0.05) * (1 - 0.6 * t / d)
    return (tone + n) * am * fade


def crash(rng):
    d = 2.2
    t = tv(d)
    n = hp(rng.standard_normal(len(t)), 600) * np.exp(-t * 4)
    ring = sum(np.sin(2 * np.pi * f * t + rng.random() * 6) * np.exp(-t * (3 + k)) for k, f in
               enumerate((410, 690, 1130, 1780, 2470)))
    crunch = np.zeros_like(t)
    for _ in range(40):
        s = int(rng.uniform(0, 0.5) * SR)
        L = int(rng.uniform(0.005, 0.03) * SR)
        crunch[s:s + L] += rng.standard_normal(L) * rng.uniform(0.3, 1)
    return n * 0.9 + ring * 0.15 + hp(crunch, 1500) * 0.6 + hit(rng, 1.6, d)


def glass(rng, d=1.2):
    out = np.zeros(int(d * SR))
    for _ in range(70):
        s = int((rng.uniform(0, 1) ** 2) * d * 0.7 * SR)
        dd = rng.uniform(0.04, 0.2)
        tt = tv(dd)
        b = np.sin(2 * np.pi * rng.uniform(2500, 7500) * tt) * np.exp(-tt / dd * 4) * rng.uniform(0.1, 0.35)
        out[s:s + len(b)] += b[: len(out) - s]
    return out


def leaves(rng, d=1.5, dens=1.0):
    t = tv(d)
    n = bp(rng.standard_normal(len(t)), 1500, 7000)
    am = np.abs(lp(rng.standard_normal(len(t)), 25)) * 4 * dens
    return n * np.clip(am, 0, 1) * env(len(t), 0.05, 0.4) * 0.6


def tinnitus(d=2.0):
    t = tv(d)
    return np.sin(2 * np.pi * 3900 * t) * np.exp(-t * 1.6) * 0.06


def tape_rewind(rng, d):
    t = tv(d)
    f = 300 + 2400 * (t / d) ** 1.4 + 80 * np.sin(2 * np.pi * 21 * t)
    s = lp(saw_f(f, len(t)), 3500) * 0.45 + bp(rng.standard_normal(len(t)), 2500, 9000) * 0.25
    return s * env(len(t), 0.05, 0.1)


def horn(d=0.5):
    t = tv(d)
    x = np.sign(np.sin(2 * np.pi * 415 * t)) + np.sign(np.sin(2 * np.pi * 523 * t))
    return lp(x, 2200) * 0.35 * env(len(t), 0.01, 0.04)


def click(f=2500):
    t = tv(0.04)
    return np.sin(2 * np.pi * f * t) * np.exp(-t * 180)


def relay(hi=True):
    t = tv(0.05)
    return (np.sin(2 * np.pi * (1900 if hi else 1500) * t) + 0.6 * np.sin(2 * np.pi * 700 * t)) * np.exp(-t * 140) * 0.6


def step(rng):
    t = tv(0.12)
    return bp(rng.standard_normal(len(t)), 300, 4000) * np.exp(-t * 35) * 0.6


def thump(rng):
    t = tv(0.2)
    return np.sin(2 * np.pi * (70 + 60 * np.exp(-t * 30)) * t) * np.exp(-t * 18) + step(rng)[: len(t)] * 0.3 if False else \
        np.sin(2 * np.pi * (70 + 60 * np.exp(-t * 30)) * t) * np.exp(-t * 18)


def dtmf(a, b, d=0.16):
    t = tv(d)
    return (np.sin(2 * np.pi * a * t) + np.sin(2 * np.pi * b * t)) * 0.25 * env(len(t), 0.005, 0.01)


def ui_pop(f=620):
    t = tv(0.14)
    return np.sin(2 * np.pi * (f + 500 * t / 0.14) * t) * np.exp(-t * 28) * 0.5


def owl(rng):
    out = []
    for d, f in ((0.35, 380), (0.15, 0), (0.6, 372)):
        t = tv(d)
        if f == 0:
            out.append(np.zeros_like(t))
            continue
        fm = f * (1 - 0.06 * t / d) + 6 * np.sin(2 * np.pi * 6 * t)
        out.append(np.sin(2 * np.pi * np.cumsum(fm) / SR) * np.sin(np.pi * t / d) ** 2)
    return np.concatenate(out) * 0.35


# ------------------------------------------------------------------ music
def score(total, rng, R):
    n = int(total * SR)
    t = np.arange(n) / SR
    out = np.zeros((2, n))

    def pad(freqs, a, b, g, cutoff=900):
        i0, i1 = int(a * SR), int(b * SR)
        m = i1 - i0
        x = np.zeros((2, m))
        for f in freqs:
            for ch, det in ((0, -0.7), (1, 0.7)):
                x[ch] += saw_f(f + det, m, rng.random())
        for ch in (0, 1):
            x[ch] = lp(x[ch], cutoff) / len(freqs) * env(m, 0.8, 0.8) * g
        out[:, i0:i1] += x

    am = (110, 130.81, 164.81)
    pad(am + (55,), 0.0, R.T_IMPACT + 0.2, 0.55)
    pad((110, 116.54, 164.81), 3.4, 9.0, 0.35, 1400)  # dissonant swell at the deer
    pad(am + (55,), R.B_START - 0.3, R.W_("mehr", "springt"), 0.5)
    pad((110, 138.59, 164.81, 220), R.W_("mehr", "springt"), R.ST("frage"), 0.45, 1300)  # relief: A major
    pad((110, 130.81, 164.81, 196), R.ST("frage") - 0.2, total, 0.4, 1000)
    # soft heartbeat-like pulse
    for a, b, step_ in ((0.0, 3.4, 0.82), (3.4, 8.9, 0.6), (10.4, 13.2, 0.42), (R.B_START, R.T_STOP, 0.6)):
        p = a
        while p < b:
            h = np.sin(2 * np.pi * (55 + 30 * np.exp(-tv(0.3) * 25)) * tv(0.3)) * np.exp(-tv(0.3) * 14) * 0.5
            i = int(p * SR)
            out[:, i:i + len(h)] += h[: n - i]
            p += step_
    # high shimmer
    sh = np.sin(2 * np.pi * 1318.5 * t) * 0.012 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t))
    out += sh
    return out


# ------------------------------------------------------------------ build
def reverb(x, seconds=1.4, seed=0):
    r = np.random.default_rng(31 + seed)
    m = int(seconds * SR)
    tt = np.arange(m) / SR
    ir = lp(r.standard_normal(m) * np.exp(-tt * 4.2), 6000)
    ir[0] = 0
    return fftconvolve(x, ir)[: len(x)] * 0.05


def build(path, R):
    rng = np.random.default_rng(5)
    total = R.TOTAL
    n = int(total * SR)
    t = np.arange(n) / SR
    voice = np.zeros(n)
    for l in R.VOICE["lines"]:
        with wave.open(l["wav"]) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32768
        i = int(l["start"] * SR)
        voice[i:i + len(a)] += a[: n - i]
    voice = hp(voice, 90)
    sfx = np.zeros((2, n))

    def put(sig, T, g=1.0, pan=0.0):
        i = int(max(0, T) * SR)
        seg = sig[: max(0, n - i)] * g
        sfx[0, i:i + len(seg)] += seg * math.sqrt(0.5 * (1 - pan))
        sfx[1, i:i + len(seg)] += seg * math.sqrt(0.5 * (1 + pan))

    # engine + tyres follow the simulated car speed
    blk = int(0.01 * SR)
    sp = np.zeros(n)
    on = np.ones(n)
    prev = None
    for i in range(0, n, blk):
        T = i / SR
        c = R.car_state(T)
        if prev is not None:
            v = math.hypot(c["x"] - prev[0], c["y"] - prev[1]) / 0.01
        else:
            v = 650
        if R.T_RW0 <= T < R.T_RW1:
            v = 0
        sp[i:i + blk] = min(v, 1200)
        if c["run"] == "A" and c["ta"] > R.T_IMPACT:
            on[i:i + blk] = 0
        if c["run"] == "B" and T > R.ST("merk"):
            on[i:i + blk] = 0.5
        prev = (c["x"], c["y"])
    sp = lp(sp, 3)
    f = 34 + sp * 0.07
    eng = (saw_f(f, n) * 0.5 + saw_f(f * 2.01, n) * 0.25 + np.sin(2 * np.pi * np.cumsum(f * 0.5) / SR) * 0.6)
    eng = lp(eng, 380) * (0.10 + 0.22 * np.clip(sp / 650, 0, 1)) * lp(on, 5)
    tyre = lp(bp(rng.standard_normal(n), 120, 1400), 1600) * 0.07 * np.clip(sp / 650, 0, 1.4)
    for ch in (0, 1):
        sfx[ch] += eng + tyre
    # night ambience
    wind = lp(rng.standard_normal(n), 420) * 0.05 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t))
    sfx[0] += wind
    sfx[1] += np.roll(wind, 2400)
    put(owl(rng), 0.9, 0.5, -0.6)
    put(owl(rng), R.ST("knallt") + 0.6, 0.35, 0.6)
    put(owl(rng), R.ST("frage") + 1.6, 0.45, -0.5)

    W_ = R.W_
    # A run
    put(leaves(rng, 0.9, 1.2), 2.55, 0.6, -0.6)
    put(sting(rng), W_("reh", "Reh"), 0.9)
    put(whoosh(rng, 0.6), W_("reh", "Reh") - 0.45, 0.5)
    put(screech(rng, 1.4), 7.45, 0.7, -0.2)
    put(hit(rng, 0.9), 8.9, 0.8)
    put(whoosh(rng, 0.5), 10.1, 0.5)
    put(screech(rng, 2.7, 1000), 10.5, 0.9, 0.2)
    put(crash(rng), R.T_IMPACT, 1.0, 0.25)
    put(glass(rng, 1.2), R.T_IMPACT + 0.02, 0.5, 0.3)
    put(leaves(rng, 2.0, 1.5), R.T_IMPACT + 0.1, 0.8, 0.3)
    put(tinnitus(1.7), R.T_IMPACT + 0.2, 1.0)
    put(tape_rewind(rng, R.T_RW1 - R.T_RW0), R.T_RW0, 0.8)
    put(hit(rng, 0.7), R.T_RW1, 0.6)
    # B run
    put(leaves(rng, 0.9, 1.2), R.B_START, 0.5, -0.6)
    put(ui_pop(), W_("fest", "Lenkrad"), 0.6)
    put(abs_brake(rng, R.T_STOP - R.T_BRAKE + 0.1), R.T_BRAKE, 0.75)
    put(ui_pop(700), W_("bremse", "Voll"), 0.6)
    put(horn(0.45), W_("bremse", "Hupen") + 0.02, 0.9)
    put(horn(0.7), W_("bremse", "Hupen") + 0.6, 0.9)
    put(ui_pop(760), W_("bremse", "Hupen"), 0.4)
    put(click(1800), W_("bremse", "abblenden"), 1.0)
    put(ui_pop(820), W_("bremse", "Und"), 0.5)
    tj = W_("mehr", "springt")
    for k in range(3):
        put(thump(rng), tj + k * 0.3, 0.6, 0.3 + k * 0.2)
    put(leaves(rng, 1.0), tj + 0.6, 0.6, 0.8)
    put(sting(rng) * 0.6, W_("mehr", "Oft"), 0.6)
    for k in range(8):
        put(thump(rng), W_("mehr", "Oft") + k * 0.22, 0.45, -0.6 + k * 0.17)
    put(leaves(rng, 1.4), W_("mehr", "Oft") + 1.0, 0.6, 0.8)
    put(ui_pop(600), W_("knallt", "Reh"), 0.6, -0.3)
    put(ui_pop(500), W_("knallt", "Baum"), 0.6, 0.3)
    th = W_("danach", "Warnblinker")
    k = 0
    p = th
    while p < R.ST("merk") + 1.0:
        put(relay(k % 2 == 0), p, 0.5)
        p += 0.36
        k += 1
    put(click(1200), W_("danach", "Warnweste") - 0.25, 0.8, -0.3)
    p = W_("danach", "Warnweste")
    while p < W_("danach", "Polizei"):
        put(step(rng), p, 0.6, -0.2)
        p += 0.31
    put(click(900) + 0, W_("danach", "Warndreieck") + 0.05, 1.0)
    for i, (a, b) in enumerate(((1209, 697), (1209, 697), (941, 1336))):
        put(dtmf(a, b), W_("danach", "Polizei") + 0.15 + i * 0.22, 0.7)
    for w in ("Nicht", "Festhalten", "Bremsen"):
        put(ui_pop(640), W_("merk", w), 0.6)
        put(whoosh(rng, 0.3), W_("merk", w) - 0.12, 0.35)
    put(hit(rng, 0.7), R.ST("frage"), 0.7)
    put(ui_pop(900), W_("frage", "Wärst"), 0.5)

    mus = score(total, rng, R)
    # duck under voice
    k = int(0.18 * SR)
    venv = np.convolve(np.abs(voice), np.ones(k) / k, mode="same")
    duck = 1 - np.clip(venv * 9, 0, 0.6)
    wet = np.stack([reverb(sfx[0], seed=0), reverb(sfx[1], seed=1)])
    mix = sfx * 0.7 + wet + mus * 0.45 * duck
    # freeze moment: muffle the world
    fr = ((t >= 8.9) & (t < 10.45)).astype(float)
    fr = np.convolve(fr, np.ones(2400) / 2400, mode="same")
    for ch in (0, 1):
        mix[ch] = mix[ch] * (1 - fr) + lp(mix[ch], 500) * fr
    mix = mix + voice[None, :] * 1.15
    fade = np.minimum(1, (n - np.arange(n)) / (0.25 * SR))
    mix *= fade
    mix = np.tanh(mix / np.percentile(np.abs(mix), 99.9) * 0.9) * 0.95
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix.T * 32000).astype(np.int16).tobytes())
