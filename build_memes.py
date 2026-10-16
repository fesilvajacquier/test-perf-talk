"""Genera los memes de la charla a partir de las plantillas en img/templates/.

Uso: python3 build_memes.py  (escribe en img/memes/)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
SRC = ROOT / "img" / "templates"
OUT = ROOT / "img" / "memes"
IMPACT = "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def wrap(draw, text, font, max_w):
    lines = []
    for para in text.split("\n"):
        words, line = para.split(), ""
        for w in words:
            cand = f"{line} {w}".strip()
            if draw.textlength(cand, font=font) <= max_w or not line:
                line = cand
            else:
                lines.append(line)
                line = w
        lines.append(line)
    return lines


def fit(draw, text, box, font_path, max_size):
    x0, y0, x1, y1 = box
    for size in range(max_size, 10, -2):
        font = ImageFont.truetype(font_path, size)
        lines = wrap(draw, text, font, x1 - x0)
        lh = int(size * 1.15)
        if lh * len(lines) <= y1 - y0 and all(draw.textlength(l, font=font) <= x1 - x0 for l in lines):
            return font, lines, lh
    return font, lines, lh


def text_in_box(img, text, box, style="impact", max_size=90, align="center"):
    """box en fracciones (x0, y0, x1, y1) de la imagen."""
    draw = ImageDraw.Draw(img)
    W, H = img.size
    px = (int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H))
    font_path = IMPACT if style == "impact" else SANS
    font, lines, lh = fit(draw, text.upper() if style == "impact" else text, px, font_path, max_size)
    total = lh * len(lines)
    y = px[1] + (px[3] - px[1] - total) // 2
    for line in lines:
        w = draw.textlength(line, font=font)
        x = px[0] + (px[2] - px[0] - w) // 2 if align == "center" else px[0]
        if style == "impact":
            draw.text((x, y), line, font=font, fill="white", stroke_width=max(2, font.size // 12), stroke_fill="black")
        elif style == "label":
            pad = font.size // 5
            draw.rectangle((x - pad, y - pad // 2, x + w + pad, y + lh), fill="white")
            draw.text((x, y), line, font=font, fill="black")
        else:
            draw.text((x, y), line, font=font, fill="black")
        y += lh


def band_on_top(img, text, ratio=0.35):
    W, H = img.size
    band = int(W * ratio)
    out = Image.new("RGB", (W, H + band), "white")
    out.paste(img, (0, band))
    text_in_box(out, text, (0.04, 0.03 * H / (H + band), 0.96, (band - 10) / (H + band)), style="sans", max_size=110, align="left")
    return out


def load(name, width=1200):
    img = Image.open(SRC / name).convert("RGB")
    if img.width < width:
        img = img.resize((width, int(img.height * width / img.width)), Image.LANCZOS)
    return img


def skeleton():
    img = load("skeleton.jpg", 900)
    text_in_box(img, "Yo esperando bin/rails test", (0.03, 0.01, 0.97, 0.20), "impact", 110)
    text_in_box(img, "709 segundos", (0.03, 0.82, 0.97, 0.99), "impact", 130)
    return img


def saltbae():
    img = load("saltbae.jpg", 1000)
    img = img.crop((0, int(img.height * 0.08), img.width, img.height))
    text_in_box(img, "BCrypt::Engine.cost", (0.03, 0.01, 0.97, 0.14), "impact", 120)
    text_in_box(img, "= MIN_COST", (0.03, 0.85, 0.97, 0.99), "impact", 140)
    return img


def scooby():
    img = load("scooby.jpg", 1000)
    text_in_box(img, "Tests de autorización lentos", (0.02, 0.36, 0.50, 0.50), "label", 60)
    text_in_box(img, "La página de 404 que lista todas las rutas", (0.02, 0.85, 0.55, 0.99), "label", 52)
    return img


def sandwich():
    img = load("sandwich.jpg", 1200)
    text_in_box(img, "¿Qué sos?", (0.03, 0.36, 0.97, 0.49), "impact", 120)
    text_in_box(img, "Un Bullet con raise = false", (0.03, 0.85, 0.97, 0.99), "impact", 100)
    return img


def pikachu():
    img = load("pikachu.jpg", 1200)
    img = img.crop((0, int(img.height * 0.25), img.width, img.height))
    return band_on_top(
        img,
        "Postgres: menos trabajo\n"
        "Benchmark: más lento\n"
        "Yo:",
        ratio=0.36,
    )


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for fn in [skeleton, saltbae, scooby, sandwich, pikachu]:
        fn().save(OUT / f"{fn.__name__}.jpg", quality=88)
        print("ok", fn.__name__)
