"""Recherche globale : une seule zone de saisie, des résultats groupés, limités à ce que la personne a le droit de voir."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import get_current_user
from ..web import render

router = APIRouter()
LIMIT = 15


def _like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@router.get("/recherche")
def search(request: Request, q: str = "", user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = q.strip()[:80]
    groups: list[tuple[str, list[tuple[str, str, str]]]] = []          # (clé du titre, [(lien, titre, détail)])
    if len(q) >= 2:
        like = _like(q)

        def add(key, rows):
            if rows:
                groups.append((key, rows))

        if user.is_internal:
            if user.can("membres"):
                add("gs_members", [(f"/faitieres/{f.id}", f.sigle, f.nom) for f in db.query(models.Faitiere).filter(
                    models.Faitiere.sigle.ilike(like, escape="\\") | models.Faitiere.nom.ilike(like, escape="\\")).limit(LIMIT)])
                add("gs_mandates", [(f"/faitieres/{m.faitiere_id}", m.full_name, m.fonction or m.organe) for m in db.query(models.Mandat)
                                    .filter(models.Mandat.full_name.ilike(like, escape="\\"), models.Mandat.faitiere_id.is_not(None)).limit(LIMIT)])
            if user.can("ecoles"):
                add("gs_schools", [(f"/faitieres/{e.faitiere_id}/ecoles/{e.id}", e.nom, " · ".join(x for x in (e.localite, e.directeur) if x))
                                   for e in db.query(models.Ecole).filter(models.Ecole.nom.ilike(like, escape="\\")
                                                                          | models.Ecole.localite.ilike(like, escape="\\")
                                                                          | models.Ecole.directeur.ilike(like, escape="\\")).limit(LIMIT)])
            if user.can("adhesions"):
                add("gs_applications", [(f"/adhesions/{d.id}", f"{d.sigle} — {d.nom}", d.code) for d in db.query(models.DemandeAdhesion).filter(
                    models.DemandeAdhesion.nom.ilike(like, escape="\\") | models.DemandeAdhesion.sigle.ilike(like, escape="\\")
                    | models.DemandeAdhesion.code.ilike(like, escape="\\")).limit(LIMIT)])
            if user.can("documents"):
                docs = db.query(models.Document).filter(models.Document.titre.ilike(like, escape="\\"))
                if not user.can("documents", True):
                    docs = docs.filter(models.Document.restreint.is_(False))
                add("gs_documents", [(f"/documents/{d.id}/fichier", d.titre, d.categorie_label) for d in docs.limit(LIMIT)])
                add("gs_mail", [(f"/courrier/{c.id}", f"{c.numero} — {c.objet}", c.correspondant) for c in db.query(models.Courrier).filter(
                    models.Courrier.objet.ilike(like, escape="\\") | models.Courrier.correspondant.ilike(like, escape="\\")
                    | models.Courrier.numero.ilike(like, escape="\\") | models.Courrier.reference_externe.ilike(like, escape="\\")).limit(LIMIT)])
                add("gs_agreements", [(f"/conventions/{c.id}", c.titre, c.partenaire) for c in db.query(models.Convention).filter(
                    models.Convention.titre.ilike(like, escape="\\") | models.Convention.partenaire.ilike(like, escape="\\")).limit(LIMIT)])
            if user.is_admin:
                add("gs_users", [("/users", u.full_name, u.email) for u in db.query(models.User).filter(
                    models.User.full_name.ilike(like, escape="\\") | models.User.email.ilike(like, escape="\\")).limit(LIMIT)])
        elif user.faitiere_id:                                         # une faîtière ne cherche que dans ses propres données
            add("gs_schools", [(f"/faitieres/{e.faitiere_id}/ecoles/{e.id}", e.nom, e.localite or "")
                               for e in db.query(models.Ecole).filter(models.Ecole.faitiere_id == user.faitiere_id,
                                                                      models.Ecole.nom.ilike(like, escape="\\")
                                                                      | models.Ecole.localite.ilike(like, escape="\\")).limit(LIMIT)])
            add("gs_announcements", [("/annonces", a.titre, a.created_at.strftime("%d/%m/%Y")) for a in db.query(models.Annonce).filter(
                (models.Annonce.faitiere_id.is_(None) | (models.Annonce.faitiere_id == user.faitiere_id))
                & models.Annonce.titre.ilike(like, escape="\\")).limit(LIMIT)])
    return render(request, "recherche.html", user, q=q, groups=groups, short=bool(q) and len(q) < 2)
