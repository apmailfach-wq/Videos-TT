#!/bin/bash
# Render all 2040 frames (68 s) in 3 parallel browser processes, then mux with audio.
set -e
cd "$(dirname "$0")"
OUT=../../build/waswaere/frames
export PLAYWRIGHT_PATH=${PLAYWRIGHT_PATH:-playwright}
node render.mjs frames 0 800 $OUT > ../../build/waswaere/log0.txt 2>&1 &
node render.mjs frames 800 1560 $OUT > ../../build/waswaere/log1.txt 2>&1 &
node render.mjs frames 1560 2040 $OUT > ../../build/waswaere/log2.txt 2>&1 &
wait
python3 audio.py
ffmpeg -y -loglevel error -framerate 30 -i $OUT/f%05d.jpg -i ../../build/waswaere/audio.wav \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -profile:v high -movflags +faststart \
  -af "loudnorm=I=-15:TP=-1.5:LRA=14" -ar 48000 -c:a aac -b:a 192k ../../was-waere-wenn-teil1.mp4
echo done
