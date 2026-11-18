"""Eigene Sprachaufnahme -> Szenen-Clips + Wort-Timings (gleiches Format wie tts.py).

  python3 own_voice.py AUFNAHME.m4a                 # schreibt build/bezahlen_eigen/{sceneN.npy, timings.json}
  python3 own_voice.py --replace bar NEU.m4a        # ersetzt nur eine Szene (Schlüssel aus script.py)

Ablauf:
1. leichte Aufbereitung der ganzen Aufnahme (Trittschall-Filter, sanftes Entrauschen, Wärme, Kompression)
2. Spracherkennung mit Vosk (lokal, deutsches Modell) -> Zeit jedes gesprochenen Worts
3. Szenengrenzen: das erste Wort jeder Szene nach einer Pause von mind. 0,9 s
4. Skript-Wörter per Buchstaben-Abgleich auf die erkannten Wörter legen (Erkennungsfehler wie
   "Katze" statt "Karte" stören nicht – angezeigt wird immer der Skripttext)
5. je Szene: lange Pausen auf MAX_GAP straffen; passt die Szene dann noch nicht in ihr Zeitfenster,
   wird sie tonhöhengleich beschleunigt (höchstens MAX_TEMPO)
"""
import difflib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from script import SCENES

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "bezahlen_eigen"
MODEL = ROOT / "build" / "models" / "vosk-model-small-de-0.15"
SR = 48000
MAX_GAP = 0.30        # längste Pause innerhalb einer Szene (bewusste "//"-Pausen bleiben spürbar)
MAX_TEMPO = 1.18
LEAD, TAIL = 0.06, 0.22
SPOKEN = {"470": "vierhundertsiebzig", "2": "zwei"}

CHAIN = ("highpass=f=80,afftdn=nf=-55:nr=8,"
         "equalizer=f=160:t=q:w=1.0:g=1.5,equalizer=f=3000:t=q:w=1.4:g=1.5,"
         "equalizer=f=7000:t=q:w=2.0:g=-2,"
         "acompressor=threshold=-24dB:ratio=2.5:attack=8:release=140:makeup=2")


def run_ff(args, data=None):
    return subprocess.run(["ffmpeg", "-v", "error", *args], input=data, capture_output=True, check=True).stdout


def load(path, chain=None, sr=SR):
    raw = run_ff(["-i", str(path), *(["-af", chain] if chain else []), "-ac", "1", "-ar", str(sr),
                  "-f", "s16le", "-"])
    return np.frombuffer(raw, np.int16).astype(np.float64) / 32768


def asr(audio16):
    import vosk
    vosk.SetLogLevel(-1)
    rec = vosk.KaldiRecognizer(vosk.Model(str(MODEL)), 16000)
    rec.SetWords(True)
    pcm = (np.clip(audio16, -1, 1) * 32767).astype(np.int16).tobytes()
    words = []
    for i in range(0, len(pcm), 32000):
        if rec.AcceptWaveform(pcm[i:i + 32000]):
            words += json.loads(rec.Result()).get("result", [])
    words += json.loads(rec.FinalResult()).get("result", [])
    return words


def norm(s):
    s = "".join(ch for ch in s.lower() if ch.isalnum())
    return SPOKEN.get(s, s)


def script_tokens(text):
    return [t for t in text.split() if any(ch.isalnum() for ch in t)]


def scene_bounds(words):
    """Index des ersten erkannten Worts je Szene."""
    starts = [0]
    for sc in SCENES[1:]:
        first = norm(script_tokens(sc["text"])[0])
        best = None
        for j in range(starts[-1] + 1, len(words)):
            gap = words[j]["start"] - words[j - 1]["end"]
            sim = difflib.SequenceMatcher(None, first, words[j]["word"]).ratio()
            if gap > 0.9 and sim >= 0.5:
                best = j
                break
        if best is None:
            raise SystemExit(f"Szenenanfang nicht gefunden: {sc['key']} ({first})")
        starts.append(best)
    return starts + [len(words)]


