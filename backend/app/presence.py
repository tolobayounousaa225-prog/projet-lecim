"""Suivi en mémoire des visiteurs actuellement en ligne sur la vitrine — chaque
onglet ouvert envoie un signal de vie ("heartbeat") périodique avec un
identifiant aléatoire généré côté client (sessionStorage, jamais un cookie ni
une IP), et un visiteur est considéré « en ligne » tant qu'un signal a été reçu
au cours des ACTIVE_WINDOW_SECONDS dernières secondes. Purement éphémère (pas de
table, pas d'historique) — perdu au redémarrage du serveur, sans conséquence
puisque seul le nombre instantané de connectés a un sens."""

import time
from threading import Lock

ACTIVE_WINDOW_SECONDS = 90

_lock = Lock()
_sessions: dict[str, float] = {}


def heartbeat(session_id: str) -> int:
    now = time.time()
    cutoff = now - ACTIVE_WINDOW_SECONDS
    with _lock:
        _sessions[session_id] = now
        expired = [sid for sid, ts in _sessions.items() if ts < cutoff]
        for sid in expired:
            del _sessions[sid]
        return len(_sessions)


def count_active() -> int:
    cutoff = time.time() - ACTIVE_WINDOW_SECONDS
    with _lock:
        return sum(1 for ts in _sessions.values() if ts >= cutoff)
