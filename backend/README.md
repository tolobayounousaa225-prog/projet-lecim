# Backend LECIM

API et espace d'administration pour le site vitrine de la LECIM (Ligue des Établissements
Confessionnels et Madrassas en Côte d'Ivoire), construits avec **FastAPI** + **PostgreSQL**.

Ce backend gère :
- Le **formulaire de contact** du site (réception + consultation des messages)
- Les **actualités** affichées sur la page d'accueil
- Les **activités** affichées sur la page "Nos activités"
- Un **espace d'administration web** (`/admin`) permettant à un non-développeur de publier
  du contenu sans toucher au code
- Une **API JSON** publique en lecture (`/api/news`, `/api/activities`) que le site statique
  peut interroger
- Des **comptes multi-utilisateurs pour le Bureau Exécutif National (BEN)** : l'administrateur
  crée un accès par poste (Président, Vice-Présidents, Secrétaires nationaux, etc.), chaque
  titulaire voit à sa connexion ses attributions statutaires et accède aux **réunions**
  (avec **répertoire permanent des membres** et **feuille de présence**), aux **PV et
  documents** et à la **galerie photo** — ces contenus sont réservés aux comptes connectés,
  non publiés sur le site public. Le poste Communication/TIC gère en plus les Actualités du
  site, et les postes Pédagogie/Éducation gèrent les Activités du site.
- Un lien **« Connecter »** dans la navigation du site public, qui pointe vers `/admin/login`

> Ce module ne couvre que le site vitrine. La plateforme de gestion scolaire complète
> (préinscription, comptabilité, notes, bulletins bilingues, examens) est documentée comme
> second chantier dans [`../ARCHITECTURE_GESTION_SCOLAIRE.md`](../ARCHITECTURE_GESTION_SCOLAIRE.md).

## Démarrage rapide avec Docker (recommandé)

```bash
cd backend
cp .env.example .env
docker compose up -d --build
docker compose exec api python -m scripts.init_db
```

- API + docs interactives : http://localhost:8000/docs
- Espace admin : http://localhost:8000/admin/login
  (identifiants définis par `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD` dans `.env`)

## Démarrage sans Docker

Prérequis : Python 3.12+, une base PostgreSQL accessible (locale ou distante).

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
copy .env.example .env         # puis éditez DATABASE_URL etc.

python -m scripts.init_db      # crée les tables + admin + contenu de démo
uvicorn app.main:app --reload
```

## Connecter le site statique à l'API

Le front (`index.html`, `activites.html`, `contact.html` à la racine du projet) charge
`assets/js/script.js`, qui lit une variable globale `window.LECIM_API_BASE` pour savoir où
se trouve l'API (par défaut `http://localhost:8000`). En production, définissez cette
variable dans le `<head>` de chaque page pour pointer vers votre domaine d'API, et ajoutez
ce domaine à `CORS_ORIGINS` dans `.env`.

Le formulaire de contact envoie directement un `POST /api/contact`. Les sections
"Actualités" et "Nos activités" tentent de charger le contenu dynamique depuis l'API ;
si l'API est injoignable (ex. ouverture du fichier HTML en local sans backend lancé),
le contenu statique déjà présent dans les pages reste affiché.

## Structure du projet

```
backend/
  app/
    main.py          Point d'entrée FastAPI, CORS, montage des routes
    config.py         Configuration via variables d'environnement (.env)
    database.py        Connexion SQLAlchemy / session
    models.py          Modèles (User, NewsPost, Activity, ContactMessage, Membre,
                         Reunion, Presence, Document, Photo)
    postes.py           Les 14 postes du BEN : libellés + attributions statutaires
    schemas.py          Schémas Pydantic (validation entrées/sorties API)
    security.py        Hash de mot de passe (bcrypt) + JWT
    deps.py              Dépendances d'authentification et de permissions
                          (par niveau d'accès et par poste)
    routers/
      auth.py            POST /api/auth/token — connexion API (JWT Bearer)
      news.py             CRUD actualités (admin + poste Communication/TIC)
      activities.py        CRUD activités (admin + postes Pédagogie/Éducation)
      contact.py            Formulaire de contact + notification e-mail optionnelle
      admin.py               Connexion, tableau de bord personnalisé, actualités/
                              activités/messages (HTML, Jinja2, cookie de session)
      admin_users.py          Gestion des comptes & accès (admin uniquement)
      admin_reunions.py        Réunions, répertoire des membres, présence
      admin_files.py            Documents/PV et galerie photo (upload + diffusion
                                 protégée par authentification)
    templates/admin/     Pages HTML de l'espace admin
    static/admin.css      Style de l'espace admin (même palette que le site)
  uploads/                Fichiers PV et photos téléversés (hors dépôt Git)
  scripts/init_db.py     Création des tables + compte admin + données de démo
  requirements.txt
  Dockerfile / docker-compose.yml
```

## Comptes & postes du BEN

Seul un compte **administrateur** (`access_level=admin`) peut créer/modifier/révoquer des
accès, depuis `/admin/users`. Chaque compte peut être rattaché à l'un des 14 postes du
Bureau Exécutif National (définis dans `app/postes.py`, avec leurs attributions statutaires
complètes) et marqué comme titulaire ou adjoint.

Tout compte connecté (quel que soit son poste) accède au socle commun : Réunions,
Répertoire des membres, Documents & PV, Galerie photo. Certains postes reçoivent en plus
un accès à des modules du site public :

| Module | Accès |
|---|---|
| Actualités du site | Admin + Secrétaire Communication/TIC |
| Activités du site | Admin + Secrétaires Pédagogie/Vie scolaire et Éducation/Formation |
| Messages de contact | Admin + Secrétaire Administratif + Secrétariat Permanent |

D'autres modules dédiés (cotisations/finances, partenaires extérieurs, projets/patrimoine,
affaires sociales, antennes régionales...) restent à construire au fil de l'eau pour les
postes restants, une fois ce socle validé en usage réel.

## Sécurité avant mise en production

- Changez `SECRET_KEY` et le mot de passe admin par défaut dans `.env`.
- Servez l'API derrière HTTPS (le cookie de session admin est `httponly` mais pas encore
  marqué `secure` — à activer dans `admin.py` une fois HTTPS en place).
- Restreignez `CORS_ORIGINS` au(x) seul(s) domaine(s) réel(s) du site.
