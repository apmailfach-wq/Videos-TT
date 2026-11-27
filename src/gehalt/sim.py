"""Physik-Level 'Schafft es mein Gehalt bis zum Urlaub?' (deutsches Leben, 3.350 € brutto).

Ablauf von oben nach unten:
 1. Schacht mit 5 Schranken = Lohnabzüge (jede hält den Ball kurz an, zieht ab, zerbricht)
 2. Rotoren = Fixkosten (Warmmiete, Strom, Handy) – je einmal pro Monat
 3. Plinko = Alltag (Kaffee, Döner, Pizza ...), grüner Pfand-Bumper
 4. Kammer = Überraschungen (Kugeln mit Gesicht kreisen und rempeln)
 5. Monatsende = Kolben (Kfz, Deutschlandticket, Knöllchen), Steuererstattung, NK-Nachzahlung
    und drei Taschen: Dispo / Urlaub / Nudeln bis zum 1.
Deterministisch: gleicher Seed = gleicher Lauf.
"""
import math
import random

import pymunk

from daten import BRUTTO, ITEMS

W = 1080
FPS = 60
SUB = 4
DT = 1.0 / (FPS * SUB)
GRAVITY = 1200
R_MAX, R_MIN = 62, 33
WALL_L, WALL_R = 40, W - 40
POCKET_TOP = 7650
LEVEL_END = 8050
VMAX = 1450
BALL, OBST, WALL = 1, 2, 3

RED = (255, 59, 78)
ORANGE = (255, 150, 50)
YELLOW = (255, 214, 50)
PURPLE = (150, 95, 255)
PINK = (255, 80, 170)
TOOTH = (235, 245, 255)
GREEN = (40, 220, 120)
BLUE = (60, 150, 255)
TEAL = (0, 200, 200)
GREY = (120, 125, 150)
GOLD = (255, 200, 40)
STEEL = (120, 170, 255)


class Obstacle:
    def __init__(self, key, kind, color, shapes, body, **kw):
        self.key = key
        self.kind = kind
        self.cost = ITEMS[key][2]
        self.color = color
        self.shapes = shapes
        self.body = body
        self.last_hit = -10.0
        self.hits = 0
        self.max_hits = kw.pop("max_hits", 99)
        self.cooldown = kw.pop("cooldown", 0.8)
        self.open_at = None          # barriers: time they break
        self.extra = kw


