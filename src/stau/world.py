"""Builds the 3D highway world in Blender (bpy) – road, walls, trees, sky, car pool."""
import math, random
import bpy, bmesh
from mathutils import Vector

# ---------------------------------------------------------------- layout
LANE_W = 3.75
LANES = [1.9, 1.9 + LANE_W, 1.9 + 2 * LANE_W]          # our carriageway, left→right
OPP_LANES = [-4.9, -4.9 - LANE_W, -4.9 - 2 * LANE_W]    # opposite carriageway
ROAD_Y0, ROAD_Y1 = -600.0, 3200.0
ROAD_LEN = ROAD_Y1 - ROAD_Y0
ROAD_MID = (ROAD_Y0 + ROAD_Y1) / 2

rng = random.Random(7)


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


# ---------------------------------------------------------------- materials
def mat(name, color=(0.5, 0.5, 0.5), rough=0.5, metal=0.0, emit=None, emit_strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = emit_strength
    return m


def noise_color_mat(name, c1, c2, scale, rough=0.9, detail=6, bump=0.0, scale_vec=(1, 1, 1)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = scale_vec
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = detail
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[1].position = 0.7
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Roughness"].default_value = rough
    if bump:
        bn = nt.nodes.new("ShaderNodeBump")
        bn.inputs["Strength"].default_value = bump
        nt.links.new(nz.outputs["Fac"], bn.inputs["Height"])
        nt.links.new(bn.outputs["Normal"], p.inputs["Normal"])
    return m


def car_paint_mat():
    """Body colour comes from object colour (rgb)."""
    m = bpy.data.materials.new("carpaint")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    nt.links.new(oi.outputs["Color"], p.inputs["Base Color"])
    p.inputs["Metallic"].default_value = 0.45
    p.inputs["Roughness"].default_value = 0.32
    p.inputs["Coat Weight"].default_value = 1.0
    p.inputs["Coat Roughness"].default_value = 0.04
    return m


def brake_mat():
    """Tail lights: brightness from object colour alpha (0 = off, 1 = braking)."""
    m = bpy.data.materials.new("taillight")
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.35, 0.0, 0.0, 1)
    p.inputs["Roughness"].default_value = 0.2
    p.inputs["Emission Color"].default_value = (1.0, 0.03, 0.01, 1)
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY_ADD"
    mul.inputs[1].default_value = 28.0
    mul.inputs[2].default_value = 0.6
    nt.links.new(oi.outputs["Alpha"], mul.inputs[0])
    nt.links.new(mul.outputs[0], p.inputs["Emission Strength"])
    return m


# ---------------------------------------------------------------- mesh helpers
def box(name, size, loc, material, bevel=0.0, taper_top=None, segs=2):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
        if taper_top and v.co.z > 0:
            v.co.x *= taper_top[0]
            v.co.y = v.co.y * taper_top[1] + taper_top[2]
        v.co += Vector(loc)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(material)
    if bevel:
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segs, affect="EDGES", profile=0.5)
        bm.to_mesh(me); bm.free()
    for poly in me.polygons:
        poly.use_smooth = bevel > 0
    return me


def cyl(name, r, depth, loc, material, axis="X", verts=20):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r, depth=depth)
    rot = {"X": (0, math.pi / 2, 0), "Y": (math.pi / 2, 0, 0), "Z": (0, 0, 0)}[axis]
    from mathutils import Euler
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=Euler(rot).to_matrix())
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(loc))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = True
    return me


def join_meshes(name, meshes):
    """Merge several meshes (each with its own material) into one mesh."""
    objs = []
    for me in meshes:
        o = bpy.data.objects.new(me.name, me)
        bpy.context.scene.collection.objects.link(o)
        objs.append(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    out = objs[0]
    me = out.data
    me.name = name
    bpy.data.objects.remove(out)
    return me


def obj(name, me, loc=(0, 0, 0), coll=None):
    o = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(o)
    o.location = loc
    return o


def strip(name, x0, x1, y0, y1, z, material):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [], [(0, 1, 2, 3)])
    me.materials.append(material)
    return obj(name, me)


