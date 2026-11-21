"""Einstellungen für Folge 2 – Oma Frieda geht zur Schule. Jede Funktion: (t_lokal, T_global) -> RGBA-Frame."""
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "omafrieda"))
import shots as S1  # noqa: E402
import world as Wd  # noqa: E402
import world2 as W2  # noqa: E402
from chars import bonbon_sprite, head, person  # noqa: E402
from gfx import (H, W, blur, cam, clamp01, ease_back, ease_in, ease_io, ease_out, emoji, grade, lerp,  # noqa: E402
                 paste_c, vignette)
from world import View, actor, blink, mouth, view_bg  # noqa: E402

shake = S1.shake
FREEZE_AT = 0.45
HOOK_VIEW = (1.08, 520, 1180)


def bright(f, amt=1.0):
    f = grade(f, sat=1.08, contrast=1.04, bright=1.03, warm=0.1 * amt)
    f.alpha_composite(vignette(0.3))
    return f


def frame(static, T, v, actors=(), pre=(), post=(), blur_r=0.0):
    f = view_bg(static, W2.K, v, blur_r).copy()
    for p in pre:
        p(f, v)
    for a in actors:
        actor(f, v, **a)
    for p in post:
        p(f, v)
    return f


# Positionen Schulhof
OMA_Y = dict(who="oma", D=125, x=820, y=1180)
ROW_D = 105
ROW_POS = (650, 1235)
KLE = dict(who="kleiner", D=92, x=520, y=1300)


def rowdy_fly(s, m=0.9):
    x, y = W2.fly_pos(s)
    return dict(who="rowdy", D=ROW_D, pose="rowdy_fly", x=x, y=y, rot=W2.fly_rot(s), center=True, expr="shock",
                mouth=m, items=(("sandwich", (1.2, -0.35)),))


def sandwich_fly(s):
    def fn(f, v):
        if s < 0.25:
            return
        x, y = W2.fly_pos(s - 0.12)
        im = Image.new("RGBA", (int(160 * v.z), int(120 * v.z)), (0, 0, 0, 0))
        from chars import sandwich
        sandwich(im, im.width / 2, im.height / 2, 110 * v.z)
        paste_c(f, im, *v.p(x + 60, y - 120), 1.0, 1.0, s * 300)
    return fn


_cache = {}


def hook_frame(t, with_oma=True):
    tt = min(t, FREEZE_AT)
    key = (round(tt * 30), with_oma)
    if key in _cache:
        return _cache[key].copy()
    s = 0.47 + 0.03 * tt / FREEZE_AT
    Tsim = 28.2 + tt * 0.3
    v = View(*HOOK_VIEW)
    acts = [dict(KLE, pose="kid_stand", expr="shock", mouth=0.8, mouth_kind="o", look=(-0.6, -0.6))]
    if with_oma:
        acts.append(dict(OMA_Y, pose="oma_knit_stand", expr="smile", look=(0.0, 0.6), items=(("knit", (0, 1.0)),),
                         knit_phase=0.3))
    acts.append(rowdy_fly(s))
    f = frame(W2.yard_static(), Tsim, v, acts, post=(sandwich_fly(s),))
    f = S1.dramatic(f, 0.5)
    _cache[key] = f
    return f.copy()


def shot_hook(t, T):
    f = hook_frame(t)
    if t >= FREEZE_AT:
        dt = t - FREEZE_AT
        f = cam(f, 1.05 + 0.03 * ease_out(dt / 0.15), 480, 760)
        f = grade(f, sat=0.75, contrast=1.08)
        if dt < 0.12:
            f.alpha_composite(Image.new("RGBA", f.size, (255, 255, 255, int(200 * (1 - dt / 0.12)))))
    else:
        f = cam(f, 1.05 + 0.06 * t, 480, 760)
    return f


def shot_hook_end(t, T):
    return shot_hook(FREEZE_AT + 0.13 + t, T) if t > 0.05 else shot_hook(FREEZE_AT + t, T)


