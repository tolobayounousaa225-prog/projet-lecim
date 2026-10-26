"""Logique métier des cotisations : génération des échéances, paiements, situation, relances."""

import csv
import datetime
import hashlib
import hmac
import io
import secrets

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .audit import log_action
from .config import settings
from .emailing import send_email


def fcfa(amount: int) -> str:
    """500000 -> '500 000 FCFA' (espace insécable)."""
    return f"{amount:,}".replace(",", " ") + " FCFA"


# ---------- Barème et génération des échéances ----------

def set_bareme(db: Session, user, annee: int, montant: int, date_limite, reference: str | None) -> models.BaremeCotisation:
    if montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")
    if not 2000 <= annee <= 2100:
        raise HTTPException(status_code=400, detail="Année invalide")
    bareme = db.query(models.BaremeCotisation).filter_by(annee=annee).first()
    if bareme:
        detail = f"{annee}: {bareme.montant} -> {montant}"
        bareme.montant, bareme.date_limite, bareme.reference_decision = montant, date_limite, reference
        log_action(db, user, "modification", "bareme", bareme.id, detail)
    else:
        bareme = models.BaremeCotisation(
            annee=annee, montant=montant, date_limite=date_limite, reference_decision=reference,
            created_by_id=user.id if user else None,
        )
        db.add(bareme)
        db.flush()
        log_action(db, user, "creation", "bareme", bareme.id, f"{annee}: {montant}")
    return bareme


def generate_annual_echeances(db: Session, annee: int, user=None) -> int:
    """Crée la cotisation annuelle de chaque membre actif (fondateur ou ordinaire) qui n'en a
    pas encore pour `annee`. Idempotent. Les échéances déjà créées ne sont jamais modifiées,
    même si le barème change ensuite. Retourne le nombre d'échéances créées."""
    bareme = db.query(models.BaremeCotisation).filter_by(annee=annee).first()
    if not bareme:
        raise HTTPException(status_code=400, detail=f"Aucun montant de cotisation défini pour {annee}")
    existing = {
        fid for (fid,) in db.query(models.Echeance.faitiere_id).filter_by(type="annuelle", annee=annee)
    }
    created = 0
    for f in db.query(models.Faitiere).order_by(models.Faitiere.id):
        if not f.is_membre_actif or f.id in existing:
            continue
        db.add(models.Echeance(
            faitiere_id=f.id, type="annuelle", annee=annee, libelle=f"Cotisation annuelle {annee}",
            montant_du=bareme.montant, date_limite=bareme.date_limite,
            reference_decision=bareme.reference_decision, created_by_id=user.id if user else None,
        ))
        created += 1
    if created:
        db.flush()
        log_action(db, user, "generation", "echeance", None, f"{created} cotisation(s) annuelle(s) {annee}")
    return created


def create_adhesion_echeance(db: Session, user, faitiere: models.Faitiere, montant: int, date_limite, reference) -> models.Echeance:
    if montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")
    if db.query(models.Echeance).filter_by(faitiere_id=faitiere.id, type="adhesion").first():
        raise HTTPException(status_code=409, detail="Un droit d'adhésion existe déjà pour cette faîtière")
    e = models.Echeance(
        faitiere_id=faitiere.id, type="adhesion", annee=datetime.date.today().year,
        libelle="Droit d'adhésion", montant_du=montant, date_limite=date_limite,
        reference_decision=reference, created_by_id=user.id if user else None,
    )
    db.add(e)
    db.flush()
    log_action(db, user, "creation", "echeance", e.id, f"adhésion {faitiere.sigle}: {montant}")
    return e


# ---------- Appels exceptionnels ----------

