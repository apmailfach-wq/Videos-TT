"""Voiceover with the open-source Piper voice 'Thorsten (high)' – more emotion than edge-tts.

Every phrase is synthesized on its own so it can get its own tempo, expressiveness and
loudness (exclamations louder and faster, dramatic lines slower), plus deliberate pauses.
English words are spelled phonetically for the German voice (PRON) but shown correctly
in the captions. Word timings are distributed inside each phrase by syllables.
Writes build/motivation/sceneN.wav + timings.json (same format as tts.py).
"""
import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

from script import SCENES

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "build" / "motivation"
VOICES = ROOT / "build" / "voices"
MODEL = VOICES / "de_DE-thorsten-high.onnx"
URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx"
SR = 22050

PRON = {"Screen Time": "Skrien Taim", "Swipe": "Swaip", "Cardio": "Kardio", "TikTok": "Tick Tock",
        "App": "Äpp", "Scrolling": "Skrolling", "Glow-up": "Glou-app", "Reels": "Riels", "Like": "Laik"}

# per scene: (length_scale, noise_scale, noise_w)  – lower length = faster
STYLE = {"hook": (0.95, 0.85, 0.9), "scroll": (0.9, 0.9, 0.95), "others": (0.95, 0.8, 0.9),
         "clock": (1.0, 0.8, 0.9), "turn": (0.86, 0.95, 1.0), "steps": (0.88, 0.9, 0.95),
         "future": (0.98, 0.85, 0.9), "cta": (0.92, 0.85, 0.9)}


def ensure_model():
    VOICES.mkdir(parents=True, exist_ok=True)
    for suf in ("", ".json"):
        p = Path(str(MODEL) + suf)
        if not p.exists():
            subprocess.run(["curl", "-sSfL", "-o", str(p), URL + suf], check=True)


def syl(tok):
    t = PRON.get(tok.strip(".,!?:"), tok).lower()
    return max(1, len(re.findall(r"[aeiouäöüy]+", t)))


def phrases(text):
    """Split into phrases at punctuation; keep the punctuation for pause/emphasis decisions."""
    text = text.replace("[[", "").replace("]]", "")
    return [p.strip() for p in re.findall(r"[^.!?,]+[.!?,]*", text) if p.strip()]


def synth(text, ls, ns, nw):
    spoken = text
    for en, de in PRON.items():
        spoken = spoken.replace(en, de)
    raw = subprocess.run(["piper", "-m", str(MODEL), "--output-raw", "--length-scale", str(ls),
                          "--noise-scale", str(ns), "--noise-w-scale", str(nw), "--sentence-silence", "0"],
                         input=spoken.encode(), capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    nz = np.where(np.abs(x) > 0.01)[0]                     # trim silence
    return x[max(0, nz[0] - 200):nz[-1] + 600] if len(nz) else x


def main():
    ensure_model()
    res = []
    for i, sc in enumerate(SCENES):
        ls, ns, nw = STYLE[sc["key"]]
        audio, words, t = [], [], 0.0
        for ph in phrases(sc["text"]):
            excl = ph.endswith("!") or len(ph.split()) <= 2          # short punches = shouted
            x = synth(ph, ls * (0.93 if excl else 1.0), ns, nw)
            x = x * (1.35 if excl else 1.0)
            dur = len(x) / SR
            toks = ph.split()
            tot = sum(syl(k) for k in toks)
            tt = t
            for k in toks:
                d = dur * syl(k) / tot
                words.append({"text": k.strip(".,!?:"), "start": tt, "end": tt + d})
                tt += d
            pause = 0.42 if ph[-1] in "?!" else 0.3 if ph[-1] == "." else 0.12 if ph[-1] == "," else 0.05
            audio += [x, np.zeros(int(pause * SR), np.float32)]
            t += dur + pause
        y = np.clip(np.concatenate(audio), -1, 1)
        p = OUT / f"scene{i}.wav"
        with wave.open(str(p), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes((y * 32767).astype(np.int16).tobytes())
        res.append({"audio": str(p), "duration": len(y) / SR, "words": words})
        print(sc["key"], round(len(y) / SR, 2))
    (OUT / "timings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("total", round(sum(r["duration"] for r in res), 2))


if __name__ == "__main__":
    main()
