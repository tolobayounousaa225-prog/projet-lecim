import datetime
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, models, storage
from ..attestations_pdf import generate_etablissement_attestation_pdf
from ..card_pdf import generate_student_card_pdf
from ..database import get_db
from ..deps import (
    require_etab_annonces_web,
    require_etab_cartes_web,
    require_etab_cotisation_web,
    require_etab_demandes_web,
    require_etab_effectifs_web,
    require_etab_enseignants_web,
    require_etab_messagerie_web,
    require_etab_resultats_web,
    require_etablissement_login_web,
)
from ..finances_constants import cotisation_rule
from ..notifications import notify_cartes_scolaires_gestionnaires, notify_messagerie_gestionnaires
from ..reports import current_annee_scolaire
from ..security import hash_password, password_policy_error, verify_password
from .admin_files import ALLOWED_PHOTO_EXT

TYPES_EXAMEN = ["CEPE", "BEPC", "BAC"]
CARTES_SCOLAIRES_PHOTOS_DIR = "cartes_scolaires"

router = APIRouter(tags=["etablissement-portal"])

templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/etablissement/login")
def etablissement_login_page(request: Request):
    return templates.TemplateResponse(request, "etablissement_login.html", {"error": None})


@router.get("/etablissement/logout")
def etablissement_logout():
    response = RedirectResponse(url="/etablissement/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response


@router.get("/etablissement")
def etablissement_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etablissement_login_web),
):
    etablissement = user.etablissement
    annee = current_annee_scolaire()
    cotisation = (
        db.query(models.Cotisation)
        .filter(models.Cotisation.etablissement_id == etablissement.id, models.Cotisation.annee_scolaire == annee)
        .first()
    )
    counts = {
        "resultats": db.query(models.ResultatExamen)
        .filter(models.ResultatExamen.etablissement_id == etablissement.id, models.ResultatExamen.is_published.is_(True))
        .count(),
        "enseignants": db.query(models.Enseignant).filter(models.Enseignant.etablissement_id == etablissement.id).count(),
        "demandes_ouvertes": db.query(models.DemandeEtablissement)
        .filter(models.DemandeEtablissement.etablissement_id == etablissement.id, models.DemandeEtablissement.statut == "nouvelle")
        .count(),
    }
    return templates.TemplateResponse(
        request,
        "etablissement/dashboard.html",
        {
            "user": user,
            "etablissement": etablissement,
            "annee": annee,
            "cotisation": cotisation,
            "counts": counts,
            "active": "dashboard",
        },
    )


@router.get("/etablissement/mon-compte/mot-de-passe")
def etablissement_change_password_page(
    request: Request,
    user: models.User = Depends(require_etablissement_login_web),
):
    return templates.TemplateResponse(
        request,
        "etablissement/change_password.html",
        {"user": user, "etablissement": user.etablissement, "active": "mon_compte", "error": None, "success": None},
    )