def create_appel(db: Session, user, intitule: str, motif: str | None, reference: str | None,
                 date_limite, lignes: list[tuple[models.Faitiere, int]]) -> models.AppelExceptionnel:
    """Crée l'appel et une échéance par faîtière concernée. `lignes` = (faîtière, montant).
    Les montants peuvent différer d'une faîtière à l'autre ; aucune formule n'est imposée."""
    if not intitule.strip():
        raise HTTPException(status_code=400, detail="L'intitulé est obligatoire")
    if not lignes:
        raise HTTPException(status_code=400, detail="Sélectionnez au moins une faîtière")
    seen = set()
    for faitiere, montant in lignes:
        if montant <= 0:
            raise HTTPException(status_code=400, detail=f"Montant invalide pour {faitiere.sigle}")
        if faitiere.id in seen:
            raise HTTPException(status_code=400, detail="Faîtière en double")
        seen.add(faitiere.id)
    appel = models.AppelExceptionnel(
        intitule=intitule.strip(), motif=motif, reference_decision=reference, date_limite=date_limite,
        created_by_id=user.id if user else None,
    )
    db.add(appel)
    db.flush()
    for faitiere, montant in lignes:
        db.add(models.Echeance(
            faitiere_id=faitiere.id, type="exceptionnelle", annee=datetime.date.today().year,
            libelle=appel.intitule[:255], montant_du=montant, date_limite=date_limite,
            reference_decision=reference, appel_id=appel.id, created_by_id=user.id if user else None,
        ))
    db.flush()
    total = sum(m for _, m in lignes)
    log_action(db, user, "creation", "appel", appel.id,
               f"{appel.intitule}: {len(lignes)} faîtière(s), {fcfa(total)} — décision: {reference or 'non précisée'}")
    return appel


def exonerer_echeance(db: Session, user, e: models.Echeance, motif: str) -> None:
    if e.exoneree:
        raise HTTPException(status_code=409, detail="Déjà exonérée")
    if not motif.strip():
        raise HTTPException(status_code=400, detail="Le motif de l'exonération est obligatoire")
    e.exoneree, e.exoneration_motif = True, motif.strip()[:500]
    e.exoneree_par_id, e.exoneree_at = user.id, datetime.datetime.utcnow()
    log_action(db, user, "exoneration", "echeance", e.id, f"{e.faitiere.sigle} / {e.libelle}: {e.exoneration_motif}")


def retablir_echeance(db: Session, user, e: models.Echeance) -> None:
    if not e.exoneree:
        raise HTTPException(status_code=409, detail="Cette échéance n'est pas exonérée")
    e.exoneree, e.exoneration_motif, e.exoneree_par_id, e.exoneree_at = False, None, None, None
    log_action(db, user, "retablissement", "echeance", e.id, f"{e.faitiere.sigle} / {e.libelle}")


def reporter_echeance(db: Session, user, e: models.Echeance, nouvelle_date: datetime.date, motif: str) -> None:
    if not motif.strip():
        raise HTTPException(status_code=400, detail="Le motif du report est obligatoire")
    if e.date_limite and nouvelle_date <= e.date_limite:
        raise HTTPException(status_code=400, detail="La nouvelle date doit être postérieure à la date limite actuelle")
    ancienne = e.date_limite
    e.date_limite = nouvelle_date
    # Les paliers de relance recommencent à partir de la nouvelle date
    db.query(models.RelanceLog).filter_by(echeance_id=e.id).delete()
    log_action(db, user, "report", "echeance", e.id,
               f"{e.faitiere.sigle} / {e.libelle}: {ancienne} -> {nouvelle_date} ({motif.strip()[:300]})")


def corriger_montant(db: Session, user, e: models.Echeance, montant: int, motif: str) -> None:
    """Corrige le montant d'une échéance (jamais en dessous de ce qui est déjà payé)."""
    if not motif.strip():
        raise HTTPException(status_code=400, detail="Le motif de la correction est obligatoire")
    if montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")
    if montant < e.montant_paye:
        raise HTTPException(status_code=400, detail=f"Le montant ne peut pas être inférieur aux paiements déjà reçus ({fcfa(e.montant_paye)})")
    ancien = e.montant_du
    e.montant_du = montant
    log_action(db, user, "correction", "echeance", e.id,
               f"{e.faitiere.sigle} / {e.libelle}: {ancien} -> {montant} ({motif.strip()[:300]})")


