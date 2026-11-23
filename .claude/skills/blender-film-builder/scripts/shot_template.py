# TEMPLATE SHOT (worked example): ORIGINS, Shot 8J. Aurel at an open window releases a glowing paper strip into the rain.
# Copy this file per shot and replace the SET / CHARACTER / HERO PROP / CAMERA sections. Keep the helpers and render settings.
# Run (official build, pip bpy):  python shot_template.py -- <out_prefix> [width] [samples] [frame_start] [frame_end]
# Run (Ubuntu apt Blender 4.0):  blender -b -P shot_template.py -- <out_prefix> [width] [samples] [frame_start] [frame_end]
import bpy, math, random, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = argv[0] if argv else '/tmp/8J/'
RES_X = int(argv[1]) if len(argv) > 1 else 1280
SAMPLES = int(argv[2]) if len(argv) > 2 else 24
F0 = int(argv[3]) if len(argv) > 3 else 1
F1 = int(argv[4]) if len(argv) > 4 else 192
random.seed(8)
import bpy as _b
# Official builds (Blender 5.x / pip bpy) include OpenImageDenoise; the Ubuntu apt 4.0 build does not.
DENOISE = _b.app.version >= (4, 2, 0)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.frame_start, sc.frame_end, sc.render.fps = 1, 192, 24

def hexrgb(h, a=1.0):
    h = h.lstrip('#'); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (a,)

def mat(name, color, rough=0.8, metal=0.0, emit=None, estr=0.0, sheen=0.0, transm=0.0, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = hexrgb(color)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if sheen: b.inputs['Sheen Weight'].default_value = sheen
    if transm: b.inputs['Transmission Weight'].default_value = transm
    if alpha < 1: b.inputs['Alpha'].default_value = alpha
    if emit:
        b.inputs['Emission Color'].default_value = hexrgb(emit); b.inputs['Emission Strength'].default_value = estr
    return m

def noisy(m, scale=40, strength=0.25):  # break up flat surfaces with a bump
    nt = m.node_tree; n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = scale
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = strength
    nt.links.new(n.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], nt.nodes['Principled BSDF'].inputs['Normal'])
    return m

def box(name, loc, size, m, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot); o = bpy.context.object; o.name = name
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2); o.data.materials.append(m); return o

def link_to(o, parent):
    o.parent = parent; o.matrix_parent_inverse = parent.matrix_world.inverted()

# ---------------- materials (palette from Stage 5) ----------------
M_WALL = noisy(mat('wall', '#2E3A4A', 0.95), 30, 0.3)
M_FLOOR = noisy(mat('floor', '#1a1510', 0.7), 8, 0.2)
M_WOOD = noisy(mat('frame', '#0f0d0b', 0.6), 60, 0.15)
M_GLASS = mat('glass', '#c8d4e0', 0.04, transm=1.0)
M_CURTAIN = noisy(mat('curtain', '#3a4556', 0.9, sheen=0.4), 120, 0.1)
M_COAT = noisy(mat('coat', '#4a515b', 0.95, sheen=0.2), 200, 0.35)
M_SKIN = mat('skin', '#3a302c', 0.6)
M_HAIR = noisy(mat('hair', '#5b5f66', 0.9), 300, 0.4)
M_BLDG = noisy(mat('bldg', '#141A24', 0.9), 4, 0.3)
M_ROOF = mat('roof', '#1d2733', 0.5, 0.1)
M_WIN = mat('litwin', '#000000', 1.0, emit='#d9c79a', estr=3.0)
M_RAIN = mat('rain', '#a9bed4', 0.1, emit='#7f9bb8', estr=0.6, alpha=0.6)
M_OLDSTRIP = mat('oldstrip', '#E8E0CF', 0.8, emit='#E8E0CF', estr=0.15)
M_STRIP = mat('strip', '#E8E0CF', 0.6, emit='#F2A541', estr=14.0)

