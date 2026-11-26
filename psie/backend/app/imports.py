"""Imports en lot depuis Excel (CSV) : recensement du personnel, résultats d'examens, liste des membres.

Principe commun : tout le fichier est contrôlé d'abord ; s'il y a la moindre erreur, rien n'est enregistré et un
rapport ligne par ligne est présenté. La « simulation » montre ce qui serait fait sans rien écrire."""

import csv
import datetime
import io
import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from . import models

MAX_BYTES = 300_000
MAX_ROWS = 1000


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKD", (text or "").lower()).encode("ascii", "ignore").decode())


def read_rows(raw: bytes, columns: dict[str, tuple[str, ...]]) -> list[dict]:
    """Lit un CSV : séparateur ; ou , détecté, en-têtes tolérants (accents, majuscules, synonymes).
    Retourne une liste de dicts {colonne: texte, "_line": n°}. Les colonnes sont celles de `columns` (clé -> synonymes)."""
    if len(raw) > MAX_BYTES:
        raise ValueError("Fichier trop volumineux.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    delimiter = ";" if text.count(";") >= text.count(",") else ","
    table = [r for r in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in r)]
    if len(table) < 2:
        raise ValueError("Le fichier doit contenir une ligne d'en-têtes puis au moins une ligne de données.")
    if len(table) - 1 > MAX_ROWS:
        raise ValueError(f"Trop de lignes : {MAX_ROWS} au maximum.")
    header = [norm(h) for h in table[0]]
    index = {}
    for key, synonyms in columns.items():
        names = {norm(key)} | {norm(s) for s in synonyms}
        found = next((i for i, h in enumerate(header) if h in names), None)
        if found is not None:
            index[key] = found
    missing = [k for k in columns if k not in index and k in REQUIRED.get(id(columns), ())]
    if missing:
        raise ValueError("Colonne(s) manquante(s) : " + ", ".join(missing))
    out = []
    for n, row in enumerate(table[1:], start=2):
        d = {k: (row[i].strip() if i < len(row) else "") for k, i in index.items()}
        d["_line"] = n
        out.append(d)
    return out


REQUIRED: dict[int, tuple[str, ...]] = {}


@dataclass
class Report:
    ok: list[str] = field(default_factory=list)          # ce qui sera (ou a été) fait
    errors: list[str] = field(default_factory=list)      # "ligne N : message"

    @property
    def clean(self) -> bool:
        return not self.errors


def _int(value: str, label: str, low: int = 0, high: int = 1_000_000) -> int:
    v = (value or "0").strip() or "0"
    if not re.fullmatch(r"\d+", v) or not low <= int(v) <= high:
        raise ValueError(f"{label} : nombre entier entre {low} et {high} attendu (reçu « {value} »)")
    return int(v)


def _year(value: str) -> int:
    return _int(value, "année", 1990, datetime.date.today().year + 1)


# ------------------------------------------------------------------ Recensement du personnel

RECENSEMENT_COLS = {
    "ecole": ("école", "etablissement", "nom"), "annee": ("année", "annee scolaire"), "eleves": ("élèves", "effectif"),
    "admin_francophone": ("administratifs francophones", "admin fr"), "admin_arabisant": ("administratifs arabisants", "admin ar"),
    "ens_francophone": ("enseignants francophones", "ens fr"), "ens_arabisant": ("enseignants arabisants", "ens ar"),
}
REQUIRED[id(RECENSEMENT_COLS)] = ("ecole", "annee")


def recensement(db: Session, faitiere: models.Faitiere, raw: bytes, apply: bool) -> Report:
    rows = read_rows(raw, RECENSEMENT_COLS)
    schools = {norm(e.nom): e for e in db.query(models.Ecole).filter_by(faitiere_id=faitiere.id)}
    rep, todo = Report(), []
    for r in rows:
        try:
            school = schools.get(norm(r.get("ecole", "")))
            if not school:
                raise ValueError(f"école inconnue « {r.get('ecole', '')} » (ajoutez-la d'abord à la liste des écoles)")
            values = {k: _int(r.get(k, ""), k) for k in ("eleves", "admin_francophone", "admin_arabisant", "ens_francophone", "ens_arabisant")}
            todo.append((school, _year(r.get("annee", "")), values))
            rep.ok.append(f"ligne {r['_line']} : {school.nom} — {todo[-1][1]}")
        except ValueError as e:
            rep.errors.append(f"ligne {r['_line']} : {e}")
    if apply and rep.clean:
        for school, year, values in todo:
            rec = next((x for x in school.recensements if x.annee == year), None)
            if rec is None:
                rec = models.RecensementEcole(ecole_id=school.id, annee=year)
                db.add(rec)
            for k, v in values.items():
                setattr(rec, k, v)
            rec.updated_at = datetime.datetime.utcnow()
    return rep


