"""Voiceover per scene with edge-tts. English parts ([[...]]) are voiced as their own
segments so the multilingual voice pronounces them in English. Segments are trimmed
and joined into build/motivation/sceneN.wav; word timings are shifted accordingly."""
import asyncio, json, os, re, ssl, subprocess, wave
from pathlib import Path
import numpy as np
import edge_tts
import edge_tts.communicate as _ec

PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
_ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.exists(_ca):
    _ec._SSL_CTX = ssl.create_default_context(cafile=_ca)

from script import SCENES, VOICE, RATE

OUT = Path(__file__).resolve().parent.parent.parent / "build" / "motivation"
OUT.mkdir(parents=True, exist_ok=True)
SR = 24000


async def seg(text, path):
    comm = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="WordBoundary", proxy=PROXY)
    words = []
    with open(path, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"text": ch["text"], "start": ch["offset"] / 1e7,
                              "end": (ch["offset"] + ch["duration"]) / 1e7})
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, np.int16), words


async def scene(idx, text):
    parts = [p for p in re.split(r"(\[\[.*?\]\])", text) if p.strip()]
    audio, words, t = [], [], 0.0
    for j, p in enumerate(parts):
        txt = p.strip("[]").strip()
        x, ws = await seg(txt, OUT / f"seg{idx}_{j}.mp3")
        a = max(0.0, ws[0]["start"] - 0.03)
        b = ws[-1]["end"] + (0.28 if txt[-1] in ".,?!" else 0.06)
        audio.append(x[int(a * SR):int(b * SR)])
        words += [{"text": w["text"], "start": t + w["start"] - a, "end": t + w["end"] - a} for w in ws]
        t += b - a
    audio.append(np.zeros(int(0.15 * SR), np.int16))
    y = np.concatenate(audio)
    p = OUT / f"scene{idx}.wav"
    with wave.open(str(p), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR); wf.writeframes(y.tobytes())
    return {"audio": str(p), "duration": len(y) / SR, "words": words}


async def main():
    res = [await scene(i, s["text"]) for i, s in enumerate(SCENES)]
    (OUT / "timings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for s, r in zip(SCENES, res):
        print(s["key"], round(r["duration"], 2), " ".join(w["text"] for w in r["words"]))
    print("total", round(sum(r["duration"] for r in res), 2))

asyncio.run(main())
