"""Tonspur: Sprecher + leise Hintergrundmusik + Klick je Zahlung, Ping je Push-Nachricht,
Münz-/Schein-Geräusche für BAR, kleine Akzente für Einblendungen -> build/bezahlen/mix.wav"""
import math
import wave
import numpy as np

from timeline import AUDIO_START, ATM_T, BUILD, DURATION, EVENTS, TIM, at

SR = 48000
N = int(DURATION * SR)
rng = np.random.default_rng(7)


def env(n, a=0.005, r=0.1):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / r)


def tone(f, dur, a=0.005, r=0.1, harm=((1, 1),)):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = sum(g * np.sin(2 * np.pi * f * h * t) for h, g in harm)
    return y * env(n, a, r)


def noise(dur, r=0.03, hp=True):
    n = int(dur * SR)
    y = rng.standard_normal(n)
    if hp:
        y = np.diff(y, prepend=0)
    return y * env(n, 0.001, r)


def mixs(*sigs):
    n = max(len(x) for x in sigs)
    out = np.zeros(n)
    for x in sigs:
        out[:len(x)] += x
    return out


def add(buf, sig, t, gain):
    i = int(t * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[:j - i] * gain


# ---------------- Effekte
CLICK = mixs(noise(0.03, 0.004) * 0.6, tone(2600, 0.05, 0.001, 0.012) * 0.5)
TAP = mixs(tone(1800, 0.06, 0.001, 0.015) * 0.5, noise(0.02, 0.003) * 0.4)
PING = mixs(tone(1318.5, 0.6, 0.002, 0.18, ((1, 1), (2, 0.25))), 0.7 * np.concatenate(
    [np.zeros(int(0.09 * SR)), tone(1975.5, 0.5, 0.002, 0.16, ((1, 1), (2, 0.2)))]))
COIN = sum(tone(f, 0.35, 0.001, 0.07) * g for f, g in ((3950, 0.5), (5270, 0.35), (6620, 0.25)))
RUSTLE = noise(0.22, 0.08) * 0.35
WHOOSH_N = int(0.35 * SR)
_w = rng.standard_normal(WHOOSH_N)
_w = np.convolve(_w, np.ones(30) / 30, "same")
WHOOSH = _w * np.sin(np.linspace(0, np.pi, WHOOSH_N)) ** 2 * 2.5
THUD = mixs(tone(90, 0.4, 0.002, 0.12, ((1, 1), (2, 0.4))) * 1.2, noise(0.05, 0.01) * 0.3)
DING = tone(880, 0.6, 0.002, 0.25, ((1, 1), (2, 0.3), (3, 0.1)))


def music():
    """Ruhiger Pad + weiche Zupf-Arpeggios, 96 BPM, Am – F – C – G."""
    t = np.arange(N) / SR
    beat = 60 / 96
    bar = beat * 4
    chords = [(57, 60, 64), (53, 57, 60), (48, 55, 64), (55, 59, 62)]
    y = np.zeros(N)
    midi = lambda m: 440 * 2 ** ((m - 69) / 12)
    nb = int(DURATION / bar) + 1
    for b in range(nb):
        ch = chords[b % 4]
        i0, i1 = int(b * bar * SR), min(N, int((b + 1) * bar * SR) + int(0.3 * SR))
        if i0 >= N:
            break
        tt = np.arange(i1 - i0) / SR
        e = np.minimum(1, tt / 0.6) * np.minimum(1, np.maximum(0, (bar + 0.3 - tt) / 0.5))
        for m in ch:
            f = midi(m - 12)
            y[i0:i1] += 0.10 * e * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.003 * tt))
        y[i0:i1] += 0.12 * e * np.sin(2 * np.pi * midi(ch[0] - 24) * tt)
        for k in range(8):  # Achtel-Arpeggio
            m = ch[[0, 1, 2, 1][k % 4]] + (12 if k % 4 == 2 else 0)
            add(y, tone(midi(m), 0.5, 0.004, 0.16, ((1, 1), (2, 0.15))) * 0.07, b * bar + k * beat / 2, 1)
        for k in range(4):  # leiser Hi-Hat-Hauch
            add(y, noise(0.05, 0.01) * 0.04, b * bar + k * beat + beat / 2, 1)
    return y


def main():
    voice = np.zeros(N)
    for st, tim in zip(AUDIO_START, TIM):
        add(voice, np.load(tim["audio"]), st, 1.0)

    mus = music()
    # Ducking unter der Stimme
    e = np.abs(voice)
    k = int(0.15 * SR)
    e = np.convolve(e, np.ones(k) / k, "same")
    duck = 1 - 0.55 * np.clip(e / 0.05, 0, 1)
    fade = np.minimum(1, np.arange(N) / (1.0 * SR)) * np.minimum(1, (N - np.arange(N)) / (1.5 * SR))
    mus = mus * duck * fade * 0.16

    fx = np.zeros(N)
    for ev in EVENTS:
        if ev["skip"]:
            continue
        if ev["pay"] == "card":
            add(fx, CLICK, ev["t"], 0.32)
        elif ev["pay"] == "phone":
            add(fx, TAP, ev["t"], 0.32)
        elif ev["pay"] == "bills":
            add(fx, RUSTLE, ev["t"], 0.5)
            add(fx, CLICK, ev["t"] + 0.6, 0.25)
        elif ev["pay"] == "coin":
            add(fx, COIN, ev["t"], 0.22)
        if ev["push"]:
            add(fx, PING, ev["t"] + 0.05, 0.22)
    # Geldautomat
    for k in range(4):
        add(fx, RUSTLE, ATM_T[0] + 0.35 + k * 0.12, 0.5)
    # Akzente
    for tt in (3.0, 5.5, 8.0, at("falsch", "Ist") - 0.1, 22.0, 30.0, 38.0, 43.9, 49.9, 55.9):
        add(fx, WHOOSH, tt, 0.18)
    add(fx, THUD, 0.0, 0.5)                                   # Hook-Einschlag
    add(fx, THUD, at("falsch", "Noch") - 0.05, 0.6)
    t_first = at("endstand", "Mit") - 0.1
    for i in range(3):
        add(fx, DING, t_first + i * 0.45, 0.18 * (1 + 0.3 * (i == 0)))
    add(fx, THUD, at("endstand", "meisten") - 0.15, 0.55)
    for k in range(10):                                       # Zähler 39 -> 468 €
        add(fx, COIN, at("endstand", "Aufs") + 0.4 + k * 0.09, 0.12)
    add(fx, DING * 0.8, 43.6, 0.25)
    add(fx, DING, at("schmerz", "Tipp") - 0.1, 0.16)
    t_click = at("ende", "abonnier") + 0.1
    add(fx, CLICK, t_click, 0.6)
    add(fx, PING, t_click + 0.08, 0.25)

    mix = voice * 1.0 + mus + fx
    mix = np.tanh(mix * 1.1) / 1.1   # weicher Limiter
    peak = np.max(np.abs(mix))
    mix = mix / max(peak, 1e-6) * 0.89
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(BUILD / "mix.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("mix.wav", round(N / SR, 2), "s, peak", round(float(peak), 3))


if __name__ == "__main__":
    main()
