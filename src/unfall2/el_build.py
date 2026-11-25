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
GAP = 0.14        # pause inside the same speaker
GAP_SPK = 0.3     # clear pause when another person speaks
SPEAKER = {"rad_handy_a": "radler", "rad_er_a": "radler", "auto_rep_a": "auto", "auto_er_a": "auto",
           "pol_a": "polizei"}
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


def envelope(a):
    hop = SR // 200                      # 5 ms frames
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1))
    return rms, rms.max() * 0.015        # sensitive threshold: keeps soft R/S/T endings


def speech_bounds(a, t_first, t_last):
    """Real start/end of the sound around the recognised words (recogniser ends words too early)."""
    rms, thr = envelope(a)
    n = len(rms)
    i = max(0, int(t_first * 200))
    for _ in range(60):                  # search back up to 0.3 s for the true onset
        if i > 0 and rms[i - 1] > thr:
            i -= 1
        else:
            break
    j = min(n - 1, int(t_last * 200))
    quiet = 0
    while j < n - 1 and quiet < 24:      # until 120 ms of continuous silence
        j += 1
        quiet = quiet + 1 if rms[j] <= thr else 0
    return max(0.0, i / 200 - 0.05), min(len(a) / SR, (j - quiet) / 200 + 0.09)


def tighten(a, words):
    """Shorten only long pauses (> 0.35 s) to 0.24 s, with 15 ms crossfades - never touches sound."""
    rms, thr = envelope(a)
    n = len(rms)
    silent = rms <= thr
    keep_after, keep_before = 28, 20     # 140 ms after speech, 100 ms before next speech
    pieces, cuts, last, i = [], [], 0, 0
    while i < n:
        if silent[i]:
            j = i
            while j < n and silent[j]:
                j += 1
            if j - i > 70 and i > 0 and j < n:
                c0, c1 = (i + keep_after) * (SR // 200), (j - keep_before) * (SR // 200)
                pieces.append((last, c0))
                cuts.append((c0 / SR, (c1 - c0) / SR))
                last = c1
            i = j
        else:
            i += 1
    pieces.append((last, len(a)))
    xf = int(0.015 * SR)
    out = a[pieces[0][0]:pieces[0][1]].copy()
    for p0, p1 in pieces[1:]:
        nxt = a[p0:p1].copy()
        k = min(xf, len(out), len(nxt))
        ramp = np.linspace(0, 1, k)
        out[-k:] = out[-k:] * (1 - ramp) + nxt[:k] * ramp
        out = np.concatenate([out, nxt[k:]])

    def remap(t):
        s_ = 0.0
        for c0, d in cuts:
            if t > c0 + d:
                s_ += d
            elif t > c0:
                s_ += t - c0
        return t - s_
    for w in words:
        w["start"], w["end"] = remap(w["start"]), remap(w["end"])
    return out


def fade(seg, ms=12):
    k = min(len(seg) // 2, int(ms / 1000 * SR))
    seg[:k] *= np.linspace(0, 1, k)
    seg[-k:] *= np.linspace(1, 0, k)
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
        chunks, words, t, prev_spk = [], [], 0.0, None
        for src, arg in PARTS[sc["key"]]:
            if src == "erz":
                full, pw = erz_audio, [dict(w) for w in paras[arg]]
                spk = "erz"
            else:
                full, pw = load(src), align(arg, f"{src}.words.json")
                spk = SPEAKER[src]
            t0, t1 = speech_bounds(full, pw[0]["start"], pw[-1]["end"])
            seg = full[int(t0 * SR):int(t1 * SR)].copy()
            for w in pw:
                w["start"] = max(0.0, w["start"] - t0)
                w["end"] = min(t1 - t0, w["end"] - t0)
            pw[-1]["end"] = t1 - t0 - 0.09     # last word lasts until the sound really ends
            seg = fade(tighten(seg, pw))
            if chunks:
                g = GAP if spk == prev_spk else GAP_SPK
                chunks.append(np.zeros(int(g * SR), np.float32))
                t += g
            prev_spk = spk
            for w in pw:
                words.append(dict(text=w["text"], start=w["start"] + t, end=w["end"] + t, spk=spk))
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
