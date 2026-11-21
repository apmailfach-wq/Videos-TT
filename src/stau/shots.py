"""Per-shot traffic + camera, rendered with Blender Cycles.

usage: python shots.py <shot> [first_frame last_frame]
Frames go to build/stau/frames/<shot>/0000.png; screen-space overlay anchors
go to build/stau/frames/<shot>/meta.json.
"""
import json, math, random, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

import world as W
from sim import overreact_lane, FPS

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "stau"
L0, L1, L2 = W.LANES
O0, O1, O2 = W.OPP_LANES


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def lerp(a, b, x):
    return a + (b - a) * x


def lerpv(a, b, x):
    return tuple(lerp(p, q, x) for p, q in zip(a, b))


# ------------------------------------------------------------------ helpers
class Alloc:
    def __init__(self, pool):
        self.pool = pool
        self.used_prev = set()
        self.reset()

    def reset(self):
        self.ci = 0; self.ti = 0; self.used = set()

    def take(self, kind="car"):
        if kind == "truck":
            o = self.pool.trucks[self.ti]; self.ti += 1
        else:
            o = self.pool.cars[self.ci]; self.ci += 1
        self.used.add(o.name)
        return o

    def finish(self):
        for o in self.pool.cars + self.pool.trucks:
            if o.name not in self.used and o.location.z > -10:
                o.location = (0, 0, -50)
        self.used_prev = self.used


def flow(al, lane_x, t, v, center, count, spacing, seed, back=250, ahead=900, trucks=0.0, yaw=0.0):
    """Endless stream of vehicles in one lane, wrapped around `center`."""
    r = random.Random(seed)
    span = back + ahead
    offs = []
    acc = 0.0
    for k in range(count):
        acc += spacing * r.uniform(0.7, 1.5)
        offs.append((acc, "truck" if r.random() < trucks else "car", r.uniform(-0.15, 0.15)))
    for base, kind, jit in offs:
        y = base + v * t
        y = (y - (center - back)) % span + (center - back)
        o = al.take(kind)
        W.place(o, lane_x + jit, y, yaw)


def opposite(al, t, center, seed=11):
    for k, x in enumerate((O0, O1, O2)):
        flow(al, x, t, -33 + 4 * k, center, 9, 120, seed + k, trucks=0.25 if k == 2 else 0.0, yaw=math.pi)


def brake_from(acc, v):
    return 1.0 if (acc < -0.7 or v < 0.4) else 0.0


