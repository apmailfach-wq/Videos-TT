"""Voice every line (two voices) with edge-tts and store word timings."""
import asyncio, json, os, ssl, subprocess
from pathlib import Path
import edge_tts
import edge_tts.communicate as _ec

PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
_ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.exists(_ca):
    _ec._SSL_CTX = ssl.create_default_context(cafile=_ca)

from lines import LINES, VOICES

OUT = Path(__file__).resolve().parent.parent.parent / "build" / "bossfight"
OUT.mkdir(parents=True, exist_ok=True)


async def synth(i, who, text):
    v = VOICES[who]
    comm = edge_tts.Communicate(text, v["voice"], rate=v["rate"], pitch=v["pitch"],
                                boundary="WordBoundary", proxy=PROXY)
    mp3 = OUT / f"line{i:02d}.mp3"
    words = []
    with open(mp3, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"text": ch["text"], "start": ch["offset"] / 1e7,
                              "end": (ch["offset"] + ch["duration"]) / 1e7})
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                         "-of", "csv=p=0", str(mp3)]).decode())
    return {"audio": str(mp3), "duration": dur, "words": words}


async def main():
    res = [await synth(i, w, t) for i, (_, w, t) in enumerate(LINES)]
    (OUT / "timings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for (k, w, _), r in zip(LINES, res):
        print(f"{k:8s} {w:5s} {r['duration']:.2f}")
    print("total", round(sum(r["duration"] for r in res), 2))

asyncio.run(main())
