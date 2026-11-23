# Lessons from the first shot (ORIGINS 8J)

Each item is a real problem that cost a test cycle. Check your script against this list before the first test render.

## Crashes and setup
- **"Build without OpenImageDenoiser":** the apt (Ubuntu) build of Blender has no OIDN. Prefer the official `bpy` wheel from PyPI (Blender 5.3 was tested, with OIDN working). blender.org itself was blocked (403) by the proxy. Install the pip wheel in a background task, because a 60 s timeout is not enough for it.
- **`Couldn't open libEGL.so.1`, then abort (exit 134)** with the pip `bpy`: install `libegl1 libgl1 libgles2 libgl1-mesa-dri libvulkan1 mesa-vulkan-drivers`. The Vulkan warning that remains is harmless.
- **Blender 5 API changes** that broke a 4.0 script:
  - `action.fcurves` is gone, so use `bpy_extras.anim_utils.action_get_channelbag_for_slot(action, obj.animation_data.action_slot).fcurves`.
  - `scene.node_tree` is gone. The compositor is a `CompositorNodeTree` node group assigned to `scene.compositing_node_group`, with a `NodeGroupOutput` (add an `Image` output socket to its interface).
  - `CompositorNodeMixRGB`, `CompositorNodeMath` and `CompositorNodeComposite` are gone. Use `ShaderNodeMix` (data_type `RGBA`, colour inputs at index 6 and 7, colour output at index 2) and `ShaderNodeMath`.
  - Glare options are now input sockets: `gl.inputs['Type'].default_value = 'Fog Glow'`, `gl.inputs['Threshold']`.
- **Denoising tradeoff:** OIDN gives clean frames at 32 samples, but it smooths fine bump texture (wool, plaster) and makes primitive characters look even more like smooth mannequins. Raise the bump strength or the texture scale if surfaces look plastic.
- **EEVEE** needs an OpenGL context, so in a headless CPU container use **Cycles**.
- **Editing scripts with string replacement:** when a replacement splits a line that holds several `;`-separated statements, the next line can end up with a stray leading space, which causes an `IndentationError`. Prefer one statement per line in shot scripts.

## Geometry
- **Walls around an opening:** centre each side piece at `±(half_opening + half_piece_width)`. A first version centred them further out and left gaps that showed the city through the "wall".
- **Hinged casements:** a pane hinged at the left edge that extends toward +x swings outward (+y) with a **positive** Z rotation. The right pane needs a negative rotation. In short: `rotation_z = side * radians(-65)` with side = −1 for left and +1 for right.
- **The view out of a window:** keep tall buildings out of the axis of the view (skip |x| < 6 for y < 32), and make buildings taller as they get further away, so the window frames a roofscape instead of a wall.
- **Hero prop vs. actor:** a prop that leaves the actor's hand travels along the camera's line of sight, and the actor's head easily hides it. Offset the actor to one side, offset the camera the same way, and keep the prop's path on the open side of the frame.

## Light (night interior lit through a window, AgX, exposure 1.1)
| Light | Settings that worked |
|---|---|
| Outside key (rain light) | AREA, size 6, **4500 W**, colour `#7f9bb8`, about 6 m outside, aimed at the actor |
| Interior fill | AREA, size 2, 140 W, colour `#2E3A4A` |
| Window bounce | AREA, size 1.6, 70 W, just inside the window facing into the room, `visible_camera = False` |
| Glowing strip | emission 14 → 4 over the shot, plus a parented POINT light of 30 → 6 W |
| World | `#1e2a3a` at strength 1.2; mist from 4 m start over 30 m depth |

The first attempt used a 900 W key and exposure 0.4, and the room came out almost black.

## Noise
- Use `sample_clamp_indirect = 1.0` and `sample_clamp_direct = 8.0` to kill fireflies from the bright emissive prop.
- 32 samples plus ffmpeg hqdn3d plus film grain is acceptable for an animatic-to-preview level. Use 64+ samples for anything final.

## Materials
- Grey wool with sheen 0.6 under a strong key looks like white marshmallow. Use a darker base (`#4a515b`) and sheen of about 0.2.
- Glass: transmission 1.0, roughness 0.04.

## Timing (4-core CPU, no GPU)
- At 960×402 and 32 samples: about 13 s per frame on apt Blender 4.0 (no denoise), and about 17 s per frame on pip Blender 5.3 with OIDN. Each test frame also pays a few seconds of startup.
- 8 s at 24 fps (192 frames) took about 40 min. Quote time to the user before full renders, and suggest lower width, lower fps, or fewer shots when the time is too long.

## Characters
Primitive-built people (cone body, sphere head, cylinder limbs) read as mannequins. Make it work by:
- shooting from behind, backlit, small in frame, or as a silhouette in a doorway or window;
- letting light and props carry the emotion;
- using AI image generation or rigged models for faces when the shot needs them.