# ------------------------------------------------------------------ extra props
def build_props():
    P = {}
    # hero car: wagon with tinted see-through glass, pillars, roof and interior
    hero = W.obj("hero", W.car_mesh("wagon", hero=True), (0, 0, -50))
    hero.color = (0.1, 0.32, 0.38, 0.0)   # petrol blue like the reference
    # seat + driver billboard
    img = bpy.data.images.load(str(BUILD / "driver.png"))
    dm = bpy.data.materials.new("driver")
    dm.use_nodes = True
    nt = dm.node_tree
    pb = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
    nt.links.new(tex.outputs["Color"], pb.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], pb.inputs["Alpha"])
    pb.inputs["Roughness"].default_value = 0.8
    pb.inputs["Emission Color"].default_value = (1, 1, 1, 1)
    nt.links.new(tex.outputs["Color"], pb.inputs["Emission Color"])
    pb.inputs["Emission Strength"].default_value = 0.8
    h = 0.86
    w = h * 600 / 760
    me = bpy.data.meshes.new("driverplane")
    me.from_pydata([(0, -w / 2, 0), (0, w / 2, 0), (0, w / 2, h), (0, -w / 2, h)], [], [(0, 1, 2, 3)])
    me.uv_layers.new()
    uv = me.uv_layers[0].data
    for i, c in enumerate([(1, 0), (0, 0), (0, 1), (1, 1)]):
        uv[i].uv = c
    me.materials.append(dm)
    drv = W.obj("driver", me)
    drv.parent = hero
    drv.location = (-0.45, 0.32, 0.70)
    P["hero"] = hero

    # green distance carpet
    cm = bpy.data.materials.new("carpet")
    cm.use_nodes = True
    pb = cm.node_tree.nodes["Principled BSDF"]
    pb.inputs["Base Color"].default_value = (0.1, 1.0, 0.3, 1)
    pb.inputs["Emission Color"].default_value = (0.1, 1.0, 0.35, 1)
    pb.inputs["Emission Strength"].default_value = 1.6
    pb.inputs["Alpha"].default_value = 0.55
    me = bpy.data.meshes.new("carpet")
    me.from_pydata([(-1.6, 0, 0), (1.6, 0, 0), (1.6, 1, 0), (-1.6, 1, 0)], [], [(0, 1, 2, 3)])
    me.materials.append(cm)
    P["carpet"] = W.obj("carpet", me, (0, 0, -50))

    # construction zone (lane L2 closes at Y_END)
    Y_END = 420.0
    P["Y_END"] = Y_END
    bk = []
    stripe = bpy.data.materials.new("bake")
    stripe.use_nodes = True
    nt = stripe.node_tree
    pb = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.wave_type = "BANDS"; wv.bands_direction = "DIAGONAL"
    wv.inputs["Scale"].default_value = 2.2
    wv.inputs["Distortion"].default_value = 0
    nt.links.new(tc.outputs["Object"], wv.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (0.75, 0.02, 0.02, 1)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (0.9, 0.9, 0.9, 1)
    nt.links.new(wv.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], pb.inputs["Base Color"])
    pb.inputs["Roughness"].default_value = 0.4
    lamp = W.mat("lamp", (1, 0.75, 0.1), rough=0.2, emit=(1, 0.7, 0.05), emit_strength=6)
    post = W.join_meshes("bake", [
        W.box("bp", (0.22, 0.1, 1.0), (0, 0, 0.62), stripe, bevel=0.03),
        W.box("bf", (0.45, 0.45, 0.12), (0, 0, 0.06), W.M["black"]),
        W.cyl("bl", 0.11, 0.1, (0, 0, 1.22), lamp, axis="Y"),
    ])
    pts = []
    # taper across lane L2 over 70 m, then along the lane line
    x_out, x_in = W.LANES[2] + 1.6, W.LANES[1] + W.LANE_W / 2 + 0.1
    for k in range(9):
        f = k / 8
        pts.append((lerp(x_out, x_in, f), Y_END - 32 + 32 * f))
    y = Y_END + 10
    while y < Y_END + 600:
        pts.append((x_in, y)); y += 10
    for x, y in pts:
        bk.append(W.obj("bake", post, (x, y, 0)))
    # yellow temporary edge line along the closure
    W.strip("yline", x_in - 0.12, x_in + 0.12, Y_END, Y_END + 600, 0.008, W.M["yellow"])
    # arrow trailer board (black panel, yellow chevrons)
    arrow_mat = W.mat("arrow", (1, 0.8, 0.1), emit=(1, 0.75, 0.05), emit_strength=8)
    parts = [W.box("board", (2.2, 0.15, 2.2), (0, 0, 2.6), W.M["black"]),
             W.box("trl", (2.0, 2.5, 0.7), (0, 0.8, 0.7), W.M["truckbox"]),
             W.box("leg", (0.2, 0.2, 1.5), (0, 0, 1.0), W.M["darksteel"])]
    for i in range(3):
        parts.append(W.box("chev", (0.35, 0.05, 0.12), (-0.4 + 0.4 * i, -0.1, 2.85), arrow_mat))
        parts.append(W.box("chev", (0.35, 0.05, 0.12), (-0.4 + 0.4 * i, -0.1, 2.35), arrow_mat))
    parts.append(W.box("chev", (1.4, 0.05, 0.14), (0.0, -0.1, 2.6), arrow_mat))
    board = W.obj("arrowboard", W.join_meshes("arrowboard", parts), (12.1, Y_END - 45, 0))
    board.rotation_euler.z = math.pi  # face oncoming traffic
    P["construction"] = bk + [board, bpy.data.objects["yline"]]
    return P


