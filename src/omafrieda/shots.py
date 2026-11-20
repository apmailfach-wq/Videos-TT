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
                   extras=(("post", lambda fr, vv: bonbon_rain(fr, vv, s, Tsim)),), jet_frozen=False, flock_T=Tsim)
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
        # Zeitlupe: leichter Kamera-Drift
        f = cam(f, 1.05 + 0.06 * t, 470, 760)
    return f


def shot_hook_end(t, T):
    return shot_hook(FREEZE_AT + 0.13 + t, T) if t > 0.05 else shot_hook(FREEZE_AT + t, T)


def shot_hook_oma(t, T):
    bg = hook_frame(1.0, with_oma=False)  # nur eine Oma im Bild
    bg = cam(bg, 1.3, 520, 820)
    bg = grade(blur(bg, 7), sat=0.55, contrast=0.95, bright=0.85)
    v = View(1.0, 540, 960)
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
        z = 1.75 + 0.18 * t
        f = cam(f, z, 600, 760)
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
    return bus_cool(Wd.bus_frame(T, v, [
        dict(MAN, pose="jung_straight", x=815, y=1017, expr="scared", sweat=True, look=(-0.5, 0.0),
             head_off=(0.0, 0.0, 0.0)),
        dict(who="oma", D=150, pose="oma_sit_rest", x=420, y=1047 + drop, expr="smile", look=(0.0, 0.0),
             items=(("bag", (0.3, 1.3)),), blink=blink(T, 1))]))


# ------------------------------------------------------------------ Szene 5: Fitnessstudio
OMA_GYM = dict(who="oma", D=130, x=540, y=1356)


def guys(T, expr, pose="musk_laugh", m=0.0, bounce=True, mk=None):
    b = math.sin(T * 18) * 8 if bounce else 0
    return [dict(who="musk1", D=120, pose=pose, x=270, y=1280 + b, expr=expr, mouth=m, mouth_kind=mk,
                 look=(0.5, 0.2)),
            dict(who="musk2", D=120, pose=pose, x=820, y=1280 - b, expr=expr, mouth=m * 0.7, mouth_kind=mk,
                 look=(-0.5, 0.2), flip=True)]


def floor_dumbbell(f, v):
    from chars import dumbbell
    im = Image.new("RGBA", (int(260 * v.z), int(140 * v.z)), (0, 0, 0, 0))
    dumbbell(im, im.width / 2, im.height / 2, 120 * v.z)
    sx, sy = v.p(720, 1690)
    Wd.soft_shadow(f, sx, sy + 50 * v.z, 110 * v.z, 14 * v.z, 0.5)
    paste_c(f, im, sx, sy)


def shot_gym_laugh(t, T):
    v = View(1.32, 540, 1330)
    m = mouth("musk", T)
    return Wd.gym_frame(T, v, guys(T, "laugh", m=m) + [
        dict(OMA_GYM, pose="oma_stand_bag", expr="neutral", look=(0.0, -0.2), items=(("bag", (0.62, 1.2)),),
             blink=blink(T, 1))], pre=floor_dumbbell)


def shot_gym_point(t, T):
    v = View(2.0 + 0.1 * t, 380, 1150)
    m = mouth("musk", T)
    g = guys(T, "laugh", "musk_point", m=m)
    return Wd.gym_frame(T, v, [g[0], dict(OMA_GYM, pose="oma_stand_bag", expr="neutral",
                                         items=(("bag", (0.62, 1.2)),))], pre=floor_dumbbell)


def shot_gym_bagdown(t, T):
    v = View(2.2, 600, 1450)
    return Wd.gym_frame(T, v, [dict(OMA_GYM, pose="oma_stand_bagdown", expr="smirk", look=(0.4, 0.5),
                                    items=(("bag", (0.85, 1.55)),))], pre=floor_dumbbell)


def dust(t):
    def fn(f, v):
        d = ImageDraw.Draw(f, "RGBA")
        r = random.Random(9)
        for k in range(40):
            x = r.uniform(300, 800) + math.sin(t * 2 + k) * 20
            y = r.uniform(900, 1700) - t * 40
            sx, sy = v.p(x, y)
            rr = r.uniform(2, 5)
            d.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], fill=(255, 240, 200, 120))
    return fn


def shot_gym_lift(t, T):
    v = View(2.25 - 0.15 * t, 590, 1170)
    lifted = t > 0.28
    pose = "oma_lift" if lifted else "oma_lift_low"
    items = (("dumbbell", (0.85, -1.55), 1.3),) if lifted else (("dumbbell", (0.8, 1.2), 1.3),)
    f = Wd.gym_frame(T, v, [dict(OMA_GYM, pose=pose, expr="smirk" if lifted else "neutral", look=(0.0, 0.0),
                                 items=items, blink=False)], post=dust(t))
    if lifted:
        Wd.rays(f, 620, 700, T, (255, 230, 160), int(45 * clamp01((t - 0.28) / 0.3)), 16, 6)
        sp = emoji("✨", 90)
        for k, (x, y) in enumerate(((760, 420), (900, 560), (520, 500))):
            ph = (t * 2 + k * 0.3) % 1
            paste_c(f, sp, x, y, 0.6 + 0.5 * math.sin(ph * math.pi), 1.0)
    return f


