"""Baut die Tonspur: Tempo, Zeitplan, Soundeffekte, Musik -> build/doener/mix.wav + timeline.json"""
import json
import os
import subprocess
import wave
from pathlib import Path

import numpy as np

EP = os.environ.get("EP", "01")
if EP == "02":
    from timeline02 import EVENTS, TEMPO, TEMPO_LAW
else:
    from timeline import EVENTS, TEMPO, TEMPO_LAW

ROOT = Path(__file__).resolve().parents[2]
B = ROOT / "build" / ("dauerkarte" if EP == "02" else "doener")
SR = 44100
FPS = 30
GAP = 0.08


def load(path):
    with wave.open(str(path)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return a


def tempo(src, dst, t, clip=None):
    cut = ["-ss", str(clip[0])] if clip else []
    subprocess.run(["ffmpeg", "-v", "error", "-y", *cut, "-i", str(src), "-af", f"atempo={t}",
                    "-ar", str(SR), "-ac", "1", str(dst)], check=True)


rng = np.random.default_rng(7)


def env(n, a=0.002, d=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / d)


def sfx_whoosh(dur=0.45):
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    # einfacher Tiefpass mit wanderndem Koeffizienten
    out = np.zeros(n)
    y = 0
    for i in range(n):
        k = 0.02 + 0.25 * (i / n)
        y += k * (noise[i] - y)
        out[i] = y
    e = np.sin(np.linspace(0, np.pi, n)) ** 2
    return 0.5 * out * e / (np.abs(out).max() + 1e-6)


def sfx_bang():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    thump = np.sin(2 * np.pi * (90 * t - 60 * t ** 2)) * env(n, 0.001, 0.09)
    click = rng.standard_normal(n) * env(n, 0.0005, 0.012)
    return 0.9 * thump + 0.5 * click


def sfx_gavel():
    a = sfx_bang()
    wood = np.sin(2 * np.pi * 620 * np.arange(len(a)) / SR) * env(len(a), 0.0005, 0.05)
    return 0.8 * a + 0.4 * wood


def sfx_sting():
    # "Dun-dun-DUNNN" tief
    parts = []
    for f, d in [(110, 0.22), (104, 0.22), (82, 0.9)]:
        n = int(d * SR)
        t = np.arange(n) / SR
        tone = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2 * f * t) + 0.25 * np.sin(2 * np.pi * 3 * f * t))
        parts.append(tone * env(n, 0.005, d * 0.8) * 0.35)
    return np.concatenate(parts)


def sfx_cricket(dur=1.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    carrier = np.sin(2 * np.pi * 4300 * t)
    chirp = ((np.sin(2 * np.pi * 30 * t) > 0) & ((t % 0.5) < 0.18)).astype(float)
    return 0.06 * carrier * chirp


def sfx_sparkle():
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for k, f in enumerate([1760, 2217, 2637, 3520]):
        st = int(k * 0.07 * SR)
        m = n - st
        s[st:] += np.sin(2 * np.pi * f * t[:m]) * env(m, 0.002, 0.15)
    return 0.12 * s


def sfx_tick():
    n = int(0.08 * SR)
    return 0.25 * np.sin(2 * np.pi * 1800 * np.arange(n) / SR) * env(n, 0.0005, 0.02)


def music(total):
    """Kleiner, frecher Pizzicato-Loop (C-Dur), 116 bpm."""
    bpm = 116
    beat = 60 / bpm
    n = int(total * SR)
    out = np.zeros(n + SR)
    prog = [(48, [60, 64, 67]), (43, [59, 62, 67]), (45, [60, 64, 69]), (41, [60, 65, 69])]
    step = 0
    t0 = 0.0
    while t0 < total:
        bar = (step // 8) % 4
        root, chord = prog[bar]
        pos = step % 8
        if pos in (0, 3, 4, 7):
            f = 440 * 2 ** ((root - 69) / 12)
            m = int(0.4 * SR)
            tt = np.arange(m) / SR
            tone = np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt)
            i = int(t0 * SR)
            out[i:i + m] += 0.5 * tone * env(m, 0.003, 0.16)
        if pos in (1, 2, 5, 6):
            note = chord[(step * 2 + pos) % 3] + 12
            f = 440 * 2 ** ((note - 69) / 12)
            m = int(0.25 * SR)
            tt = np.arange(m) / SR
            tone = np.sin(2 * np.pi * f * tt) * (1 + 0.4 * np.sin(2 * np.pi * 4 * f * tt))
            i = int(t0 * SR)
            out[i:i + m] += 0.18 * tone * env(m, 0.002, 0.07)
        step += 1
        t0 += beat / 2
    return out[:n]


def mouth_env(a):
    hop = SR // FPS
    k = len(a) // hop + 1
    v = np.array([np.sqrt(np.mean(a[i * hop:(i + 1) * hop] ** 2) + 1e-9) for i in range(k)])
    v = v / (np.percentile(v, 95) + 1e-6)
    return np.clip(v, 0, 1.5).round(3).tolist()


TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03,areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,"
        "silenceremove=stop_periods=-1:stop_duration=0.2:stop_threshold=-42dB")


