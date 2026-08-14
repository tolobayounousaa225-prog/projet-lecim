from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import models, scheduler
from .config import settings
from .migrations import run_startup_migrations
from .database import SessionLocal
from .security import decode_access_token
from .deps import (
    DelegationNotAuthenticatedException,
    EtablissementNotAuthenticatedException,
    NotAuthenticatedException,
    NotAuthorizedException,
    WrongPortalException,
)
from .routers import (
    activities,
    adhesion,
    admin,
    admin_audit,
    admin_backups,
    admin_calendar,
    admin_cartes,
    admin_cartes_scolaires,
    admin_connexions,
    admin_delegations,
    admin_effectifs,
    admin_enseignants,
    admin_etablissement_portail,
    admin_executif,
    admin_faq,
    admin_files,
    admin_finances,
    admin_gouvernance,
    admin_historique,
    admin_messagerie,
    admin_partenaires,
    admin_password_resets,
    admin_projets,
    admin_publications,
    admin_ressources,
    admin_resultats_examens,
    admin_reunions,
    admin_site_content,
    admin_social,
    admin_sondages,
    admin_users,
    auth,
    carte,
    contact,
    delegation_portal,
    etablissement_portal,
    etablissement_ressources,
    etablissements_public,
    faq_public,
    gouvernance,
    historique,
    news,
    partenaires_public,
    partenariat_requests,
    password_reset,
    photos_public,
    projets_public,
    publications,
    resultats_examens,
    search_public,
    site_content,
    transparence_public,
    verify,
    verify_attestations,
    verify_eleve,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    run_startup_migrations()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="LECIM API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PORTAL_PREFIXES = ("/admin", "/delegation", "/etablissement")
OBSERVER_EXEMPT_PATHS = {"/admin/login"}


@app.middleware("http")
async def enforce_observer_read_only(request: Request, call_next):
    """Un compte "observateur" peut consulter les modules qui lui sont accordés
    mais ne peut déclencher aucune action qui modifie des données."""
    path = request.url.path
    if (
        request.method in ("POST", "PUT", "PATCH", "DELETE")
        and path.startswith(PORTAL_PREFIXES)
        and path not in OBSERVER_EXEMPT_PATHS
    ):
        token = request.cookies.get("access_token")
        if token:
            email = decode_access_token(token)
            if email:
                db = SessionLocal()
                try:
                    user = db.query(models.User).filter(models.User.email == email).first()
                finally:
                    db.close()
                if user and user.is_observer:
                    return HTMLResponse(
                        "<h1>Action non autorisée</h1>"
                        "<p>Votre compte est en mode observateur (lecture seule) — "
                        "aucune modification n'est autorisée.</p>"
                        "<p><a href=\"javascript:history.back()\">&larr; Retour</a></p>",
                        status_code=403,
                    )
    return await call_next(request)


static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

upload_dir = Path(__file__).resolve().parent.parent / settings.upload_dir
upload_dir.mkdir(parents=True, exist_ok=True)
(upload_dir / "documents").mkdir(exist_ok=True)
(upload_dir / "photos").mkdir(exist_ok=True)
(upload_dir / "justificatifs").mkdir(exist_ok=True)
(upload_dir / "cartes_photos").mkdir(exist_ok=True)
(upload_dir / "publications").mkdir(exist_ok=True)
(upload_dir / "historique").mkdir(exist_ok=True)
(upload_dir / "news").mkdir(exist_ok=True)
(upload_dir / "gouvernance").mkdir(exist_ok=True)
(upload_dir / "etablissements_logos").mkdir(exist_ok=True)
(upload_dir / "partenaires_logos").mkdir(exist_ok=True)
(upload_dir / "cartes_scolaires").mkdir(exist_ok=True)
(upload_dir / "ressources_pedagogiques").mkdir(exist_ok=True)


@app.exception_handler(NotAuthenticatedException)
def not_authenticated_handler(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse(url="/admin/login")


@app.exception_handler(NotAuthorizedException)
def not_authorized_handler(request: Request, exc: NotAuthorizedException):
    return RedirectResponse(url="/admin")


@app.exception_handler(WrongPortalException)
def wrong_portal_handler(request: Request, exc: WrongPortalException):
    return RedirectResponse(url=exc.redirect_to)


@app.exception_handler(EtablissementNotAuthenticatedException)
def etablissement_not_authenticated_handler(request: Request, exc: EtablissementNotAuthenticatedException):
    return RedirectResponse(url="/etablissement/login")


@app.exception_handler(DelegationNotAuthenticatedException)
def delegation_not_authenticated_handler(request: Request, exc: DelegationNotAuthenticatedException):
    return RedirectResponse(url="/delegation/login")


app.include_router(auth.router)
app.include_router(password_reset.router)
app.include_router(carte.router)
app.include_router(etablissements_public.router)
app.include_router(news.router)
app.include_router(activities.router)
app.include_router(contact.router)
app.include_router(adhesion.router)
app.include_router(partenaires_public.router)
app.include_router(partenariat_requests.router)
app.include_router(projets_public.router)
app.include_router(photos_public.router)
app.include_router(faq_public.router)
app.include_router(transparence_public.router)
app.include_router(search_public.router)
app.include_router(publications.router)
app.include_router(admin.router)
app.include_router(admin_audit.router)
app.include_router(admin_backups.router)
app.include_router(admin_users.router)
app.include_router(admin_reunions.router)
app.include_router(admin_files.router)
app.include_router(admin_finances.router)
app.include_router(admin_cartes.router)
app.include_router(admin_cartes_scolaires.router)
app.include_router(admin_partenaires.router)
app.include_router(admin_projets.router)
app.include_router(admin_faq.router)
app.include_router(admin_social.router)
app.include_router(admin_publications.router)
app.include_router(admin_ressources.router)
app.include_router(verify.router)
app.include_router(verify_eleve.router)
app.include_router(verify_attestations.router)
app.include_router(admin_calendar.router)
app.include_router(admin_delegations.router)
app.include_router(admin_executif.router)
app.include_router(admin_enseignants.router)
app.include_router(admin_effectifs.router)
app.include_router(admin_resultats_examens.router)
app.include_router(resultats_examens.router)
app.include_router(admin_historique.router)
app.include_router(historique.router)
app.include_router(admin_gouvernance.router)
app.include_router(gouvernance.router)
app.include_router(admin_site_content.router)
app.include_router(site_content.router)
app.include_router(admin_sondages.router)
app.include_router(delegation_portal.router)
app.include_router(admin_etablissement_portail.router)
app.include_router(admin_messagerie.router)
app.include_router(admin_connexions.router)
app.include_router(admin_password_resets.router)
app.include_router(etablissement_portal.router)
app.include_router(etablissement_ressources.router)


@app.get("/")
def root():
    return {"name": "LECIM API", "docs": "/docs", "admin": "/admin"}


@app.get("/api/health")
def health():
    return {"status": "ok"}
