"""Synthesised sound design for "Was wäre, wenn … Teil 1" (68 s, 48 kHz stereo, with narration).

Quiet wonder and cheering -> blackout -> silent meteor -> deep rumble -> earthquake + car alarms
-> one second of total silence -> pressure wave -> tinnitus, fire, wind -> tinny phone playback -> silence.
"""
import sys
import wave
from pathlib import Path

import numpy as np

import json
TLJ = json.loads((Path(__file__).resolve().parent / 'timeline.json').read_text())
WARP = TLJ['warp']


def U(x):
    """story time (as used by the 3D scene) -> output time"""
    for (u0, t0), (u1, t1) in zip(WARP, WARP[1:]):
        if x <= t1:
            return u0 + (u1 - u0) * (x - t0) / (t1 - t0)
    return WARP[-1][0]


SR = 48000
DUR = TLJ['duration']
N = int(SR * DUR)
rng = np.random.default_rng(1859)
t = np.arange(N) / SR


def seg(a, b):
    return slice(int(a * SR), int(b * SR))


def band(x, lo, hi, soft=0.15):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.ones_like(f)
    if lo > 0:
        m *= 1 / (1 + np.exp(-(np.log(f + 1e-6) - np.log(lo)) / soft))
    if hi:
        m *= 1 / (1 + np.exp((np.log(f + 1e-6) - np.log(hi)) / soft))
    return np.fft.irfft(X * m, len(x))


def env(a, b, fi, fo, n=N):
    e = np.zeros(n)
    tt = np.arange(n) / SR
    e = np.clip((tt - a) / max(fi, 1e-4), 0, 1) * np.clip((b - tt) / max(fo, 1e-4), 0, 1)
    return e


def smooth_noise(rate, n=N, seed=0):
    r = np.random.default_rng(seed)
    k = int(DUR * rate) + 3
    pts = r.uniform(-1, 1, k)
    x = np.arange(n) / SR * rate
    i = np.floor(x).astype(int)
    f = x - i
    f = f * f * (3 - 2 * f)
    return pts[i] * (1 - f) + pts[i + 1] * f


def norm(x, peak=1.0):
    m = np.max(np.abs(x)) + 1e-9
    return x / m * peak


L = np.zeros(N)
Rch = np.zeros(N)


def add(x, gain=1.0, pan=0.0):
    global L, Rch
    L += x * gain * np.sqrt(0.5 * (1 - pan))
    Rch += x * gain * np.sqrt(0.5 * (1 + pan))


# ------------------------------------------------------------------ crowd (babble, oohs, cheers, laughs)
def crowd_layer(seed, level_curve):
    r = np.random.default_rng(seed)
    out = np.zeros(N)
    for v in range(36):
        noise = r.standard_normal(N)
        f1 = r.uniform(350, 800)
        voice = band(noise, f1, f1 * r.uniform(2.5, 4.5), 0.25)
        syl = np.clip(smooth_noise(r.uniform(3.5, 6.5), seed=seed * 100 + v), 0, 1) ** 1.5
        phrase = np.clip(smooth_noise(0.4, seed=seed * 300 + v) + 0.3, 0, 1)
        out += norm(voice) * syl * phrase
    return norm(out) * level_curve


def vowel(f0, dur, formants, seed, vib=0.03):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    r = np.random.default_rng(seed)
    f = f0 * (1 + vib * np.sin(2 * np.pi * r.uniform(4, 6) * tt) + 0.05 * np.sin(np.pi * tt / dur))
    ph = np.cumsum(f) / SR
    saw = 2 * (ph % 1) - 1
    y = sum(band(saw, fm * 0.85, fm * 1.15, 0.08) * g for fm, g in formants)
    return y


