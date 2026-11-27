"""Synthesize the whole soundtrack from build/schlaf/events.json (numpy only).

Snoring synced to the pillow's breathing, music-box lullaby, hyperactive
squeaks, boings, ball pops, a 150 bpm chaos beat, a falling whistle, the
THUD of the iron block - and then total silence.
"""
import json
import math
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim  # noqa: E402

SR = 44100
N = int(sim.DUR * SR)
rng = np.random.default_rng(5)


def tt(d):
    return np.arange(int(d * SR)) / SR


def add(buf, t0, sig, gain=1.0):
    i = int(t0 * SR)
    if i >= len(buf) or i + len(sig) <= 0:
        return
    if i < 0:
        sig, i = sig[-i:], 0
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def lowpass(x, fc):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / fc) ** 4)
    return np.fft.irfft(X, len(x))


def bandpass(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / hi) ** 4) * (1 - 1 / (1 + (f / lo) ** 4))
    return np.fft.irfft(X, len(x))


def note(freq, d, decay=3.0, harm=(1, 0.35, 0.12)):
    t = tt(d)
    s = sum(a * np.sin(2 * np.pi * freq * (k + 1) * t) for k, a in enumerate(harm))
    env = np.exp(-t * decay) * np.minimum(1, t * 400)
    return s * env


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


