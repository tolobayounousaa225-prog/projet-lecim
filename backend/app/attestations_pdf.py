"""Attestations officielles (affiliation établissement, appartenance BEN) en PDF,
au format A4, avec QR code de vérification publique — même logique de confiance
que les cartes (card_pdf.py) mais pour un document plein format, imprimable."""

import datetime
from pathlib import Path

import qrcode
from fpdf import FPDF

from .config import settings
from .reports import pdf_safe

GREEN_DARK = (11, 61, 46)
GREEN = (15, 122, 76)
GOLD = (224, 165, 44)

LOGO_PATH = Path(__file__).resolve().parent / "static" / "img" / "logo.jpg"


def numero_affiliation(etablissement_id: int) -> str:
    return f"LECIM-AFF-{etablissement_id:04d}"


def _draw_frame(pdf: FPDF) -> None:
    pdf.set_draw_color(*GOLD)
    pdf.set_line_width(1.1)
    pdf.rect(8, 8, pdf.w - 16, pdf.h - 16)
    pdf.set_draw_color(*GREEN_DARK)
    pdf.set_line_width(0.3)
    pdf.rect(11, 11, pdf.w - 22, pdf.h - 22)


def _header(pdf: FPDF, subtitle: str) -> None:
    pdf.add_page()
    _draw_frame(pdf)

    if LOGO_PATH.exists():
        pdf.image(str(LOGO_PATH), x=pdf.w / 2 - 13, y=18, w=26, h=26)

    pdf.set_xy(20, 48)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*GREEN_DARK)
    pdf.cell(pdf.w - 40, 9, "LECIM", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(20)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(
        pdf.w - 40, 5.5,
        "Ligue des Etablissements Confessionnels et Madrassas en Cote d'Ivoire",
        align="C", new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*GOLD)
    pdf.cell(pdf.w - 40, 10, subtitle, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)


def _body_paragraph(pdf: FPDF, text: str) -> None:
    pdf.set_x(28)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(pdf.w - 56, 7.5, pdf_safe(text), align="J")
    pdf.ln(6)


def _kv_line(pdf: FPDF, label: str, value: str) -> None:
    pdf.set_x(28)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*GREEN_DARK)
    pdf.cell(55, 7, pdf_safe(label))
    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 7, pdf_safe(value), new_x="LMARGIN", new_y="NEXT")


