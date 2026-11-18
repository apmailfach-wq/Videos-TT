"""Tonspur (Stereo): Sprecher + leise Musik + Effekte aus der earshot-Soundbank (UI-Pops je Zahlung,\nHolz-Ding je Push-Nachricht, Swishes, Hits, Riser),
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


# Bezahl-Töne wie in Version 3 (kurzer Klick mit hellem Piep), im Mix ca. 6 dB leiser als damals
CLICK = mixs(noise(0.03, 0.004) * 0.6, tone(2600, 0.05, 0.001, 0.012) * 0.5)
TAP3 = mixs(tone(1800, 0.06, 0.001, 0.015) * 0.5, noise(0.02, 0.003) * 0.4)
PING = mixs(tone(1318.5, 0.6, 0.002, 0.18, ((1, 1), (2, 0.25))), 0.7 * np.concatenate(
    [np.zeros(int(0.09 * SR)), tone(1975.5, 0.5, 0.002, 0.16, ((1, 1), (2, 0.2)))]))
COIN3 = sum(tone(f, 0.3, 0.002, 0.06) * g for f, g in ((2093, 0.5), (2637, 0.3), (3136, 0.15)))
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


# ---------------- Earshot-Soundbank (github.com/Leonxlnx/earshot): Effekte als Code, Stereo, 48 kHz
from functools import lru_cache

try:
    from earshot.forge import bank as _bank
except ImportError:  # ohne earshot: eigene Ersatzklänge
    _bank = None


@lru_cache(maxsize=None)
def es(sound_id, pitch=None, seed=None, dur=None):
    """Ein Take aus der earshot-Bank als (n, 2)-Array plus Einsatz-Zeitpunkt (onset) in Sekunden."""
    y, meta = _bank.render(sound_id, seed=seed, pitch=pitch, dur=dur, peak_db=-1.0, checks=False)
    y = np.asarray(y, dtype=np.float64)
    if y.ndim == 1:
        y = np.stack([y, y], axis=1)
    return y, float(meta.get("onset_s") or 0.0)


def place(buf, sound, cue, gain, lead=0.0):
    """Setzt einen earshot-Take so, dass sein Einsatz auf `cue` (+lead) fällt."""
    y, onset = sound
    i = int((cue + lead - onset) * SR)
    if i < 0:
        y, i = y[-i:], 0
    if i >= len(buf):
        return
    j = min(len(buf), i + len(y))
    buf[i:j] += y[:j - i] * gain


def humanize_voice(v):
    """Macht die TTS-Stimme natürlicher: Trittschall weg, mehr Wärme und Präsenz, weniger Zischen,
    sanfte Kompression und ein kleiner Raum (wie in einem Zimmer aufgenommen statt trocken aus dem Rechner)."""
    import subprocess
    chain = ("highpass=f=75,"
             "equalizer=f=170:t=q:w=1.0:g=2.5,"        # Wärme
             "equalizer=f=450:t=q:w=1.2:g=-1.5,"       # weniger 'Pappe'
             "equalizer=f=3200:t=q:w=1.4:g=1.5,"       # Präsenz
             "equalizer=f=7200:t=q:w=2.0:g=-3,"        # Zischlaute weicher
             "acompressor=threshold=-22dB:ratio=2.2:attack=10:release=150:makeup=1.5,"
             "aecho=0.85:0.5:19|33|47:0.09|0.06|0.04")  # kleiner Raum
    pcm = (np.clip(v, -1, 1) * 32767).astype(np.int16).tobytes()
    out = subprocess.run(["ffmpeg", "-v", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-",
                          "-af", chain, "-f", "s16le", "-ar", str(SR), "-ac", "1", "-"],
                         input=pcm, capture_output=True, check=True).stdout
    y = np.frombuffer(out, np.int16).astype(np.float64) / 32768
    y = np.pad(y, (0, max(0, len(v) - len(y))))[:len(v)]
    return y * (np.max(np.abs(v)) / max(np.max(np.abs(y)), 1e-9))


def stereo(mono):
    return np.stack([mono, mono], axis=1)


def main():
    voice = np.zeros(N)
    for st, tim in zip(AUDIO_START, TIM):
        add(voice, np.load(tim["audio"]), st, 1.0)
    if not TIM[0].get("own"):   # nur die TTS-Stimme nachbearbeiten; die eigene Aufnahme ist schon aufbereitet
        voice = humanize_voice(voice)

    mus = music()
    e = np.abs(voice)
    k = int(0.15 * SR)
    e = np.convolve(e, np.ones(k) / k, "same")
    duck = 1 - 0.55 * np.clip(e / 0.05, 0, 1)
    fade = np.minimum(1, np.arange(N) / (1.0 * SR)) * np.minimum(1, (N - np.arange(N)) / (1.5 * SR))
    mus = mus * duck * fade * 0.5

    fx = np.zeros((N, 2))
    card_p, phone_p = ("C5", "D5", "E5"), ("E5", "G5", "A5")
    for i, ev in enumerate(EVENTS):
        if ev["skip"]:
            continue
        t = ev["t"]
        if ev["pay"] == "card":                         # Karte: Klick-Piep (leise)
            add(fx[:, 0], CLICK, t, 0.12); add(fx[:, 1], CLICK, t, 0.12)
        elif ev["pay"] == "phone":                      # Handy: Tipp-Piep (leise)
            add(fx[:, 0], TAP3, t, 0.13); add(fx[:, 1], TAP3, t, 0.13)
        elif ev["pay"] == "bills":                      # Scheine: Rascheln, dann Klick beim Übergeben
            add(fx[:, 0], RUSTLE, t, 0.35)
            add(fx[:, 1], RUSTLE, t + 0.01, 0.35)
            add(fx[:, 0], CLICK, t + 0.6, 0.11); add(fx[:, 1], CLICK, t + 0.6, 0.11)
        elif ev["pay"] == "coin":                       # Münzen: leises Klingeln
            add(fx[:, 0], COIN3, t, 0.07); add(fx[:, 1], COIN3, t + 0.004, 0.07)
        if ev["push"]:                                  # Push-Nachricht: Ping (leise)
            add(fx[:, 0], PING, t + 0.05, 0.08); add(fx[:, 1], PING, t + 0.05, 0.08)
    for k in range(4):                                  # Geldautomat
        add(fx[:, k % 2], RUSTLE, ATM_T[0] + 0.35 + k * 0.12, 0.45)
    place(fx, es("knock/double"), ATM_T[0] + 0.1, 0.25, -0.04)
    # Übergänge
    for tt in (3.95, 8.0, at("falsch", "Ist") - 0.1, 22.0, 30.0, 38.0, 49.9, 55.9):
        place(fx, es("swish/soft"), tt, 0.3)
    # Treffer
    place(fx, es("cut_hit/kick"), 0.0, 0.75)                          # Hook-Einschlag ab Frame 0
    place(fx, es("cut_hit/sub"), 0.02, 0.5)
    place(fx, es("cut_hit/kick"), at("falsch", "Noch") - 0.05, 0.6)   # "NOCH NICHT."
    place(fx, es("riser/dark"), 43.95 - 0.7, 0.35)                    # Spannung vor dem Ergebnis
    place(fx, es("knock/double"), 43.6, 0.25)                         # Tag 30: alle bleiben stehen
    t_first = at("endstand", "Mit") - 0.1
    for i in range(3):
        place(fx, es("ui_pop/step", ("G4", "A4", "C5")[i]), t_first + i * 0.45, 0.3)
    place(fx, es("cut_hit/punch"), at("endstand", "meisten") - 0.15, 0.55)
    place(fx, es("ui_pop/soft", "G5"), at("schmerz", "Tipp") - 0.1, 0.3)
    t_click = at("ende", "abonnier") + 0.1
    place(fx, es("ui_pop/step", "C5"), t_click, 0.4)

    mix = stereo(voice) + stereo(mus) + fx
    mix = np.tanh(mix * 1.1) / 1.1   # weicher Limiter
    peak = np.max(np.abs(mix))
    mix = mix / max(peak, 1e-6) * 0.89
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(BUILD / "mix.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("mix.wav", round(N / SR, 2), "s stereo, peak", round(float(peak), 3))


if __name__ == "__main__":
    main()
