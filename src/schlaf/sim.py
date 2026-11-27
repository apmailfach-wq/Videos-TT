"""Physics + timeline for "Die 5 Phasen von 'Ich geh heute früh schlafen'".

Everything that moves is simulated here once, deterministically, and stored
per frame in build/schlaf/sim.npz (+ sound events in events.json). render.py
and audio.py only read these files, so frames can be drawn in parallel.
"""
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "schlaf"

W, H, FPS = 1080, 1920, 30
DUR = 30.0
NF = int(DUR * FPS)
SUB = 12

FLOOR = 1480            # mattress surface (kept above TikTok's bottom caption zone)
CEIL = 140
PIL_W0, PIL_H0 = 940, 250   # overwritten from the sprite size via set_pillow_size()

T_WORD_IN = 1.6         # rubber word pops in
T_PH2 = 4.6             # "Nur 1 Video" phase caption
T_DROP = 5.6            # rubber word jumps
T_PH4 = 16.0            # balls start to settle / bury
T_BLOCK = 25.0          # iron block released
NB = 50
WORD_HH = 62            # half height of the rubber word (contact)

PALETTE = [(37, 244, 238), (254, 44, 85), (255, 214, 10), (160, 90, 255),
           (60, 230, 120), (255, 140, 30), (255, 255, 255), (60, 140, 255)]


def breath(t):
    """Pillow breathing factor (snore cycle 3.2 s), fades out after the split."""
    return 1 + 0.05 * math.sin(2 * math.pi * t / 3.2 - math.pi / 2)


