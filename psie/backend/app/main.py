from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  (enregistre les tables)
from sqlalchemy import text

from .config import production_problems, settings
from .database import engine
from .deps import NotAuthenticatedException
from . import scheduler
from .routers import admin, adhesions, appels, assemblees, auth, compta, cotisations, public, sanctions
from .web import BASE_DIR, render

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    problems = production_problems(settings)
    if problems:
        raise RuntimeError("Configuration de production refusée :\n- " + "\n- ".join(problems))
    # Le schéma est créé et mis à jour par les migrations (alembic upgrade head), jamais ici.
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="PSIE",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.debug else None,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Protection CSRF : une requête d'écriture venant d'un navigateur porte un Origin (ou à
    # défaut un Referer) ; s'il ne désigne pas ce site, on refuse. Complète SameSite=Lax.
    if request.method in UNSAFE_METHODS:
        source = request.headers.get("origin") or request.headers.get("referer")
        if source and urlparse(source).netloc != request.headers.get("host", ""):
            return JSONResponse({"detail": "Origine de la requête refusée"}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    # Aucun JavaScript dans l'application : on interdit donc tout script, ce qui neutralise
    # l'essentiel des attaques par injection de code même si un échappement venait à manquer.
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "frame-ancestors 'none'; form-action 'self'; base-uri 'self'; object-src 'none'",
    )
    if settings.cookie_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.exception_handler(NotAuthenticatedException)
async def not_authenticated(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if "text/html" in request.headers.get("accept", ""):
        return render(request, "error.html", status_code=exc.status_code, message=exc.detail)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    """Champ obligatoire manquant ou de mauvais format : message lisible plutôt que du JSON brut."""
    fields = sorted({str(e["loc"][-1]) for e in exc.errors() if e.get("loc")})
    message = "Champ(s) manquant(s) ou invalide(s) : " + ", ".join(fields) if fields else "Requête invalide"
    if "text/html" in request.headers.get("accept", ""):
        return render(request, "error.html", status_code=422, message=message)
    return JSONResponse({"detail": message}, status_code=422)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    """Vérifie aussi la base (utilisé par la supervision)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"status": "database unavailable"}, status_code=503)
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(cotisations.router)
app.include_router(appels.router)
app.include_router(adhesions.router)
app.include_router(compta.router)
app.include_router(assemblees.router)
app.include_router(sanctions.router)
app.include_router(public.router)
