"""Folge 2 (neu): Oma Frieda geht zur Schule – Mobbing am Dixi-Klo, Judo-Fußfeger. ~63 s."""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "omafrieda"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import shots as S1  # noqa: E402
import shots2 as S2  # noqa: E402
import world as Wd  # noqa: E402
import world2 as W2  # noqa: E402
import world3 as W3  # noqa: E402
from chars import POSES, bonbon_sprite, head  # noqa: E402
from gfx import H, W, blur, cam, clamp01, ease_back, ease_io, ease_out, emoji, grade, lerp, paste_c  # noqa: E402
from world import View, actor, blink, mouth, view_bg  # noqa: E402

shake = S1.shake

# realistischeres Klassenzimmer für alle Klassenszenen
W2.board_static = W3.board3_static


def class_frame3(T, v, kids, post=(), blur_r=0.0, extra=()):
    f = view_bg(W3.class3_static(), W3.K, v, blur_r).copy()
    for k in W3.KIDS_BACK:
        W3.chair_back(f, v, k["x"], k["y"], k["D"])
        actor(f, v, **dict(k, pose="kid_desk", expr="neutral", blink=blink(T, k["x"]), look=(0.0, 0.1)))
        W3.desk3(f, v, k["x"], k["y"] + 1.0 * k["D"], 250, 170)
    for k in kids:
        W3.chair_back(f, v, k["x"], k["y"], k["D"])
    for k in kids:
        actor(f, v, **k)
    for k in kids:
        W3.desk3(f, v, k["x"], 1360, 290, 220)
    for e in extra:
        e(f, v)
    for p in post:
        p(f, v)
    return f


S2.class_frame = class_frame3
import importlib.util as _ilu  # noqa: E402
_spec = _ilu.spec_from_file_location("script_f2", str(Path(__file__).resolve().parent / "script.py"))
_sc = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_sc)
INS, R, R_end, at = _sc.INS, _sc.R, _sc.R_end, _sc.at
FREEZE_AT = 0.45

# ------------------------------------------------------------------ Positionen (Schulhof)
OMA = dict(who="oma", D=125)
ROW = dict(who="rowdy", D=112)       # Achtklässler 1
BUL = dict(who="bully2", D=112)      # Achtklässler 2
KLE = dict(who="kleiner", D=88)      # Fünftklässler
ROW_XY = (500, 1190)
BUL_XY = (360, 1172)
KLE_XY = (650, 1272)
OMA_FIGHT = (330, 1185)
DOOR1 = W3.dixi_door_center(0)
DOOR2 = W3.dixi_door_center(1)

# Zeitpunkte
GRAB_T = R(41.70)
GRIP_T = R(41.95)
STEP_T = R(42.15)
SWEEP_T = R(42.35)
SLAM_T = R(43.45)
RUN_T = R(45.55)
SLAM2_T = R(46.30)
BONBON_T = R(48.0)


def lerp_pose(a, b, u, base="oma_stand"):
    """Zwischenpose (quantisiert, damit der Sprite-Cache greift)."""
    u = round(clamp01(u) * 6) / 6
    pa, pb = POSES[a], POSES[b]

    def L(x, y):
        return (round(lerp(x[0], y[0], u), 2), round(lerp(x[1], y[1], u), 2))
    arms = tuple((L(ea, eb), L(ha, hb), mb) for (ea, ha, ma), (eb, hb, mb) in zip(pa["arms"], pb["arms"]))
    ov = [base, ("lower", pb["lower"]), ("arms", arms)]
    if pa.get("legs") and pb.get("legs"):
        legs = tuple(tuple(L(x, y) for x, y in zip(la, lb)) for la, lb in zip(pa["legs"], pb["legs"]))
        ov.append(("legs", legs))
    return tuple(ov)


def yard(T, v, acts=(), dixi=None, pre=(), post=(), blur_r=0.0):
    """Schulhof mit Dixi-Klos. dixi = dict(i: (door_open, red, shake))."""
    dixi = dixi or {}
    st = {0: (1.0, False, 0.0), 1: (0.0, False, 0.0)}
    st.update(dixi)
    f = view_bg(W3.yard3_static(), W3.K, v, blur_r).copy()
    for i in (1, 0):
        W3.draw_dixi(f, v, i, "back", *st[i])
        if i == 1:
            W3.draw_dixi(f, v, 1, "front", *st[1])
    for p in pre:
        p(f, v)
    behind = [a for a in acts if a.get("_dixi") == 0]
    for a in behind:
        actor(f, v, **{k: val for k, val in a.items() if k != "_dixi"})
    W3.draw_dixi(f, v, 0, "front", *st[0])
    for a in acts:
        if a.get("_dixi") == 0:
            continue
        actor(f, v, **{k: val for k, val in a.items() if k != "_dixi"})
    for p in post:
        p(f, v)
    W3.draw_flies(f, v, T, W3.DIXI[0]["fx"] - 10, W3.DIXI[0]["G"] - 380, n=3, radius=70, seed=3, size=14)
    return f