# ---------------- room: window wall with opening ----------------
WY, OX, Z0, Z1 = 2.0, 0.85, 0.95, 2.45  # wall plane y, half opening width, sill, head
box('wall_L', (-OX - 2.1, WY, 1.6), (4.2, 0.25, 3.4), M_WALL)
box('wall_R', (OX + 2.1, WY, 1.6), (4.2, 0.25, 3.4), M_WALL)
box('wall_B', (0, WY, Z0 / 2), (2 * OX, 0.25, Z0), M_WALL)
box('wall_T', (0, WY, (Z1 + 3.3) / 2), (2 * OX, 0.25, 3.3 - Z1), M_WALL)
box('wall_side_L', (-3.6, -1.0, 1.6), (0.2, 6.0, 3.4), M_WALL)
box('wall_side_R', (3.6, -1.0, 1.6), (0.2, 6.0, 3.4), M_WALL)
box('floor', (0, -1.0, -0.05), (7.4, 6.2, 0.1), M_FLOOR)
box('ceiling', (0, -1.0, 3.3), (7.4, 6.2, 0.1), M_WALL)
box('sill', (0, WY - 0.12, Z0 - 0.03), (2 * OX + 0.3, 0.32, 0.06), M_WOOD)
# frame
for nm, l, s in (('fr_L', (-OX - 0.04, WY, (Z0 + Z1) / 2), (0.08, 0.3, Z1 - Z0 + 0.16)),
                 ('fr_R', (OX + 0.04, WY, (Z0 + Z1) / 2), (0.08, 0.3, Z1 - Z0 + 0.16)),
                 ('fr_T', (0, WY, Z1 + 0.04), (2 * OX + 0.16, 0.3, 0.08))):
    box(nm, l, s, M_WOOD)

# casements, hinged at the outer edges, swung outward (~65°)
def casement(side):
    hx = -OX if side < 0 else OX
    bpy.ops.object.empty_add(location=(hx, WY + 0.14, Z0)); hinge = bpy.context.object
    w, h, t = OX, Z1 - Z0, 0.045; cx = hx - side * w / 2
    parts = [box('c', (cx, WY + 0.14, Z0 + h / 2), (w, t, h), M_GLASS)]
    for (dx, dz, sx, sz) in ((-w / 2 + 0.03, h / 2, 0.06, h), (w / 2 - 0.03, h / 2, 0.06, h), (0, 0.03, w, 0.06), (0, h - 0.03, w, 0.06),
                             (0, h / 3, w, 0.035), (0, 2 * h / 3, w, 0.035)):
        parts.append(box('m', (cx + dx, WY + 0.14, Z0 + dz), (sx, t + 0.02, sz), M_WOOD))
    for p in parts: link_to(p, hinge)
    hinge.rotation_euler = (0, 0, side * math.radians(-65))
    return hinge
casement(-1); casement(1)

# curtains billowing (Wave modifier gives continuous motion)
def curtain(x, sign):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=24, y_subdivisions=40, size=1, location=(x, WY - 0.25, 1.65), rotation=(math.radians(90), 0, 0))
    o = bpy.context.object; o.scale = (0.55, 1.75, 1); o.data.materials.append(M_CURTAIN)
    wv = o.modifiers.new('wave', 'WAVE'); wv.height = 0.09; wv.width = 0.55; wv.speed = 0.035 * sign; wv.narrowness = 1.2; wv.use_x = True; wv.use_y = True
    wv.start_position_x = sign * 0.4
    o.modifiers.new('sub', 'SUBSURF').levels = 1; bpy.ops.object.shade_smooth()
    o.rotation_euler[2] = math.radians(sign * -12)
curtain(-OX - 0.45, 1); curtain(OX + 0.45, -1)

# ---------------- outside: the night city of Lettern ----------------
for i in range(34):
    x = random.uniform(-16, 16); y = random.uniform(9, 46); w = random.uniform(2.2, 4.5); d = random.uniform(3, 6); h = random.uniform(3, 9) + y * 0.12
    if abs(x) < 6 and y < 32: continue
    zbase = -9.0  # flat is on the 5th floor, the street is far below
    b = box('bldg', (x, y, zbase + h / 2), (w, d, h + 9), M_BLDG)
    r = box('roof', (x, y, zbase + h + 4.5), (w * 0.7, d, w * 0.7), M_ROOF, rot=(0, math.radians(45), 0))
    for k in range(random.randint(1, 4)):
        if random.random() < 0.55:
            bpy.ops.mesh.primitive_plane_add(size=1, location=(x + random.uniform(-w / 3, w / 3), y - d / 2 - 0.02, zbase + random.uniform(5, h + 3)), rotation=(math.radians(90), 0, 0))
            p = bpy.context.object; p.scale = (0.35, 0.5, 1); p.data.materials.append(M_WIN)

