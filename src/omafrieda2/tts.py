"""edge-tts je Zeile (mit Wortzeiten), Nachbearbeitung.

Natürliche Sprechgeschwindigkeit: Statt eine Zeile stark zu beschleunigen, wird die Zeitachse an dieser Stelle
gedehnt ("Warp"). Die Knoten der Dehnung (Basiszeit -> neue Zeit) landen in timeline.json; render.py übersetzt
damit Bild, Untertitel und Geräusche.
"""
import asyncio
import json
import os
import ssl
import subprocess
from pathlib import Path

import edge_tts
import edge_tts.communicate as _ec

from script import LINES, TOTAL, VOICES

OUT = Path(__file__).resolve().parents[2] / "build" / "omafrieda2"
OUT.mkdir(parents=True, exist_ok=True)
PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
_ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.exists(_ca):
    _ec._SSL_CTX = ssl.create_default_context(cafile=_ca)

MAX_TEMPO = 1.08   # höchstens 8 % schneller als natürlich
MAX_GAP = 0.22     # lange Satzpausen werden auf diese Länge gekürzt


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
    import numpy as np
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp3), "-f", "s16le", "-ac", "1", "-ar", "48000", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(pcm, np.int16).astype(np.float32)
    SR = 48000
    lead = words[0]["start"] if words else 0.0
    speech_end = (words[-1]["end"] + 0.12) if words else len(x) / SR
    # lange Pausen zwischen Wörtern kürzen (Wortzeiten werden exakt mitverschoben)
    segs, cut = [], 0.0
    pos = max(0.0, lead - 0.03)
    new_words = []
    for i, w in enumerate(words):
        ws, we = w["start"] - cut, w["end"] - cut
        new_words.append(dict(text=w["text"], start=ws, end=we))
        if i + 1 < len(words):
            gap = words[i + 1]["start"] - w["end"]
            if gap > MAX_GAP + 0.05:
                a0 = w["end"] + 0.06
                a1 = words[i + 1]["start"] - (MAX_GAP - 0.06)
                segs.append((pos, a0))
                pos = a1
                cut += a1 - a0
    segs.append((pos, speech_end))
    # Teilstücke mit 12-ms-Überblendung verbinden (keine Knackser an den Nähten)
    xf = int(0.012 * SR)
    pieces = [x[int(p0 * SR):int(p1 * SR)].copy() for p0, p1 in segs]
    y = pieces[0]
    for p in pieces[1:]:
        if len(y) > xf and len(p) > xf:
            ramp = np.linspace(0, 1, xf, dtype=np.float32)
            mix = y[-xf:] * (1 - ramp) + p[:xf] * ramp
            y = np.concatenate([y[:-xf], mix, p[xf:]])
            cut += xf / SR   # Überblendung verkürzt minimal
        else:
            y = np.concatenate([y, p])
    fade = int(0.008 * SR)
    if len(y) > 2 * fade:
        y[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
        y[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    trimmed = OUT / f"{lid}_trim.wav"
    import wave as _wave
    with _wave.open(str(trimmed), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(np.clip(y, -32768, 32767).astype(np.int16).tobytes())
    words = new_words
    lead = 0.03
    raw = len(y) / SR - 0.03
    allowed = latest - start
    tempo = max(1.0, min(MAX_TEMPO, raw / allowed))
    filt = "anull"
    if tempo > 1.001:
        filt += f",atempo={tempo:.4f}"
    filt += "," + post + ",apad=pad_dur=0.25"
    wav = OUT / f"{lid}.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(trimmed), "-af", filt, "-ar", "48000", "-ac", "1",
                    str(wav)], check=True)
    length = raw / tempo
    # Wortzeiten relativ zum Audioanfang (Audio beginnt 0.03 s vor dem ersten Wort)
    w0 = words[0]["start"] if words else 0.0
    words = [dict(text=w["text"], start=w["start"] - w0 + lead, end=w["end"] - w0 + lead) for w in words]
    return dict(id=lid, speaker=spk, text=text, wav=str(wav), base_start=start, base_end=latest, tempo=tempo,
                length=length, extra=max(0.0, length - allowed),
                rel_words=[dict(text=w["text"], s=(w["start"] - lead + 0.03) / tempo,
                                e=(w["end"] - lead + 0.03) / tempo) for w in words])


async def main():
    res = []
    for lid, spk, text, start, latest in LINES:
        res.append(await synth(lid, spk, text, start, latest))
    res.sort(key=lambda r: r["base_start"])
    # natürliche Reaktionspause vor der nächsten Zeile (mind. 0,3 s)
    for r, nxt in zip(res, res[1:]):
        room = nxt["base_start"] - r["base_start"]
        r["extra"] = max(r["extra"], r["length"] + 0.3 - room)
        r["base_end"] = max(r["base_end"], min(nxt["base_start"], r["base_end"]))
    # Warp-Knoten: jede Zeile bekommt ihre natürliche Länge
    knots = [(0.0, 0.0)]
    shift = 0.0
    for r in res:
        a, b = r["base_start"], r["base_end"]
        knots.append((a, a + shift))
        shift += r["extra"]
        knots.append((b, b + shift))
    knots.append((TOTAL, TOTAL + shift))
    knots = sorted(set(knots))

    def W(t):
        for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
            if x0 <= t <= x1:
                return y0 + (y1 - y0) * ((t - x0) / (x1 - x0) if x1 > x0 else 0)
        return t + shift

    out = []
    for r in res:
        s = W(r["base_start"])
        out.append(dict(id=r["id"], speaker=r["speaker"], text=r["text"], wav=r["wav"], start=s,
                        end=s + r["length"], tempo=r["tempo"],
                        words=[dict(text=w["text"], start=s + w["s"], end=s + w["e"]) for w in r["rel_words"]]))
        print(f'{s:6.2f}-{s + r["length"]:6.2f} tempo {r["tempo"]:.2f} +{r["extra"]:.2f}s {r["speaker"]:8s} {r["text"]}')
    (OUT / "timeline.json").write_text(json.dumps(dict(lines=out, warp=knots, total=TOTAL + shift),
                                                  ensure_ascii=False, indent=1))
    print("TOTAL", round(TOTAL + shift, 2), "(+%.2f s für natürliche Sprechpausen)" % shift)

asyncio.run(main())
