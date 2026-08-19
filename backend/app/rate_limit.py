"""Limitation de débit best-effort en mémoire, sans dépendance externe (pas de
Redis) — suffisante pour dissuader l'énumération/brute-force sur les endpoints
publics sensibles d'une application à faible trafic comme celle-ci."""

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status

_buckets: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def rate_limiter(name: str, max_requests: int, window_seconds: int):
    """Retourne une dépendance FastAPI qui limite à `max_requests` requêtes par
    `window_seconds` secondes, par adresse IP cliente, pour le point d'entrée
    identifié par `name`."""

    def dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{name}:{client_ip}"
        now = time.time()
        cutoff = now - window_seconds
        with _lock:
            hits = _buckets[key]
            while hits and hits[0] < cutoff:
                hits.pop(0)
            if len(hits) >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Trop de requêtes, réessayez dans quelques instants.",
                )
            hits.append(now)

    return dependency