def align_tokens(tokens, words):
    """Buchstaben-Abgleich Skript-Token <-> erkannte Wörter; liefert (start, end) je Token."""
    s_chars, s_owner = [], []
    for i, t in enumerate(tokens):
        for ch in norm(t):
            s_chars.append(ch)
            s_owner.append(i)
    a_chars, a_owner = [], []
    for i, w in enumerate(words):
        for ch in w["word"]:
            a_chars.append(ch)
            a_owner.append(i)
    sm = difflib.SequenceMatcher(None, s_chars, a_chars, autojunk=False)
    hit = {}
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            hit.setdefault(s_owner[blk.a + k], []).append(a_owner[blk.b + k])
    times = []
    for i in range(len(tokens)):
        if i in hit:
            times.append((words[min(hit[i])]["start"], words[max(hit[i])]["end"]))
        else:
            times.append(None)
    # Lücken (nicht erkannte Wörter) zwischen den Nachbarn verteilen
    for i, tm in enumerate(times):
        if tm is None:
            prev = next((times[k][1] for k in range(i - 1, -1, -1) if times[k]), words[0]["start"])
            nxt = next((times[k][0] for k in range(i + 1, len(times)) if times[k]), words[-1]["end"])
            times[i] = (prev, max(prev + 0.05, nxt))
    # Monotonie sicherstellen
    for i in range(1, len(times)):
        s, e = times[i]
        s = max(s, times[i - 1][0] + 0.02)
        times[i] = (s, max(e, s + 0.05))
    return times


def squeeze(seg, t0, toks, max_gap=MAX_GAP):
    """Pausen > max_gap kürzen. Herausgeschnitten wird das leiseste Stück der Pause (nicht der Anfang eines
    Worts oder das Ausklingen davor), mit 30-ms-Überblendung – so ruckelt nichts.
    toks: [(text, start, end)] in Sekunden relativ zur Aufnahme."""
    cuts, out, shift = [], [], 0.0
    win = int(0.01 * SR)
    for i, (txt, s, e) in enumerate(toks):
        if i:
            g0, g1 = toks[i - 1][2] + 0.06, s - 0.06      # Wortgrenzen nicht anfassen
            cut = (s - toks[i - 1][2]) - max_gap
            if cut > 0.02 and g1 - g0 > cut:
                a0, a1 = int((g0 - t0) * SR), int((g1 - t0) * SR)
                L = int(cut * SR)
                en = np.convolve(seg[a0:a1] ** 2, np.ones(win), "same")
                csum = np.concatenate([[0], np.cumsum(en)])
                k = int(np.argmin(csum[L:] - csum[:-L])) if len(en) > L else 0
                c0 = t0 + (a0 + k) / SR
                cuts.append((c0, c0 + cut))
                shift += cut + 0.03          # + Überblendung
        out.append((txt, s - shift, e - shift))
    xf = int(0.03 * SR)
    y, cursor = None, t0
    for c0, c1 in cuts + [(None, None)]:
        piece = seg[int((cursor - t0) * SR):(int((c0 - t0) * SR) if c0 is not None else None)]
        if y is None:
            y = piece
        elif len(y) > xf and len(piece) > xf:
            ph = np.linspace(0, np.pi / 2, xf)
            y = np.concatenate([y[:-xf], y[-xf:] * np.cos(ph) + piece[:xf] * np.sin(ph), piece[xf:]])
        else:
            y = np.concatenate([y, piece])
        if c1 is not None:
            cursor = c1
    # Wortzeiten: Schnitte liegen in Pausen, die Überblendung verkürzt je Schnitt um xf
    return y, [(t, s_ - t0, e_ - t0) for t, s_, e_ in out]


