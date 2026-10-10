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

    can_manage_delegations = user.is_admin or user.poste == "vp2_interieur"
    if user.can_manage_membres or can_manage_delegations:
        membres = db.query(models.Membre).limit(CANDIDATES_CAP).all()
        for m in membres:
            if m.delegation_id and not can_manage_delegations:
                continue
            if m.delegation_id is None and not user.can_manage_membres:
                continue
            score = _score(term, m.full_name, m.phone, m.email, m.poste_label)
            if score >= MIN_SCORE:
                # Pas de fiche individuelle côté admin pour un membre de délégation —
                # on renvoie vers la fiche de la délégation elle-même.
                url = f"/admin/delegations/{m.delegation_id}" if m.delegation_id else "/admin/membres"
                results.append((
                    score,
                    schemas.SearchResultOut(type="membre", title=m.full_name, subtitle=m.poste_label, url=url),
                ))

    if user.can_manage_finances:
        etablissements = db.query(models.Etablissement).limit(CANDIDATES_CAP).all()
        for e in etablissements:
            score = _score(term, e.nom, e.directeur_nom, e.bureau_local, e.contact_telephone)
            if score >= MIN_SCORE:
                results.append((
                    score,
                    schemas.SearchResultOut(
                        type="etablissement", title=e.nom, subtitle=e.bureau_local,
                        url=f"/admin/etablissements/{e.id}/edit",
                    ),
                ))

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
