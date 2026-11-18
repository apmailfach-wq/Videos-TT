"""Narration for "Was wäre, wenn … Teil 1": one file per line, deep documentary voice.

Default: edge-tts de-DE-ConradNeural, slowed and pitched down (rubberband keeps it natural).
To use other recordings (e.g. ElevenLabs), drop line00.wav … line10.wav into build/waswaere/voice/
and run with --keep: only the durations are re-measured.
"""
import asyncio, json, os, ssl, subprocess, sys
from pathlib import Path

NARRATION = [
    "Was wäre, wenn der schönste Himmel deines Lebens … der letzte wäre?",
    "Ein Sonnensturm trifft die Erde. Polarlichter über Frankfurt. Die ganze Stadt ist auf der Straße.",
    "Der Sturm legt Satelliten und Stromnetze lahm.",
    "Dann … ein heller Streifen. Alle halten ihn für einen Teil der Show. Deshalb warnt dich niemand.",
    "Ein Asteroid schlägt hundert Kilometer entfernt ein. Mit mehr Energie als alle Atomwaffen der Welt.",
    "Zuerst kommt das Erdbeben.",
    "Dann … die Druckwelle.",
    "Millionen Menschen lebten hier.",
    "Der schönste Himmel deines Lebens … verschwindet.",
    "Es war das Letzte, was du gefilmt hast.",
    "Teil zwei: Die Sonne verschwindet. Folge, um es zu sehen.",
]
VOICE, RATE, PITCH = "de-DE-ConradNeural", "-8%", "-6Hz"
SHIFT = 0.89  # extra pitch shift (rubberband) for a deeper timbre
OUT = Path(__file__).resolve().parents[2] / "build" / "waswaere" / "voice"


def dur(f):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)]).decode())


async def synth(i, text):
    import edge_tts, edge_tts.communicate as ec
    ca = "/root/.ccr/ca-bundle.crt"
    if os.path.exists(ca):
        ec._SSL_CTX = ssl.create_default_context(cafile=ca)
    mp3 = OUT / f"raw{i:02d}.mp3"
    comm = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH, proxy=os.environ.get("HTTPS_PROXY"))
    await comm.save(str(mp3))
    wav = OUT / f"line{i:02d}.wav"
    # deeper, warmer: pitch down, low shelf, gentle compression, trim silence
    af = (f"rubberband=pitch={SHIFT}:formant=preserved,"
          "equalizer=f=140:t=q:w=1:g=3,equalizer=f=3500:t=q:w=1.5:g=-2,"
          "acompressor=threshold=-20dB:ratio=3:attack=5:release=120,"
          "silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-af", af, "-ar", "48000", "-ac", "1", str(wav)], check=True)


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if "--keep" not in sys.argv:
        for i, t in enumerate(NARRATION):
            await synth(i, t)
    info = [{"text": t, "file": str(OUT / f"line{i:02d}.wav"), "dur": round(dur(OUT / f"line{i:02d}.wav"), 3)} for i, t in enumerate(NARRATION)]
    (OUT / "lines.json").write_text(json.dumps(info, ensure_ascii=False, indent=1))
    for x in info:
        print(f"{x['dur']:5.2f}  {x['text']}")

asyncio.run(main())