@router.post("/etablissement/mon-compte/mot-de-passe")
def etablissement_change_password_submit(
    request: Request,
    mot_de_passe_actuel: str = Form(...),
    nouveau_mot_de_passe: str = Form(...),
    confirmation: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etablissement_login_web),
):
    error = None
    if not verify_password(mot_de_passe_actuel, user.hashed_password):
        error = "Mot de passe actuel incorrect."
    elif nouveau_mot_de_passe != confirmation:
        error = "Les deux mots de passe ne correspondent pas."
    else:
        error = password_policy_error(nouveau_mot_de_passe)

    if error:
        return templates.TemplateResponse(
            request,
            "etablissement/change_password.html",
            {"user": user, "etablissement": user.etablissement, "active": "mon_compte", "error": error, "success": None},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user.hashed_password = hash_password(nouveau_mot_de_passe)
    db.query(models.PasswordResetRequest).filter(
        models.PasswordResetRequest.user_id == user.id, models.PasswordResetRequest.used.is_(False)
    ).update({"used": True})
    audit.log(db, user, "update", "Mot de passe", user.id, f"{user.full_name} a changé son mot de passe")
    db.commit()
    return templates.TemplateResponse(
        request,
        "etablissement/change_password.html",
        {"user": user, "etablissement": user.etablissement, "active": "mon_compte", "error": None, "success": "Mot de passe mis à jour."},
    )


@router.get("/etablissement/export-donnees")
def etablissement_export_donnees(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etablissement_login_web),
):
    """Export RGPD : toutes les données propres à l'établissement, en un fichier
    JSON téléchargeable, pour que l'établissement garde une copie de ce qu'il a
    déclaré sur la plateforme."""
    etablissement = user.etablissement

    def d(value):
        return value.isoformat() if value is not None else None

    payload = {
        "genere_le": datetime.datetime.utcnow().isoformat(),
        "etablissement": {
            "nom": etablissement.nom,
            "code_adhesion": etablissement.code_adhesion,
            "bureau_local": etablissement.bureau_local,
            "district": etablissement.district,
            "region": etablissement.region,
            "statut_cotisation": etablissement.statut,
            "date_adhesion": d(etablissement.date_adhesion),
            "contact_email": etablissement.contact_email,
            "contact_telephone": etablissement.contact_telephone,
            "directeur_nom": etablissement.directeur_nom,
            "type_enseignement": etablissement.type_enseignement,
            "numero_agrement": etablissement.numero_agrement,
            "statut_agrement": etablissement.statut_agrement,
            "date_expiration_agrement": d(etablissement.date_expiration_agrement),
        },
        "effectifs": [
            {
                "annee_scolaire": e.annee_scolaire,
                "niveau": e.niveau,
                "nombre_garcons": e.nombre_garcons,
                "nombre_filles": e.nombre_filles,
            }
            for e in db.query(models.Effectif).filter(models.Effectif.etablissement_id == etablissement.id).all()
        ],
        "resultats_examens": [
            {
                "annee_scolaire": r.annee_scolaire,
                "type_examen": r.type_examen,
                "nombre_inscrits": r.nombre_inscrits,
                "nombre_admis": r.nombre_admis,
                "is_published": r.is_published,
            }
            for r in db.query(models.ResultatExamen).filter(models.ResultatExamen.etablissement_id == etablissement.id).all()
        ],
        "enseignants": [
            {
                "full_name": ens.full_name,
                "matiere": ens.matiere,
                "diplome": ens.diplome,
                "telephone": ens.telephone,
                "email": ens.email,
                "date_debut": d(ens.date_debut),
            }
            for ens in db.query(models.Enseignant).filter(models.Enseignant.etablissement_id == etablissement.id).all()
        ],
        "cartes_scolaires": [
            {
                "eleve_nom": c.eleve_nom,
                "classe": c.classe,
                "annee_scolaire": c.annee_scolaire,
                "matricule": c.matricule,
                "status": c.status,
                "date_soumission": d(c.date_soumission),
            }
            for c in db.query(models.CarteScolaire).filter(models.CarteScolaire.etablissement_id == etablissement.id).all()
        ],
        "cotisations": [
            {
                "annee_scolaire": c.annee_scolaire,
                "montant_du": c.montant_du,
                "montant_paye": c.montant_paye,
                "date_paiement": d(c.date_paiement),
            }
            for c in db.query(models.Cotisation).filter(models.Cotisation.etablissement_id == etablissement.id).all()
        ],
        "demandes": [
            {
                "objet": dem.objet,
                "message": dem.message,
                "reponse": dem.reponse,
                "statut": dem.statut,
                "created_at": d(dem.created_at),
            }
            for dem in db.query(models.DemandeEtablissement).filter(models.DemandeEtablissement.etablissement_id == etablissement.id).all()
        ],
        "messages": [
            {
                "expediteur": "LECIM" if m.is_from_ben else etablissement.nom,
                "message": m.body,
                "date": d(m.created_at),
            }
            for m in db.query(models.MessageEtablissement).filter(models.MessageEtablissement.etablissement_id == etablissement.id).all()
        ],
    }

    filename = f"lecim-export-{etablissement.nom.replace(' ', '_')}-{datetime.date.today().isoformat()}.json"
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/etablissement/attestation/pdf")
def etablissement_attestation_pdf(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etablissement_login_web),
):
    etablissement = user.etablissement
    pdf_bytes = generate_etablissement_attestation_pdf(etablissement)
    filename = f"attestation_affiliation_{etablissement.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/etablissement/messagerie")