def rowdy_fall(u, m=0.9):
    """u 0..1: vom Fußfeger bis in die Dixi-Tür."""
    x0, y0 = ROW_XY[0], ROW_XY[1] + 1.1 * ROW["D"]
    x1, y1 = DOOR1[0] + 10, DOOR1[1] + 10
    e = ease_io(u)
    x = lerp(x0, x1, e)
    y = lerp(y0, y1, e) - 170 * math.sin(math.pi * min(1.0, u * 1.05))
    rot = -100 * ease_out(min(1.0, u * 1.4))
    pose = "b_trip" if u < 0.25 else "b_fall"
    return dict(ROW, pose=pose, x=x, y=y, rot=rot, center=True, expr="shock", mouth=m, mouth_kind="o",
                _dixi=0 if u > 0.8 else None)


# ------------------------------------------------------------------ HOOK
_cache = {}
HOOK_VIEW = (1.25, 560, 1250)


def hook_frame(t, with_oma=True):
    tt = min(t, FREEZE_AT)
    key = (round(tt * 30), with_oma)
    if key in _cache:
        return _cache[key].copy()
    u = 0.5 + 0.06 * tt / FREEZE_AT
    v = View(*HOOK_VIEW)
    acts = [dict(BUL, x=BUL_XY[0] - 120, y=BUL_XY[1] - 40, pose="b_hold", expr="shock", mouth=0.8, mouth_kind="o",
                 items=(("backpack", (0.8, -0.55)),)),
            dict(KLE, x=170, y=1290, pose="kid_stand", expr="shock", mouth=0.7, mouth_kind="o", look=(0.8, -0.3))]
    if with_oma:
        acts.append(dict(OMA, x=OMA_FIGHT[0], y=OMA_FIGHT[1], pose="oma_sweep", expr="smirk", look=(0.8, 0.0),
                         gl=0.1))
    acts.append(rowdy_fall(u))
    f = yard(28.0 + tt, v, acts)
    f = S1.dramatic(f, 0.4)
    _cache[key] = f
    return f.copy()


def shot_hook(t, T):
    f = hook_frame(t)
    if t >= FREEZE_AT:
        dt = t - FREEZE_AT
        f = cam(f, 1.04 + 0.03 * ease_out(dt / 0.15), 560, 900)
        f = grade(f, sat=0.75, contrast=1.08)
        if dt < 0.12:
            f.alpha_composite(Image.new("RGBA", f.size, (255, 255, 255, int(200 * (1 - dt / 0.12)))))
    else:
        f = cam(f, 1.04 + 0.06 * t, 560, 900)
    return f


def shot_hook_end(t, T):
    return shot_hook(FREEZE_AT + 0.13 + t, T) if t > 0.05 else shot_hook(FREEZE_AT + t, T)


def shot_hook_oma(t, T):
    bg = hook_frame(1.0, with_oma=False)
    bg = grade(blur(cam(bg, 1.25, 600, 900), 7), sat=0.55, contrast=0.95, bright=0.85)
    actor(bg, View(1.0 + 0.04 * t, 540, 1100), "oma", 300, "oma_stand", 540, 1330, expr="smirk", look=(0.0, 0.0),
          mouth=mouth("oma", T), blink=blink(T, 2), head_off=(0, 0, -4))
    return bg


def shot_rewind(t, T):
    v = View(*HOOK_VIEW)
    u = lerp(0.5, 0.0, t / 0.75)
    g = yard(T, v, [dict(OMA, x=OMA_FIGHT[0], y=OMA_FIGHT[1], pose=lerp_pose("oma_ready", "oma_sweep", 1 - t / 0.75)),
                    rowdy_fall(u, 0.3)])
    g = grade(g, sat=0.6, contrast=1.15)
    import numpy as np
    a = np.asarray(g.convert("RGB")).copy()
    a[..., 0] = np.roll(a[..., 0], 10, axis=1)
    a[..., 2] = np.roll(a[..., 2], -10, axis=1)
    a[::4] = (a[::4] * 0.75).astype("uint8")
    return Image.fromarray(a).convert("RGBA")


# ------------------------------------------------------------------ Morgens
def shot_arrive(t, T):
    v = View(1.0 + 0.05 * t, 540, 1080)
    x = lerp(140, 330, t / 1.65)
    bob = abs(math.sin(t * 8)) * -8
    return yard(T, v, [dict(OMA, x=x, y=1185 + bob, pose="oma_stand_bag", expr="smile", look=(0.5, -0.2),
                            items=(("bag", (0.62, 1.2)),), blink=blink(T, 1))], dixi={0: (0.0, False, 0.0)})


def shot_80(t, T):
    v = View(2.5 + 0.12 * t, 330, 1060)
    return yard(T, v, [dict(OMA, x=330, y=1185, pose="oma_stand_bag", expr="warm", look=(0.0, 0.0),
                            items=(("bag", (0.62, 1.2)),))], dixi={0: (0.0, False, 0.0)}, blur_r=6)


def board_oma(t, T, pose="oma_stand", **kw):
    v = View(2.0 + 0.06 * t, 470, 1000)
    d = dict(S2.OMA_B, pose=pose, expr=kw.pop("expr", "smirk"), mouth=mouth("oma", T), look=kw.pop("look", (0.0, 0.0)),
             blink=blink(T, 1))
    d.update(kw)
    return S2.frame(W2.board_static(), T, v, [d], post=(lambda f, vv: W2.board_text(f, vv, 99, 0, 1),), blur_r=3)