def show(objs, on):
    for o in objs:
        o.hide_render = not on


# ------------------------------------------------------------------ shots
class Shot:
    sim_t0 = 0.0

    def __init__(self, P):
        self.P = P

    def prepare(self):
        pass

    def frame(self, al, cam, t):
        raise NotImplementedError

    def meta(self, cam, t):
        return None


class Hook(Shot):
    """Drone over a completely stationary jam, oncoming side flows freely."""

    def prepare(self):
        r = random.Random(5)
        self.jam = []
        for li, x in enumerate(W.LANES):
            y = 60.0 + r.uniform(0, 5)
            while y < 950:
                kind = "truck" if (li == 2 and r.random() < 0.35) or (li == 1 and r.random() < 0.05) else "car"
                ln = 16 if kind == "truck" else 4.6
                self.jam.append((x + r.uniform(-0.25, 0.25), y + ln / 2, kind, r.uniform(-0.04, 0.04)))
                y += ln + r.uniform(2.2, 4.5)

    def frame(self, al, cam, t):
        creep = 0.6 * t
        for x, y, kind, yaw in self.jam:
            W.place(al.take(kind), x, y + creep, yaw, 1.0)
        opposite(al, t, 200)
        u = t / 6.5
        loc = (lerp(8.0, 5.0, u), lerp(46, 80, u), lerp(7, 24, smooth(u)))
        aim_ = (lerp(5.5, 5.0, u), lerp(110, 190, u), 0)
        W.aim(cam, loc, aim_, lens=20)


class Phantom(Shot):
    """Shared overreaction simulation for brake / wave / aerial."""

    def prepare(self):
        self.lanes = []
        r = random.Random(8)
        cfg = [(L0, 2.6, 6.0, 30.0, 0), (L1, 1.5, 7.0, 0.0, 0), (L2, 3.2, 6.0, -12.0, 1)]
        for x, tb, d0, ylead, has_trucks in cfg:
            n = 38
            kinds = ["truck" if (has_trucks and r.random() < 0.3 and i > 2) else "car" for i in range(n)]
            lens = np.array([16.0 if k == "truck" else 4.6 for k in kinds])
            Y, V, A = overreact_lane(n=n, tb=tb, d0=d0, y_lead=900 + ylead, lengths=lens, t_end=24,
                                     v_init=24.0 if x != L0 else 26.0)
            # positions in sim are the vehicle front; place() wants the centre
            self.lanes.append((x, kinds, Y - lens / 2, V, A))

    def put(self, al, t):
        f = min(int(t * FPS), self.lanes[0][2].shape[0] - 1)
        for x, kinds, Y, V, A in self.lanes:
            for i, k in enumerate(kinds):
                W.place(al.take(k), x, Y[f, i], 0.0, brake_from(A[f, i], V[f, i]))
        return f


PH = None


def phantom(P):
    global PH
    if PH is None:
        PH = Phantom(P); PH.prepare()
    return PH


class Brake(Shot):
    t0 = 0.4

    def frame(self, al, cam, t):
        ph = phantom(self.P)
        st = self.t0 + t
        f = ph.put(al, st)
        x, kinds, Y, V, A = ph.lanes[1]
        yc = Y[f, 2]
        opposite(al, st, yc)
        # chase camera behind car #2, slightly to the left, sees car #1 and the leader
        loc = (L1 - 0.6, yc - 9.5, 2.9)
        W.aim(cam, loc, (L1 + 0.3, yc + 45, 0.2), lens=21)