def trim_all():
    """ElevenLabs-Rohdateien (src/urteilmal/voice/<id>.mp3): Stille vorn/hinten weg, lange Pausen kürzen."""
    (B / "trim").mkdir(parents=True, exist_ok=True)
    for src in sorted((Path(__file__).parent / "voice").glob("*.mp3")):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", TRIM, "-ar", str(SR), "-ac", "1",
                        str(B / "trim" / (src.stem + ".wav"))], check=True)


def main():
    trim_all()
    (B / "tempo").mkdir(parents=True, exist_ok=True)
    t = 0.25
    tl = []
    voice_clips = []
    for ev in EVENTS:
        t += ev.get("pre", 0)
        if "pause" in ev:
            tl.append(dict(ev, start=t, dur=ev["pause"]))
            t += ev["pause"]
            continue
        src = B / "trim" / f"{ev.get('src', ev['id'])}.wav"
        dst = B / "tempo" / f"{ev['id']}.wav"
        tempo(src, dst, TEMPO_LAW if ev.get("law") else TEMPO, ev.get("clip"))
        a = load(dst)
        d = len(a) / SR
        voice_clips.append((t, a))
        tl.append(dict(ev, start=t, dur=d, mouth=mouth_env(a)))
        t += d + ev.get("post", 0) + GAP
    total = t + 0.2
    n = int(total * SR) + SR
    voice = np.zeros(n)
    for st, a in voice_clips:
        i = int(st * SR)
        voice[i:i + len(a)] += a
    fx = np.zeros(n)
    mus_gate = np.ones(n)

    def put(buf, st, a, gain=1.0):
        i = int(st * SR)
        a = a[: max(0, n - i)]
        buf[i:i + len(a)] += gain * a

    for e in tl:
        st = e["start"]
        for f in e.get("fx", []):
            if f == "whoosh":
                put(fx, max(0, st - 0.25), sfx_whoosh(), 0.8)
            elif f == "bang":
                put(fx, st + 0.05, sfx_bang(), 0.8)
            elif f == "shake":
                put(fx, st, sfx_whoosh(0.25), 0.4)
            elif f == "gavel":
                put(fx, st + 0.02, sfx_gavel(), 1.0)
                put(fx, st + 0.42, sfx_gavel(), 0.7)
            elif f == "sting":
                put(fx, st, sfx_sting(), 0.9)
            elif f == "cricket":
                put(fx, st + 0.1, sfx_cricket(e["dur"]), 1.0)
            elif f == "sting_late":
                put(fx, st + e["dur"] * 0.55, sfx_sting(), 0.9)
            elif f == "folder":
                put(fx, st + 0.05, sfx_gavel(), 0.7)
            elif f in ("sparkle_doener", "sparkle"):
                put(fx, st + 0.1, sfx_sparkle(), 1.0)
        if e.get("music") is False:
            i0, i1 = int(st * SR), int((st + e["dur"]) * SR)
            mus_gate[i0:i1] = 0.0
        if e["id"] in ("22", "23") or e.get("end"):
            for k in range(int(e["dur"] / 0.4)):
                put(fx, st + 0.2 + k * 0.4, sfx_tick(), 0.6)
    # Musik aus ab dem Rechts-Teil wieder an, im Finale an
    m = music(n / SR)[:n]
    # weiche Übergänge im Gate
    ker = np.ones(int(0.15 * SR)) / int(0.15 * SR)
    mus_gate = np.convolve(mus_gate, ker, mode="same")
    # Ducking unter Sprache
    venv = np.convolve(np.abs(voice), np.ones(4410) / 4410, mode="same")
    duck = 1 - 0.55 * np.clip(venv / 0.05, 0, 1)
    mix = voice * 1.0 + fx * 0.9 + m * 0.11 * mus_gate * duck
    mix = mix[: int(total * SR)]
    mix = mix / max(1.0, np.abs(mix).max() / 0.95)
    with wave.open(str(B / "mix.wav"), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    for e in tl:
        e.pop("hide", None) if False else None
        if "hide" in e:
            e["hide"] = sorted(e["hide"])
    json.dump(dict(total=total, events=tl), open(B / "timeline.json", "w"), ensure_ascii=False, indent=0)
    print(f"Gesamtlänge: {total:.1f} s")
    for e in tl:
        print(f"{e['id']:>3} {e['start']:6.2f} {e['dur']:5.2f}  {e.get('text', '(Pause)')[:50]}")


if __name__ == "__main__":
    main()
