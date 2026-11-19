"""Narration with word timings for the "Level up" short (edge-tts, Florian, energetic)."""
import asyncio, json, os, ssl, subprocess
from pathlib import Path
import edge_tts, edge_tts.communicate as ec

LINES = [
    "Stell dir vor, dein Leben ist ein Game.",
    "Am Anfang bist du Level 1.",
    "Die anderen wirken stärker. Schneller. Besser.",
    "Aber sie haben auch mal bei Level 1 angefangen.",
    "Jeder Fehler? Gibt dir XP.",
    "Jedes Mal, wenn du hinfällst und wieder aufstehst: Level up!",
    "Du verlierst nicht, wenn du scheiterst.",
    "Du verlierst nur, wenn du aufhörst zu spielen.",
    "Also drück auf … Weiter.",
    "Folge für mehr Level-ups!",
]
VOICE, RATE, PITCH = "de-DE-FlorianMultilingualNeural", "+0%", "+0Hz"
# spoken spelling (so "up" sounds English) -> back to the written word for the captions
SPEAK = [("XP", "X P"), ("Level up", "Level App"), ("Level-ups", "Level Apps")]
UNSPEAK = {"App": "up", "Apps": "ups"}
OUT = Path(__file__).resolve().parents[2] / "build" / "levelup" / "voice"


import re


def spoken(text):
    for a, b in SPEAK:
        text = text.replace(a, b)
    return text


def n_tokens(text):
    return len([w for w in re.split(r"\s+", spoken(text)) if w.strip(" .,!?…:")])


async def main():
    """Speak the whole script in one take (natural flow between sentences), then cut it per line."""
    OUT.mkdir(parents=True, exist_ok=True)
    ca = "/root/.ccr/ca-bundle.crt"
    if os.path.exists(ca):
        ec._SSL_CTX = ssl.create_default_context(cafile=ca)
    full = " ".join(spoken(t) for t in LINES)
    mp3 = OUT / "full.mp3"
    comm = edge_tts.Communicate(full, VOICE, rate=RATE, pitch=PITCH, boundary="WordBoundary", proxy=os.environ.get("HTTPS_PROXY"))
    words = []
    with open(mp3, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"text": UNSPEAK.get(ch["text"].strip(" .,!?"), ch["text"]), "start": ch["offset"] / 1e7, "end": (ch["offset"] + ch["duration"]) / 1e7})
    counts = [n_tokens(t) for t in LINES]
    assert sum(counts) == len(words), (counts, sum(counts), len(words), [w["text"] for w in words])
    wav = OUT / "full.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-af", "highpass=f=70", "-ar", "48000", "-ac", "1", str(wav)], check=True)
    total = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)]))
    res, k = [], 0
    starts = []
    for c in counts:
        starts.append(words[k]["start"] - 0.08); k += c
    k = 0
    for i, (text, c) in enumerate(zip(LINES, counts)):
        a = starts[i]; b = starts[i + 1] if i + 1 < len(starts) else total
        seg = OUT / f"line{i:02d}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-af", "afade=t=out:st=%.3f:d=0.04" % max(0, b - a - 0.04), str(seg)], check=True)
        ws = [{"text": w["text"], "start": w["start"] - a, "end": w["end"] - a} for w in words[k:k + c]]
        res.append({"text": text, "file": str(seg), "dur": b - a, "words": ws, "gap": max(0.15, (b - a) - ws[-1]["end"])})
        k += c
    (OUT / "lines.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for r in res:
        print(f"{r['dur']:5.2f}  gap {r['gap']:.2f}  {r['text']}")

asyncio.run(main())