def place(x, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    y = np.zeros(N)
    j = min(N, i + len(x))
    y[i:j] = x[: j - i]
    add(y, gain, pan)
    return y


crowd_lvl = (0.55 * env(0, U(16.05), 0.05, 0.06) + 0.45 * env(U(11.4), U(16.05), 0.6, 0.06) + 0.25 * env(U(7.4), U(9.5), 0.2, 1.2))
crowd = crowd_layer(1, crowd_lvl)
add(crowd, 0.22, -0.2)
crowd2 = crowd_layer(2, crowd_lvl)
add(crowd2, 0.22, 0.25)

# "Ohhh" of wonder at the start, "ohh" at the blackout
OOH = [(450, 1.0), (800, 0.6), (2600, 0.15)]
AAH = [(750, 1.0), (1200, 0.7), (2700, 0.2)]
for k in range(10):
    d = 1.8 + rng.uniform(0, 0.8)
    x = vowel(rng.uniform(110, 260), d, OOH if k % 2 else AAH, 50 + k) * np.hanning(int(d * SR))
    place(norm(x), 0.15 + rng.uniform(0, 0.6), 0.05, rng.uniform(-0.8, 0.8))
for k in range(12):
    d = 1.4 + rng.uniform(0, 0.6)
    x = vowel(rng.uniform(110, 260), d, OOH, 80 + k) * np.hanning(int(d * SR))
    place(norm(x), U(7.5) + rng.uniform(0, 0.4), 0.055, rng.uniform(-0.8, 0.8))

# cheers + whistles for the "meteor show"
cheer = band(rng.standard_normal(N), 500, 4200, 0.3) * env(U(11.6), U(16.03), 0.5, 0.05) * (0.7 + 0.3 * np.clip(smooth_noise(3, seed=9), -1, 1))
add(norm(cheer), 0.2)
for k in range(6):
    a = U(11.9) + k * 1.1 + rng.uniform(0, 0.3)
    d = 0.7
    n = int(d * SR)
    tt = np.arange(n) / SR
    f = np.linspace(rng.uniform(1600, 2000), rng.uniform(2600, 3200), n)
    w = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / d) ** 2
    if a + d < U(16):
        place(w, a, 0.03, rng.uniform(-0.7, 0.7))
for k in range(9):
    a = U(3.0) + k * 2.0 + rng.uniform(0, 0.4)
    if a > U(15.4):
        break
    nh = rng.integers(3, 6)
    for h in range(nh):
        x = vowel(rng.uniform(170, 290), 0.13, AAH, 200 + k * 10 + h) * np.hanning(int(0.13 * SR))
        place(norm(x), a + h * 0.19, 0.06, rng.uniform(-0.6, 0.6))

# soft ambient pad (wonder) – cut by the flash
pad = np.zeros(N)
for f in [110, 164.81, 220, 246.94, 329.63, 440]:
    pad += np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t + f))
pad = band(pad, 80, 3000) * env(0, U(16.0), 0.05, 0.02)
add(norm(pad), 0.06)

# blackout: electrical thunk + mains hum dies
hum = (np.sin(2 * np.pi * 100 * t) + 0.4 * np.sin(2 * np.pi * 200 * t) + 0.2 * np.sin(2 * np.pi * 300 * t)) * env(0, U(8.4), 0.5, 0.05)
add(hum, 0.012)
for a in [U(x) for x in [7.35, 7.9, 8.35]]:
    n = int(0.5 * SR)
    tt = np.arange(n) / SR
    th = np.sin(2 * np.pi * (70 - 30 * tt) * tt) * np.exp(-tt * 9) + band(rng.standard_normal(n), 100, 900) * 0.2 * np.exp(-tt * 30)
    place(th, a, 0.18)

# meteor: thin hiss, rising
hiss = band(rng.standard_normal(N), 3000, 9000) * np.clip((t - U(11)) / (U(16) - U(11)), 0, 1) ** 2 * env(U(11), U(16.0), 0.1, 0.02)
add(norm(hiss), 0.035)

# flash: crowd cut, high ring; sound arrives later as a deep rumble
ring = np.sin(2 * np.pi * 5200 * t) * env(U(16.0), U(16.0) + 3.5, 0.01, 3.4) * np.exp(-np.clip(t - U(16), 0, None) * 0.6)
add(ring, 0.02)
gasp = band(rng.standard_normal(N), 800, 5000) * env(U(16.05), U(16.05) + 0.6, 0.03, 0.4)
add(norm(gasp), 0.05)
brown = np.cumsum(rng.standard_normal(N))
brown = band(brown - np.convolve(brown, np.ones(4800) / 4800, mode='same'), 18, 140, 0.3)
brown = norm(brown)
rumble_env = np.clip((t - U(17.0)) / (U(20.0) - U(17.0)), 0, 1) ** 1.5 * 0.55 * env(U(17), U(24.0), 0.1, 0.02) + env(U(20.0), U(24.0), 0.15, 0.02) * 0.6
rumble_env *= 1 + 0.3 * smooth_noise(6, seed=33)
add(brown * rumble_env, 0.95)