CLASS = ("girl", "gamer", "kleiner")


def klass(T, v, **over):
    kids = []
    for name in CLASS:
        kw = dict(pose="kid_desk", expr="neutral")
        kw.update(over.get(name, {}))
        kids.append(S2.kid(name, **kw))
    return S2.class_frame(T, v, kids)


def shot_class_shock(t, T):
    return klass(T, View(1.05, 540, 1080), girl=dict(expr="shock", mouth=0.6, mouth_kind="o"),
                 gamer=dict(expr="shock"), kleiner=dict(expr="shock", mouth=0.5, mouth_kind="o"))


def shot_girl(t, T):
    m = mouth("girl", T)
    return klass(T, View(2.2, 300, 1100), girl=dict(pose="kid_laugh", expr="smirk" if m > 0.1 else "laugh", mouth=m))


def shot_class_laugh(t, T):
    b = math.sin(T * 18) * 6
    return klass(T, View(1.05, 540, 1080), girl=dict(pose="kid_laugh", expr="laugh", mouth=0.8, mouth_kind="grin", y=1180 + b),
                 gamer=dict(pose="kid_laugh", expr="laugh", mouth=mouth("gamer", T), mouth_kind="grin", y=1175 - b),
                 kleiner=dict(expr="smile"))


def shot_enkel(t, T):
    return board_oma(t, T, "oma_stand", expr="smirk", brow_up=1 if t > 0.9 else 0)


def shot_silence(t, T):
    return klass(T, View(1.1, 540, 1080), girl=dict(expr="shock", mouth_kind="flat"), gamer=dict(expr="sad"),
                 kleiner=dict(expr="smile"))


def shot_throw(t, T):
    v = View(1.05, 540, 1080)
    f = klass(T, v, girl=dict(expr="shock"), gamer=dict(pose="kid_throw", expr="sneaky", mouth_kind="grin"),
              kleiner=dict(expr="scared"))
    u = clamp01((t - 0.25) / 0.4)
    if u > 0:
        S2.paper_ball(f, *v.p(lerp(560, 1150, u), lerp(980, 760, u) - 160 * 4 * u * (1 - u)), 26 * v.z * (1 + u))
    return f


def shot_catch(t, T):
    return S2.shot_catch(t * 1.0, T)


def shot_sport(t, T):
    v = View(2.0, 470, 1000)
    f = S2.frame(W2.board_static(), T, v, [dict(S2.OMA_B, pose="oma_catch", expr="smirk", mouth=mouth("oma", T),
                                                brow_up=1, look=(0.0, 0.0))],
                 post=(lambda ff, vv: W2.board_text(ff, vv, 99, 0, 1),), blur_r=3)
    hx, hy = S2.OMA_B["x"] + 1.05 * S2.OMA_B["D"], S2.OMA_B["y"] - 0.2 * S2.OMA_B["D"]
    d = ImageDraw.Draw(f)
    a, b = v.p(hx, hy), v.p(hx + 30, hy - 150)
    d.line([a, b], fill=(200, 205, 220), width=int(8 * v.z))
    S2.paper_ball(f, *v.p(hx + 22, hy - 110), 30 * v.z)
    return f


def shot_wow(t, T):
    return klass(T, View(1.1, 540, 1080), girl=dict(expr="shock", mouth=0.8, mouth_kind="o"),
                 gamer=dict(expr="shock", mouth=0.9, mouth_kind="o"), kleiner=dict(pose="kid_cheer", expr="laugh",
                                                                                   mouth=0.7, mouth_kind="grin"))


def shot_phone_game(t, T):
    return S2.shot_phone_game(t, T)


def shot_phone_take(t, T):
    return S2.shot_phone_take(t, T)


def shot_phone_sock(t, T):
    return S2.shot_phone_sock(t, T)


def shot_phone_cry(t, T):
    return S2.shot_phone_cry(t, T)


def shot_klo(t, T):
    m = mouth("girl", T)
    return klass(T, View(2.0, 320, 1090), girl=dict(pose="kid_reach", expr="neutral", mouth=m, look=(0.6, -0.4)),
                 gamer=dict(expr="laugh", mouth_kind="grin"))


def shot_kaputt(t, T):
    return board_oma(t, T, "oma_stand", expr="glare", gl=0.12, look=(0.6, 0.0))


def shot_bullies_outside(t, T):
    v = View(1.55, 640, 1250)
    kick = (t % 0.6) < 0.15
    return S1.dramatic(yard(T, v, [
        dict(BUL, x=520, y=BUL_XY[1], pose="b_push" if kick else "b_stand", expr="arrogant", mouth_kind="grin"),
        dict(ROW, x=ROW_XY[0] - 160, y=ROW_XY[1], pose="b_stand", expr="laugh", mouth=0.6, mouth_kind="grin")],
        dixi={0: (0.0, False, 6.0 if kick else 0.0)}), 0.4)


