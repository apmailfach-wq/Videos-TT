"""Traffic models for the shots. All return arrays sampled at FPS."""
import numpy as np

FPS = 30


def overreact_lane(n=40, v_init=24.0, t_end=20.0, tb=1.5, tau=0.9, d0=7.0,
                   gain=1.38, y_lead=0.0, lengths=None, min_gap=3.5):
    """Each driver reacts tau later than the one in front and brakes harder
    (gain). Initial gaps are chosen so nobody collides."""
    if lengths is None:
        lengths = np.full(n, 4.6)
    sub = 4
    dt = 1.0 / FPS / sub
    ts = np.arange(int(t_end * FPS * sub)) * dt
    V = np.zeros((len(ts), n))
    for i in range(n):
        depth = min(v_init, d0 * gain ** i)
        dec = min(8.0, 3.5 * 1.18 ** i)
        rise = depth / dec
        plateau = 0.2 + 0.45 * i if depth >= v_init else 0.2 + 0.15 * i
        rel = depth / 1.6
        t0 = tb + i * tau
        x = ts - t0
        dip = np.where(x < 0, 0,
              np.where(x < rise, depth * x / rise,
              np.where(x < rise + plateau, depth,
              np.where(x < rise + plateau + rel, depth * (1 - (x - rise - plateau) / rel), 0))))
        V[:, i] = v_init - dip
    D = np.cumsum(V, axis=0) * dt                      # distance travelled
    # gaps: choose initial spacing so min gap >= min_gap
    y0 = np.zeros(n); y0[0] = y_lead
    for i in range(1, n):
        rel_motion = D[:, i - 1] - D[:, i]             # how gap changes
        need = min_gap + lengths[i - 1] - rel_motion.min()
        base = 1.2 * v_init + lengths[i - 1]           # ~1.2 s headway
        y0[i] = y0[i - 1] - max(need, base)
    Y = y0[None, :] + D
    A = np.gradient(V, dt, axis=0)
    k = sub
    return Y[::k], V[::k], A[::k]


if __name__ == "__main__":
    Y, V, A = overreact_lane()
    gaps = Y[:, :-1] - Y[:, 1:] - 4.6
    print("min gap %.1f" % gaps.min(), "init spacing", np.round(Y[0, :12] - np.roll(Y[0, :12], -1), 1)[:11])
    for i in range(0, 14):
        print(i, "vmin %.1f" % V[:, i].min(), "t_stop %.1f" % (V[:, i].argmin() / FPS), "len standing %.1f" % ((V[:, i] < 0.5).sum() / FPS))
