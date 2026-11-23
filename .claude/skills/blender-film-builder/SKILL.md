---
name: blender-film-builder
description: Turns a storyboard shot into a real rendered 3D video clip for free, using headless Blender driven by Python (bpy) in a CPU-only Linux container, then grades it and adds sound with ffmpeg. Use this skill whenever the user wants to actually produce or render a film shot, scene, or animated short (especially one planned with idea-to-film-director), wants "real 3D" instead of 2D drawings or an animatic, asks to make a scene in Blender, or wants to avoid paid AI video generators. It also applies to requests like "صوّر هذا المشهد", "اعمل اللقطة ثلاثية الأبعاد" or "استخدم بلندر".
---

# Blender Film Builder

Build each storyboard shot as a Python script that constructs the set, characters, props, lights and camera procedurally. Render it headless with Cycles on the CPU, then assemble the frames with audio into an MP4.

What this approach is good and bad at shapes every decision below, so be honest with the user about it:
- **Strong:** environments, architecture, weather (rain, mist), light that comes from objects (glowing props), and camera moves.
- **Weak:** characters. Bodies built from primitives read as mannequins. Keep characters small in frame, backlit, silhouetted or seen from behind. Suggest AI image generation or imported rigged models for close-ups of faces.
- **Slow:** a CPU renders a 960-wide frame at 32 samples in about 13 s, so an 8 s shot takes about 40 min. Always quote the render time before starting a full render.

## Workflow

### 1. Read the shot
From the storyboard, take the shot ID, duration, composition, action, camera, lighting and emotional intent. If the project has a production bible (palette hex codes, continuity rules), use it. The palette goes straight into the materials.

### 2. Install Blender once per container
**Preferred: the official build from PyPI** (`bpy`, Blender 5.x). It includes OpenImageDenoise, so frames come out clean. download.blender.org is often blocked by the network proxy, but PyPI is allowed. The download is large, so run it as a background task:
```bash
python3 -m venv ~/bpyenv && ~/bpyenv/bin/pip install -q bpy
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libegl1 libgl1 libgles2 libgl1-mesa-dri libvulkan1 mesa-vulkan-drivers
~/bpyenv/bin/python -c "import bpy; print(bpy.app.version_string)"
```
Without the EGL/GL libraries, rendering aborts with `Couldn't open libEGL.so.1`. Run shot scripts with `~/bpyenv/bin/python shot.py -- <args>`.

**Fallback: the Ubuntu apt build** (Blender 4.0, quick to install): `apt-get install -y blender`, then run with `blender -b -P shot.py -- <args>`. It has **no OpenImageDenoise**, so denoising must be off or the render aborts with "Build without OpenImageDenoiser". The template switches this automatically by version, and the ffmpeg step cleans up the noise instead.

The template works on both versions. Blender 5 moved the compositor to `scene.compositing_node_group` and animation curves into layered actions, and the template handles both.

### 3. Write the shot script
Copy `scripts/shot_template.py` (a complete, working shot) and replace its scene sections. Keep its structure, because each part solves a real problem:
- **Helpers:** `hexrgb` converts sRGB hex to linear colour, `mat` builds a Principled material (emission, sheen, transmission), `noisy` adds a bump so surfaces don't look like flat CG, `box` builds primitives, and `link_to` parents objects.
- **Set:** build walls as boxes *around* openings, and check that the pieces meet with no gaps (see the reference file).
- **Weather:** rain is a particle system instancing thin streak meshes, pushed by a wind force field. Use one large emitter for the distance and one small emitter for rain blowing near the camera.
- **Motion:** the Wave modifier makes cloth and paper move for free. Use keyframes for hero objects. Add F-curve NOISE modifiers on the camera for a handheld drift.
- **Glowing props:** an emissive material *plus* a point light parented to the prop, so the prop really lights the actor. Set `light.visible_camera = False`, or the light shows up as a bright ball.
- **Atmosphere:** in the compositor, mix the mist pass with a fog colour for depth, then add a FOG_GLOW glare for bloom.
- **Colour:** use the AgX view transform. Put `exposure` around 1.0 for night scenes.
- **Arguments:** the script reads `-- <out_prefix> [width] [samples] [f0] [f1]`, so the same file serves for test frames and the full render.

### 4. Test frames before the full render
Set `BL` to how Blender is run: `BL="$HOME/bpyenv/bin/python"` for the official build, or `BL="blender -b -P"` for apt. Render 2–3 single frames (beginning, middle, end) at width 960 and 32 samples, then look at them with `scripts/contact_sheet.py`:
```bash
mkdir -p test && for f in 30 110 180; do $BL shot.py -- $PWD/test/f_ 960 32 $f $f 2>&1 | grep -E "Error|Traceback"; done
python3 scripts/contact_sheet.py test/sheet.png test/f_0030.png test/f_0110.png test/f_0180.png
```
Look at the sheet yourself. The first renders almost always have one of these problems: too dark, something blocking the view, a hero prop hidden behind the actor, gaps in the walls, or visible lights. Fix and re-test. Writing each test into a fresh folder (`test2/`, `test3/` …) is simpler than deleting files.

### 5. Full render in the background
```bash
mkdir -p full && $BL shot.py -- $PWD/full/f_ 960 32 1 <last_frame> > full/render.log 2>&1
```
Run it as a background task. Tell the user how long it will take, and use the waiting time to prepare the audio.

### 6. Assemble
```bash
scripts/assemble.sh full/f_ shot_audio.wav SHOT_ID.mp4 24
```
This denoises (hqdn3d), adds a vignette and fine film grain, and muxes the audio. To cut audio for one shot out of a scene track: `ffmpeg -ss <start> -t <dur> -i scene.wav -af "afade=t=in:d=0.3,afade=t=out:st=<dur-0.6>:d=0.6" shot.wav`.

### 7. Deliver honestly
Send the MP4. Say what worked and what didn't (usually character quality, noise and darkness), and how long the render took. Then offer next steps: more shots, the hybrid approach (Blender sets plus AI-generated close-ups), or more samples for final quality.

## References
- `references/lessons.md`: specific bugs hit while building the first shot and their fixes, plus calibration numbers for lights, timing and samples. Read it before writing a new shot script; it saves several test cycles.
- `scripts/shot_template.py`: the complete working shot (night interior, open window, rain, city, glowing prop leaving the frame).
- `scripts/assemble.sh` and `scripts/contact_sheet.py`: assembly and review helpers.