def shot_pause(t, T):
    v = View(1.05, 540, 1130)
    f = yard(T, v, [dict(KLE, x=lerp(160, 520, t / 2.2), y=1272, pose="kid_stand", expr="smile", look=(0.6, 0.0),
                         items=(("backpack", (0.0, 0.1)),)),
                    dict(BUL, x=BUL_XY[0], y=BUL_XY[1], pose="b_stand", expr="sneaky", look=(0.6, 0.2)),
                    dict(ROW, x=ROW_XY[0] + 120, y=ROW_XY[1], pose="b_stand", expr="sneaky", look=(-0.6, 0.2))])
    if t < 0.9:
        S2.bell(f, t)
    return f


def mob_acts(T, m_row=0.0, kle_expr="scared", kle_m=0.0, push=True):
    return [dict(BUL, x=BUL_XY[0], y=BUL_XY[1], pose="b_hold", expr="laugh", mouth=0.5, mouth_kind="grin",
                 items=(("backpack", (0.8, -0.55)),), look=(0.6, 0.0)),
            dict(ROW, x=ROW_XY[0], y=ROW_XY[1], pose="b_push" if push else "b_stand", expr="arrogant", mouth=m_row,
                 mouth_kind="grin" if m_row < 0.1 else None, look=(0.7, 0.2)),
            dict(KLE, x=KLE_XY[0], y=KLE_XY[1], pose="kid_reach", expr=kle_expr, mouth=kle_m, look=(-0.7, -0.3))]


def shot_mob_wide(t, T):
    v = View(1.35, 560, 1230)
    return S1.dramatic(yard(T, v, mob_acts(T, mouth("rowdy", T))), 0.5)


def shot_mob_close(t, T):
    v = View(2.0, 560, 1170)
    return S1.dramatic(yard(T, v, mob_acts(T, mouth("rowdy", T))), 0.5)


def shot_kleiner(t, T):
    v = View(2.6, KLE_XY[0], 1250)
    return S1.dramatic(yard(T, v, mob_acts(T, 0.0, "sad", mouth("kleiner", T)), blur_r=3), 0.4)


def shot_oma_enters(t, T):
    v = View(1.3, 480, 1220)
    x = lerp(60, 230, ease_out(t / 0.8))
    acts = mob_acts(T, 0.0, "scared", 0.0, push=False)
    acts.append(dict(OMA, x=x, y=1185, pose="oma_stand_bag", expr="glare", gl=0.12, mouth=mouth("oma", T),
                     look=(0.8, 0.0), items=(("bag", (0.62, 1.2)),)))
    return S1.dramatic(yard(T, v, acts), 0.5)


def shot_mutig(t, T):
    v = View(2.0, 430, 1150)
    acts = [dict(BUL, x=BUL_XY[0], y=BUL_XY[1], pose="b_hold", expr="neutral", items=(("backpack", (0.8, -0.55)),),
                 look=(-0.8, 0.0)),
            dict(ROW, x=ROW_XY[0], y=ROW_XY[1], pose="b_stand", expr="neutral", look=(-0.8, 0.0))]
    return S1.dramatic(yard(T, v, acts, blur_r=0), 0.5)


def shot_raus(t, T):
    v = View(1.9, 430, 1170)
    acts = [dict(OMA, x=OMA_FIGHT[0] - 60, y=OMA_FIGHT[1], pose="oma_stand_bag", expr="glare", gl=0.12, look=(0.8, 0.0),
                 items=(("bag", (0.62, 1.2)),)),
            dict(ROW, x=ROW_XY[0], y=ROW_XY[1], pose="b_point", expr="arrogant", mouth=mouth("rowdy", T),
                 look=(-0.8, 0.0))]
    return S1.dramatic(yard(T, v, acts), 0.5)


def shot_achtzig(t, T):
    v = View(2.5 + 0.1 * t, OMA_FIGHT[0] - 30, 1080)
    acts = [dict(OMA, x=OMA_FIGHT[0] - 60, y=OMA_FIGHT[1], pose="oma_ready", expr="smirk", mouth=mouth("oma", T),
                 look=(0.0, 0.0), brow_up=1 if t > 0.8 else 0)]
    return S1.dramatic(yard(T, v, acts, blur_r=4), 0.5)


def shot_eyes(t, T):
    return S2.shot_oma_eyes(t, T)


