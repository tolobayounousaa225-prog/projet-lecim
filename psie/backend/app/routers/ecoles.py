"""Écoles d'une faîtière : fiche, recensement du personnel et des élèves, résultats d'examens, bilans annuels.

La faîtière tient ses écoles à jour elle-même et ne voit jamais celles des autres. Les secrétariats concernés
(rubrique « Écoles et suivi des faîtières ») les consultent, les corrigent s'ils ont le droit de modification,
et examinent les bilans proposés (validation ou demande de correction)."""

import csv
import datetime
import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from .. import imports, models, stats
from ..audit import log_action
from ..database import get_db
from ..deps import get_current_user
from ..web import clean, render

router = APIRouter()

MAX_IMPORT_BYTES = 200_000
MAX_IMPORT_ROWS = 500


def _faitiere(db: Session, user: models.User, faitiere_id: int, write: bool = False) -> models.Faitiere:
    f = db.get(models.Faitiere, faitiere_id)
    if not f or not user.can_view_faitiere(faitiere_id):
        raise HTTPException(status_code=404, detail="Faîtière introuvable")
    if user.is_internal and not user.can("ecoles", write):
        raise HTTPException(status_code=403, detail="Cette rubrique ne fait pas partie de votre espace")
    if write and not user.is_internal and user.faitiere_id != faitiere_id:
        raise HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")
    return f


def _ecole(db: Session, f: models.Faitiere, ecole_id: int) -> models.Ecole:
    e = db.get(models.Ecole, ecole_id)
    if not e or e.faitiere_id != f.id:                                   # jamais l'école d'une autre faîtière
        raise HTTPException(status_code=404, detail="École introuvable")
    return e


def _int(value: str, label: str, low: int = 0, high: int = 1_000_000) -> int:
    try:
        n = int((value or "0").strip() or 0)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{label} : nombre entier attendu")
    if not low <= n <= high:
        raise HTTPException(status_code=400, detail=f"{label} : valeur hors limites")
    return n


def _year(value: str) -> int:
    return _int(value, "Année", 1990, datetime.date.today().year + 1)


def _text(value: str, label: str, required: bool = False, limit: int = 255) -> str | None:
    v = clean(value)
    if required and not v:
        raise HTTPException(status_code=400, detail=f"{label} : champ obligatoire")
    if v and len(v) > limit:
        raise HTTPException(status_code=400, detail=f"{label} : texte trop long")
    return v


def _niveau(value: str) -> str | None:
    v = clean(value)
    if v and v not in models.NIVEAUX_ECOLE:
        raise HTTPException(status_code=400, detail="Niveau inconnu")
    return v


def _back(f: models.Faitiere, e: models.Ecole | None = None) -> RedirectResponse:
    return RedirectResponse(f"/faitieres/{f.id}/ecoles" + (f"/{e.id}" if e else ""), status_code=303)


