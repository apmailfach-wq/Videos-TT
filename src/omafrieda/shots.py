"""Alle Einstellungen. Jede Funktion: (t_lokal, T_global) -> RGBA-Frame ohne Texte."""
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import world as Wd
from chars import head, handbag, pigeon, bonbon_sprite
from gfx import (H, W, blur, cam, clamp01, ease_back, ease_in, ease_io, ease_out, emoji, glow, grade, lerp,
                 paste_c, tint, vignette)
from world import (FLOCK, FOUNT, OMA_D, OMA_NECK, View, actor, blink, bonbon_rain, draw_fountain_front, mouth,
                   oma_bench, park_frame, splash, thief_fly)

HOOK_VIEW = (1.04, 560, 1000)
FREEZE_AT = 0.45


def shake(T, amt, seed=0):
    if amt <= 0:
        return (0.0, 0.0)
    r = random.Random(int(T * 30) * 13 + seed)
    return (r.uniform(-amt, amt), r.uniform(-amt, amt))


def world_bag(x, y, D):
    def fn(f, v):
        im = Image.new("RGBA", (int(D * v.z * 1.6), int(D * v.z * 1.6)), (0, 0, 0, 0))
        handbag(im, im.width / 2, im.height * 0.12, D * v.z)
        sx, sy = v.p(x, y)
        f.alpha_composite(im, (int(sx - im.width / 2), int(sy - im.height * 0.12)))
    return fn


def dramatic(f, amt=1.0):
    f = grade(f, sat=1.0 + 0.1 * amt, contrast=1.0 + 0.14 * amt, bright=1.0 - 0.04 * amt, warm=0.35 * amt)
    f.alpha_composite(vignette(0.55 * amt))
    return f


def sunny(f):
    f = grade(f, sat=1.08, contrast=1.02, bright=1.04, warm=0.12)
    f.alpha_composite(vignette(0.25))
    return f


# ------------------------------------------------------------------ HOOK
_cache = {}


def thief2_of(d, s, T, m=0.0):
    """Zweiter Dieb fliegt leicht versetzt hinter dem ersten."""
    x, y = Wd.fly_pos(max(0.0, s - 0.06))
    return dict(who="thief2", D=112, pose="thief_fly", x=x - 120, y=y + 30, rot=Wd.fly_rot(s) + 35, center=True,
                expr="shock", mouth=m, flip=True)


def two_thieves_extra(s, T, m1=0.85, m2=0.85):
    def fn(fr, vv):
        actor(fr, vv, **thief2_of(None, s, T, m2))
    return fn


def hook_frame(t_hook, with_oma=True):
    """t_hook in [0, FREEZE_AT]; danach eingefroren."""
    tt = min(t_hook, FREEZE_AT)
    key = (round(tt * 30), with_oma)
    if key in _cache:
        return _cache[key].copy()
    s = 0.465 + 0.035 * tt / FREEZE_AT
    Tsim = 25.9 + tt * 0.25
    v = View(*HOOK_VIEW)
    f = park_frame(Tsim, v, oma=oma_bench(Tsim, look=(0.0, 0.55), expr="smile") if with_oma else None,
                   thief=thief_fly(s, Tsim, 0.85),
                   extras=(("pre", two_thieves_extra(s, Tsim)),
                           ("post", lambda fr, vv: bonbon_rain(fr, vv, s, Tsim))), jet_frozen=False, flock_T=Tsim)
    f = dramatic(f, 0.6)
    _cache[key] = f
    return f.copy()


def shot_hook(t, T):
    f = hook_frame(t)
    if t >= FREEZE_AT:
        dt = t - FREEZE_AT
        z = 1.05 + 0.03 * ease_out(dt / 0.15)
        f = cam(f, z, 470, 760)
        f = grade(f, sat=0.75, contrast=1.08)
        if dt < 0.12:
            fl = Image.new("RGBA", f.size, (255, 255, 255, int(200 * (1 - dt / 0.12))))
            f.alpha_composite(fl)
    else:
        f = cam(f, 1.05 + 0.06 * t, 470, 760)
    return f


def shot_hook_end(t, T):
    return shot_hook(FREEZE_AT + 0.13 + t, T) if t > 0.05 else shot_hook(FREEZE_AT + t, T)


def shot_hook_oma(t, T):
    bg = hook_frame(1.0, with_oma=False)  # nur eine Oma im Bild
    bg = cam(bg, 1.3, 520, 820)
    bg = grade(blur(bg, 7), sat=0.55, contrast=0.95, bright=0.85)
    z = 1.0 + 0.04 * t
    m = mouth("oma", T)
    actor(bg, View(z, 540, 1100), "oma", 300, "oma_sit_knit", 540, 1330, expr="smirk", look=(0.0, 0.0),
          mouth=m, blink=blink(T, 2), items=(("knit", (0, 1.0)),), head_off=(0, 0, -4))
    return bg


