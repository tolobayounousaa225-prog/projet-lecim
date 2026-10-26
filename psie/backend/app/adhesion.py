"""Circuit d'adhésion : dépôt public, examen, avis du CA, décision de l'AG, création du membre."""

import datetime
import re
import secrets

from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import finance, models
from .audit import log_action
from .emailing import send_email

_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sans caractères ambigus (0/O, 1/I/L)
_PHONE_RE = re.compile(r"^[0-9+()./ -]{6,30}$")


def new_code() -> str:
    return "ADH-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


def submit_demande(db: Session, *, nom: str, sigle: str, representant_nom: str, representant_fonction: str | None,
                   email: str, telephone: str, siege: str | None, statut_juridique: str | None,
                   date_creation: datetime.date | None, nb_structures: int | None, message: str | None,
                   accepte_statuts: bool, accepte_cotisations: bool) -> models.DemandeAdhesion:
    nom, sigle, representant_nom = nom.strip(), sigle.strip().upper(), representant_nom.strip()
    if not nom or not sigle or not representant_nom:
        raise HTTPException(status_code=400, detail="Nom, sigle et représentant sont obligatoires")
    if len(nom) > 255 or len(sigle) > 50 or len(representant_nom) > 255:
        raise HTTPException(status_code=400, detail="Un des champs est trop long")
    try:
        email = validate_email(email.strip(), check_deliverability=False).normalized
    except EmailNotValidError:
        raise HTTPException(status_code=400, detail="Adresse e-mail invalide")
    if not _PHONE_RE.match(telephone.strip()):
        raise HTTPException(status_code=400, detail="Numéro de téléphone invalide")
    if not (accepte_statuts and accepte_cotisations):
        raise HTTPException(status_code=400, detail="L'approbation des statuts et l'engagement de cotiser sont requis")
    if nb_structures is not None and not 0 <= nb_structures <= 100000:
        raise HTTPException(status_code=400, detail="Nombre de structures invalide")
    if date_creation and date_creation > datetime.date.today():
        raise HTTPException(status_code=400, detail="Date de création dans le futur")
    if db.query(models.Faitiere).filter(models.Faitiere.sigle == sigle).first():
        raise HTTPException(status_code=409, detail="Une organisation portant ce sigle est déjà membre")
    for _ in range(5):
        code = new_code()
        if not db.query(models.DemandeAdhesion).filter_by(code=code).first():
            break
    demande = models.DemandeAdhesion(
        code=code, nom=nom, sigle=sigle, representant_nom=representant_nom,
        representant_fonction=(representant_fonction or "").strip() or None, email=email,
        telephone=telephone.strip(), siege=(siege or "").strip()[:255] or None,
        statut_juridique=(statut_juridique or "").strip()[:255] or None, date_creation=date_creation,
        nb_structures=nb_structures, message=(message or "").strip()[:3000] or None,
        accepte_statuts=True, accepte_cotisations=True,
    )
    db.add(demande)
    db.flush()
    log_action(db, None, "depot", "demande_adhesion", demande.id, f"{sigle} ({code})")
    return demande


def start_examen(db: Session, user, demande: models.DemandeAdhesion, notes: str | None) -> None:
    if demande.etat not in ("nouvelle", "en_examen"):
        raise HTTPException(status_code=409, detail="La demande est déjà traitée")
    demande.etat = "en_examen"
    if notes is not None:
        demande.notes_examen = notes.strip() or None
    log_action(db, user, "examen", "demande_adhesion", demande.id, demande.sigle)


def record_avis(db: Session, user, demande: models.DemandeAdhesion, avis: str, motif: str | None) -> None:
    if not demande.is_open:
        raise HTTPException(status_code=409, detail="La demande est déjà traitée")
    if avis not in ("favorable", "defavorable"):
        raise HTTPException(status_code=400, detail="Avis invalide")
    if avis == "defavorable" and not (motif or "").strip():
        raise HTTPException(status_code=400, detail="Le motif d'un avis défavorable est obligatoire")
    demande.avis_ca, demande.avis_ca_motif = avis, (motif or "").strip() or None
    demande.avis_ca_par_id, demande.avis_ca_at = user.id, datetime.datetime.utcnow()
    if demande.etat == "nouvelle":
        demande.etat = "en_examen"
    log_action(db, user, "avis_ca", "demande_adhesion", demande.id, f"{demande.sigle}: {avis}")


def decide(db: Session, user, demande: models.DemandeAdhesion, *, accepter: bool, reference: str | None,
           date_decision: datetime.date | None, motif: str | None,
           droit_adhesion: int | None) -> models.Faitiere | None:
    """Enregistre la décision de l'AG. Une acceptation exige un avis favorable du CA et la
    référence de la décision ; elle crée le membre (ordinaire, actif) et, si un montant est
    fourni, son droit d'adhésion à payer."""
    if not demande.is_open:
        raise HTTPException(status_code=409, detail="La demande est déjà traitée")
    reference = (reference or "").strip() or None
    if not reference:
        raise HTTPException(status_code=400, detail="La référence de la décision de l'AG est obligatoire")
    date_decision = date_decision or datetime.date.today()
    if date_decision > datetime.date.today():
        raise HTTPException(status_code=400, detail="La date de décision est dans le futur")
    demande.decision_reference, demande.decision_date = reference, date_decision
    demande.decision_motif, demande.decide_par_id = (motif or "").strip() or None, user.id

    if not accepter:
        demande.etat = "refusee"
        log_action(db, user, "refus", "demande_adhesion", demande.id, f"{demande.sigle} — {reference}")
        _notify(demande, accepted=False)
        return None

    if demande.avis_ca != "favorable":
        raise HTTPException(status_code=400, detail="Une adhésion ne peut être acceptée qu'après un avis favorable du CA")
    if db.query(models.Faitiere).filter(models.Faitiere.sigle == demande.sigle).first():
        raise HTTPException(status_code=409, detail="Une organisation portant ce sigle est déjà membre")
    faitiere = models.Faitiere(
        nom=demande.nom, sigle=demande.sigle, categorie="ordinaire", statut="actif",
        date_creation=demande.date_creation, date_adhesion=date_decision,
        statut_juridique=demande.statut_juridique, siege=demande.siege, email=demande.email,
        telephone=demande.telephone,
    )
    db.add(faitiere)
    db.flush()
    demande.faitiere_id = faitiere.id
    demande.etat = "acceptee"
    demande.cert_token = secrets.token_hex(16)
    log_action(db, user, "acceptation", "demande_adhesion", demande.id, f"{demande.sigle} — {reference}")
    if droit_adhesion:
        finance.create_adhesion_echeance(db, user, faitiere, droit_adhesion, None, reference)
    _notify(demande, accepted=True)
    return faitiere


def _notify(demande: models.DemandeAdhesion, accepted: bool) -> None:
    """E-mail au demandeur (au mieux : un échec d'envoi ne bloque pas la décision)."""
    if accepted:
        fr = f"Votre demande d'adhésion ({demande.code}) a été acceptée par l'Assemblée Générale."
        ar = "تم قبول طلب انخراطكم من طرف الجمعية العامة."
    else:
        fr = f"Votre demande d'adhésion ({demande.code}) n'a pas été retenue."
        ar = "لم يتم قبول طلب انخراطكم."
    send_email(demande.email, f"PSIE — Demande d'adhésion {demande.code}",
               f"{fr}\n\n{ar}\n\nPlateforme des Structures Islamiques d'Éducation (PSIE)\n")
