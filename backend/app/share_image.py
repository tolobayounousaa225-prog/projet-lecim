"""Génère l'image de partage (Open Graph) d'une actualité — utilisée par les
aperçus de lien sur WhatsApp/Facebook/Twitter quand un article est partagé.

Le rendu utilise la police intégrée à Pillow (portable, aucun fichier de
police à embarquer dans le dépôt) qui ne couvre que l'ASCII de base : les
accents et tirets typographiques du titre sont donc translittérés pour cette
image uniquement — le contenu réel du site n'est jamais modifié."""

import unicodedata
from io import BytesIO
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630
GREEN_DARK = (10, 61, 99)
GREEN = (4, 56, 114)
GOLD = (224, 165, 44)
WHITE = (255, 255, 255)

LOGO_PATH = Path(__file__).resolve().parent / "static" / "img" / "logo.jpg"


def _ascii_ize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    return (
        stripped.replace("—", "-")
        .replace("–", "-")
        .replace("’", "'")
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def _vertical_gradient(width: int, height: int, top: tuple, bottom: tuple) -> Image.Image:
    base = Image.new("RGB", (1, height))
    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        base.putpixel((0, y), color)
    return base.resize((width, height))


def generate_news_share_image(title: str, published_at_label: str) -> bytes:
    img = _vertical_gradient(WIDTH, HEIGHT, GREEN_DARK, GREEN)
    draw = ImageDraw.Draw(img)

    # Logo circulaire en haut à gauche
    try:
        logo = Image.open(LOGO_PATH).convert("RGB").resize((88, 88))
        mask = Image.new("L", (88, 88), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 88, 88), fill=255)
        img.paste(logo, (60, 56), mask)
    except Exception:
        pass

    font_brand = ImageFont.load_default(size=34)
    font_title = ImageFont.load_default(size=54)
    font_meta = ImageFont.load_default(size=26)

    draw.text((166, 78), "LECIM", font=font_brand, fill=WHITE)
    draw.text((166, 118), "ACTUALITE", font=font_meta, fill=GOLD)

    # Titre, réparti sur plusieurs lignes centrées verticalement
    safe_title = _ascii_ize(title).upper()
    lines = wrap(safe_title, width=28)[:4]
    line_height = 68
    block_height = len(lines) * line_height
    start_y = (HEIGHT - block_height) // 2 + 20
    for i, line in enumerate(lines):
        draw.text((60, start_y + i * line_height), line, font=font_title, fill=WHITE)

    # Barre d'accent dorée + date en pied d'image
    draw.rectangle((0, HEIGHT - 8, WIDTH, HEIGHT), fill=GOLD)
    if published_at_label:
        draw.text((60, HEIGHT - 60), _ascii_ize(published_at_label), font=font_meta, fill=(255, 255, 255, 200))

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
