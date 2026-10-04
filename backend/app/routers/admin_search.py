"""Recherche globale pour le panneau admin — étend la recherche publique
(search_public.py) au courrier et aux tâches personnelles, deux types de contenu
interne invisibles du public. Réservée aux comptes du Bureau Exécutif National
connectés (require_login_api) : le courrier est en plus filtré par le module
`courrier` de l'utilisateur, et les tâches ne renvoient jamais que les siennes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_login_api
from ..text_matching import score_text as _score

router = APIRouter(prefix="/api/admin-search", tags=["admin-search"])

RESULTS_PER_TYPE = 5
MIN_SCORE = 0.35
CANDIDATES_CAP = 500


@router.get("", response_model=list[schemas.SearchResultOut])
def admin_search(
    q: str = Query(default="", max_length=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(require_login_api),
):
    term = q.strip()
    if len(term) < 2:
        return []

    results: list[tuple[float, schemas.SearchResultOut]] = []

    if user.has_module("courrier"):
        courriers = db.query(models.Courrier).limit(CANDIDATES_CAP).all()
        for c in courriers:
            score = _score(term, c.numero, c.correspondant, c.objet)
            if score >= MIN_SCORE:
                results.append((
                    score,
                    schemas.SearchResultOut(
                        type="courrier",
                        title=f"{c.type_label} — {c.numero}",
                        subtitle=c.objet,
                        url=f"/admin/courrier/{c.id}/edit",
                    ),
                ))

    taches = (
        db.query(models.TachePersonnelle)
        .filter(models.TachePersonnelle.user_id == user.id)
        .limit(CANDIDATES_CAP)
        .all()
    )
    for t in taches:
        score = _score(term, t.titre, t.description)
        if score >= MIN_SCORE:
            results.append((
                score,
                schemas.SearchResultOut(type="tache", title=t.titre, subtitle=t.description, url="/admin/taches"),
            ))

    results.sort(key=lambda r: r[0], reverse=True)

    per_type_count: dict[str, int] = {}
    output: list[schemas.SearchResultOut] = []
    for _, result in results:
        if per_type_count.get(result.type, 0) >= RESULTS_PER_TYPE:
            continue
        per_type_count[result.type] = per_type_count.get(result.type, 0) + 1
        output.append(result)

    return output