def array(o, count, offset):
    m = o.modifiers.new("arr", "ARRAY")
    m.count = count
    m.use_relative_offset = False
    m.use_constant_offset = True
    m.constant_offset_displace = offset
    return m


# ---------------------------------------------------------------- world
M = {}


def build_materials():
    M["asphalt"] = noise_color_mat("asphalt", (0.055, 0.055, 0.06), (0.11, 0.11, 0.115), 60, rough=0.88, bump=0.15)
    M["asphalt_old"] = noise_color_mat("asphalt2", (0.07, 0.07, 0.075), (0.14, 0.14, 0.14), 9, rough=0.9,
                                       scale_vec=(1, 0.08, 1))
    M["grass"] = noise_color_mat("grass", (0.04, 0.12, 0.02), (0.22, 0.3, 0.07), 0.012, rough=0.95, detail=3)
    M["verge"] = noise_color_mat("verge", (0.06, 0.16, 0.03), (0.2, 0.33, 0.06), 1.5, rough=0.95, detail=8, bump=0.4)
    M["white"] = mat("marking", (0.85, 0.85, 0.85), rough=0.6)
    M["yellow"] = mat("marking_y", (0.95, 0.7, 0.02), rough=0.6)
    M["steel"] = mat("steel", (0.62, 0.64, 0.66), rough=0.35, metal=0.9)
    M["darksteel"] = mat("darksteel", (0.18, 0.19, 0.2), rough=0.5, metal=0.6)
    M["teal"] = mat("wall_teal", (0.33, 0.62, 0.56), rough=0.6)
    M["wallwhite"] = mat("wall_white", (0.78, 0.8, 0.8), rough=0.6)
    M["trunk"] = mat("trunk", (0.12, 0.08, 0.05), rough=0.9)
    M["leaf1"] = noise_color_mat("leaf1", (0.04, 0.12, 0.02), (0.14, 0.3, 0.05), 6, rough=0.8, bump=0.6)
    M["leaf2"] = noise_color_mat("leaf2", (0.03, 0.09, 0.025), (0.09, 0.2, 0.04), 6, rough=0.8, bump=0.6)
    M["paint"] = car_paint_mat()
    M["glass"] = mat("glass", (0.01, 0.012, 0.016), rough=0.04, metal=0.3)
    gh = mat("glass_hero", (0.12, 0.16, 0.2), rough=0.02)
    gh.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.3
    M["glass_hero"] = gh
    M["redstripe"] = mat("redstripe", (0.75, 0.03, 0.02), rough=0.4)
    M["orangestripe"] = mat("orangestripe", (1.0, 0.35, 0.0), rough=0.4)
    bl = mat("bluelight", (0.05, 0.15, 1.0), rough=0.2, emit=(0.1, 0.3, 1.0), emit_strength=1.0)
    nt = bl.node_tree
    oi = nt.nodes.new("ShaderNodeObjectInfo")
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY_ADD"
    mul.inputs[1].default_value = 40.0; mul.inputs[2].default_value = 0.5
    nt.links.new(oi.outputs["Alpha"], mul.inputs[0])
    nt.links.new(mul.outputs[0], nt.nodes["Principled BSDF"].inputs["Emission Strength"])
    M["bluelight"] = bl
    M["tire"] = mat("tire", (0.02, 0.02, 0.02), rough=0.8)
    M["rim"] = mat("rim", (0.5, 0.5, 0.52), rough=0.3, metal=1.0)
    M["tail"] = brake_mat()
    M["head"] = mat("headlight", (0.9, 0.9, 0.85), rough=0.05, emit=(1, 1, 0.9), emit_strength=0.4)
    M["plate"] = mat("plate", (0.85, 0.85, 0.82), rough=0.4)
    M["black"] = mat("plastic", (0.025, 0.025, 0.028), rough=0.6)
    M["truckbox"] = mat("truckbox", (0.75, 0.76, 0.78), rough=0.45, metal=0.2)
    M["reflector"] = mat("reflector", (1.0, 0.6, 0.1), rough=0.2, emit=(1, 0.55, 0.1), emit_strength=2.0)
    M["sign"] = mat("signblue", (0.02, 0.12, 0.45), rough=0.4)
    M["redwhite"] = None  # built in baken()


