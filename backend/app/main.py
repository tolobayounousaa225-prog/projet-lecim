from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import scheduler
from .config import settings
from .deps import (
    DelegationNotAuthenticatedException,
    EtablissementNotAuthenticatedException,
    NotAuthenticatedException,
    NotAuthorizedException,
    WrongPortalException,
)
from .routers import (
    activities,
    admin,
    admin_audit,
    admin_backups,
    admin_calendar,
    admin_cartes,
    admin_delegations,
    admin_enseignants,
    admin_etablissement_portail,
    admin_executif,
    admin_files,
    admin_finances,
    admin_gouvernance,
    admin_historique,
    admin_partenaires,
    admin_projets,
    admin_publications,
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
    gouvernance,
    historique,
    news,
    publications,
    resultats_examens,
    site_content,
    verify,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
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
app.include_router(carte.router)
app.include_router(news.router)
app.include_router(activities.router)
app.include_router(contact.router)
app.include_router(publications.router)
app.include_router(admin.router)
app.include_router(admin_audit.router)
app.include_router(admin_backups.router)
app.include_router(admin_users.router)
app.include_router(admin_reunions.router)
app.include_router(admin_files.router)
app.include_router(admin_finances.router)
app.include_router(admin_cartes.router)
app.include_router(admin_partenaires.router)
app.include_router(admin_projets.router)
app.include_router(admin_social.router)
app.include_router(admin_publications.router)
app.include_router(verify.router)
app.include_router(admin_calendar.router)
app.include_router(admin_delegations.router)
app.include_router(admin_executif.router)
app.include_router(admin_enseignants.router)
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
app.include_router(etablissement_portal.router)


@app.get("/")
def root():
    return {"name": "LECIM API", "docs": "/docs", "admin": "/admin"}


@app.get("/api/health")
def health():
    return {"status": "ok"}