# old pale strips drifting over the roofs
for i in range(40):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(random.uniform(-10, 10), random.uniform(6, 30), random.uniform(1, 9)),
                                     rotation=(random.uniform(0, 3), random.uniform(0, 3), random.uniform(0, 3)))
    o = bpy.context.object; o.scale = (0.28, 0.012, 1); o.data.materials.append(M_OLDSTRIP)
    o.keyframe_insert('location', frame=1); o.location.z += random.uniform(0.3, 0.8); o.location.x += random.uniform(-0.4, 0.4)
    o.keyframe_insert('location', frame=192)

# ---------------- rain (particles instancing thin streaks) ----------------
bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.0035, depth=0.22, location=(0, 0, -50), rotation=(0, math.radians(90), 0))
drop = bpy.context.object; drop.data.materials.append(M_RAIN); bpy.ops.object.transform_apply(rotation=True)
def rain_emitter(loc, size, count):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc); em = bpy.context.object; em.scale = size
    em.modifiers.new('ps', 'PARTICLE_SYSTEM'); ps = em.particle_systems[0].settings
    ps.count = count; ps.frame_start = -80; ps.frame_end = 192; ps.lifetime = 60; ps.emit_from = 'FACE'
    ps.normal_factor = 0; ps.object_align_factor = (0, 0, -9); ps.factor_random = 0.3
    ps.render_type = 'OBJECT'; ps.instance_object = drop; ps.particle_size = 1; ps.size_random = 0.4
    ps.use_rotations = True; ps.rotation_mode = 'VEL'
    em.show_instancer_for_render = False
    return em
rain_emitter((0, 14, 12), (14, 12, 1), 9000)
rain_emitter((0, 3.0, 4.5), (2.5, 1.6, 1), 900)   # rain right outside / blowing in
bpy.ops.object.effector_add(type='WIND', location=(0, 6, 3), rotation=(math.radians(90), 0, 0))
bpy.context.object.field.strength = 2.5; bpy.context.object.field.noise = 1.5

# ---------------- Aurel, seen from behind ----------------
AX, AY = -0.42, 1.05
bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=0.36, radius2=0.25, depth=1.45, location=(AX, AY, 0.72)); body = bpy.context.object
body.data.materials.append(M_COAT); body.modifiers.new('s', 'SUBSURF').levels = 2; bpy.ops.object.shade_smooth()
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(AX, AY, 1.43)); sh = bpy.context.object; sh.scale = (0.27, 0.15, 0.13)
sh.data.materials.append(M_COAT); bpy.ops.object.shade_smooth()
bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=0.16, location=(AX, AY + 0.02, 1.57)); bpy.context.object.data.materials.append(M_COAT)  # collar
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.115, location=(AX, AY + 0.03, 1.72)); hd = bpy.context.object; hd.scale = (1, 1.05, 1.22)
hd.data.materials.append(M_SKIN); bpy.ops.object.shade_smooth()
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(AX, AY + 0.01, 1.76)); hr = bpy.context.object; hr.scale = (1, 1.05, 1.1)
hr.data.materials.append(M_HAIR); bpy.ops.object.shade_smooth()
# left arm hanging
bpy.ops.mesh.primitive_cylinder_add(radius=0.065, depth=0.7, location=(AX - 0.27, AY, 1.08), rotation=(0, math.radians(6), 0))
bpy.context.object.data.materials.append(M_COAT)
# right arm raised out through the window
def limb(a, b, r, m):
    a, b = Vector(a), Vector(b); d = b - a
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, location=(a + b) / 2)
    o = bpy.context.object; o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = d.to_track_quat('Z', 'Y'); o.data.materials.append(m)
    bpy.ops.object.shade_smooth(); return o