# ------------------------------------------------------------------ Zurückspulen
def shot_rewind(t, T):
    s = lerp(0.5, 0.0, ease_in(t / 0.75) * 0.6 + t / 0.75 * 0.4)
    v = View(*HOOK_VIEW)
    Tsim = 25.9 - t * 3
    f = park_frame(Tsim, v, oma=oma_bench(Tsim), thief=thief_fly(s, Tsim, 0.4),
                   extras=(("post", lambda fr, vv: bonbon_rain(fr, vv, s, Tsim)),), flock_T=Tsim)
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
    d = ImageDraw.Draw(f)
    y = int((T * 2400) % H)
    d.rectangle([0, y, W, y + 26], fill=(255, 255, 255, 70))
    return f


# ------------------------------------------------------------------ Szene 2: harmlose Oma
def shot_establish(t, T):
    v = View(1.0 + 0.08 * t / 1.55, 610, 1010)
    return sunny(park_frame(T, v, oma=oma_bench(T), flock_T=T))


def shot_80(t, T):
    v = View(2.6 + 0.15 * t, 800, 915)
    return sunny(park_frame(T, v, oma=oma_bench(T, expr="warm", look=(0.0, 0.0), mouth=0.0), bg_blur=6, flock_T=T))


def shot_knit(t, T):
    v = View(3.3 + 0.2 * t, 800, 1110)
    return sunny(park_frame(T, v, oma=oma_bench(T, knit_phase=round((T * 4) % 1.0, 1)), bg_blur=8))


def crumbs(t):
    def fn(f, v):
        d = ImageDraw.Draw(f)
        r = random.Random(3)
        for k in range(22):
            t0 = r.uniform(0.0, 0.25)
            dt = t - t0
            if dt < 0:
                continue
            x0, y0 = OMA_NECK[0] + 1.15 * OMA_D, OMA_NECK[1]
            tx, ty = r.uniform(480, 760), r.uniform(1290, 1460)
            u = clamp01(dt / 0.55)
            x = lerp(x0, tx, u) - 0
            x = lerp(x0, tx, u)
            y = lerp(y0, ty, u) - 260 * 4 * u * (1 - u)
            sx, sy = v.p(x, y)
            rr = 5 * v.z
            d.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], fill=(230, 190, 120))
    return fn


def shot_feed(t, T):
    v = View(1.45, 690, 1150)
    pose = "oma_sit_throw" if t < 0.35 else "oma_sit_knit"
    items = (("knit", (0, 1.0)),) if pose == "oma_sit_knit" else ()
    oma = oma_bench(T, pose=pose, items=items, look=(0.6, 0.6), expr="warm")
    return sunny(park_frame(T, v, oma=oma, flock_T=T, extras=(("post", crumbs(t)),)))


def shot_smile(t, T):
    v = View(2.9 - 0.12 * t, 800, 905)
    return sunny(park_frame(T, v, oma=oma_bench(T, expr="warm", look=(0.0, 0.0), head_off=(0, 0, 7),
                                                blink=False), bg_blur=6, flock_T=T))


# ------------------------------------------------------------------ Szene 3: Foto
def shot_photo(t, T, zoom=False):
    f = Wd.table_bg().copy()
    p = Wd.photo_static()
    sc = 960 / p.width
    paste_c(f, p, 540, 940, sc, 1.0, -3.0)
    if not zoom:
        z = 1.0 + 0.06 * t
        f = cam(f, z, 540, 900)
        if t < 0.1:
            f.alpha_composite(Image.new("RGBA", f.size, (255, 255, 255, int(255 * (1 - t / 0.1)))))
    else:
        if T < 11.55:
            f = cam(f, 1.75 + 0.18 * t, 600, 760)
        else:
            f = cam(f, 2.3 + 0.25 * (T - 11.55), 640, 1090)
    f = Wd.grain(f, T, 14)
    if int(T * 30) % 7 == 0:
        f = grade(f, bright=1.06)
    return f


# ------------------------------------------------------------------ Szene 4: Bus
MAN = dict(who="jung", D=150)


