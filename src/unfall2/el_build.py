"""Build per-scene voice tracks + word timings from the ElevenLabs takes (narrator + character voices).

Narrator = one long take, cut into scenes using Whisper word timestamps (faster-whisper, local).
Character lines are separate takes. Output: build/unfall2_el/scene*.wav + timings.json (same format as tts.py).
"""
import difflib, json, re, subprocess, wave
from pathlib import Path
import numpy as np
from script import SCENES

ROOT = Path(__file__).resolve().parents[2]
EL = ROOT / "assets" / "unfall2_el"
OUT = ROOT / "build" / "unfall2_el"
OUT.mkdir(parents=True, exist_ok=True)
SR = 48000
TEMPO = 1.12      # slightly faster, pitch preserved
MAX_SIL = 0.18    # longest pause kept inside a part
GAP = 0.14        # pause between speakers
TAIL = 0.22       # breath after each scene

# scene -> parts: ("erz", index of narrator paragraph) or (file, text)
PARTS = {
    "hook": [("erz", 0)], "unfall": [("erz", 1)], "schaden": [("erz", 2)],
    "streit": [("rad_handy_a", "Sie zahlen mein Handy!"), ("auto_rep_a", "Und wer zahlt meine Reparatur?!"), ("erz", 3)],
    "polizei": [("pol_a", "Soso. Und wer hat angefangen?"), ("rad_er_a", "Er!"), ("auto_er_a", "Er!"), ("erz", 4)],
    "recht": [("erz", 5)], "tipps": [("erz", 6)], "fazit": [("erz", 7)], "cta": [("erz", 8)],
}
ERZ = [
    "Radfahrer gegen Auto. Es kracht! Stell dir vor, das bist du: Wer zahlt jetzt den ganzen Wahnsinn? So ist die Rechtslage.",
    "Der Autofahrer knallt mit der Stirn aufs Lenkrad. Der Radfahrer fliegt über die Motorhaube.",
    "Bilanz: Handy kaputt, Fahrrad mit Achter, Schulter verletzt. Am Auto eine Delle, plus Beule an der Stirn. Willkommen im Schadensmuseum!",
    "Dann wird gerangelt. Ganz schlechte Idee.",
    "Beide zeigen aufeinander. Der Beamte braucht jetzt Urlaub.",
    "Jetzt wird's spannend: Nach Paragraf 7 Straßenverkehrsgesetz haftet der Halter des Autos grundsätzlich, auch ohne Verschulden. Aber: Fährt der Radfahrer zum Beispiel bei Rot, kann er einen großen Teil selbst tragen und bleibt womöglich auf Handy und Fahrrad sitzen. Schmerzensgeld gibt's unter Umständen für beide. Und wer zuschlägt, riskiert eine Anzeige wegen Körperverletzung.",
    "Drei Tipps: Polizei rufen, Fotos und Zeugen sichern, Verletzungen beim Arzt dokumentieren.",
    "Ein kleiner Unfall: fünf Schäden, drei Streitparteien und mehr Papierkram als bei einer Hochzeit.",
    "Autofahrer oder Radfahrer: Wer ist schuld? Schreib's in die Kommentare und speicher das Video!",
]


def norm(w):
    w = w.lower().strip(".,:;!?\"'„“")
    return {"§": "paragraf", "7": "sieben", "soso": "so"}.get(w, w)


def load(name):
    b = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(EL / f"{name}.mp3"), "-af", f"atempo={TEMPO}",
                                 "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"])
    return np.frombuffer(b, np.float32).copy()


