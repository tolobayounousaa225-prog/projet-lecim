# Architecture

## Deux dépôts, trois adresses
| Élément | Où | Rôle |
|---|---|---|
| **Site vitrine** | dépôt GitHub `PSIE` → GitHub Pages (`https://<compte>.github.io/PSIE/`) | Site public statique (accueil, à propos, membres, guide, vérification…). Reconstruit par GitHub Actions. |
| **Application** | dépôt `projet-lecim`, dossier `psie/backend` → serveur Contabo | Espace connecté (membres, finances, assemblées, écoles, documents…) + API publique. |
| **Serveur** | VPS Contabo, Docker Compose, projet `psie` (`docker compose -p psie …`) | Trois conteneurs : `db` (PostgreSQL 16), `api` (FastAPI), `caddy` (HTTPS automatique). |

> Le dossier `psie/` du dépôt `projet-lecim` cohabite avec le projet LECIM (dossier `backend/` à la racine) : **ne jamais toucher aux fichiers hors `psie/`** depuis une modification PSIE.

## Comment le site vitrine et l'application se parlent
1. Un éditeur modifie « Contenu du site » dans l'application.
2. L'application prévient GitHub (événement `repository_dispatch` `contenu-modifie`) avec un jeton limité au dépôt `PSIE`.
3. GitHub Actions reconstruit le site : il télécharge `https://<application>/api/public/site.json` (contenu + fichiers, tout-ou-rien, empreintes SHA-256) puis publie.
4. Les boutons du site (Adhérer, Suivre ma demande, Connexion) pointent vers l'application ; les QR des reçus/attestations pointent vers ses pages `/verifier/...`.
5. Variable `API_BASE` (GitHub → PSIE → Variables) : permet au site d'afficher en direct les membres de l'application (`/api/public/vitrine.json`).

## L'application (`psie/backend`)
- **FastAPI + SQLAlchemy 2 + Alembic** ; pages rendues côté serveur (Jinja2) ; PostgreSQL en production, SQLite pour les tests.
- `app/main.py` : assemblage, en-têtes de sécurité (CSP), gestionnaires d'erreurs, tâches planifiées.
- `app/models.py` : toutes les tables. `migrations/versions/` : une migration par évolution (0001 → …), appliquées automatiquement au démarrage.
- `app/routers/` : un fichier par domaine — `membres`, `adhesions`, `assemblees`, `sanctions`, `cotisations`/`appels`/`compta` (finances), `ecoles`/`statistiques`/`relation` (espace faîtière), `documents` (documents, courrier, conventions, registres), `contenu` (site vitrine), `acces` (droits), `auth`/`reinitialisation`, `public`.
- `app/acces.py` : **droits par rubrique** (niveaux aucun / lecture / modification, par rôle puis par personne). `deps.visibility_guard` l'applique à *toutes* les adresses.
- `app/i18n.py` (+ `*_texts.py`) : textes français et arabe ; une clé absente retombe sur le français.
- `app/scheduler.py` : tâches planifiées (voir EXPLOITATION.md). `app/rappels.py` : rappels réglementaires, chacun envoyé une seule fois.
- `app/audit.py` : journal d'audit de toute écriture sensible.
- Fichiers (pièces, documents, photos du site) : **en base** (donc sauvegardés avec le reste), nettoyés à l'entrée (`media.py`).

## Sécurité en bref
Mots de passe bcrypt ; cookie de session HTTPS ; double authentification par e-mail pour les rôles sensibles ; verrouillage après échecs ; limitation de débit ; liens de mot de passe à usage unique stockés sous forme d'empreinte ; téléversements contrôlés (PDF vérifiés, images ré-encodées, SVG refusé) ; cloisonnement strict d'une faîtière à ses données ; sauvegardes chiffrées AES-256.

## Tests
`cd psie/backend && python -m pytest -q` (≈ 10 min). La CI GitHub exécute la suite sur SQLite et sur PostgreSQL, et construit l'image Docker.
