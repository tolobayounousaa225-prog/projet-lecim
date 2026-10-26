FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --uid 10001 psie

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=psie:psie . .

USER psie
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/db', timeout=4).status == 200 else 1)"

# Les migrations s'appliquent avant chaque démarrage (idempotent), puis le serveur démarre.
# Un seul processus (pas de --workers) : le planificateur et la limitation de débit tournent dedans.
# --proxy-headers : le conteneur n'est joignable que derrière le reverse proxy HTTPS.
CMD sh -c "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"
