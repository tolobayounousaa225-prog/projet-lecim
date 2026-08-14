"""Recherche globale sur le contenu public de la vitrine (écoles, actualités,
documents publiés, FAQ) — utilisée par la barre de recherche du site."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/search", tags=["search"])

RESULTS_PER_TYPE = 5


@router.get("", response_model=list[schemas.SearchResultOut])
def search(q: str = Query(default="", max_length=200), db: Session = Depends(get_db)):
    term = q.strip()
    if len(term) < 2:
        return []
    like = f"%{term}%"
    results: list[schemas.SearchResultOut] = []

    ecoles = (
        db.query(models.Etablissement)
        .filter(
            (models.Etablissement.nom.ilike(like)) | (models.Etablissement.bureau_local.ilike(like))
        )
        .order_by(models.Etablissement.nom)
        .limit(RESULTS_PER_TYPE)
        .all()
    )
    for e in ecoles:
        results.append(
            schemas.SearchResultOut(
                type="ecole",
                title=e.nom,
                subtitle=e.bureau_local,
                url=f"ecoles.html#ecole-{e.id}",
            )
        )

    news = (
        db.query(models.NewsPost)
        .filter(models.NewsPost.is_published.is_(True), models.NewsPost.title.ilike(like))
        .order_by(models.NewsPost.published_at.desc())
        .limit(RESULTS_PER_TYPE)
        .all()
    )
    for n in news:
        results.append(
            schemas.SearchResultOut(
                type="actualite",
                title=n.title,
                subtitle=n.excerpt[:80],
                url=f"actualite.html?id={n.id}",
            )
        )

    publications = (
        db.query(models.PublicationPublique)
        .filter(models.PublicationPublique.is_published.is_(True), models.PublicationPublique.title.ilike(like))
        .order_by(models.PublicationPublique.published_at.desc())
        .limit(RESULTS_PER_TYPE)
        .all()
    )
    for p in publications:
        results.append(
            schemas.SearchResultOut(
                type="document",
                title=p.title,
                subtitle=None,
                url=f"/api/publications/{p.id}/file",
            )
        )

    faqs = (
        db.query(models.Faq)
        .filter(models.Faq.is_published.is_(True), models.Faq.question.ilike(like))
        .order_by(models.Faq.ordre)
        .limit(RESULTS_PER_TYPE)
        .all()
    )
    for f in faqs:
        results.append(
            schemas.SearchResultOut(
                type="faq",
                title=f.question,
                subtitle=None,
                url=f"faq.html#faq-{f.id}",
            )
        )

    return results
