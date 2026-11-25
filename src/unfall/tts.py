"""Generate every line with edge-tts (word timings), tighten internal pauses, lay lines on one timeline."""
import asyncio, json, os, ssl, subprocess, wave
from pathlib import Path
import numpy as np
import edge_tts
import edge_tts.communicate as _ec
from script import LEAD, LINES, VOICES

OUT = Path(__file__).resolve().parents[2] / "build" / "unfall"
OUT.mkdir(parents=True, exist_ok=True)
PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
_ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.exists(_ca):
    _ec._SSL_CTX = ssl.create_default_context(cafile=_ca)
SR = 48000
MAX_SIL = 0.13   # longest pause kept inside a line
TEMPO = 1.06     # extra pitch-preserving speed-up


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
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-af", f"atempo={TEMPO}",
                    "-ar", str(SR), "-ac", "1", str(wav)], check=True)
    for wd in words:
        wd["start"] /= TEMPO
        wd["end"] /= TEMPO
    tighten(wav, words)
    with wave.open(str(wav)) as w:
        dur = w.getnframes() / SR
    speech_end = words[-1]["end"] + 0.1 if words else dur
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
