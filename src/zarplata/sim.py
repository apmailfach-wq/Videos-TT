"""Physics level: 'Will my salary survive until vacation?'

A green ball (the salary) falls through a tall level full of life's expenses.
Every hit costs money; the ball shrinks with the balance. Deterministic: the
same seed always produces the same run, so we can search for a dramatic seed
and then render it frame by frame from the recording.
"""
import math
import random

import pymunk

from texts import T

W = 1080
FPS = 60
SUB = 4                     # physics substeps per frame (1/240 s)
DT = 1.0 / (FPS * SUB)
GRAVITY = 1250
START_MONEY = 85_000
R_MAX, R_MIN = 54, 30
WALL_L, WALL_R = 40, W - 40
LEVEL_END = 7300
POCKET_TOP = 6900           # top of the pocket dividers
VMAX = 1500

BALL, OBST, WALL = 1, 2, 3

RED = (255, 59, 78)
ORANGE = (255, 140, 40)
YELLOW = (255, 214, 50)
PURPLE = (160, 90, 255)
PINK = (255, 80, 170)
TOOTH = (235, 245, 255)
GREEN = (40, 230, 120)
GOLD = (255, 200, 40)
GREY = (120, 125, 150)
BLUE = (60, 150, 255)


class Obstacle:
    def __init__(self, key, kind, cost, color, shapes, body, **kw):
        self.key = key            # text key
        self.kind = kind          # spinner / peg / bumper / enemy / piston / gate / static
        self.cost = cost          # negative = money lost, positive = bonus
        self.color = color
        self.shapes = shapes
        self.body = body
        self.last_hit = -10.0
        self.hits = 0
        self.max_hits = kw.pop("max_hits", 99)
        self.cooldown = kw.pop("cooldown", 0.8)
        self.extra = kw


