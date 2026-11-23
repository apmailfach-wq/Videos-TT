"""Vertont eine Folge segmentweise mit edge-tts (inkl. Wort-Timings).

    python3 tts.py schein|flasche|socke|all
-> build/dinge/<folge>/seg_XX.mp3 + timings.json (globale Zeiten inkl. Pausen)
"""
import asyncio, json, os, ssl, subprocess, sys
from pathlib import Path

import wave

import numpy as np
import edge_tts
import edge_tts.communicate as _ec

from script import EPISODES

PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
_ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.exists(_ca):
    _ec._SSL_CTX = ssl.create_default_context(cafile=_ca)

ROOT = Path(__file__).resolve().parents[2]
LEAD = 0.15
SR = 48000
PAUSE_SCALE = 0.75  # global tightening of the dramatic pauses


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(p)]).decode().strip())


async def synth(ep, i, seg, out):
    comm = edge_tts.Communicate(seg["t"], ep["voice"], rate=ep["rate"], pitch=ep["pitch"],
                                boundary="WordBoundary", proxy=PROXY)
    mp3 = out / f"seg_{i:02d}.mp3"
    words = []
    with open(mp3, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append(dict(text=ch["text"], start=ch["offset"] / 1e7,
                                  end=(ch["offset"] + ch["duration"]) / 1e7))
    # decode to wav and cut the silence edge-tts leaves around the speech
    raw = out / f"seg_{i:02d}_raw.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-ac", "1", "-ar", str(SR), str(raw)], check=True)
    a = np.frombuffer(open(raw, "rb").read()[44:], np.int16).astype(np.float32) / 32768
    env = np.convolve(np.abs(a), np.ones(480) / 480, "same")
    on = np.where(env > 0.01)[0]
    a0 = max(0, on[0] - int(0.03 * SR)); a1 = min(len(a), on[-1] + int(0.06 * SR))
    wav = out / f"seg_{i:02d}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((a[a0:a1] * 32767).astype(np.int16).tobytes())
    sh = a0 / SR
    words = [dict(w, start=max(0, w["start"] - sh), end=max(0, w["end"] - sh)) for w in words]
    return wav, words


async def run(name):
    ep = EPISODES[name]
    out = ROOT / "build" / "dinge" / name
    out.mkdir(parents=True, exist_ok=True)
    t, res = LEAD, []
    for i, seg in enumerate(ep["segs"]):
        mp3, words = await synth(ep, i, seg, out)
        d = dur(mp3)
        # edge-tts pads ~0.1 s of silence at the end; trim it from the pause budget
        res.append(dict(seg, i=i, audio=str(mp3), start=t, dur=d,
                        words=[dict(w, start=w["start"] + t, end=w["end"] + t) for w in words]))
        t += d + seg.get("p", 0.3) * PAUSE_SCALE
    (out / "timings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(name, "total", round(t, 2), "s,", sum(len(s["t"].split()) for s in ep["segs"]), "Wörter")


if __name__ == "__main__":
    names = list(EPISODES) if sys.argv[1:] in ([], ["all"]) else sys.argv[1:]
    for n in names:
        asyncio.run(run(n))
