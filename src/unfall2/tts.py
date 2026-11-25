"""Generate the German voiceover per scene with edge-tts and store word timings."""
import asyncio, json, subprocess, sys, wave
import numpy as np
from pathlib import Path
import os, ssl
import edge_tts
import edge_tts.communicate as _ec

# Route through the environment's HTTPS proxy / CA bundle if present.
PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
_ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.exists(_ca):
    _ec._SSL_CTX = ssl.create_default_context(cafile=_ca)

from script import SCENES, VOICE, RATE

OUT = Path(__file__).resolve().parents[2] / "build" / "unfall2"
OUT.mkdir(parents=True, exist_ok=True)


SR = 48000
MAX_SIL = 0.16   # longest pause kept inside a line
TEMPO = 1.05     # extra pitch-preserving speed-up


def tighten(wav, words):
    """Shorten silences longer than MAX_SIL; remap word timings."""
    with wave.open(str(wav)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)
    hop = SR // 100
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1))
    silent = rms < max(120.0, rms.max() * 0.02)
    keep = np.ones(n, bool)
    i = 0
    cuts = []  # (time_of_cut_start, removed_seconds)
    while i < n:
        if silent[i]:
            j = i
            while j < n and silent[j]:
                j += 1
            L = j - i
            lim = int(MAX_SIL * 100)
            if L > lim and i > 0 and j < n:
                drop0 = i + lim // 2
                drop1 = j - (lim - lim // 2)
                keep[drop0:drop1] = False
                cuts.append((drop0 / 100, (drop1 - drop0) / 100))
            i = j
        else:
            i += 1
    out = a[:n * hop].reshape(n, hop)[keep].reshape(-1)
    out = np.concatenate([out, a[n * hop:]])
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(out.astype(np.int16).tobytes())

    def remap(t):
        s = 0.0
        for c0, d in cuts:
            if t > c0 + d:
                s += d
            elif t > c0:
                s += t - c0
        return t - s
    for wd in words:
        wd["start"], wd["end"] = remap(wd["start"]), remap(wd["end"])



async def synth(idx, text):
    comm = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="WordBoundary", proxy=PROXY)
    mp3 = OUT / f"scene{idx}.mp3"
    words = []
    with open(mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"text": chunk["text"],
                              "start": chunk["offset"] / 1e7,
                              "end": (chunk["offset"] + chunk["duration"]) / 1e7})
    wav = OUT / f"scene{idx}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-af", f"atempo={TEMPO}",
                    "-ar", str(SR), "-ac", "1", str(wav)], check=True)
    for wd in words:
        wd["start"] /= TEMPO
        wd["end"] /= TEMPO
    tighten(wav, words)
    # cut trailing silence, keep a short breath between scenes
    end = words[-1]["end"] + 0.28
    with wave.open(str(wav)) as w:
        a = w.readframes(w.getnframes())
    a = a[: int(end * SR) * 2]
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(a)
    return {"audio": str(wav), "duration": len(a) / 2 / SR, "words": words}


async def main():
    res = [await synth(i, s["text"]) for i, s in enumerate(SCENES)]
    (OUT / "timings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for i, r in enumerate(res):
        print(i, round(r["duration"], 2), len(r["words"]))
    print("total", round(sum(r["duration"] for r in res), 2))

asyncio.run(main())
