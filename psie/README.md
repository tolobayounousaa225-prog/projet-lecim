# PSIE — Plateforme des Structures Islamiques d'Éducation

Plateforme de gestion de la PSIE : annuaire des membres (faîtières), mandats des organes,
puis cotisations, gouvernance et finances (voir [`../PSIE_CAHIER_DES_CHARGES.md`](../PSIE_CAHIER_DES_CHARGES.md)).

Ce dossier est un **projet autonome** (sa propre base, sa propre configuration). Il est hébergé
temporairement dans le dépôt LECIM et pourra être déplacé tel quel dans son propre dépôt.

## État : phases 1 à 3 (annuaire, cotisations annuelles et exceptionnelles)

| Fait | Pas encore fait |
|---|---|
| Connexion sécurisée (bcrypt, verrouillage après 5 échecs, cookie HttpOnly, protection CSRF) | **Migrations de base (Alembic) : à mettre en place avant la première mise en ligne** (jusqu'ici les tables sont créées au démarrage, ce qui n'ajoute pas de colonnes à une base existante) |
| **Double authentification par e-mail** (administrateur et secrétaire aux finances) | Demande d'adhésion en ligne et vitrine (phase 4) |
| 7 rôles alignés sur les organes des Statuts | Assemblées, votes, sanctions (phase 5) |
| Annuaire des membres : fondateur / ordinaire / honneur, les 6 fondateurs créés | Finances complètes, double signature des paiements, registre des dons (phase 6) |
| Mandats par organe, durée de 3 ans, alertes d'échéance | Commissions et 41 délégations régionales (phase 7) |
| **Cotisation annuelle** : montant par année, création automatique des échéances, statuts à jour / partiel / en retard / impayé |  |
| **Paiements** partiels ou échelonnés, annulation avec motif (jamais de suppression), **reçus PDF numérotés** (PSIE-REC-AAAA-0001) | Relecture des traductions arabes |
| **Attestation de cotisation à jour** (PDF), **vérification publique par QR code** | |
| **Relances automatiques** par e-mail (J-30, J-7, jour J, puis chaque semaine) et résumé du lundi au secrétaire aux finances | |
| Situation par année, taux de recouvrement, export CSV | |
| Droit d'adhésion (montant saisi par le secrétaire aux finances) | |
| **Appels de cotisation exceptionnelle** : intitulé, motif, référence de la décision, date limite ; montant commun ou propre à chaque faîtière | |
| **Exonération** (motif obligatoire, rétablissable), **report** de date limite (relances relancées), **correction de montant** (jamais sous les paiements reçus) | |
| Mêmes paiements, reçus PDF et relances que pour la cotisation annuelle | |
| Cloisonnement : un représentant ne voit que sa faîtière, ses échéances et ses reçus | |
| Journal d'audit des écritures | |
| Interface et PDF en français et en arabe (droite-gauche) | |

### Qui peut faire quoi (finances)

| Rôle | Cotisations |
|---|---|
| Secrétaire chargé des finances (ou adjoint) | Lecture et écriture (montant, paiements, annulations, appels, exonérations, reports) |
| DEN, administrateur du CA, commissaire aux comptes | Lecture seule |
| Représentant de faîtière | Sa faîtière uniquement : échéances, reçus, attestation |
| Administrateur de la plate-forme | Aucun accès aux finances (rôle technique) |

### Tâches automatiques

Chaque jour à 7 h (Abidjan) : création des cotisations de l'année si le montant est défini,
puis envoi des relances dues (une seule fois par palier et par échéance). Chaque lundi à 7 h 30 :
résumé des retards aux secrétaires aux finances. Désactivables avec `SCHEDULER_ENABLED=false`.

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

Les tests utilisent une base SQLite jetable : aucun PostgreSQL requis. Ils couvrent la connexion et
la double authentification, le verrouillage, les permissions par rôle, le cloisonnement entre
faîtières, la protection CSRF, les mandats, les cotisations (génération, paiements, annulations,
statuts), les reçus et attestations PDF, la vérification publique, les relances et le journal d'audit.

## Production

- `COOKIE_SECURE=true` derrière HTTPS ; `SECRET_KEY` unique et secrète.
- `TWO_FACTOR_ENABLED=true` **avec un SMTP fonctionnel** : sans e-mail, l'administrateur et le secrétaire
  aux finances ne peuvent pas se connecter (la connexion échoue par prudence plutôt que de s'ouvrir).
- `PUBLIC_BASE_URL` = adresse réelle du site : elle est encodée dans les QR codes imprimés.
- Un seul processus serveur (un seul worker) : le planificateur tourne dans l'application.
- Changer le mot de passe administrateur après la première connexion.
