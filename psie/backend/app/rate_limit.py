"""Limitation de débit en mémoire, par adresse IP : dissuade le spam du formulaire public
d'adhésion et l'énumération des codes de suivi. Suffisant pour une application à faible trafic
et un seul processus ; à remplacer par un stockage partagé si on multiplie les processus."""

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status

_buckets: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def reset() -> None:
    with _lock:
        _buckets.clear()


def rate_limiter(name: str, max_requests: int, window_seconds: int):
    def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"{name}:{ip}"
        now = time.time()
        with _lock:
            hits = [t for t in _buckets[key] if t > now - window_seconds]
            if len(hits) >= max_requests:
                _buckets[key] = hits
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                    detail="Trop de requêtes, réessayez plus tard.")
            hits.append(now)
            _buckets[key] = hits

    return dependency