def shot_hook_oma(t, T):
    bg = hook_frame(1.0, with_oma=False)
    bg = grade(blur(cam(bg, 1.3, 480, 820), 7), sat=0.55, contrast=0.95, bright=0.85)
    actor(bg, View(1.0 + 0.04 * t, 540, 1100), "oma", 300, "oma_knit_stand", 540, 1330, expr="smirk",
          look=(0.0, 0.0), mouth=mouth("oma", T), blink=blink(T, 2), items=(("knit", (0, 1.0)),), head_off=(0, 0, -4))
    return bg


def shot_rewind(t, T):
    s = lerp(0.5, 0.0, t / 0.75)
    v = View(*HOOK_VIEW)
    f = frame(W2.yard_static(), T, v, [dict(KLE, pose="kid_stand", expr="shock"),
                                       dict(OMA_Y, pose="oma_knit_stand", expr="smile", items=(("knit", (0, 1.0)),)),
                                       rowdy_fly(s, 0.4)])
    f = grade(f, sat=0.6, contrast=1.15, bright=0.95)
    a = np.asarray(f.convert("RGB")).copy()
    r = random.Random(int(T * 30))
    a[..., 0] = np.roll(a[..., 0], 10, axis=1)
    a[..., 2] = np.roll(a[..., 2], -10, axis=1)
    for _ in range(4):
        y0 = r.randint(0, H - 80)
        hh = r.randint(20, 80)
        a[y0:y0 + hh] = np.roll(a[y0:y0 + hh], r.randint(-60, 60), axis=1)
    a[::4] = (a[::4] * 0.75).astype(np.uint8)
    f = Image.fromarray(a).convert("RGBA")
    y = int((T * 2400) % H)
    ImageDraw.Draw(f).rectangle([0, y, W, y + 26], fill=(255, 255, 255, 70))
    return f


# ------------------------------------------------------------------ Morgens: Oma kommt zur Schule
def shot_arrive(t, T):
    v = View(1.0 + 0.06 * t, 540, 1100)
    x = lerp(980, 760, t / 1.5)
    bob = abs(math.sin(t * 8)) * -10
    return bright(frame(W2.yard_static(), T, v, [
        dict(OMA_Y, x=x, y=1180 + bob, pose="oma_stand_bag", expr="smile", look=(-0.4, 0.0),
             items=(("bag", (0.62, 1.2)),), blink=blink(T, 1))]))


def shot_80(t, T):
    v = View(2.6 + 0.12 * t, 780, 1060)
    return bright(frame(W2.yard_static(), T, v, [
        dict(OMA_Y, x=780, pose="oma_stand_bag", expr="warm", look=(0.0, 0.0), items=(("bag", (0.62, 1.2)),))],
        blur_r=6))


OMA_B = dict(who="oma", D=140, x=430, y=1150)


def shot_board(t, T):
    v = View(1.05 + 0.04 * t, 540, 1050)
    return bright(frame(W2.board_static(), T, v, [
        dict(OMA_B, pose="oma_wave", expr="warm", look=(0.0, 0.0), blink=blink(T, 1))],
        post=(lambda f, vv: W2.board_text(f, vv, T, 5.8, 6.7),)))


KIDS = {
    "girl": dict(who="girl", D=100, x=230, y=1180),
    "gamer": dict(who="gamer", D=100, x=540, y=1175),
    "kleiner": dict(who="kleiner", D=92, x=850, y=1200),
    "rowdy": dict(who="rowdy", D=86, x=390, y=960),
}


def kid(name, **kw):
    d = dict(KIDS[name])
    d.update(kw)
    return d


def class_frame(T, v, kids, post=(), blur_r=0.0, extra=()):
    back = [k for k in kids if k["who"] == "rowdy"]
    front = [k for k in kids if k["who"] != "rowdy"]

    def back_desk(f, vv):
        W2.desks_front(f, vv, ys=(1100,), xs=(390,))
    return frame(W2.class_static(), T, v, back, post=(back_desk,) + tuple(
        (lambda kk: (lambda f, vv: actor(f, vv, **kk)))(k) for k in front) + (
        lambda f, vv: W2.desks_front(f, vv),) + tuple(extra) + tuple(post), blur_r=blur_r)


