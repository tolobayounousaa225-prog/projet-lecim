"""Assistant automatisé de réponse aux questions fréquentes, affiché dans la
bulle de discussion sur toutes les pages de la vitrine. Pas d'IA générative :
il cherche la question de la FAQ publiée la plus proche de celle posée (voir
text_matching.py) et en renvoie la réponse telle qu'écrite par l'admin —
gratuit, instantané, sans clé API ni compte externe."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..rate_limit import rate_limiter
from ..text_matching import score_text

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

MIN_SCORE = 0.4


@router.get("/ask", response_model=schemas.AssistantAnswerOut, dependencies=[Depends(rate_limiter("assistant-ask", 30, 60))])
def ask(q: str = Query(..., min_length=2, max_length=300), db: Session = Depends(get_db)):
    term = q.strip()
    faqs = db.query(models.Faq).filter(models.Faq.is_published.is_(True)).all()

    best: models.Faq | None = None
    best_score = 0.0
    for faq in faqs:
        score = score_text(term, faq.question, faq.reponse)
        if score > best_score:
            best_score = score
            best = faq

    if best and best_score >= MIN_SCORE:
        return schemas.AssistantAnswerOut(found=True, question=best.question, reponse=best.reponse)
    return schemas.AssistantAnswerOut(found=False)
