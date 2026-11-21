"""Upscale rendered frames to 1080x1920, add TikTok-style overlays, mux voice + ambience.

usage: python3 compose.py [preview t1 t2 ...]
"""
import json, math, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from script import SCENES

FPS = 30
W, H = 1080, 1920
ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build" / "stau"
FR = BUILD / "frames"
OUT = ROOT / "stau-video.mp4"

F_SUB = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
F_BOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
font = lambda p, s: ImageFont.truetype(p, s)

YELLOW = (255, 214, 10)
HILITE = {"stau", "grund", "stärker.", "stärker", "nichts.", "nichts", "abstand", "tacho,", "tacho",
          "reißverschluss.", "reißverschluss", "ende", "weiterrollen,", "weiterrollen", "bremsen.",
          "drängler?", "kommentare!", "alles.", "alles", "abschwächen."}

TIPS = {"gap": ("TIPP 1", "ABSTAND HALTEN"), "roll": ("TIPP 2", "ROLLEN STATT BREMSEN"),
        "zipper": ("TIPP 3", "REISSVERSCHLUSS")}

tim = json.loads((BUILD / "timings.json").read_text())


def punctuate(words, text):
    """edge-tts word boundaries carry no punctuation – take it from the script text."""
    import re
    toks = [t for t in re.split(r"\s+", text.replace("–", " ")) if t.strip()]
    out, j = [], 0
    for w in words:
        w = dict(w)
        core = w["text"].strip(".,:;!?")
        for k in range(j, min(j + 4, len(toks))):
            if toks[k].strip(".,:;!?\"'").lower() == core.lower():
                w["text"] = core + re.sub(r"^.*?([.,:;!?]*)$", r"\1", toks[k])
                j = k + 1
                break
        out.append(w)
    return out


def scene_table():
    rows, start = [], 0
    for i, s in enumerate(SCENES):
        pad = 1.6 if i == len(SCENES) - 1 else 0.3
        n = int(round((tim[i]["duration"] + pad) * FPS))
        rows.append({"shot": s["shot"], "start": start, "n": n, "words": punctuate(tim[i]["words"], s["text"]),
                     "audio": tim[i]["audio"], "dur": tim[i]["duration"]})
        start += n
    return rows


ROWS = scene_table()
TOTAL = sum(r["n"] for r in ROWS)


def chunks(words):
    """Group words into 1–2 word captions like the reference (short words pair up)."""
    out, i = [], 0
    while i < len(words):
        w = words[i]
        if i + 1 < len(words) and len(w["text"]) + len(words[i + 1]["text"]) <= 11 \
                and not w["text"].endswith((".", ",", ":", "?", "!")):
            out.append({"text": w["text"] + " " + words[i + 1]["text"], "start": w["start"]})
            i += 2
        else:
            out.append({"text": w["text"], "start": w["start"]})
            i += 1
    return out


def text_stroke(d, xy, txt, f, fill, stroke=9, anchor="mm"):
    d.text(xy, txt, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=(0, 0, 0))


def draw_caption(img, txt, age, ypos=0.50):
    pop = 1.0 + 0.18 * max(0.0, 1 - age / 0.12)
    size = int(84 * pop)
    f = font(F_SUB, size)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    words = txt.split(" ")
    widths = [d.textlength(w + " ", font=f) for w in words]
    total = sum(widths) - d.textlength(" ", font=f)
    x = W / 2 - total / 2
    y = int(H * ypos)
    # soft shadow
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    for w, wd in zip(words, widths):
        sd.text((x + 4, y + 8), w, font=f, fill=(0, 0, 0, 160), anchor="lm", stroke_width=10, stroke_fill=(0, 0, 0, 160))
        col = YELLOW if w.lower().strip("–.,:;!?") in HILITE else (255, 255, 255)
        d.text((x, y), w, font=f, fill=col, anchor="lm", stroke_width=10, stroke_fill=(0, 0, 0))
        x += wd
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    img.alpha_composite(layer)


def pill(img, cx, cy, txt, f, bg, fg, pad=(30, 16), alpha=255, radius=22):
    d = ImageDraw.Draw(img)
    bb = d.textbbox((0, 0), txt, font=f, anchor="lt")
    w, h = bb[2] - bb[0] + 2 * pad[0], bb[3] - bb[1] + 2 * pad[1]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    d.rounded_rectangle((x0 + 6, y0 + 8, x0 + w + 6, y0 + h + 8), radius, fill=(0, 0, 0, int(alpha * 0.45)))
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius, fill=(*bg, alpha))
    d.text((x0 + pad[0] - bb[0], y0 + pad[1] - bb[1]), txt, font=f, fill=(*fg, alpha), anchor="lt")
    return (x0, y0, x0 + w, y0 + h)


def ease_out(x):
    x = min(max(x, 0), 1)
    return 1 - (1 - x) ** 3