def etablissement_messagerie(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_messagerie_web),
):
    etablissement = user.etablissement
    messages = (
        db.query(models.MessageEtablissement)
        .filter(models.MessageEtablissement.etablissement_id == etablissement.id)
        .order_by(models.MessageEtablissement.created_at)
        .all()
    )
    unread = [m for m in messages if m.is_from_ben and not m.is_read_by_etablissement]
    for m in unread:
        m.is_read_by_etablissement = True
    if unread:
        db.commit()
    return templates.TemplateResponse(
        request,
        "etablissement/messagerie.html",
        {"user": user, "etablissement": etablissement, "messages": messages, "active": "messagerie"},
    )


@router.post("/etablissement/messagerie/new")
def etablissement_messagerie_send(
    body: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_messagerie_web),
):
    etablissement = user.etablissement
    message = models.MessageEtablissement(
        etablissement_id=etablissement.id,
        sender_id=user.id,
        is_from_ben=False,
        body=body,
    )
    db.add(message)
    notify_messagerie_gestionnaires(
        db, f"Nouveau message de {etablissement.nom}.", link=f"/admin/messagerie/{etablissement.id}",
    )
    db.commit()
    return RedirectResponse(url="/etablissement/messagerie", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/etablissement/annonces")
def etablissement_annonces(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_annonces_web),
):
    etablissement = user.etablissement
    items = []
    if etablissement.delegation_id:
        items = (
            db.query(models.AnnonceDelegation)
            .filter(models.AnnonceDelegation.delegation_id == etablissement.delegation_id)
            .order_by(models.AnnonceDelegation.created_at.desc())
            .all()
        )
    return templates.TemplateResponse(
        request,
        "etablissement/annonces.html",
        {"user": user, "etablissement": etablissement, "items": items, "active": "annonces"},
    )


@router.get("/etablissement/cotisation")
def etablissement_cotisation(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_cotisation_web),
):
    etablissement = user.etablissement
    cotisations = (
        db.query(models.Cotisation)
        .filter(models.Cotisation.etablissement_id == etablissement.id)
        .order_by(models.Cotisation.annee_scolaire.desc())
        .all()
    )
    adhesion = db.query(models.Adhesion).filter(models.Adhesion.etablissement_id == etablissement.id).first()
    rule = cotisation_rule(etablissement.statut)
    return templates.TemplateResponse(
        request,
        "etablissement/cotisation.html",
        {
            "user": user,
            "etablissement": etablissement,
            "cotisations": cotisations,
            "adhesion": adhesion,
            "rule": rule,
            "active": "cotisation",
        },
    )


