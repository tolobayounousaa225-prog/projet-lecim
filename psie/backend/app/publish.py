"""Reconstruction automatique du site vitrine après une modification de son contenu.

On prévient GitHub (événement « repository_dispatch ») : son workflow reconstruit et republie le site
en une à deux minutes. L'échec de cet appel n'empêche jamais d'enregistrer le contenu : il est journalisé
et le contenu sera repris à la prochaine modification ou à la prochaine reconstruction.
"""

import json
import logging
import re
import urllib.error
import urllib.request

from .config import settings

logger = logging.getLogger("psie.publish")
EVENT = "contenu-modifie"
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def rebuild_configured() -> bool:
    return bool(settings.github_dispatch_repo and settings.github_dispatch_token
                and REPO_RE.fullmatch(settings.github_dispatch_repo))


def trigger_rebuild() -> bool:
    """Demande la reconstruction du site. Retourne True si GitHub a accepté la demande."""
    if not rebuild_configured():
        logger.info("Reconstruction automatique non configurée : contenu enregistré sans republier le site")
        return False
    request = urllib.request.Request(
        f"https://api.github.com/repos/{settings.github_dispatch_repo}/dispatches",
        data=json.dumps({"event_type": EVENT}).encode(),
        headers={"Authorization": f"Bearer {settings.github_dispatch_token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json", "User-Agent": "psie-backend"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status == 204
    except (urllib.error.URLError, OSError) as e:
        logger.error("Reconstruction du site refusée ou impossible : %s", type(e).__name__)
        return False
