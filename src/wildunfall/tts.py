"""edge-tts voice per line + word timings -> build/wildunfall/voice.json"""
import asyncio, json, os, ssl, subprocess
from pathlib import Path

import edge_tts
import edge_tts.communicate as _ec

from script import LINES, VOICE, RATE

_ca = "/root/.ccr/ca-bundle.crt"
if os.path.exists(_ca):
    _ec._SSL_CTX = ssl.create_default_context(cafile=_ca)
PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
OUT = Path(__file__).resolve().parents[2] / "build" / "wildunfall"
OUT.mkdir(parents=True, exist_ok=True)


async def synth(key, text):
    comm = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="WordBoundary", proxy=PROXY)
    mp3 = OUT / f"{key}.mp3"
    words = []
    with open(mp3, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"w": ch["text"], "s": ch["offset"] / 1e7, "e": (ch["offset"] + ch["duration"]) / 1e7})
    wav = OUT / f"{key}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "48000", "-ac", "1", str(wav)], check=True)
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                         str(wav)]).decode())
    return {"key": key, "wav": str(wav), "dur": dur, "words": words}


async def main():
    res = []
    t = 0.35
    for key, text, gap in LINES:
        r = await synth(key, text)
        speech_end = r["words"][-1]["e"] if r["words"] else r["dur"]
        r["start"] = t
        r["end"] = t + speech_end
        t = r["end"] + gap
        res.append(r)
        print(f"{key:9s} {r['start']:6.2f} -> {r['end']:6.2f}  ({len(r['words'])} words)")
    (OUT / "voice.json").write_text(json.dumps({"lines": res, "total": t}, ensure_ascii=False, indent=1))
    print("total", round(t, 2))

asyncio.run(main())
