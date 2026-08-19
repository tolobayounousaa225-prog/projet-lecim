import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, models
from ..attestations_pdf import generate_etablissement_attestation_pdf
from ..database import get_db
from ..deps import require_finance_access_web
from ..postes import ETAB_MODULES
from ..security import hash_password, password_policy_error

router = APIRouter(prefix="/admin", tags=["admin-etablissement-portail"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/etablissements/{etablissement_id}/compte")
def etablissement_compte(
    etablissement_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    etablissement = db.get(models.Etablissement, etablissement_id)
    if not etablissement:
        return RedirectResponse(url="/admin/etablissements", status_code=status.HTTP_303_SEE_OTHER)
    comptes = (
        db.query(models.User)
        .filter(models.User.etablissement_id == etablissement_id)
        .order_by(models.User.is_etablissement_titulaire.desc(), models.User.created_at)
        .all()
    )
    titulaire_existe = any(c.is_etablissement_titulaire for c in comptes)
    return templates.TemplateResponse(
        request,
        "admin/etablissement_compte.html",
        {
            "admin": user,
            "etablissement": etablissement,
            "comptes": comptes,
            "titulaire_existe": titulaire_existe,
            "etab_modules": ETAB_MODULES,
            "active": "finances",
            "error": None,
        },
    )


@router.post("/etablissements/{etablissement_id}/compte/new")
async def etablissement_compte_create(
    etablissement_id: int,
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("titulaire"),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    etablissement = db.get(models.Etablissement, etablissement_id)
    if not etablissement:
        return RedirectResponse(url="/admin/etablissements", status_code=status.HTTP_303_SEE_OTHER)

    form = await request.form()
    modules = [m for m in form.getlist("modules") if m in ETAB_MODULES]

    comptes = db.query(models.User).filter(models.User.etablissement_id == etablissement_id).all()
    titulaire_existe = any(c.is_etablissement_titulaire for c in comptes)

    existing = db.query(models.User).filter(models.User.email == email).first()
    password_error = password_policy_error(password)
    if existing or password_error or (role == "titulaire" and titulaire_existe):
        error = (
            "Un compte existe déjà avec cet e-mail." if existing
            else password_error if password_error
            else "Un compte titulaire existe déjà pour cet établissement — créez un compte secrétaire à la place."
        )
        return templates.TemplateResponse(
            request,
            "admin/etablissement_compte.html",
            {
                "admin": user,
                "etablissement": etablissement,
                "comptes": comptes,
                "titulaire_existe": titulaire_existe,
                "etab_modules": ETAB_MODULES,
                "active": "finances",
                "error": error,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    is_titulaire = role == "titulaire"
    compte = models.User(
        full_name=full_name,
        email=email,
        hashed_password=hash_password(password),
        access_level="bureau",
        etablissement_id=etablissement_id,
        is_etablissement_titulaire=is_titulaire,
        allowed_modules="" if is_titulaire else ",".join(modules),
    )
    db.add(compte)
    try:
        db.flush()
    except IntegrityError:
        # Course avec une autre création concurrente (même e-mail, ou même
        # établissement pour deux titulaires à la fois) — l'index/la contrainte
        # unique a bloqué la seconde requête plutôt que de laisser un doublon.
        db.rollback()
        comptes = db.query(models.User).filter(models.User.etablissement_id == etablissement_id).all()
        return templates.TemplateResponse(
            request,
            "admin/etablissement_compte.html",
            {
                "admin": user,
                "etablissement": etablissement,
                "comptes": comptes,
                "titulaire_existe": any(c.is_etablissement_titulaire for c in comptes),
                "etab_modules": ETAB_MODULES,
                "active": "finances",
                "error": "Conflit détecté (e-mail ou titulaire déjà pris entre-temps) — veuillez réessayer.",
            },
            status_code=status.HTTP_409_CONFLICT,
        )
    role_label = "titulaire" if is_titulaire else "secrétaire"
    audit.log(db, user, "create", "Compte établissement", compte.id, f"A créé un compte {role_label} pour {etablissement.nom} ({email})")
    db.commit()
    return RedirectResponse(url=f"/admin/etablissements/{etablissement_id}/compte", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/etablissements/{etablissement_id}/compte/{compte_id}/delete")
def etablissement_compte_delete(
    etablissement_id: int,
    compte_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    compte = db.get(models.User, compte_id)
    if compte and compte.etablissement_id == etablissement_id:
        audit.log(db, user, "delete", "Compte établissement", compte.id, f"A révoqué le compte {compte.email} de l'établissement #{etablissement_id}")
        db.delete(compte)
        db.commit()
    return RedirectResponse(url=f"/admin/etablissements/{etablissement_id}/compte", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/etablissements/{etablissement_id}/attestation/pdf")
def etablissement_attestation_pdf(
    etablissement_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    etablissement = db.get(models.Etablissement, etablissement_id)
    if not etablissement:
        return RedirectResponse(url="/admin/etablissements", status_code=status.HTTP_303_SEE_OTHER)
    pdf_bytes = generate_etablissement_attestation_pdf(etablissement)
    filename = f"attestation_affiliation_{etablissement.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Demandes soumises par les établissements ----------

@router.get("/demandes-etablissements")
def demandes_list(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    items = db.query(models.DemandeEtablissement).order_by(models.DemandeEtablissement.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "admin/demandes_etablissements_list.html",
        {"admin": user, "items": items, "active": "demandes_etablissements"},
    )


@router.post("/demandes-etablissements/{demande_id}/repondre")
def demande_repondre(
    demande_id: int,
    reponse: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_finance_access_web),
):
    demande = db.get(models.DemandeEtablissement, demande_id)
    if demande:
        demande.reponse = reponse or None
        demande.statut = "traitee"
        demande.traitee_at = datetime.datetime.utcnow()
        audit.log(db, user, "update", "Demande établissement", demande.id, f"A répondu à la demande « {demande.objet} » de {demande.etablissement.nom}")
        db.commit()
    return RedirectResponse(url="/admin/demandes-etablissements", status_code=status.HTTP_303_SEE_OTHER)
