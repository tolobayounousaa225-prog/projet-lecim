# PSIE — Plateforme des Structures Islamiques d'Éducation

Plateforme de gestion de la PSIE : annuaire des membres (faîtières), mandats des organes,
puis cotisations, gouvernance et finances (voir [`../PSIE_CAHIER_DES_CHARGES.md`](../PSIE_CAHIER_DES_CHARGES.md)).

Ce dossier est un **projet autonome** (sa propre base, sa propre configuration). Il est hébergé
temporairement dans le dépôt LECIM et pourra être déplacé tel quel dans son propre dépôt.

## État : phase 1 (socle + annuaire)

| Fait | Pas encore fait |
|---|---|
| Connexion sécurisée (bcrypt, verrouillage après 5 échecs, cookie HttpOnly, protection CSRF) | Double authentification par e-mail (phase 2, avec les finances) |
| 7 rôles alignés sur les organes des Statuts | Cotisations, paiements, reçus (phase 2) |
| Annuaire des membres : fondateur / ordinaire / honneur | Appels exceptionnels (phase 3) |
| Les 6 fondateurs créés automatiquement | Assemblées, votes, sanctions (phase 5) |
| Mandats par organe, durée de 3 ans par défaut, alertes d'échéance | Finances, registre des dons (phase 6) |
| Cloisonnement : un représentant ne voit que sa faîtière | Migrations de base (Alembic) |
| Journal d'audit des écritures | |
| Interface française et arabe (droite-gauche) | Relecture des traductions arabes |

## Démarrage rapide (Docker)

```bash
cd psie/backend
cp .env.example .env          # puis changez SECRET_KEY et le mot de passe admin
docker compose up -d --build
docker compose exec api python -m scripts.init_db
```

Application : http://localhost:8100 (connexion avec `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD`).

## Sans Docker

```bash
cd psie/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # DATABASE_URL vers votre PostgreSQL
python -m scripts.init_db
uvicorn app.main:app --reload
```

## Tests

```bash
cd psie/backend
python -m pytest -q
```

Les tests utilisent une base SQLite jetable : aucun PostgreSQL requis. Ils couvrent la connexion,
le verrouillage, les permissions par rôle, le cloisonnement entre faîtières, la protection CSRF,
les mandats, le journal d'audit et la bascule français/arabe.

## Production

- `COOKIE_SECURE=true` derrière HTTPS ; `SECRET_KEY` unique et secrète.
- Changer le mot de passe administrateur après la première connexion.