def shot_bus_wide(t, T):
    v = View(1.06 + 0.05 * t, 540, 1150)
    m = mouth("jung", T)
    return bus_cool(Wd.bus_frame(T, v, [
        dict(MAN, pose="jung_spread", x=660, y=1017, expr="arrogant", mouth=m, look=(-0.6, 0.3),
             blink=blink(T, 4)),
        dict(who="oma", D=170, pose="oma_stand_bag", x=250, y=1300, expr="neutral", look=(0.6, -0.2),
             items=(("bag", (0.62, 1.2)),), blink=blink(T, 1))]))


def bus_cool(f):
    return grade(f, sat=1.05, contrast=1.06, warm=0.05)


def shot_bus_look(t, T):
    v = View(2.3 + 0.25 * t, 270, 1190)
    return bus_cool(Wd.bus_frame(T, v, [
        dict(MAN, pose="jung_spread", x=660, y=1017, expr="arrogant", look=(-0.6, 0.3)),
        dict(who="oma", D=170, pose="oma_stand_bag", x=250, y=1300, expr="glare", gl=0.14, look=(0.5, -0.35),
             items=(("bag", (0.62, 1.2)),), head_off=(0, 0.02, -5))], blur_r=0))


def shot_bus_eyes(t, T):
    f = Image.new("RGBA", (W, H), (60, 10, 14, 255))
    rays_col = (255, 60, 60)
    Wd.rays(f, 540, 900, T, rays_col, 40, 18, 30)
    D = 1150
    im, (hx, hy) = head("oma", D, "glare", 0.0, False, (0.45, -0.3), 0.15)
    sc = 1.0 + 0.1 * t
    sh = shake(T, 6 * t)
    paste_c(f, im, 540 + sh[0] + (im.width / 2 - hx) * sc, 1010 + sh[1] + (im.height / 2 - hy) * sc, sc)
    f.alpha_composite(vignette(0.95, (40, 0, 0)))
    return grade(f, contrast=1.15)


def shot_bus_after(t, T):
    v = View(1.15, 560, 1150)
    drop = -50 * (1 - ease_out(t / 0.25))
    m = mouth("jung", T)
    jump = ease_back(t / 0.25, 2.0)
    man = dict(MAN, pose="jung_offer", x=lerp(815, 860, jump), y=lerp(1017, 905, jump), expr="scared", sweat=True,
               look=(-0.6, 0.2), mouth=m, mouth_kind="wavy" if m < 0.1 else None)
    return bus_cool(Wd.bus_frame(T, v, [
        dict(who="oma", D=150, pose="oma_sit_rest", x=420, y=1047 + drop, expr="smile", look=(0.5, -0.2),
             items=(("bag", (0.3, 1.3)),), blink=blink(T, 1)), man]))


# ------------------------------------------------------------------ Szene 5: Armdrücken
AW_OMA = dict(who="oma", D=150, x=400, y=1150)
AW_MUSK = dict(who="musk1", D=125, x=745, y=1172)
TABLE_Y = 1318


def aw_table(f, v):
    x0, y0 = v.p(150, TABLE_Y)
    x1, y1 = v.p(990, 1720)
    from gfx import rrect
    rrect(f, x0, y0, x1, y1, 20 * v.z, (92, 64, 44), amb=0.5, spec=0.25)
    rrect(f, x0 - 6 * v.z, y0 - 8 * v.z, x1 + 6 * v.z, y0 + 26 * v.z, 12 * v.z, (130, 92, 62), amb=0.55, spec=0.3)


def clasp(x, y, D):
    def fn(f, v):
        sx, sy = v.p(x, y)
        Wd.ell(f, sx, sy, D * 0.2 * v.z, D * 0.17 * v.z, (236, 186, 150), amb=0.5, spec=0.25)
    return fn


def musk2_actor(T, expr="laugh", m=0.0, x=930, pose="musk_laugh", **kw):
    b = math.sin(T * 18) * 6 if expr == "laugh" else 0
    return dict(who="musk2", D=100, pose=pose, x=x, y=1020 + b, expr=expr, mouth=m, look=(-0.6, 0.2), flip=True, **kw)


def aw_frame(T, v, oma_kw, musk_kw, musk2_kw=None, post=()):
    acts = []
    if musk2_kw:
        acts.append(musk2_kw)
    if musk_kw:
        acts.append(musk_kw)
    acts.append(oma_kw)

    def post_fn(f, vv):
        aw_table(f, vv)
        for p in post:
            p(f, vv)
    return Wd.gym_frame(T, v, acts, post=post_fn)


def knit_items():
    return (("knit", (-0.25, 0.95)),)


