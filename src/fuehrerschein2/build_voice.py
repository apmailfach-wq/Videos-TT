"""Turn the aligned self-recording into per-scene wavs + timings.json for render.py."""
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

from script import SCENES

TEMPO = 1.2
PAUSE_IN = 0.2      # pause between breaths inside a chapter
PAUSE_SCENE = 0.5   # pause at the end of a chapter
PAD = 0.04
SR = 48000


def read(path):
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def main(clean_wav, words_json, segs_json, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    audio = read(clean_wav)
    words = json.load(open(words_json))
    segs = json.load(open(segs_json))
    # which segments belong to which scene
    seg_scene = {}
    for w in words:
        seg_scene.setdefault(w["seg"], w["scene"])
    tmp = out / "seg.wav"
    res = []
    for si in range(len(SCENES)):
        pieces, t, wout = [], 0.0, []
        my = [i for i in range(len(segs)) if seg_scene.get(i) == si]
        for n, i in enumerate(my):
            a, b = segs[i]
            a0, b0 = max(0, a - PAD), min(len(audio) / SR, b + PAD)
            seg = audio[int(a0 * SR):int(b0 * SR)]
            with wave.open(str(tmp), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
                w.writeframes((seg * 32767).astype(np.int16).tobytes())
            sped = out / "seg_fast.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-af", f"atempo={TEMPO}", str(sped)],
                           check=True)
            fast = read(sped)
            for w_ in words:
                if w_["seg"] == i:
                    wout.append(dict(text=w_["text"], start=t + (w_["start"] - a0) / TEMPO,
                                     end=t + (w_["end"] - a0) / TEMPO))
            pieces.append(fast)
            t += len(fast) / SR
            gap = PAUSE_SCENE if n == len(my) - 1 else PAUSE_IN
            pieces.append(np.zeros(int(gap * SR), np.float32))
            t += gap
        lead = np.zeros(int(0.15 * SR), np.float32) if si == 0 else np.zeros(0, np.float32)
        sig = np.concatenate([lead] + pieces)
        if si == 0:
            for w_ in wout:
                w_["start"] += 0.15
                w_["end"] += 0.15
        path = out / f"scene{si}.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.clip(sig, -1, 1) * 32767).astype(np.int16).tobytes())
        res.append(dict(audio=str(path), duration=len(sig) / SR, words=wout))
        print(si, round(len(sig) / SR, 2), len(wout))
    (out / "timings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("total", round(sum(r["duration"] for r in res), 2))


if __name__ == "__main__":
    main(*sys.argv[1:5])
