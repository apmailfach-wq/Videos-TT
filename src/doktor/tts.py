"""edge-tts per line (+ word timings) -> build/doktor/"""
import asyncio, json, os, ssl, subprocess
from pathlib import Path
import edge_tts
import edge_tts.communicate as _ec
from script import LINES

PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
_ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.exists(_ca):
    _ec._SSL_CTX = ssl.create_default_context(cafile=_ca)
OUT = Path(__file__).resolve().parents[2] / "build" / "doktor"
OUT.mkdir(parents=True, exist_ok=True)

async def synth(i, who, text, voice, rate, pitch):
    for attempt in range(12):
        try:
            return await _synth(i, who, text, voice, rate, pitch)
        except edge_tts.exceptions.NoAudioReceived:
            print("retry", i, attempt); await asyncio.sleep(1.5)
    raise RuntimeError(f"TTS failed for line {i}")

async def _synth(i, who, text, voice, rate, pitch):
    c = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary", proxy=PROXY)
    mp3 = OUT / f"line{i}.mp3"; words = []
    with open(mp3, "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio": f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"text": ch["text"], "start": ch["offset"]/1e7,
                              "end": (ch["offset"]+ch["duration"])/1e7})
    wav = OUT / f"line{i}.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp3), "-ac", "1", "-ar", "44100", str(wav)], check=True)
    return {"who": who, "text": text, "wav": str(wav), "words": words}

async def main():
    res = [await synth(i, *l[:5]) for i, l in enumerate(LINES)]
    (OUT / "timings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for r in res: print(r["who"], r["text"], [w["text"] for w in r["words"]])
asyncio.run(main())