def shot_aw_wide(t, T):
    v = View(1.25 + 0.04 * t, 560, 1180)
    m = mouth("musk", T)
    return aw_frame(T, v, dict(AW_OMA, pose="oma_sit_knit", expr="smile", look=(0.6, 0.0),
                               items=(("knit", (0, 1.0)),), knit_phase=round((T * 2.5) % 1.0, 1), blink=blink(T, 1)),
                    dict(AW_MUSK, pose="aw_musk", expr="laugh", mouth=m, look=(-0.6, 0.1)),
                    musk2_actor(T, "laugh", mouth("musk", T) * 0.6 if T > 20.6 else 0.2))


def shot_aw_laugh(t, T):
    v = View(1.9, 800, 1110)
    m = mouth("musk", T)
    return aw_frame(T, v, dict(AW_OMA, pose="oma_sit_knit", expr="smile", items=(("knit", (0, 1.0)),)),
                    dict(AW_MUSK, pose="aw_musk", expr="laugh", mouth=max(m, 0.4), mouth_kind="grin"),
                    musk2_actor(T, "laugh", 0.9, mouth_kind="grin"))


def shot_aw_oma(t, T):
    v = View(2.1 + 0.08 * t, 470, 1110)
    m = mouth("oma", T)
    gripped = t > 0.55
    oma = dict(AW_OMA, pose="aw_oma" if gripped else "oma_sit_knit", expr="smirk", mouth=m, look=(0.5, 0.0),
               items=knit_items() if gripped else (("knit", (0, 1.0)),), knit_phase=round((T * 3) % 1.0, 1), gl=0.1)
    post = (clasp(581, 1168, 125),) if gripped else ()
    return aw_frame(T, v, oma, dict(AW_MUSK, pose="aw_musk", expr="laugh"), post=post)


def shot_aw_strain(t, T):
    sh = shake(T, 5)
    v = View(2.0, 590, 1190, sh)
    return aw_frame(T, v, dict(AW_OMA, pose="aw_oma", expr="smile", look=(0.0, 0.6), items=knit_items(),
                               knit_phase=round((T * 4) % 1.0, 1), blink=blink(T, 1)),
                    dict(AW_MUSK, pose="aw_musk", expr="strain", sweat=True), post=(clasp(581, 1168, 125),))


def shot_aw_slam(t, T):
    slam = t > 0.18
    sh = shake(T, 22 * clamp01(1 - (t - 0.18) / 0.5)) if slam else shake(T, 4)
    v = View(1.35, 600, 1160, sh)
    oma = dict(AW_OMA, pose="aw_oma_win" if slam else "aw_oma", expr="smirk", look=(0.6, 0.2), items=knit_items(),
               knit_phase=round((T * 3) % 1.0, 1))
    if not slam:
        musk = dict(AW_MUSK, pose="aw_musk", expr="strain", sweat=True)
        post = (clasp(581, 1168, 125),)
    else:
        dt = t - 0.18
        if dt < 0.12:
            musk = dict(AW_MUSK, pose="aw_musk_lose", expr="shock", mouth=1.0, mouth_kind="o")
        else:
            u = dt - 0.12
            musk = dict(who="musk1", D=125, pose="musk_shock", x=745 + 520 * u, y=1250 - 700 * u + 900 * u * u,
                        rot=-260 * u, center=True, expr="shock", mouth=1.0, mouth_kind="o")
        post = (clasp(660, 1300, 125),)
    f = aw_frame(T, v, oma, musk, musk2_actor(T, "shock", 0.8, mouth_kind="o") if slam else musk2_actor(T), post=post)
    if slam and t - 0.18 < 0.07:
        f.alpha_composite(Image.new("RGBA", f.size, (255, 255, 255, 140)))
    return f


def shot_aw_next(t, T):
    v = View(1.3, 640, 1140)
    m = mouth("oma", T)
    run = max(0.0, T - 25.8)
    m2 = musk2_actor(T, "scared", 0.0) if run <= 0 else dict(who="musk2", D=100, pose="musk_run", x=930 + 900 * run,
                                                              y=1020 - abs(math.sin(run * 20)) * 18, expr="scared",
                                                              flip=False, look=(1.0, 0.0))
    oma = dict(AW_OMA, pose="oma_sit_knit", expr="smirk", brow_up=1, mouth=m, look=(0.7, 0.0),
               items=(("knit", (0, 1.0)),), knit_phase=round((T * 2.5) % 1.0, 1))

    def dust_fn(f, vv):
        if run > 0:
            d = ImageDraw.Draw(f, "RGBA")
            for k in range(8):
                px, py = vv.p(930 + 900 * run - 120 - k * 40, 1330 + (k % 3) * 10)
                r = (20 + k * 6) * vv.z
                d.ellipse([px - r, py - r, px + r, py + r], fill=(200, 200, 210, max(0, 150 - k * 15)))
    return aw_frame(T, v, oma, None, m2, post=(dust_fn,))


