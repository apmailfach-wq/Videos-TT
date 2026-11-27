"""Synthesised sound effects, placed on the physics events (no music: add a trending sound in TikTok)."""
import math
import random
import wave

import numpy as np

SR = 44100


def env(n, attack=0.004, decay=8.0):
    t = np.arange(n) / SR
    a = np.clip(t / attack, 0, 1)
    return a * np.exp(-t * decay)


def tone(freq0, freq1, dur, decay=8.0, kind="sine"):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = freq0 * (freq1 / freq0) ** (t / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    w = np.sin(ph) if kind == "sine" else np.sign(np.sin(ph)) * 0.5 + np.sin(ph) * 0.5
    return w * env(n, decay=decay)


def noise(dur, decay=30.0, seed=0):
    n = int(dur * SR)
    r = np.random.default_rng(seed).uniform(-1, 1, n)
    return r * env(n, decay=decay)


def lay(*sigs):
    n = max(len(x) for x in sigs)
    out = np.zeros(n)
    for x in sigs:
        out[:len(x)] += x
    return out


def s_bounce(e):
    return 0.25 * e * lay(tone(520, 300, 0.07, 40), 0.3 * noise(0.02, 120))


def s_peg(i):
    f = 900 + (i % 5) * 110
    return 0.22 * tone(f, f * 0.98, 0.09, 35)


def s_hit(cost, seed):
    k = min(1.0, abs(cost) / 25000)
    base = tone(240 - 90 * k, 70, 0.25 + 0.25 * k, 7 - 3 * k, "square") * (0.45 + 0.35 * k)
    thud = noise(0.08, 45, seed) * 0.35
    # "money leaving" descending blips
    n = len(base)
    out = np.zeros(n + int(0.35 * SR))
    out[:n] += base
    out[:len(thud)] += thud
    for j in range(3):
        b = tone(880 - j * 180, 700 - j * 180, 0.08, 30) * 0.18
        o = int((0.08 + j * 0.07) * SR)
        out[o:o + len(b)] += b
    return out


def s_gain():
    out = np.zeros(int(0.7 * SR))
    for j, f in enumerate((1318.5, 1760.0, 2637.0)):
        b = tone(f, f, 0.5, 6) * 0.25
        o = int(j * 0.06 * SR)
        out[o:o + len(b)] += b
    out[:int(0.25 * SR)] += noise(0.25, 14, 3) * 0.08
    return out


def s_fanfare():
    notes = [523.25, 659.25, 783.99, 1046.5, 783.99, 1046.5]
    times = [0, 0.12, 0.24, 0.36, 0.6, 0.72]
    out = np.zeros(int(2.2 * SR))
    for f, t0 in zip(notes, times):
        dur = 0.9 if t0 >= 0.7 else 0.3
        b = (tone(f, f, dur, 3.5, "square") * 0.18 + tone(f * 2, f * 2, dur, 5) * 0.08)
        o = int(t0 * SR)
        out[o:o + len(b)] += b
    return out


def s_whoosh():
    n = int(0.5 * SR)
    r = np.random.default_rng(9).uniform(-1, 1, n)
    k = np.exp(-((np.arange(n) / SR - 0.25) ** 2) / 0.01)
    # crude low-pass
    r = np.convolve(r, np.ones(30) / 30, mode="same")
    return r * k * 0.6


def s_drum_roll(dur):
    out = np.zeros(int(dur * SR))
    t = 0.0
    i = 0
    while t < dur:
        b = noise(0.05, 60, i) * (0.08 + 0.12 * t / dur)
        o = int(t * SR)
        out[o:o + len(b)] += b[:len(out) - o]
        t += 0.055
        i += 1
    return out


def build(run, path, fps):
    total = run.n / fps + 0.5
    mix = np.zeros(int(total * SR) + SR)

    def add(sig, at):
        o = int(at * SR)
        if o >= len(mix):
            return
        e = min(len(mix), o + len(sig))
        mix[o:e] += sig[:e - o]

    add(s_whoosh(), 0.0)
    last_bounce = -1
    for f, typ, p in run.events:
        at = f / fps
        if typ == "bounce":
            if f - last_bounce > 4:
                add(s_bounce(p["e"]), at)
                last_bounce = f
        elif typ == "hit":
            if p["key"] == "tax":
                add(s_peg(f), at)
                add(s_hit(p["cost"], f) * 0.35, at)
            elif p["cost"] > 0:
                add(s_gain(), at)
            else:
                add(s_hit(p["cost"], f), at)
        elif typ == "pocket":
            add(s_fanfare(), at + 0.05)
    # drum roll during slow motion
    slow = [i for i, fr in enumerate(run.frames) if fr["slow"]]
    if slow:
        add(s_drum_roll((slow[-1] - slow[0]) / fps), slow[0] / fps)
    # ending stamps
    land = run.land / fps
    for dt in (0.3, 1.1, 2.8, 4.2):
        add(lay(tone(180, 60, 0.25, 12) * 0.5, noise(0.05, 60, 5) * 0.3), land + dt)
    peak = np.max(np.abs(mix)) or 1
    mix = np.tanh(mix / peak * 1.6) * 0.9
    data = (mix * 32767).astype(np.int16)
    st = np.repeat(data[:, None], 2, axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())
