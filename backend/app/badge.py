"""Badge SVG d'affiliation LECIM, généré à la volée pour chaque établissement —
destiné à être intégré sur le site propre de l'école membre."""

from . import models

LEFT_TEXT = "LECIM"
FONT_CHAR_WIDTH = 6.5
PADDING = 10
HEIGHT = 20


def _text_width(text: str) -> int:
    return round(len(text) * FONT_CHAR_WIDTH) + PADDING


def generate_membership_badge_svg(etablissement: models.Etablissement) -> str:
    right_text = "École modèle" if etablissement.is_ecole_modele else "École membre"
    right_color = "#e0a52c" if etablissement.is_ecole_modele else "#0ea5e9"

    left_w = _text_width(LEFT_TEXT)
    right_w = _text_width(right_text)
    total_w = left_w + right_w
    left_x = left_w / 2
    right_x = left_w + right_w / 2

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{HEIGHT}" role="img" aria-label="{LEFT_TEXT}: {right_text}">
<linearGradient id="s" x2="0" y2="100%">
<stop offset="0" stop-color="#fff" stop-opacity=".1"/>
<stop offset="1" stop-opacity=".1"/>
</linearGradient>
<clipPath id="r"><rect width="{total_w}" height="{HEIGHT}" rx="4" fill="#fff"/></clipPath>
<g clip-path="url(#r)">
<rect width="{left_w}" height="{HEIGHT}" fill="#0a3d63"/>
<rect x="{left_w}" width="{right_w}" height="{HEIGHT}" fill="{right_color}"/>
<rect width="{total_w}" height="{HEIGHT}" fill="url(#s)"/>
</g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,sans-serif" font-size="11">
<text x="{left_x}" y="14">{LEFT_TEXT}</text>
<text x="{right_x}" y="14">{right_text}</text>
</g>
</svg>'''