@router.get("/etablissement/resultats")
def etablissement_resultats(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_resultats_web),
):
    etablissement = user.etablissement
    items = (
        db.query(models.ResultatExamen)
        .filter(models.ResultatExamen.etablissement_id == etablissement.id)
        .order_by(models.ResultatExamen.annee_scolaire.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "etablissement/resultats.html",
        {
            "user": user,
            "etablissement": etablissement,
            "items": items,
            "types_examen": TYPES_EXAMEN,
            "annee_par_defaut": current_annee_scolaire(),
            "active": "resultats",
        },
    )


@router.post("/etablissement/resultats/new")
def etablissement_resultats_create(
    annee_scolaire: str = Form(...),
    type_examen: str = Form(...),
    nombre_inscrits: int = Form(0),
    nombre_admis: int = Form(0),
    nombre_admis_garcons: int = Form(0),
    nombre_admis_filles: int = Form(0),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_resultats_web),
):
    etablissement = user.etablissement
    admis = min(nombre_admis, nombre_inscrits) if nombre_inscrits else nombre_admis
    resultat = models.ResultatExamen(
        etablissement_id=etablissement.id,
        annee_scolaire=annee_scolaire,
        type_examen=type_examen,
        nombre_inscrits=nombre_inscrits,
        nombre_admis=admis,
        nombre_admis_garcons=min(nombre_admis_garcons, admis) if admis else 0,
        nombre_admis_filles=min(nombre_admis_filles, admis) if admis else 0,
        is_published=False,
        recorded_by_id=user.id,
    )
    db.add(resultat)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return RedirectResponse(url="/etablissement/resultats", status_code=status.HTTP_303_SEE_OTHER)
    audit.log(
        db, user, "create", "Résultat d'examen", resultat.id,
        f"{etablissement.nom} a déclaré son résultat {type_examen} {annee_scolaire} (en attente de validation)",
    )
    db.commit()
    return RedirectResponse(url="/etablissement/resultats", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/etablissement/enseignants")
def etablissement_enseignants(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_enseignants_web),
):
    etablissement = user.etablissement
    items = (
        db.query(models.Enseignant)
        .filter(models.Enseignant.etablissement_id == etablissement.id)
        .order_by(models.Enseignant.full_name)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "etablissement/enseignants.html",
        {"user": user, "etablissement": etablissement, "items": items, "active": "enseignants"},
    )


@router.post("/etablissement/enseignants/new")
def etablissement_enseignants_create(
    full_name: str = Form(...),
    matiere: str = Form(""),
    diplome: str = Form(""),
    telephone: str = Form(""),
    email: str = Form(""),
    date_debut: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_enseignants_web),
):
    etablissement = user.etablissement
    enseignant = models.Enseignant(
        etablissement_id=etablissement.id,
        full_name=full_name,
        matiere=matiere or None,
        diplome=diplome or None,
        telephone=telephone or None,
        email=email or None,
        date_debut=datetime.date.fromisoformat(date_debut) if date_debut else None,
    )
    db.add(enseignant)
    db.flush()
    audit.log(db, user, "create", "Enseignant", enseignant.id, f"{etablissement.nom} a ajouté l'enseignant {full_name}")
    db.commit()
    return RedirectResponse(url="/etablissement/enseignants", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/etablissement/enseignants/{enseignant_id}/edit")
def etablissement_enseignant_edit_page(
    enseignant_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_enseignants_web),
):
    etablissement = user.etablissement
    item = db.get(models.Enseignant, enseignant_id)
    if not item or item.etablissement_id != etablissement.id:
        return RedirectResponse(url="/etablissement/enseignants", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request,
        "etablissement/enseignant_form.html",
        {"user": user, "etablissement": etablissement, "item": item, "active": "enseignants"},
    )