class Level:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.space = pymunk.Space()
        self.space.gravity = (0, GRAVITY)
        self.space.iterations = 20
        self.obstacles, self.by_shape, self.statics, self.movers = [], {}, [], []
        self.money = BRUTTO
        self.t = 0.0
        self.events = []
        self.best_y, self.best_t = 0, 0.0
        self._build()
        self._ball()
        self.space.on_collision(BALL, OBST, begin=self._on_obst)
        self.space.on_collision(BALL, WALL, post_solve=self._on_wall)

    # ------------------------------------------------------------ builders
    def seg(self, a, b, r=8, elast=0.8):
        s = pymunk.Segment(self.space.static_body, a, b, r)
        s.elasticity, s.friction, s.collision_type = elast, 0.3, WALL
        self.space.add(s)
        self.statics.append((a, b, r))

    def add_obst(self, ob):
        self.obstacles.append(ob)
        for s in ob.shapes:
            s.collision_type = OBST
            self.by_shape[s] = ob
        return ob

    def barrier(self, key, y, x0, x1):
        b = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        b.position = ((x0 + x1) / 2, y)
        s = pymunk.Poly.create_box(b, (x1 - x0, 22), radius=4)
        s.elasticity, s.friction = 0.25, 0.8
        self.space.add(b, s)
        self.add_obst(Obstacle(key, "barrier", STEEL, [s], b, w=x1 - x0, h=22, max_hits=1))

    def spinner(self, key, cx, cy, length, thick, omega, phase, color):
        b = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        b.position, b.angle, b.angular_velocity = (cx, cy), phase, omega
        s = pymunk.Poly.create_box(b, (length, thick), radius=6)
        s.elasticity, s.friction = 0.9, 0.5
        hub = pymunk.Circle(self.space.static_body, 16, (cx, cy))
        hub.elasticity, hub.collision_type = 0.8, WALL
        self.space.add(b, s, hub)
        self.add_obst(Obstacle(key, "spinner", color, [s], b, length=length, thick=thick, max_hits=1))

    def peg(self, key, x, y, r, color, kind="peg", elast=0.85, **kw):
        s = pymunk.Circle(self.space.static_body, r, (x, y))
        s.elasticity, s.friction = elast, 0.2
        self.space.add(s)
        return self.add_obst(Obstacle(key, kind, color, [s], self.space.static_body, x=x, y=y, r=r, **kw))

    def enemy(self, key, ax, ay, r, color, orbit, speed, phase, mass=3.0, max_hits=1):
        anchor = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        anchor.position = (ax + orbit * math.cos(phase), ay + orbit * math.sin(phase) * 0.6)
        b = pymunk.Body(mass, pymunk.moment_for_circle(mass, 0, r))
        b.position = anchor.position
        s = pymunk.Circle(b, r)
        s.elasticity, s.friction = 0.9, 0.4
        spring = pymunk.DampedSpring(anchor, b, (0, 0), (0, 0), 0, 260 * mass, 6 * mass)
        self.space.add(anchor, b, s, spring)

        def drive(t, anchor=anchor):
            a = phase + speed * t
            tx, ty = ax + orbit * math.cos(a), ay + orbit * math.sin(a) * 0.6
            anchor.velocity = ((tx - anchor.position.x) * FPS * SUB, (ty - anchor.position.y) * FPS * SUB)
        self.movers.append(drive)

        def vfunc(body, g, damping, dt):
            pymunk.Body.update_velocity(body, (0, GRAVITY * 0.15), 0.995, dt)
        b.velocity_func = vfunc
        self.add_obst(Obstacle(key, "enemy", color, [s], b, r=r, cooldown=1.2, max_hits=max_hits))

    def slider(self, key, kind, y, w, h, x0, x1, period, phase, color, max_hits=1):
        b = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        b.position = (x0, y)
        s = pymunk.Poly.create_box(b, (w, h), radius=8)
        s.elasticity, s.friction = 0.95, 0.4
        self.space.add(b, s)

        def drive(t, b=b):
            u = 0.5 - 0.5 * math.cos(2 * math.pi * t / period + phase)
            b.velocity = ((x0 + (x1 - x0) * u - b.position.x) * FPS * SUB, 0)
        self.movers.append(drive)
        self.add_obst(Obstacle(key, kind, color, [s], b, w=w, h=h, max_hits=max_hits))

    def _build(self):
        rng = self.rng
        self.seg((WALL_L, -900), (WALL_L, LEVEL_END), 10)
        self.seg((WALL_R, -900), (WALL_R, LEVEL_END), 10)
        self.seg((WALL_L, LEVEL_END), (WALL_R, LEVEL_END), 10)

        # --- 1. Schacht mit Lohnabzügen
        cx0, cx1 = 395, 685
        self.seg((WALL_L, 430), (cx0, 640), 9)
        self.seg((WALL_R, 430), (cx1, 640), 9)
        self.seg((cx0, 640), (cx0, 1560), 9)
        self.seg((cx1, 640), (cx1, 1560), 9)
        for i, key in enumerate(["lohnsteuer", "rente", "kranken", "pflege", "arbeitslos"]):
            self.barrier(key, 780 + i * 170, cx0 + 9, cx1 - 9)

        # --- 2. Fixkosten
        self.spinner("miete", 540, 2000, 620, 52, 1.15, rng.uniform(0, math.pi), RED)
        self.spinner("strom", 320, 2560, 400, 44, -1.6, rng.uniform(0, math.pi), ORANGE)
        self.spinner("handy", 760, 2620, 400, 44, 1.6, rng.uniform(0, math.pi), BLUE)
        self.seg((WALL_L, 2250), (160, 2310), 8)
        self.seg((WALL_R, 2250), (920, 2310), 8)

        # --- 3. Alltag-Plinko
        top, gap = 3150, 150
        icons = ["kaffee", "brezel", "doener", "pizza", "bier", "paket", "kaffee", "doener", "brezel", "bier"]
        k = 0
        for r in range(6):
            y = top + r * gap
            off = 0 if r % 2 == 0 else 75
            for i in range(7):
                x = 165 + off + i * 150
                if x > WALL_R - 110:
                    continue
                if r == 2 and i == 3:
                    self.peg("pfand", x, y, 36, GREEN, kind="bonus", elast=1.1, cooldown=0.6, max_hits=3)
                    continue
                key = icons[(k * 7 + r * 3) % len(icons)]
                k += 1
                self.peg(key, x, y, 25, (255, 255, 255), cooldown=0.4)
            self.seg((WALL_L, y - 70), (WALL_L + 62, y - 10), 7)
            self.seg((WALL_R, y - 70), (WALL_R - 62, y - 10), 7)
        self.seg((WALL_L, 4080), (200, 4160), 8)
        self.seg((WALL_R, 4080), (880, 4160), 8)

        # --- 4. Überraschungen
        self.enemy("einkauf", 300, 4400, 88, ORANGE, 130, 1.5, rng.uniform(0, 6.28), max_hits=4)
        self.enemy("zahnarzt", 760, 4600, 96, TOOTH, 110, -1.3, rng.uniform(0, 6.28), mass=5)
        self.enemy("gez", 330, 4870, 70, BLUE, 120, 2.0, rng.uniform(0, 6.28))
        self.enemy("gym", 760, 5000, 70, PURPLE, 100, -1.9, rng.uniform(0, 6.28))
        self.enemy("streaming", 320, 5220, 70, PINK, 110, 1.7, rng.uniform(0, 6.28))
        self.enemy("liefer", 740, 5330, 72, TEAL, 100, -2.2, rng.uniform(0, 6.28))
        self.seg((WALL_L, 5480), (220, 5570), 8)
        self.seg((WALL_R, 5480), (860, 5570), 8)

        # --- 5. Monatsende
        self.slider("kfz", "piston", 5750, 420, 64, WALL_L + 10, WALL_L + 440, 2.6, rng.uniform(0, 6.28), RED)
        self.slider("ticket", "piston", 6050, 420, 64, WALL_R - 10, WALL_R - 440, 2.3, rng.uniform(0, 6.28), RED)
        self.peg("erstattung", 540, 6330, 50, GREEN, kind="bonus", elast=1.15, max_hits=1)
        self.slider("knoellchen", "piston", 6600, 380, 64, WALL_L + 10, WALL_L + 460, 2.0, rng.uniform(0, 6.28), RED)
        self.peg("geschenk", 300, 6850, 25, (255, 255, 255), cooldown=0.4)
        self.peg("kaffee", 780, 6850, 25, (255, 255, 255), cooldown=0.4)
        self.spinner("nachzahlung", 540, 7250, 520, 48, 1.3 * rng.choice([-1, 1]), rng.uniform(0, math.pi), RED)
        self.pockets = [("dispo", WALL_L, 390, RED), ("urlaub", 390, 690, GOLD), ("nudeln", 690, WALL_R, GREY)]
        for x in (390, 690):
            self.seg((x, POCKET_TOP), (x, LEVEL_END), 12)

    def _ball(self):
        rng = self.rng
        b = pymunk.Body(1, pymunk.moment_for_circle(1, 0, R_MAX))
        b.position = (540 + rng.uniform(-200, 200), 300)
        b.velocity = (rng.uniform(-250, 250), 0)

        def vfunc(body, g, damping, dt):
            pymunk.Body.update_velocity(body, g, 0.999, dt)
            sp = body.velocity.length
            if sp > VMAX:
                body.velocity = body.velocity * (VMAX / sp)
        b.velocity_func = vfunc
        s = pymunk.Circle(b, R_MAX)
        s.elasticity, s.friction, s.collision_type = 0.7, 0.4, BALL
        self.space.add(b, s)
        self.ball, self.ball_shape = b, s

    # ----------------------------------------------------------- callbacks
    def _on_obst(self, arb, space, data):
        ob = self.by_shape.get(arb.shapes[1])
        if ob is None:
            return
        if self.t - ob.last_hit < ob.cooldown or ob.hits >= ob.max_hits:
            p = self.ball.position
            self.events.append((self.t, "bounce", {"x": p.x, "y": p.y, "e": 0.5}))
            return
        ob.last_hit = self.t
        ob.hits += 1
        self.money += ob.cost
        if ob.kind == "barrier":
            ob.open_at = self.t + 0.5
        pts = arb.contact_point_set.points
        p = pts[0].point_a if pts else self.ball.position
        self.events.append((self.t, "hit", {"key": ob.key, "cost": ob.cost, "x": p.x, "y": p.y,
                                            "color": ob.color, "money": self.money,
                                            "idx": self.obstacles.index(ob)}))

    def _on_wall(self, arb, space, data):
        if arb.is_first_contact and arb.total_impulse.length > 250:
            p = self.ball.position
            self.events.append((self.t, "bounce", {"x": p.x, "y": p.y,
                                                   "e": min(arb.total_impulse.length / 1500, 1)}))

    # ---------------------------------------------------------------- step
    def radius(self):
        f = max(0.0, min(1.0, self.money / BRUTTO))
        return R_MIN + (R_MAX - R_MIN) * f

    def step_frame(self, nsub=SUB):
        for _ in range(nsub):
            for m in self.movers:
                m(self.t)
            self.space.step(DT)
            self.t += DT
            for ob in self.obstacles:
                if ob.open_at is not None and self.t >= ob.open_at and ob.shapes[0].space is not None:
                    self.space.remove(ob.shapes[0])
                    self.events.append((self.t, "break", {"idx": self.obstacles.index(ob)}))
        y = self.ball.position.y
        if y > self.best_y + 25:
            self.best_y, self.best_t = y, self.t
        elif self.t - self.best_t > 1.6 and y < POCKET_TOP:
            dx = 1 if self.ball.position.x < 540 else -1
            self.ball.velocity = (dx * self.rng.uniform(380, 520), -self.rng.uniform(250, 420))
            self.best_t = self.t
        r = self.radius()
        if abs(self.ball_shape.radius - r) > 0.3:
            self.ball_shape.unsafe_set_radius(self.ball_shape.radius + (r - self.ball_shape.radius) * 0.2)

    def snapshot(self):
        b = self.ball
        return {"t": self.t, "bx": b.position.x, "by": b.position.y, "br": self.ball_shape.radius,
                "money": self.money,
                "obs": [(o.body.position.x, o.body.position.y, o.body.angle) for o in self.obstacles]}