def shot_class_shock(t, T):
    v = View(1.05, 540, 1080)
    return bright(class_frame(T, v, [kid("girl", pose="kid_desk", expr="shock", mouth=0.6, mouth_kind="o"),
                                     kid("gamer", pose="kid_desk", expr="shock"),
                                     kid("kleiner", pose="kid_desk", expr="shock", mouth=0.5, mouth_kind="o"),
                                     kid("rowdy", pose="kid_desk", expr="arrogant")]))


def shot_girl_laugh(t, T):
    v = View(2.2, 300, 1100)
    m = mouth("girl", T)
    return bright(class_frame(T, v, [kid("girl", pose="kid_laugh", expr="laugh" if m < 0.1 else "smirk", mouth=m),
                                     kid("gamer", pose="kid_desk", expr="neutral"),
                                     kid("rowdy", pose="kid_desk", expr="arrogant")]))


def shot_class_laugh(t, T):
    v = View(1.05, 540, 1080)
    b = math.sin(T * 18) * 6
    throw = t > 0.75
    return bright(class_frame(T, v, [kid("girl", y=1180 + b, pose="kid_laugh", expr="laugh", mouth=0.8, mouth_kind="grin"),
                                     kid("gamer", y=1175 - b, pose="kid_laugh", expr="laugh", mouth=mouth("gamer", T),
                                         mouth_kind="grin"),
                                     kid("kleiner", pose="kid_desk", expr="neutral"),
                                     kid("rowdy", pose="kid_throw" if throw else "kid_desk", expr="sneaky",
                                         mouth_kind="grin")]))


def paper_ball(f, x, y, r):
    d = ImageDraw.Draw(f)
    d.ellipse([x - r, y - r, x + r, y + r], fill=(250, 250, 245), outline=(180, 180, 175), width=max(2, int(r * 0.15)))
    for k in range(4):
        a = k * 1.4
        d.line([(x + math.cos(a) * r * 0.2, y + math.sin(a) * r * 0.2), (x + math.cos(a) * r * 0.8,
                                                                         y + math.sin(a) * r * 0.8)],
               fill=(190, 190, 185), width=max(1, int(r * 0.12)))


def shot_ball_fly(t, T):
    v = View(1.05, 540, 1080)
    u = t / 0.7
    f = bright(class_frame(T, v, [kid("girl", pose="kid_desk", expr="shock", mouth=0.5, mouth_kind="o"),
                                  kid("gamer", pose="kid_desk", expr="shock", mouth=0.5, mouth_kind="o"),
                                  kid("kleiner", pose="kid_desk", expr="scared"),
                                  kid("rowdy", pose="kid_throw", expr="sneaky", mouth_kind="grin")]))
    x = lerp(460, 1150, u)
    y = lerp(880, 700, u) - 200 * 4 * u * (1 - u)
    paper_ball(f, *v.p(x, y), 26 * v.z * (1 + u))
    return f


def shot_catch(t, T):
    v = View(1.6, 520, 1000)
    caught = t > 0.35
    pose = "oma_catch" if caught else "oma_knit_stand"
    f = frame(W2.board_static(), T, v, [dict(OMA_B, pose=pose, expr="smirk" if caught else "smile",
                                             look=(0.0, 0.6) if not caught else (0.0, 0.0),
                                             items=(("knit", (0, 1.0)),) if not caught else (),
                                             brow_up=1 if caught else 0)],
              post=(lambda ff, vv: W2.board_text(ff, vv, 99, 0, 1),))
    hx, hy = OMA_B["x"] + 1.05 * OMA_B["D"], OMA_B["y"] - 0.2 * OMA_B["D"]
    if caught:
        d = ImageDraw.Draw(f)
        a, b = v.p(hx, hy), v.p(hx + 30, hy - 150)
        d.line([a, b], fill=(200, 205, 220), width=int(8 * v.z))
        d.ellipse([b[0] - 9 * v.z, b[1] - 9 * v.z, b[0] + 9 * v.z, b[1] + 9 * v.z], fill=(255, 150, 190))
        paper_ball(f, *v.p(hx + 22, hy - 110), 30 * v.z)
        if t - 0.35 < 0.08:
            f.alpha_composite(Image.new("RGBA", f.size, (255, 255, 255, 120)))
    else:
        u = t / 0.35
        paper_ball(f, *v.p(lerp(-80, hx + 22, u), lerp(800, hy - 110, u)), 30 * v.z)
    return grade(f, sat=1.05, contrast=1.08)