# ------------------------------------------------------------------ Szene 6: Die Diebe
BAG_BENCH = (662, 1088)


def shot_sneak(t, T):
    v = View(1.3, 600, 1030)
    x = lerp(280, 480, t / 1.6)
    bob = abs(math.sin(t * 7)) * -14
    th = dict(who="thief", D=110, pose="thief_sneak", x=x, y=1000 + bob, expr="sneaky", look=(0.8, 0.2))
    th2 = dict(who="thief2", D=110, pose="thief_sneak", x=x - 150, y=1005 - bob, expr="sneaky", look=(0.8, 0.2))
    f = park_frame(T, v, oma=oma_bench(T), thief=th, flock_T=T,
                   extras=(("pre", world_bag(BAG_BENCH[0] - 30, BAG_BENCH[1] + 2, OMA_D)),
                           ("pre", lambda fr, vv: actor(fr, vv, **th2))))
    return dramatic(f)


def shot_whisper(t, T):
    v = View(2.3, 420, 960)
    m2 = mouth("dieb2", T)
    th = dict(who="thief", D=110, pose="thief_sneak", x=480, y=1000, expr="sneaky", look=(-0.7, 0.0),
              mouth_kind="grin" if T > 29.3 else None)
    th2 = dict(who="thief2", D=110, pose="thief_sneak", x=350, y=1000, expr="sneaky", look=(0.8, 0.0), mouth=m2,
               head_off=(0.08, 0.02, -10))
    f = park_frame(T, v, oma=oma_bench(T), thief=th,
                   extras=(("pre", world_bag(BAG_BENCH[0] - 30, BAG_BENCH[1] + 2, OMA_D)),
                           ("pre", lambda fr, vv: actor(fr, vv, **th2))), bg_blur=3)
    return dramatic(f)


def shot_grab(t, T):
    v = View(2.2, 620, 1060)
    reach = ease_out(t / 0.3)
    th = dict(who="thief", D=110, pose="thief_grab", x=lerp(470, 520, reach), y=1000, expr="sneaky",
              look=(0.8, 0.3), flip=True)
    th2 = dict(who="thief2", D=110, pose="thief_grab", x=lerp(330, 380, reach), y=1005, expr="sneaky", flip=True)
    if t < 0.35:
        oma = oma_bench(T)
        bag = (BAG_BENCH[0] - 30 + 30 * reach, BAG_BENCH[1] + 2)
    else:
        oma = oma_bench(T, pose="oma_sit_hold", flip=True, items=(), look=(0.9, 0.2), expr="glare", gl=0.1)
        bag = BAG_BENCH
    f = park_frame(T, v, oma=oma, thief=th, extras=(("pre", lambda fr, vv: actor(fr, vv, **th2)),
                                                    ("post", world_bag(*bag, OMA_D))))
    return dramatic(f)


def shot_hilfe(t, T):
    sh = shake(T, 14)
    v = View(1.95, 740, 975, sh)
    m = mouth("oma", T)
    oma = oma_bench(T, pose="oma_sit_hold", flip=True, items=(), look=(0.0, 0.0), expr="neutral", mouth=max(m, 0.15),
                    mouth_kind="o" if m > 0.3 else None, blink=False)
    th = dict(who="thief", D=110, pose="thief_grab", x=520, y=1000, expr="shock", flip=True)
    f = park_frame(T, v, oma=oma, thief=th, extras=(("post", world_bag(*BAG_BENCH, OMA_D)),))
    return dramatic(f)


def shot_passers(t, T):
    v = View(1.65, 380, 930)
    turned = t > 0.12
    ps = []
    for (who, x) in (("pass1", 190), ("pass2", 590)):
        if turned:
            ps.append(dict(who=who, D=75, pose="pass_shock", x=x, y=860, expr="shock", mouth=0.7, mouth_kind="o"))
        else:
            ps.append(dict(who=who, D=75, pose="pass_stand", x=x, y=860, expr="neutral", look=(-1.0, 0.0),
                           flip=True))
    f = park_frame(T, v, passers=ps, flock_T=T)
    if turned:
        e = emoji("❗", 90)
        for x in (190, 590):
            sx, sy = v.p(x, 860 - 150)
            paste_c(f, e, sx, sy, Wd_pop(t - 0.12))
    return dramatic(f)


def Wd_pop(dt):
    return ease_back(dt / 0.2, 2.5) if dt < 0.2 else 1.0


RELEASE_T = 32.6


