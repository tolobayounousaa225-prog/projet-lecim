"""Génération du PDF imprimable de la carte de membre (format carte CR80, 85.6 x 54 mm)."""

import io
from pathlib import Path

import qrcode
from fpdf import FPDF
from PIL import Image, ImageDraw

from .config import settings

GREEN_DARK = (11, 61, 46)
GREEN = (15, 122, 76)
GOLD = (224, 165, 44)
CREAM = (248, 246, 238)
BADGE_BLUE = (8, 44, 89)

CARD_W = 85.6
CARD_H = 54.0

# La police standard de FPDF ne couvre que le Latin-1 : certains caractères
# couramment produits par des f-strings (tiret cadratin de poste_label pour
# les comptes delegation, guillemets typographiques...) font planter la
# generation si on ne les ramene pas d'abord vers leur equivalent Latin-1.
_UNICODE_FALLBACKS = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...",
}


def _safe_text(value: str) -> str:
    for char, replacement in _UNICODE_FALLBACKS.items():
        value = value.replace(char, replacement)
    return value


LOGO_PATH = Path(__file__).resolve().parent / "static" / "img" / "logo.jpg"
MEMBRE_TEMPLATE_PATH = Path(__file__).resolve().parent / "static" / "img" / "carte_membre_template.png"


def _circular_photo_png(photo_bytes: bytes, diameter_px: int = 400) -> bytes:
    """Recadre une photo en cercle (fond transparent) pour l'incruster sur le
    modèle de carte approuvé — fpdf2 gère nativement la transparence PNG."""
    img = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    side = min(img.size)
    left = (img.width - side) // 2
    top = (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((diameter_px, diameter_px), Image.LANCZOS)

    mask = Image.new("L", (diameter_px, diameter_px), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter_px, diameter_px), fill=255)

    out = Image.new("RGBA", (diameter_px, diameter_px))
    out.paste(img, (0, 0), mask)
    buffer = io.BytesIO()
    out.save(buffer, format="PNG")
    return buffer.getvalue()