def shot_wow(t, T):
    v = View(1.1, 540, 1080)
    m = mouth("girl", T)
    return bright(class_frame(T, v, [kid("girl", pose="kid_desk", expr="shock", mouth=max(m, 0.7), mouth_kind="o"),
                                     kid("gamer", pose="kid_desk", expr="shock", mouth=0.9, mouth_kind="o"),
                                     kid("kleiner", pose="kid_cheer", expr="shock", mouth=0.8, mouth_kind="o"),
                                     kid("rowdy", pose="kid_desk", expr="scared")]))


def shot_judo(t, T):
    v = View(2.4 + 0.1 * t, 430, 1000)
    f = frame(W2.board_static(), T, v, [dict(OMA_B, pose="oma_stand", expr="smirk", look=(0.0, 0.0),
                                             brow_up=1 if t > 0.8 else 0)], blur_r=4)
    p = Wd.photo_static()
    s = ease_back(clamp01((t - 0.2) / 0.3), 2.0) * 0.36
    if s > 0.01:
        paste_c(f, p, 800, 640, s, 1.0, 8)
    return grade(f, contrast=1.06, warm=0.1)


def shot_phone_game(t, T):
    v = View(2.6, 540, 1150)
    f = bright(class_frame(T, v, [kid("gamer", pose="kid_phone", expr="smile", look=(0.0, 0.7),
                                      items=(("phone", (0, 0.85)),))], blur_r=0))
    g = Wd.glow(int(260), (120, 220, 255), 1.6, 0.6)
    paste_c(f, g, *v.p(540, 1175 + 0.85 * 100))
    return f


def shot_phone_take(t, T):
    v = View(1.5, 640, 1120)
    took = t > 0.45
    m = mouth("oma", T)
    acts = [kid("gamer", pose="kid_phone", expr="shock" if took else "smile", look=(0.6, 0.0) if took else (0, 0.7),
                items=() if took else (("phone", (0, 0.85)),), mouth=0.6 if took else 0, mouth_kind="o" if took else None),
            kid("kleiner", pose="kid_desk", expr="neutral", look=(-0.6, 0.0))]
    oma = dict(who="oma", D=150, x=790, y=1020, pose="oma_take_phone" if not took else "oma_show_phone", expr="glare",
               gl=0.12, mouth=m, look=(-0.6, 0.3), items=(("phone", (0.75, -0.25)),) if took else ())
    return bright(class_frame(T, v, acts, extra=(lambda f, vv: actor(f, vv, **oma),)))


def shot_phone_sock(t, T):
    v = View(2.0 + 0.08 * t, 540, 960)
    m = mouth("oma", T)
    f = frame(W2.board_static(), T, v, [dict(OMA_B, x=520, pose="oma_show_phone", expr="smirk", mouth=m,
                                             look=(0.0, 0.0), items=(("phone_sock", (0.75, -0.25)),), brow_up=1)],
              blur_r=4)
    return bright(f)


def shot_phone_cry(t, T):
    v = View(2.5, 540, 1130)
    m = mouth("gamer", T)
    return bright(class_frame(T, v, [kid("gamer", pose="kid_reach", expr="sad", mouth=max(m, 0.2), mouth_kind="wavy"
                                         if m < 0.1 else None)]))


# ------------------------------------------------------------------ Große Pause
def bell(f, t):
    e = emoji("🔔", 140)
    paste_c(f, e, 870, 560, 1.0, 1.0, math.sin(t * 40) * 20 * max(0.0, 1 - t / 0.8))


def shot_pause(t, T):
    v = View(1.08, 520, 1180)
    m = mouth("rowdy", T)
    f = bright(frame(W2.yard_static(), T, v, [
        dict(KLE, pose="kid_reach", expr="sad", look=(0.6, -0.4)),
        dict(who="rowdy", D=ROW_D, x=ROW_POS[0], y=ROW_POS[1], pose="rowdy_grab", expr="arrogant", mouth=m,
             look=(-0.6, 0.2), items=(("sandwich", (0.75, -0.5)),))]))
    if t < 0.8:
        bell(f, t)
    return f