# earthquake detail: rattle, cracks, car alarms
rattle = band(rng.standard_normal(N), 900, 6000) * (rng.random(N) < 0.004) * 8
rattle = np.convolve(rattle, np.exp(-np.arange(400) / 60), mode='same') * env(U(20.1), U(24.0), 0.2, 0.02)
add(norm(rattle), 0.12, 0.2)
for a in [U(x) for x in [20.4, 21.0, 21.6, 22.3, 22.9, 20.9, 21.3, 21.8, 22.6, 23.2, 23.5]]:  # cracks, falling facade/lamps
    n = int(0.35 * SR)
    tt = np.arange(n) / SR
    c = band(rng.standard_normal(n), 60, 2500) * np.exp(-tt * 14)
    place(norm(c), a, 0.25, rng.uniform(-0.5, 0.5))
# your phone hitting the ground
n = int(0.25 * SR)
tt = np.arange(n) / SR
place(norm(band(rng.standard_normal(n), 600, 7000) * np.exp(-tt * 40)), U(21.95), 0.2, 0.3)


def car_alarm(start, f1, f2, rate, pan, gain):
    tt = t - start
    sw = (np.floor(tt * rate) % 2 == 0)
    f = np.where(sw, f1, f2)
    ph = np.cumsum(f) / SR
    sq = np.sign(np.sin(2 * np.pi * ph)) * 0.6 + np.sin(2 * np.pi * ph) * 0.4
    sq = band(sq, 300, 4000)
    e = env(start, U(24.0), 0.05, 0.02) + env(U(25.0), U(27.6), 0.05, 0.02) * 0.6
    add(sq * e, gain, pan)


car_alarm(U(20.7), 780, 980, 3.0, -0.6, 0.035)
car_alarm(U(21.3), 1200, 1500, 6.0, 0.5, 0.025)
car_alarm(U(22.1), 650, 650, 1.0, 0.1, 0.02)

# 24.0 – 25.0: TOTAL SILENCE (everything above is gated to 24.0)

# pressure wave: rising roar, blast, glass
T_HIT = U(25.0 + 700 / 260)
roar = band(rng.standard_normal(N), 30, 700, 0.4)
roar_env = np.clip((t - U(25.0)) / (T_HIT - U(25.0)), 0, 1) ** 2.2 * env(U(25.0), DUR, 0.01, 0.01)
roar_env = np.where(t > T_HIT, np.exp(-(t - T_HIT) * 1.8), roar_env)
add(norm(roar) * roar_env, 0.55)
blast = band(rng.standard_normal(N), 20, 9000, 0.4) * env(T_HIT, T_HIT + 3, 0.004, 0.01) * np.exp(-np.clip(t - T_HIT, 0, None) * 2.5)
add(norm(blast), 0.95)
sub = np.sin(2 * np.pi * 38 * t) * env(T_HIT, T_HIT + 2.5, 0.01, 2.4) * np.exp(-np.clip(t - T_HIT, 0, None) * 1.5)
add(sub, 0.5)
glass = np.zeros(N)
for k in range(260):
    a = U(25.6) + (T_HIT - U(25.6)) * rng.random() ** 0.5 + rng.uniform(0, 0.9)
    n = int(0.12 * SR)
    tt = np.arange(n) / SR
    f = rng.uniform(2500, 7500)
    s = (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.7 * tt)) * np.exp(-tt * rng.uniform(25, 60))
    i = int(a * SR)
    if i + n < N:
        glass[i:i + n] += s * rng.uniform(0.2, 1) * (0.4 if a < T_HIT else 1)
add(norm(glass), 0.2)

# aftermath: tinnitus, muffled wind, fire crackle, debris thuds
tinn = np.sin(2 * np.pi * 3900 * t) * env(T_HIT + 0.3, U(34.0), 0.6, 1.5)
add(tinn, 0.025)
wind = band(rng.standard_normal(N), 60, 500, 0.4) * env(T_HIT + 0.5, U(41.0), 1.0, 0.02) * (0.7 + 0.3 * smooth_noise(0.5, seed=71))
add(norm(wind), 0.12)
crack = (rng.random(N) < 0.0012) * rng.uniform(-1, 1, N)
crack = band(np.convolve(crack, np.exp(-np.arange(300) / 40), mode='same'), 400, 6000) * env(U(28.3), U(34.0), 1.0, 0.6)
add(norm(crack), 0.13, -0.3)
for k in range(14):
    a = U(28.6) + rng.uniform(0, U(33.8) - U(28.6))
    n = int(0.4 * SR)
    tt = np.arange(n) / SR
    place(np.sin(2 * np.pi * (90 - 50 * tt) * tt) * np.exp(-tt * 10), a, 0.15, rng.uniform(-0.8, 0.8))
add(brown * env(U(28.0), U(34.0), 0.5, 0.8), 0.25)