# ---------- Paiements ----------

def _next_recu_numero(db: Session, year: int) -> str:
    prefix = f"PSIE-REC-{year}-"
    last = (
        db.query(func.max(models.Paiement.recu_numero))
        .filter(models.Paiement.recu_numero.like(prefix + "%"))
        .scalar()
    )
    seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def record_paiement(db: Session, user, echeance: models.Echeance, montant: int, date_paiement: datetime.date,
                    mode: str, reference: str | None) -> models.Paiement:
    if mode not in models.MODES_PAIEMENT:
        raise HTTPException(status_code=400, detail="Mode de paiement invalide")
    if montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")
    if montant > echeance.solde:
        raise HTTPException(status_code=400, detail=f"Le montant dépasse le solde restant ({fcfa(echeance.solde)})")
    if date_paiement > datetime.date.today():
        raise HTTPException(status_code=400, detail="La date de paiement est dans le futur")
    for attempt in range(5):
        paiement = models.Paiement(
            echeance_id=echeance.id, montant=montant, date_paiement=date_paiement, mode=mode,
            reference=reference, recu_numero=_next_recu_numero(db, date_paiement.year),
            verify_token=secrets.token_hex(16), saisi_par_id=user.id if user else None,
        )
        try:
            with db.begin_nested():
                db.add(paiement)
                db.flush()
            break
        except IntegrityError:  # deux reçus simultanés : on retente avec le numéro suivant
            continue
    else:
        raise HTTPException(status_code=503, detail="Numérotation du reçu indisponible, réessayez")
    db.refresh(echeance)
    log_action(db, user, "paiement", "paiement", paiement.id,
               f"{paiement.recu_numero}: {fcfa(montant)} — {echeance.faitiere.sigle} / {echeance.libelle}")
    return paiement


def cancel_paiement(db: Session, user, paiement: models.Paiement, motif: str) -> None:
    if paiement.annule:
        raise HTTPException(status_code=409, detail="Paiement déjà annulé")
    if not motif.strip():
        raise HTTPException(status_code=400, detail="Le motif d'annulation est obligatoire")
    paiement.annule = True
    paiement.annule_motif = motif.strip()[:500]
    paiement.annule_par_id = user.id
    paiement.annule_at = datetime.datetime.utcnow()
    log_action(db, user, "annulation", "paiement", paiement.id, f"{paiement.recu_numero}: {paiement.annule_motif}")


# ---------- Situation ----------

def situation(db: Session, annee: int) -> dict:
    """Cotisations annuelles d'une année : une ligne par faîtière + totaux."""
    rows = (
        db.query(models.Echeance)
        .filter_by(type="annuelle", annee=annee)
        .join(models.Faitiere)
        .order_by(models.Faitiere.sigle)
        .all()
    )
    du = sum(e.montant_du for e in rows if not e.exoneree)
    paye = sum(e.montant_paye for e in rows if not e.exoneree)
    return {
        "annee": annee,
        "rows": rows,
        "total_du": du,
        "total_paye": paye,
        "reste": sum(e.solde for e in rows),
        "taux": round(100 * paye / du) if du else 0,
        "nb_retard": sum(1 for e in rows if e.statut == "en_retard"),
        "nb_a_jour": sum(1 for e in rows if e.statut in ("paye", "exonere")),
    }


def situation_csv(data: dict) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Faîtière", "Libellé", "Dû (FCFA)", "Payé (FCFA)", "Solde (FCFA)", "Date limite", "Statut"])
    for e in data["rows"]:
        writer.writerow([e.faitiere.sigle, e.libelle, e.montant_du, e.montant_paye, e.solde,
                         e.date_limite or "", e.statut])
    writer.writerow(["TOTAL", "", data["total_du"], data["total_paye"], data["reste"], "", f"{data['taux']} %"])
    return out.getvalue()


