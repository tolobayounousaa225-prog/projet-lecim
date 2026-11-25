"""Vitrine publique : présentation, membres, actualités, demande d'adhésion, vérification."""


from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import adhesion, models
from ..config import settings
from ..database import get_db
from ..deps import get_optional_user
from ..emailing import send_email
from ..rate_limit import rate_limiter
from ..web import clean, current_lang, parse_date, render

router = APIRouter()

submit_limit = rate_limiter("adhesion-submit", 5, 3600)
track_limit = rate_limiter("adhesion-track", 30, 600)


@router.get("/")
def home(request: Request, user: models.User | None = Depends(get_optional_user)):
    if settings.vitrine_url:  # la vitrine vit sur GitHub Pages : on y renvoie les visiteurs
        return RedirectResponse(settings.vitrine_url, status_code=302)
    return render(request, "home.html", user)


@router.get("/api/public/vitrine.json")
def vitrine_data(db: Session = Depends(get_db)):
    """Données publiques lues par le site vitrine : membres actifs et actualités publiées.
    Volontairement sobre : aucune coordonnée, aucun identifiant interne sensible."""
    members = [
        {"sigle": f.sigle, "nom": f.nom, "categorie": f.categorie}
        for f in db.query(models.Faitiere).order_by(models.Faitiere.categorie, models.Faitiere.sigle)
        if f.is_membre_actif or (f.categorie == "honneur" and f.statut == "actif")
    ]
    news = [
        {"id": n.id, "date": n.date_publication.isoformat(), "titre": {"fr": n.titre_fr, "ar": n.titre_ar},
         "contenu": {"fr": n.contenu_fr, "ar": n.contenu_ar}}
        for n in db.query(models.Actualite).filter_by(publie=True)
        .order_by(models.Actualite.date_publication.desc(), models.Actualite.id.desc()).limit(50)
    ]
    return JSONResponse({"membres": members, "actualites": news}, headers={"Cache-Control": "public, max-age=300"})


@router.get("/apropos")
def about(request: Request, user: models.User | None = Depends(get_optional_user)):
    return render(request, "apropos.html", user)


@router.get("/membres")
def public_members(request: Request, user: models.User | None = Depends(get_optional_user),
                   db: Session = Depends(get_db)):
    members = [f for f in db.query(models.Faitiere).order_by(models.Faitiere.categorie, models.Faitiere.sigle)
               if f.is_membre_actif or (f.categorie == "honneur" and f.statut == "actif")]
    return render(request, "membres_public.html", user, members=members)


@router.get("/actualites")
def news_list(request: Request, user: models.User | None = Depends(get_optional_user),
              db: Session = Depends(get_db)):
    items = (db.query(models.Actualite).filter_by(publie=True)
             .order_by(models.Actualite.date_publication.desc(), models.Actualite.id.desc()).all())
    return render(request, "actualites.html", user, items=items)


@router.get("/actualites/{item_id}")
def news_detail(item_id: int, request: Request, user: models.User | None = Depends(get_optional_user),
                db: Session = Depends(get_db)):
    item = db.get(models.Actualite, item_id)
    if not item or not item.publie:
        raise HTTPException(status_code=404, detail="Actualité introuvable")
    return render(request, "actualite.html", user, item=item)


# ---------- Demande d'adhésion ----------

@router.get("/adhesion")
def join_form(request: Request, user: models.User | None = Depends(get_optional_user)):
    return render(request, "adhesion_form.html", user, values={})


@router.post("/adhesion", dependencies=[Depends(submit_limit)])
def join_submit(
    request: Request,
    nom: str = Form(...), sigle: str = Form(...), representant_nom: str = Form(...),
    representant_fonction: str = Form(""), email: str = Form(...), telephone: str = Form(...),
    siege: str = Form(""), statut_juridique: str = Form(""), date_creation: str = Form(""),
    nb_structures: str = Form(""), message: str = Form(""),
    accepte_statuts: str = Form(""), accepte_cotisations: str = Form(""),
    website: str = Form(""),  # piège à robots : champ invisible que seuls les robots remplissent
    user: models.User | None = Depends(get_optional_user), db: Session = Depends(get_db),
):
    if website.strip():
        # Robot : on répond comme si tout allait bien, sans rien enregistrer
        return render(request, "adhesion_confirm.html", user, code="ADH-XXXXXXXX")
    if nb_structures.strip() and not nb_structures.strip().isdigit():
        raise HTTPException(status_code=400, detail="Nombre de structures invalide")
    demande = adhesion.submit_demande(
        db, nom=nom, sigle=sigle, representant_nom=representant_nom, representant_fonction=representant_fonction,
        email=email, telephone=telephone, siege=siege, statut_juridique=statut_juridique,
        date_creation=parse_date(date_creation),
        nb_structures=int(nb_structures) if nb_structures.strip() else None, message=message,
        accepte_statuts=bool(accepte_statuts), accepte_cotisations=bool(accepte_cotisations),
    )
    db.commit()
    send_email(demande.email, f"PSIE — Demande d'adhésion {demande.code}",
               f"Votre demande d'adhésion a bien été reçue. Code de suivi : {demande.code}\n\n"
               f"تم استلام طلب انخراطكم. رمز المتابعة: {demande.code}\n")
    if settings.notify_email:
        send_email(settings.notify_email, f"PSIE — Nouvelle demande d'adhésion : {demande.sigle}",
                   f"{demande.nom} ({demande.sigle}) a déposé une demande ({demande.code}).")
    return render(request, "adhesion_confirm.html", user, code=demande.code)


@router.get("/adhesion/suivi")
def track_form(request: Request, user: models.User | None = Depends(get_optional_user)):
    return render(request, "adhesion_suivi.html", user, demande=None)


@router.post("/adhesion/suivi", dependencies=[Depends(track_limit)])
def track(request: Request, code: str = Form(...), user: models.User | None = Depends(get_optional_user),
          db: Session = Depends(get_db)):
    demande = db.query(models.DemandeAdhesion).filter_by(code=code.strip().upper()).first()
    # Réponse volontairement minimale : l'état seulement, jamais les données du dossier
    return render(request, "adhesion_suivi.html", user, demande=demande, searched=True,
                  status_code=200 if demande else 404)


@router.get("/verifier/adhesion/{token}")
def verify_certificate(token: str, request: Request, user: models.User | None = Depends(get_optional_user),
                       db: Session = Depends(get_db)):
    demande = db.query(models.DemandeAdhesion).filter_by(cert_token=token).first()
    if not demande or demande.etat != "acceptee" or not demande.faitiere:
        raise HTTPException(status_code=404, detail="Certificat non reconnu")
    return render(request, "verifier.html", user, kind="adhesion", faitiere=demande.faitiere, demande=demande)
