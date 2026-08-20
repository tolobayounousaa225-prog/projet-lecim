"""Recherche globale sur le contenu public de la vitrine (écoles, actualités,
documents publiés, FAQ) — utilisée par la barre de recherche du site.

Le classement tolère les fautes de frappe et classe les résultats par
pertinence : plutôt que de filtrer en base avec un simple ILIKE (qui rate
tout terme mal orthographié), chaque type de contenu est chargé en entier
puis noté en Python avec difflib (voir text_matching.py) — volumes de
données modestes pour une association nationale, donc sans coût de
performance réel.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..text_matching import score_text as _score

router = APIRouter(prefix="/api/search", tags=["search"])

RESULTS_PER_TYPE = 5
MIN_SCORE = 0.35
CANDIDATES_CAP = 500


@router.get("", response_model=list[schemas.SearchResultOut])
def search(q: str = Query(default="", max_length=200), db: Session = Depends(get_db)):
    term = q.strip()
    if len(term) < 2:
        return []

    results: list[tuple[float, schemas.SearchResultOut]] = []

    ecoles = db.query(models.Etablissement).limit(CANDIDATES_CAP).all()
    for e in ecoles:
        score = _score(term, e.nom, e.bureau_local)
        if score >= MIN_SCORE:
            results.append((
                score,
                schemas.SearchResultOut(type="ecole", title=e.nom, subtitle=e.bureau_local, url=f"ecoles.html#ecole-{e.id}"),
            ))

    news = (
        db.query(models.NewsPost)
        .filter(models.NewsPost.is_published.is_(True))
        .limit(CANDIDATES_CAP)
        .all()
    )
    for n in news:
        score = _score(term, n.title, n.excerpt)
        if score >= MIN_SCORE:
            results.append((
                score,
                schemas.SearchResultOut(type="actualite", title=n.title, subtitle=n.excerpt[:80], url=f"actualite.html?id={n.id}"),
            ))

    publications = (
        db.query(models.PublicationPublique)
        .filter(models.PublicationPublique.is_published.is_(True))
        .limit(CANDIDATES_CAP)
        .all()
    )
    for p in publications:
        score = _score(term, p.title)
        if score >= MIN_SCORE:
            results.append((
                score,
                schemas.SearchResultOut(type="document", title=p.title, subtitle=None, url=f"/api/publications/{p.id}/file"),
            ))

    faqs = (
        db.query(models.Faq)
        .filter(models.Faq.is_published.is_(True))
        .limit(CANDIDATES_CAP)
        .all()
    )
    for f in faqs:
        score = _score(term, f.question, f.reponse)
        if score >= MIN_SCORE:
            results.append((
                score,
                schemas.SearchResultOut(type="faq", title=f.question, subtitle=None, url=f"faq.html#faq-{f.id}"),
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
