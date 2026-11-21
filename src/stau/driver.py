"""Draws the flat cartoon driver (side view, looking left) as a transparent PNG."""
from pathlib import Path
from PIL import Image, ImageDraw

S = 4  # supersampling


def draw(path, mood="calm"):
    W, H = 600 * S, 760 * S
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = lambda *v: [int(x * S) for x in v]
    ink = (35, 30, 30, 255)
    skin = (252, 236, 222, 255)
    hair = (150, 88, 48, 255)
    shirt = (60, 110, 160, 255)
    lw = int(7 * S)
    # shoulders / torso
    d.rounded_rectangle(k(90, 560, 520, 900), radius=110 * S, fill=shirt, outline=ink, width=lw)
    # neck
    d.rectangle(k(255, 470, 345, 590), fill=skin, outline=ink, width=lw)
    # head
    d.ellipse(k(140, 110, 460, 520), fill=skin, outline=ink, width=lw)
    # ear (on the right side of the image = back of head)
    d.ellipse(k(395, 300, 455, 380), fill=skin, outline=ink, width=lw)
    # hair cap (back/top of head), drawn as polygon
    d.chord(k(135, 70, 470, 420), start=180, end=360, fill=hair, outline=ink, width=lw)
    d.polygon(k(300, 150, 470, 240, 468, 330, 410, 300, 390, 250), fill=hair)
    d.ellipse(k(150, 130, 260, 230), fill=hair)
    # face looks to the left (towards the camera side of the car = driving direction)
    if mood == "annoyed":
        # half-closed eyes
        d.line(k(190, 300, 238, 300), fill=ink, width=lw)
        d.line(k(268, 300, 316, 300), fill=ink, width=lw)
        d.pieslice(k(196, 282, 236, 322), 0, 180, fill=ink)
        d.pieslice(k(274, 282, 314, 322), 0, 180, fill=ink)
        d.line(k(220, 425, 290, 410), fill=ink, width=lw)
    else:
        d.ellipse(k(198, 280, 232, 318), fill=ink)
        d.ellipse(k(276, 280, 310, 318), fill=ink)
        d.ellipse(k(206, 286, 216, 296), fill=(255, 255, 255, 255))
        d.ellipse(k(284, 286, 294, 296), fill=(255, 255, 255, 255))
        d.arc(k(205, 360, 300, 440), start=20, end=150, fill=ink, width=lw)
    # eyebrows
    d.line(k(190, 262, 236, 255), fill=ink, width=lw)
    d.line(k(270, 255, 318, 262), fill=ink, width=lw)
    # nose
    d.arc(k(232, 320, 268, 370), start=90, end=250, fill=ink, width=int(5 * S))
    im = im.resize((W // S, H // S), Image.LANCZOS)
    im.save(path)


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[2] / "build" / "stau"
    out.mkdir(parents=True, exist_ok=True)
    draw(out / "driver.png")
    print(out / "driver.png")