@router.post("/etablissement/enseignants/{enseignant_id}/edit")
def etablissement_enseignant_edit(
    enseignant_id: int,
    full_name: str = Form(...),
    matiere: str = Form(""),
    diplome: str = Form(""),
    telephone: str = Form(""),
    email: str = Form(""),
    date_debut: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_enseignants_web),
):
    etablissement = user.etablissement
    item = db.get(models.Enseignant, enseignant_id)
    if item and item.etablissement_id == etablissement.id:
        item.full_name = full_name
        item.matiere = matiere or None
        item.diplome = diplome or None
        item.telephone = telephone or None
        item.email = email or None
        item.date_debut = datetime.date.fromisoformat(date_debut) if date_debut else None
        audit.log(db, user, "update", "Enseignant", item.id, f"{etablissement.nom} a modifié l'enseignant {full_name}")
        db.commit()
    return RedirectResponse(url="/etablissement/enseignants", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/etablissement/enseignants/{enseignant_id}/delete")
def etablissement_enseignant_delete(
    enseignant_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_enseignants_web),
):
    etablissement = user.etablissement
    item = db.get(models.Enseignant, enseignant_id)
    if item and item.etablissement_id == etablissement.id:
        audit.log(db, user, "delete", "Enseignant", item.id, f"{etablissement.nom} a retiré l'enseignant {item.full_name}")
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/etablissement/enseignants", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/etablissement/effectifs")
def etablissement_effectifs(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_effectifs_web),
):
    etablissement = user.etablissement
    items = (
        db.query(models.Effectif)
        .filter(models.Effectif.etablissement_id == etablissement.id)
        .order_by(models.Effectif.annee_scolaire.desc(), models.Effectif.niveau)
        .all()
    )
    niveaux = (
        ["primaire"] if etablissement.type_enseignement == "primaire"
        else ["secondaire"] if etablissement.type_enseignement == "secondaire"
        else ["primaire", "secondaire"]
    )
    return templates.TemplateResponse(
        request,
        "etablissement/effectifs.html",
        {
            "user": user,
            "etablissement": etablissement,
            "items": items,
            "niveaux": niveaux,
            "annee_par_defaut": current_annee_scolaire(),
            "active": "effectifs",
        },
    )


