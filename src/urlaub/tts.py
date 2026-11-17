"""Voiceover per scene (edge-tts, de-AT-JonasNeural) + word timings -> build/urlaub/."""
import asyncio, json, subprocess, sys
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

OUT = Path(__file__).resolve().parents[2] / "build" / "urlaub"
OUT.mkdir(parents=True, exist_ok=True)


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
    # tighten the pause after each scene so the whole clip stays snappy (35-45 s)
    keep = words[-1]["end"] + (0.75 if idx == len(SCENES) - 1 else 0.38)
    wav = OUT / f"scene{idx}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-t", f"{keep:.3f}",
                    "-af", "afade=t=out:st=%.3f:d=0.08" % (keep - 0.08), "-ar", "48000", "-ac", "1", str(wav)],
                   check=True)
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(wav)]).decode().strip())
    return {"audio": str(wav), "duration": dur, "words": words}


async def main():
    res = [await synth(i, s["text"]) for i, s in enumerate(SCENES)]
    (OUT / "timings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for i, r in enumerate(res):
        print(i, round(r["duration"], 2), len(r["words"]))
    print("total", round(sum(r["duration"] for r in res), 2))

asyncio.run(main())
