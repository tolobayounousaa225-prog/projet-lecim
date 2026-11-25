"""Finances de la PSIE : dépenses à double signature, justificatifs, recettes, dons, budget, états."""

import datetime
import hashlib

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .audit import log_action
from .finance import fcfa


# ---------- Justificatifs ----------

def detect_content_type(data: bytes) -> str | None:
    """Type réel du fichier d'après son contenu (PDF, PNG, JPEG), jamais d'après son nom."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def add_justificatif(db: Session, user, depense: models.Depense, nom: str, data: bytes) -> models.Justificatif:
    if depense.statut in ("payee", "annulee"):
        raise HTTPException(status_code=409, detail="Cette dépense est close : on ne peut plus y joindre de pièce")
    if not data:
        raise HTTPException(status_code=400, detail="Fichier vide")
    if len(data) > models.JUSTIFICATIF_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (5 Mo maximum)")
    ctype = detect_content_type(data)
    if not ctype:
        raise HTTPException(status_code=400, detail="Format refusé : seuls les PDF, PNG et JPEG sont acceptés")
    nom = (nom or "piece").replace("\\", "/").rsplit("/", 1)[-1].strip()[:200] or "piece"
    j = models.Justificatif(depense_id=depense.id, nom=nom, content_type=ctype, taille=len(data),
                            sha256=hashlib.sha256(data).hexdigest(), contenu=data, ajoute_par_id=user.id)
    depense.justificatifs.append(j)
    db.flush()
    log_action(db, user, "justificatif", "depense", depense.id, f"{nom} ({ctype}, {len(data)} octets)")
    return j


# ---------- Dépenses et double signature ----------

def create_depense(db: Session, user, *, libelle: str, categorie: str, montant: int, date_depense: datetime.date,
                   beneficiaire: str | None, ordre_mission: str | None,
                   derogation: str | None) -> models.Depense:
    if categorie not in models.DEPENSE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Catégorie invalide")
    if not libelle.strip():
        raise HTTPException(status_code=400, detail="Le libellé est obligatoire")
    if montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")
    if date_depense > datetime.date.today():
        raise HTTPException(status_code=400, detail="La date de la dépense est dans le futur")
    if categorie == "mission" and not (ordre_mission or "").strip():
        raise HTTPException(status_code=400, detail="Un frais de mission exige la référence de l'ordre de mission")
    d = models.Depense(libelle=libelle.strip(), categorie=categorie, montant=montant, date_depense=date_depense,
                       beneficiaire=(beneficiaire or "").strip() or None,
                       ordre_mission=(ordre_mission or "").strip() or None,
                       derogation_ca_reference=(derogation or "").strip() or None, created_by_id=user.id)
    db.add(d)
    db.flush()
    log_action(db, user, "creation", "depense", d.id, f"{d.libelle}: {fcfa(montant)}")
    return d


def sign_depense(db: Session, user, d: models.Depense) -> models.Depense:
    """Pose la signature du DEN ou du secrétaire aux finances. Quand les deux sont posées, la
    dépense devient payable. Les deux signataires doivent venir d'organisations différentes
    (Statuts art. 38)."""
    if user.role not in models.SIGNATAIRE_ROLES:
        raise HTTPException(status_code=403, detail="Seuls le DEN et le secrétaire aux finances signent les dépenses")
    if d.statut != "a_valider":
        raise HTTPException(status_code=409, detail="Cette dépense n'est plus à valider")
    if d.validation_de(user.role):
        raise HTTPException(status_code=409, detail="Cette signature est déjà posée")
    if not d.justificatifs and not d.derogation_ca_reference:
        raise HTTPException(status_code=400, detail=(
            "Pièce justificative manquante : joignez-la, ou indiquez la décision motivée du CA qui autorise "
            "cette dépense (Statuts art. 39.2)"))
    if not user.faitiere_origine_id:
        raise HTTPException(status_code=400, detail=(
            "Votre organisation d'origine n'est pas renseignée sur votre compte : demandez à l'administrateur de la saisir"))
    for v in d.validations:
        if v.faitiere_origine_id == user.faitiere_origine_id:
            raise HTTPException(status_code=400, detail=(
                "Le DEN et le secrétaire aux finances ne peuvent pas être de la même organisation (Statuts art. 38)"))
    d.validations.append(models.ValidationDepense(user_id=user.id, user_nom=user.full_name, role=user.role,
                                                  faitiere_origine_id=user.faitiere_origine_id))
    if not d.roles_manquants:
        d.statut = "validee"
    db.flush()
    log_action(db, user, "signature", "depense", d.id, f"{user.role} — {'validée' if d.statut == 'validee' else '1 signature'}")
    return d


def pay_depense(db: Session, user, d: models.Depense, date_paiement: datetime.date, mode: str,
                reference: str | None) -> None:
    if d.statut != "validee":
        raise HTTPException(status_code=409, detail="Seule une dépense validée par les deux signataires peut être payée")
    if mode not in models.MODES_PAIEMENT:
        raise HTTPException(status_code=400, detail="Mode de paiement invalide")
    if date_paiement > datetime.date.today():
        raise HTTPException(status_code=400, detail="La date de paiement est dans le futur")
    d.statut, d.payee_le, d.mode_paiement = "payee", date_paiement, mode
    d.reference_paiement = (reference or "").strip() or None
    log_action(db, user, "paiement", "depense", d.id, f"{d.libelle}: {fcfa(d.montant)} le {date_paiement}")


def cancel_depense(db: Session, user, d: models.Depense, motif: str) -> None:
    if d.statut == "payee":
        raise HTTPException(status_code=409, detail="Une dépense payée ne s'annule pas : enregistrez une écriture corrective")
    if d.statut == "annulee":
        raise HTTPException(status_code=409, detail="Déjà annulée")
    if not motif.strip():
        raise HTTPException(status_code=400, detail="Le motif d'annulation est obligatoire")
    d.statut, d.annulee_motif = "annulee", motif.strip()[:500]
    log_action(db, user, "annulation", "depense", d.id, d.annulee_motif)


# ---------- Recettes, dons, paramètres ----------

def create_recette(db: Session, user, *, categorie: str, libelle: str, source: str | None, montant: int,
                   date_recette: datetime.date, reference: str | None) -> models.Recette:
    if categorie not in models.RECETTE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Catégorie invalide")
    if not libelle.strip() or montant <= 0:
        raise HTTPException(status_code=400, detail="Libellé et montant positif obligatoires")
    if date_recette > datetime.date.today():
        raise HTTPException(status_code=400, detail="La date est dans le futur")
    r = models.Recette(categorie=categorie, libelle=libelle.strip(), source=(source or "").strip() or None,
                       montant=montant, date_recette=date_recette, reference=(reference or "").strip() or None,
                       created_by_id=user.id)
    db.add(r)
    db.flush()
    log_action(db, user, "creation", "recette", r.id, f"{r.libelle}: {fcfa(montant)}")
    return r


def get_parametre(db: Session, cle: str) -> str | None:
    p = db.get(models.Parametre, cle)
    return p.valeur if p else None


def seuil_don(db: Session) -> int | None:
    v = get_parametre(db, "seuil_don")
    return int(v) if v and v.isdigit() else None


def set_seuil_don(db: Session, user, montant: int | None) -> None:
    if montant is not None and montant <= 0:
        raise HTTPException(status_code=400, detail="Le seuil doit être positif")
    p = db.get(models.Parametre, "seuil_don")
    if montant is None:
        if p:
            db.delete(p)
    elif p:
        p.valeur, p.updated_by_id, p.updated_at = str(montant), user.id, datetime.datetime.utcnow()
    else:
        db.add(models.Parametre(cle="seuil_don", valeur=str(montant), updated_by_id=user.id))
    log_action(db, user, "parametre", "parametre", None, f"seuil_don = {montant}")


def record_don(db: Session, user, *, donateur_nom: str, adresse: str, telephone: str | None, piece_type: str | None,
               piece_numero: str | None, nature: str, description: str | None, valeur: int,
               date_don: datetime.date, origine_fonds: str | None) -> models.Don:
    """Inscrit un don au registre. Identité complète du donateur, date, nature et valeur sont
    obligatoires ; au-delà du seuil fixé par le secrétaire aux finances, la pièce d'identité et
    l'origine des fonds le deviennent aussi (vérification renforcée)."""
    if not donateur_nom.strip() or not adresse.strip():
        raise HTTPException(status_code=400, detail="Le nom et l'adresse du donateur sont obligatoires")
    if nature not in models.DON_NATURES:
        raise HTTPException(status_code=400, detail="Nature invalide")
    if valeur <= 0:
        raise HTTPException(status_code=400, detail="La valeur doit être positive")
    if date_don > datetime.date.today():
        raise HTTPException(status_code=400, detail="La date du don est dans le futur")
    if piece_type and piece_type not in models.PIECE_TYPES:
        raise HTTPException(status_code=400, detail="Type de pièce invalide")
    seuil = seuil_don(db)
    renforcee = seuil is not None and valeur >= seuil
    if renforcee and not ((piece_type or "") and (piece_numero or "").strip() and (origine_fonds or "").strip()):
        raise HTTPException(status_code=400, detail=(
            f"Don supérieur ou égal au seuil de {fcfa(seuil)} : la pièce d'identité (type et numéro) et l'origine "
            "des fonds sont obligatoires (vérification renforcée)"))
    don = models.Don(
        donateur_nom=donateur_nom.strip(), adresse=adresse.strip(), telephone=(telephone or "").strip() or None,
        piece_type=piece_type or None, piece_numero=(piece_numero or "").strip() or None, nature=nature,
        description=(description or "").strip() or None, valeur=valeur, date_don=date_don,
        origine_fonds=(origine_fonds or "").strip() or None, verification_renforcee=renforcee,
        created_by_id=user.id)
    db.add(don)
    db.flush()
    log_action(db, user, "creation", "don", don.id, f"{fcfa(valeur)}{' — vérification renforcée' if renforcee else ''}")
    return don


