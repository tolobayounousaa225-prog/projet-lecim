import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, models, storage
from ..database import get_db
from ..deps import require_finance_access_web
from ..email_utils import send_email
from ..finances_constants import ADHESION_MONTANT, BUDGET_CATEGORIES, COTISATION_RULES, RECETTE_CATEGORIES, cotisation_rule
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
from .admin_files import ALLOWED_DOCUMENT_EXT, ALLOWED_PHOTO_EXT

router = APIRouter(prefix="/admin", tags=["admin-finances"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


def _safe_float(raw: str) -> float | None:
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _safe_date(raw: str) -> datetime.date | None:
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        return None

PIECES_DIR = "justificatifs"
ALLOWED_PIECE_EXT = ALLOWED_DOCUMENT_EXT | ALLOWED_PHOTO_EXT
ETABLISSEMENT_LOGOS_DIR = "etablissements_logos"


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
    total_ventes_livres = db.query(func.coalesce(func.sum(models.VenteLivre.montant), 0)).scalar()
    total_droits_examens = db.query(func.coalesce(func.sum(models.DroitExamen.montant), 0)).scalar()
    total_depenses = db.query(func.coalesce(func.sum(models.Depense.montant), 0)).scalar()
    solde = (
        total_adhesions + total_cotisations + total_recettes + total_ventes_livres + total_droits_examens
        - total_depenses
    )

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
            "total_ventes_livres": total_ventes_livres,
            "total_droits_examens": total_droits_examens,
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
    pdf_bytes = generate_financial_report_pdf(db, date_debut, date_fin, user=user)
    filename = f"Rapport financier {date_debut.strftime('%d-%m-%Y')} au {date_fin.strftime('%d-%m-%Y')}.pdf"

    if archiver:
        stored_name = storage.store_bytes(db, "documents", pdf_bytes, "application/pdf")
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
        user=user,
        label_a=label_a or "Période A",
        label_b=label_b or "Période B",
    )
    filename = "Rapport comparatif " + date_fin_b.strftime("%d-%m-%Y") + ".pdf"

    if archiver:
        stored_name = storage.store_bytes(db, "documents", pdf_bytes, "application/pdf")
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
    bureau_local: str | None = None,
    categorie: str | None = None,
    district: str | None = None,
    region: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    query = db.query(models.Etablissement)
    if bureau_local:
        query = query.filter(models.Etablissement.bureau_local == bureau_local)
    if categorie in ("membre", "partenaire"):
        query = query.filter(models.Etablissement.categorie == categorie)
    if district:
        query = query.filter(models.Etablissement.district == district)
    if region:
        query = query.filter(models.Etablissement.region == region)
    items = query.order_by(models.Etablissement.nom).all()
    bureaux_locaux = [
        row[0] for row in db.query(models.Etablissement.bureau_local)
        .filter(models.Etablissement.bureau_local.isnot(None))
        .distinct()
        .order_by(models.Etablissement.bureau_local)
        .all()
    ]
    districts = [
        row[0] for row in db.query(models.Etablissement.district)
        .filter(models.Etablissement.district.isnot(None))
        .distinct()
        .order_by(models.Etablissement.district)
        .all()
    ]
    regions = [
        row[0] for row in db.query(models.Etablissement.region)
        .filter(models.Etablissement.region.isnot(None))
        .distinct()
        .order_by(models.Etablissement.region)
        .all()
    ]
    return templates.TemplateResponse(
        request,
        "admin/etablissements_list.html",
        {
            "admin": user,
            "items": items,
            "bureaux_locaux": bureaux_locaux,
            "districts": districts,
            "regions": regions,
            "selected_bureau_local": bureau_local,
            "selected_categorie": categorie,
            "selected_district": district,
            "selected_region": region,
            "active": "etablissements",
            "error": error,
        },
    )


@router.get("/etablissements/export.csv")
def etablissements_export_csv(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    import csv
    import io as _io

    items = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    buffer = _io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Code adhesion", "Nom", "Categorie", "District", "Region", "Commune (bureau local)", "Statut", "Date adhesion", "Telephone", "Email", "Agrement"])
    for e in items:
        writer.writerow([
            e.code_adhesion or "", e.nom,
            "Partenaire" if e.categorie == "partenaire" else "Membre affilie",
            e.district or "", e.region or "", e.bureau_local or "",
            "Subventionne" if e.statut == "subventionne" else "Non subventionne",
            e.date_adhesion.isoformat() if e.date_adhesion else "",
            e.contact_telephone or "", e.contact_email or "", e.numero_agrement or "",
        ])
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="etablissements_affilies.csv"'},
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
async def etablissements_create(
    nom: str = Form(...),
    code_adhesion: str = Form(""),
    bureau_local: str = Form(""),
    district: str = Form(""),
    region: str = Form(""),
    statut: str = Form("non_subventionne"),
    date_adhesion: str = Form(""),
    contact_email: str = Form(""),
    contact_telephone: str = Form(""),
    latitude: str = Form(""),
    longitude: str = Form(""),
    directeur_nom: str = Form(""),
    type_enseignement: str = Form("les_deux"),
    numero_agrement: str = Form(""),
    statut_agrement: str = Form("en_cours"),
    date_expiration_agrement: str = Form(""),
    is_ecole_modele: bool = Form(False),
    categorie: str = Form("membre"),
    logo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    logo_path = None
    if logo is not None and logo.filename:
        try:
            stored_name, _ = await storage.save_upload(db, logo, ETABLISSEMENT_LOGOS_DIR, ALLOWED_PHOTO_EXT)
            logo_path = f"etablissements_logos/{stored_name}"
        except ValueError:
            pass

    etablissement = models.Etablissement(
        nom=nom,
        code_adhesion=code_adhesion or None,
        bureau_local=bureau_local or None,
        district=district or None,
        region=region or None,
        statut=statut if statut in COTISATION_RULES else "non_subventionne",
        date_adhesion=_safe_date(date_adhesion),
        contact_email=contact_email or None,
        contact_telephone=contact_telephone or None,
        latitude=_safe_float(latitude),
        longitude=_safe_float(longitude),
        directeur_nom=directeur_nom or None,
        type_enseignement=type_enseignement if type_enseignement in {"primaire", "secondaire", "les_deux"} else "les_deux",
        numero_agrement=numero_agrement or None,
        statut_agrement=statut_agrement if statut_agrement in {"agree", "en_cours", "expire"} else "en_cours",
        date_expiration_agrement=_safe_date(date_expiration_agrement),
        is_ecole_modele=is_ecole_modele,
        categorie=categorie if categorie in {"membre", "partenaire"} else "membre",
        logo_path=logo_path,
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
    if not item:
        return RedirectResponse(url="/admin/etablissements", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "admin/etablissement_form.html",
        {"admin": user, "item": item, "cotisation_rules": COTISATION_RULES, "active": "finances"},
    )


@router.post("/etablissements/{etablissement_id}/edit")
async def etablissements_update(
    etablissement_id: int,
    nom: str = Form(...),
    code_adhesion: str = Form(""),
    bureau_local: str = Form(""),
    district: str = Form(""),
    region: str = Form(""),
    statut: str = Form("non_subventionne"),
    date_adhesion: str = Form(""),
    contact_email: str = Form(""),
    contact_telephone: str = Form(""),
    latitude: str = Form(""),
    longitude: str = Form(""),
    directeur_nom: str = Form(""),
    type_enseignement: str = Form("les_deux"),
    numero_agrement: str = Form(""),
    statut_agrement: str = Form("en_cours"),
    date_expiration_agrement: str = Form(""),
    is_ecole_modele: bool = Form(False),
    categorie: str = Form("membre"),
    logo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    etablissement = db.get(models.Etablissement, etablissement_id)
    if etablissement:
        if logo is not None and logo.filename:
            try:
                stored_name, _ = await storage.save_upload(db, logo, ETABLISSEMENT_LOGOS_DIR, ALLOWED_PHOTO_EXT)
                storage.delete_stored_file(db, etablissement.logo_path)
                etablissement.logo_path = f"etablissements_logos/{stored_name}"
            except ValueError:
                pass

        etablissement.nom = nom
        etablissement.code_adhesion = code_adhesion or None
        etablissement.bureau_local = bureau_local or None
        etablissement.district = district or None
        etablissement.region = region or None
        etablissement.statut = statut if statut in COTISATION_RULES else "non_subventionne"
        etablissement.date_adhesion = _safe_date(date_adhesion)
        etablissement.contact_email = contact_email or None
        etablissement.contact_telephone = contact_telephone or None
        etablissement.latitude = _safe_float(latitude)
        etablissement.longitude = _safe_float(longitude)
        etablissement.directeur_nom = directeur_nom or None
        etablissement.type_enseignement = type_enseignement if type_enseignement in {"primaire", "secondaire", "les_deux"} else "les_deux"
        etablissement.numero_agrement = numero_agrement or None
        etablissement.statut_agrement = statut_agrement if statut_agrement in {"agree", "en_cours", "expire"} else "en_cours"
        etablissement.date_expiration_agrement = _safe_date(date_expiration_agrement)
        etablissement.is_ecole_modele = is_ecole_modele
        etablissement.categorie = categorie if categorie in {"membre", "partenaire"} else "membre"
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
        blockers = []
        dependent_checks = [
            (models.Adhesion, "des adhésions"),
            (models.Cotisation, "des cotisations"),
            (models.Effectif, "des effectifs déclarés"),
            (models.Enseignant, "des enseignants"),
            (models.ResultatExamen, "des résultats d'examens"),
            (models.DroitExamen, "des droits d'examens"),
            (models.RessourcePedagogique, "des ressources pédagogiques"),
            (models.DemandeEtablissement, "des demandes"),
            (models.MessageEtablissement, "des messages"),
            (models.CarteScolaire, "des cartes scolaires"),
            (models.User, "un compte portail"),
        ]
        for model_cls, label in dependent_checks:
            if db.query(model_cls).filter(model_cls.etablissement_id == etablissement_id).first():
                blockers.append(label)
        if blockers:
            message = f"Impossible de supprimer « {etablissement.nom} » : il a encore {', '.join(blockers)} rattaché(e)s. Retirez-les d'abord."
            return RedirectResponse(url=f"/admin/etablissements?error={quote(message)}", status_code=status.HTTP_303_SEE_OTHER)
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
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return RedirectResponse(url="/admin/adhesions", status_code=status.HTTP_303_SEE_OTHER)
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
    # Proportionnel au montant effectivement versé — un paiement partiel ne doit
    # jamais générer une part bureau local supérieure à ce qui a été encaissé
    # (auparavant, le moindre acompte déclenchait la part statutaire complète).
    part_bureau_local = (
        round(rule["part_bureau_local"] * min(montant_paye, rule["montant_du"]) / rule["montant_du"])
        if montant_paye > 0 and rule["montant_du"]
        else 0
    )

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
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return RedirectResponse(url="/admin/cotisations", status_code=status.HTTP_303_SEE_OTHER)
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


# ---------- Ventes de livres ----------

@router.get("/ventes-livres")
def ventes_livres_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    items = db.query(models.VenteLivre).order_by(models.VenteLivre.date.desc()).all()
    total = sum(v.montant for v in items)
    return templates.TemplateResponse(
        request,
        "admin/ventes_livres_list.html",
        {"admin": user, "items": items, "total": total, "active": "finances"},
    )


@router.get("/ventes-livres/new")
def ventes_livres_new_form(
    request: Request,
    user: models.User = Depends(require_finance_access_web),
):
    return templates.TemplateResponse(
        request,
        "admin/vente_livre_form.html",
        {"admin": user, "today": datetime.date.today(), "active": "finances"},
    )


@router.post("/ventes-livres/new")
def ventes_livres_create(
    titre: str = Form(...),
    quantite: int = Form(1),
    montant: int = Form(...),
    date: datetime.date = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    vente = models.VenteLivre(titre=titre, quantite=quantite, montant=montant, date=date, recorded_by_id=user.id)
    db.add(vente)
    db.flush()
    audit.log(db, user, "create", "Vente de livre", vente.id, f"A enregistré une vente de livre : {vente.titre} ({money(vente.montant)})")
    db.commit()
    return RedirectResponse(url="/admin/ventes-livres", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ventes-livres/{vente_id}/delete")
def ventes_livres_delete(
    vente_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    vente = db.get(models.VenteLivre, vente_id)
    if vente:
        audit.log(db, user, "delete", "Vente de livre", vente.id, f"A supprimé la vente de livre : {vente.titre} ({money(vente.montant)})")
        db.delete(vente)
        db.commit()
    return RedirectResponse(url="/admin/ventes-livres", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Droits d'examens ----------

@router.get("/droits-examens")
def droits_examens_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    items = db.query(models.DroitExamen).order_by(models.DroitExamen.date.desc()).all()
    total = sum(d.montant for d in items)
    return templates.TemplateResponse(
        request,
        "admin/droits_examens_list.html",
        {"admin": user, "items": items, "total": total, "active": "finances"},
    )


@router.get("/droits-examens/new")
def droits_examens_new_form(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    etablissements = db.query(models.Etablissement).order_by(models.Etablissement.nom).all()
    return templates.TemplateResponse(
        request,
        "admin/droit_examen_form.html",
        {"admin": user, "etablissements": etablissements, "today": datetime.date.today(), "active": "finances"},
    )


@router.post("/droits-examens/new")
def droits_examens_create(
    libelle: str = Form(...),
    type_examen: str = Form(""),
    etablissement_id: str = Form(""),
    montant: int = Form(...),
    date: datetime.date = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    droit = models.DroitExamen(
        libelle=libelle,
        type_examen=type_examen or None,
        etablissement_id=int(etablissement_id) if etablissement_id else None,
        montant=montant,
        date=date,
        recorded_by_id=user.id,
    )
    db.add(droit)
    db.flush()
    audit.log(db, user, "create", "Droit d'examen", droit.id, f"A enregistré un droit d'examen : {droit.libelle} ({money(droit.montant)})")
    db.commit()
    return RedirectResponse(url="/admin/droits-examens", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/droits-examens/{droit_id}/delete")
def droits_examens_delete(
    droit_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    droit = db.get(models.DroitExamen, droit_id)
    if droit:
        audit.log(db, user, "delete", "Droit d'examen", droit.id, f"A supprimé le droit d'examen : {droit.libelle} ({money(droit.montant)})")
        db.delete(droit)
        db.commit()
    return RedirectResponse(url="/admin/droits-examens", status_code=status.HTTP_303_SEE_OTHER)


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
            stored_name, original_name = await storage.save_upload(db, justificatif, PIECES_DIR, ALLOWED_PIECE_EXT)
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
    stored = storage.get_stored_file(db, depense.justificatif_path)
    if not stored:
        return RedirectResponse(url="/admin/depenses", status_code=status.HTTP_303_SEE_OTHER)
    return Response(
        content=stored.data,
        media_type=stored.content_type,
        headers={"Content-Disposition": f'attachment; filename="{depense.justificatif_filename}"'},
    )


@router.post("/depenses/{depense_id}/delete")
def depenses_delete(
    depense_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    depense = db.get(models.Depense, depense_id)
    if depense:
        storage.delete_stored_file(db, depense.justificatif_path)
        audit.log(db, user, "delete", "Dépense", depense.id, f"A supprimé la dépense : {depense.libelle} ({money(depense.montant)})")
        db.delete(depense)
        db.commit()
    return RedirectResponse(url="/admin/depenses", status_code=status.HTTP_303_SEE_OTHER)


# ---------- Budget prévisionnel vs réalisé ----------

@router.get("/finances/budget")
def budget_list(
    request: Request,
    annee_scolaire: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    annee = annee_scolaire or current_annee_scolaire()
    realise_par_annee = {d["annee"]: d for d in multi_year_financial_summary(db)}
    realise_annee = realise_par_annee.get(annee, {})
    previsions = {
        b.categorie: b
        for b in db.query(models.BudgetPrevisionnel)
        .filter(models.BudgetPrevisionnel.annee_scolaire == annee)
        .all()
    }

    # "depenses" est un flux sortant : l'additionner aux entrées fausserait le
    # total (c'était le bug — les dépenses gonflaient artificiellement le total
    # prévu/réalisé). On sépare donc entrées et dépenses, et on calcule un solde.
    lignes = []
    total_entrees_prevu = 0
    total_entrees_realise = 0
    depenses_prevu = 0
    depenses_realise = 0
    for cle, label in BUDGET_CATEGORIES.items():
        prevu = previsions[cle].montant_prevu if cle in previsions else 0
        realise = realise_annee.get(cle, 0)
        taux = round(realise / prevu * 100) if prevu else None
        lignes.append(
            {
                "categorie": cle,
                "label": label,
                "prevu": prevu,
                "realise": realise,
                "ecart": realise - prevu,
                "taux": taux,
            }
        )
        if cle == "depenses":
            depenses_prevu = prevu
            depenses_realise = realise
        else:
            total_entrees_prevu += prevu
            total_entrees_realise += realise

    solde_prevu = total_entrees_prevu - depenses_prevu
    solde_realise = total_entrees_realise - depenses_realise

    annees_disponibles = sorted(
        set(realise_par_annee.keys())
        | {b.annee_scolaire for b in db.query(models.BudgetPrevisionnel.annee_scolaire).distinct().all()}
        | {current_annee_scolaire()},
        reverse=True,
    )

    return templates.TemplateResponse(
        request,
        "admin/finances_budget.html",
        {
            "admin": user,
            "active": "finances",
            "annee": annee,
            "annees_disponibles": annees_disponibles,
            "lignes": lignes,
            "total_entrees_prevu": total_entrees_prevu,
            "total_entrees_realise": total_entrees_realise,
            "total_entrees_taux": round(total_entrees_realise / total_entrees_prevu * 100) if total_entrees_prevu else None,
            "depenses_prevu": depenses_prevu,
            "depenses_realise": depenses_realise,
            "solde_prevu": solde_prevu,
            "solde_realise": solde_realise,
        },
    )


@router.post("/finances/budget")
async def budget_save(
    request: Request,
    annee_scolaire: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    form = await request.form()
    for cle in BUDGET_CATEGORIES:
        raw = str(form.get(f"montant_{cle}", "")).strip()
        montant = int(raw) if raw.isdigit() else 0
        existing = (
            db.query(models.BudgetPrevisionnel)
            .filter(
                models.BudgetPrevisionnel.annee_scolaire == annee_scolaire,
                models.BudgetPrevisionnel.categorie == cle,
            )
            .first()
        )
        if existing:
            existing.montant_prevu = montant
        else:
            db.add(
                models.BudgetPrevisionnel(
                    annee_scolaire=annee_scolaire,
                    categorie=cle,
                    montant_prevu=montant,
                    recorded_by_id=user.id,
                )
            )
    audit.log(db, user, "update", "Budget prévisionnel", annee_scolaire, f"A mis à jour le budget prévisionnel {annee_scolaire}")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return RedirectResponse(
        url=f"/admin/finances/budget?annee_scolaire={annee_scolaire}", status_code=status.HTTP_303_SEE_OTHER
    )