def fight_acts(T, cam_slow=False):
    """Choreografie: Griff -> Schritt -> Fußfeger -> Zug; der Rowdy kippt rückwärts ins Dixi."""
    oma = dict(OMA, x=OMA_FIGHT[0], y=OMA_FIGHT[1], expr="smirk", look=(0.8, 0.0), gl=0.1)
    if T < GRIP_T:
        oma["pose"] = lerp_pose("oma_ready", "oma_grip", (T - GRAB_T) / (GRIP_T - GRAB_T))
    elif T < STEP_T:
        oma["pose"] = lerp_pose("oma_grip", "oma_step", (T - GRIP_T) / (STEP_T - GRIP_T))
    elif T < SWEEP_T:
        oma["pose"] = lerp_pose("oma_step", "oma_sweep", (T - STEP_T) / (SWEEP_T - STEP_T))
    elif T < SWEEP_T + 0.35:
        oma["pose"] = "oma_sweep"
    else:
        oma["pose"] = lerp_pose("oma_sweep", "oma_pull", (T - SWEEP_T - 0.35) / 0.4)
    acts = [dict(BUL, x=BUL_XY[0] - 120, y=BUL_XY[1] - 40, pose="b_hold", expr="shock" if T > SWEEP_T else "neutral",
                 mouth=0.8 if T > SWEEP_T else 0, mouth_kind="o" if T > SWEEP_T else None,
                 items=(("backpack", (0.8, -0.55)),), look=(0.6, 0.2)),
            dict(KLE, x=170, y=1290, pose="kid_stand", expr="shock" if T > SWEEP_T else "scared",
                 mouth=0.7 if T > SWEEP_T else 0, mouth_kind="o" if T > SWEEP_T else None, look=(0.8, -0.2))]
    if T < SWEEP_T:
        acts.append(dict(ROW, x=ROW_XY[0], y=ROW_XY[1], pose="b_grab", expr="arrogant" if T < GRIP_T else "shock",
                         look=(-0.8, 0.0)))
    elif T < SLAM_T:
        u = (T - SWEEP_T) / (SLAM_T - SWEEP_T - 0.05)
        acts.append(rowdy_fall(min(1.0, u), mouth("rowdy", T)))
    acts.append(oma)
    return acts


def dixi_state(T):
    d0 = (1.0, False, 0.0)
    if T >= SLAM_T:
        dt = T - SLAM_T
        d0 = (max(0.0, 1 - dt / 0.08), True, math.sin(dt * 60) * 8 * max(0.0, 1 - dt / 0.6))
    d1 = (0.0, False, 0.0)
    if T >= RUN_T - 0.3:
        d1 = (1.0, False, 0.0)
    if T >= SLAM2_T:
        dt = T - SLAM2_T
        d1 = (max(0.0, 1 - dt / 0.08), True, math.sin(dt * 60) * 6 * max(0.0, 1 - dt / 0.6))
    return {0: d0, 1: d1}


def sweep_fx(T):
    def fn(f, v):
        dt = T - SWEEP_T
        if 0 <= dt < 0.4:
            fx, fy = v.p(OMA_FIGHT[0] + 1.12 * OMA["D"], OMA_FIGHT[1] + 2.45 * OMA["D"])
            d = ImageDraw.Draw(f, "RGBA")
            r = (30 + 260 * dt) * v.z
            d.ellipse([fx - r, fy - r * 0.45, fx + r, fy + r * 0.45], outline=(255, 255, 255, int(230 * (1 - dt / 0.4))),
                      width=int(6 * v.z))
            for k in range(7):
                a = -math.pi + k * math.pi / 6
                d.line([(fx + math.cos(a) * r * 0.5, fy + math.sin(a) * r * 0.25),
                        (fx + math.cos(a) * r * 1.1, fy + math.sin(a) * r * 0.55)],
                       fill=(255, 240, 160, int(220 * (1 - dt / 0.4))), width=int(5 * v.z))
        # Bewegungsbogen des fegenden Fußes
        if STEP_T <= T < SWEEP_T + 0.15:
            d = ImageDraw.Draw(f, "RGBA")
            cx, cy = v.p(OMA_FIGHT[0] + 0.5 * OMA["D"], OMA_FIGHT[1] + 2.6 * OMA["D"])
            r = 0.7 * OMA["D"] * v.z
            d.arc([cx - r, cy - r * 0.5, cx + r, cy + r * 0.5], 300, 20, fill=(255, 255, 255, 150), width=int(8 * v.z))
    return fn


def shot_fight1(t, T):
    v = View(1.75, 470, 1250)
    return S1.dramatic(yard(T, v, fight_acts(T), dixi=dixi_state(T), post=(sweep_fx(T),)), 0.5)


def shot_fight2(t, T):
    v = View(1.3, 580, 1260)
    f = S1.dramatic(yard(T, v, fight_acts(T), dixi=dixi_state(T), post=(sweep_fx(T),)), 0.5)
    if T - SWEEP_T < 0.06:
        f.alpha_composite(Image.new("RGBA", f.size, (255, 255, 255, 120)))
    return grade(f, sat=0.92, contrast=1.06)


def shot_slam(t, T):
    sh = shake(T, 14 * clamp01(1 - (T - SLAM_T) / 0.4))
    v = View(1.9, 800, 1300, sh)
    return S1.dramatic(yard(T, v, [], dixi=dixi_state(T)), 0.4)


def shot_bully2_shock(t, T):
    v = View(2.3, BUL_XY[0] - 120, 1130)
    return S1.dramatic(yard(T, v, [dict(BUL, x=BUL_XY[0] - 120, y=BUL_XY[1] - 40, pose="b_hold", expr="shock", mouth=0.8,
                                        mouth_kind="o", items=(("backpack", (0.8, -0.55)),))], dixi=dixi_state(T),
                            blur_r=3), 0.4)


def shot_duauch(t, T):
    v = View(2.0, OMA_FIGHT[0] + 40, 1100)
    return S1.dramatic(yard(T, v, [dict(OMA, x=OMA_FIGHT[0], y=OMA_FIGHT[1], pose="oma_ready", expr="smirk", brow_up=1,
                                        mouth=mouth("oma", T), look=(-0.6, 0.0))], dixi=dixi_state(T), blur_r=3), 0.4)