def _add_recto(pdf: FPDF, carte, photo_bytes: bytes | None) -> None:
    """Recto basé sur le modèle de carte approuvé (image de fond fixe) : seuls
    le badge de catégorie, la photo, le nom/la fonction et le QR de vérification
    sont superposés — le reste du visuel (en-tête, armoiries, filigrane) vient
    tel quel de l'image approuvée, jamais redessiné. Réservé aux comptes du
    Bureau Exécutif National — les présidents de délégation ont leur propre
    modèle entièrement dessiné (voir _add_recto_delegation)."""
    pdf.add_page()

    if MEMBRE_TEMPLATE_PATH.exists():
        # Ajustement "cover" repris de l'outil de référence : l'image source n'a
        # pas exactement les proportions d'une carte CR80, donc légèrement
        # surdimensionnée et décalée pour remplir le cadre sans déformation.
        pdf.image(str(MEMBRE_TEMPLATE_PATH), x=-3.59, y=-4.47, w=92.26, h=62.78)
    else:
        pdf.set_fill_color(*CREAM)
        pdf.rect(0, 0, CARD_W, CARD_H, style="F")

    badge_text = "ADMINISTRATION NATIONALE - CARTE OFFICIELLE"
    badge_x, badge_y, badge_w, badge_h = 14.12, 12.69, 58.21, 3.89
    pdf.set_fill_color(*BADGE_BLUE)
    pdf.rect(badge_x, badge_y, badge_w, badge_h, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 6.2)
    pdf.set_xy(badge_x, badge_y + 0.9)
    pdf.cell(badge_w, badge_h - 1, badge_text, align="C")

    photo_x, photo_y, photo_d = 5.56, 22.79, 19.0
    photo_cx, photo_cy, photo_r = photo_x + photo_d / 2, photo_y + photo_d / 2, photo_d / 2
    pdf.set_fill_color(*GREEN)
    pdf.ellipse(photo_cx - photo_r - 1.2, photo_cy - photo_r - 1.2, (photo_r + 1.2) * 2, (photo_r + 1.2) * 2, style="F")
    pdf.set_fill_color(255, 255, 255)
    pdf.ellipse(photo_cx - photo_r - 0.5, photo_cy - photo_r - 0.5, (photo_r + 0.5) * 2, (photo_r + 0.5) * 2, style="F")
    if photo_bytes:
        pdf.image(io.BytesIO(_circular_photo_png(photo_bytes)), x=photo_x, y=photo_y, w=photo_d, h=photo_d)
    else:
        pdf.set_fill_color(230, 232, 229)
        pdf.ellipse(photo_x, photo_y, photo_d, photo_d, style="F")
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(*GREEN)
        pdf.set_xy(photo_x, photo_cy - 2)
        pdf.cell(photo_d, 4, "PHOTO", align="C")

    info_x, info_y, info_w = 25.85, 23.5, 37.66
    pdf.set_text_color(*GREEN)
    pdf.set_font("Helvetica", "", 5.8)
    pdf.set_xy(info_x, info_y)
    pdf.cell(info_w, 3, "Nom complet", align="L")
    pdf.set_text_color(10, 10, 10)
    pdf.set_font("Helvetica", "B", 8.2)
    pdf.set_xy(info_x, info_y + 3)
    pdf.multi_cell(info_w, 3.6, _safe_text(carte.full_name_snapshot), align="L")
    pdf.set_text_color(*GREEN)
    pdf.set_font("Helvetica", "", 5.8)
    pdf.set_xy(info_x, info_y + 9.5)
    pdf.cell(info_w, 3, "Fonction", align="L")
    pdf.set_text_color(10, 10, 10)
    fonction_text = _safe_text(carte.user.poste_label)
    fonction_size = 6.8
    pdf.set_font("Helvetica", "B", fonction_size)
    while fonction_size > 4.5 and pdf.get_string_width(fonction_text) > info_w:
        fonction_size -= 0.3
        pdf.set_font("Helvetica", "B", fonction_size)
    pdf.set_xy(info_x, info_y + 12.3)
    pdf.cell(info_w, 3.4, fonction_text, align="L")

    # QR de verification (remplace le code-barres decoratif du modele : un
    # visuel non fonctionnel n'aurait aucune valeur de securite)
    qr_payload = f"{settings.public_base_url}/verify/{carte.numero_carte or ''}"
    qr_img = qrcode.make(qr_payload, border=1)
    qr_size = 11.0
    qr_x = CARD_W - 3.5 - qr_size
    qr_y = CARD_H - 3.5 - qr_size
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(qr_x - 0.8, qr_y - 0.8, qr_size + 1.6, qr_size + 1.6, style="F", round_corners=True, corner_radius=1)
    pdf.image(qr_img.get_image() if hasattr(qr_img, "get_image") else qr_img, x=qr_x, y=qr_y, w=qr_size, h=qr_size)

    pdf.set_font("Helvetica", "B", 6.2)
    pdf.set_text_color(*GREEN)
    pdf.set_xy(3.5, CARD_H - 9)
    pdf.cell(30, 3, f"N. {carte.numero_carte or '-'}", align="L")
    pdf.set_font("Helvetica", "", 5.3)
    pdf.set_text_color(80, 80, 80)
    pdf.set_xy(3.5, CARD_H - 6)
    validite = carte.date_validite.strftime("%d/%m/%Y") if carte.date_validite else "-"
    pdf.cell(30, 3, f"Valable jusqu'au {validite}", align="L")