# ---------- Budget ----------

def set_budget_line(db: Session, user, annee: int, sens: str, categorie: str, montant: int) -> None:
    valid = models.BUDGET_RECETTE_CATEGORIES if sens == "recette" else models.DEPENSE_CATEGORIES
    if sens not in models.BUDGET_SENS or categorie not in valid:
        raise HTTPException(status_code=400, detail="Ligne de budget invalide")
    if montant < 0:
        raise HTTPException(status_code=400, detail="Le montant ne peut pas être négatif")
    b = db.query(models.BudgetAnnee).filter_by(annee=annee).first()
    if b and b.statut == "valide":
        raise HTTPException(status_code=409, detail="Le budget est validé par l'AGA : il n'est plus modifiable")
    if not b:
        b = models.BudgetAnnee(annee=annee)
        db.add(b)
        db.flush()
    ligne = next((x for x in b.lignes if x.sens == sens and x.categorie == categorie), None)
    if ligne:
        ligne.montant_prevu = montant
    else:
        b.lignes.append(models.BudgetLigne(sens=sens, categorie=categorie, montant_prevu=montant))
    db.flush()
    log_action(db, user, "budget", "budget", b.id, f"{annee} {sens}/{categorie}: {montant}")


def validate_budget(db: Session, user, annee: int, reference: str) -> None:
    b = db.query(models.BudgetAnnee).filter_by(annee=annee).first()
    if not b or not b.lignes:
        raise HTTPException(status_code=400, detail="Aucun budget à valider pour cette année")
    if b.statut == "valide":
        raise HTTPException(status_code=409, detail="Budget déjà validé")
    if not reference.strip():
        raise HTTPException(status_code=400, detail="La référence de la résolution de l'AGA est obligatoire")
    b.statut, b.reference_validation = "valide", reference.strip()
    log_action(db, user, "validation_budget", "budget", b.id, f"{annee} — {reference.strip()}")