def overlays(img, row, lf, t):
    shot = row["shot"]
    d = ImageDraw.Draw(img)
    # --- hook title (first seconds)
    if shot == "hook":
        a = ease_out(t / 0.25)
        y = 330 - 40 * (1 - a)
        pill(img, W / 2, y, "ACHTUNG STAU!", font(F_SUB, 84), (225, 30, 30), (255, 255, 255), alpha=int(255 * a))
    # --- tip header
    if shot in TIPS:
        num, title = TIPS[shot]
        a = ease_out(t / 0.3)
        y = 300 - 60 * (1 - a)
        pill(img, W / 2, y, num, font(F_SUB, 46), YELLOW, (0, 0, 0), alpha=int(255 * a))
        pill(img, W / 2, y + 100, title, font(F_SUB, 62), (255, 255, 255), (0, 0, 0), alpha=int(255 * a))
    # --- gap: 50 m label on the carpet
    if shot == "gap":
        meta = json.loads((FR / "gap" / "meta.json").read_text())
        m = meta.get(str(lf))
        a = ease_out((t - 2.4) / 0.3)
        if m and a > 0:
            x, y = m["label"][0] * W, m["label"][1] * H
            pill(img, x, y - 40, "50 m", font(F_SUB, 70), (20, 200, 80), (255, 255, 255), alpha=int(255 * a))
            pill(img, W / 2, 1500, "100 km/h  →  50 m Abstand", font(F_BOLD, 44), (0, 0, 0), (255, 255, 255),
                 alpha=int(220 * a))
    # --- zipper: marker at merge point
    if shot == "zipper":
        meta = json.loads((FR / "zipper" / "meta.json").read_text())
        m = meta.get(str(lf))
        a = ease_out((t - 2.6) / 0.3)
        if m and a > 0 and 0 < m["merge"][1] < 1:
            x, y = m["merge"][0] * W, m["merge"][1] * H
            bob = 10 * math.sin(t * 6)
            pill(img, x, y - 170 + bob, "HIER EINFÄDELN", font(F_SUB, 46), YELLOW, (0, 0, 0), alpha=int(255 * a))
            ax, ay = x, y - 115 + bob
            d.polygon([(ax - 26, ay), (ax + 26, ay), (ax, ay + 40)], fill=(*YELLOW, int(255 * a)),
                      outline=(0, 0, 0, int(255 * a)), width=4)
    # --- outro CTA after the voice ends
    if shot == "outro":
        a = ease_out((t - (row["dur"] - 3.2)) / 0.35)
        if a > 0:
            pill(img, W / 2, 330 - 40 * (1 - a), "UND DU?", font(F_SUB, 70), (225, 30, 30), (255, 255, 255),
                 alpha=int(255 * a))


def caption_at(row, t):
    cs = chunks(row["words"])
    cur = None
    for c in cs:
        if c["start"] <= t:
            cur = c
    if cur is None:
        return None, 0
    # hide caption in pauses longer than 0.7 s after the last word
    last = row["words"][-1]
    if t > last["end"] + 0.35:
        return None, 0
    return cur["text"], t - cur["start"]


def frame_image(gf):
    for row in ROWS:
        if gf < row["start"] + row["n"]:
            break
    lf = gf - row["start"]
    t = lf / FPS
    src = FR / row["shot"] / f"{lf:04d}.png"
    base = Image.open(src).convert("RGB").resize((W, H), Image.LANCZOS)
    base = base.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    # punch-in zoom on every cut
    z = 1.0 + 0.06 * (1 - ease_out(lf / 8))
    if z > 1.001:
        cw, ch = int(W / z), int(H / z)
        base = base.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((W, H), Image.BILINEAR)
    img = base.convert("RGBA")
    overlays(img, row, lf, t)
    txt, age = caption_at(row, t)
    if txt:
        draw_caption(img, txt, age, {"roll": 0.74, "gap": 0.36}.get(row["shot"], 0.50))
    return img.convert("RGB")


def build_audio():
    parts, filt = [], []
    for i, r in enumerate(ROWS):
        parts += ["-i", r["audio"]]
        filt.append(f"[{i}:a]apad=whole_dur={r['n'] / FPS:.4f},atrim=0:{r['n'] / FPS:.4f}[a{i}]")
    n = len(ROWS)
    total = TOTAL / FPS
    filt.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1,volume=1.6[voice]")
    # low motorway rumble as ambience
    filt.append(f"anoisesrc=color=brown:amplitude=0.5:duration={total:.3f},lowpass=f=400,volume=0.10[amb]")
    filt.append("[voice][amb]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[out]")
    wav = BUILD / "mix.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *parts, "-filter_complex", ";".join(filt),
                    "-map", "[out]", "-ar", "48000", str(wav)], check=True)
    return wav


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        out = BUILD / "stills"; out.mkdir(exist_ok=True)
        for s in sys.argv[2:]:
            gf = int(float(s) * FPS)
            frame_image(gf).save(out / f"still_{s}.png")
        return
    wav = build_audio()
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(wav),
                           "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(OUT)],
                          stdin=subprocess.PIPE)
    for gf in range(TOTAL):
        ff.stdin.write(frame_image(gf).tobytes())
        if gf % 150 == 0:
            print("frame", gf, "/", TOTAL, flush=True)
    ff.stdin.close()
    ff.wait()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