def run(seed, max_frames=FPS * 80, record=False, tail=1.0):
    lv = Level(seed)
    frames, result, settle = [], None, None
    stuck_y, stuck_since = 0, 0
    for f in range(max_frames):
        by = lv.ball.position.y
        slow = POCKET_TOP - 800 < by < POCKET_TOP + 120 and settle is None
        ev0 = len(lv.events)
        lv.step_frame(2 if slow else SUB)
        if record:
            snap = lv.snapshot()
            snap["events"], snap["slow"] = lv.events[ev0:], slow
            frames.append(snap)
        by = lv.ball.position.y
        if by > stuck_y + 40:
            stuck_y, stuck_since = by, f
        elif f - stuck_since > FPS * 7 and settle is None:
            result = "stuck"
            break
        if by > POCKET_TOP + 150 and settle is None:
            x = lv.ball.position.x
            result = next(n for n, x0, x1, _ in lv.pockets if x0 <= x < x1 + 1)
            settle = f
            ev = (lv.t, "pocket", {"name": result, "x": x, "y": by})
            lv.events.append(ev)
            if record:
                frames[-1]["events"].append(ev)
        if settle is not None and f - settle > FPS * tail:
            break
    hits = [e for e in lv.events if e[1] == "hit"]
    return {"seed": seed, "result": result or "timeout", "money": lv.money, "frames": frames,
            "n_frames": f + 1, "hits": hits, "level": lv}


if __name__ == "__main__":
    import sys
    from collections import Counter
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    c = Counter()
    for s in range(n):
        r = run(s)
        c[r["result"]] += 1
        keys = sorted({h[2]["key"] for h in r["hits"]})
        print(s, r["result"], r["money"] / 100, round(r["n_frames"] / FPS, 1), len(r["hits"]), keys)
    print(c)