@router.post("/etablissement/effectifs/new")
def etablissement_effectifs_create(
    annee_scolaire: str = Form(...),
    niveau: str = Form(...),
    nombre_garcons: int = Form(0),
    nombre_filles: int = Form(0),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_effectifs_web),
):
    etablissement = user.etablissement
    existant = (
        db.query(models.Effectif)
        .filter(
            models.Effectif.etablissement_id == etablissement.id,
            models.Effectif.annee_scolaire == annee_scolaire,
            models.Effectif.niveau == niveau,
        )
        .first()
    )
    if existant:
        existant.nombre_garcons = nombre_garcons
        existant.nombre_filles = nombre_filles
        existant.recorded_by_id = user.id
        action, effectif = "update", existant
    else:
        effectif = models.Effectif(
            etablissement_id=etablissement.id,
            annee_scolaire=annee_scolaire,
            niveau=niveau,
            nombre_garcons=nombre_garcons,
            nombre_filles=nombre_filles,
            recorded_by_id=user.id,
        )
        db.add(effectif)
        action = "create"
    try:
        db.flush()
    except IntegrityError:
        # Deux soumissions concurrentes (double-clic, deux onglets) pour le même
        # année/niveau : la contrainte unique a bloqué la seconde, l'autre a déjà
        # enregistré la déclaration.
        db.rollback()
        return RedirectResponse(url="/etablissement/effectifs", status_code=status.HTTP_303_SEE_OTHER)
    audit.log(
        db, user, action, "Effectif", effectif.id,
        f"{etablissement.nom} a déclaré son effectif {effectif.niveau_label} {annee_scolaire}",
    )
    db.commit()
    return RedirectResponse(url="/etablissement/effectifs", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/etablissement/cartes-scolaires")
def etablissement_cartes_scolaires(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_cartes_web),
):
    etablissement = user.etablissement
    items = (
        db.query(models.CarteScolaire)
        .filter(models.CarteScolaire.etablissement_id == etablissement.id)
        .order_by(models.CarteScolaire.date_soumission.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "etablissement/cartes_scolaires.html",
        {
            "user": user,
            "etablissement": etablissement,
            "items": items,
            "annee_par_defaut": current_annee_scolaire(),
            "active": "cartes_scolaires",
            "error": None,
        },
    )


@router.post("/etablissement/cartes-scolaires/new")
async def etablissement_cartes_scolaires_create(
    request: Request,
    eleve_nom: str = Form(...),
    eleve_sexe: str = Form(""),
    eleve_date_naissance: str = Form(""),
    classe: str = Form(...),
    annee_scolaire: str = Form(...),
    photo: UploadFile | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_cartes_web),
):
    etablissement = user.etablissement

    photo_path = None
    if photo is not None and photo.filename:
        try:
            stored_name, _original = await storage.save_upload(db, photo, CARTES_SCOLAIRES_PHOTOS_DIR, ALLOWED_PHOTO_EXT)
            photo_path = f"cartes_scolaires/{stored_name}"
        except ValueError as exc:
            items = (
                db.query(models.CarteScolaire)
                .filter(models.CarteScolaire.etablissement_id == etablissement.id)
                .order_by(models.CarteScolaire.date_soumission.desc())
                .all()
            )
            return templates.TemplateResponse(
                request,
                "etablissement/cartes_scolaires.html",
                {
                    "user": user,
                    "etablissement": etablissement,
                    "items": items,
                    "annee_par_defaut": current_annee_scolaire(),
                    "active": "cartes_scolaires",
                    "error": str(exc),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    carte = models.CarteScolaire(
        etablissement_id=etablissement.id,
        requested_by_id=user.id,
        eleve_nom=eleve_nom,
        eleve_sexe=eleve_sexe or None,
        eleve_date_naissance=datetime.date.fromisoformat(eleve_date_naissance) if eleve_date_naissance else None,
        classe=classe,
        annee_scolaire=annee_scolaire,
        photo_path=photo_path,
        status="soumise",
    )
    db.add(carte)
    notify_cartes_scolaires_gestionnaires(
        db,
        f"Nouvelle demande de carte scolaire pour {eleve_nom} ({etablissement.nom}).",
        link="/admin/cartes-scolaires",
    )
    db.commit()
    return RedirectResponse(url="/etablissement/cartes-scolaires", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/etablissement/cartes-scolaires/{carte_id}/pdf")
def etablissement_carte_scolaire_pdf(
    carte_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_cartes_web),
):
    etablissement = user.etablissement
    carte = db.get(models.CarteScolaire, carte_id)
    if not carte or carte.etablissement_id != etablissement.id or carte.status not in {"validee", "imprimee", "disponible"}:
        return RedirectResponse(url="/etablissement/cartes-scolaires", status_code=status.HTTP_303_SEE_OTHER)
    stored_photo = storage.get_stored_file(db, carte.photo_path)
    stored_logo = storage.get_stored_file(db, etablissement.logo_path)
    pdf_bytes = generate_student_card_pdf(
        carte,
        stored_photo.data if stored_photo else None,
        stored_logo.data if stored_logo else None,
    )
    filename = f"carte_scolaire_{carte.matricule or carte.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/etablissement/cartes-scolaires/{carte_id}/photo")
def etablissement_carte_scolaire_photo(
    carte_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_cartes_web),
):
    etablissement = user.etablissement
    carte = db.get(models.CarteScolaire, carte_id)
    if not carte or carte.etablissement_id != etablissement.id or not carte.photo_path:
        return RedirectResponse(url="/etablissement/cartes-scolaires", status_code=status.HTTP_303_SEE_OTHER)
    stored = storage.get_stored_file(db, carte.photo_path)
    if not stored:
        return RedirectResponse(url="/etablissement/cartes-scolaires", status_code=status.HTTP_303_SEE_OTHER)
    return Response(content=stored.data, media_type=stored.content_type)


@router.get("/etablissement/demandes")
def etablissement_demandes(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_demandes_web),
):
    etablissement = user.etablissement
    items = (
        db.query(models.DemandeEtablissement)
        .filter(models.DemandeEtablissement.etablissement_id == etablissement.id)
        .order_by(models.DemandeEtablissement.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "etablissement/demandes.html",
        {"user": user, "etablissement": etablissement, "items": items, "active": "demandes"},
    )


@router.post("/etablissement/demandes/new")
def etablissement_demandes_create(
    objet: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_etab_demandes_web),
):
    demande = models.DemandeEtablissement(
        etablissement_id=user.etablissement_id,
        objet=objet,
        message=message,
    )
    db.add(demande)
    db.commit()
    return RedirectResponse(url="/etablissement/demandes", status_code=status.HTTP_303_SEE_OTHER)
