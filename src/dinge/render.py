"""Render an episode of "Wenn Dinge reden könnten".

    python3 render.py schein|flasche|socke            -> ../../wenn-dinge-reden-<ep>.mp4
    python3 render.py schein preview 1 9 20 ...       -> build/dinge/<ep>/stills/*.jpg
"""
import importlib
import os
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image

import core
from core import FPS, H, W, Ctx, Timeline
from script import EPISODES

EP = TL = MOD = CHUNKS = None


def setup(name):
    global EP, TL, MOD, CHUNKS
    EP = name
    TL = Timeline(name)
    env = TL.dir / "env.npy"
    if env.exists():
        TL.env = np.load(env)
    MOD = importlib.import_module(f"ep_{name}")
    MOD.TL = TL
    CHUNKS = core.build_chunks(TL)


def frame(t):
    ctx = Ctx(TL, t)
    img = Image.new("RGB", (W, H), (0, 0, 0))
    extra = MOD.draw(img, ctx) or {}
    img = core.post(img, ctx, zoom_extra=extra.get("zoom", 0.0), shake=extra.get("shake", 0.0),
                    grade=extra.get("grade")).convert("RGBA")
    # UI layer (not affected by camera)
    core.paste(img, core.badge_tile(EPISODES[EP]["folge"]), W / 2, 235)
    if ctx.scene == "cta":
        core.draw_cta(img, ctx)
    else:
        core.draw_stamp(img, MOD.LABELS, ctx)
        core.draw_captions(img, CHUNKS, t)
    if hasattr(MOD, "hud"):
        MOD.hud(img, ctx)
    return img.convert("RGB")


def render_frame(i):
    return frame(i / FPS).tobytes()


def init(name):
    setup(name)


def main(name):
    setup(name)
    audio = TL.dir / "mix.wav"
    core.mix(TL, audio)
    np.save(TL.dir / "env.npy", TL.env)
    out = core.ROOT / os.environ.get("VIDEO_OUT", f"wenn-dinge-reden-{name}.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-maxrate", "14M", "-bufsize", "28M",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
           "-t", f"{TL.nframes / FPS:.3f}", str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=init, initargs=(name,)) as pool:
        for i, buf in enumerate(pool.imap(render_frame, range(TL.nframes), chunksize=4)):
            ff.stdin.write(buf)
            if i % 150 == 0:
                print(f"{name}: frame {i}/{TL.nframes}", flush=True)
    ff.stdin.close()
    ff.wait()
    print("done", out, f"{TL.nframes / FPS:.2f}s")


def preview(name, times):
    setup(name)
    if TL.env is None:
        v = core.voice_track(TL)
        TL.load_env(v)
        np.save(TL.dir / "env.npy", TL.env)
    d = TL.dir / "stills"
    d.mkdir(exist_ok=True)
    paths = []
    for t in times:
        p = d / f"{name}_{t:05.1f}.jpg"
        frame(t).save(p, quality=85)
        paths.append(str(p))
    # contact sheet
    ims = [Image.open(p).resize((270, 480)) for p in paths]
    cols = min(6, len(ims))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (270 * cols, 480 * rows), (0, 0, 0))
    for k, im in enumerate(ims):
        sheet.paste(im, ((k % cols) * 270, (k // cols) * 480))
    sheet.save(d / "sheet.jpg", quality=85)
    print(d / "sheet.jpg")


if __name__ == "__main__":
    name = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == "preview":
        ts = [float(x) for x in sys.argv[3:]]
        if not ts:
            setup(name)
            ts = [round(a + min(1.2, (b - a) / 2), 1) for _, a, b in TL.scenes]
        preview(name, ts)
    else:
        main(name)
