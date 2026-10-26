# PSIE — Plateforme des Structures Islamiques d'Éducation

Plateforme de gestion de la PSIE : annuaire des membres (faîtières), mandats des organes,
puis cotisations, gouvernance et finances (voir [`../PSIE_CAHIER_DES_CHARGES.md`](../PSIE_CAHIER_DES_CHARGES.md)).

Ce dossier est un **projet autonome** (sa propre base, sa propre configuration). Il est hébergé
temporairement dans le dépôt LECIM et pourra être déplacé tel quel dans son propre dépôt.

## État : phases 1 à 6 réalisées, déploiement préparé

| Fait | Pas encore fait |
|---|---|
| Connexion sécurisée (bcrypt, verrouillage après 5 échecs, cookie HttpOnly, protection CSRF) | « Mot de passe oublié » automatique par e-mail (l'administrateur peut réinitialiser un mot de passe) |
| **Double authentification par e-mail** (administrateur et secrétaire aux finances) |  |
| 7 rôles alignés sur les organes des Statuts |  |
| Annuaire des membres : fondateur / ordinaire / honneur, les 6 fondateurs créés | Commissions techniques (CNECI, CNVSP) et 41 délégations régionales (phase 7) |
| Mandats par organe, durée de 3 ans, alertes d'échéance | **Cotisation annuelle** : montant par année, création automatique des échéances, statuts à jour / partiel / en retard / impayé |  |
| **Paiements** partiels ou échelonnés, annulation avec motif (jamais de suppression), **reçus PDF numérotés** (PSIE-REC-AAAA-0001) | Relecture des traductions arabes |
| **Attestation de cotisation à jour** (PDF), **vérification publique par QR code** | |
| **Relances automatiques** par e-mail (J-30, J-7, jour J, puis chaque semaine) et résumé du lundi au secrétaire aux finances | |
| Situation par année, taux de recouvrement, export CSV | |
| Droit d'adhésion (montant saisi par le secrétaire aux finances) | |
| **Appels de cotisation exceptionnelle** : intitulé, motif, référence de la décision, date limite ; montant commun ou propre à chaque faîtière | |
| **Exonération** (motif obligatoire, rétablissable), **report** de date limite (relances relancées), **correction de montant** (jamais sous les paiements reçus) | |
| Mêmes paiements, reçus PDF et relances que pour la cotisation annuelle | |
| **Vitrine publique bilingue** : accueil, à propos (missions, principes, organes tirés des Statuts), membres actifs, actualités | |
| **Demande d'adhésion en ligne** (code de suivi, anti-spam : limite par adresse IP et champ piège), suivi public limité à l'état de la demande | |
| **Circuit d'adhésion des Statuts** : examen par la DEN, avis écrit du CA, décision de l'AG avec référence ; acceptation impossible sans avis favorable | |
| Acceptation : le membre (ordinaire, actif) est créé, son droit d'adhésion à payer est créé si un montant est saisi, **certificat d'adhésion PDF** à QR code vérifiable publiquement | |
| Gestion des actualités FR/AR (brouillon ou publié, texte brut échappé) | |
| **Assemblées générales** (AGA, AGO, AGE) : convocation par e-mail et PDF, **15 jours minimum** et **avis favorable du CA** sur l'ordre du jour pour l'AGA et l'AGO (pas pour l'AGE, qui exige l'indication de la demande conjointe) | |
| **Séance** : liste d'émargement générée (délégués des organisations actives, CA, DEN, CC en cours de mandat), **quorum des 2/3** calculé en direct, impayés affichés **à titre d'information seulement** | |
| **Résolutions et scrutins** : consensus ou **majorité des voix des présents** ; **dissolution à 4/5** réservée à l'AGE ; aucune délibération sans quorum ; scrutin clos = voix figées | |
| Mode de vote **paramétrable par assemblée** (une voix par organisation, ou par délégué présent) : les textes ne le tranchent pas | |
| Clôture avec président et deux assesseurs, **procès-verbal PDF** (émargement, quorum, résolutions et résultats) | |
| **Sanctions** (avertissement, blâme, suspension, radiation) avec référence de l'avis du CA ou de la résolution d'AG, notification PDF, levée d'une suspension ; une organisation suspendue ou radiée ne siège plus, ne cotise plus et disparaît de la vitrine | |
| Tableau de bord : composition réelle des organes comparée aux Statuts (CA 13, DEN 13, CC 2, 2 délégués par organisation) | |
| Cloisonnement : un représentant ne voit que sa faîtière, ses échéances et ses reçus | |
| Journal d'audit des écritures | |
| **Dépenses à double signature** : une dépense n'est payable qu'après la signature du DEN **et** du secrétaire aux finances, qui doivent venir d'**organisations différentes** (Statuts art. 38) ; jamais supprimée, annulable avant paiement avec motif | |
| **Justificatifs** (PDF, PNG, JPEG, 5 Mo) stockés dans la base donc sauvegardés ; type vérifié d'après le contenu du fichier ; une dépense sans pièce exige la décision motivée du CA (art. 39.2) ; frais de mission : ordre de mission obligatoire | |
| **Registre spécial des dons** (identité complète, date, nature, valeur) ; **vérification renforcée** (pièce d'identité et origine des fonds obligatoires) au-delà d'un seuil que le secrétaire aux finances définit dans son espace | |
| Subventions et autres recettes ; **budget annuel** (DEN et secrétaire aux finances) validé par l'AGA avec référence, puis figé | |
| **États financiers** (exercice, 1er ou 2e semestre) en PDF et CSV, avec comparaison au budget ; dépenses engagées non payées et dons en nature séparés de la caisse | |
| **Commissaires aux comptes** : lecture de toutes les écritures et pièces, rapports écrits visibles du DEN, du CA et du secrétaire aux finances | |
| **Déclarations de conflit d'intérêts** des membres des organes | |
| Changement de mot de passe (le mauvais mot de passe actuel compte comme un échec de connexion) ; réinitialisation par l'administrateur | |
| **Migrations Alembic** (schéma versionné, aucune table créée « à la volée ») ; un test échoue si un modèle change sans migration | |
| **Déploiement** : image Docker non-root, composition de production (base non exposée), Caddy optionnel, sauvegardes chiffrées AES-256 avec test de restauration, [guide pas à pas](deploy/DEPLOIEMENT.md) | |
| **Durcissement** : refus de démarrer avec une configuration dangereuse, CSP sans script, HSTS, `/health/db` | |
| Suite de tests aussi exécutée sur **PostgreSQL** en CI | |
| Interface et PDF en français et en arabe (droite-gauche) | |

### Qui peut faire quoi (finances)

| Rôle | Cotisations |
|---|---|
| Secrétaire chargé des finances (ou adjoint) | Lecture et écriture (montant, paiements, annulations, appels, exonérations, reports) |
| DEN, administrateur du CA, commissaire aux comptes | Lecture seule |
| Représentant de faîtière | Sa faîtière uniquement : échéances, reçus, attestation, certificat d'adhésion |
| Administrateur de la plate-forme | Aucun accès aux finances (rôle technique) |

#### Dépenses, dons, budget

| Action | Qui |
|---|---|
| Créer une dépense, joindre une pièce, payer, annuler ; enregistrer dons et recettes ; fixer le seuil des dons | Secrétaire aux finances |
| Signer une dépense | DEN et secrétaire aux finances (organisations d'origine différentes) |
| Élaborer le budget, saisir la référence de validation de l'AGA | DEN et secrétaire aux finances |
| Lire dépenses, pièces, dons, budget, états | DEN, administrateur du CA, commissaire aux comptes, secrétaire aux finances |
| Rédiger un rapport de contrôle | Commissaire aux comptes |

L'**organisation d'origine** du DEN et du secrétaire aux finances est saisie par l'administrateur (page « Comptes ») : sans elle, la signature est refusée.

### Adhésions (qui fait quoi)

| Étape | Qui |
|---|---|
| Dépôt de la demande | Public (formulaire en ligne) |
| Prise en charge, décision de l'AG | Administrateur, DEN, secrétaire de la DEN |
| Avis écrit du CA | Administrateur du CA (ou, en son nom, DEN / secrétaire) |
| Lecture des demandes | Tous les organes de la PSIE |

### Vie statutaire (qui fait quoi)

| Action | Qui |
|---|---|
| Créer, convoquer, ouvrir la séance, émarger, saisir les votes, clôturer, prononcer une sanction | Administrateur, DEN, secrétaire de la DEN |
| Avis du CA sur l'ordre du jour | Administrateur du CA (ou, en son nom, DEN / secrétaire) |
| Consulter | Tous les organes de la PSIE |
| Voir la convocation | Représentants de faîtière (assemblées convoquées uniquement) |

Les votes sont saisis par le bureau de séance à partir du scrutin constaté : le vote électronique des délégués n'est pas prévu à ce stade.

Après une acceptation, le secrétaire aux finances crée les cotisations de l'année depuis la page
Cotisations : le nouveau membre y est inclus. Aucun prorata n'est appliqué (les textes n'en prévoient pas).

### Tâches automatiques

Chaque jour à 7 h (Abidjan) : création des cotisations de l'année si le montant est défini,
puis envoi des relances dues (une seule fois par palier et par échéance). Chaque lundi à 7 h 30 :
résumé des retards aux secrétaires aux finances. Désactivables avec `SCHEDULER_ENABLED=false`.

## Vitrine publique

Le site public est un **dépôt séparé** (`PSIE`, publié sur GitHub Pages à l'adresse https://tolobayounousaa225-prog.github.io/PSIE/). L'application n'expose pour lui qu'une
source de données en lecture seule (`/api/public/vitrine.json` : sigles, noms et catégories des membres actifs,
actualités publiées), accessible uniquement depuis l'adresse déclarée dans `VITRINE_ORIGINS`, sans cookie. Tant que
`VITRINE_URL` est vide, l'application sert elle-même ses pages publiques.

## Mise en ligne

Voir **[deploy/DEPLOIEMENT.md](deploy/DEPLOIEMENT.md)** (serveur partagé ou dédié, HTTPS, e-mail,
sauvegardes chiffrées, mises à jour, checklist). Les scripts `deploy/backup.sh` et `deploy/restore.sh`
sauvegardent et restaurent la base ; `./restore.sh --test` prouve qu'une sauvegarde est exploitable.

## Démarrage rapide en local (Docker)

```bash
cd psie/backend
cp .env.example .env          # puis changez SECRET_KEY et le mot de passe admin
docker compose up -d --build  # les migrations s'appliquent au démarrage
docker compose exec api python -m scripts.init_db   # compte administrateur + 6 fondateurs
```

Application : http://localhost:8100 (connexion avec `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD`).

## Sans Docker

```bash
cd psie/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # DATABASE_URL vers votre PostgreSQL
python -m scripts.init_db     # applique les migrations puis crée l'administrateur et les fondateurs
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

## Migrations de base de données

```bash
cd psie/backend
alembic upgrade head                                   # applique les migrations
alembic revision --autogenerate -m "description"       # après avoir modifié un modèle
alembic check                                          # signale un modèle sans migration
```

Ne jamais modifier une migration déjà appliquée en production : en créer une nouvelle.

## Production

- `COOKIE_SECURE=true` derrière HTTPS ; `SECRET_KEY` unique et secrète. Dans ce mode, l'application
  refuse de démarrer avec une configuration dangereuse (clé faible, SMTP absent, adresse en `http://`…).
- `TWO_FACTOR_ENABLED=true` **avec un SMTP fonctionnel** : sans e-mail, l'administrateur et le secrétaire
  aux finances ne peuvent pas se connecter (la connexion échoue par prudence plutôt que de s'ouvrir).
- `PUBLIC_BASE_URL` = adresse réelle du site : elle est encodée dans les QR codes imprimés.
- Un seul processus serveur (un seul worker) : le planificateur et la limitation de débit tournent dans l'application.
- `NOTIFY_EMAIL` (facultatif) : adresse prévenue à chaque nouvelle demande d'adhésion.
- Changer le mot de passe administrateur après la première connexion.
