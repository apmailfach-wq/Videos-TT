#!/bin/bash
# Renders all shots with two parallel Blender workers (2 threads each).
# Safe to re-run: frames that already exist are skipped.
PY=${BPY:-python3}
cd "$(dirname "$0")"
export SKIP_EXISTING=1 THREADS=2
( for s in hook brake wave aerial gap posts; do $PY shots.py $s; done ) > ../../build/stau/workerA.log 2>&1 &
( for s in roll zipper gasse outro; do $PY shots.py $s; done ) > ../../build/stau/workerB.log 2>&1 &
wait