def shot_run(t, T):
    v = View(1.3, 520, 1200)
    m = mouth("bully2", T)
    acts = [dict(OMA, x=OMA_FIGHT[0], y=OMA_FIGHT[1], pose="oma_ready", expr="smirk", look=(0.0, 0.0)),
            dict(KLE, x=170, y=1290, pose="kid_stand", expr="shock", look=(0.6, -0.2))]
    if T < RUN_T:
        acts.append(dict(BUL, x=BUL_XY[0] - 120, y=BUL_XY[1] - 40, pose="b_hold", expr="scared", mouth=m,
                         items=(("backpack", (0.8, -0.55)),)))
    elif T < SLAM2_T:
        u = (T - RUN_T) / (SLAM2_T - RUN_T)
        x = lerp(BUL_XY[0] - 120, DOOR2[0], ease_io(u))
        y = lerp(BUL_XY[1] - 40, DOOR2[1] - 1.0 * 92, ease_io(u)) - abs(math.sin(u * 14)) * 12
        acts.append(dict(BUL, D=lerp(112, 92, u), x=x, y=y, pose="b_run", expr="scared", mouth=m))
    post = ()
    if T >= RUN_T:
        def bag_drop(f, vv):
            from chars import backpack
            im = Image.new("RGBA", (int(80 * vv.z), int(90 * vv.z)), (0, 0, 0, 0))
            backpack(im, im.width / 2, 6 * vv.z, 100 * vv.z)
            paste_c(f, im, *vv.p(BUL_XY[0] - 60, 1440))
        post = (bag_drop,)
    return S1.dramatic(yard(T, v, acts, dixi=dixi_state(T), post=post), 0.4)


