"""Cover for cent-video.mp4: the coffee price-tag hook at full impact."""
import render as R

R.init()
im = R.hook_scene(R.T_ROLL1 + 0.8).convert("RGB")
out = R.ROOT / "cent-video-cover.png"
im.save(out)
print(out)
