FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Forme shell (pas exec) pour permettre l'expansion de $PORT — Railway et d'autres
# hébergeurs assignent dynamiquement leur propre port via cette variable.
# --proxy-headers --forwarded-allow-ips='*' : ce conteneur n'est jamais exposé
# directement à Internet (seul Caddy l'est, via le réseau Docker interne), donc faire
# confiance à l'en-tête X-Forwarded-For de n'importe quelle IP amont est sûr ici — sans
# ça, request.client.host voit toujours l'IP interne de Caddy pour toutes les requêtes,
# ce qui rend la limitation de débit par IP (rate_limiter) inopérante : tous les
# visiteurs partagent le même quota au lieu d'avoir chacun le leur.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'