def shot_gym_jaw(t, T):
    v = View(1.42, 540, 1250)
    jaw = 0.6 + 0.4 * ease_out(t / 0.2)
    return Wd.gym_frame(T, v, guys(T, "shock", "musk_shock", m=jaw, bounce=False, mk="o") + [
        dict(OMA_GYM, pose="oma_lift", expr="smirk", items=(("dumbbell", (0.85, -1.55), 1.3),), brow_up=1)],
                        post=dust(t + 1))


# ------------------------------------------------------------------ Szene 6: Der Dieb
BAG_BENCH = (662, 1088)


def shot_sneak(t, T):
    v = View(1.35, 620, 1030)
    x = lerp(300, 505, t / 1.5)
    bob = abs(math.sin(t * 7)) * -14
    th = dict(who="thief", D=110, pose="thief_sneak", x=x, y=1000 + bob, expr="sneaky", look=(0.8, 0.2))
    f = park_frame(T, v, oma=oma_bench(T), thief=th, flock_T=T,
                   extras=(("pre", world_bag(BAG_BENCH[0] - 30, BAG_BENCH[1] + 2, OMA_D)),))
    return dramatic(f)


def shot_grab(t, T):
    v = View(2.4, 640, 1060)
    reach = ease_out(t / 0.3)
    th = dict(who="thief", D=110, pose="thief_grab", x=lerp(470, 520, reach), y=1000, expr="sneaky",
              look=(0.8, 0.3), flip=True)
    if t < 0.35:
        oma = oma_bench(T)
        bag = (BAG_BENCH[0] - 30 + 30 * reach, BAG_BENCH[1] + 2)
    else:
        oma = oma_bench(T, pose="oma_sit_hold", flip=True, items=(), look=(0.9, 0.2), expr="glare", gl=0.1)
        bag = BAG_BENCH
    f = park_frame(T, v, oma=oma, thief=th, extras=(("post", world_bag(*bag, OMA_D)),))
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
    for (who, x, sd) in (("pass1", 190, 1), ("pass2", 590, 2)):
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


def shot_tug(t, T):
    released = t > 0.62
    sh = shake(T, 4 + 10 * clamp01(t / 0.6)) if not released else shake(T, 18 * clamp01(1 - (t - 0.62) / 0.3))
    v = View(1.5 + 0.08 * t, 650, 1040, sh)
    if not released:
        pull = math.sin(T * 25) * 6
        th = dict(who="thief", D=110, pose="thief_pull", x=470 + pull, y=1000, expr="strain", flip=True)
        oma = oma_bench(T, pose="oma_sit_pull", flip=True, items=(), look=(0.9, 0.1), expr="smirk", gl=0.1)
        bag = (608 + pull, 1080)
    else:
        dt = t - 0.62
        s = clamp01(dt * 0.35)
        x, y = Wd.fly_pos(s)
        th = dict(who="thief", D=110, pose="thief_fly", x=x - 140 * dt, y=y + 150 - 60 * dt, center=True, rot=-15 - 60 * dt,
                  expr="shock", mouth=0.9, items=(("bag", (1.35, -0.4)),))
        oma = oma_bench(T, pose="oma_sit_release", flip=True, items=(), look=(0.0, 0.0), expr="smirk", brow_up=-1)
        bag = None
    ex = []
    if bag:
        ex.append(("pre", world_bag(*bag, OMA_D)))

        def strap(f, vv):
            d = ImageDraw.Draw(f)
            a = vv.p(bag[0] + 10, bag[1] - 10)
            b = vv.p(OMA_NECK[0] - 1.3 * OMA_D, OMA_NECK[1] + 0.55 * OMA_D)
            d.line([a, b], fill=(110, 62, 30), width=int(9 * vv.z))
        ex.append(("pre", strap))
    f = park_frame(T, v, oma=oma, thief=th, extras=tuple(ex))
    f = dramatic(f)
    if released and t - 0.62 < 0.08:
        f.alpha_composite(Image.new("RGBA", f.size, (255, 255, 255, 150)))
    return f


SPLASH_T = 26.33


def fly_s(t):
    pts = [(0, 0.0), (0.22, 0.36), (0.78, 0.57), (1.18, 1.0)]
    for (a, sa), (b, sb) in zip(pts, pts[1:]):
        if t <= b:
            u = (t - a) / (b - a)
            return lerp(sa, sb, u)
    return 1.0