# ---------- Contrôle : rapports des commissaires et déclarations d'intérêt ----------

def add_rapport_cc(db: Session, user, annee: int, titre: str, texte: str) -> models.RapportCC:
    if not titre.strip() or not texte.strip():
        raise HTTPException(status_code=400, detail="Titre et texte obligatoires")
    r = models.RapportCC(annee=annee, titre=titre.strip(), texte=texte.strip(), auteur_id=user.id,
                         auteur_nom=user.full_name)
    db.add(r)
    db.flush()
    log_action(db, user, "rapport_cc", "rapport", r.id, r.titre)
    return r


def declare_interet(db: Session, user, objet: str) -> models.DeclarationInteret:
    if not objet.strip():
        raise HTTPException(status_code=400, detail="Décrivez l'intérêt déclaré")
    d = models.DeclarationInteret(user_id=user.id, declarant_nom=user.full_name, objet=objet.strip())
    db.add(d)
    db.flush()
    log_action(db, user, "declaration_interet", "declaration", d.id, None)
    return d


# ---------- États financiers ----------

PERIODES = {"annee": "Exercice complet", "s1": "1er semestre (janvier–juin)", "s2": "2e semestre (juillet–décembre)"}


def _bornes(annee: int, periode: str) -> tuple[datetime.date, datetime.date]:
    if periode == "s1":
        return datetime.date(annee, 1, 1), datetime.date(annee, 6, 30)
    if periode == "s2":
        return datetime.date(annee, 7, 1), datetime.date(annee, 12, 31)
    return datetime.date(annee, 1, 1), datetime.date(annee, 12, 31)