def _add_verso(pdf: FPDF, carte) -> None:
    """Verso volontairement sobre : fond blanc (économie d'encre à
    l'impression), petites touches de vert/bleu pour rester cohérent avec
    le recto, une seule phrase d'information plutôt qu'un paragraphe."""
    pdf.add_page()

    # Coins arrondis (rayon standard d'une carte CR80, 3.18 mm) pour retrouver
    # la meme silhouette que le recto, dont l'image de fond est deja arrondie.
    corner_r = 3.18
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, CARD_W, CARD_H, style="F", round_corners=True, corner_radius=corner_r)

    pdf.set_fill_color(*GREEN)
    pdf.rect(corner_r, 0, CARD_W - 2 * corner_r, 1.2, style="F")

    pdf.set_text_color(*BADGE_BLUE)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_xy(5, 5)
    pdf.cell(CARD_W - 10, 4, "LECIM", align="L")

    pdf.set_text_color(70, 70, 70)
    pdf.set_font("Helvetica", "", 6.3)
    pdf.set_xy(5, 10.5)
    pdf.multi_cell(
        CARD_W - 10, 3.3,
        _safe_text(
            "Cette carte atteste la qualité de membre du Bureau Exécutif National de son "
            "titulaire et demeure la propriété de la LECIM. Merci de la retourner au "
            "secrétariat en cas de découverte."
        ),
        align="L",
    )

    # Volontairement rien d'autre d'identifiant ici (ni N. CNI, ni contact
    # d'urgence, ni numero de carte) : le verso doit rester un texte generique,
    # identique sur toutes les cartes. Les informations propres au titulaire
    # (nom, fonction, numero, QR) restent uniquement au recto.

    # Ligne de signature
    sig_y = CARD_H - 11
    pdf.set_draw_color(180, 180, 180)
    pdf.line(CARD_W - 36, sig_y, CARD_W - 5, sig_y)
    pdf.set_font("Helvetica", "", 5.2)
    pdf.set_text_color(120, 120, 120)
    pdf.set_xy(CARD_W - 36, sig_y + 1)
    pdf.cell(31, 3, "Signature", align="C")

    pdf.set_text_color(130, 130, 130)
    pdf.set_font("Helvetica", "", 5.3)
    pdf.set_xy(5, CARD_H - 7)
    pdf.cell(40, 3, "lecimnational@gmail.com", align="L")

    pdf.set_fill_color(*GREEN)
    pdf.rect(corner_r, CARD_H - 1.2, CARD_W - 2 * corner_r, 1.2, style="F")