def shot_rowdy_close(t, T):
    v = View(2.2, 600, 1180)
    m = mouth("rowdy", T)
    return bright(frame(W2.yard_static(), T, v, [
        dict(KLE, pose="kid_reach", expr="sad"),
        dict(who="rowdy", D=ROW_D, x=ROW_POS[0], y=ROW_POS[1], pose="rowdy_grab", expr="arrogant", mouth=m,
             mouth_kind="grin" if m < 0.1 else None, look=(-0.6, 0.2), items=(("sandwich", (0.75, -0.5)),))],
        blur_r=3))


def shot_kleiner(t, T):
    v = View(2.6, 520, 1270)
    m = mouth("kleiner", T)
    return bright(frame(W2.yard_static(), T, v, [dict(KLE, pose="kid_reach", expr="sad", mouth=m, look=(0.6, -0.5))],
                        blur_r=5))


def shot_oma_appears(t, T):
    v = View(1.45, 700, 1160)
    m = mouth("oma", T)
    x = lerp(1000, OMA_Y["x"], ease_out(t / 0.4))
    return S1.dramatic(frame(W2.yard_static(), T, v, [
        dict(KLE, pose="kid_stand", expr="shock", look=(0.8, -0.5)),
        dict(who="rowdy", D=ROW_D, x=ROW_POS[0], y=ROW_POS[1], pose="rowdy_grab", expr="neutral",
             items=(("sandwich", (0.75, -0.5)),), look=(0.8, 0.0)),
        dict(OMA_Y, x=x, pose="oma_stand_bag", expr="glare", gl=0.13, mouth=m, look=(-0.7, 0.2),
             items=(("bag", (0.62, 1.2)),))]), 0.6)


def shot_oma_eyes(t, T):
    f = Image.new("RGBA", (W, H), (60, 10, 14, 255))
    Wd.rays(f, 540, 900, T, (255, 60, 60), 40, 18, 30)
    im, (hx, hy) = head("oma", 1150, "glare", mouth("oma", T), False, (-0.45, -0.1), 0.15)
    sc = 1.0 + 0.08 * t
    sh = shake(T, 5 * t)
    paste_c(f, im, 540 + sh[0] + (im.width / 2 - hx) * sc, 1010 + sh[1] + (im.height / 2 - hy) * sc, sc)
    f.alpha_composite(vignette(0.95, (40, 0, 0)))
    return grade(f, contrast=1.15)


def shot_rowdy_cheeky(t, T):
    v = View(1.9, 700, 1150)
    m = mouth("rowdy", T)
    return S1.dramatic(frame(W2.yard_static(), T, v, [
        dict(who="rowdy", D=ROW_D, x=ROW_POS[0], y=ROW_POS[1], pose="rowdy_point", expr="arrogant", mouth=m,
             look=(0.8, -0.2), items=(("sandwich", (0.75, -0.5)),)),
        dict(OMA_Y, pose="oma_stand_bag", expr="glare", gl=0.13, look=(-0.7, 0.2), items=(("bag", (0.62, 1.2)),))]),
        0.6)


THROW_T = 27.1


def shot_throw(t, T):
    thrown = T >= THROW_T
    sh = shake(T, 16 * clamp01(1 - (T - THROW_T) / 0.3)) if thrown else (0, 0)
    v = View(1.6, 700, 1120, sh)
    if not thrown:
        acts = [dict(who="rowdy", D=ROW_D, x=ROW_POS[0] + 30, y=ROW_POS[1], pose="rowdy_point", expr="shock",
                     look=(0.8, 0.0), items=(("sandwich", (0.75, -0.5)),)),
                dict(OMA_Y, x=760, pose="oma_grab", expr="smirk", look=(-0.7, 0.2))]
    else:
        dt = T - THROW_T
        s = clamp01(dt * 0.25)
        x, y = W2.fly_pos(s)
        acts = [dict(OMA_Y, x=760, pose="oma_throw", expr="smirk", look=(-0.3, -0.5)),
                dict(rowdy_fly(s), x=x + 40 - 200 * dt, y=y - 120 - 300 * dt)]
    f = S1.dramatic(frame(W2.yard_static(), T, v, acts), 0.6)
    if thrown and T - THROW_T < 0.08:
        f.alpha_composite(Image.new("RGBA", f.size, (255, 255, 255, 150)))
    return f


