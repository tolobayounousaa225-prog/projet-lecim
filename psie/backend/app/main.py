from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  (enregistre les tables)
from .config import settings
from .database import Base, engine
from .deps import NotAuthenticatedException
from . import scheduler
from .routers import admin, auth, cotisations
from .web import BASE_DIR, render

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
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
    return response


@app.exception_handler(NotAuthenticatedException)
async def not_authenticated(request: Request, exc: NotAuthenticatedException):
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    if "text/html" in request.headers.get("accept", ""):
        return render(request, "error.html", status_code=exc.status_code, message=exc.detail)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(cotisations.router)
