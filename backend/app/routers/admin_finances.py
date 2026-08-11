import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import audit, models
from ..database import get_db
from ..deps import require_finance_access_web
from ..email_utils import send_email
from ..finances_constants import ADHESION_MONTANT, COTISATION_RULES, RECETTE_CATEGORIES, cotisation_rule
from ..reports import (
    current_annee_scolaire,
    etablissements_en_retard,
    export_transactions_csv,
    export_transactions_xlsx,
    generate_comparative_report_pdf,
    generate_financial_report_pdf,
    money,
    multi_year_financial_summary,
)
from .admin_files import ALLOWED_DOCUMENT_EXT, ALLOWED_PHOTO_EXT, UPLOAD_ROOT, _save_upload
import mimetypes
import uuid

router = APIRouter(prefix="/admin", tags=["admin-finances"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

PIECES_DIR = UPLOAD_ROOT / "justificatifs"
ALLOWED_PIECE_EXT = ALLOWED_DOCUMENT_EXT | ALLOWED_PHOTO_EXT


# ---------- Tableau de bord finances ----------

@router.get("/finances")
def finances_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    total_adhesions = db.query(func.coalesce(func.sum(models.Adhesion.montant), 0)).scalar()
    total_cotisations = db.query(func.coalesce(func.sum(models.Cotisation.montant_paye), 0)).scalar()
    total_recettes = db.query(func.coalesce(func.sum(models.Recette.montant), 0)).scalar()
    total_depenses = db.query(func.coalesce(func.sum(models.Depense.montant), 0)).scalar()
    solde = total_adhesions + total_cotisations + total_recettes - total_depenses

    recettes_par_categorie = (
        db.query(models.Recette.categorie, func.coalesce(func.sum(models.Recette.montant), 0))
        .group_by(models.Recette.categorie)
        .all()
    )

    nb_etablissements = db.query(models.Etablissement).count()
    cotisations = db.query(models.Cotisation).all()
    nb_cotisations_impayees = sum(1 for c in cotisations if c.statut_paiement != "paye")

    return templates.TemplateResponse(
        request,
        "admin/finances_dashboard.html",
        {
            "admin": user,
            "active": "finances",
            "total_adhesions": total_adhesions,
            "total_cotisations": total_cotisations,
            "total_recettes": total_recettes,
            "total_depenses": total_depenses,
            "solde": solde,
            "recettes_par_categorie": recettes_par_categorie,
            "categories_labels": RECETTE_CATEGORIES,
            "nb_etablissements": nb_etablissements,
            "nb_cotisations_impayees": nb_cotisations_impayees,
        },
    )


# ---------- Rapport financier (PDF, période libre) ----------

@router.get("/finances/rapport")
def finances_rapport_form(
    request: Request,
    user: models.User = Depends(require_finance_access_web),
):
    today = datetime.date.today()
    debut_mois = today.replace(day=1)
    return templates.TemplateResponse(
        request,
        "admin/finances_rapport_form.html",
        {
            "admin": user,
            "active": "finances",
            "date_debut": debut_mois,
            "date_fin": today,
        },
    )


@router.post("/finances/rapport")
def finances_rapport_generate(
    date_debut: datetime.date = Form(...),
    date_fin: datetime.date = Form(...),
    archiver: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    pdf_bytes = generate_financial_report_pdf(db, date_debut, date_fin, generated_by=user.full_name)
    filename = f"Rapport financier {date_debut.strftime('%d-%m-%Y')} au {date_fin.strftime('%d-%m-%Y')}.pdf"

    if archiver:
        stored_name = f"{uuid.uuid4().hex}.pdf"
        (UPLOAD_ROOT / "documents" / stored_name).write_bytes(pdf_bytes)
        db.add(
            models.Document(
                title=f"Rapport financier — {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
                category="rapport",
                file_path=f"documents/{stored_name}",
                original_filename=filename,
                uploaded_by_id=user.id,
            )
        )
        db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Retards de cotisation ----------

@router.get("/finances/retards")
def finances_retards(
    request: Request,
    envoyees: int | None = None,
    ignorees: int | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    annee = current_annee_scolaire()
    retards = etablissements_en_retard(db, annee)
    return templates.TemplateResponse(
        request,
        "admin/finances_retards.html",
        {
            "admin": user,
            "active": "finances",
            "retards": retards,
            "annee": annee,
            "envoyees": envoyees,
            "ignorees": ignorees,
        },
    )


@router.post("/finances/retards/relances")
def finances_retards_relances(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    annee = current_annee_scolaire()
    retards = etablissements_en_retard(db, annee)
    envoyees = 0
    ignorees = 0
    for r in retards:
        etablissement = r["etablissement"]
        if not etablissement.contact_email:
            ignorees += 1
            continue
        subject = f"[LECIM] Rappel de cotisation — année scolaire {annee}"
        body = (
            f"Cher(e) responsable de {etablissement.nom},\n\n"
            f"Sauf erreur de notre part, votre établissement affiche un solde impayé sur la cotisation "
            f"de l'année scolaire {annee} au titre de la LECIM.\n\n"
            f"Montant dû : {money(r['montant_du'])}\n"
            f"Montant déjà versé : {money(r['montant_paye'])}\n"
            f"Reste à recouvrer : {money(r['reste'])}\n\n"
            "Nous vous remercions de régulariser cette situation dans les meilleurs délais auprès "
            "du Bureau Exécutif National.\n\n"
            "Cordialement,\n"
            "La Ligue des Établissements Confessionnels et Madrassas de Côte d'Ivoire (LECIM)"
        )
        if send_email(etablissement.contact_email, subject, body):
            envoyees += 1
        else:
            ignorees += 1
    return RedirectResponse(
        url=f"/admin/finances/retards?envoyees={envoyees}&ignorees={ignorees}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ---------- Évolution pluriannuelle ----------

@router.get("/finances/evolution")
def finances_evolution(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    data = multi_year_financial_summary(db)

    chart_width, chart_height, chart_top = 760, 220, 20
    baseline = chart_top + chart_height
    max_val = max([1] + [d["total_entrees"] for d in data] + [d["depenses"] for d in data])
    year_width = chart_width / len(data) if data else chart_width
    bar_width = year_width * 0.32

    bars = []
    labels = []
    for i, d in enumerate(data):
        group_x = i * year_width + year_width * 0.12
        entrees_h = (d["total_entrees"] / max_val) * chart_height
        depenses_h = (d["depenses"] / max_val) * chart_height
        bars.append(
            {"x": group_x, "y": baseline - entrees_h, "width": bar_width, "height": entrees_h, "color": "var(--green)"}
        )
        bars.append(
            {
                "x": group_x + bar_width + 4,
                "y": baseline - depenses_h,
                "width": bar_width,
                "height": depenses_h,
                "color": "var(--gold)",
            }
        )
        labels.append({"x": group_x + bar_width, "y": baseline + 18, "text": d["annee"]})

    return templates.TemplateResponse(
        request,
        "admin/finances_evolution.html",
        {
            "admin": user,
            "active": "finances",
            "data": data,
            "bars": bars,
            "labels": labels,
            "chart_width": chart_width,
            "chart_height": chart_height,
            "baseline": baseline,
        },
    )


# ---------- Export CSV des transactions ----------

@router.get("/finances/export.csv")
def finances_export_csv(
    date_debut: datetime.date,
    date_fin: datetime.date,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    csv_content = export_transactions_csv(db, date_debut, date_fin)
    filename = f"transactions_{date_debut.isoformat()}_{date_fin.isoformat()}.csv"
    return Response(
        content="﻿" + csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/finances/export.xlsx")
def finances_export_xlsx(
    date_debut: datetime.date,
    date_fin: datetime.date,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    xlsx_bytes = export_transactions_xlsx(db, date_debut, date_fin)
    filename = f"transactions_{date_debut.isoformat()}_{date_fin.isoformat()}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Rapport comparatif (deux périodes) ----------

@router.get("/finances/rapport-comparatif")
def finances_rapport_comparatif_form(
    request: Request,
    user: models.User = Depends(require_finance_access_web),
):
    today = datetime.date.today()
    debut_mois = today.replace(day=1)
    mois_precedent_fin = debut_mois - datetime.timedelta(days=1)
    mois_precedent_debut = mois_precedent_fin.replace(day=1)
    return templates.TemplateResponse(
        request,
        "admin/finances_rapport_comparatif_form.html",
        {
            "admin": user,
            "active": "finances",
            "date_debut_a": mois_precedent_debut,
            "date_fin_a": mois_precedent_fin,
            "date_debut_b": debut_mois,
            "date_fin_b": today,
        },
    )


@router.post("/finances/rapport-comparatif")
def finances_rapport_comparatif_generate(
    date_debut_a: datetime.date = Form(...),
    date_fin_a: datetime.date = Form(...),
    date_debut_b: datetime.date = Form(...),
    date_fin_b: datetime.date = Form(...),
    label_a: str = Form("Période A"),
    label_b: str = Form("Période B"),
    archiver: bool = Form(False),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    pdf_bytes = generate_comparative_report_pdf(
        db,
        date_debut_a,
        date_fin_a,
        date_debut_b,
        date_fin_b,
        generated_by=user.full_name,
        label_a=label_a or "Période A",
        label_b=label_b or "Période B",
    )
    filename = "Rapport comparatif " + date_fin_b.strftime("%d-%m-%Y") + ".pdf"

    if archiver:
        stored_name = f"{uuid.uuid4().hex}.pdf"
        (UPLOAD_ROOT / "documents" / stored_name).write_bytes(pdf_bytes)
        db.add(
            models.Document(
                title=f"Rapport comparatif — {label_a} vs {label_b} (généré le {datetime.date.today().strftime('%d/%m/%Y')})",
                category="rapport",
                file_path=f"documents/{stored_name}",
                original_filename=filename,
                uploaded_by_id=user.id,
            )
        )
        db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Établissements affiliés ----------

@router.get("/etablissements")
def etablissements_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    items = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    return templates.TemplateResponse(
        request,
        "admin/etablissements_list.html",
        {"admin": user, "items": items, "active": "finances"},
    )


@router.get("/etablissements/new")
def etablissements_new_form(
    request: Request,
    user: models.User = Depends(require_finance_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/etablissement_form.html",
        {"admin": user, "item": None, "cotisation_rules": COTISATION_RULES, "active": "finances"},
    )


@router.post("/etablissements/new")
def etablissements_create(
    nom: str = Form(...),
    bureau_local: str = Form(""),
    statut: str = Form("non_subventionne"),
    date_adhesion: str = Form(""),
    contact_email: str = Form(""),
    contact_telephone: str = Form(""),
    latitude: str = Form(""),
    longitude: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    etablissement = models.Etablissement(
        nom=nom,
        bureau_local=bureau_local or None,
        statut=statut if statut in COTISATION_RULES else "non_subventionne",
        date_adhesion=datetime.date.fromisoformat(date_adhesion) if date_adhesion else None,
        contact_email=contact_email or None,
        contact_telephone=contact_telephone or None,
        latitude=float(latitude) if latitude else None,
        longitude=float(longitude) if longitude else None,
    )
    db.add(etablissement)
    db.flush()
    audit.log(db, user, "create", "Établissement", etablissement.id, f"A ajouté l'établissement {etablissement.nom}")
    db.commit()
    return RedirectResponse(url="/admin/etablissements", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/etablissements/{etablissement_id}/edit")
def etablissements_edit_form(
    etablissement_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    item = db.get(models.Etablissement, etablissement_id)
    return templates.TemplateResponse(
        request,
        "admin/etablissement_form.html",
        {"admin": user, "item": item, "cotisation_rules": COTISATION_RULES, "active": "finances"},
    )


@router.post("/etablissements/{etablissement_id}/edit")
def etablissements_update(
    etablissement_id: int,
    nom: str = Form(...),
    bureau_local: str = Form(""),
    statut: str = Form("non_subventionne"),
    date_adhesion: str = Form(""),
    contact_email: str = Form(""),
    contact_telephone: str = Form(""),
    latitude: str = Form(""),
    longitude: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    etablissement = db.get(models.Etablissement, etablissement_id)
    if etablissement:
        etablissement.nom = nom
        etablissement.bureau_local = bureau_local or None
        etablissement.statut = statut if statut in COTISATION_RULES else "non_subventionne"
        etablissement.date_adhesion = (
            datetime.date.fromisoformat(date_adhesion) if date_adhesion else None
        )
        etablissement.contact_email = contact_email or None
        etablissement.contact_telephone = contact_telephone or None
        etablissement.latitude = float(latitude) if latitude else None
        etablissement.longitude = float(longitude) if longitude else None
        audit.log(db, user, "update", "Établissement", etablissement.id, f"A modifié l'établissement {etablissement.nom}")
        db.commit()
    return RedirectResponse(url="/admin/etablissements", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/etablissements/{etablissement_id}/delete")
def etablissements_delete(
    etablissement_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    etablissement = db.get(models.Etablissement, etablissement_id)
    if etablissement:
        audit.log(db, user, "delete", "Établissement", etablissement.id, f"A retiré l'établissement {etablissement.nom}")
        db.delete(etablissement)
        db.commit()
    return RedirectResponse(url="/admin/etablissements", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Droits d'adhésion ----------

@router.get("/adhesions")
def adhesions_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    etablissements = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    paid_ids = {a.etablissement_id for a in db.query(models.Adhesion).all()}
    adhesions = db.query(models.Adhesion).order_by(models.Adhesion.date_paiement.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/adhesions_list.html",
        {
            "admin": user,
            "etablissements": etablissements,
            "paid_ids": paid_ids,
            "adhesions": adhesions,
            "montant": ADHESION_MONTANT,
            "active": "finances",
        },
    )


@router.post("/adhesions/new")
def adhesions_create(
    etablissement_id: int = Form(...),
    date_paiement: datetime.date = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    exists = (
        db.query(models.Adhesion).filter(models.Adhesion.etablissement_id == etablissement_id).first()
    )
    if not exists:
        adhesion = models.Adhesion(
            etablissement_id=etablissement_id,
            montant=ADHESION_MONTANT,
            date_paiement=date_paiement,
            recorded_by_id=user.id,
        )
        db.add(adhesion)
        db.flush()
        etablissement = db.get(models.Etablissement, etablissement_id)
        audit.log(db, user, "create", "Droit d'adhésion", adhesion.id, f"A enregistré le droit d'adhésion de {etablissement.nom if etablissement else etablissement_id}")
        db.commit()
    return RedirectResponse(url="/admin/adhesions", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/adhesions/{adhesion_id}/delete")
def adhesions_delete(
    adhesion_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    adhesion = db.get(models.Adhesion, adhesion_id)
    if adhesion:
        audit.log(db, user, "delete", "Droit d'adhésion", adhesion.id, f"A supprimé un droit d'adhésion (établissement #{adhesion.etablissement_id})")
        db.delete(adhesion)
        db.commit()
    return RedirectResponse(url="/admin/adhesions", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Cotisations annuelles ----------

@router.get("/cotisations")
def cotisations_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    items = db.query(models.Cotisation).order_by(models.Cotisation.annee_scolaire.desc()).all()
    etablissements = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    return templates.TemplateResponse(
        request,
        "admin/cotisations_list.html",
        {
            "admin": user,
            "items": items,
            "etablissements": etablissements,
            "cotisation_rules": COTISATION_RULES,
            "active": "finances",
        },
    )


@router.post("/cotisations/new")
def cotisations_create(
    request: Request,
    etablissement_id: int = Form(...),
    annee_scolaire: str = Form(...),
    montant_paye: int = Form(0),
    date_paiement: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    etablissement = db.get(models.Etablissement, etablissement_id)
    if not etablissement:
        return RedirectResponse(url="/admin/cotisations", status_code=status.HTTP_303_SEE_OTHER)

    existing = (
        db.query(models.Cotisation)
        .filter(
            models.Cotisation.etablissement_id == etablissement_id,
            models.Cotisation.annee_scolaire == annee_scolaire,
        )
        .first()
    )
    rule = cotisation_rule(etablissement.statut)
    part_bureau_local = rule["part_bureau_local"] if montant_paye > 0 else 0

    if existing:
        existing.montant_paye = montant_paye
        existing.part_bureau_local = part_bureau_local
        existing.date_paiement = datetime.date.fromisoformat(date_paiement) if date_paiement else None
        audit.log(db, user, "update", "Cotisation", existing.id, f"A mis à jour la cotisation {annee_scolaire} de {etablissement.nom}")
    else:
        cotisation = models.Cotisation(
            etablissement_id=etablissement_id,
            annee_scolaire=annee_scolaire,
            montant_du=rule["montant_du"],
            montant_paye=montant_paye,
            part_bureau_local=part_bureau_local,
            date_paiement=datetime.date.fromisoformat(date_paiement) if date_paiement else None,
            recorded_by_id=user.id,
        )
        db.add(cotisation)
        db.flush()
        audit.log(db, user, "create", "Cotisation", cotisation.id, f"A enregistré la cotisation {annee_scolaire} de {etablissement.nom}")
    db.commit()
    return RedirectResponse(url="/admin/cotisations", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/cotisations/{cotisation_id}/delete")
def cotisations_delete(
    cotisation_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    cotisation = db.get(models.Cotisation, cotisation_id)
    if cotisation:
        audit.log(db, user, "delete", "Cotisation", cotisation.id, f"A supprimé la cotisation {cotisation.annee_scolaire} (établissement #{cotisation.etablissement_id})")
        db.delete(cotisation)
        db.commit()
    return RedirectResponse(url="/admin/cotisations", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Autres recettes (subventions, dons, ventes, activités, examens) ----------

@router.get("/recettes")
def recettes_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    items = db.query(models.Recette).order_by(models.Recette.date.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/recettes_list.html",
        {"admin": user, "items": items, "categories": RECETTE_CATEGORIES, "active": "finances"},
    )


@router.get("/recettes/new")
def recettes_new_form(
    request: Request,
    user: models.User = Depends(require_finance_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/recette_form.html",
        {
            "admin": user,
            "categories": RECETTE_CATEGORIES,
            "today": datetime.date.today(),
            "active": "finances",
        },
    )


@router.post("/recettes/new")
def recettes_create(
    categorie: str = Form(...),
    libelle: str = Form(...),
    montant: int = Form(...),
    date: datetime.date = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    recette = models.Recette(
        categorie=categorie if categorie in RECETTE_CATEGORIES else "autre",
        libelle=libelle,
        montant=montant,
        date=date,
        recorded_by_id=user.id,
    )
    db.add(recette)
    db.flush()
    audit.log(db, user, "create", "Recette", recette.id, f"A enregistré une recette : {recette.libelle} ({money(recette.montant)})")
    db.commit()
    return RedirectResponse(url="/admin/recettes", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/recettes/{recette_id}/delete")
def recettes_delete(
    recette_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    recette = db.get(models.Recette, recette_id)
    if recette:
        audit.log(db, user, "delete", "Recette", recette.id, f"A supprimé la recette : {recette.libelle} ({money(recette.montant)})")
        db.delete(recette)
        db.commit()
    return RedirectResponse(url="/admin/recettes", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Dépenses ----------

@router.get("/depenses")
def depenses_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    items = db.query(models.Depense).order_by(models.Depense.date.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/depenses_list.html",
        {"admin": user, "items": items, "active": "finances"},
    )


@router.get("/depenses/new")
def depenses_new_form(
    request: Request,
    user: models.User = Depends(require_finance_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/depense_form.html",
        {"admin": user, "today": datetime.date.today(), "active": "finances", "error": None},
    )


@router.post("/depenses/new")
async def depenses_create(
    request: Request,
    libelle: str = Form(...),
    montant: int = Form(...),
    date: datetime.date = Form(...),
    justificatif: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    justificatif_path = None
    justificatif_filename = None
    if justificatif is not None and justificatif.filename:
        try:
            stored_name, original_name = await _save_upload(justificatif, PIECES_DIR, ALLOWED_PIECE_EXT)
            justificatif_path = f"justificatifs/{stored_name}"
            justificatif_filename = original_name
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "admin/depense_form.html",
                {
                    "admin": user,
                    "today": datetime.date.today(),
                    "active": "finances",
                    "error": str(exc),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    depense = models.Depense(
        libelle=libelle,
        montant=montant,
        date=date,
        justificatif_path=justificatif_path,
        justificatif_filename=justificatif_filename,
        recorded_by_id=user.id,
    )
    db.add(depense)
    db.flush()
    audit.log(db, user, "create", "Dépense", depense.id, f"A enregistré une dépense : {depense.libelle} ({money(depense.montant)})")
    db.commit()
    return RedirectResponse(url="/admin/depenses", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/depenses/{depense_id}/justificatif")
def depenses_justificatif(
    depense_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    depense = db.get(models.Depense, depense_id)
    if not depense or not depense.justificatif_path:
        return RedirectResponse(url="/admin/depenses", status_code=status.HTTP_303_SEE_OTHER)
    path = UPLOAD_ROOT / depense.justificatif_path
    media_type = mimetypes.guess_type(depense.justificatif_filename)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=depense.justificatif_filename)


@router.post("/depenses/{depense_id}/delete")
def depenses_delete(
    depense_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    depense = db.get(models.Depense, depense_id)
    if depense:
        if depense.justificatif_path:
            path = UPLOAD_ROOT / depense.justificatif_path
            if path.exists():
                path.unlink()
        audit.log(db, user, "delete", "Dépense", depense.id, f"A supprimé la dépense : {depense.libelle} ({money(depense.montant)})")
        db.delete(depense)
        db.commit()
    return RedirectResponse(url="/admin/depenses", status_code=status.HTTP_303_SEE_OTHER)