def build_sky(sun_elev=48, sun_rot=200):
    w = bpy.data.worlds.new("sky")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    sky = nt.nodes.new("ShaderNodeTexSky")
    for t in ("MULTIPLE_SCATTERING", "NISHITA", "SINGLE_SCATTERING"):
        try:
            sky.sky_type = t
            break
        except TypeError:
            continue
    sky.sun_elevation = math.radians(sun_elev)
    sky.sun_rotation = math.radians(sun_rot)
    try:
        sky.air_density = 1.0
        sky.aerosol_density = 1.0
    except AttributeError:
        pass
    # --- cloud layer: project view direction onto a plane in the sky
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    zc = nt.nodes.new("ShaderNodeMath"); zc.operation = "MAXIMUM"; zc.inputs[1].default_value = 0.02
    nt.links.new(sep.outputs["Z"], zc.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    dx = nt.nodes.new("ShaderNodeMath"); dx.operation = "DIVIDE"
    dy = nt.nodes.new("ShaderNodeMath"); dy.operation = "DIVIDE"
    nt.links.new(sep.outputs["X"], dx.inputs[0]); nt.links.new(zc.outputs[0], dx.inputs[1])
    nt.links.new(sep.outputs["Y"], dy.inputs[0]); nt.links.new(zc.outputs[0], dy.inputs[1])
    nt.links.new(dx.outputs[0], comb.inputs["X"]); nt.links.new(dy.outputs[0], comb.inputs["Y"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.42
    nz.inputs["Detail"].default_value = 6
    nz.inputs["Roughness"].default_value = 0.55
    nt.links.new(comb.outputs[0], nz.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.49
    ramp.color_ramp.elements[1].position = 0.58
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    # fade clouds near horizon so they look far away
    hz = nt.nodes.new("ShaderNodeMapRange")
    hz.inputs["From Min"].default_value = 0.02
    hz.inputs["From Max"].default_value = 0.25
    nt.links.new(sep.outputs["Z"], hz.inputs["Value"])
    cov = nt.nodes.new("ShaderNodeMath"); cov.operation = "MULTIPLY"
    nt.links.new(ramp.outputs["Color"], cov.inputs[0]); nt.links.new(hz.outputs["Result"], cov.inputs[1])
    # cloud colour: bright white with slightly grey shaded parts
    shade = nt.nodes.new("ShaderNodeValToRGB")
    import os
    K = float(os.environ.get("CLOUD_K", "22"))
    shade.color_ramp.elements[0].color = (0.55 * K, 0.6 * K, 0.7 * K, 1)
    shade.color_ramp.elements[1].color = (K, K, K, 1)
    shade.color_ramp.elements[0].position = 0.5
    shade.color_ramp.elements[1].position = 0.66
    nt.links.new(nz.outputs["Fac"], shade.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    nt.links.new(cov.outputs[0], mix.inputs["Factor"])
    hs = nt.nodes.new("ShaderNodeHueSaturation")
    hs.inputs["Saturation"].default_value = 1.6
    hs.inputs["Value"].default_value = 0.9
    nt.links.new(sky.outputs["Color"], hs.inputs["Color"])
    nt.links.new(hs.outputs["Color"], mix.inputs["A"])
    nt.links.new(shade.outputs["Color"], mix.inputs["B"])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.35
    nt.links.new(mix.outputs["Result"], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    # explicit sun lamp (sharp shadows like in a game engine)
    sd = bpy.data.lights.new("sun", "SUN")
    sd.energy = 4.2
    sd.angle = math.radians(1.2)
    sd.color = (1.0, 0.96, 0.9)
    so = bpy.data.objects.new("sun", sd)
    bpy.context.scene.collection.objects.link(so)
    # sky texture: sun_rotation measured from +X counterclockwise looking down
    el, rot = math.radians(sun_elev), math.radians(sun_rot)
    d = Vector((math.cos(el) * math.sin(rot), math.cos(el) * math.cos(rot), math.sin(el)))
    so.rotation_euler = d.to_track_quat("Z", "Y").to_euler()


def build_road(merge_end=None):
    y0, y1 = ROAD_Y0, ROAD_Y1
    g = strip("ground", -3000, 3000, -3000, 6000, -0.02, M["grass"])
    strip("verge_r", 11.0, 30, y0, y1, -0.01, M["verge"])
    strip("verge_l", -36, -15.5, y0, y1, -0.01, M["verge"])
    strip("median", -1.2, 0.0, y0, y1, -0.005, M["verge"])
    strip("road", -0.2, 13.0, y0, y1, 0.0, M["asphalt"])
    strip("road_opp", -15.8, -1.0, y0, y1, 0.0, M["asphalt"])
    # markings
    def solid(name, x, w, mm="white"):
        strip(name, x - w / 2, x + w / 2, y0, y1, 0.006, M[mm])

    solid("edge_l", 0.15, 0.3); solid("edge_r", 11.55, 0.3)
    solid("oedge_l", -1.35, 0.3); solid("oedge_r", -14.75, 0.3)
    for k, x in enumerate([LANES[0] + LANE_W / 2, LANES[1] + LANE_W / 2,
                           OPP_LANES[0] - LANE_W / 2, OPP_LANES[1] - LANE_W / 2]):
        d = strip(f"dash{k}", x - 0.08, x + 0.08, y0, y0 + 6, 0.006, M["white"])
        array(d, int(ROAD_LEN / 18), (0, 18, 0))
    # guard rails: right, median (both sides)
    for name, x in (("rail_r", 12.6), ("rail_m1", -0.45), ("rail_m2", -0.75), ("rail_l", -16.3)):
        o = obj(name, box(name, (0.06, ROAD_LEN, 0.32), (0, ROAD_MID, 0.68), M["steel"]))
        o.location.x = x
        p = obj(name + "_p", box(name + "p", (0.12, 0.1, 0.75), (x + (0.1 if x > 0 else -0.1), y0, 0.37), M["darksteel"]))
        array(p, int(ROAD_LEN / 4), (0, 4, 0))
    # noise barrier: alternating teal/white panels + steel posts
    wall_x, wall_h, pw = 16.0, 4.6, 5.0
    for k, mname in enumerate(("teal", "wallwhite")):
        o = obj(f"wall{k}", box(f"wall{k}", (0.15, pw - 0.15, wall_h), (wall_x, y0 + pw / 2 + k * pw, wall_h / 2), M[mname]))
        array(o, int(ROAD_LEN / (2 * pw)), (0, 2 * pw, 0))
    po = obj("wallpost", box("wallpost", (0.3, 0.22, wall_h + 0.2), (wall_x - 0.1, y0, (wall_h + 0.2) / 2), M["darksteel"]))
    array(po, int(ROAD_LEN / pw), (0, pw, 0))
    # overhead gantry sign every ~700 m (like the blue lane signs in the reference)
    for gy in (260, 980, 1700, 2400):
        obj("gpost_l", box("gp", (0.35, 0.35, 7.0), (-1.0, gy, 3.5), M["darksteel"]))
        obj("gpost_r", box("gp", (0.35, 0.35, 7.0), (13.4, gy, 3.5), M["darksteel"]))
        obj("gbeam", box("gb", (14.8, 0.4, 0.5), (6.2, gy, 7.0), M["darksteel"]))
        for sx in (LANES[0], LANES[2]):
            obj("gsign", box("gs", (2.6, 0.12, 2.4), (sx, gy - 0.3, 5.6), M["sign"]))
    # Leitpfosten (delineator posts) every 50 m – white with black band, as on German motorways
    lp = join_meshes("leitpfosten", [
        box("lpw", (0.12, 0.12, 1.0), (0, 0, 0.5), M["white"], bevel=0.02),
        box("lpb", (0.13, 0.13, 0.25), (0, 0, 0.82), M["black"]),
        box("lpr", (0.06, 0.02, 0.12), (0, -0.07, 0.82), M["reflector"]),
    ])
    y = 0.0
    while y > ROAD_Y0:
        y -= 50
    while y < ROAD_Y1:
        obj("leitpfosten", lp, (12.15, y, 0))
        y += 50
    build_trees()


def tree_meshes():
    out = []
    # poplar / deciduous: displaced ico sphere stack
    for k in range(3):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
        r = random.Random(k)
        for v in bm.verts:
            n = v.co.normalized()
            v.co *= 1.0 + 0.18 * math.sin(7 * n.x + k) * math.cos(6 * n.y) + 0.12 * math.sin(11 * n.z + 2 * k)
            v.co.x *= 1.6; v.co.y *= 1.6; v.co.z *= 3.4
            v.co.z += 6.5
        crown = bpy.data.meshes.new("crown"); bm.to_mesh(crown); bm.free()
        crown.materials.append(M["leaf1"] if k != 1 else M["leaf2"])
        for p in crown.polygons:
            p.use_smooth = True
        trunk = cyl("trunk", 0.18, 5.0, (0, 0, 2.5), M["trunk"], axis="Z", verts=8)
        out.append(join_meshes(f"tree{k}", [crown, trunk]))
    # conifer
    parts = [cyl("trunk", 0.16, 4, (0, 0, 2), M["trunk"], axis="Z", verts=8)]
    for i in range(5):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=14, radius1=2.4 - 0.4 * i, radius2=0.1, depth=3.2)
        bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((0, 0, 3.4 + 1.9 * i)))
        me = bpy.data.meshes.new("cone"); bm.to_mesh(me); bm.free()
        me.materials.append(M["leaf2"])
        parts.append(me)
    out.append(join_meshes("conifer", parts))
    return out


def build_trees():
    coll = bpy.data.collections.new("trees")
    bpy.context.scene.collection.children.link(coll)
    meshes = tree_meshes()
    r = rng
    rows_r = [(19.5, 7.0), (25, 8.0), (31, 9.0), (38, 10.0), (47, 12.0)]
    rows_l = [(-19.5, 7.0), (-25, 8.0), (-32, 9.0), (-40, 11.0)]
    for rows in (rows_r, rows_l):
        for x, step in rows:
            y = ROAD_Y0
            while y < ROAD_Y1 + 300:
                me = r.choice(meshes)
                o = bpy.data.objects.new("tree", me)
                coll.objects.link(o)
                o.location = (x + r.uniform(-2, 2), y + r.uniform(-2, 2), 0)
                s = r.uniform(0.8, 1.35)
                o.scale = (s, s, s * r.uniform(0.9, 1.25))
                o.rotation_euler.z = r.uniform(0, 6.28)
                y += step * r.uniform(0.6, 1.4)
    # distant tree lines (cheap: long dark-green boxes) for the horizon
    # scattered woods further out
    for _ in range(260):
        side = r.choice((-1, 1))
        cx, cy = side * r.uniform(60, 400), r.uniform(ROAD_Y0, ROAD_Y1 + 800)
        for _ in range(r.randint(6, 16)):
            o = bpy.data.objects.new("tree", r.choice(meshes))
            coll.objects.link(o)
            o.location = (cx + r.uniform(-18, 18), cy + r.uniform(-25, 25), 0)
            s = r.uniform(1.0, 1.6); o.scale = (s, s, s)


# ---------------------------------------------------------------- vehicles
def strut(name, p0, p1, w, d, material):
    """Thin box from p0 to p1 (pillar)."""
    p0, p1 = Vector(p0), Vector(p1)
    axis = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    q = axis.to_track_quat("Z", "Y")
    for v in bm.verts:
        v.co.x *= w; v.co.y *= d; v.co.z *= axis.length
        v.co = q @ v.co + (p0 + p1) / 2
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(material)
    return me


def cabin_parts(W, zb1, ch, yc, cl, taper, kind, glass, hero=False):
    """Glass cabin + body-coloured pillars + solid roof."""
    tx, ty, tsh = taper
    parts = [box("cab", (W - 0.18, cl, ch), (0, yc, zb1 + ch / 2), glass, bevel=0.07,
                 taper_top=taper, segs=2)]
    hw = (W - 0.18) / 2 + 0.012
    zt = zb1 + ch
    fr = [0.0, 0.52, 1.0] if kind == "sedan" else [0.0, 0.36, 0.68, 1.0]
    for f in fr:
        yb = yc - cl / 2 + f * cl
        yt = yc + (-cl / 2 + f * cl) * ty + tsh
        wid = 0.16 if f in (0.0, 1.0) else 0.11
        for sx in (-1, 1):
            parts.append(strut("pillar", (sx * hw, yb, zb1 - 0.02), (sx * (hw * tx + 0.004), yt, zt + 0.01),
                               0.05, wid, M["paint"]))
    # solid roof sitting on the pillars
    rl = cl * ty + 0.06
    parts.append(box("roof", (2 * hw * tx + 0.04, rl, 0.09), (0, yc + tsh, zt + 0.03), M["paint"], bevel=0.04))
    # window frame strip (beltline) in black
    parts.append(box("belt", (W - 0.12, cl + 0.02, 0.05), (0, yc, zb1 + 0.01), M["black"]))
    if kind != "sedan":
        parts.append(box("rails", (2 * hw * tx - 0.2, rl - 0.3, 0.05), (0, yc + tsh, zt + 0.1), M["black"]))
    if hero:
        # interior so the cabin reads as a car, not a glass box
        dash_y = yc + cl / 2 - 0.35
        parts.append(box("dash", (W - 0.3, 0.45, 0.25), (0, dash_y, zb1 + 0.05), M["black"], bevel=0.05))
        for sx in (-0.42, 0.42):
            parts.append(box("seatback", (0.5, 0.14, 0.6), (sx, yc + 0.55, zb1 + 0.1), M["black"], bevel=0.05))
            parts.append(box("seatback2", (0.5, 0.14, 0.55), (sx, yc - 0.55, zb1 + 0.05), M["black"], bevel=0.05))
        parts.append(strut("steer", (-0.42, dash_y - 0.32, zb1 + 0.05), (-0.42, dash_y - 0.22, zb1 + 0.28),
                           0.36, 0.04, M["black"]))
    return parts


def car_mesh(kind, hero=False):
    parts = []
    glass = M["glass_hero"] if hero else M["glass"]
    if kind in ("sedan", "wagon", "suv"):
        L, W = 4.6, 1.84
        zb0, zb1 = (0.32, 1.0) if kind != "suv" else (0.38, 1.18)
        parts.append(box("body", (W, L, zb1 - zb0), (0, 0, (zb0 + zb1) / 2), M["paint"], bevel=0.13, segs=3))
        ch = 0.52 if kind != "suv" else 0.58
        if kind == "sedan":
            parts += cabin_parts(W, zb1, ch, -0.2, 2.5, (0.9, 0.7, -0.05), kind, glass, hero)
        else:
            parts += cabin_parts(W, zb1, ch, -0.5, 3.2, (0.92, 0.86, -0.15), kind, glass, hero)
        wy = 1.42
        tail_z = zb1 - 0.16
        rear = -L / 2
        front = L / 2
        # bumpers + grille + mirrors
        parts.append(box("bump_r", (W - 0.05, 0.12, 0.2), (0, rear - 0.02, zb0 + 0.12), M["black"], bevel=0.04))
        parts.append(box("bump_f", (W - 0.05, 0.12, 0.2), (0, front + 0.02, zb0 + 0.12), M["black"], bevel=0.04))
        parts.append(box("grille", (0.8, 0.05, 0.16), (0, front + 0.03, zb1 - 0.3), M["black"], bevel=0.02))
        for sx in (-1, 1):
            parts.append(box("mirror", (0.22, 0.1, 0.12), (sx * (W / 2 + 0.08), 0.75, zb1 + 0.08), M["paint"], bevel=0.03))
        wheel_r = 0.34 if kind != "suv" else 0.38
    elif kind == "ambulance":
        L, W = 6.0, 2.1
        parts.append(box("box", (W, 4.0, 2.2), (0, -0.9, 1.6), M["paint"], bevel=0.08))
        parts.append(box("cab", (W, 1.9, 1.5), (0, 2.0, 1.25), M["paint"], bevel=0.15))
        parts.append(box("wind", (W - 0.2, 0.5, 0.65), (0, 2.75, 1.75), M["glass"], bevel=0.05, taper_top=(0.95, 0.6, -0.15)))
        parts.append(box("stripe", (W + 0.02, 6.0, 0.25), (0, -0.05, 1.05), M["redstripe"]))
        parts.append(box("stripe2", (W + 0.02, 4.0, 0.12), (0, -0.9, 2.3), M["orangestripe"]))
        for sx in (-0.7, 0.7):
            parts.append(box("blue", (0.45, 0.3, 0.16), (sx, 1.3, 2.78), M["bluelight"], bevel=0.04))
            parts.append(box("blue_r", (0.3, 0.2, 0.16), (sx, -2.85, 2.78), M["bluelight"], bevel=0.04))
        wy = 1.9
        tail_z = 1.2
        rear, front = -2.9, 2.95
        wheel_r = 0.38
    else:  # truck
        L, W = 16.0, 2.5
        parts.append(box("trailer", (W, 12.6, 3.0), (0, -1.6, 2.6), M["truckbox"], bevel=0.05))
        parts.append(box("chassis", (W - 0.4, 15.5, 0.35), (0, -0.5, 0.85), M["black"]))
        parts.append(box("cabin", (W, 2.2, 2.6), (0, 6.6, 2.25), M["paint"], bevel=0.12))
        parts.append(box("wind", (W - 0.2, 0.08, 0.95), (0, 7.72, 2.85), M["glass"]))
        wy = None
        tail_z = 1.05
        rear, front = -7.9, 7.75
        wheel_r = 0.5
    # lights
    lx = W / 2 - 0.3
    for sx in (-lx, lx):
        parts.append(box("tail", (0.42, 0.06, 0.14), (sx, rear - 0.06, tail_z), M["tail"], bevel=0.02))
        parts.append(box("headl", (0.36, 0.06, 0.11), (sx, front + 0.04, (tail_z - 0.05) if wy else 1.2), M["head"], bevel=0.02))
    parts.append(box("plate", (0.52, 0.04, 0.12), (0, rear - 0.1, (tail_z - 0.3) if wy else 0.75), M["plate"]))
    # wheels
    if wy:
        ws = [(sx, sy) for sx in (-W / 2 + 0.12, W / 2 - 0.12) for sy in (-wy, wy)]
    else:
        ws = [(sx, sy) for sx in (-W / 2 + 0.15, W / 2 - 0.15) for sy in (6.4, -4.5, -5.8, -7.0)]
    for sx, sy in ws:
        parts.append(cyl("tire", wheel_r, 0.26, (sx, sy, wheel_r), M["tire"]))
        parts.append(cyl("rim", wheel_r * 0.6, 0.27, (sx, sy, wheel_r), M["rim"], verts=12))
    return join_meshes(kind + ("_hero" if hero else ""), parts)


CAR_COLORS = [(0.8, 0.8, 0.8), (0.82, 0.82, 0.84), (0.45, 0.46, 0.48), (0.02, 0.02, 0.025),
              (0.08, 0.09, 0.1), (0.1, 0.22, 0.27), (0.55, 0.03, 0.02), (0.03, 0.08, 0.3),
              (0.6, 0.6, 0.62), (0.9, 0.9, 0.9), (0.45, 0.3, 0.05), (0.15, 0.3, 0.6)]
LENGTH = {"sedan": 4.6, "wagon": 4.6, "suv": 4.6, "truck": 16.0}


class Pool:
    """Fixed set of vehicle objects; shots place them every frame."""

    def __init__(self, n_cars=400, n_trucks=40):
        self.meshes = {k: car_mesh(k) for k in ("sedan", "wagon", "suv", "truck", "ambulance")}
        self.ambulance = obj("ambulance", self.meshes["ambulance"], (0, 0, -50), None)
        self.ambulance.color = (0.92, 0.92, 0.9, 0.0)
        self.coll = bpy.data.collections.new("vehicles")
        bpy.context.scene.collection.children.link(self.coll)
        self.cars, self.trucks = [], []
        r = random.Random(3)
        for i in range(n_cars):
            k = r.choice(["sedan", "sedan", "wagon", "suv"])
            o = obj(f"car{i}", self.meshes[k], (0, 0, -50), self.coll)
            o.color = (*r.choice(CAR_COLORS), 0.0)
            o["kind"] = k
            self.cars.append(o)
        for i in range(n_trucks):
            o = obj(f"truck{i}", self.meshes["truck"], (0, 0, -50), self.coll)
            o.color = (*r.choice([(0.8, 0.8, 0.8), (0.1, 0.15, 0.35), (0.55, 0.05, 0.03), (0.9, 0.9, 0.9)]), 0.0)
            o["kind"] = "truck"
            self.trucks.append(o)

    def hide_all(self):
        for o in self.cars + self.trucks:
            o.location = (0, 0, -50)


def place(o, x, y, yaw=0.0, brake=0.0):
    o.location = (x, y, 0.0)
    o.rotation_euler = (0, 0, yaw)
    c = o.color
    o.color = (c[0], c[1], c[2], float(brake))


# ---------------------------------------------------------------- render setup
def setup_render(w=720, h=1280, samples=6):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.1
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    sc.cycles.max_bounces = 3
    sc.cycles.diffuse_bounces = 1
    sc.cycles.glossy_bounces = 1
    sc.cycles.transmission_bounces = 2
    sc.cycles.transparent_max_bounces = 4
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.render.use_persistent_data = True
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Punchy"
    except TypeError:
        pass
    sc.view_settings.exposure = -0.9
    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 22
    cam_d.clip_end = 6000
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def aim(cam, loc, target, lens=None, roll=0.0):
    cam.location = loc
    d = Vector(target) - Vector(loc)
    q = d.to_track_quat("-Z", "Y")
    e = q.to_euler()
    if roll:
        from mathutils import Matrix
        m = q.to_matrix() @ Matrix.Rotation(roll, 3, "Z")
        e = m.to_euler()
    cam.rotation_euler = e
    if lens:
        cam.data.lens = lens


def build_all():
    clear()
    build_materials()
    build_sky()
    build_road()
    pool = Pool()
    cam = setup_render()
    return pool, cam
