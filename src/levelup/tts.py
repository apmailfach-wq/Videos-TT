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
VOICE, RATE, PITCH = "de-DE-FlorianMultilingualNeural", "+4%", "+0Hz"
# spoken spelling (so "up" sounds English) -> back to the written word for the captions
SPEAK = [("XP", "X P"), ("Level up", "Level App"), ("Level-ups", "Level Apps")]
UNSPEAK = {"App": "up", "Apps": "ups"}
OUT = Path(__file__).resolve().parents[2] / "build" / "levelup" / "voice"


async def synth(i, text):
    mp3 = OUT / f"raw{i:02d}.mp3"
    spoken = text
    for a, b in SPEAK:
        spoken = spoken.replace(a, b)
    comm = edge_tts.Communicate(spoken, VOICE, rate=RATE, pitch=PITCH, boundary="WordBoundary", proxy=os.environ.get("HTTPS_PROXY"))
    words = []
    with open(mp3, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"text": UNSPEAK.get(ch["text"].strip(" .,!?"), ch["text"]), "start": ch["offset"] / 1e7, "end": (ch["offset"] + ch["duration"]) / 1e7})
    wav = OUT / f"line{i:02d}.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-af", "highpass=f=70,acompressor=threshold=-20dB:ratio=3:attack=5:release=120",
                    "-ar", "48000", "-ac", "1", str(wav)], check=True)
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)]))
    return {"text": text, "file": str(wav), "dur": dur, "words": words}


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ca = "/root/.ccr/ca-bundle.crt"
    if os.path.exists(ca):
        ec._SSL_CTX = ssl.create_default_context(cafile=ca)
    res = [await synth(i, t) for i, t in enumerate(LINES)]
    (OUT / "lines.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for r in res:
        print(f"{r['dur']:5.2f} {r['words'][0]['start'] if r['words'] else -1:5.2f}-{r['words'][-1]['end'] if r['words'] else -1:5.2f}  {r['text']}")

asyncio.run(main())