def run():
    BUILD.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(347)
    dt = 1 / FPS / SUB

    pil = np.zeros((NF, 3))          # w, h, breath-amount
    word = np.zeros((NF, 6))         # x, y, sx, sy, visible, scale-in
    balls = np.zeros((NF, NB, 6))    # x, y, angle, sx, sy, visible
    block = np.zeros((NF, 2))        # bottom y, visible
    shake = np.zeros((NF, 2))
    events = []

    # pillow squash spring
    s, sv = 0.0, 0.0
    # rubber word
    wx, wy, wvy = 540.0, 800.0, 0.0
    q, qv = 0.0, 0.0                 # word squash spring
    hits = 0
    split_t = None
    # balls
    r = rng.uniform(40, 49, NB)
    p = np.zeros((NB, 2))
    v = np.zeros((NB, 2))
    ang = rng.uniform(0, 360, NB)
    alive = np.zeros(NB, bool)
    flying = np.zeros(NB, bool)      # squeezed out sideways by the block
    last_snd = np.full(NB, -1.0)
    shakes = []                      # (t0, amp, dur)
    # block
    b_bottom, b_v = -40.0, 0.0
    impact_t = None
    pile_top0 = None
    frozen = None

    for f in range(NF):
        t = f / FPS
        bam = 1.0 if (split_t is None) else max(0.0, 1 - (t - split_t) / 0.6)
        bfac = 1 + (breath(t) - 1) * bam
        for k in range(SUB):
            tt = t + k * dt
            # ---------------- phase dependent ball params
            if tt < T_PH4:
                g, e_wall, e_bb, e_pil, air = 1500.0, 0.98, 0.96, 1.06, 0.0
            else:
                u = min(1.0, (tt - T_PH4) / 2.5)
                g = 1500 + 1700 * u
                e_wall = 0.98 - 0.85 * u
                e_bb = 0.96 - 0.86 * u
                e_pil = 1.06 - 0.96 * u
                air = 0.0 + 2.2 * max(0.0, (tt - T_PH4 - 2.0) / 3.0)

            # ---------------- pillow spring (weight of buried balls pushes it flat)
            s0 = 0.0
            if alive.any() and tt > T_PH4:
                s0 = 0.20 * min(1.0, (tt - T_PH4) / 4.0)
            sa = -260 * (s - s0) - 13 * sv
            sv += sa * dt
            s += sv * dt
            s = min(max(s, -0.25), 0.55)
            pw = PIL_W0 * (1 + 0.45 * s)
            ph = PIL_H0 * (1 - s) * bfac
            ptop = FLOOR - ph

            # ---------------- rubber word
            if split_t is None and tt >= T_DROP:
                if tt - dt < T_DROP:
                    wvy = -900.0
                wvy += 3400 * dt
                wy += wvy * dt
                if wy + WORD_HH * (1 - 0.5 * q) >= ptop and wvy > 0:
                    hits += 1
                    vimp = wvy
                    events.append({"t": tt, "type": "boing", "v": vimp, "n": hits})
                    shakes.append((tt, 6 + 4 * hits, 0.25))
                    sv += 2.6 * vimp / 2000
                    qv += 9.0 * vimp / 2000
                    if hits >= 3:
                        split_t = tt
                        events.append({"t": tt, "type": "split"})
                        shakes.append((tt, 22, 0.45))
                        # spawn the 50 bouncy balls in the footprint of the word
                        cols, rows = 10, 5
                        idx = 0
                        for rr_ in range(rows):
                            for cc in range(cols):
                                x = 540 + (cc - (cols - 1) / 2) * 68 + rng.uniform(-8, 8)
                                y = wy - 40 + (rr_ - (rows - 1) / 2) * 30 + rng.uniform(-6, 6)
                                p[idx] = (x, y)
                                dx = x - 540
                                sp = rng.uniform(1700, 2900)
                                a = math.atan2(-abs(rng.uniform(0.35, 1.0)), dx / 330 + rng.uniform(-0.5, 0.5))
                                v[idx] = (math.cos(a) * sp, math.sin(a) * sp)
                                idx += 1
                        alive[:] = True
                    else:
                        wy = ptop - WORD_HH * (1 - 0.5 * q)
                        wvy = -vimp * 1.09          # hyperactive: it gains energy
                qa = -520 * q - 16 * qv
                qv += qa * dt
                q += qv * dt
            elif split_t is None:
                qa = -520 * q - 16 * qv
                qv += qa * dt
                q += qv * dt

            # ---------------- balls
            # phase 4: the pillow sinks away under the balls -> they bury it (drawn in front)
            coll = 1.0 - min(1.0, max(0.0, (tt - T_PH4 - 0.8) / 1.6)) ** 2 * 1.0
            if alive.any() and frozen is None:
                v[:, 1] += g * dt
                if air > 0:
                    v *= max(0.0, 1 - air * dt)
                p += v * dt
                ang -= (v[:, 0] / r) * dt * 57.3
                # walls / ceiling / floor
                for i in range(NB):
                    x, y = p[i]
                    ri = r[i]
                    imp = 0.0
                    if x - ri < 0:
                        p[i, 0] = ri; imp = max(imp, -v[i, 0]); v[i, 0] = abs(v[i, 0]) * e_wall
                    elif x + ri > W:
                        p[i, 0] = W - ri; imp = max(imp, v[i, 0]); v[i, 0] = -abs(v[i, 0]) * e_wall
                    if y - ri < CEIL:
                        p[i, 1] = CEIL + ri; imp = max(imp, -v[i, 1]); v[i, 1] = abs(v[i, 1]) * e_wall
                    elif y + ri > FLOOR:
                        p[i, 1] = FLOOR - ri; imp = max(imp, v[i, 1]); v[i, 1] = -abs(v[i, 1]) * e_wall
                        v[i, 0] *= 0.995 if tt < T_PH4 else 0.9
                    # pillow = rounded rectangle on the floor
                    cph = ph * coll
                    rr = min(110.0, cph / 2)
                    ix0, ix1 = 540 - pw / 2 + rr, 540 + pw / 2 - rr
                    iy0, iy1 = FLOOR - cph + rr, FLOOR - rr
                    qx = min(max(p[i, 0], ix0), ix1)
                    qy = min(max(p[i, 1], iy0), iy1)
                    dx, dy = p[i, 0] - qx, p[i, 1] - qy
                    dd = math.hypot(dx, dy)
                    if dd < rr + ri and coll > 0.02:
                        if dd < 1e-6:
                            nx, ny = 0.0, -1.0
                        else:
                            nx, ny = dx / dd, dy / dd
                        pen = rr + ri - dd
                        p[i, 0] += nx * pen
                        p[i, 1] += ny * pen
                        vn = v[i, 0] * nx + v[i, 1] * ny
                        if vn < 0:
                            v[i, 0] -= (1 + e_pil) * vn * nx
                            v[i, 1] -= (1 + e_pil) * vn * ny
                            if tt >= T_PH4:
                                tx, ty = -ny, nx
                                vt = v[i, 0] * tx + v[i, 1] * ty
                                v[i, 0] -= 0.25 * vt * tx
                                v[i, 1] -= 0.25 * vt * ty
                            imp = max(imp, -vn)
                            sv += 0.05 * (-vn) / 1500 * (1 if tt < T_PH4 else 0.3)
                    if imp > 380 and tt - last_snd[i] > 0.09:
                        last_snd[i] = tt
                        events.append({"t": tt, "type": "pop", "v": float(imp), "i": i})
                # ball-ball
                d = p[:, None, :] - p[None, :, :]
                dist = np.sqrt((d ** 2).sum(-1)) + 1e-9
                ov = r[:, None] + r[None, :] - dist
                ii, jj = np.nonzero(np.triu(ov > 0, 1))
                for i, j in zip(ii, jj):
                    dx, dy = p[i] - p[j]
                    dd = math.hypot(dx, dy) + 1e-9
                    pen = r[i] + r[j] - dd
                    if pen <= 0:
                        continue
                    nx, ny = dx / dd, dy / dd
                    corr = min(pen, 25) * 0.5
                    p[i, 0] += nx * corr; p[i, 1] += ny * corr
                    p[j, 0] -= nx * corr; p[j, 1] -= ny * corr
                    vn = (v[i, 0] - v[j, 0]) * nx + (v[i, 1] - v[j, 1]) * ny
                    if vn < 0:
                        jimp = -(1 + e_bb) * vn / 2
                        v[i, 0] += jimp * nx; v[i, 1] += jimp * ny
                        v[j, 0] -= jimp * nx; v[j, 1] -= jimp * ny
                        if tt >= T_PH4:
                            tx, ty = -ny, nx
                            vt = (v[i, 0] - v[j, 0]) * tx + (v[i, 1] - v[j, 1]) * ty
                            v[i, 0] -= 0.12 * vt * tx; v[i, 1] -= 0.12 * vt * ty
                            v[j, 0] += 0.12 * vt * tx; v[j, 1] += 0.12 * vt * ty
                        if -vn > 420 and tt - last_snd[i] > 0.09 and tt - last_snd[j] > 0.09:
                            last_snd[i] = last_snd[j] = tt
                            events.append({"t": tt, "type": "pop", "v": float(-vn), "i": int(i)})
                # keep the chaos alive in phase 3 (flubber energy)
                if tt < T_PH4 - 0.5 and k == 0:
                    slow = (v ** 2).sum(1) < 900 ** 2
                    for i in np.nonzero(slow)[0]:
                        if rng.random() < 0.05:
                            v[i] += (rng.uniform(-900, 900), rng.uniform(-1900, -1200))

        # ---------------- iron block (frame resolution is enough)
        if t >= T_BLOCK:
            if frozen is None:
                frozen = (p.copy(), ang.copy())
                pile_top0 = float((p[:, 1] - r).min())
                events.append({"t": t, "type": "whistle"})
            if impact_t is None:
                b_v += 9500 / FPS
                b_v = max(b_v, 900)
                b_bottom += b_v / FPS
                if b_bottom >= pile_top0:
                    b_bottom = pile_top0
                    impact_t = t
                    events.append({"t": t, "type": "thud"})
                    shakes.append((t, 46, 0.7))
                    # the outermost balls get squeezed out sideways
                    order = np.argsort(frozen[0][:, 0])
                    out_ids = list(order[:3]) + list(order[-3:])
                    flying[out_ids] = True
                    for i in out_ids:
                        side = -1 if frozen[0][i, 0] < 540 else 1
                        v[i] = (side * rng.uniform(1300, 2000), rng.uniform(-1300, -700))
                    p[:] = frozen[0]
            else:
                u = min(1.0, (t - impact_t) / 0.12)
                eo = 1 - (1 - u) ** 3
                target = FLOOR - 120
                b_bottom = pile_top0 + (target - pile_top0) * eo
                # tiny rebound
                if t - impact_t > 0.12:
                    w_ = t - impact_t - 0.12
                    b_bottom = target - 10 * math.exp(-w_ * 9) * abs(math.sin(w_ * 30))
            block[f] = (b_bottom, 1)

        # ---------------- record frame
        bfac = 1 + (breath(t) - 1) * bam
        k_crush = 1.0
        if impact_t is not None:
            k_crush = max(0.12, (FLOOR - block[f, 0]) / (FLOOR - pile_top0))
        pil[f] = (PIL_W0 * (1 + 0.45 * s) * (1 + 0.35 * (1 - k_crush)),
                  PIL_H0 * (1 - s) * bfac * k_crush, bam)
        if split_t is None:
            sc = min(1.0, max(0.0, (t - T_WORD_IN) / 0.45))
            if t < T_DROP:
                wx = 540 + 46 * math.sin(t * 2.3) + 8 * math.sin(t * 17)
                wy = 800 + 26 * math.sin(t * 3.1) + 6 * math.sin(t * 23)
            stretch = 1 + min(0.22, abs(wvy) / 9000) if t >= T_DROP else 1
            sy = (1 - q) * stretch
            sx = (1 + 0.7 * q) / stretch ** 0.5
            word[f] = (wx, wy, sx, sy, 1 if t >= T_WORD_IN else 0, sc)
        if alive.any():
            if impact_t is None:
                balls[f, :, 0:2] = p
                balls[f, :, 2] = ang
                balls[f, :, 3:5] = 1
                balls[f, :, 5] = 1
            else:
                fp, fa = frozen
                for i in range(NB):
                    if flying[i]:
                        v[i, 1] += 2600 / FPS
                        p[i] += v[i] / FPS
                        ang[i] -= v[i, 0] / r[i] / FPS * 57.3
                        balls[f, i] = (p[i, 0], p[i, 1], ang[i], 1, 1, 1)
                    else:
                        y = FLOOR - (FLOOR - fp[i, 1]) * k_crush
                        x = 540 + (fp[i, 0] - 540) * (1 + 0.18 * (1 - k_crush))
                        balls[f, i] = (x, y, fa[i], min(1.7, 1 / k_crush ** 0.45), k_crush, 1)
        sdx = sdy = 0.0
        for (t0, amp, du) in shakes:
            if t0 <= t < t0 + du:
                a = amp * (1 - (t - t0) / du) ** 2
                sdx += a * math.sin(t * 91 + t0 * 7)
                sdy += a * math.cos(t * 77 + t0 * 3)
        shake[f] = (sdx, sdy)

    np.savez(BUILD / "sim.npz", pil=pil, word=word, balls=balls, block=block, shake=shake, r=r,
             meta=np.array([split_t, impact_t, pile_top0, PIL_W0, PIL_H0]))
    (BUILD / "events.json").write_text(json.dumps(events))
    print(f"split at {split_t:.2f}s, impact at {impact_t:.2f}s, pile top {pile_top0:.0f}, "
          f"{sum(e['type'] == 'pop' for e in events)} pops")


def set_pillow_size(w, h):
    global PIL_W0, PIL_H0
    PIL_W0, PIL_H0 = w, h


if __name__ == "__main__":
    import sys
    sz = BUILD / "pillow_size.json"
    if sz.exists():
        set_pillow_size(*json.loads(sz.read_text()))
    run()