# ------------------------------------------------------------------ Résultats d'examens

EXAMEN_COLS = {"ecole": ("école", "etablissement", "nom"), "annee": ("année",), "examen": ("examen",),
               "inscrits": ("candidats", "présentés"), "admis": ("admis", "reçus")}
REQUIRED[id(EXAMEN_COLS)] = ("ecole", "annee", "examen", "inscrits", "admis")
EXAMEN_ALIASES = {norm(k): k for k in models.EXAMENS} | {norm(v): k for k, v in models.EXAMENS.items()}


def examens(db: Session, faitiere: models.Faitiere, raw: bytes, apply: bool) -> Report:
    rows = read_rows(raw, EXAMEN_COLS)
    schools = {norm(e.nom): e for e in db.query(models.Ecole).filter_by(faitiere_id=faitiere.id)}
    rep, todo = Report(), []
    for r in rows:
        try:
            school = schools.get(norm(r.get("ecole", "")))
            if not school:
                raise ValueError(f"école inconnue « {r.get('ecole', '')} »")
            exam = EXAMEN_ALIASES.get(norm(r.get("examen", "")))
            if not exam:
                raise ValueError(f"examen inconnu « {r.get('examen', '')} » (possibles : {', '.join(models.EXAMENS.values())})")
            n_in, n_ok = _int(r.get("inscrits", ""), "candidats"), _int(r.get("admis", ""), "admis")
            if n_in < 1 or n_ok > n_in:
                raise ValueError("le nombre d'admis ne peut pas dépasser celui des candidats (et il faut au moins un candidat)")
            todo.append((school, _year(r.get("annee", "")), exam, n_in, n_ok))
            rep.ok.append(f"ligne {r['_line']} : {school.nom} — {models.EXAMENS[exam]} {todo[-1][1]} ({n_ok}/{n_in})")
        except ValueError as e:
            rep.errors.append(f"ligne {r['_line']} : {e}")
    if apply and rep.clean:
        for school, year, exam, n_in, n_ok in todo:
            res = next((x for x in school.resultats if x.annee == year and x.examen == exam), None)
            if res is None:
                res = models.ResultatExamen(ecole_id=school.id, annee=year, examen=exam, inscrits=n_in, admis=n_ok)
                db.add(res)
            res.inscrits, res.admis = n_in, n_ok
    return rep


# ------------------------------------------------------------------ Liste des membres (faîtières)

MEMBRE_COLS = {"sigle": ("sigle",), "nom": ("nom", "dénomination", "denomination"), "categorie": ("catégorie",),
               "email": ("e-mail", "mail"), "telephone": ("téléphone", "tel"), "siege": ("siège",)}
REQUIRED[id(MEMBRE_COLS)] = ("sigle", "nom")
CAT_ALIASES = {norm(k): k for k in models.CATEGORIES} | {norm(v): k for k, v in models.CATEGORIES.items()} | {"": "ordinaire"}


def membres(db: Session, raw: bytes, apply: bool) -> Report:
    rows = read_rows(raw, MEMBRE_COLS)
    existing = {norm(f.sigle) for f in db.query(models.Faitiere)}
    seen: set[str] = set()
    rep, todo = Report(), []
    for r in rows:
        try:
            sigle, nom = r.get("sigle", "").strip(), r.get("nom", "").strip()
            if not sigle or not nom or len(sigle) > 50 or len(nom) > 255:
                raise ValueError("sigle et nom obligatoires (sigle ≤ 50 caractères)")
            if norm(sigle) in existing:
                raise ValueError(f"« {sigle} » existe déjà (laissée telle quelle : retirez la ligne)")
            if norm(sigle) in seen:
                raise ValueError(f"« {sigle} » en double dans le fichier")
            seen.add(norm(sigle))
            cat = CAT_ALIASES.get(norm(r.get("categorie", "")))
            if not cat:
                raise ValueError(f"catégorie inconnue « {r.get('categorie', '')} »")
            mail = r.get("email", "")
            if mail and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", mail):
                raise ValueError("adresse e-mail invalide")
            todo.append(models.Faitiere(sigle=sigle, nom=nom, categorie=cat, email=mail or None,
                                        telephone=(r.get("telephone") or None), siege=(r.get("siege") or None)))
            rep.ok.append(f"ligne {r['_line']} : {sigle} — {nom}")
        except ValueError as e:
            rep.errors.append(f"ligne {r['_line']} : {e}")
    if apply and rep.clean:
        db.add_all(todo)
    return rep