def _add_recto_delegation(pdf: FPDF, carte, photo_bytes: bytes | None) -> None:
    """Recto des présidents de délégation régionale — modèle propre (gabarit
    fourni par l'utilisateur, "Bureau Local"), entièrement redessiné plutôt que
    superposé sur l'image de fond nationale : liseré or/vert, bandeau de
    catégorie, photo encadrée, nom/fonction/délégation, naissance, QR de
    vérification. Version française uniquement (le modèle d'origine est
    bilingue FR/AR, non reproduit ici faute de prise en charge de l'arabe
    dans le pipeline PDF actuel)."""
    pdf.add_page()
    corner_r = 3.18

    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, CARD_W, CARD_H, style="F", round_corners=True, corner_radius=corner_r)

    # Liseré décoratif gauche (or puis vert) — version simplifiée, non diagonale,
    # du bandeau du modèle approuvé.
    pdf.set_fill_color(*GOLD)
    pdf.rect(0, 0, 2.2, CARD_H, style="F")
    pdf.set_fill_color(*GREEN)
    pdf.rect(2.2, 0, 2.2, CARD_H, style="F")

    header_x = 8.5
    if LOGO_PATH.exists():
        pdf.image(str(LOGO_PATH), x=header_x, y=2.2, w=8, h=8)
        header_x += 9.5
    pdf.set_text_color(*GREEN_DARK)
    pdf.set_font("Helvetica", "B", 5.4)
    pdf.set_xy(header_x, 2.2)
    pdf.cell(CARD_W - header_x - 3, 3, "LECIM", align="L")
    pdf.set_font("Helvetica", "", 4.1)
    pdf.set_text_color(70, 85, 78)
    pdf.set_xy(header_x, 5.3)
    pdf.multi_cell(
        CARD_W - header_x - 3, 2.6,
        "Ligue des Etablissements Confessionnels Islamiques et Madrassas",
        align="L",
    )

    ribbon_y = 12.2
    pdf.set_fill_color(*GREEN)
    pdf.rect(2.2, ribbon_y, CARD_W - 2.2, 3.7, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 5.8)
    pdf.set_xy(5.5, ribbon_y + 0.7)
    pdf.cell(CARD_W - 9, 2.6, "BUREAU LOCAL - CARTE OFFICIELLE", align="L")

    photo_x, photo_y, photo_w, photo_h = 6, 18, 17, 20
    pdf.set_draw_color(*GREEN)
    pdf.set_fill_color(240, 242, 239)
    pdf.rect(photo_x, photo_y, photo_w, photo_h, style="DF", round_corners=True, corner_radius=1.2)
    if photo_bytes:
        img = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
        side = min(img.size)
        left, top = (img.width - side) // 2, (img.height - side) // 2
        img = img.crop((left, top, left + side, top + side))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pdf.image(io.BytesIO(buf.getvalue()), x=photo_x + 0.8, y=photo_y + 0.8, w=photo_w - 1.6, h=photo_h - 1.6)
    else:
        pdf.set_font("Helvetica", "", 5.5)
        pdf.set_text_color(*GREEN)
        pdf.set_xy(photo_x, photo_y + photo_h / 2 - 2)
        pdf.cell(photo_w, 4, "PHOTO", align="C")

    info_x, info_w = 26, CARD_W - 26 - 4
    pdf.set_text_color(*GREEN)
    pdf.set_font("Helvetica", "", 4.6)
    pdf.set_xy(info_x, 18.2)
    pdf.cell(info_w, 2.8, "NOM COMPLET", align="L")
    pdf.set_text_color(10, 10, 10)
    pdf.set_font("Helvetica", "B", 7.2)
    pdf.set_xy(info_x, 20.8)
    pdf.multi_cell(info_w, 3.4, _safe_text(carte.full_name_snapshot), align="L")

    fonction = carte.user.role_local or "Président du Bureau Local"
    pdf.set_text_color(*GREEN)
    pdf.set_font("Helvetica", "", 4.6)
    pdf.set_xy(info_x, 27.5)
    pdf.cell(info_w, 2.8, "FONCTION", align="L")
    pdf.set_text_color(10, 10, 10)
    pdf.set_font("Helvetica", "B", 6.4)
    pdf.set_xy(info_x, 30.1)
    pdf.cell(info_w, 3.2, _safe_text(fonction), align="L")

    delegation_nom = carte.user.delegation.nom if carte.user.delegation else "-"
    pdf.set_text_color(90, 90, 90)
    pdf.set_font("Helvetica", "", 5.6)
    pdf.set_xy(info_x, 33.8)
    pdf.cell(info_w, 3, _safe_text(delegation_nom), align="L")

    naissance_bits = []
    if carte.date_naissance:
        naissance_bits.append(f"Ne(e) le {carte.date_naissance.strftime('%d/%m/%Y')}")
    if carte.lieu_naissance:
        naissance_bits.append(f"a {_safe_text(carte.lieu_naissance)}")
    if naissance_bits:
        pdf.set_text_color(90, 90, 90)
        pdf.set_font("Helvetica", "", 4.6)
        pdf.set_xy(6, 39.3)
        pdf.cell(63, 3, " ".join(naissance_bits), align="L")

    qr_payload = f"{settings.public_base_url}/verify/{carte.numero_carte or ''}"
    qr_img = qrcode.make(qr_payload, border=1)
    qr_size = 11.0
    qr_x = CARD_W - 3.2 - qr_size
    qr_y = CARD_H - 3.2 - qr_size
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(qr_x - 0.8, qr_y - 0.8, qr_size + 1.6, qr_size + 1.6, style="F", round_corners=True, corner_radius=1)
    pdf.image(qr_img.get_image() if hasattr(qr_img, "get_image") else qr_img, x=qr_x, y=qr_y, w=qr_size, h=qr_size)

    pdf.set_font("Helvetica", "B", 6.0)
    pdf.set_text_color(*GREEN)
    pdf.set_xy(6, CARD_H - 9)
    pdf.cell(60, 3, f"N. {carte.numero_carte or '-'}", align="L")
    pdf.set_font("Helvetica", "", 5.0)
    pdf.set_text_color(80, 80, 80)
    pdf.set_xy(6, CARD_H - 6)
    validite = carte.date_validite.strftime("%d/%m/%Y") if carte.date_validite else "-"
    pdf.cell(60, 3, f"Valable jusqu'au {validite}", align="L")


