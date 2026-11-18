#!/bin/bash
# Render all 1350 frames in 3 parallel browser processes, then mux with audio.
set -e
cd "$(dirname "$0")"
OUT=../../build/waswaere/frames
export PLAYWRIGHT_PATH=${PLAYWRIGHT_PATH:-playwright}
node render.mjs frames 0 450 $OUT > ../../build/waswaere/log0.txt 2>&1 &
node render.mjs frames 450 900 $OUT > ../../build/waswaere/log1.txt 2>&1 &
node render.mjs frames 900 1350 $OUT > ../../build/waswaere/log2.txt 2>&1 &
wait
[ -f ../../build/waswaere/audio.wav ] || python3 audio.py
ffmpeg -y -loglevel error -framerate 30 -i $OUT/f%05d.jpg -i ../../build/waswaere/audio.wav \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -profile:v high -movflags +faststart \
  -af "loudnorm=I=-15:TP=-1.5:LRA=14" -ar 48000 -c:a aac -b:a 192k -shortest ../../was-waere-wenn-teil1.mp4
echo done
