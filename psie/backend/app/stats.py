"""Statistiques par faîtière : écoles, élèves, personnel, examens, bilans, cotisation.

Toutes les valeurs sont calculées à partir des recensements, résultats et bilans saisis par les faîtières :
rien n'est inventé. Une année sans recensement compte pour zéro."""

import datetime

from sqlalchemy.orm import Session

from . import finance, models


def current_year() -> int:
    return datetime.date.today().year


def years(db: Session) -> list[int]:
    found = {r[0] for r in db.query(models.RecensementEcole.annee).distinct()}
    found |= {r[0] for r in db.query(models.ResultatExamen.annee).distinct()}
    found.add(current_year())
    return sorted(found, reverse=True)


def faitiere_row(db: Session, f: models.Faitiere, annee: int) -> dict:
    ecoles = db.query(models.Ecole).filter_by(faitiere_id=f.id).all()
    ids = [e.id for e in ecoles]
    rec = db.query(models.RecensementEcole).filter(
        models.RecensementEcole.ecole_id.in_(ids or [0]), models.RecensementEcole.annee == annee).all()
    res = db.query(models.ResultatExamen).filter(
        models.ResultatExamen.ecole_id.in_(ids or [0]), models.ResultatExamen.annee == annee).all()
    bilans = db.query(models.BilanEcole).filter(
        models.BilanEcole.ecole_id.in_(ids or [0]), models.BilanEcole.annee == annee).all()
    inscrits, admis = sum(r.inscrits for r in res), sum(r.admis for r in res)
    row = {
        "faitiere": f, "id": f.id, "sigle": f.sigle, "ecoles": len(ecoles), "recensees": len({r.ecole_id for r in rec}),
        "eleves": sum(r.eleves for r in rec),
        "admin_francophone": sum(r.admin_francophone for r in rec), "admin_arabisant": sum(r.admin_arabisant for r in rec),
        "ens_francophone": sum(r.ens_francophone for r in rec), "ens_arabisant": sum(r.ens_arabisant for r in rec),
        "inscrits": inscrits, "admis": admis, "taux": round(100 * admis / inscrits, 1) if inscrits else None,
        "bilans_soumis": sum(1 for b in bilans if b.statut in ("soumis", "valide")),
        "bilans_valides": sum(1 for b in bilans if b.statut == "valide"),
        "a_jour": finance.faitiere_a_jour(db, f.id, annee),
    }
    row["admin"] = row["admin_francophone"] + row["admin_arabisant"]
    row["enseignants"] = row["ens_francophone"] + row["ens_arabisant"]
    row["francophones"] = row["admin_francophone"] + row["ens_francophone"]
    row["arabisants"] = row["admin_arabisant"] + row["ens_arabisant"]
    row["personnel"] = row["admin"] + row["enseignants"]
    return row


def all_rows(db: Session, annee: int) -> list[dict]:
    fs = db.query(models.Faitiere).order_by(models.Faitiere.sigle).all()
    return [faitiere_row(db, f, annee) for f in fs]


SUM_KEYS = ("ecoles", "recensees", "eleves", "admin_francophone", "admin_arabisant", "ens_francophone", "ens_arabisant",
            "admin", "enseignants", "francophones", "arabisants", "personnel", "inscrits", "admis",
            "bilans_soumis", "bilans_valides")


def totals(rows: list[dict]) -> dict:
    total = {k: sum(r[k] for r in rows) for k in SUM_KEYS}
    total["taux"] = round(100 * total["admis"] / total["inscrits"], 1) if total["inscrits"] else None
    total["a_jour"] = sum(1 for r in rows if r["a_jour"])
    return total


def averages(rows: list[dict]) -> dict:
    """Moyenne par faîtière (sans les nommer) : sert de repère à une faîtière sans révéler les chiffres des autres."""
    rows = [r for r in rows if r["ecoles"]] or rows                      # seules les faîtières qui ont des écoles comptent
    n = len(rows) or 1
    avg = {k: round(sum(r[k] for r in rows) / n, 1) for k in ("ecoles", "eleves", "personnel")}
    rated = [r["taux"] for r in rows if r["taux"] is not None]
    avg["taux"] = round(sum(rated) / len(rated), 1) if rated else None
    return avg


def exam_breakdown(db: Session, annee: int, faitiere_id: int | None = None) -> list[dict]:
    q = db.query(models.ResultatExamen).join(models.Ecole).filter(models.ResultatExamen.annee == annee)
    if faitiere_id is not None:
        q = q.filter(models.Ecole.faitiere_id == faitiere_id)
    out: dict[str, dict] = {}
    for r in q:
        d = out.setdefault(r.examen, {"examen": r.examen_label, "inscrits": 0, "admis": 0})
        d["inscrits"] += r.inscrits
        d["admis"] += r.admis
    for d in out.values():
        d["taux"] = round(100 * d["admis"] / d["inscrits"], 1) if d["inscrits"] else None
    return list(out.values())


def evolution(db: Session, faitiere_id: int | None = None) -> list[dict]:
    """Élèves, personnel et taux de réussite année par année."""
    out = []
    for annee in sorted(years(db)):
        rows = all_rows(db, annee) if faitiere_id is None else [faitiere_row(db, db.get(models.Faitiere, faitiere_id), annee)]
        t = totals(rows)
        if t["eleves"] or t["personnel"] or t["inscrits"]:
            out.append({"annee": annee, **t})
    return out


def dossier(db: Session, f: models.Faitiere, annee: int) -> dict:
    """Ce qu'il reste à compléter pour que le dossier de la faîtière soit à jour (barre de progression)."""
    row = faitiere_row(db, f, annee)
    n_delegues = db.query(models.DelegueRegional).filter_by(faitiere_id=f.id).count()
    n_pieces = db.query(models.PieceFaitiere).filter_by(faitiere_id=f.id).count()
    steps = [
        ("step_pieces", n_pieces > 0, f"/faitieres/{f.id}"),
        ("step_delegates", n_delegues > 0, f"/faitieres/{f.id}/delegues"),
        ("step_schools", row["ecoles"] > 0, f"/faitieres/{f.id}/ecoles"),
        ("step_census", row["ecoles"] > 0 and row["recensees"] >= row["ecoles"], f"/faitieres/{f.id}/ecoles"),
        ("step_reports", row["ecoles"] > 0 and row["bilans_soumis"] >= row["ecoles"], f"/faitieres/{f.id}/ecoles"),
        ("step_dues", row["a_jour"], f"/faitieres/{f.id}"),
    ]
    done = sum(1 for _, ok, _ in steps if ok)
    return {"steps": steps, "done": done, "total": len(steps), "percent": round(100 * done / len(steps)), "row": row}