def tempo(y, factor):
    if abs(factor - 1) < 0.005:
        return y
    pcm = (np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes()
    raw = run_ff(["-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-", "-af", f"atempo={factor:.4f}",
                  "-f", "s16le", "-"], pcm)
    return np.frombuffer(raw, np.int16).astype(np.float64) / 32768


def process_scene(si, full, ws, prev_end_abs, gain=1.0):
    sc = SCENES[si]
    toks = script_tokens(sc["text"])
    times = align_tokens(toks, ws)
    t0, t1 = times[0][0] - LEAD, times[-1][1] + TAIL
    seg = full[int(max(0, t0) * SR):int(t1 * SR)].copy() * gain
    # Zeitfenster wie in tts.py: Titel darf 1 s in Szene 2 laufen, Schluss muss vor 60 s enden
    start_abs = max(sc["start"] + (0.05 if si == 0 else 0.15), prev_end_abs + 0.2)
    limit = {0: sc["end"] + 1.0, len(SCENES) - 1: 59.9}.get(si, sc["end"] - 0.2)
    # natürliche Pausen behalten, so weit die Zeit reicht; nur wenn nötig enger schneiden
    for mg in (0.7, 0.55, 0.45, 0.38, MAX_GAP):
        y, rel = squeeze(seg, t0, [(tok, s, e) for tok, (s, e) in zip(toks, times)], mg)
        if rel[-1][2] <= limit - start_abs:
            break
    need = rel[-1][2]
    avail = limit - start_abs
    f = 1.0 if need <= avail else min(MAX_TEMPO, need / avail)
    y = tempo(y, f)
    rel = [(t, s / f, e / f) for t, s, e in rel]
    fade = int(0.015 * SR)
    y[:fade] *= np.linspace(0, 1, fade)
    y[-fade:] *= np.linspace(1, 0, fade)
    np.save(OUT / f"scene{si}.npy", y.astype(np.float32))
    entry = {"audio": str(OUT / f"scene{si}.npy"), "duration": len(y) / SR, "own": True, "tempo": round(f, 3),
             "words": [{"text": t.strip(".,:!?–"), "start": max(0.0, s), "end": e} for t, s, e in rel]}
    end_abs = start_abs + rel[-1][2]
    print(f"{si} {sc['key']:9s} {len(ws):2d} Wörter  Pausen max {mg:.2f}s  Sprechzeit {need:4.2f}s  Tempo x{f:.2f}  "
          f"-> {start_abs:5.2f}–{end_abs:5.2f}s (Fenster {sc['start']}–{sc['end']})")
    return entry, end_abs


def speech_rms(y):
    frames = y[:len(y) // 960 * 960].reshape(-1, 960)
    r = np.sqrt((frames ** 2).mean(axis=1))
    loud = r[r > np.percentile(r, 60)]
    return float(np.sqrt((loud ** 2).mean())) if len(loud) else 1e-6


def replace(key, src):
    """Ersetzt eine einzelne Szene durch eine neue Aufnahme, Lautstärke an die alte Szene angeglichen."""
    si = [s["key"] for s in SCENES].index(key)
    res = json.loads((OUT / "timings.json").read_text())
    old = np.load(res[si]["audio"])
    full = load(src, CHAIN)
    words = asr(load(src, sr=16000))
    if not words:
        raise SystemExit("In der neuen Aufnahme wurde keine Sprache erkannt.")
    # Ende der vorherigen Szene (absolut) wie in timeline.py nachrechnen
    prev_end_abs = 0.0
    for k in range(si):
        st = max(SCENES[k]["start"] + (0.05 if k == 0 else 0.15), prev_end_abs + 0.2)
        prev_end_abs = st + res[k]["words"][-1]["end"]
    probe, _ = process_scene(si, full, words, prev_end_abs)
    gain = speech_rms(old) / speech_rms(np.load(probe["audio"]))
    entry, _ = process_scene(si, full, words, prev_end_abs, gain=gain)
    print(f"   Lautstärke angeglichen: x{gain:.2f}")
    res[si] = entry
    (OUT / "timings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))


def main(src):
    OUT.mkdir(parents=True, exist_ok=True)
    full = load(src, CHAIN)
    words = asr(load(src, sr=16000))
    (OUT / "asr.json").write_text(json.dumps(words, ensure_ascii=False, indent=0))
    bounds = scene_bounds(words)
    res = []
    prev_end_abs = 0.0
    for si, sc in enumerate(SCENES):
        entry, prev_end_abs = process_scene(si, full, words[bounds[si]:bounds[si + 1]], prev_end_abs)
        res.append(entry)
    (OUT / "timings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--replace":
        replace(sys.argv[2], sys.argv[3])      # z. B. --replace bar NEUE_AUFNAHME.m4a
    else:
        main(sys.argv[1])
