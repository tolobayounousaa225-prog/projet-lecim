"""Statistiques par faîtière. La PSIE voit toutes les faîtières ; une faîtière ne voit que ses chiffres,
comparés à la moyenne (sans nommer les autres)."""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from .. import models, stats
from ..database import get_db
from ..deps import get_current_user
from ..routers.ecoles import _safe
from ..web import render

router = APIRouter()


def _year(annee: int | None) -> int:
    return annee or stats.current_year()


@router.get("/statistiques")
def overview(request: Request, annee: int | None = None, user: models.User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    if not user.is_internal:                                   # une faîtière est renvoyée vers ses propres chiffres
        return RedirectResponse(f"/faitieres/{user.faitiere_id}/statistiques", status_code=303)
    if not user.can("ecoles"):
        raise HTTPException(status_code=403, detail="Cette rubrique ne fait pas partie de votre espace")
    annee = _year(annee)
    rows = stats.all_rows(db, annee)
    return render(request, "statistiques.html", user, rows=rows, total=stats.totals(rows), annee=annee, years=stats.years(db),
                  exams=stats.exam_breakdown(db, annee), evolution=stats.evolution(db), show_dues=user.can_view_finances)


@router.get("/statistiques.csv")
def overview_csv(annee: int | None = None, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_internal or not user.can("ecoles"):
        raise HTTPException(status_code=403, detail="Cette rubrique ne fait pas partie de votre espace")
    annee = _year(annee)
    out = io.StringIO()
    w = csv.writer(out, delimiter=";")
    head = ["Faîtière", "Écoles", "Élèves", "Administratifs francophones", "Administratifs arabisants", "Enseignants francophones",
            "Enseignants arabisants", "Personnel total", "Candidats", "Admis", "Taux de réussite (%)", "Bilans validés"]
    if user.can_view_finances:
        head.append("Cotisation à jour")
    w.writerow(head)
    for r in stats.all_rows(db, annee):
        line = [_safe(r["sigle"]), r["ecoles"], r["eleves"], r["admin_francophone"], r["admin_arabisant"], r["ens_francophone"],
                r["ens_arabisant"], r["personnel"], r["inscrits"], r["admis"], "" if r["taux"] is None else r["taux"], r["bilans_valides"]]
        if user.can_view_finances:
            line.append("oui" if r["a_jour"] else "non")
        w.writerow(line)
    return Response("﻿" + out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="statistiques-{annee}.csv"'})


@router.get("/faitieres/{faitiere_id}/statistiques")
def faitiere_stats(faitiere_id: int, request: Request, annee: int | None = None, user: models.User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    f = db.get(models.Faitiere, faitiere_id)
    if not f or not user.can_view_faitiere(faitiere_id):
        raise HTTPException(status_code=404, detail="Faîtière introuvable")
    if user.is_internal and not user.can("ecoles"):
        raise HTTPException(status_code=403, detail="Cette rubrique ne fait pas partie de votre espace")
    annee = _year(annee)
    row = stats.faitiere_row(db, f, annee)
    return render(request, "faitiere_stats.html", user, f=f, row=row, annee=annee, years=stats.years(db),
                  avg=stats.averages(stats.all_rows(db, annee)), exams=stats.exam_breakdown(db, annee, f.id),
                  evolution=stats.evolution(db, f.id), show_dues=(not user.is_internal) or user.can_view_finances)
