"""Voiceover je Szene mit edge-tts + Wort-Timings.

Lange Satzpausen werden auf MAX_GAP gekürzt, und das Tempo wird pro Szene nur so
weit angehoben, dass der Satz in sein Zeitfenster passt (Stimme bleibt ruhig).
Ergebnis: build/bezahlen/sceneN.wav + timings.json
"""
import asyncio, json, os, ssl, subprocess
from pathlib import Path
import numpy as np
import edge_tts
import edge_tts.communicate as _ec

PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
_ca = os.environ.get("SSL_CERT_FILE") or "/root/.ccr/ca-bundle.crt"
if os.path.exists(_ca):
    _ec._SSL_CTX = ssl.create_default_context(cafile=_ca)

from script import SCENES, VOICE

OUT = Path(__file__).resolve().parents[2] / "build" / "bezahlen"
OUT.mkdir(parents=True, exist_ok=True)
SR = 48000
MAX_GAP = 0.32


def decode(path):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le",
                                   "-ac", "1", "-ar", str(SR), "-"])
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def squeeze(audio, words):
    """Kürzt Pausen zwischen Wörtern auf MAX_GAP und verschiebt die Timings."""
    pieces, out_words, cursor, shift = [], [], 0.0, 0.0
    for i, w in enumerate(words):
        if i > 0:
            gap = w["start"] - words[i - 1]["end"]
            if gap > MAX_GAP:
                cut0 = words[i - 1]["end"] + MAX_GAP / 2
                cut1 = w["start"] - MAX_GAP / 2
                pieces.append(audio[int(cursor * SR):int(cut0 * SR)])
                cursor = cut1
                shift += cut1 - cut0
        out_words.append({"text": w["text"], "start": w["start"] - shift, "end": w["end"] - shift})
    pieces.append(audio[int(cursor * SR):int((words[-1]["end"] + 0.25) * SR)])
    a = np.concatenate(pieces)
    fade = int(0.02 * SR)
    a[-fade:] *= np.linspace(1, 0, fade)
    return a, out_words


async def synth(idx, text, rate):
    comm = edge_tts.Communicate(text, VOICE, rate=f"{rate:+d}%", boundary="WordBoundary", proxy=PROXY)
    mp3 = OUT / f"scene{idx}.mp3"
    words = []
    with open(mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"text": chunk["text"], "start": chunk["offset"] / 1e7,
                              "end": (chunk["offset"] + chunk["duration"]) / 1e7})
    audio, words = squeeze(decode(mp3), words)
    return audio, words


async def main():
    res = []
    for i, s in enumerate(SCENES):
        window = s["end"] - s["start"]
        # Titel darf etwas in Szene 2 hineinlaufen (deren Satz ist kurz)
        budget = {0: window + 1.0, len(SCENES) - 1: window - 0.15}.get(i, window - 0.35)
        rate = 0
        while True:
            audio, words = await synth(i, s["text"], rate)
            if words[-1]["end"] <= budget or rate >= 35:
                break
            rate += 5
        wav = OUT / f"scene{i}.npy"
        np.save(wav, audio)
        res.append({"audio": str(wav), "duration": len(audio) / SR, "words": words, "rate": rate})
        print(i, s["key"], f"rate {rate:+d}%", round(words[-1]["end"], 2), "/", window)
    (OUT / "timings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))

asyncio.run(main())