def faitiere_a_jour(db: Session, faitiere_id: int, annee: int) -> bool:
    """Cotisation annuelle de `annee` intégralement payée."""
    e = db.query(models.Echeance).filter_by(faitiere_id=faitiere_id, type="annuelle", annee=annee).first()
    return bool(e and e.solde <= 0)


# ---------- Signature des attestations (vérification publique par QR code) ----------

def attestation_signature(faitiere_id: int, annee: int) -> str:
    msg = f"attestation:{faitiere_id}:{annee}".encode()
    return hmac.new(settings.secret_key.encode(), msg, hashlib.sha256).hexdigest()[:24]


# ---------- Relances ----------

def _reminder_kind(days_left: int) -> str | None:
    """Rappel le plus urgent applicable. Tolère un jour de planificateur manqué : on teste des
    seuils, pas des jours exacts."""
    if days_left <= -7:
        return f"R{(-days_left) // 7}"  # hebdomadaire après le retard
    if days_left <= 0:
        return "J0"
    if days_left <= 7:
        return "J7"
    if days_left <= 30:
        return "J30"
    return None


def _reminder_text(e: models.Echeance, days_left: int) -> tuple[str, str]:
    solde = fcfa(e.solde)
    if days_left > 0:
        fr = f"Rappel : votre {e.libelle.lower()} ({solde}) est à régler avant le {e.date_limite:%d/%m/%Y}."
        ar = f"تذكير: يجب تسديد {solde} قبل {e.date_limite:%d/%m/%Y}."
    else:
        fr = f"Relance : votre {e.libelle.lower()} ({solde}) est en retard depuis le {e.date_limite:%d/%m/%Y}."
        ar = f"تنبيه: تأخر تسديد {solde} منذ {e.date_limite:%d/%m/%Y}."
    subject = f"PSIE — {e.libelle} — {e.faitiere.sigle}"
    body = f"{fr}\n\n{ar}\n\nPlateforme des Structures Islamiques d'Éducation (PSIE)\n"
    return subject, body


def send_reminders(db: Session, today: datetime.date | None = None, sender=send_email) -> int:
    """Envoie les relances dues. Un rappel donné n'est envoyé qu'une fois par échéance.
    Retourne le nombre d'e-mails envoyés."""
    today = today or datetime.date.today()
    sent = 0
    items = (
        db.query(models.Echeance)
        .filter(models.Echeance.date_limite.is_not(None))
        .all()
    )
    for e in items:
        if e.solde <= 0 or not e.faitiere.email or not e.faitiere.is_membre_actif:
            continue
        days_left = (e.date_limite - today).days
        kind = _reminder_kind(days_left)
        if not kind:
            continue
        if db.query(models.RelanceLog).filter_by(echeance_id=e.id, kind=kind).first():
            continue
        subject, body = _reminder_text(e, days_left)
        if sender(e.faitiere.email, subject, body):
            db.add(models.RelanceLog(echeance_id=e.id, kind=kind))
            sent += 1
    db.commit()
    return sent


def send_weekly_digest(db: Session, today: datetime.date | None = None, sender=send_email) -> int:
    """Liste des cotisations en retard, envoyée aux secrétaires aux finances. Retourne le
    nombre de destinataires atteints."""
    today = today or datetime.date.today()
    late = [e for e in db.query(models.Echeance).all() if e.solde > 0 and e.date_limite and e.date_limite < today]
    if not late:
        return 0
    lines = [f"- {e.faitiere.sigle} : {e.libelle}, solde {fcfa(e.solde)}, échéance {e.date_limite:%d/%m/%Y}"
             for e in sorted(late, key=lambda x: x.faitiere.sigle)]
    body = f"Cotisations en retard au {today:%d/%m/%Y} :\n\n" + "\n".join(lines) + "\n"
    reached = 0
    for u in db.query(models.User).filter_by(role="finances", is_active=True):
        if sender(u.email, "PSIE — Cotisations en retard", body):
            reached += 1
    return reached