def shot_knock(t, T):
    v = View(1.9, 720, 1250)
    knock = (t % 0.5) < 0.12 and T < BONBON_T
    acts = [dict(OMA, x=640, y=1185, pose="oma_knock" if knock or T < BONBON_T else "oma_ready", expr="warm",
                 mouth=mouth("oma", T), look=(0.6, 0.0))]

    def bon(f, vv):
        if T >= BONBON_T:
            u = clamp01((T - BONBON_T) / 0.5)
            paste_c(f, bonbon_sprite(int(26 * vv.z), (235, 60, 60), int(u * 360) // 30 * 30 % 360),
                    *vv.p(lerp(700, 790, u), lerp(1500, 1485, u)))
            if T > BONBON_T + 0.7:
                # Hand von drinnen schnappt es
                hx, hy = vv.p(780, 1480)
                Wd.ell(f, hx, hy, 18 * vv.z, 14 * vv.z, (242, 198, 168), amb=0.5)
    return S1.dramatic(yard(T, v, acts, dixi=dixi_state(T), post=(bon,)), 0.4)


def shot_mutig_end(t, T):
    v = View(1.6, 300, 1200)
    gave = T > R(51.2)
    kle = dict(KLE, x=180, y=1280, pose="kid_cheer" if gave else "kid_reach", expr="laugh" if gave else "sad",
               look=(0.7, -0.4), items=(("backpack", (0.7, -0.6)),) if gave else (), mouth=0.5 if gave else 0,
               mouth_kind="grin" if gave else None)
    oma = dict(OMA, x=400, y=1185, pose="oma_give_bag" if not gave else "oma_ready", expr="warm",
               mouth=mouth("oma", T), look=(-0.7, 0.3), items=(("backpack", (-1.05, 0.5)),) if not gave else ())
    return yard(T, v, [kle, oma], dixi=dixi_state(T))


def shot_mutig_close(t, T):
    v = View(2.4, 400, 1080)
    return yard(T, v, [dict(OMA, x=400, y=1185, pose="oma_ready", expr="warm", mouth=mouth("oma", T),
                            look=(-0.5, 0.2), brow_up=0)], dixi=dixi_state(T), blur_r=4)


def shot_danke(t, T):
    v = View(2.5, 180, 1230)
    m = mouth("kleiner", T)
    f = yard(T, v, [dict(KLE, x=180, y=1280, pose="kid_cheer", expr="laugh", mouth=max(m, 0.3),
                         mouth_kind="grin" if m < 0.1 else None, items=(("backpack", (0.7, -0.6)),))],
             dixi=dixi_state(T), blur_r=5)
    hearts = emoji("💛", 70)
    for k in range(3):
        ph = (t * 0.8 + k * 0.33) % 1
        paste_c(f, hearts, 300 + k * 230, 900 - ph * 300, 0.8 + 0.3 * ph, 1 - ph)
    return f


def hero2(t, T):
    sh = shake(T, 12 * clamp01(1 - (T - R(57.9)) / 0.35)) if T > R(57.9) else (0, 0)
    return S1.hero_frame(t + 1, T, 400, (540 + sh[0], 1330 + sh[1]), 1.0 + 0.03 * t)


_OLD_SHOTS = [
    (0.00, 0.90, shot_hook),
    (0.90, 2.20, shot_hook_oma),
    (2.20, 2.95, shot_rewind),
    (2.95, 4.60, shot_arrive),
    (4.60, 5.90, shot_80),
    (5.90, 7.30, S2.shot_board),
    (7.30, 8.40, shot_class_shock),
    (8.40, 9.90, shot_girl),
    (9.90, 11.00, shot_class_laugh),
    (11.00, 12.50, shot_enkel),
    (12.50, 13.85, shot_silence),
    (13.85, 14.50, shot_throw),
    (14.50, 15.10, shot_catch),
    (15.10, 16.70, shot_sport),
    (16.70, 17.30, shot_wow),
    (17.30, 18.00, shot_phone_game),
    (18.00, 19.20, shot_phone_take),
    (19.20, 21.00, shot_phone_sock),
    (21.00, 21.85, shot_phone_cry),
    (21.85, 24.50, shot_klo),
    (24.50, 25.90, shot_kaputt),
    (25.90, 27.40, shot_bullies_outside),
    (27.40, 29.60, shot_pause),
    (29.60, 30.80, shot_mob_wide),
    (30.80, 32.00, shot_mob_close),
    (32.00, 33.20, shot_kleiner),
    (33.20, 35.20, shot_oma_enters),
    (35.20, 37.15, shot_mutig),
    (37.15, 38.55, shot_raus),
    (38.55, 40.10, shot_achtzig),
    (40.10, 41.70, shot_eyes),
    (41.70, 42.35, shot_fight1),
    (42.35, 43.45, shot_fight2),
    (43.45, 43.95, shot_slam),
    (43.95, 44.65, shot_bully2_shock),
    (44.65, 45.45, shot_duauch),
    (45.45, 46.90, shot_run),
    (46.90, 49.90, shot_knock),
    (49.90, 52.40, shot_mutig_end),
    (52.40, 54.80, shot_mutig_close),
    (54.80, 56.30, shot_danke),
    (56.30, 57.70, S1.shot_hero),
    (57.70, 59.40, hero2),
    (59.40, 62.60, S1.shot_end),
    (62.60, 63.10, shot_hook_end),
]


# ------------------------------------------------------------------ Zusätzliche Gags (Einschübe)
def stink(f, v, T, i=0, strength=1.0):
    """Weiche, durchscheinende Geruchsschwaden + Fliegen über dem Dixi."""
    p = W3.DIXI[i]
    lay = Image.new("RGBA", f.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay, "RGBA")
    for k in range(4):
        ph = (T * 0.45 + k / 4) % 1
        x0 = p["fx"] - 80 + k * 45
        pts = []
        for j in range(14):
            u = j / 13
            pts.append(v.p(x0 + math.sin(u * 6 + T * 2.2 + k) * 16, p["G"] - 350 - u * 170 - ph * 50))
        d.line(pts, fill=(150, 175, 95, int(80 * strength * (1 - ph))), width=int(14 * v.z), joint="curve")
    f.alpha_composite(lay.filter(ImageFilter.GaussianBlur(6 * v.z)))
    W3.draw_flies(f, v, T, p["fx"] - 20, p["G"] - 400, n=6, radius=90, seed=7 + i, size=16)

def shot_sniff(t, T):
    v = View(1.9, 740, 1210)
    m = mouth("oma", T)
    x = lerp(560, 640, ease_out(t / 0.6))
    oma = dict(OMA, x=x, y=1185, pose="oma_stand_bag", expr="sad" if t > 0.3 else "smile", mouth=m,
               look=(0.7, -0.3), items=(("bag", (0.62, 1.2)),), head_off=(0, 0, 6 if t > 0.3 else 0))
    return yard(T, v, [oma], dixi={0: (0.0, False, 0.0)}, post=(lambda f, vv: stink(f, vv, T, 0, 1.0),))


def shot_rollcall(t, T):
    return board_oma(t, T, "oma_stand", expr="neutral", look=(0.3, 0.0), gl=0.12)


def shot_hand_up(t, T):
    up = t < 0.55
    return klass(T, View(1.2, 540, 1080), gamer=dict(pose="kid_reach" if up else "kid_desk",
                                                     expr="neutral" if up else "shock", look=(0.6, -0.3)),
                 girl=dict(expr="laugh" if not up else "smirk", mouth=0.6 if not up else 0, mouth_kind="grin"),
                 kleiner=dict(expr="smile", look=(-0.7, 0.0)))


def shot_age_q(t, T):
    m = mouth("girl", T)
    return klass(T, View(2.1, 300, 1100), girl=dict(pose="kid_reach", expr="neutral", mouth=m, look=(0.5, -0.4)))


def shot_age_a(t, T):
    return board_oma(t, T, "oma_stand", expr="smirk", look=(-0.3, 0.0), brow_up=1 if t > 1.0 else 0)


def shot_faust_q(t, T):
    m = mouth("gamer", T)
    return klass(T, View(2.2, 540, 1100), gamer=dict(pose="kid_reach", expr="neutral", mouth=m, look=(0.0, -0.5)),
                 girl=dict(expr="smile"), kleiner=dict(expr="neutral"))


def shot_faust_a(t, T):
    v = View(2.1 + 0.08 * t, 480, 990)
    pose = ("oma_stand", ("arms", (((-0.62, 0.7), (-0.6, 1.25), "front"), ((0.75, 0.2), (0.75, -0.25), "fist"))))
    f = S2.frame(W2.board_static(), T, v, [dict(S2.OMA_B, pose=pose, expr="smirk", mouth=mouth("oma", T),
                                                look=(0.0, 0.0), brow_up=1)],
                 post=(lambda ff, vv: W2.board_text(ff, vv, 99, 0, 1),), blur_r=3)
    if t > 1.2:
        e = emoji("😳", 110)
        paste_c(f, e, 860, 1500, S1.Wd_pop(t - 1.2))
    return f


def shot_gulp(t, T):
    return klass(T, View(1.1, 540, 1080), girl=dict(expr="scared"), gamer=dict(expr="scared", sweat=True),
                 kleiner=dict(expr="shock", mouth=0.5, mouth_kind="o"))


def shot_stricken_q(t, T):
    v = View(2.1, ROW_XY[0], 1150)
    acts = [dict(ROW, x=ROW_XY[0], y=ROW_XY[1], pose="b_point", expr="arrogant", mouth=mouth("rowdy", T),
                 mouth_kind="grin" if mouth("rowdy", T) < 0.1 else None, look=(-0.8, 0.0))]
    return S1.dramatic(yard(T, v, acts, blur_r=2), 0.5)


def shot_stricken_a(t, T):
    v = View(2.3 + 0.08 * t, OMA_FIGHT[0] - 40, 1110)
    acts = [dict(OMA, x=OMA_FIGHT[0] - 60, y=OMA_FIGHT[1], pose="oma_knit_stand", expr="smirk", mouth=mouth("oma", T),
                 look=(0.0, 0.0), items=(("knit", (0, 1.0)),), knit_phase=round((T * 5) % 1.0, 1),
                 brow_up=1 if t > 1.2 else 0)]
    return S1.dramatic(yard(T, v, acts, blur_r=4), 0.5)


def shot_besetzt(t, T):
    v = View(1.9, 700, 1230)
    dust = (t % 0.4) < 0.2
    pose = ("oma_stand", ("arms", (((-0.5, 0.75), (0.05 if dust else -0.1, 1.05), "front"),
                                   ((0.5, 0.75), (-0.05 if dust else 0.1, 1.0), "front"))))
    acts = [dict(OMA, x=560, y=1185, pose=pose, expr="smirk", mouth=mouth("oma", T), look=(0.8, -0.3), brow_up=1)]
    return S1.dramatic(yard(T, v, acts, dixi=dixi_state(T), post=(lambda f, vv: stink(f, vv, T, 0, 0.7),)), 0.4)


def shot_muffled(t, T):
    sh = math.sin(T * 40) * 3 if mouth("dixi", T) > 0.1 else 0.0
    v = View(2.3, 830, 1260)
    d = dixi_state(T)
    d[0] = (d[0][0], d[0][1], sh)
    f = S1.dramatic(yard(T, v, [], dixi=d, post=(lambda ff, vv: stink(ff, vv, T, 0, 0.6),)), 0.4)
    e = emoji("💬", 120)
    paste_c(f, e, 700, 760, S1.Wd_pop(t - 0.1))
    return f


def shot_morgen_q(t, T):
    v = View(2.5, 180, 1230)
    m = mouth("kleiner", T)
    return yard(T, v, [dict(KLE, x=180, y=1280, pose="kid_stand", expr="smile", mouth=m, look=(0.7, -0.5),
                            items=(("backpack", (0.0, 0.1)),))], dixi=dixi_state(T), blur_r=5)


def shot_morgen_a(t, T):
    v = View(2.4 + 0.06 * t, 400, 1080)
    return yard(T, v, [dict(OMA, x=400, y=1185, pose="oma_ready", expr="smirk", mouth=mouth("oma", T),
                            look=(-0.4, 0.1), brow_up=1 if t > 0.9 else 0, blink=t > 1.6 and t < 1.75)],
                dixi=dixi_state(T), blur_r=4)


INSERTS = [
    [(0.0, 2.4, shot_sniff)],
    [(0.0, 2.7, shot_rollcall), (2.7, 3.55, shot_hand_up), (3.55, 5.9, shot_age_q), (5.9, 8.45, shot_age_a),
     (8.45, 10.3, shot_faust_q), (10.3, 12.0, shot_faust_a), (12.0, 12.6, shot_gulp)],
    [(0.0, 2.15, shot_stricken_q), (2.15, 4.8, shot_stricken_a)],
    [(0.0, 1.2, shot_besetzt)],
    [(0.0, 1.4, shot_muffled)],
    [(0.0, 1.7, shot_morgen_q), (1.7, 3.8, shot_morgen_a)],
]


def _build():
    out = [(R(a) if a > 0 else 0.0, R_end(b), fn) for a, b, fn in _OLD_SHOTS]
    for k, (p, dur) in enumerate(INS):
        base = R_end(p)
        for a, b, fn in INSERTS[k]:
            out.append((round(base + a, 3), round(base + b, 3), fn))
    out.sort(key=lambda s: s[0])
    return out


SHOTS = _build()


def shot_at(T):
    for i, (a, b, fn) in enumerate(SHOTS):
        if a <= T < b or (i == len(SHOTS) - 1 and T >= a):
            return i, a, b, fn
    return len(SHOTS) - 1, *SHOTS[-1]
