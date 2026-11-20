#!/bin/bash
# Render all 2235 frames (74.5 s) in 3 parallel browser processes, then mux with audio.
set -e
cd "$(dirname "$0")"
OUT=../../build/waswaere/frames
export PLAYWRIGHT_PATH=${PLAYWRIGHT_PATH:-playwright}
node render.mjs frames 0 850 $OUT > ../../build/waswaere/log0.txt 2>&1 &
node render.mjs frames 850 1680 $OUT > ../../build/waswaere/log1.txt 2>&1 &
node render.mjs frames 1680 2235 $OUT > ../../build/waswaere/log2.txt 2>&1 &
wait
python3 audio.py
ffmpeg -y -loglevel error -framerate 30 -i $OUT/f%05d.jpg -i ../../build/waswaere/audio.wav \
  -c:v libx264 -preset slow -crf 21 -pix_fmt yuv420p -profile:v high -movflags +faststart \
  -af "loudnorm=I=-15:TP=-1.5:LRA=14" -ar 48000 -c:a aac -b:a 192k ../../was-waere-wenn-teil1.mp4
echo done