def _footer_qr_and_signature(pdf: FPDF, verify_url: str, numero: str) -> None:
    qr_img = qrcode.make(verify_url, border=1)
    qr_size = 26.0
    qr_x = pdf.w - 20 - qr_size - 10
    qr_y = pdf.h - 60
    pdf.image(qr_img.get_image() if hasattr(qr_img, "get_image") else qr_img, x=qr_x, y=qr_y, w=qr_size, h=qr_size)
    pdf.set_xy(qr_x - 8, qr_y + qr_size + 2)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(qr_size + 16, 3.5, "Scanner pour verifier", align="C", new_x="LMARGIN", new_y="NEXT")

    sig_x = 28
    sig_y = pdf.h - 55
    pdf.set_xy(sig_x, sig_y)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(75, 6, f"Fait a Abidjan, le {datetime.date.today().strftime('%d/%m/%Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(sig_x, sig_y + 8)
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.cell(75, 6, "Le President de la LECIM", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(150, 150, 150)
    pdf.line(sig_x, sig_y + 24, sig_x + 65, sig_y + 24)

    pdf.set_xy(0, pdf.h - 16)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(pdf.w, 4, f"Reference : {numero}  -  Contact : ben_jemci@gmail.com", align="C")


def generate_etablissement_attestation_pdf(etablissement) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    _header(pdf, "ATTESTATION D'AFFILIATION")

    numero = numero_affiliation(etablissement.id)
    date_adhesion = (
        etablissement.date_adhesion.strftime("%d/%m/%Y") if etablissement.date_adhesion else "non renseignee"
    )

    _body_paragraph(
        pdf,
        f"La Ligue des Etablissements Confessionnels et Madrassas en Cote d'Ivoire (LECIM) "
        f"atteste par la presente que l'etablissement ci-dessous designe est regulierement "
        f"affilie a la LECIM et reconnu comme membre actif de la ligue.",
    )

    pdf.ln(2)
    _kv_line(pdf, "Etablissement :", etablissement.nom)
    _kv_line(pdf, "Statut :", etablissement.statut_label)
    _kv_line(pdf, "Niveaux d'enseignement :", {
        "primaire": "Primaire",
        "secondaire": "Secondaire",
        "les_deux": "Primaire et secondaire",
    }.get(etablissement.type_enseignement, etablissement.type_enseignement))
    if etablissement.bureau_local:
        _kv_line(pdf, "Bureau local / region :", etablissement.bureau_local)
    _kv_line(pdf, "Membre depuis le :", date_adhesion)
    _kv_line(pdf, "Numero d'affiliation :", numero)

    pdf.ln(6)
    _body_paragraph(
        pdf,
        "Cette attestation est delivree pour servir et valoir ce que de droit, et peut etre "
        "verifiee a tout moment via le code QR ci-dessous ou le lien de verification publique.",
    )

    verify_url = f"{settings.public_base_url}/verify-etablissement/{etablissement.id}"
    _footer_qr_and_signature(pdf, verify_url, numero)

    return bytes(pdf.output())


def generate_membre_attestation_pdf(user) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    _header(pdf, "ATTESTATION D'APPARTENANCE")

    numero = f"LECIM-BEN-{user.id:04d}"
    depuis = user.created_at.strftime("%d/%m/%Y") if user.created_at else "non renseignee"

    _body_paragraph(
        pdf,
        f"La Ligue des Etablissements Confessionnels et Madrassas en Cote d'Ivoire (LECIM) "
        f"atteste par la presente que la personne ci-dessous designee est membre du Bureau "
        f"Executif National (BEN) de la LECIM.",
    )

    pdf.ln(2)
    _kv_line(pdf, "Nom complet :", user.full_name)
    _kv_line(pdf, "Fonction occupee :", user.poste_label)
    _kv_line(pdf, "Membre depuis le :", depuis)
    _kv_line(pdf, "Reference :", numero)

    pdf.ln(6)
    _body_paragraph(
        pdf,
        "Cette attestation est delivree pour servir et valoir ce que de droit, et peut etre "
        "verifiee a tout moment via le code QR ci-dessous ou le lien de verification publique.",
    )

    verify_url = f"{settings.public_base_url}/verify-membre/{user.id}"
    _footer_qr_and_signature(pdf, verify_url, numero)

    return bytes(pdf.output())


def generate_adhesion_recepisse_pdf(demande) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    _header(pdf, "RECEPISSE DE DEMANDE D'ADHESION")

    _body_paragraph(
        pdf,
        "La Ligue des Etablissements Confessionnels et Madrassas en Cote d'Ivoire (LECIM) "
        "accuse reception de la demande d'adhesion ci-dessous. Ce recepisse doit etre "
        "presente, avec les pieces justificatives utiles, lors de l'entretien de validation "
        "au siege de la LECIM.",
    )

    pdf.ln(2)
    _kv_line(pdf, "Code de demande :", demande.code_demande)
    _kv_line(pdf, "Etablissement :", demande.nom_etablissement)
    _kv_line(pdf, "Nom du directeur :", demande.nom_directeur)
    _kv_line(pdf, "Localite :", demande.localite)
    _kv_line(pdf, "Contact :", demande.telephone)
    _kv_line(pdf, "Date de soumission :", demande.created_at.strftime("%d/%m/%Y"))

    pdf.ln(6)
    _body_paragraph(
        pdf,
        "Ce recepisse ne constitue pas une adhesion validee. Il confirme uniquement "
        "l'enregistrement de la demande, qui sera examinee lors d'un entretien avec le "
        "secretariat de la LECIM. Le statut de la demande peut etre suivi a tout moment "
        "via le code QR ci-dessous.",
    )

    verify_url = f"{settings.public_base_url}/verify-adhesion/{demande.code_demande}"
    _footer_qr_and_signature(pdf, verify_url, demande.code_demande)

    return bytes(pdf.output())


def generate_adhesion_certificat_pdf(demande) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    _header(pdf, "CERTIFICAT D'ADHESION")

    _body_paragraph(
        pdf,
        "La Ligue des Etablissements Confessionnels et Madrassas en Cote d'Ivoire (LECIM) "
        "certifie par la presente que l'etablissement ci-dessous designe a ete examine et "
        "valide comme membre de la ligue, a l'issue d'un entretien avec le secretariat "
        "charge des affaires interieures.",
    )

    date_adhesion = demande.date_adhesion.strftime("%d/%m/%Y") if demande.date_adhesion else "non renseignee"

    pdf.ln(2)
    _kv_line(pdf, "Etablissement :", demande.nom_etablissement)
    _kv_line(pdf, "Localite :", demande.localite)
    if demande.numero_agrement:
        _kv_line(pdf, "Numero d'agrement :", demande.numero_agrement)
    _kv_line(pdf, "Date d'adhesion :", date_adhesion)
    _kv_line(pdf, "Code de demande :", demande.code_demande)

    pdf.ln(6)
    _body_paragraph(
        pdf,
        "Ce certificat est delivre pour servir et valoir ce que de droit, et peut etre "
        "verifie a tout moment via le code QR ci-dessous ou le lien de verification publique.",
    )

    verify_url = f"{settings.public_base_url}/verify-adhesion/{demande.code_demande}"
    _footer_qr_and_signature(pdf, verify_url, demande.code_demande)

    return bytes(pdf.output())
