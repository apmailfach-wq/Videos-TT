"""edge-tts für jede Zeile (mit Wort-Timings) -> build/frieda/lines.json"""
import asyncio, json, os, ssl, subprocess
from pathlib import Path
import edge_tts
import edge_tts.communicate as _ec
from script import LINES, VOICES

OUT = Path(__file__).resolve().parents[2] / "build" / "frieda"
OUT.mkdir(parents=True, exist_ok=True)
PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
_ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.exists(_ca):
    _ec._SSL_CTX = ssl.create_default_context(cafile=_ca)


async def synth(lid, spk, text):
    voice, rate, pitch = VOICES[spk]
    mp3, wav = OUT / f"{lid}.mp3", OUT / f"{lid}.wav"
    words = []
    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary", proxy=PROXY)
    with open(mp3, "wb") as f:
        async for c in comm.stream():
            if c["type"] == "audio":
                f.write(c["data"])
            elif c["type"] == "WordBoundary":
                words.append({"text": c["text"], "start": c["offset"] / 1e7,
                              "end": (c["offset"] + c["duration"]) / 1e7})
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "48000", "-ac", "1", str(wav)],
                   check=True)
    first = words[0]["start"] if words else 0.0
    last = words[-1]["end"] + 0.1 if words else 1.0
    return dict(id=lid, speaker=spk, text=text, wav=str(wav), lead=first, speech=last - first, words=words)


async def main():
    res = [await synth(*l) for l in LINES]
    (OUT / "lines.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for r in res:
        print(f'{r["speech"]:5.2f}s lead {r["lead"]:.2f}  {r["speaker"]:7s} {r["text"]}')

asyncio.run(main())