class Level:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.space = pymunk.Space()
        self.space.gravity = (0, GRAVITY)
        self.space.iterations = 20
        self.obstacles = []
        self.by_shape = {}
        self.statics = []          # (a, b, radius) static wall segments for drawing
        self.movers = []           # callables(t) to drive kinematic bodies
        self.money = START_MONEY
        self.t = 0.0
        self.events = []           # (t, type, payload)
        self.best_y, self.best_t = 0, 0.0
        self._build()
        self._ball()
        self.space.on_collision(BALL, OBST, begin=self._on_obst)
        self.space.on_collision(BALL, WALL, post_solve=self._on_wall)

    # ------------------------------------------------------------------ build
    def seg(self, a, b, r=8, elast=0.8, draw=True):
        s = pymunk.Segment(self.space.static_body, a, b, r)
        s.elasticity, s.friction, s.collision_type = elast, 0.3, WALL
        self.space.add(s)
        if draw:
            self.statics.append((a, b, r))
        return s

    def add_obst(self, ob):
        self.obstacles.append(ob)
        for s in ob.shapes:
            s.collision_type = OBST
            self.by_shape[s] = ob

    def spinner(self, key, cx, cy, length, thick, omega, phase, cost, color):
        b = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        b.position = (cx, cy)
        b.angle = phase
        b.angular_velocity = omega
        s = pymunk.Poly.create_box(b, (length, thick), radius=6)
        s.elasticity, s.friction = 0.9, 0.5
        self.space.add(b, s)
        self.add_obst(Obstacle(key, "spinner", cost, color, [s], b,
                               length=length, thick=thick, cooldown=1.0, max_hits=1))
        # small hub
        hub = pymunk.Circle(self.space.static_body, 14, (cx, cy))
        hub.elasticity, hub.collision_type = 0.8, WALL
        self.space.add(hub)

    def peg(self, key, x, y, r, cost, color, kind="peg", elast=0.85, **kw):
        s = pymunk.Circle(self.space.static_body, r, (x, y))
        s.elasticity, s.friction = elast, 0.2
        self.space.add(s)
        self.add_obst(Obstacle(key, kind, cost, color, [s], self.space.static_body,
                               x=x, y=y, r=r, **kw))

    def enemy(self, key, ax, ay, r, cost, color, orbit, speed, phase, mass=3.0):
        anchor = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        anchor.position = (ax + orbit * math.cos(phase), ay + orbit * math.sin(phase))
        b = pymunk.Body(mass, pymunk.moment_for_circle(mass, 0, r))
        b.position = anchor.position
        s = pymunk.Circle(b, r)
        s.elasticity, s.friction = 0.9, 0.4
        spring = pymunk.DampedSpring(anchor, b, (0, 0), (0, 0), 0, 260 * mass, 6 * mass)
        self.space.add(anchor, b, s, spring)

        def drive(t, anchor=anchor):
            a = phase + speed * t
            target = (ax + orbit * math.cos(a), ay + orbit * math.sin(a) * 0.6)
            anchor.velocity = ((target[0] - anchor.position.x) * FPS * SUB,
                               (target[1] - anchor.position.y) * FPS * SUB)
        self.movers.append(drive)
        # enemies don't feel gravity strongly: counter it with the spring + custom velocity func
        def vfunc(body, g, damping, dt):
            pymunk.Body.update_velocity(body, (0, GRAVITY * 0.15), 0.995, dt)
        b.velocity_func = vfunc
        self.add_obst(Obstacle(key, "enemy", cost, color, [s], b, r=r, cooldown=1.2))

    def slider(self, key, kind, y, w, h, x0, x1, period, phase, cost, color, max_hits=99):
        b = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        b.position = (x0, y)
        s = pymunk.Poly.create_box(b, (w, h), radius=8)
        s.elasticity, s.friction = 0.95, 0.4
        self.space.add(b, s)

        def drive(t, b=b):
            u = 0.5 - 0.5 * math.cos(2 * math.pi * t / period + phase)
            tx = x0 + (x1 - x0) * u
            b.velocity = ((tx - b.position.x) * FPS * SUB, 0)
        self.movers.append(drive)
        self.add_obst(Obstacle(key, kind, cost, color, [s], b, w=w, h=h,
                               cooldown=1.0, max_hits=max_hits))

    def _build(self):
        rng = self.rng
        # outer walls
        self.seg((WALL_L, -900), (WALL_L, LEVEL_END), 10)
        self.seg((WALL_R, -900), (WALL_R, LEVEL_END), 10)
        self.seg((WALL_L, LEVEL_END), (WALL_R, LEVEL_END), 10)
        # spawn shelf: slight slopes guiding the ball to the centre
        self.seg((WALL_L, 520), (300, 640), 8)
        self.seg((WALL_R, 520), (780, 640), 8)

        # --- 1. RENT and UTILITIES spinners
        ph = rng.uniform(0, math.pi)
        self.spinner("rent", 540, 1050, 560, 46, 1.25, ph, -30_000, RED)
        self.spinner("util_spin", 330, 1650, 400, 40, -1.7, rng.uniform(0, math.pi), -7_500, RED)
        self.spinner("util_spin", 760, 1700, 400, 40, 1.7, rng.uniform(0, math.pi), -7_500, RED)
        # deflectors so the ball can't slide down the wall
        self.seg((WALL_L, 1300), (150, 1360), 8)
        self.seg((WALL_R, 1300), (930, 1360), 8)

        # --- 2. TAX peg field
        top, rows, gap = 2150, 7, 150
        for r in range(rows):
            y = top + r * gap
            off = 0 if r % 2 == 0 else 75
            for i in range(7):
                x = 150 + off + i * 150
                if x > WALL_R - 100:
                    continue
                if r == 3 and i == 3:
                    self.peg("cashback", x + 0 * off, y, 34, +47, GREEN, kind="bonus",
                             elast=1.1, max_hits=99, cooldown=0.5)
                    continue
                self.peg("tax", x, y, 15, -1_300, ORANGE, cooldown=0.35)
            # wall deflectors so the ball can never park between peg and wall
            self.seg((WALL_L, y - 70), (WALL_L + 60, y - 10), 7)
            self.seg((WALL_R, y - 70), (WALL_R - 60, y - 10), 7)
        self.seg((WALL_L, 3250), (200, 3330), 8)
        self.seg((WALL_R, 3250), (880, 3330), 8)

        # --- 3. enemy chamber (orbiting expense balls)
        self.enemy("food", 300, 3650, 84, -3_900, ORANGE, 110, 1.6, rng.uniform(0, 6.28))
        self.enemy("dentist", 740, 3900, 105, -18_000, TOOTH, 120, -1.3, rng.uniform(0, 6.28), mass=5)
        self.enemy("subs", 380, 4200, 66, -1_990, PURPLE, 140, 2.1, rng.uniform(0, 6.28))
        self.enemy("bday", 720, 4450, 72, -5_000, PINK, 120, -1.8, rng.uniform(0, 6.28))
        self.seg((WALL_L, 4600), (220, 4700), 8)
        self.seg((WALL_R, 4600), (860, 4700), 8)

        # --- 4. pistons + bonus
        self.slider("credit", "piston", 4950, 420, 60, WALL_L + 210 - 200, WALL_L + 210 + 230,
                    2.6, rng.uniform(0, 6.28), -12_000, RED)
        self.peg("bonus", 540, 5250, 46, +15_000, GREEN, kind="bonus", elast=1.15,
                 max_hits=1, cooldown=1.0)
        self.slider("fine", "piston", 5550, 420, 60, WALL_R - 210 + 200, WALL_R - 210 - 230,
                    2.2, rng.uniform(0, 6.28), -5_000, RED)
        self.seg((WALL_L, 5800), (200, 5880), 8)
        self.seg((WALL_R, 5800), (880, 5880), 8)

        # --- 5. finale: price-gate and three pockets
        self.peg("tax", 300, 6150, 18, -1_300, ORANGE, cooldown=0.35)
        self.peg("tax", 780, 6150, 18, -1_300, ORANGE, cooldown=0.35)
        self.slider("prices", "gate", 6500, 300, 46, 230, 850, 3.0, rng.uniform(0, 6.28),
                    -4_000, RED)
        # pocket dividers
        self.pockets = [("loan", WALL_L, 390, RED), ("vacation", 390, 690, GOLD),
                        ("broke", 690, WALL_R, GREY)]
        for x in (390, 690):
            self.seg((x, POCKET_TOP), (x, LEVEL_END), 12)

    def _ball(self):
        rng = self.rng
        b = pymunk.Body(1, pymunk.moment_for_circle(1, 0, R_MAX))
        b.position = (540 + rng.uniform(-160, 160), 330)
        b.velocity = (rng.uniform(-250, 250), 0)

        def vfunc(body, g, damping, dt):
            pymunk.Body.update_velocity(body, g, 0.999, dt)
            v = body.velocity
            sp = v.length
            if sp > VMAX:
                body.velocity = v * (VMAX / sp)
        b.velocity_func = vfunc
        s = pymunk.Circle(b, R_MAX)
        s.elasticity, s.friction, s.collision_type = 0.72, 0.4, BALL
        self.space.add(b, s)
        self.ball, self.ball_shape = b, s

    # ------------------------------------------------------------- callbacks
    def _on_obst(self, arb, space, data):
        ball_s, other = arb.shapes
        ob = self.by_shape.get(other)
        if ob is None:
            return
        if self.t - ob.last_hit < ob.cooldown or ob.hits >= ob.max_hits:
            self.events.append((self.t, "bounce", {"x": self.ball.position.x,
                                                   "y": self.ball.position.y, "e": 0.5}))
            return
        ob.last_hit = self.t
        ob.hits += 1
        self.money += ob.cost
        p = arb.contact_point_set.points[0].point_a if arb.contact_point_set.points else self.ball.position
        self.events.append((self.t, "hit", {"key": ob.key, "cost": ob.cost, "x": p.x, "y": p.y,
                                            "color": ob.color, "money": self.money,
                                            "idx": self.obstacles.index(ob)}))

    def _on_wall(self, arb, space, data):
        if not arb.is_first_contact:
            return
        imp = arb.total_impulse.length
        if imp > 250:
            p = self.ball.position
            self.events.append((self.t, "bounce", {"x": p.x, "y": p.y, "e": min(imp / 1500, 1)}))

    # ------------------------------------------------------------------ step
    def radius(self):
        f = max(0.0, min(1.0, self.money / START_MONEY))
        return R_MIN + (R_MAX - R_MIN) * f

    def step_frame(self, nsub=SUB):
        for _ in range(nsub):
            for m in self.movers:
                m(self.t)
            self.space.step(DT)
            self.t += DT
        # anti-stuck: no downward progress for 1.4 s -> kick towards the centre
        y = self.ball.position.y
        if y > self.best_y + 25:
            self.best_y, self.best_t = y, self.t
        elif self.t - self.best_t > 1.4 and y < POCKET_TOP:
            dx = 1 if self.ball.position.x < 540 else -1
            self.ball.velocity = (dx * self.rng.uniform(380, 520), -self.rng.uniform(250, 420))
            self.best_t = self.t
        r = self.radius()
        if abs(self.ball_shape.radius - r) > 0.3:
            self.ball_shape.unsafe_set_radius(self.ball_shape.radius + (r - self.ball_shape.radius) * 0.25)

    def snapshot(self):
        obs = []
        for ob in self.obstacles:
            b = ob.body
            obs.append((b.position.x, b.position.y, b.angle))
        b = self.ball
        return {"t": self.t, "bx": b.position.x, "by": b.position.y, "ba": b.angle,
                "br": self.ball_shape.radius, "money": self.money, "obs": obs}


