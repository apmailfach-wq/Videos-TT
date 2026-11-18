"""Tonspur: Sprecher + leise Hintergrundmusik + weicher Marimba-Ton je Zahlung, Doppelton je Push-Nachricht,
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


# ---------------- Effekte (bewusst ohne hohe Pieptöne)
def lowpass(y, k):
    """Einfacher Tiefpass (gleitender Mittelwert) – macht Geräusche dumpf und weich."""
    return np.convolve(y, np.ones(k) / k, "same")


def soft_tick(dur=0.035, k=10, r=0.008):
    return lowpass(noise(dur, r, hp=False), k) * 3.0


TICK = soft_tick()                                   # Karte: leises, dumpfes Tippen
TAP = soft_tick(0.03, 14, 0.006)                     # Handy: noch weicher
CHINK = soft_tick(0.05, 10, 0.012) * 0.9             # Münzen: kurzes Klimpern ohne Ton
_bz = np.arange(int(0.09 * SR)) / SR
_buzz = np.sign(np.sin(2 * np.pi * 165 * _bz)) * np.minimum(1, _bz / 0.005) * np.minimum(1, (0.09 - _bz) / 0.01)
BUZZ = lowpass(np.concatenate([_buzz, np.zeros(int(0.05 * SR)), _buzz]), 20) * 0.6   # Handy vibriert statt Ping
POP = tone(240, 0.12, 0.003, 0.035, ((1, 1), (2, 0.15)))   # tiefer, weicher Plopp für Knöpfe
RUSTLE = lowpass(noise(0.22, 0.08, hp=False), 8) * 0.9
WHOOSH_N = int(0.35 * SR)
_w = rng.standard_normal(WHOOSH_N)
_w = np.convolve(_w, np.ones(30) / 30, "same")
WHOOSH = _w * np.sin(np.linspace(0, np.pi, WHOOSH_N)) ** 2 * 2.5
def mallet(f, dur=0.35, decay=0.09):
    """Weicher Holz-/Marimba-Anschlag: warm, kurz, nicht piepsig."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    att = np.minimum(1, t / 0.004)
    y = (np.sin(2 * np.pi * f * t) * np.exp(-t / decay)
         + 0.35 * np.sin(2 * np.pi * 4.0 * f * t) * np.exp(-t / (decay * 0.18))
         + 0.12 * np.sin(2 * np.pi * 2.0 * f * t) * np.exp(-t / (decay * 0.4)))
    return lowpass(y * att, 3)


NOTE = lambda m: 440 * 2 ** ((m - 69) / 12)
# Töne aus C-Dur-Pentatonik, passend zur Musik (Am – F – C – G)
CARD_NOTES = [NOTE(m) for m in (72, 74, 76)]          # C5 D5 E5
PHONE_NOTES = [NOTE(m) for m in (76, 79, 81)]         # E5 G5 A5
COIN_SND = mixs(mallet(NOTE(79), 0.25, 0.05), np.concatenate([np.zeros(int(0.045 * SR)), mallet(NOTE(84), 0.25, 0.05)]))
PUSH_SND = mixs(mallet(NOTE(74), 0.3, 0.07), np.concatenate([np.zeros(int(0.08 * SR)), mallet(NOTE(81), 0.35, 0.09)]))
THUD = mixs(tone(90, 0.4, 0.002, 0.12, ((1, 1), (2, 0.4))) * 1.2, lowpass(noise(0.05, 0.01), 8) * 0.6)