SHOULDER, ELBOW, HAND = (AX + 0.25, AY + 0.02, 1.46), (AX + 0.42, AY + 0.45, 1.62), (AX + 0.52, WY + 0.25, 1.80)
limb(SHOULDER, ELBOW, 0.066, M_COAT); limb(ELBOW, HAND, 0.058, M_COAT)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.05, location=HAND); hand = bpy.context.object; hand.scale = (0.9, 1.4, 0.6)
hand.data.materials.append(M_SKIN); bpy.ops.object.shade_smooth()
# fingers open at the release (frames 40–56)
hand.keyframe_insert('scale', frame=40); hand.scale = (1.4, 1.7, 0.45); hand.keyframe_insert('scale', frame=56)

# ---------------- Nell's strip: warm, rises out into the rain ----------------
bpy.ops.mesh.primitive_grid_add(x_subdivisions=40, y_subdivisions=2, size=1, location=HAND)
st = bpy.context.object; st.name = 'NellStrip'; st.scale = (0.5, 0.024, 1); st.data.materials.append(M_STRIP)
tw = st.modifiers.new('wave', 'WAVE'); tw.height = 0.06; tw.width = 0.35; tw.speed = 0.02; tw.use_y = False; tw.use_normal = False
bpy.ops.object.light_add(type='POINT', location=HAND); glow = bpy.context.object; glow.data.color = hexrgb('#F2A541')[:3]
glow.data.shadow_soft_size = 0.05; glow.visible_camera = False; link_to(glow, st)
path = [(1, HAND, (0.3, 0.2, 0.2)), (44, (HAND[0] + 0.02, HAND[1] + 0.03, HAND[2] + 0.05), (0.4, 0.3, 0.6)),
        (90, (0.75, 4.6, 2.2), (1.2, 0.8, 1.6)), (140, (1.3, 8.5, 2.7), (2.0, 1.1, 2.4)), (192, (1.8, 13.0, 3.3), (2.6, 1.5, 3.2))]
for f, loc, rot in path:
    st.location = loc; st.rotation_euler = rot; st.keyframe_insert('location', frame=f); st.keyframe_insert('rotation_euler', frame=f)
emis = M_STRIP.node_tree.nodes['Principled BSDF'].inputs['Emission Strength']
for f, e, p in ((1, 14, 30), (48, 12, 26), (192, 4, 6)):  # warm near the speaker, cools after release
    emis.default_value = e; emis.keyframe_insert('default_value', frame=f)
    glow.data.energy = p; glow.data.keyframe_insert('energy', frame=f)

