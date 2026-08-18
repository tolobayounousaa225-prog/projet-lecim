"""Flux RSS des actualités publiques de la LECIM."""

import datetime
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/api/rss", tags=["rss"])


def _rfc822(d: datetime.date) -> str:
    dt = datetime.datetime.combine(d, datetime.time(8, 0))
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


@router.get("/actualites.xml")
def rss_actualites(db: Session = Depends(get_db)):
    items = (
        db.query(models.NewsPost)
        .filter(models.NewsPost.is_published.is_(True))
        .order_by(models.NewsPost.published_at.desc())
        .limit(30)
        .all()
    )

    entries = []
    for n in items:
        link = f"{settings.vitrine_base_url}/actualite.html?id={n.id}"
        entries.append(
            "<item>"
            f"<title>{escape(n.title)}</title>"
            f"<link>{escape(link)}</link>"
            f"<guid isPermaLink=\"true\">{escape(link)}</guid>"
            f"<pubDate>{_rfc822(n.published_at)}</pubDate>"
            f"<description>{escape(n.excerpt)}</description>"
            "</item>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0">'
        "<channel>"
        "<title>LECIM — Actualités</title>"
        f"<link>{escape(settings.vitrine_base_url)}/actualites.html</link>"
        "<description>Actualités de la Ligue des Établissements Confessionnels et Madrassas en Côte d'Ivoire</description>"
        "<language>fr</language>"
        + "".join(entries)
        + "</channel></rss>"
    )
    return Response(content=xml, media_type="application/rss+xml")