class Wave(Shot):
    t0 = 4.2

    def frame(self, al, cam, t):
        ph = phantom(self.P)
        st = self.t0 + t
        f = ph.put(al, st)
        x, kinds, Y, V, A = ph.lanes[1]
        yc = Y[f, 8]
        opposite(al, st, yc)
        u = t / 5.0
        loc = (lerp(L1 - 3, L1 + 1, u), yc - 22, lerp(11, 9, u))
        W.aim(cam, loc, (L1, Y[f, 3] - 20, 0), lens=22)


class Aerial(Shot):
    t0 = 9.1

    def frame(self, al, cam, t):
        ph = phantom(self.P)
        st = self.t0 + t
        f = ph.put(al, st)
        x, kinds, Y, V, A = ph.lanes[1]
        yc = Y[int(self.t0 * FPS), 9] + 15 * t        # slowly drift forward
        opposite(al, st, yc)
        u = t / 5.6
        ang = lerp(-0.5, -0.2, u)
        loc = (6 + 45 * math.sin(ang), yc - 45 * math.cos(ang) - 10, lerp(42, 36, u))
        W.aim(cam, loc, (6, yc + 45, 0), lens=22)


class Gap(Shot):
    """Hero keeps 'halber Tacho' (50 m at 100 km/h) – green carpet shows the gap."""
    V = 27.8

    def frame(self, al, cam, t):
        hero = self.P["hero"]
        hy = 100 + self.V * t
        lead_y = hy + 4.6 + 50
        W.place(hero, L1, hy)
        W.place(al.take(), L1, lead_y)
        flow(al, L1, t, self.V, hy + 300, 6, 70, 31, back=0, ahead=600)  # further ahead
        flow(al, L0, t, 34, hy, 7, 60, 32, back=120, ahead=500)
        flow(al, L2, t, 22, hy, 8, 45, 33, back=120, ahead=500, trucks=0.45)
        opposite(al, t, hy)
        c = self.P["carpet"]
        grow = smooth((t - 1.6) / 1.0)
        c.location = (L1, hy + 2.4, 0.03 if grow > 0 else -50)
        c.scale = (1, max(grow, 0.001) * (lead_y - hy - 4.6 - 0.2), 1)
        loc = (L1 - 0.4, hy - 10.5, 3.6)
        W.aim(cam, loc, (L1, hy + 40, 0), lens=21)

    def meta(self, cam, t):
        hy = 100 + self.V * t
        p = world_to_camera_view(bpy.context.scene, cam, Vector((L1, hy + 2.4 + 25, 0.05)))
        return {"label": [p.x, 1 - p.y]}


class Roll(Shot):
    """Side view of the hero (cartoon driver) rolling smoothly while the next lane stop-and-goes."""

    def frame(self, al, cam, t):
        hero = self.P["hero"]
        hy = 300 + 6.0 * t
        W.place(hero, L0, hy)
        # car ahead of hero, also smooth
        W.place(al.take(), L0, hy + 26 + 6.0 * 0)
        W.place(al.take(), L0, hy - 30)
        # lane L1/L2: stop & go waves (brake lights flicker)
        for li, x in enumerate((L1, L2)):
            for k in range(14):
                ph = 0.9 * k + li * 1.7
                base = 300 - 60 + k * 15.5 + li * 6
                # v = 6 + 5.5*sin(w t + ph)  → integrate analytically
                w = 1.4
                y = base + 6 * t - 5.5 / w * (math.cos(w * t + ph) - math.cos(ph))
                acc = 5.5 * w * math.cos(w * t + ph)
                vel = 6 + 5.5 * math.sin(w * t + ph)
                kind = "truck" if (li == 1 and k % 5 == 2) else "car"
                W.place(al.take(kind), x, y + (6 if kind == "truck" else 0), 0, brake_from(acc - 1.5, vel))
        opposite(al, t, hy)
        u = t / 11.0
        loc = (-0.6, hy + lerp(-2.6, 0.6, u), 1.55)
        W.aim(cam, loc, (L0 - 0.45, hy + lerp(0.1, -0.5, u), 1.18), lens=19)


