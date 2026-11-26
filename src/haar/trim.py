"""Cut trailing silence of each line so the dialogue runs tight (keeps a dramatic pause before 'r1')."""
import json, subprocess
from pathlib import Path
B = Path(__file__).resolve().parents[2] / "build" / "haar"
T = json.loads((B / "timings.json").read_text())
PAUSE = {"k3": 0.9, "r1": 0.5, "r2": 0.5, "cta": 0.6}
from script import SCENES
for s, sc in zip(T, SCENES):
    keep = s["words"][-1]["end"] + PAUSE.get(sc["key"], 0.22)
    src = Path(s["audio"]).with_suffix(".mp3")
    out = src.with_suffix(".wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-t", f"{keep:.3f}", "-ar", "48000", str(out)],
                   check=True)
    s["audio"], s["duration"] = str(out), keep
(B / "timings.json").write_text(json.dumps(T, ensure_ascii=False, indent=1))
print("total", round(sum(s["duration"] for s in T), 2))