# ---------------- light ----------------
bpy.ops.object.light_add(type='AREA', location=(0.6, 6.5, 6.0)); key = bpy.context.object
key.data.size = 6; key.data.energy = 4500; key.data.color = hexrgb('#7f9bb8')[:3]
key.rotation_euler = (Vector((0, 0.5, 1.2)) - key.location).to_track_quat('-Z', 'Y').to_euler()
bpy.ops.object.light_add(type='AREA', location=(-2.8, -1.5, 3.0)); fill = bpy.context.object
fill.data.size = 2; fill.data.energy = 140;
bpy.ops.object.light_add(type='AREA', location=(0, 1.6, 2.0)); bounce = bpy.context.object; bounce.data.size = 1.6; bounce.data.energy = 70
bounce.data.color = hexrgb('#7f9bb8')[:3]; bounce.rotation_euler = (math.radians(-90), 0, 0); bounce.visible_camera = False
fill.data.color = hexrgb('#2E3A4A')[:3]; fill.rotation_euler = (math.radians(60), 0, math.radians(-120))
w = bpy.data.worlds.new('night'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = hexrgb('#1e2a3a'); w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.2
w.mist_settings.start = 4; w.mist_settings.depth = 30

# ---------------- camera: behind him, slow handheld drift (8H onward the camera is free) ----------------
bpy.ops.object.camera_add(location=(-0.95, -1.75, 1.42)); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 30; cam.data.sensor_width = 36
cam.rotation_euler = (Vector((0.25, 3.0, 2.05)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 2.9; cam.data.dof.aperture_fstop = 2.8
cam.keyframe_insert('location', frame=1); cam.keyframe_insert('rotation_euler', frame=1)
cam.location.z += 0.12; cam.location.y += 0.1
cam.rotation_euler = (Vector((0.5, 3.0, 2.25)) - cam.location).to_track_quat('-Z', 'Y').to_euler()  # tilt up to follow the strip
cam.keyframe_insert('location', frame=192); cam.keyframe_insert('rotation_euler', frame=192)
def anim_fcurves(obj):  # Blender 4.x: action.fcurves; Blender 5.x: layered actions (channelbags)
    a = obj.animation_data.action
    if hasattr(a, 'fcurves'): return a.fcurves
    from bpy_extras import anim_utils
    return anim_utils.action_get_channelbag_for_slot(a, obj.animation_data.action_slot).fcurves
for fc in anim_fcurves(cam):
    for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'
    n = fc.modifiers.new('NOISE'); n.scale = 40; n.strength = 0.012 if fc.data_path == 'location' else 0.004

# ---------------- render settings ----------------
r = sc.render; r.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = DENOISE; sc.cycles.max_bounces = 4; sc.cycles.transmission_bounces = 4; sc.cycles.use_adaptive_sampling = True; sc.cycles.sample_clamp_indirect = 1.0; sc.cycles.sample_clamp_direct = 8.0
r.resolution_x = RES_X; r.resolution_y = int(RES_X / 2.39) // 2 * 2; r.resolution_percentage = 100
r.image_settings.file_format = 'PNG'; r.filepath = OUT
sc.view_settings.view_transform = 'AgX'
for look in ('AgX - Medium High Contrast', 'Medium High Contrast'):
    try: sc.view_settings.look = look; break
    except Exception: pass
try: pass
except Exception: pass
sc.view_settings.exposure = 1.1
bpy.context.view_layer.use_pass_mist = True
FOG = hexrgb('#1f2c3c')
if hasattr(sc, 'compositing_node_group'):  # Blender 5.x compositor
    nt = bpy.data.node_groups.new('Comp', 'CompositorNodeTree'); sc.compositing_node_group = nt
    nt.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = nt.nodes.new('CompositorNodeRLayers')
    mf = nt.nodes.new('ShaderNodeMath'); mf.operation = 'MULTIPLY'; mf.inputs[1].default_value = 0.75
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.inputs[7].default_value = FOG
    gl = nt.nodes.new('CompositorNodeGlare'); gl.inputs['Type'].default_value = 'Fog Glow'; gl.inputs['Threshold'].default_value = 0.9
    if 'Size' in gl.inputs: gl.inputs['Size'].default_value = 0.5
    out = nt.nodes.new('NodeGroupOutput')
    nt.links.new(rl.outputs['Mist'], mf.inputs[0]); nt.links.new(mf.outputs[0], mix.inputs[0]); nt.links.new(rl.outputs['Image'], mix.inputs[6])
    nt.links.new(mix.outputs[2], gl.inputs['Image']); nt.links.new(gl.outputs['Image'], out.inputs[0])
else:  # Blender 4.x compositor
    sc.use_nodes = True; nt = sc.node_tree; nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers'); mix = nt.nodes.new('CompositorNodeMixRGB'); mix.blend_type = 'MIX'
    mix.inputs[2].default_value = FOG; gl = nt.nodes.new('CompositorNodeGlare'); gl.glare_type = 'FOG_GLOW'; gl.threshold = 0.9; gl.size = 8
    mf = nt.nodes.new('CompositorNodeMath'); mf.operation = 'MULTIPLY'; mf.inputs[1].default_value = 0.75
    out = nt.nodes.new('CompositorNodeComposite')
    nt.links.new(rl.outputs['Mist'], mf.inputs[0]); nt.links.new(mf.outputs[0], mix.inputs[0]); nt.links.new(rl.outputs['Image'], mix.inputs[1])
    nt.links.new(mix.outputs[0], gl.inputs[0]); nt.links.new(gl.outputs[0], out.inputs[0])

sc.frame_start, sc.frame_end = F0, F1
bpy.ops.wm.save_as_mainfile(filepath=OUT.rstrip('/') + '_scene.blend')
bpy.ops.render.render(animation=True)
