#!/bin/bash
# Renders all shots with two parallel Blender workers (2 threads each).
PY=${BPY:-python3}
cd "$(dirname "$0")"
( for s in hook brake wave aerial gap; do THREADS=2 $PY shots.py $s; done ) > ../../build/stau/workerA.log 2>&1 &
( for s in roll zipper outro; do THREADS=2 $PY shots.py $s; done ) > ../../build/stau/workerB.log 2>&1 &
wait
