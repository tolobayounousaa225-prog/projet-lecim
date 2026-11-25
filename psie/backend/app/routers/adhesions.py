"""Instruction des demandes d'adhésion et gestion des actualités (espace interne)."""


from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from .. import adhesion, models, pdfs
from ..audit import log_action
from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_internal, require_member_manager
from ..web import clean, parse_date, render

router = APIRouter()


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _get(db: Session, demande_id: int) -> models.DemandeAdhesion:
    d = db.get(models.DemandeAdhesion, demande_id)
    if not d:
        raise HTTPException(status_code=404, detail="Demande introuvable")
    return d


@router.get("/adhesions")
def adhesions_list(request: Request, user: models.User = Depends(require_internal), db: Session = Depends(get_db)):
    items = db.query(models.DemandeAdhesion).order_by(models.DemandeAdhesion.id.desc()).all()
    items.sort(key=lambda d: not d.is_open)  # demandes à traiter d'abord (tri stable)
    return render(request, "adhesions_list.html", user, items=items, etats=models.ADHESION_ETATS)


@router.get("/adhesions/{demande_id}")
def adhesion_detail(demande_id: int, request: Request, user: models.User = Depends(require_internal),
                    db: Session = Depends(get_db)):
    return render(request, "adhesion_detail.html", user, d=_get(db, demande_id), etats=models.ADHESION_ETATS)


@router.post("/adhesions/{demande_id}/examen")
def adhesion_examen(demande_id: int, notes: str = Form(""), user: models.User = Depends(require_member_manager),
                    db: Session = Depends(get_db)):
    d = _get(db, demande_id)
    adhesion.start_examen(db, user, d, notes)
    db.commit()
    return _redirect(f"/adhesions/{d.id}")


@router.post("/adhesions/{demande_id}/avis")
def adhesion_avis(demande_id: int, avis: str = Form(...), motif: str = Form(""),
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role not in models.ADHESION_AVIS_ROLES:
        raise HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")
    d = _get(db, demande_id)
    adhesion.record_avis(db, user, d, avis, motif)
    db.commit()
    return _redirect(f"/adhesions/{d.id}")


@router.post("/adhesions/{demande_id}/decision")
def adhesion_decision(demande_id: int, decision: str = Form(...), reference: str = Form(""),
                      date_decision: str = Form(""), motif: str = Form(""), droit_adhesion: str = Form(""),
                      user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    if decision not in ("accepter", "refuser"):
        raise HTTPException(status_code=400, detail="Décision invalide")
    montant = droit_adhesion.strip().replace(" ", "")
    if montant and not montant.isdigit():
        raise HTTPException(status_code=400, detail="Montant du droit d'adhésion invalide")
    d = _get(db, demande_id)
    adhesion.decide(db, user, d, accepter=decision == "accepter", reference=reference,
                    date_decision=parse_date(date_decision), motif=motif,
                    droit_adhesion=int(montant) if montant else None)
    db.commit()
    return _redirect(f"/adhesions/{d.id}")


@router.get("/adhesions/{demande_id}/certificat.pdf")
def certificate_pdf(demande_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = _get(db, demande_id)
    own = not user.is_internal and d.faitiere_id is not None and user.can_view_faitiere(d.faitiere_id)
    if not (user.can_manage_members or own) or d.etat != "acceptee" or not d.faitiere or not d.cert_token:
        raise HTTPException(status_code=404, detail="Certificat introuvable")
    url = f"{settings.public_base_url.rstrip('/')}/verifier/adhesion/{d.cert_token}"
    return Response(pdfs.membership_certificate_pdf(d, url), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="certificat-{d.faitiere.sigle}.pdf"'})


# ---------- Actualités (vitrine) ----------

@router.get("/gestion/actualites")
def news_admin(request: Request, user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    items = db.query(models.Actualite).order_by(models.Actualite.id.desc()).all()
    return render(request, "actualites_admin.html", user, items=items, item=None)


def _news_fields(titre_fr, titre_ar, contenu_fr, contenu_ar, publie, date_publication) -> dict:
    fields = dict(titre_fr=clean(titre_fr), titre_ar=clean(titre_ar), contenu_fr=clean(contenu_fr),
                  contenu_ar=clean(contenu_ar), publie=bool(publie))
    if not (fields["titre_fr"] or fields["titre_ar"]):
        raise HTTPException(status_code=400, detail="Un titre (français ou arabe) est obligatoire")
    when = parse_date(date_publication)
    if when:
        fields["date_publication"] = when
    return fields


@router.post("/gestion/actualites")
def news_create(titre_fr: str = Form(""), titre_ar: str = Form(""), contenu_fr: str = Form(""),
                contenu_ar: str = Form(""), publie: str = Form(""), date_publication: str = Form(""),
                user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    item = models.Actualite(created_by_id=user.id,
                            **_news_fields(titre_fr, titre_ar, contenu_fr, contenu_ar, publie, date_publication))
    db.add(item)
    db.flush()
    log_action(db, user, "creation", "actualite", item.id, item.titre("fr"))
    db.commit()
    return _redirect("/gestion/actualites")


@router.get("/gestion/actualites/{item_id}/edit")
def news_edit_form(item_id: int, request: Request, user: models.User = Depends(require_member_manager),
                   db: Session = Depends(get_db)):
    item = db.get(models.Actualite, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Actualité introuvable")
    return render(request, "actualites_admin.html", user, items=[], item=item)


@router.post("/gestion/actualites/{item_id}/edit")
def news_edit(item_id: int, titre_fr: str = Form(""), titre_ar: str = Form(""), contenu_fr: str = Form(""),
              contenu_ar: str = Form(""), publie: str = Form(""), date_publication: str = Form(""),
              user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    item = db.get(models.Actualite, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Actualité introuvable")
    for k, v in _news_fields(titre_fr, titre_ar, contenu_fr, contenu_ar, publie, date_publication).items():
        setattr(item, k, v)
    log_action(db, user, "modification", "actualite", item.id, item.titre("fr"))
    db.commit()
    return _redirect("/gestion/actualites")


@router.post("/gestion/actualites/{item_id}/delete")
def news_delete(item_id: int, user: models.User = Depends(require_member_manager), db: Session = Depends(get_db)):
    item = db.get(models.Actualite, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Actualité introuvable")
    log_action(db, user, "suppression", "actualite", item.id, item.titre("fr"))
    db.delete(item)
    db.commit()
    return _redirect("/gestion/actualites")
