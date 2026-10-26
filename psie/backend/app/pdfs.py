"""PDF bilingues (français à gauche, arabe à droite) : reçus de paiement et attestations."""

import datetime
import io
from pathlib import Path

import qrcode
from fpdf import FPDF

from . import models
from .config import settings
from .finance import fcfa

FONTS = Path(__file__).resolve().parent / "static" / "fonts"
GREEN = (20, 83, 45)
GREY = (93, 111, 103)

ORG_FR = "Plateforme des Structures Islamiques d'Éducation"
ORG_AR = "منصة الهياكل الإسلامية للتعليم"
SIEGE = "Mosquée AL FATH, Treichville, Abidjan"


def _new_pdf() -> FPDF:
    pdf = FPDF(format="A4")
    pdf.add_font("dv", "", str(FONTS / "DejaVuSans.ttf"))
    pdf.add_font("dv", "B", str(FONTS / "DejaVuSans-Bold.ttf"))
    # Mise en forme des lettres arabes (formes liées) et sens de lecture droite-gauche
    pdf.set_text_shaping(True)
    pdf.set_auto_page_break(False)
    pdf.add_page()
    return pdf


def _qr_png(url: str) -> io.BytesIO:
    img = qrcode.make(url, box_size=6, border=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _header(pdf: FPDF, title_fr: str, title_ar: str) -> None:
    pdf.set_fill_color(*GREEN)
    pdf.rect(0, 0, 210, 34, style="F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(15, 9)
    pdf.set_font("dv", "B", 10)
    pdf.cell(105, 7, ORG_FR)
    pdf.set_font("dv", "B", 13)
    pdf.cell(75, 7, ORG_AR, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_xy(15, 19)
    pdf.set_font("dv", "", 9)
    pdf.cell(105, 6, f"PSIE — {SIEGE}")
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(15, 44)
    pdf.set_font("dv", "B", 18)
    pdf.cell(180, 9, title_fr, new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(15)
    pdf.cell(180, 9, title_ar, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)


def _row(pdf: FPDF, fr: str, value: str, ar: str) -> None:
    """Une ligne : libellé français | valeur | libellé arabe (jamais de mélange sur une cellule)."""
    pdf.set_x(15)
    pdf.set_font("dv", "", 10)
    pdf.set_text_color(*GREY)
    pdf.cell(55, 9, fr, border="B")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("dv", "B", 11)
    pdf.cell(70, 9, value, border="B", align="C")
    pdf.set_font("dv", "", 10)
    pdf.set_text_color(*GREY)
    pdf.cell(55, 9, ar, border="B", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)


def _footer(pdf: FPDF, verify_url: str, note_fr: str, note_ar: str,
            signer: tuple[str, str] = ("Le Secrétaire chargé des finances", "الأمين المكلف بالشؤون المالية")) -> None:
    y = 205
    pdf.image(_qr_png(verify_url), x=15, y=y, w=34)
    pdf.set_xy(54, y + 4)
    pdf.set_font("dv", "", 9)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(80, 5, note_fr)
    pdf.set_xy(120, y + 4)
    pdf.multi_cell(75, 5, note_ar, align="R")
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(15, 255)
    pdf.set_font("dv", "", 10)
    pdf.cell(90, 6, signer[0])
    pdf.cell(90, 6, signer[1], align="R")


def receipt_pdf(paiement: models.Paiement) -> bytes:
    e = paiement.echeance
    f = e.faitiere
    pdf = _new_pdf()
    _header(pdf, "REÇU DE PAIEMENT", "إيصال دفع")
    _row(pdf, "N° du reçu", paiement.recu_numero, "رقم الإيصال")
    _row(pdf, "Date", f"{paiement.date_paiement:%d/%m/%Y}", "التاريخ")
    _row(pdf, "Reçu de", f.sigle, "المدفوع من")
    _row(pdf, "Objet", e.libelle, "الغرض")
    _row(pdf, "Montant", fcfa(paiement.montant), "المبلغ")
    _row(pdf, "Mode de paiement", paiement.mode_label, "طريقة الدفع")
    if paiement.reference:
        _row(pdf, "Référence", paiement.reference, "المرجع")
    _row(pdf, "Solde restant", fcfa(max(e.solde, 0)), "الرصيد المتبقي")
    if paiement.annule:
        pdf.set_xy(15, 150)
        pdf.set_text_color(180, 35, 24)
        pdf.set_font("dv", "B", 26)
        pdf.cell(180, 14, "ANNULÉ — ملغى", align="C")
        pdf.set_text_color(0, 0, 0)
    url = f"{settings.public_base_url.rstrip('/')}/verifier/{paiement.verify_token}"
    _footer(pdf, url, "Scannez pour vérifier l'authenticité de ce reçu.", "امسح الرمز للتحقق من صحة هذا الإيصال.")
    return bytes(pdf.output())


def attestation_pdf(faitiere: models.Faitiere, annee: int, echeance: models.Echeance, verify_url: str) -> bytes:
    pdf = _new_pdf()
    _header(pdf, "ATTESTATION DE COTISATION À JOUR", "شهادة الوفاء بالاشتراك")
    _row(pdf, "Organisation", faitiere.sigle, "المنظمة")
    _row(pdf, "Dénomination", faitiere.nom[:34], "التسمية")
    cat_fr, cat_ar = faitiere.categorie_label_pdf
    _row(pdf, "Catégorie", cat_fr, f"الفئة: {cat_ar}")
    _row(pdf, "Exercice", str(annee), "السنة")
    _row(pdf, "Cotisation annuelle", fcfa(echeance.montant_du), "الاشتراك السنوي")
    _row(pdf, "Situation", "À JOUR", "مسدد")
    _row(pdf, "Délivrée le", f"{datetime.date.today():%d/%m/%Y}", "صدرت بتاريخ")
    pdf.set_xy(15, 140)
    pdf.set_font("dv", "", 10)
    pdf.multi_cell(
        180, 6,
        f"La PSIE atteste que {faitiere.sigle} est à jour de sa cotisation annuelle {annee}.",
    )
    pdf.set_x(15)
    pdf.multi_cell(180, 6, f"تشهد المنصة بأن {faitiere.sigle} قد سددت اشتراكها السنوي لسنة {annee}.", align="R")
    _footer(pdf, verify_url, "Scannez pour vérifier cette attestation (situation à la date de lecture).",
            "امسح الرمز للتحقق من هذه الشهادة.")
    return bytes(pdf.output())


def membership_certificate_pdf(demande: models.DemandeAdhesion, verify_url: str) -> bytes:
    f = demande.faitiere
    pdf = _new_pdf()
    _header(pdf, "CERTIFICAT D'ADHÉSION", "شهادة انخراط")
    _row(pdf, "Organisation", f.sigle, "المنظمة")
    _row(pdf, "Dénomination", f.nom[:34], "التسمية")
    _row(pdf, "Qualité", "Membre ordinaire", "صفة: عضو عادي")
    _row(pdf, "Adhésion le", f"{f.date_adhesion:%d/%m/%Y}" if f.date_adhesion else "—", "تاريخ الانخراط")
    _row(pdf, "Décision de l'AG", (demande.decision_reference or "—")[:34], "قرار الجمعية العامة")
    _row(pdf, "Dossier", demande.code, "رقم الملف")
    pdf.set_xy(15, 140)
    pdf.set_font("dv", "", 10)
    pdf.multi_cell(180, 6, f"La PSIE certifie que {f.sigle} est membre de la Plateforme des Structures Islamiques d'Éducation.")
    pdf.set_x(15)
    pdf.multi_cell(180, 6, f"تشهد المنصة بأن {f.sigle} عضو في منصة الهياكل الإسلامية للتعليم.", align="R")
    _footer(pdf, verify_url, "Scannez pour vérifier l'authenticité de ce certificat.",
            "امسح الرمز للتحقق من صحة هذه الشهادة.", signer=("Le Directeur Exécutif National", "المدير التنفيذي الوطني"))
    return bytes(pdf.output())