def _add_verso_delegation(pdf: FPDF, carte) -> None:
    """Verso des présidents de délégation — même sobriété que le verso national,
    avec la ligne de valeurs du modèle approuvé (Cooperation / Service /
    Qualite / Excellence) en plus pour differencier visuellement la categorie."""
    pdf.add_page()
    corner_r = 3.18

    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, CARD_W, CARD_H, style="F", round_corners=True, corner_radius=corner_r)

    pdf.set_fill_color(*GREEN)
    pdf.rect(corner_r, 0, CARD_W - 2 * corner_r, 1.2, style="F")

    pdf.set_text_color(*BADGE_BLUE)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_xy(5, 5)
    pdf.cell(CARD_W - 10, 4, "LECIM", align="L")

    pdf.set_text_color(70, 70, 70)
    pdf.set_font("Helvetica", "", 6.3)
    pdf.set_xy(5, 10.5)
    pdf.multi_cell(
        CARD_W - 10, 3.3,
        _safe_text(
            "Cette carte atteste la qualité de président de délégation régionale de son "
            "titulaire et demeure la propriété de la LECIM. Merci de la retourner au "
            "secrétariat en cas de découverte."
        ),
        align="L",
    )

    valeurs = ["Cooperation", "Service", "Qualite", "Excellence"]
    val_y = 34
    col_w = (CARD_W - 10) / len(valeurs)
    pdf.set_draw_color(*GREEN)
    pdf.line(5, val_y - 1.5, CARD_W - 5, val_y - 1.5)
    for i, label in enumerate(valeurs):
        cx = 5 + col_w * i
        pdf.set_fill_color(*GREEN)
        pdf.ellipse(cx + col_w / 2 - 0.8, val_y, 1.6, 1.6, style="F")
        pdf.set_text_color(*GREEN_DARK)
        pdf.set_font("Helvetica", "", 4.6)
        pdf.set_xy(cx, val_y + 2.2)
        pdf.cell(col_w, 3, label, align="C")

    sig_y = CARD_H - 11
    pdf.set_draw_color(180, 180, 180)
    pdf.line(CARD_W - 36, sig_y, CARD_W - 5, sig_y)
    pdf.set_font("Helvetica", "", 5.2)
    pdf.set_text_color(120, 120, 120)
    pdf.set_xy(CARD_W - 36, sig_y + 1)
    pdf.cell(31, 3, "Signature", align="C")

    pdf.set_text_color(130, 130, 130)
    pdf.set_font("Helvetica", "", 5.3)
    pdf.set_xy(5, CARD_H - 7)
    pdf.cell(40, 3, "lecimnational@gmail.com", align="L")

    pdf.set_fill_color(*GREEN)
    pdf.rect(corner_r, CARD_H - 1.2, CARD_W - 2 * corner_r, 1.2, style="F")


def generate_card_pdf(carte, photo_bytes: bytes | None) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format=(CARD_H, CARD_W))
    pdf.set_auto_page_break(auto=False)

    is_delegation = bool(carte.user.delegation_id)
    if is_delegation:
        _add_recto_delegation(pdf, carte, photo_bytes)
        _add_verso_delegation(pdf, carte)
    else:
        _add_recto(pdf, carte, photo_bytes)
        _add_verso(pdf, carte)

    return bytes(pdf.output())


