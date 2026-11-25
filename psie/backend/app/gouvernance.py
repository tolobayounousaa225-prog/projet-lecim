"""Vie statutaire : convocation, émargement, quorum, scrutins, sanctions (Statuts et RI de la PSIE)."""

import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models
from .audit import log_action
from .emailing import send_email

CONVOCATION_RECIPIENT_ORGANES = ("AG", "CA", "DEN", "CC")


# ---------- Convocation ----------

def mandat_actif(m: models.Mandat, jour: datetime.date) -> bool:
    return (m.date_debut is None or m.date_debut <= jour) and (m.date_fin is None or m.date_fin >= jour)


def create_assemblee(db: Session, user, *, type_: str, date_assemblee: datetime.date, heure: str | None, lieu: str,
                     ordre_du_jour: str, mode_vote: str, demande_age: str | None) -> models.Assemblee:
    if type_ not in models.ASSEMBLEE_TYPES:
        raise HTTPException(status_code=400, detail="Type d'assemblée invalide")
    if mode_vote not in models.VOTE_MODES:
        raise HTTPException(status_code=400, detail="Mode de vote invalide")
    if not lieu.strip() or not ordre_du_jour.strip():
        raise HTTPException(status_code=400, detail="Le lieu et l'ordre du jour sont obligatoires")
    if heure and not (len(heure) == 5 and heure[2] == ":" and heure.replace(":", "").isdigit()):
        raise HTTPException(status_code=400, detail="Heure invalide (HH:MM)")
    if type_ == "AGE" and not (demande_age or "").strip():
        raise HTTPException(status_code=400, detail="Une AGE exige l'indication de la demande conjointe qui la motive")
    a = models.Assemblee(
        type=type_, date_assemblee=date_assemblee, heure=heure or None, lieu=lieu.strip(),
        ordre_du_jour=ordre_du_jour.strip(), mode_vote=mode_vote,
        demande_age=(demande_age or "").strip() or None, created_by_id=user.id,
    )
    db.add(a)
    db.flush()
    log_action(db, user, "creation", "assemblee", a.id, f"{type_} du {date_assemblee}")
    return a


def record_ca_opinion(db: Session, user, a: models.Assemblee, reference: str) -> None:
    if a.statut != "preparation":
        raise HTTPException(status_code=409, detail="L'ordre du jour n'est plus modifiable")
    if not a.requires_ca_opinion:
        raise HTTPException(status_code=400, detail="Une AGE ne requiert pas l'avis du CA sur l'ordre du jour")
    if not reference.strip():
        raise HTTPException(status_code=400, detail="La référence de l'avis du CA est obligatoire")
    a.avis_ca_reference, a.avis_ca_par_id, a.avis_ca_at = reference.strip(), user.id, datetime.datetime.utcnow()
    log_action(db, user, "avis_ca", "assemblee", a.id, reference.strip())


def convocation_recipients(db: Session, a: models.Assemblee) -> list[str]:
    emails: set[str] = set()
    for f in db.query(models.Faitiere):
        if f.is_membre_actif and f.email:
            emails.add(f.email.strip().lower())
    for m in db.query(models.Mandat).filter(models.Mandat.organe.in_(CONVOCATION_RECIPIENT_ORGANES)):
        if m.email and mandat_actif(m, a.date_assemblee):
            emails.add(m.email.strip().lower())
    return sorted(emails)


def convocation_text(a: models.Assemblee) -> tuple[str, str]:
    when = f"{a.date_assemblee:%d/%m/%Y}" + (f" à {a.heure}" if a.heure else "")
    subject = f"PSIE — Convocation : {a.type_label} du {a.date_assemblee:%d/%m/%Y}"
    body = (
        f"Vous êtes convoqué(e) à l'{a.type_label} de la PSIE.\n\nDate : {when}\nLieu : {a.lieu}\n\n"
        f"Ordre du jour :\n{a.ordre_du_jour}\n\n"
        f"استدعاء لحضور {a.type_label}: {when} — {a.lieu}\n\nPlateforme des Structures Islamiques d'Éducation (PSIE)\n"
    )
    return subject, body


