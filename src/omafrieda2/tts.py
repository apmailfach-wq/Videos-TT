"""edge-tts je Zeile (mit Wortzeiten), Nachbearbeitung, Einpassen in das feste Zeitfenster."""
import asyncio, json, os, ssl, subprocess
from pathlib import Path
import edge_tts
import edge_tts.communicate as _ec
from script import LINES, VOICES

OUT = Path(__file__).resolve().parents[2] / "build" / "omafrieda2"
OUT.mkdir(parents=True, exist_ok=True)
PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
_ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.exists(_ca):
    _ec._SSL_CTX = ssl.create_default_context(cafile=_ca)


def dur_of(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(p)]).decode())


async def synth(lid, spk, text, start, latest):
    voice, rate, pitch, post = VOICES[spk]
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
    # find leading silence = first word start
    lead = words[0]["start"] if words else 0.0
    speech_end = (words[-1]["end"] + 0.12) if words else dur_of(mp3)
    raw = speech_end - lead
    allowed = latest - start
    tempo = max(1.0, raw / allowed)
    filt = f"atrim=start={max(0, lead - 0.03):.3f}:end={speech_end:.3f},asetpts=PTS-STARTPTS"
    if tempo > 1.001:
        filt += f",atempo={min(tempo, 2.0):.4f}"
    filt += "," + post + ",apad=pad_dur=0.25"
    wav = OUT / f"{lid}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-af", filt, "-ar", "48000", "-ac", "1",
                    str(wav)], check=True)
    ws = [dict(text=w["text"], start=start + (w["start"] - lead + 0.03) / tempo,
               end=start + (w["end"] - lead + 0.03) / tempo) for w in words]
    return dict(id=lid, speaker=spk, text=text, wav=str(wav), start=start, end=start + raw / tempo,
                tempo=tempo, words=ws)


async def main():
    res = []
    for lid, spk, text, start, latest in LINES:
        r = await synth(lid, spk, text, start, latest)
        res.append(r)
        print(f'{r["start"]:6.2f}-{r["end"]:6.2f} tempo {r["tempo"]:.2f} {spk:7s} {text}')
    (OUT / "timeline.json").write_text(json.dumps(dict(lines=res), ensure_ascii=False, indent=1))

asyncio.run(main())
