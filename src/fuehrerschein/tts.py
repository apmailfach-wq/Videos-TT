"""Generate every line with edge-tts (word timings included) and lay them on one timeline."""
import asyncio, json, os, ssl, subprocess
from pathlib import Path
import edge_tts
import edge_tts.communicate as _ec
from script import LINES, VOICES

OUT = Path(__file__).resolve().parents[2] / "build" / "fuehrerschein"
OUT.mkdir(parents=True, exist_ok=True)
PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
_ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.exists(_ca):
    _ec._SSL_CTX = ssl.create_default_context(cafile=_ca)

LEAD = 0.25  # silence before the first line


async def synth(lid, spk, text):
    voice, rate, pitch = VOICES[spk]
    mp3 = OUT / f"{lid}.mp3"
    words = []
    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary", proxy=PROXY)
    with open(mp3, "wb") as f:
        async for c in comm.stream():
            if c["type"] == "audio":
                f.write(c["data"])
            elif c["type"] == "WordBoundary":
                words.append({"text": c["text"], "start": c["offset"] / 1e7,
                              "end": (c["offset"] + c["duration"]) / 1e7})
    wav = OUT / f"{lid}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "48000", "-ac", "1", str(wav)], check=True)
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                         "-of", "csv=p=0", str(wav)]).decode())
    # trim trailing silence edge-tts adds (~0.1-0.2 s) by trusting last word end
    speech_end = words[-1]["end"] + 0.12 if words else dur
    return dict(id=lid, speaker=spk, text=text, wav=str(wav), dur=dur, speech=min(dur, speech_end), words=words)


async def main():
    res, t = [], LEAD
    for lid, spk, text, pause in LINES:
        r = await synth(lid, spk, text)
        r["start"] = t
        t += r["speech"] + pause
        res.append(r)
    (OUT / "timeline.json").write_text(json.dumps(dict(lines=res, total=t), ensure_ascii=False, indent=1))
    for r in res:
        print(f'{r["start"]:6.2f} {r["speech"]:5.2f} {r["speaker"]:8s} {r["text"][:60]}')
    print("TOTAL", round(t, 2))

asyncio.run(main())
