#!/usr/bin/env bash
# Assemble rendered PNG frames + audio into a graded MP4.
# Usage: assemble.sh <frames_prefix e.g. out/f_> <audio.wav|none> <output.mp4> [fps=24]
# hqdn3d cleans Cycles noise (the apt build of Blender has no OpenImageDenoise);
# vignette + light temporal grain give a filmic finish and hide leftover noise.
set -euo pipefail
PREFIX="$1"; AUDIO="$2"; OUT="$3"; FPS="${4:-24}"
VF="hqdn3d=4:3:6:6,vignette=PI/5,noise=alls=5:allf=t"
if [ "$AUDIO" = "none" ]; then
  ffmpeg -y -loglevel error -framerate "$FPS" -i "${PREFIX}%04d.png" -vf "$VF" -c:v libx264 -crf 18 -pix_fmt yuv420p -movflags +faststart "$OUT"
else
  ffmpeg -y -loglevel error -framerate "$FPS" -i "${PREFIX}%04d.png" -i "$AUDIO" -vf "$VF" -c:v libx264 -crf 18 -pix_fmt yuv420p \
    -c:a aac -b:a 192k -shortest -movflags +faststart "$OUT"
fi
ffprobe -v error -show_entries format=duration -of default=nw=1 "$OUT"