def shot_fly(t, T):
    s = fly_s(t)
    v = View(*HOOK_VIEW)
    after = T >= SPLASH_T
    th = None if after else thief_fly(s, T, mouth("dieb", T))
    oma = oma_bench(T, look=(0.0, 0.55), expr="smile")
    ex = [("post", lambda fr, vv: bonbon_rain(fr, vv, s if not after else 1.0 + (T - SPLASH_T), T))]
    if after:
        ex.append(("post", lambda fr, vv: splash(fr, vv, T - SPLASH_T)))
    f = park_frame(T, v, oma=oma, thief=th, extras=tuple(ex), flock_T=T, flock_scare=SPLASH_T + 0.05)
    f = dramatic(f, 0.7)
    slowmo = 0.22 < t < 0.78
    if slowmo:
        f = grade(f, sat=0.9, contrast=1.05)
    if after and T - SPLASH_T < 0.25:
        f = cam(f, 1.0 + 0.05 * (1 - (T - SPLASH_T) / 0.25), 420, 1100)
    return f


def shot_offer(t, T):
    v = View(1.9 + 0.05 * t, 540, 1000)
    take = T > 28.35
    th_pose = "thief_take" if take else "thief_wet"
    th = dict(who="thief", D=118, pose=th_pose, x=420, y=1010, expr="sad", wet=True, look=(0.7, -0.2),
              blink=blink(T, 3))
    m = mouth("oma", T)
    has_bonbon = not take
    oma = dict(who="oma", D=118, pose="oma_offer", x=705, y=860, expr="warm", look=(-0.7, 0.2), mouth=m,
               items=(("bonbon", (-1.2, 0.35)),) if has_bonbon else (), blink=blink(T, 1))

    def front(f, vv):
        draw_fountain_front(f, vv)
        r = random.Random(1)
        for k in range(6):
            bx = [205, 250, 300, 545, 590, 630][k]
            by = 1105 + r.uniform(-20, 30) + math.sin(T * 3 + k) * 3
            paste_c(f, bonbon_sprite(int(24 * vv.z), (235, 60, 60) if k % 2 else (250, 160, 40), (k * 60) % 360),
                    *vv.p(bx, by))
        if take:
            paste_c(f, bonbon_sprite(int(24 * vv.z), (235, 60, 60), 0), *vv.p(420 + 0.95 * 118, 1010 + 0.1 * 118))
        # Taube landet auf dem Kopf
        if T > 27.4:
            u = clamp01((T - 27.4) / 0.45)
            px = lerp(250, 405, ease_out(u))
            py = lerp(700, 1010 - 0.5 * 118 - 70, ease_out(u))
            img = pigeon(int(50 * vv.z), int(T * 14) % 4 if u < 1 else -1, 1)
            paste_c(f, img, *vv.p(px, py))

    f = park_frame(T, v, oma=oma, thief=None, extras=(
        ("pre", lambda fr, vv: actor(fr, vv, **th)), ("post", front),
        ("post", lambda fr, vv: splash(fr, vv, T - SPLASH_T))), flock_T=None)
    return dramatic(f, 0.7)


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
    sh = shake(T, 12 * clamp01(1 - (T - 30.9) / 0.35)) if T > 30.9 else (0, 0)
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
    (0.90, 2.00, shot_hook_oma),
    (2.00, 2.75, shot_rewind),
    (2.75, 4.30, shot_establish),
    (4.30, 5.45, shot_80),
    (5.45, 6.50, shot_knit),
    (6.50, 7.35, shot_feed),
    (7.35, 8.00, shot_smile),
    (8.00, 9.55, lambda t, T: shot_photo(t, T, False)),
    (9.55, 11.00, lambda t, T: shot_photo(t, T, True)),
    (11.00, 12.70, shot_bus_wide),
    (12.70, 13.60, shot_bus_look),
    (13.60, 14.60, shot_bus_eyes),
    (14.60, 16.00, shot_bus_after),
    (16.00, 17.20, shot_gym_laugh),
    (17.20, 18.50, shot_gym_point),
    (18.50, 19.10, shot_gym_bagdown),
    (19.10, 20.20, shot_gym_lift),
    (20.20, 21.00, shot_gym_jaw),
    (21.00, 22.50, shot_sneak),
    (22.50, 23.20, shot_grab),
    (23.20, 23.80, shot_hilfe),
    (23.80, 24.30, shot_passers),
    (24.30, 25.15, shot_tug),
    (25.15, 26.45, shot_fly),
    (26.45, 29.00, shot_offer),
    (29.00, 30.50, shot_hero),
    (30.50, 32.00, shot_hero2),
    (32.00, 34.55, shot_end),
    (34.55, 35.00, shot_hook_end),
]


def shot_at(T):
    for i, (a, b, fn) in enumerate(SHOTS):
        if a <= T < b or (i == len(SHOTS) - 1 and T >= a):
            return i, a, b, fn
    return len(SHOTS) - 1, *SHOTS[-1]