def shot_tug(t, T):
    released = T >= RELEASE_T
    sh = shake(T, 4 + 10 * clamp01(t / 0.7)) if not released else shake(T, 18 * clamp01(1 - (T - RELEASE_T) / 0.3))
    v = View(1.4 + 0.06 * t, 600, 1040, sh)
    ex = []
    if not released:
        pull = math.sin(T * 25) * 6
        th = dict(who="thief", D=110, pose="thief_pull", x=470 + pull, y=1000, expr="strain", flip=True)
        th2 = dict(who="thief2", D=110, pose="thief_pull", x=330 + pull * 1.5, y=1005, expr="strain", flip=True)
        oma = oma_bench(T, pose="oma_sit_pull", flip=True, items=(), look=(0.9, 0.1), expr="smirk", gl=0.1)
        bag = (608 + pull, 1080)
        ex.append(("pre", world_bag(*bag, OMA_D)))

        def strap(f, vv):
            d = ImageDraw.Draw(f)
            a = vv.p(bag[0] + 10, bag[1] - 10)
            b = vv.p(OMA_NECK[0] - 1.3 * OMA_D, OMA_NECK[1] + 0.55 * OMA_D)
            d.line([a, b], fill=(110, 62, 30), width=int(9 * vv.z))
        ex.append(("pre", strap))
        ex.append(("pre", lambda fr, vv: actor(fr, vv, **th2)))
    else:
        dt = T - RELEASE_T
        s = clamp01(dt * 0.35)
        x, y = Wd.fly_pos(s)
        th = dict(who="thief", D=110, pose="thief_fly", x=x - 140 * dt, y=y + 150 - 60 * dt, center=True,
                  rot=-15 - 60 * dt, expr="shock", mouth=0.9, items=(("bag", (1.35, -0.4)),))
        th2 = dict(who="thief2", D=110, pose="thief_fly", x=x - 260 * dt - 120, y=y + 170 - 40 * dt, center=True,
                   rot=20 - 80 * dt, expr="shock", mouth=0.9, flip=True)
        ex.append(("pre", lambda fr, vv: actor(fr, vv, **th2)))
        oma = oma_bench(T, pose="oma_sit_release", flip=True, items=(), look=(0.0, 0.0), expr="smirk", brow_up=-1)
    f = park_frame(T, v, oma=oma, thief=th, extras=tuple(ex))
    f = dramatic(f)
    if released and T - RELEASE_T < 0.08:
        f.alpha_composite(Image.new("RGBA", f.size, (255, 255, 255, 150)))
    return f


SPLASH_T = 34.25
FLY_A = 32.95


def fly_s(t):
    pts = [(0, 0.0), (0.22, 0.36), (0.78, 0.57), (1.3, 1.0)]
    for (a, sa), (b, sb) in zip(pts, pts[1:]):
        if t <= b:
            return lerp(sa, sb, (t - a) / (b - a))
    return 1.0


def shot_fly(t, T):
    s = fly_s(t)
    v = View(*HOOK_VIEW)
    after = T >= SPLASH_T
    m = mouth("dieb", T)
    th = None if after else thief_fly(s, T, m)
    oma = oma_bench(T, look=(0.0, 0.55), expr="smile")
    ex = [("post", lambda fr, vv: bonbon_rain(fr, vv, s if not after else 1.0 + (T - SPLASH_T), T))]
    if not after:
        ex.insert(0, ("pre", two_thieves_extra(s, T, m, m)))
    else:
        ex.append(("post", lambda fr, vv: splash(fr, vv, T - SPLASH_T, scale=1.3)))
    f = park_frame(T, v, oma=oma, thief=th, extras=tuple(ex), flock_T=T, flock_scare=SPLASH_T + 0.05)
    f = dramatic(f, 0.7)
    if 0.22 < t < 0.78:
        f = grade(f, sat=0.9, contrast=1.05)
    if after and T - SPLASH_T < 0.25:
        f = cam(f, 1.0 + 0.05 * (1 - (T - SPLASH_T) / 0.25), 420, 1100)
    return f


# Brunnen-Finale: zwei nasse Diebe, Oma verteilt Hustenbonbons
TH1 = (300, 1012)
TH2 = (500, 1016)
OMA_F = (760, 860)
GIVE_T = 36.15   # Dieb 2 nimmt das Bonbon
FLICK_T = 36.55  # Oma schnippt Dieb 1 ein Bonbon in den Mund
PIGEON_T = 37.9