def main():
    ev = json.loads((sim.BUILD / "events.json").read_text())
    split_t = next(e["t"] for e in ev if e["type"] == "split")
    thud_t = next(e["t"] for e in ev if e["type"] == "thud")
    whistle_t = next(e["t"] for e in ev if e["type"] == "whistle")

    mus = np.zeros(N)
    sfx = np.zeros(N)

    # ---------------- snoring (inhale = rumbling buzz, exhale = soft "pfff")
    t = np.arange(N) / SR
    ph = (t / 3.2) % 1.0
    inhale = np.clip(np.sin(np.pi * np.clip(ph / 0.55, 0, 1)), 0, 1) ** 1.5
    exhale = np.clip(np.sin(np.pi * np.clip((ph - 0.58) / 0.38, 0, 1)), 0, 1) ** 2 * (ph > 0.58)
    f0 = 62 + 10 * inhale
    saw = 2 * ((np.cumsum(f0) / SR) % 1.0) - 1
    noise = rng.normal(0, 1, N)
    buzz = lowpass(saw * (0.6 + 0.4 * noise * 0.3), 420) * inhale
    pff = bandpass(noise, 900, 3200) * exhale * 0.35
    snore = (buzz * 0.9 + pff)
    fade = np.clip((split_t - 0.15 - t) / 0.3, 0, 1)
    sfx += snore * fade * 0.55

    # ---------------- music box lullaby until the split
    bpm = 84
    beat = 60 / bpm
    prog = [[60, 64, 67, 72], [57, 60, 64, 69], [53, 57, 60, 65], [55, 59, 62, 67]]
    k = 0
    tb = 0.0
    while tb < split_t:
        ch = prog[(k // 8) % 4]
        m = ch[[0, 1, 2, 3, 2, 1, 2, 3][k % 8]] + 12
        add(mus, tb, note(midi(m), 1.4, decay=3.2, harm=(1, 0.25, 0.08, 0.05)), 0.16)
        k += 1
        tb += beat / 2
    mus *= np.clip((split_t - t) / 0.08, 0, 1)

    # ---------------- hyperactive squeaks of the rubber word while hovering
    tq = sim.T_WORD_IN
    while tq < sim.T_DROP:
        d = rng.uniform(0.05, 0.09)
        x = tt(d)
        f = rng.uniform(1400, 2400) * (1 + 0.6 * x / d)
        sq = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * x / d)
        add(sfx, tq, sq, 0.10)
        tq += rng.uniform(0.18, 0.45)
    # pop-in
    x = tt(0.18)
    add(sfx, sim.T_WORD_IN, np.sin(2 * np.pi * np.cumsum(300 + 1800 * x / 0.18) / SR) * np.exp(-x * 14), 0.3)

    # ---------------- events
    pops = [e for e in ev if e["type"] == "pop"]
    last = -1
    for e in ev:
        if e["type"] == "boing":
            x = tt(0.7)
            f = 150 + 380 * (1 - np.exp(-x * 9)) + 40 * np.sin(2 * np.pi * 28 * x) * np.exp(-x * 4)
            f *= 1 + 0.12 * e["n"]
            s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 5)
            s += 0.5 * np.sin(2 * np.pi * 60 * x) * np.exp(-x * 18)
            add(sfx, e["t"], s, 0.55)
        elif e["type"] == "split":
            x = tt(0.5)
            burst = rng.normal(0, 1, len(x)) * np.exp(-x * 14)
            add(sfx, e["t"], burst * 0.5 + np.sin(2 * np.pi * 70 * x) * np.exp(-x * 9), 0.7)
            for j in range(14):  # sparkle
                add(sfx, e["t"] + j * 0.025, note(rng.uniform(1500, 3800), 0.25, decay=18, harm=(1,)), 0.12)
    # ball pops: throttle density, louder for harder hits
    for e in pops:
        if e["t"] - last < 0.035:
            continue
        last = e["t"]
        v = min(1.0, e["v"] / 2600)
        if v < 0.12:
            continue
        x = tt(0.09)
        f0 = 520 + (e["i"] * 37 % 12) * 70
        f = f0 * (1.6 - 0.6 * x / 0.09)
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 45)
        s[:60] += rng.normal(0, 0.5, 60)
        add(sfx, e["t"], s, 0.26 * v ** 0.8)

    # ---------------- chaos beat 150 bpm (split -> block)
    bpm = 150
    b = 60 / bpm
    end = whistle_t - 0.3
    kick = (lambda x: np.sin(2 * np.pi * np.cumsum(50 + 110 * np.exp(-x * 30)) / SR) * np.exp(-x * 7))(tt(0.35))
    clap = (lambda x: bandpass(rng.normal(0, 1, len(x)), 900, 5000) * np.exp(-x * 22))(tt(0.25))
    hat = (lambda x: bandpass(rng.normal(0, 1, len(x)), 6000, 14000) * np.exp(-x * 70))(tt(0.08))
    bass_notes = [36, 36, 48, 36, 39, 39, 51, 39, 41, 41, 53, 41, 43, 43, 55, 46]
    lead = [72, 75, 79, 84, 79, 75, 72, 75, 74, 77, 81, 86, 81, 77, 74, 79]
    n = 0
    tb = split_t + 0.05
    while tb < end:
        step = n % 16
        if step % 4 == 0:
            add(mus, tb, kick, 0.55)
        if step % 8 == 4:
            add(mus, tb, clap, 0.22)
        add(mus, tb, hat, 0.07 if step % 2 else 0.04)
        x = tt(b / 2 * 0.95)
        bf = midi(bass_notes[(n // 2) % 16])
        sq = np.sign(np.sin(2 * np.pi * bf * x)) * np.exp(-x * 5)
        add(mus, tb, lowpass(sq, 900) if False else sq, 0.07)
        if tb > split_t + 1.5:
            add(mus, tb, note(midi(lead[n % 16]), 0.25, decay=14, harm=(1, 0.5, 0.3, 0.2)), 0.07)
        n += 1
        tb += b / 4
    # riser into the block
    x = tt(2.0)
    riser = bandpass(rng.normal(0, 1, len(x)), 1500, 9000) * (x / 2.0) ** 2
    add(mus, end - 2.0, riser, 0.25)
    mus[int(end * SR):] = 0

    # ---------------- falling whistle + THUD, then silence
    d = thud_t - whistle_t
    x = tt(d)
    f = 2200 - 1500 * (x / d) ** 1.3
    add(sfx, whistle_t, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, x * 20), 0.22)
    x = tt(2.2)
    thud = np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-x * 12)) / SR) * np.exp(-x * 2.2)
    thud += lowpass(rng.normal(0, 1, len(x)), 600) * np.exp(-x * 6) * 2.5
    thud += np.sin(2 * np.pi * 820 * x) * np.exp(-x * 9) * 0.25 * (1 + 0.5 * np.sin(2 * np.pi * 7 * x))
    add(sfx, thud_t, thud, 1.0)
    sfx[int((thud_t + 2.2) * SR):] = 0

    mix = mus + sfx
    mix = np.tanh(mix * 1.6) / np.tanh(1.6)
    mix *= 0.85 / np.abs(mix).max()
    st = np.repeat((mix * 32767).astype(np.int16)[:, None], 2, axis=1)
    out = sim.BUILD / "audio.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(st.tobytes())
    print("audio ->", out)


if __name__ == "__main__":
    main()