SAND_T = 28.75


def fly_s(t):
    pts = [(0, 0.12), (0.25, 0.4), (0.8, 0.56), (1.2, 1.0)]
    for (a, sa), (b, sb) in zip(pts, pts[1:]):
        if t <= b:
            return lerp(sa, sb, (t - a) / (b - a))
    return 1.0


def shot_fly(t, T):
    s = fly_s(t)
    v = View(*HOOK_VIEW)
    after = T >= SAND_T
    acts = [dict(KLE, pose="kid_stand", expr="shock", mouth=0.8, mouth_kind="o", look=(-0.6, -0.6)),
            dict(OMA_Y, pose="oma_knit_stand", expr="smile", look=(0.0, 0.6), items=(("knit", (0, 1.0)),),
                 knit_phase=round((T * 2.5) % 1.0, 1))]
    post = [sandwich_fly(s if not after else 0.0)]
    if not after:
        acts.append(rowdy_fly(s, mouth("rowdy", T)))
    else:
        acts.append(dict(who="rowdy", D=ROW_D, pose="rowdy_sit", x=W2.SAND[0], y=W2.SAND[1] - 120, expr="shock",
                         mouth=0.6, mouth_kind="o"))
        post += [W2.draw_sand_front, lambda f, vv: W2.sand_puff(f, vv, T - SAND_T)]
    f = S1.dramatic(frame(W2.yard_static(), T, v, acts, post=tuple(post)), 0.5)
    if 0.25 < t < 0.8:
        f = grade(f, sat=0.9, contrast=1.05)
    if after and T - SAND_T < 0.25:
        f = cam(f, 1.0 + 0.05 * (1 - (T - SAND_T) / 0.25), 300, 1450)
    return f


ROW_SAND = (W2.SAND[0], W2.SAND[1] - 120)
OMA_S = dict(who="oma", D=125, x=560, y=1150)
GIVE_T = 31.4


def sandy(f, v):
    d = ImageDraw.Draw(f, "RGBA")
    r = random.Random(2)
    for _ in range(40):
        x = ROW_SAND[0] + r.uniform(-60, 60)
        y = ROW_SAND[1] - 110 + r.uniform(-50, 40)
        sx, sy = v.p(x, y)
        rr = r.uniform(2, 5) * v.z
        d.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], fill=(225, 195, 130, 230))


def sand_scene(T, v, oma_kw, blur_r=0.0):
    took = T > GIVE_T
    row = dict(who="rowdy", D=ROW_D, x=ROW_SAND[0], y=ROW_SAND[1], pose="rowdy_take" if took else "rowdy_sit",
               expr="sad", look=(0.7, -0.3), blink=blink(T, 3))
    post = [W2.draw_sand_front, sandy, lambda f, vv: W2.sand_puff(f, vv, T - SAND_T)]
    if took:
        post.append(lambda f, vv: paste_c(f, bonbon_sprite(int(24 * vv.z), (235, 60, 60), 0),
                                          *vv.p(ROW_SAND[0] + 0.9 * ROW_D, ROW_SAND[1] + 0.15 * ROW_D)))
    return S1.dramatic(frame(W2.yard_static(), T, v, [row, oma_kw], post=tuple(post), blur_r=blur_r), 0.5)


def oma_offer(T, **kw):
    has = T < GIVE_T
    base = dict(OMA_S, pose="oma_offer", expr="warm", look=(-0.7, 0.2), mouth=mouth("oma", T),
                items=(("bonbon", (-1.2, 0.35)),) if has else (), blink=blink(T, 1))
    base.update(kw)
    return base


def shot_sand_wide(t, T):
    return sand_scene(T, View(1.7 + 0.05 * t, 420, 1280), oma_offer(T))