def send_convocation(db: Session, user, a: models.Assemblee, today: datetime.date | None = None,
                     sender=send_email) -> int:
    """Convoque l'assemblée. AGA et AGO : au moins 15 jours à l'avance et avis favorable du CA sur
    l'ordre du jour (Statuts art. 14.1 et 18). Retourne le nombre d'e-mails envoyés."""
    today = today or datetime.date.today()
    if a.statut != "preparation":
        raise HTTPException(status_code=409, detail="L'assemblée est déjà convoquée")
    if a.type != "AGE":
        if (a.date_assemblee - today).days < models.CONVOCATION_DELAI_JOURS:
            raise HTTPException(status_code=400, detail=(
                f"Une {a.type} doit être convoquée au moins {models.CONVOCATION_DELAI_JOURS} jours à l'avance"))
        if not a.avis_ca_reference:
            raise HTTPException(status_code=400, detail="L'avis favorable du CA sur l'ordre du jour est requis")
    elif a.date_assemblee < today:
        raise HTTPException(status_code=400, detail="La date de l'assemblée est passée")
    subject, body = convocation_text(a)
    sent = sum(1 for to in convocation_recipients(db, a) if sender(to, subject, body))
    a.statut, a.convocation_at, a.convocation_envoyes = "convoquee", datetime.datetime.utcnow(), sent
    log_action(db, user, "convocation", "assemblee", a.id, f"{a.type} du {a.date_assemblee} — {sent} e-mail(s)")
    return sent


# ---------- Séance : émargement et quorum ----------

def open_session(db: Session, user, a: models.Assemblee, today: datetime.date | None = None) -> int:
    """Ouvre la séance et prépare la liste d'émargement : délégués des organisations membres
    actives, puis membres du CA, de la DEN et du CC en cours de mandat."""
    today = today or datetime.date.today()
    if a.statut != "convoquee":
        raise HTTPException(status_code=409, detail="L'assemblée doit être convoquée avant d'ouvrir la séance")
    if a.date_assemblee > today:
        raise HTTPException(status_code=400, detail="La séance ne peut pas s'ouvrir avant la date de l'assemblée")
    n = 0
    for m in (db.query(models.Mandat).filter(models.Mandat.organe.in_(CONVOCATION_RECIPIENT_ORGANES))
              .order_by(models.Mandat.organe, models.Mandat.full_name)):
        if not mandat_actif(m, a.date_assemblee):
            continue
        if m.organe == "AG" and not (m.faitiere and m.faitiere.is_membre_actif):
            continue  # un délégué d'une organisation suspendue ou radiée ne siège pas
        db.add(models.PresenceAG(assemblee_id=a.id, mandat_id=m.id, nom=m.full_name, organe=m.organe,
                                 faitiere_id=m.faitiere_id))
        n += 1
    a.statut = "en_seance"
    log_action(db, user, "ouverture_seance", "assemblee", a.id, f"{n} personne(s) attendue(s)")
    return n


def set_presence(db: Session, user, a: models.Assemblee, present_ids: set[int]) -> None:
    if a.statut != "en_seance":
        raise HTTPException(status_code=409, detail="L'émargement n'est possible qu'en séance")
    if any(r.statut == "close" for r in a.resolutions):
        raise HTTPException(status_code=409, detail="Un scrutin est déjà clos : l'émargement est figé")
    for p in a.presences:
        p.present = p.id in present_ids
    log_action(db, user, "emargement", "assemblee", a.id, f"{len(present_ids)} présent(s)")


def voting_base(db: Session, a: models.Assemblee) -> dict:
    """Corps votant et quorum (2/3, Statuts art. 15).

    Mode « organisation » : base = organisations membres actives ; présente = au moins un délégué.
    Mode « délégué » : base = délégués attendus ; présent = délégué émargé."""
    delegues = [p for p in a.presences if p.is_delegue]
    if a.mode_vote == "organisation":
        base_ids = {f.id for f in db.query(models.Faitiere) if f.is_membre_actif}
        present_ids = {p.faitiere_id for p in delegues if p.present and p.faitiere_id in base_ids}
        units = {f"o:{fid}": next(f.sigle for f in db.query(models.Faitiere).filter_by(id=fid)) for fid in present_ids}
        base = len(base_ids)
    else:
        units = {f"d:{p.id}": f"{p.nom} ({p.faitiere.sigle})" for p in delegues if p.present}
        base = len(delegues)
    presents = len(units)
    return {
        "mode": a.mode_vote, "base": base, "presents": presents, "units": units,
        "quorum": base > 0 and 3 * presents >= 2 * base,
    }