def generate_card_pdf_recto(carte, photo_bytes: bytes | None) -> bytes:
    """Fichier d'un seul feuillet (recto uniquement) : certaines imprimantes de
    cartes ne savent pas imprimer recto/verso à partir d'un PDF à deux pages,
    il faut donc deux fichiers séparés pour les deux passages d'impression."""
    pdf = FPDF(orientation="L", unit="mm", format=(CARD_H, CARD_W))
    pdf.set_auto_page_break(auto=False)
    if carte.user.delegation_id:
        _add_recto_delegation(pdf, carte, photo_bytes)
    else:
        _add_recto(pdf, carte, photo_bytes)
    return bytes(pdf.output())


def generate_card_pdf_verso(carte) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format=(CARD_H, CARD_W))
    pdf.set_auto_page_break(auto=False)
    if carte.user.delegation_id:
        _add_verso_delegation(pdf, carte)
    else:
        _add_verso(pdf, carte)
    return bytes(pdf.output())


def _add_recto_eleve(pdf: FPDF, carte, photo_bytes: bytes | None, ecole_logo_bytes: bytes | None) -> None:
    pdf.add_page()

    pdf.set_fill_color(*CREAM)
    pdf.rect(0, 0, CARD_W, CARD_H, style="F")

    pdf.set_fill_color(*GREEN_DARK)
    pdf.rect(0, 0, CARD_W, 14, style="F")

    text_x = 4
    if ecole_logo_bytes:
        pdf.image(io.BytesIO(ecole_logo_bytes), x=3, y=1.5, w=11, h=11)
        text_x = 16
    elif LOGO_PATH.exists():
        pdf.image(str(LOGO_PATH), x=3, y=1.5, w=11, h=11)
        text_x = 16

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_xy(text_x, 1.5)
    pdf.multi_cell(CARD_W - text_x - 4, 3.6, carte.etablissement.nom, align="L")
    pdf.set_font("Helvetica", "", 6)
    pdf.set_xy(text_x, 9.5)
    pdf.cell(CARD_W - text_x - 4, 3.5, "Carte scolaire - Etablissement affilie LECIM", align="L")

    pdf.set_fill_color(*GOLD)
    pdf.rect(0, 14, CARD_W, 1.2, style="F")

    photo_x, photo_y, photo_w, photo_h = 4, 18, 21, 27
    if photo_bytes:
        pdf.image(io.BytesIO(photo_bytes), x=photo_x, y=photo_y, w=photo_w, h=photo_h)
    else:
        pdf.set_draw_color(*GREEN)
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(photo_x, photo_y, photo_w, photo_h, style="DF")
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(*GREEN)
        pdf.set_xy(photo_x, photo_y + photo_h / 2 - 2)
        pdf.cell(photo_w, 4, "PHOTO", align="C")
    pdf.set_draw_color(*GREEN_DARK)
    pdf.rect(photo_x, photo_y, photo_w, photo_h)

    qr_payload = f"{settings.public_base_url}/verify-eleve/{carte.matricule or ''}"
    qr_img = qrcode.make(qr_payload, border=1)
    qr_size = 12.0
    qr_x = CARD_W - 4 - qr_size
    qr_y = CARD_H - 3 - qr_size - 1
    pdf.image(qr_img.get_image() if hasattr(qr_img, "get_image") else qr_img, x=qr_x, y=qr_y, w=qr_size, h=qr_size)

    info_x = photo_x + photo_w + 4
    info_w = qr_x - 2 - info_x

    pdf.set_text_color(*GREEN_DARK)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(info_x, 19)
    pdf.multi_cell(info_w, 4.3, carte.eleve_nom, align="L")

    pdf.set_text_color(80, 80, 80)
    pdf.set_font("Helvetica", "", 7.2)
    pdf.set_xy(info_x, pdf.get_y() + 0.5)
    pdf.multi_cell(info_w, 3.4, f"Classe : {carte.classe}", align="L")

    pdf.set_font("Helvetica", "", 6.3)
    pdf.set_xy(info_x, pdf.get_y() + 0.5)
    pdf.cell(info_w, 3.2, f"Annee scolaire {carte.annee_scolaire}", align="L")

    pdf.set_font("Helvetica", "B", 6.8)
    pdf.set_text_color(*GREEN)
    pdf.set_xy(info_x, CARD_H - 12)
    pdf.cell(info_w, 3.6, f"Mat. {carte.matricule or '-'}", align="L")

    pdf.set_font("Helvetica", "", 6)
    pdf.set_text_color(80, 80, 80)
    pdf.set_xy(info_x, CARD_H - 8)
    validite = carte.date_validite.strftime("%d/%m/%Y") if carte.date_validite else "-"
    pdf.cell(info_w, 3.4, f"Valable jusqu'au {validite}", align="L")

    pdf.set_fill_color(*GREEN_DARK)
    pdf.rect(0, CARD_H - 3, CARD_W, 3, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "", 5)
    pdf.set_xy(0, CARD_H - 3)
    pdf.cell(CARD_W, 3, "Carte scolaire certifiee LECIM", align="C")