class Zipper(Shot):
    """Right lane ends – both lanes used to the end, then merge alternately."""
    V = 5.0

    def frame(self, al, cam, t):
        ye = self.P["Y_END"]
        s = 9.6
        lane_r_x = L2
        y_front = ye + 260 + self.V * t
        # left lane (L1): car every 2s before the merge zone, every s after
        n = 60
        for k in range(n):
            y = y_front - k * s
            if y < ye:  # before merge point: only even slots are L1 cars
                if k % 2:
                    # odd slot = car still in the right lane, merges near the end
                    x = lane_r_x
                    m = smooth((y - (ye - 28)) / 22)
                    x = lerp(lane_r_x, L1, m)
                    yaw = -0.12 * math.sin(math.pi * m) if 0 < m < 1 else 0.0
                    W.place(al.take(), x, y, yaw, 0.0 if k % 3 else 1.0)
                    continue
            W.place(al.take("truck" if k % 11 == 4 else "car"), L1, y, 0.0, 1.0 if k % 4 == 0 else 0.0)
        # fast lane: dense slow traffic too
        for k in range(45):
            y = y_front + 5 - k * 11.5
            W.place(al.take(), L0, y, 0.0, 1.0 if k % 5 == 1 else 0.0)
        opposite(al, t, ye)
        cy = ye - 88 + self.V * t
        loc = (L2 + 0.9, cy, 3.4)
        W.aim(cam, loc, (L1 + 2.2, cy + 55, 0.4), lens=21)

    def meta(self, cam, t):
        ye = self.P["Y_END"]
        p = world_to_camera_view(bpy.context.scene, cam, Vector((L1 + 1.8, ye - 6, 0.5)))
        return {"merge": [p.x, 1 - p.y]}


class Posts(Shot):
    """Leitpfosten every 50 m: one post gap between you and the car in front."""
    V = 27.8

    def frame(self, al, cam, t):
        hero = self.P["hero"]
        hy = 612 + self.V * t
        W.place(hero, L1, hy)
        W.place(al.take(), L1, hy + 4.6 + 50)
        flow(al, L1, t, self.V, hy + 300, 5, 80, 51, back=0, ahead=600)
        flow(al, L0, t, 34, hy, 6, 70, 52, back=120, ahead=500)
        flow(al, L2, t, 21, hy, 6, 55, 53, back=120, ahead=500, trucks=0.5)
        opposite(al, t, hy)
        loc = (L1 + 2.0, hy - 9.0, 3.3)
        W.aim(cam, loc, (L1 + 2.6, hy + 38, 0.3), lens=22)

    def meta(self, cam, t):
        hy = 612 + self.V * t
        sc = bpy.context.scene
        front = hy + 2.3
        p1 = math.ceil(front / 50.0) * 50.0
        pts = {}
        for name, y in (("p1", p1), ("p2", p1 + 50), ("p0", p1 - 50)):
            p = world_to_camera_view(sc, cam, Vector((12.15, y, 0.9)))
            pts[name] = [p.x, 1 - p.y, p.z]
        return pts


class Gasse(Shot):
    """Standing traffic forms the emergency corridor, ambulance drives through."""

    def prepare(self):
        r = random.Random(17)
        self.cars = []
        for li, x in enumerate(W.LANES):
            y = 190.0 + r.uniform(0, 4)
            while y < 520:
                kind = "truck" if (li == 2 and r.random() < 0.3) else "car"
                ln = 16 if kind == "truck" else 4.6
                self.cars.append((li, x, y + ln / 2, kind, r.uniform(-0.6, 0.4)))
                y += ln + r.uniform(2.5, 4.0)

    def frame(self, al, cam, t):
        shift = {0: -0.95, 1: 1.0, 2: 1.25}
        for li, x, y, kind, delay in self.cars:
            s = smooth((t - 0.9 - delay - (y - 190) / 400) / 1.8)
            yaw = (0.07 if li == 0 else -0.07) * math.sin(math.pi * s)
            W.place(al.take(kind), x + shift[li] * s, y + 1.2 * s, yaw, 1.0)
        opposite(al, t, 300)
        amb = self.P["pool"].ambulance
        ta = max(0.0, t - 2.4)
        ay = 163 + 6 * ta + 1.1 * ta * ta
        amb.location = ((W.LANES[0] + W.LANES[1]) / 2 + 0.05, ay, 0)
        amb.rotation_euler = (0, 0, 0)
        c = amb.color
        amb.color = (c[0], c[1], c[2], 1.0 if (t * 3.0) % 1 < 0.5 else 0.0)
        u = t / 7.7
        loc = (lerp(4.6, 3.9, u), lerp(170, 182, u), lerp(11, 9.5, u))
        W.aim(cam, loc, (3.8, lerp(250, 262, u), 0), lens=22)


