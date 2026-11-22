"""Voiceover per scene with edge-tts + word timings.  Usage: python3 tts.py geld"""
import asyncio, json, os, ssl, subprocess, sys
from pathlib import Path
import edge_tts
import edge_tts.communicate as _ec

PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
_ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.exists(_ca):
    _ec._SSL_CTX = ssl.create_default_context(cafile=_ca)

from episodes import EPISODES

EP = sys.argv[1]
E = EPISODES[EP]
OUT = Path(__file__).resolve().parents[2] / "build" / "sprichwort" / EP
OUT.mkdir(parents=True, exist_ok=True)


async def synth(i, text):
    comm = edge_tts.Communicate(text, E["voice"], rate=E["rate"], boundary="WordBoundary", proxy=PROXY)
    mp3, words = OUT / f"scene{i}.mp3", []
    with open(mp3, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append(dict(text=ch["text"], start=ch["offset"] / 1e7,
                                  end=(ch["offset"] + ch["duration"]) / 1e7))
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                         "-of", "csv=p=0", str(mp3)]).decode())
    return dict(audio=str(mp3), duration=dur, words=words)


async def main():
    res = [await synth(i, s["text"]) for i, s in enumerate(E["scenes"])]
    (OUT / "timings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for i, r in enumerate(res):
        print(i, round(r["duration"], 2), [w["text"] for w in r["words"]])
    print("total", round(sum(r["duration"] for r in res), 2))

asyncio.run(main())