def shot_sand_close(t, T):
    return sand_scene(T, View(2.4, 360, 1290), oma_offer(T), blur_r=0)


def shot_bread_back(t, T):
    v = View(1.75, 560, 1180)
    m = mouth("oma", T)
    gave = t > 1.0
    acts = [dict(KLE, x=420, pose="kid_reach" if not gave else "kid_cheer", expr="sad" if not gave else "laugh",
                 look=(0.7, -0.4), items=(("sandwich", (0.7, -0.6)),) if gave else (), mouth=0.6 if gave else 0,
                 mouth_kind="grin" if gave else None),
            dict(OMA_S, x=640, pose="oma_offer", expr="warm", look=(-0.7, 0.3), mouth=m,
                 items=(("sandwich_hand",),) if False else ())]
    f = bright(frame(W2.yard_static(), T, v, acts))
    if not gave:
        from chars import sandwich
        im = Image.new("RGBA", (int(160 * v.z), int(120 * v.z)), (0, 0, 0, 0))
        sandwich(im, im.width / 2, im.height / 2, 110 * v.z)
        hx, hy = 640 - 1.2 * 125, 1150 + 0.35 * 125
        paste_c(f, im, *v.p(hx, hy - 20))
    return f


def shot_danke(t, T):
    v = View(2.5, 440, 1230)
    m = mouth("kleiner", T)
    hearts = emoji("💛", 70)
    f = bright(frame(W2.yard_static(), T, v, [dict(KLE, x=440, pose="kid_cheer", expr="laugh", mouth=max(m, 0.3),
                                                    mouth_kind="grin" if m < 0.1 else None,
                                                    items=(("sandwich", (0.7, -0.6)),))], blur_r=5))
    for k in range(3):
        ph = (t * 0.8 + k * 0.33) % 1
        paste_c(f, hearts, 300 + k * 230, 900 - ph * 300, 0.8 + 0.3 * ph, 1 - ph)
    return f


SHOTS = [
    (0.00, 0.90, shot_hook),
    (0.90, 2.20, shot_hook_oma),
    (2.20, 2.95, shot_rewind),
    (2.95, 4.45, shot_arrive),
    (4.45, 5.60, shot_80),
    (5.60, 7.00, shot_board),
    (7.00, 8.40, shot_class_shock),
    (8.40, 9.70, shot_girl_laugh),
    (9.70, 10.90, shot_class_laugh),
    (10.90, 11.60, shot_ball_fly),
    (11.60, 12.85, shot_catch),
    (12.85, 13.50, shot_wow),
    (13.50, 15.40, shot_judo),
    (15.40, 16.20, shot_phone_game),
    (16.20, 17.30, shot_phone_take),
    (17.30, 18.50, shot_phone_sock),
    (18.50, 19.30, shot_phone_cry),
    (19.30, 20.50, shot_pause),
    (20.50, 21.70, shot_rowdy_close),
    (21.70, 23.00, shot_kleiner),
    (23.00, 24.20, shot_oma_appears),
    (24.20, 25.30, shot_oma_eyes),
    (25.30, 26.80, shot_rowdy_cheeky),
    (26.80, 27.55, shot_throw),
    (27.55, 28.95, shot_fly),
    (28.95, 30.60, shot_sand_wide),
    (30.60, 32.30, shot_sand_close),
    (32.30, 34.30, shot_bread_back),
    (34.30, 35.90, shot_danke),
    (35.90, 37.50, S1.shot_hero),
    (37.50, 39.00, lambda t, T: S1.hero_frame(t + 1, T, 400, (540 + shake(T, 12 * clamp01(1 - (T - 37.7) / 0.35))[0]
                                                           if T > 37.7 else 540, 1330), 1.0 + 0.03 * t)),
    (39.00, 42.00, S1.shot_end),
    (42.00, 42.50, shot_hook_end),
]


def shot_at(T):
    for i, (a, b, fn) in enumerate(SHOTS):
        if a <= T < b or (i == len(SHOTS) - 1 and T >= a):
            return i, a, b, fn
    return len(SHOTS) - 1, *SHOTS[-1]