def _add_verso_eleve(pdf: FPDF, carte) -> None:
    pdf.add_page()

    pdf.set_fill_color(*CREAM)
    pdf.rect(0, 0, CARD_W, CARD_H, style="F")

    pdf.set_fill_color(*GREEN_DARK)
    pdf.rect(0, 0, CARD_W, 8, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_xy(4, 1.5)
    pdf.cell(CARD_W - 8, 5, "LECIM - Informations", align="L")

    pdf.set_text_color(50, 50, 50)
    pdf.set_font("Helvetica", "", 6)
    pdf.set_xy(4, 11)
    pdf.multi_cell(
        CARD_W - 8,
        3.2,
        "Cette carte atteste que son titulaire est regulierement inscrit(e) dans un "
        "etablissement affilie a la LECIM. En cas de decouverte, merci de la retourner "
        "a l'etablissement ou au secretariat administratif de la LECIM.",
        align="L",
    )

    pdf.set_font("Helvetica", "", 5.8)
    pdf.set_xy(4, pdf.get_y() + 2)
    pdf.cell(CARD_W - 8, 3.2, "Contact : lecimnational@gmail.com", align="L")

    if carte.eleve_date_naissance:
        pdf.set_xy(4, pdf.get_y() + 4)
        pdf.cell(CARD_W - 8, 3.2, f"Ne(e) le : {carte.eleve_date_naissance.strftime('%d/%m/%Y')}", align="L")

    sig_y = CARD_H - 14
    pdf.set_draw_color(120, 120, 120)
    pdf.line(CARD_W - 40, sig_y, CARD_W - 6, sig_y)
    pdf.set_font("Helvetica", "", 5.5)
    pdf.set_text_color(80, 80, 80)
    pdf.set_xy(CARD_W - 40, sig_y + 1)
    pdf.cell(34, 3, "Signature du Directeur", align="C")

    pdf.set_fill_color(*GREEN_DARK)
    pdf.rect(0, CARD_H - 3, CARD_W, 3, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "", 5)
    pdf.set_xy(0, CARD_H - 3)
    pdf.cell(CARD_W, 3, f"Mat. {carte.matricule or '-'}", align="C")


def generate_student_card_pdf(carte, photo_bytes: bytes | None, ecole_logo_bytes: bytes | None) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format=(CARD_H, CARD_W))
    pdf.set_auto_page_break(auto=False)

    _add_recto_eleve(pdf, carte, photo_bytes, ecole_logo_bytes)
    _add_verso_eleve(pdf, carte)

    return bytes(pdf.output())


def generate_student_card_pdf_recto(carte, photo_bytes: bytes | None, ecole_logo_bytes: bytes | None) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format=(CARD_H, CARD_W))
    pdf.set_auto_page_break(auto=False)
    _add_recto_eleve(pdf, carte, photo_bytes, ecole_logo_bytes)
    return bytes(pdf.output())


def generate_student_card_pdf_verso(carte) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format=(CARD_H, CARD_W))
    pdf.set_auto_page_break(auto=False)
    _add_verso_eleve(pdf, carte)
    return bytes(pdf.output())