def fountain_frame(T, v, oma_kw, bg_blur=0.0, extra_post=()):
    m1 = 0.0
    flick_dt = T - FLICK_T
    if 0.15 < flick_dt < 0.55:
        m1 = 0.9
    th1 = dict(who="thief", D=112, pose="thief_wet", x=TH1[0], y=TH1[1], expr="sad" if flick_dt < 0.55 else "smile",
               wet=True, look=(0.7, -0.2), blink=blink(T, 3), mouth=m1, mouth_kind="o" if m1 else None)
    took = T > GIVE_T
    m2 = mouth("dieb2", T)
    th2 = dict(who="thief2", D=112, pose="thief_take" if took else "thief_wet", x=TH2[0], y=TH2[1],
               expr="sad", wet=True, look=(0.7, -0.3), mouth=m2, blink=blink(T, 4))

    def front(f, vv):
        draw_fountain_front(f, vv)
        r = random.Random(1)
        for k in range(5):
            bx = [180, 220, 400, 610, 640][k]
            by = 1105 + r.uniform(-20, 30) + math.sin(T * 3 + k) * 3
            paste_c(f, bonbon_sprite(int(24 * vv.z), (235, 60, 60) if k % 2 else (250, 160, 40), (k * 60) % 360),
                    *vv.p(bx, by))
        if took:
            paste_c(f, bonbon_sprite(int(24 * vv.z), (235, 60, 60), 0),
                    *vv.p(TH2[0] + 0.95 * 112, TH2[1] + 0.12 * 112))
        if 0 <= flick_dt < 0.45:
            u = flick_dt / 0.45
            hx, hy = OMA_F[0] - 1.2 * 118, OMA_F[1] + 0.35 * 118
            tx, ty = TH1[0], TH1[1] - 0.5 * 112 + 0.3 * 112
            px = lerp(hx, tx, u)
            py = lerp(hy, ty, u) - 260 * 4 * u * (1 - u)
            paste_c(f, bonbon_sprite(int(24 * vv.z), (250, 160, 40), int(u * 720) // 30 * 30 % 360), *vv.p(px, py))
        if T > PIGEON_T - 0.45:
            u = clamp01((T - (PIGEON_T - 0.45)) / 0.45)
            px = lerp(120, TH1[0] - 5, ease_out(u))
            py = lerp(700, TH1[1] - 0.5 * 112 - 72, ease_out(u))
            img = pigeon(int(50 * vv.z), int(T * 14) % 4 if u < 1 else -1, 1)
            paste_c(f, img, *vv.p(px, py))
        for p in extra_post:
            p(f, vv)

    f = park_frame(T, v, oma=oma_kw, thief=None, bg_blur=bg_blur, extras=(
        ("pre", lambda fr, vv: actor(fr, vv, **th1)), ("pre", lambda fr, vv: actor(fr, vv, **th2)),
        ("post", front), ("post", lambda fr, vv: splash(fr, vv, T - SPLASH_T, scale=1.3))))
    return dramatic(f, 0.7)


def oma_offer_kw(T, **kw):
    m = mouth("oma", T)
    has = T < GIVE_T or (FLICK_T - 0.4 < T < FLICK_T)
    base = dict(who="oma", D=118, pose="oma_offer", x=OMA_F[0], y=OMA_F[1], expr="warm", look=(-0.7, 0.2), mouth=m,
                items=(("bonbon", (-1.2, 0.35)),) if has else (), blink=blink(T, 1))
    base.update(kw)
    return base


def shot_offer_wide(t, T):
    return fountain_frame(T, View(1.75 + 0.05 * t, 520, 990), oma_offer_kw(T))


def shot_offer_close(t, T):
    return fountain_frame(T, View(2.3, 450, 960), oma_offer_kw(T))


def shot_offer_danke(t, T):
    return fountain_frame(T, View(2.6, 400, 960), oma_offer_kw(T), bg_blur=2)


def shot_offer_oma(t, T):
    kw = dict(pose="oma_stand", expr="smirk", look=(-0.6, 0.1), items=())
    if 0.5 < (t % 1.2) < 0.9:
        kw["brow_up"] = 1
    return fountain_frame(T, View(2.4, OMA_F[0] - 20, 820), oma_offer_kw(T, **kw), bg_blur=3)


def shot_offer_end(t, T):
    kw = dict(pose="oma_stand", expr="warm", look=(-0.6, 0.1), items=())
    return fountain_frame(T, View(1.7, 520, 990), oma_offer_kw(T, **kw))


# ------------------------------------------------------------------ Szene 7: Held
def hero_frame(t, T, D, neck, zoom):
    f = Wd.hero_sky("hero").copy()
    Wd.rays(f, 540, neck[1] - D * 0.6, T, (255, 240, 200), 55, 16, 10)
    g = glow(int(D * 3.2), (255, 235, 180), 1.4, 0.95)
    paste_c(f, g, 540, neck[1] - D * 0.55)
    # Wolkenfetzen unten
    if t < 0.75 and D < 400:
        pose, gl, brow = "oma_glasses", lerp(0.13, 0.03, ease_io((t - 0.15) / 0.5)), 0
        expr = "neutral"
    else:
        pose, gl, brow = "oma_stand", 0.03, 1
        expr = "smirk"
    m = mouth("oma", T)
    v = View(zoom, 540, 960)
    sx, sy = v.p(*neck)
    Dz = D * zoom
    Wd.scarf(f, sx + Dz * 0.15, sy + Dz * 0.08, Dz, T, 1)
    from chars import person
    im, (nx, ny), sc = person("oma", Dz, pose, expr=expr, mouth=m, gl=round(gl, 2), brow_up=brow, look=(0.0, 0.0),
                              blink=blink(T, 5) and brow == 0)
    pos = (int(sx - nx * sc), int(sy - ny * sc))
    if abs(sc - 1) > 0.01:
        im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BICUBIC)
    f.alpha_composite(im, pos) if pos[0] >= 0 and pos[1] >= 0 else paste_c(f, im, pos[0] + im.width / 2,
                                                                             pos[1] + im.height / 2)
    Wd.rim_glow(f, im, pos) if pos[0] >= 0 and pos[1] >= 0 else None
    f.alpha_composite(vignette(0.45))
    return grade(f, contrast=1.06, warm=0.15)


def shot_hero(t, T):
    return hero_frame(t, T, 300, (540, 1230), 1.0 + 0.05 * t)


def shot_hero2(t, T):
    sh = shake(T, 12 * clamp01(1 - (T - 43.1) / 0.35)) if T > 43.1 else (0, 0)
    f = hero_frame(t + 1, T, 400, (540 + sh[0], 1330 + sh[1]), 1.0 + 0.03 * t)
    return f


# ------------------------------------------------------------------ Szene 8: Ende
def shot_end(t, T):
    f = Wd.hero_sky("end").copy()
    Wd.rays(f, 540, 1300, T, (255, 220, 160), 40, 18, 12)
    from chars import person
    im, (nx, ny), sc = person("oma", 330, "oma_point", expr="smirk", brow_up=1, look=(0.0, 0.0),
                              blink=blink(T, 2), mouth=0.0)
    bob = math.sin(t * 6) * 6
    paste_c(f, im, 560, 1540 + bob + (im.height / 2 - ny) * sc, sc)
    f.alpha_composite(vignette(0.4))
    return f


SHOTS = [
    (0.00, 0.90, shot_hook),
    (0.90, 2.20, shot_hook_oma),
    (2.20, 2.95, shot_rewind),
    (2.95, 4.50, shot_establish),
    (4.50, 5.65, shot_80),
    (5.65, 6.70, shot_knit),
    (6.70, 7.70, shot_feed),
    (7.70, 8.60, shot_smile),
    (8.60, 10.30, lambda t, T: shot_photo(t, T, False)),
    (10.30, 12.80, lambda t, T: shot_photo(t, T, True)),
    (12.80, 14.70, shot_bus_wide),
    (14.70, 15.50, shot_bus_look),
    (15.50, 16.50, shot_bus_eyes),
    (16.50, 18.20, shot_bus_after),
    (18.20, 20.05, shot_aw_wide),
    (20.05, 21.25, shot_aw_laugh),
    (21.25, 22.45, shot_aw_oma),
    (22.45, 23.70, shot_aw_strain),
    (23.70, 24.85, shot_aw_slam),
    (24.85, 26.70, shot_aw_next),
    (26.70, 28.45, shot_sneak),
    (28.45, 29.60, shot_whisper),
    (29.60, 30.30, shot_grab),
    (30.30, 31.25, shot_hilfe),
    (31.25, 31.80, shot_passers),
    (31.80, 32.95, shot_tug),
    (32.95, 34.45, shot_fly),
    (34.45, 35.90, shot_offer_wide),
    (35.90, 37.30, shot_offer_close),
    (37.30, 38.40, shot_offer_danke),
    (38.40, 39.90, shot_offer_oma),
    (39.90, 41.30, shot_offer_end),
    (41.30, 42.80, shot_hero),
    (42.80, 44.40, shot_hero2),
    (44.40, 47.40, shot_end),
    (47.40, 47.90, shot_hook_end),
]


def shot_at(T):
    for i, (a, b, fn) in enumerate(SHOTS):
        if a <= T < b or (i == len(SHOTS) - 1 and T >= a):
            return i, a, b, fn
    return len(SHOTS) - 1, *SHOTS[-1]