class Outro(Shot):
    V = 30.0

    def frame(self, al, cam, t):
        cy = 150 + self.V * t
        flow(al, L0, t, 33, cy, 14, 55, 41, back=150, ahead=700)
        flow(al, L1, t, 30, cy, 14, 55, 42, back=150, ahead=700)
        flow(al, L2, t, 25, cy, 14, 60, 43, back=150, ahead=700, trucks=0.4)
        hero = self.P["hero"]
        W.place(hero, L1, cy + 12)
        opposite(al, t, cy)
        u = smooth(t / 9.5)
        loc = (lerp(L1, -4, u), cy + lerp(-2, -30, u), lerp(3.2, 70, u))
        W.aim(cam, loc, (L1, cy + lerp(60, 120, u), 0), lens=lerp(20, 22, u))


SHOTS = {"hook": Hook, "brake": Brake, "wave": Wave, "aerial": Aerial, "gap": Gap, "posts": Posts,
         "roll": Roll, "zipper": Zipper, "gasse": Gasse, "outro": Outro}


def frames_for(shot):
    tim = json.loads((BUILD / "timings.json").read_text())
    from script import SCENES
    for i, s in enumerate(SCENES):
        if s["shot"] == shot:
            pad = 1.6 if i == len(SCENES) - 1 else 0.3
            return int(round((tim[i]["duration"] + pad) * FPS))
    raise KeyError(shot)


def main():
    name = sys.argv[1]
    n = frames_for(name)
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    last = int(sys.argv[3]) if len(sys.argv) > 3 else n - 1
    step = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    pool, cam = W.build_all()
    P = build_props()
    P["pool"] = pool
    pool.ambulance.location = (0, 0, -50)
    show(P["construction"], name == "zipper")
    shot = SHOTS[name](P)
    shot.prepare()
    al = Alloc(pool)
    out = BUILD / "frames" / name
    out.mkdir(parents=True, exist_ok=True)
    metaf = out / "meta.json"
    meta = json.loads(metaf.read_text()) if metaf.exists() else {}
    sc = bpy.context.scene
    import os
    if os.environ.get("THREADS"):
        sc.render.threads_mode = "FIXED"
        sc.render.threads = int(os.environ["THREADS"])
    for fi in range(first, min(last, n - 1) + 1, step):
        t = fi / FPS
        al.reset()
        if name not in ("gap", "posts", "roll", "outro"):
            P["hero"].location = (0, 0, -50)
        P["carpet"].location.z = -50 if name != "gap" else P["carpet"].location.z
        shot.frame(al, cam, t)
        al.finish()
        bpy.context.view_layer.update()
        m = shot.meta(cam, t)
        if m:
            meta[str(fi)] = m
        sc.render.filepath = str(out / f"{fi:04d}.png")
        if os.environ.get("SKIP_EXISTING") and Path(sc.render.filepath).exists():
            continue
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[{name}] frame {fi}/{n - 1} {time.time() - t0:.1f}s", flush=True)
    metaf.write_text(json.dumps(meta))


if __name__ == "__main__":
    main()