def etat_financier(db: Session, annee: int, periode: str = "annee") -> dict:
    """Recettes encaissées et dépenses payées sur la période (comptabilité de caisse), avec les
    engagements non payés et la comparaison au budget (exercice complet)."""
    if periode not in PERIODES:
        raise HTTPException(status_code=400, detail="Période invalide")
    debut, fin = _bornes(annee, periode)

    coti = {"annuelle": 0, "adhesion": 0, "exceptionnelle": 0}
    for p in (db.query(models.Paiement).filter(models.Paiement.annule.is_(False),
                                                models.Paiement.date_paiement.between(debut, fin))):
        coti[p.echeance.type] = coti.get(p.echeance.type, 0) + p.montant
    dons = (db.query(func.coalesce(func.sum(models.Don.valeur), 0))
            .filter(models.Don.nature == "numeraire", models.Don.date_don.between(debut, fin)).scalar())
    dons_nature = (db.query(func.coalesce(func.sum(models.Don.valeur), 0))
                   .filter(models.Don.nature == "nature", models.Don.date_don.between(debut, fin)).scalar())
    autres = {c: 0 for c in models.RECETTE_CATEGORIES}
    for r in db.query(models.Recette).filter(models.Recette.date_recette.between(debut, fin)):
        autres[r.categorie] += r.montant
    recettes = {
        "Cotisations annuelles": coti["annuelle"], "Droits d'adhésion": coti["adhesion"],
        "Cotisations exceptionnelles": coti["exceptionnelle"], "Dons en numéraire": dons,
        "Subventions": autres["subvention"], "Autres recettes": autres["autre"],
    }
    depenses = {c: 0 for c in models.DEPENSE_CATEGORIES}
    for d in db.query(models.Depense).filter(models.Depense.statut == "payee",
                                              models.Depense.payee_le.between(debut, fin)):
        depenses[d.categorie] += d.montant
    engagees = sum(d.montant for d in db.query(models.Depense).filter(
        models.Depense.statut.in_(("a_valider", "validee")), models.Depense.date_depense.between(debut, fin)))
    total_rec, total_dep = sum(recettes.values()), sum(depenses.values())

    budget = db.query(models.BudgetAnnee).filter_by(annee=annee).first()
    comparaison = []
    if budget and periode == "annee":
        reel_recette = {"cotisations": coti["annuelle"] + coti["adhesion"] + coti["exceptionnelle"], "dons": dons,
                        "subvention": autres["subvention"], "autre": autres["autre"]}
        for l in budget.lignes:
            reel = reel_recette.get(l.categorie, 0) if l.sens == "recette" else depenses.get(l.categorie, 0)
            label = (models.BUDGET_RECETTE_CATEGORIES if l.sens == "recette" else models.DEPENSE_CATEGORIES)[l.categorie]
            comparaison.append({"sens": l.sens, "categorie": label, "prevu": l.montant_prevu, "reel": reel,
                                "ecart": reel - l.montant_prevu})
    return {
        "annee": annee, "periode": periode, "periode_label": PERIODES[periode], "debut": debut, "fin": fin,
        "recettes": recettes, "total_recettes": total_rec,
        "depenses": {models.DEPENSE_CATEGORIES[k]: v for k, v in depenses.items()}, "total_depenses": total_dep,
        "solde": total_rec - total_dep, "engagements_non_payes": engagees, "dons_en_nature": dons_nature,
        "budget": budget, "comparaison": comparaison,
    }


def etat_csv(e: dict) -> str:
    import csv
    import io
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([f"État financier PSIE — {e['periode_label']} {e['annee']}", f"du {e['debut']} au {e['fin']}"])
    w.writerow([])
    w.writerow(["RECETTES", "FCFA"])
    for k, v in e["recettes"].items():
        w.writerow([k, v])
    w.writerow(["Total recettes", e["total_recettes"]])
    w.writerow([])
    w.writerow(["DÉPENSES", "FCFA"])
    for k, v in e["depenses"].items():
        w.writerow([k, v])
    w.writerow(["Total dépenses", e["total_depenses"]])
    w.writerow([])
    w.writerow(["SOLDE (recettes - dépenses)", e["solde"]])
    w.writerow(["Dépenses engagées non payées", e["engagements_non_payes"]])
    w.writerow(["Dons en nature (valeur estimée, hors caisse)", e["dons_en_nature"]])
    if e["comparaison"]:
        w.writerow([])
        w.writerow(["BUDGET", "Prévu", "Réalisé", "Écart"])
        for c in e["comparaison"]:
            w.writerow([f"{'Recettes' if c['sens'] == 'recette' else 'Dépenses'} — {c['categorie']}",
                        c["prevu"], c["reel"], c["ecart"]])
    return out.getvalue()