@router.get("/faitieres/{faitiere_id}/ecoles")
def ecoles_list(faitiere_id: int, request: Request, annee: int | None = None, user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    f = _faitiere(db, user, faitiere_id)
    annee = annee or stats.current_year()
    ecoles = db.query(models.Ecole).filter_by(faitiere_id=f.id).order_by(models.Ecole.nom).all()
    recs = {r.ecole_id: r for e in ecoles for r in e.recensements if r.annee == annee}
    row = stats.faitiere_row(db, f, annee)
    can_write = user.faitiere_id == faitiere_id or user.can("ecoles", True)
    return render(request, "ecoles_liste.html", user, f=f, ecoles=ecoles, recs=recs, row=row, annee=annee,
                  years=stats.years(db), can_write=can_write, niveaux=models.NIVEAUX_ECOLE)


@router.post("/faitieres/{faitiere_id}/ecoles")
def ecole_add(faitiere_id: int, nom: str = Form(""), localite: str = Form(""), drena: str = Form(""),
              telephone: str = Form(""), niveau: str = Form(""), directeur: str = Form(""),
              user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = _faitiere(db, user, faitiere_id, write=True)
    e = models.Ecole(faitiere_id=f.id, nom=_text(nom, "Nom", True), localite=_text(localite, "Localité"),
                     drena=_text(drena, "DRENA", limit=80), telephone=_text(telephone, "Téléphone", limit=40),
                     niveau=_niveau(niveau), directeur=_text(directeur, "Directeur"))
    db.add(e)
    db.flush()
    log_action(db, user, "creation", "ecoles", e.id, e.nom)
    db.commit()
    return _back(f)


@router.post("/faitieres/{faitiere_id}/ecoles/import")
async def ecoles_import(faitiere_id: int, fichier: UploadFile = File(...), user: models.User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """Import d'un fichier CSV (exporté d'Excel) : nom;localité;DRENA;téléphone;niveau;directeur."""
    f = _faitiere(db, user, faitiere_id, write=True)
    raw = await fichier.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    delimiter = ";" if text.count(";") >= text.count(",") else ","
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in r)]
    if rows and rows[0] and rows[0][0].strip().lower() in ("nom", "école", "ecole"):
        rows = rows[1:]
    if not rows or len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(status_code=400, detail=f"Le fichier doit contenir entre 1 et {MAX_IMPORT_ROWS} écoles")
    known = {e.nom.lower() for e in db.query(models.Ecole).filter_by(faitiere_id=f.id)}
    created = 0
    for i, r in enumerate(rows, start=1):
        r = (r + [""] * 6)[:6]
        nom = _text(r[0], f"Ligne {i} : nom", True)
        if nom.lower() in known:
            continue                                                       # une école déjà enregistrée n'est pas dupliquée
        niveau = clean(r[4]).lower() if clean(r[4]) else None
        db.add(models.Ecole(faitiere_id=f.id, nom=nom, localite=_text(r[1], "Localité"), drena=_text(r[2], "DRENA", limit=80),
                            telephone=_text(r[3], "Téléphone", limit=40),
                            niveau=niveau if niveau in models.NIVEAUX_ECOLE else None, directeur=_text(r[5], "Directeur")))
        known.add(nom.lower())
        created += 1
    log_action(db, user, "import", "ecoles", f.id, f"{created} école(s)")
    db.commit()
    return _back(f)


@router.get("/faitieres/{faitiere_id}/export-ecoles.csv")
def ecoles_export(faitiere_id: int, annee: int | None = None, user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    f = _faitiere(db, user, faitiere_id)
    annee = annee or stats.current_year()
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    w.writerow(["École", "Localité", "DRENA", "Niveau", "Directeur", "Téléphone", f"Élèves {annee}", "Administratifs francophones",
                "Administratifs arabisants", "Enseignants francophones", "Enseignants arabisants", "Personnel total"])
    for e in db.query(models.Ecole).filter_by(faitiere_id=f.id).order_by(models.Ecole.nom):
        r = next((x for x in e.recensements if x.annee == annee), None)
        w.writerow([_safe(e.nom), _safe(e.localite), _safe(e.drena), e.niveau_label, _safe(e.directeur), _safe(e.telephone),
                    *( [r.eleves, r.admin_francophone, r.admin_arabisant, r.ens_francophone, r.ens_arabisant, r.personnel_total]
                       if r else [""] * 6)])
    return Response("﻿" + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="ecoles-{f.sigle}-{annee}.csv"'})


def _safe(value: str | None) -> str:
    """Neutralise les formules Excel (=, +, -, @) dans les exports."""
    v = value or ""
    return "'" + v if v[:1] in ("=", "+", "-", "@") else v


@router.get("/faitieres/{faitiere_id}/ecoles/{ecole_id}")
def ecole_detail(faitiere_id: int, ecole_id: int, request: Request, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    f = _faitiere(db, user, faitiere_id)
    e = _ecole(db, f, ecole_id)
    can_write = user.faitiere_id == faitiere_id or user.can("ecoles", True)
    return render(request, "ecole_detail.html", user, f=f, e=e, can_write=can_write, can_review=user.is_internal and user.can("ecoles", True),
                  niveaux=models.NIVEAUX_ECOLE, examens=models.EXAMENS, year=stats.current_year())


@router.post("/faitieres/{faitiere_id}/ecoles/{ecole_id}/modifier")
def ecole_update(faitiere_id: int, ecole_id: int, nom: str = Form(""), localite: str = Form(""), drena: str = Form(""),
                 telephone: str = Form(""), niveau: str = Form(""), directeur: str = Form(""),
                 user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = _faitiere(db, user, faitiere_id, write=True)
    e = _ecole(db, f, ecole_id)
    e.nom, e.localite, e.drena = _text(nom, "Nom", True), _text(localite, "Localité"), _text(drena, "DRENA", limit=80)
    e.telephone, e.niveau, e.directeur = _text(telephone, "Téléphone", limit=40), _niveau(niveau), _text(directeur, "Directeur")
    log_action(db, user, "modification", "ecoles", e.id, e.nom)
    db.commit()
    return _back(f, e)


@router.post("/faitieres/{faitiere_id}/ecoles/{ecole_id}/supprimer")
def ecole_delete(faitiere_id: int, ecole_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = _faitiere(db, user, faitiere_id, write=True)
    e = _ecole(db, f, ecole_id)
    log_action(db, user, "suppression", "ecoles", e.id, e.nom)
    db.delete(e)
    db.commit()
    return _back(f)


@router.post("/faitieres/{faitiere_id}/ecoles/{ecole_id}/recensement")
def recensement_save(faitiere_id: int, ecole_id: int, annee: str = Form(""), eleves: str = Form("0"),
                     admin_francophone: str = Form("0"), admin_arabisant: str = Form("0"),
                     ens_francophone: str = Form("0"), ens_arabisant: str = Form("0"),
                     user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = _faitiere(db, user, faitiere_id, write=True)
    e = _ecole(db, f, ecole_id)
    year = _year(annee)
    values = {"eleves": _int(eleves, "Élèves"), "admin_francophone": _int(admin_francophone, "Administratifs francophones", 0, 10000),
              "admin_arabisant": _int(admin_arabisant, "Administratifs arabisants", 0, 10000),
              "ens_francophone": _int(ens_francophone, "Enseignants francophones", 0, 10000),
              "ens_arabisant": _int(ens_arabisant, "Enseignants arabisants", 0, 10000)}
    r = next((x for x in e.recensements if x.annee == year), None)
    if r is None:
        r = models.RecensementEcole(ecole_id=e.id, annee=year)
        db.add(r)
    for k, v in values.items():
        setattr(r, k, v)
    r.updated_at = datetime.datetime.utcnow()
    log_action(db, user, "recensement", "ecoles", e.id, f"{e.nom} {year}")
    db.commit()
    return _back(f, e)


@router.post("/faitieres/{faitiere_id}/ecoles/{ecole_id}/examens")
def examen_save(faitiere_id: int, ecole_id: int, annee: str = Form(""), examen: str = Form(""), inscrits: str = Form("0"),
                admis: str = Form("0"), user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = _faitiere(db, user, faitiere_id, write=True)
    e = _ecole(db, f, ecole_id)
    if examen not in models.EXAMENS:
        raise HTTPException(status_code=400, detail="Examen inconnu")
    year, n_in, n_ok = _year(annee), _int(inscrits, "Candidats inscrits"), _int(admis, "Admis")
    if n_in < 1 or n_ok > n_in:
        raise HTTPException(status_code=400, detail="Le nombre d'admis ne peut pas dépasser celui des candidats")
    r = next((x for x in e.resultats if x.annee == year and x.examen == examen), None)
    if r is None:
        r = models.ResultatExamen(ecole_id=e.id, annee=year, examen=examen, inscrits=n_in, admis=n_ok)
        db.add(r)
    r.inscrits, r.admis = n_in, n_ok
    log_action(db, user, "resultat_examen", "ecoles", e.id, f"{e.nom} {examen} {year}")
    db.commit()
    return _back(f, e)


@router.post("/faitieres/{faitiere_id}/ecoles/{ecole_id}/examens/{resultat_id}/supprimer")
def examen_delete(faitiere_id: int, ecole_id: int, resultat_id: int, user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    f = _faitiere(db, user, faitiere_id, write=True)
    e = _ecole(db, f, ecole_id)
    r = db.get(models.ResultatExamen, resultat_id)
    if not r or r.ecole_id != e.id:
        raise HTTPException(status_code=404, detail="Résultat introuvable")
    db.delete(r)
    log_action(db, user, "suppression", "resultat_examen", r.id, e.nom)
    db.commit()
    return _back(f, e)


@router.post("/faitieres/{faitiere_id}/ecoles/{ecole_id}/bilans")
def bilan_save(faitiere_id: int, ecole_id: int, annee: str = Form(""), resume: str = Form(""), difficultes: str = Form(""),
               perspectives: str = Form(""), action: str = Form("brouillon"), user: models.User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    f = _faitiere(db, user, faitiere_id, write=True)
    e = _ecole(db, f, ecole_id)
    year = _year(annee)
    b = next((x for x in e.bilans if x.annee == year), None)
    if b is not None and b.statut == "valide":
        raise HTTPException(status_code=400, detail="Ce bilan est validé : il ne peut plus être modifié")
    if b is None:
        b = models.BilanEcole(ecole_id=e.id, annee=year, resume="")
        db.add(b)
    b.resume = _text(resume, "Résumé", True, 5000)
    b.difficultes, b.perspectives = _text(difficultes, "Difficultés", limit=5000), _text(perspectives, "Perspectives", limit=5000)
    b.statut = "soumis" if action == "soumettre" else "brouillon"
    b.updated_at = datetime.datetime.utcnow()
    log_action(db, user, "bilan_" + b.statut, "ecoles", e.id, f"{e.nom} {year}")
    db.commit()
    return _back(f, e)


@router.post("/faitieres/{faitiere_id}/ecoles/{ecole_id}/bilans/{bilan_id}/decision")
def bilan_decision(faitiere_id: int, ecole_id: int, bilan_id: int, decision: str = Form(""), avis: str = Form(""),
                   user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Examen d'un bilan proposé : réservé aux secrétariats habilités, jamais à la faîtière elle-même."""
    if not user.is_internal:
        raise HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")
    f = _faitiere(db, user, faitiere_id, write=True)
    e = _ecole(db, f, ecole_id)
    b = db.get(models.BilanEcole, bilan_id)
    if not b or b.ecole_id != e.id:
        raise HTTPException(status_code=404, detail="Bilan introuvable")
    if b.statut != "soumis":
        raise HTTPException(status_code=400, detail="Seul un bilan proposé peut être examiné")
    if decision not in ("valider", "a_corriger"):
        raise HTTPException(status_code=400, detail="Décision inconnue")
    b.avis = _text(avis, "Avis", decision == "a_corriger", 2000)
    b.statut = "valide" if decision == "valider" else "a_corriger"
    log_action(db, user, "bilan_" + b.statut, "ecoles", e.id, f"{e.nom} {b.annee}")
    db.commit()
    return _back(f, e)


# ---------- Imports en lot : recensement du personnel et résultats d'examens (CSV d'Excel) ----------

IMPORTS = {"recensement": imports.recensement, "examens": imports.examens}


@router.post("/faitieres/{faitiere_id}/import-{kind}")
async def bulk_import(faitiere_id: int, kind: str, request: Request, fichier: UploadFile = File(...), simuler: str = Form(""),
                      user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if kind not in IMPORTS:
        raise HTTPException(status_code=404, detail="Import inconnu")
    f = _faitiere(db, user, faitiere_id, write=True)
    raw = await fichier.read(imports.MAX_BYTES + 1)
    try:
        report = IMPORTS[kind](db, f, raw, apply=not simuler)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    applied = bool(report.clean and not simuler)
    if applied:
        log_action(db, user, "import", "ecoles", f.id, f"{kind} : {len(report.ok)} ligne(s)")
    db.commit()
    return render(request, "import_rapport.html", user, report=report, applied=applied, back=f"/faitieres/{f.id}/ecoles",
                  status_code=200 if report.clean else 400)