def music():
    """Leichter, freundlicher Erklärvideo-Beat: warmer Pad, E-Piano-Akkorde, Bass, weiche Kick + Shaker.
    100 BPM, Am – F – C – G. Keine hohen Zupf-/Pieptöne."""
    beat = 60 / 100
    bar = beat * 4
    chords = [(57, 60, 64), (53, 57, 60), (48, 55, 64), (55, 59, 62)]
    y = np.zeros(N)
    nb = int(DURATION / bar) + 1

    def ep(f, dur=1.3):  # E-Piano: Grundton + leichte Obertöne, sanft abklingend, Tremolo
        n = int(dur * SR)
        t = np.arange(n) / SR
        env_ = np.minimum(1, t / 0.008) * np.exp(-t / 0.55)
        trem = 1 + 0.08 * np.sin(2 * np.pi * 5 * t)
        return (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.2)) * env_ * trem

    kick_t = np.arange(int(0.25 * SR)) / SR
    kick = np.sin(2 * np.pi * (50 + 60 * np.exp(-kick_t / 0.03)) * kick_t) * np.exp(-kick_t / 0.11)
    shaker = lowpass(noise(0.06, 0.02), 3)
    for b in range(nb):
        ch = chords[b % 4]
        t0 = b * bar
        i0, i1 = int(t0 * SR), min(N, int((t0 + bar) * SR) + int(0.3 * SR))
        if i0 >= N:
            break
        tt = np.arange(i1 - i0) / SR
        e = np.minimum(1, tt / 0.6) * np.minimum(1, np.maximum(0, (bar + 0.3 - tt) / 0.5))
        for m in ch:  # Pad
            f = NOTE(m - 12)
            y[i0:i1] += 0.06 * e * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.003 * tt))
        # Bass: Grundton auf 1 und 3
        for bb in (0, 2):
            n = int(beat * 1.8 * SR)
            t_ = np.arange(n) / SR
            add(y, np.sin(2 * np.pi * NOTE(ch[0] - 24) * t_) * np.minimum(1, t_ / 0.01) * np.exp(-t_ / 0.5),
                t0 + bb * beat, 0.16)
        # E-Piano-Akkorde: Schlag 1 und "und" von 2
        for off in (0.0, 1.5 * beat, 3.0 * beat):
            for m in ch:
                add(y, ep(NOTE(m)), t0 + off, 0.045)
        if t0 >= 3.0:  # Beat erst nach dem Hook
            for k in range(4):
                add(y, kick, t0 + k * beat, 0.22 if k % 2 == 0 else 0.12)
            for k in range(8):
                add(y, shaker, t0 + k * beat / 2 + 0.01, 0.05 if k % 2 else 0.025)
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
    mus = mus * duck * fade * 0.5

    fx = np.zeros(N)
    for i, ev in enumerate(EVENTS):
        ev["i"] = i
        if ev["skip"]:
            continue
        if ev["pay"] == "card":
            add(fx, mallet(CARD_NOTES[ev["i"] % 3]), ev["t"], 0.16)
        elif ev["pay"] == "phone":
            add(fx, mallet(PHONE_NOTES[ev["i"] % 3]), ev["t"], 0.15)
        elif ev["pay"] == "bills":
            add(fx, RUSTLE, ev["t"], 0.45)
            add(fx, mallet(NOTE(67), 0.3, 0.1), ev["t"] + 0.6, 0.14)
        elif ev["pay"] == "coin":
            add(fx, COIN_SND, ev["t"], 0.1)
        if ev["push"]:
            add(fx, PUSH_SND, ev["t"] + 0.06, 0.14)
    # Geldautomat
    for k in range(4):
        add(fx, RUSTLE, ATM_T[0] + 0.35 + k * 0.12, 0.5)
    # Akzente
    for tt in (3.0, 5.5, 8.0, at("falsch", "Ist") - 0.1, 22.0, 30.0, 38.0, 43.9, 49.9):
        add(fx, WHOOSH, tt, 0.18)
    add(fx, THUD, 0.0, 0.5)                                   # Hook-Einschlag
    add(fx, THUD, at("falsch", "Noch") - 0.05, 0.6)
    t_first = at("endstand", "Mit") - 0.1
    for i in range(3):
        add(fx, POP, t_first + i * 0.45, 0.35)
    add(fx, THUD, at("endstand", "meisten") - 0.15, 0.55)
    add(fx, POP, at("schmerz", "Tipp") - 0.1, 0.3)
    t_click = at("ende", "abonnier") + 0.1
    add(fx, POP, t_click, 0.4)

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
