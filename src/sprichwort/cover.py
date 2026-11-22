"""Cover image for an episode.  Usage: python3 cover.py sport "SPORT IST *MORD?*" "Wir haben's gecheckt" """
import math
import sys
from PIL import Image, ImageDraw
import render as R

head, sub = sys.argv[2], sys.argv[3]
R.init()
im = R.BG.copy()
d = ImageDraw.Draw(im)
# pill
fp = R.font(R.F_HEAD, 34)
pw = fp.getlength("SPRICHWORT-CHECK #%d" % R.E["number"]) + 70
d.rounded_rectangle([540 - pw / 2, 150, 540 + pw / 2, 214], radius=32, fill=R.INK)
d.text((540, 183), "SPRICHWORT-CHECK #%d" % R.E["number"], font=fp, fill=R.YELLOW, anchor="mm")
# huge headline with marker
size, lines = R.rich_lines(head, R.F_HEAD, 980, range(150, 60, -4), max_lines=2)
f = R.font(R.F_HEAD, size)
y = 260 + size
for ln in lines:
    sp = f.getlength(" ")
    full = sum(f.getlength(w) for w, _ in ln) + sp * (len(ln) - 1)
    x = 540 - full / 2
    for w, hl in ln:
        ww = f.getlength(w)
        if hl:
            d.rounded_rectangle([x - 12, y - size * 0.86, x + ww + 12, y + size * 0.16], radius=18, fill=(255, 220, 60))
        d.text((x, y), w, font=f, fill=R.INK, anchor="ls", stroke_width=0)
        x += ww + sp
    y += size * 1.12
# plaque
pl = R.plaque_img(R.E["saying"] + ".").rotate(-4, resample=Image.BICUBIC, expand=True)
pl = pl.resize((int(pl.width * 0.82), int(pl.height * 0.82)), Image.LANCZOS)
im.alpha_composite(pl, (int(540 - pl.width / 2), int(y - 40)))
# emojis + stamp
R.paste_c(im, R.emoji(sys.argv[4] if len(sys.argv) > 4 else "🛋️", 170), 170, y + pl.height - 60, 1, 10)
R.paste_c(im, R.emoji(sys.argv[5] if len(sys.argv) > 5 else "🏃", 170), 910, y + pl.height - 80, 1, -10)
R.paste_c(im, R.emoji("❓", 150), 900, y + 60, 1, 14)
R.paste_c(im, R.stamp_img(sub.upper(), R.RED, 48), 540, y + pl.height + 40, 1, -5)
out = R.ROOT / R.E["out"].replace(".mp4", "-cover.png")
im.convert("RGB").save(out)
print(out)