# ---------- Résolutions et scrutins ----------

def add_resolution(db: Session, user, a: models.Assemblee, intitule: str, texte: str | None, regle: str) -> models.Resolution:
    if a.statut not in ("preparation", "convoquee", "en_seance"):
        raise HTTPException(status_code=409, detail="L'assemblée est clôturée")
    if not intitule.strip():
        raise HTTPException(status_code=400, detail="L'intitulé est obligatoire")
    if regle not in ("majorite", "dissolution"):
        raise HTTPException(status_code=400, detail="Règle de vote invalide")
    if regle == "dissolution" and a.type != "AGE":
        raise HTTPException(status_code=400, detail="La dissolution relève exclusivement d'une AGE")
    numero = max((r.numero for r in a.resolutions), default=0) + 1
    r = models.Resolution(assemblee_id=a.id, numero=numero, intitule=intitule.strip(),
                          texte=(texte or "").strip() or None, regle=regle)
    db.add(r)
    db.flush()
    log_action(db, user, "creation", "resolution", r.id, f"{a.type} {a.date_assemblee} — n°{numero}")
    return r


def _check_scrutin_open(db: Session, a: models.Assemblee, r: models.Resolution) -> dict:
    if a.statut != "en_seance":
        raise HTTPException(status_code=409, detail="Les votes ne s'enregistrent qu'en séance")
    if r.statut != "ouverte":
        raise HTTPException(status_code=409, detail="Ce scrutin est clos")
    base = voting_base(db, a)
    if not base["quorum"]:
        raise HTTPException(status_code=400, detail="Le quorum des 2/3 n'est pas atteint : l'assemblée ne peut pas délibérer")
    return base


def record_votes(db: Session, user, a: models.Assemblee, r: models.Resolution, choix_par_unite: dict[str, str]) -> None:
    base = _check_scrutin_open(db, a, r)
    for unite, choix in choix_par_unite.items():
        if unite not in base["units"]:
            raise HTTPException(status_code=400, detail="Une voix est saisie pour une unité absente ou inconnue")
        if choix not in models.VOTE_CHOIX:
            raise HTTPException(status_code=400, detail="Choix de vote invalide")
    r.votes.clear()
    db.flush()
    for unite, choix in choix_par_unite.items():
        r.votes.append(models.Vote(unite=unite, libelle=base["units"][unite], choix=choix))
    db.flush()
    log_action(db, user, "vote", "resolution", r.id, f"n°{r.numero}: {len(choix_par_unite)} voix saisie(s)")


def close_scrutin(db: Session, user, a: models.Assemblee, r: models.Resolution, consensus: bool = False) -> models.Resolution:
    """Clôt le scrutin. Décision par consensus ou, à défaut, à la majorité des voix des membres
    présents (art. 15) ; la dissolution exige les 4/5 des membres statutaires (art. 41)."""
    base = _check_scrutin_open(db, a, r)
    if consensus and r.regle == "dissolution":
        raise HTTPException(status_code=400, detail="La dissolution exige un vote à la majorité des 4/5")
    r.base, r.presents = base["base"], base["presents"]
    if consensus:
        r.mode_adoption, r.pour, r.contre, r.abstention, r.adoptee = "consensus", base["presents"], 0, 0, True
    else:
        votes = r.votes
        if not votes:
            raise HTTPException(status_code=400, detail="Aucune voix saisie")
        r.mode_adoption = "vote"
        r.pour = sum(1 for v in votes if v.choix == "pour")
        r.contre = sum(1 for v in votes if v.choix == "contre")
        r.abstention = sum(1 for v in votes if v.choix == "abstention")
        if r.regle == "dissolution":
            r.adoptee = 5 * r.pour >= 4 * r.base
        else:
            r.adoptee = 2 * r.pour > r.presents  # majorité des voix des présents : les abstentions ne comptent pas pour
    r.statut, r.closed_at = "close", datetime.datetime.utcnow()
    log_action(db, user, "cloture_scrutin", "resolution", r.id,
               f"n°{r.numero}: {'adoptée' if r.adoptee else 'rejetée'} ({r.pour} pour, {r.contre} contre, {r.abstention} abst.)")
    return r