# 34 – 41: close-up. muffled world + tinny phone playback of the cheering
add(norm(band(rng.standard_normal(N), 50, 300, 0.4)) * env(U(34.0), U(41.0), 0.4, 0.02), 0.05)
play_src = (crowd + crowd2)[seg(U(3.0), U(3.0) + 7.0)]
play_extra = np.zeros(len(play_src))
for k in range(4):  # laughs inside the clip
    for h in range(4):
        x = vowel(rng.uniform(180, 280), 0.13, AAH, 400 + k * 10 + h) * np.hanning(int(0.13 * SR))
        i = int((2.3 + k * 0.35 + h * 0.18) * SR)
        play_extra[i:i + len(x)] += norm(x) * 0.6
play = band(norm(play_src) + play_extra, 900, 4200, 0.12)
play = np.tanh(norm(play) * 2.5) * 0.8
y = np.zeros(N)
PA = U(34.3)
y[seg(PA, PA + len(play) / SR)] = play[: len(y[seg(PA, PA + len(play) / SR)])]
y *= env(PA, U(41.0), 0.15, 0.003)
y *= np.where((t > U(40.72)) & (t < U(41.0)), (np.floor(t * 28) % 2) * 0.7 + 0.3, 1.0)
add(y, 0.22, 0.05)
# low-battery beep
for a in [U(39.75)]:
    n = int(0.18 * SR)
    tt = np.arange(n) / SR
    place(np.sin(2 * np.pi * 1320 * tt) * np.hanning(n), a, 0.05)

# extra action: meteor breaking apart, lamp posts / facade crashing, car explosion
n = int(0.9 * SR); tt = np.arange(n) / SR
place(norm(band(rng.standard_normal(n), 2000, 9000) * np.exp(-tt * 3) * np.sin(np.pi * tt / 0.9)), U(14.5), 0.05, -0.4)
for a in [U(x) for x in [21.2, 21.9, 22.5, 23.1]]:   # metal poles hitting the street
    n = int(0.8 * SR); tt = np.arange(n) / SR
    clang = sum(np.sin(2 * np.pi * f * tt) * np.exp(-tt * d) for f, d in [(410, 6), (1130, 9), (2370, 12)])
    place(norm(clang + band(rng.standard_normal(n), 80, 1500) * np.exp(-tt * 20)), a, 0.12, rng.uniform(-0.7, 0.7))
EX = U(31.2)
n = int(3.0 * SR); tt = np.arange(n) / SR
boom = band(rng.standard_normal(n), 25, 3000, 0.4) * np.exp(-tt * 3.5) + np.sin(2 * np.pi * (60 - 25 * tt) * tt) * np.exp(-tt * 2.5)
place(norm(boom), EX, 0.75, -0.2)

# ------------------------------------------------------------------ master: SFX bus + narration
sfx = np.stack([L, Rch], 1)
SILENT = [(U(24.0), U(25.0)), (U(41.0), DUR)]
for a, b in SILENT:
    sfx[seg(a, b)] = 0
sfx = np.tanh(sfx * 1.6) / np.tanh(1.6)
sfx = sfx / (np.max(np.abs(sfx)) + 1e-9) * 0.85

voice = np.zeros(N)
vdir = Path(__file__).resolve().parents[2] / 'build' / 'waswaere' / 'voice'
lines = json.loads((vdir / 'lines.json').read_text())
for at, ln in zip(TLJ['voice_at'], lines):
    with wave.open(ln['file']) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(float) / 32767
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(1)
    i = int(at * SR); j = min(N, i + len(x)); voice[i:j] += x[: j - i]
voice = voice / (np.max(np.abs(voice)) + 1e-9) * 0.95
# ducking: SFX down ~8 dB while the narrator speaks (smoothed)
act = np.convolve((np.abs(voice) > 0.02).astype(float), np.ones(int(0.25 * SR)) / int(0.25 * SR), mode='same')
act = np.convolve(np.clip(act * 4, 0, 1), np.ones(int(0.15 * SR)) / int(0.15 * SR), mode='same')
duck = 1 - 0.6 * act
pre = sfx * duck[:, None] + voice[:, None] * 0.9
g = 0.95 / (np.max(np.abs(pre)) + 1e-9)
mix = pre * g
for a, b in SILENT:   # dead silence: only the narrator may speak here
    mix[seg(a, b)] = voice[seg(a, b)][:, None] * 0.9 * g
out = Path(sys.argv[1] if len(sys.argv) > 1 else '../../build/waswaere/audio.wav')
out.parent.mkdir(parents=True, exist_ok=True)
with wave.open(str(out), 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((np.clip(mix, -1, 1) * 32767).astype('<i2').tobytes())
print('wrote', out)