def align(script_text, wjson):
    """Script tokens get the times of the matching whisper words (interpolated when unmatched)."""
    toks = script_text.split()
    ww = json.load(open(EL / wjson))
    a = [norm(t) for t in toks]
    b = [norm(w["text"]) for w in ww]
    times = [None] * len(toks)
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            w = ww[blk.b + k]
            times[blk.a + k] = (w["start"] / TEMPO, w["end"] / TEMPO)
    # interpolate gaps
    for i in range(len(toks)):
        if times[i] is None:
            prev = next((times[j] for j in range(i - 1, -1, -1) if times[j]), (0.0, 0.0))
            nxt = next((times[j] for j in range(i + 1, len(toks)) if times[j]), None)
            st = prev[1]
            en = nxt[0] if nxt else st + 0.3
            times[i] = (st, st + max(0.12, (en - st)))
    return [dict(text=t.strip(".,:!?\"„“"), start=s, end=e) for t, (s, e) in zip(toks, times)]


def tighten(a, words):
    hop = SR // 100
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1))
    silent = rms < max(0.004, rms.max() * 0.03)
    keep = np.ones(n, bool)
    cuts, i, lim = [], 0, int(MAX_SIL * 100)
    while i < n:
        if silent[i]:
            j = i
            while j < n and silent[j]:
                j += 1
            if j - i > lim and i > 0 and j < n:
                d0, d1 = i + lim // 2, j - (lim - lim // 2)
                keep[d0:d1] = False
                cuts.append((d0 / 100, (d1 - d0) / 100))
            i = j
        else:
            i += 1
    out = np.concatenate([a[:n * hop].reshape(n, hop)[keep].reshape(-1), a[n * hop:]])

    def remap(t):
        s = 0.0
        for c0, d in cuts:
            if t > c0 + d:
                s += d
            elif t > c0:
                s += t - c0
        return t - s
    for w in words:
        w["start"], w["end"] = remap(w["start"]), remap(w["end"])
    return out


def trim(a, words, pre=0.04, post=0.12):
    """Cut leading/trailing silence around the spoken words."""
    t0 = max(0.0, words[0]["start"] - pre)
    t1 = min(len(a) / SR, words[-1]["end"] + post)
    seg = a[int(t0 * SR):int(t1 * SR)]
    for w in words:
        w["start"] -= t0
        w["end"] -= t0
    return seg


def main():
    erz_audio = load("erz_b")
    erz_words = align(" ".join(ERZ), "erz_b.words.json")
    # split narrator words per paragraph
    paras, k = [], 0
    for p in ERZ:
        n = len(p.split())
        paras.append(erz_words[k:k + n])
        k += n
    res = []
    for si, sc in enumerate(SCENES):
        chunks, words, t = [], [], 0.0
        for src, arg in PARTS[sc["key"]]:
            if src == "erz":
                pw = [dict(w) for w in paras[arg]]
                t0 = max(0.0, pw[0]["start"] - 0.06)
                t1 = pw[-1]["end"] + 0.15
                seg = erz_audio[int(t0 * SR):int(t1 * SR)]
                for w in pw:
                    w["start"] -= t0
                    w["end"] -= t0
            else:
                seg = load(src)
                pw = align(arg, f"{src}.words.json")
                seg = trim(seg, pw)
            seg = tighten(seg, pw)
            if chunks:
                chunks.append(np.zeros(int(GAP * SR), np.float32))
                t += GAP
            for w in pw:
                words.append(dict(text=w["text"], start=w["start"] + t, end=w["end"] + t))
            chunks.append(seg)
            t += len(seg) / SR
        chunks.append(np.zeros(int(TAIL * SR), np.float32))
        audio = np.concatenate(chunks)
        # per-scene loudness match (RMS of voiced part)
        rms = np.sqrt(np.mean(audio[np.abs(audio) > 0.01] ** 2))
        audio = np.clip(audio * (0.12 / max(rms, 1e-4)), -1, 1)
        wav = OUT / f"scene{si}.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((audio * 32000).astype(np.int16).tobytes())
        res.append(dict(audio=str(wav), duration=len(audio) / SR, words=words))
        print(si, sc["key"], round(len(audio) / SR, 2), " ".join(w["text"] for w in words)[:90])
    (OUT / "timings.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("total", round(sum(r["duration"] for r in res), 2))


if __name__ == "__main__":
    main()