def close_assemblee(db: Session, user, a: models.Assemblee, president: str, assesseur1: str, assesseur2: str) -> None:
    """Clôture : un président et deux assesseurs sont requis (Statuts art. 16)."""
    if a.statut != "en_seance":
        raise HTTPException(status_code=409, detail="Seule une assemblée en séance peut être clôturée")
    if not (president.strip() and assesseur1.strip() and assesseur2.strip()):
        raise HTTPException(status_code=400, detail="Le président de séance et les deux assesseurs sont obligatoires")
    if any(r.statut == "ouverte" for r in a.resolutions):
        raise HTTPException(status_code=400, detail="Des résolutions sont encore ouvertes : clôturez ou supprimez leur scrutin")
    a.president_nom, a.assesseur1_nom, a.assesseur2_nom = president.strip(), assesseur1.strip(), assesseur2.strip()
    a.statut, a.closed_at = "close", datetime.datetime.utcnow()
    log_action(db, user, "cloture", "assemblee", a.id, f"{a.type} du {a.date_assemblee}")


# ---------- Sanctions ----------

def pronounce_sanction(db: Session, user, faitiere: models.Faitiere, type_: str, motif: str, reference: str,
                       date_decision: datetime.date) -> models.Sanction:
    """Avertissement, blâme, suspension : prononcés par la DEN après avis favorable du CA (référence
    de l'avis écrit). Radiation : décision de l'AG (référence de la résolution)."""
    if type_ not in models.SANCTION_TYPES:
        raise HTTPException(status_code=400, detail="Type de sanction invalide")
    if not motif.strip() or not reference.strip():
        raise HTTPException(status_code=400, detail=(
            "Le motif et la référence sont obligatoires "
            "(avis écrit du CA, ou résolution de l'AG pour une radiation)"))
    if date_decision > datetime.date.today():
        raise HTTPException(status_code=400, detail="La date de décision est dans le futur")
    if faitiere.statut == "radie":
        raise HTTPException(status_code=409, detail="Cette organisation est déjà radiée")
    if faitiere.categorie == "honneur":
        raise HTTPException(status_code=400, detail="Les sanctions visent les organisations membres, pas les membres d'honneur")
    s = models.Sanction(faitiere_id=faitiere.id, type=type_, motif=motif.strip(), reference=reference.strip(),
                        date_decision=date_decision, decide_par_id=user.id)
    db.add(s)
    effet = models.SANCTION_EFFETS.get(type_)
    if effet:
        faitiere.statut = effet
    db.flush()
    log_action(db, user, "sanction", "sanction", s.id, f"{faitiere.sigle}: {type_} — {reference.strip()}")
    return s


def lift_suspension(db: Session, user, s: models.Sanction, motif: str) -> None:
    if s.type != "suspension" or not s.is_active:
        raise HTTPException(status_code=409, detail="Seule une suspension en cours peut être levée")
    if s.faitiere.statut == "radie":
        raise HTTPException(status_code=409, detail="Cette organisation est radiée")
    if not motif.strip():
        raise HTTPException(status_code=400, detail="Le motif de la levée est obligatoire")
    s.levee_le, s.levee_motif = datetime.date.today(), motif.strip()[:500]
    autres = [x for x in s.faitiere.sanctions_actives if x.id != s.id and x.type == "suspension"]
    if not autres:
        s.faitiere.statut = "actif"
    log_action(db, user, "levee_suspension", "sanction", s.id, f"{s.faitiere.sigle}: {motif.strip()[:200]}")


def composition_organes(db: Session, jour: datetime.date | None = None) -> list[dict]:
    """Effectifs réels des organes comparés à ceux des Statuts (CA 13, DEN 13, CC 2) et des
    délégués à l'AG (2 par organisation membre active)."""
    jour = jour or datetime.date.today()
    actifs = [m for m in db.query(models.Mandat) if mandat_actif(m, jour)]
    rows = [{"organe": o, "attendu": n, "reel": sum(1 for m in actifs if m.organe == o)}
            for o, n in models.COMPOSITION_ATTENDUE.items()]
    membres = sum(1 for f in db.query(models.Faitiere) if f.is_membre_actif)
    rows.append({"organe": "AG", "attendu": 2 * membres,
                 "reel": sum(1 for m in actifs if m.organe == "AG" and m.faitiere and m.faitiere.is_membre_actif)})
    return rows