def run(seed, max_frames=FPS * 75, record=False, tail=1.0):
    """Simulate. Slow motion near the pockets. Returns a result dict."""
    lv = Level(seed)
    frames = []
    result = None
    stuck_y, stuck_since = 0, 0
    settle = None
    for f in range(max_frames):
        by = lv.ball.position.y
        slow = POCKET_TOP - 750 < by < POCKET_TOP + 120 and settle is None
        nsub = 2 if slow else SUB
        ev0 = len(lv.events)
        lv.step_frame(nsub)
        if record:
            snap = lv.snapshot()
            snap["events"] = lv.events[ev0:]
            snap["slow"] = slow
            frames.append(snap)
        by = lv.ball.position.y
        if by > stuck_y + 40:
            stuck_y, stuck_since = by, f
        elif f - stuck_since > FPS * 6 and settle is None:
            result = "stuck"
            break
        if lv.money <= 0 and result is None:
            result = "bankrupt"
            settle = settle or f
        if by > POCKET_TOP + 140 and settle is None:
            x = lv.ball.position.x
            for name, x0, x1, _ in lv.pockets:
                if x0 <= x < x1:
                    result = name
            settle = f
            lv.events.append((lv.t, "pocket", {"name": result, "x": x, "y": by}))
            if record:
                frames[-1]["events"].append(lv.events[-1])
        if settle is not None and f - settle > FPS * tail:
            break
    hits = [e for e in lv.events if e[1] == "hit"]
    return {"seed": seed, "result": result or "timeout", "money": lv.money, "frames": frames,
            "n_frames": f + 1, "hits": hits, "level": lv}


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    good = []
    for s in range(n):
        r = run(s)
        keys = {h[2]["key"] for h in r["hits"]}
        min_money = min([h[2]["money"] for h in r["hits"]] + [START_MONEY])
        print(s, r["result"], r["money"], round(r["n_frames"] / FPS, 1), len(r["hits"]),
              "min", min_money, sorted(keys))
        if r["result"] == "vacation":
            good.append((s, r["money"]))
    print("vacation:", good)
