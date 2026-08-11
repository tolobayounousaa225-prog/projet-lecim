# Architecture — Plateforme de gestion des écoles confessionnelles (LECIM)

> Document de conception (phase 2). Rien ici n'est encore implémenté : c'est le plan de
> construction du second module, une fois le site vitrine et son backend ([`backend/`](backend/))
> stabilisés. L'objectif est de donner à chaque école membre de la LECIM un outil unique pour
> gérer préinscription, inscription, comptabilité, notes, enseignants et bulletins bilingues,
> et à la LECIM une vue nationale consolidée.

## 1. Utilisateurs et rôles

| Rôle | Portée | Exemples d'actions |
|---|---|---|
| **Super-admin LECIM** | Toutes les écoles | Valider l'adhésion d'un établissement, consulter les statistiques nationales, piloter les examens islamiques |
| **Directeur d'établissement** | Son école | Gérer classes, enseignants, valider les inscriptions, consulter la comptabilité |
| **Secrétariat / Scolarité** | Son école | Saisir préinscriptions/inscriptions, générer les matricules |
| **Comptable** | Son école | Encaisser les frais, gérer les relances, éditer les reçus |
| **Enseignant** | Ses classes | Saisir les notes de ses matières, consulter ses classes |
| **Parent / Élève** *(optionnel, phase ultérieure)* | Son dossier | Consulter notes, bulletins, échéancier de paiement |

Le modèle est **multi-établissement (multi-tenant)** : un même compte LECIM héberge toutes
les écoles membres, chaque utilisateur n'ayant accès qu'aux données de son (ou ses)
établissement(s), à l'exception du super-admin LECIM.

## 2. Modules fonctionnels

### 2.1 Gestion des établissements
- Fiche établissement (nom, région, contact, statut d'adhésion à la LECIM)
- Rattachement des utilisateurs (directeur, secrétariat, comptable, enseignants) à un établissement
- Années scolaires et niveaux/classes propres à chaque établissement

### 2.2 Préinscription & inscription
- Formulaire de préinscription (public ou guichet) → dossier en attente
- Workflow de validation par le secrétariat/directeur → génération automatique du **matricule élève**
- Bascule préinscription → inscription définitive après paiement des frais initiaux
- Pièces jointes (acte de naissance, photo, certificat de transfert)

### 2.3 Comptabilité & scolarité
- Grille de frais par niveau/année (frais d'inscription, scolarité mensuelle/trimestrielle, cantine, transport…)
- Échéancier par élève, encaissements partiels, génération de reçus
- **Relances** automatiques (email/SMS) sur échéances impayées
- Etat des lieux comptable par classe/établissement, exportable

### 2.4 Classes, enseignants, emplois du temps
- Affectation des enseignants aux classes et matières (programme arabe + programme français)
- Emploi du temps par classe

### 2.5 Notes et bulletins bilingues
- Saisie des notes par matière, par période (trimestre/semestre)
- Calcul des moyennes pondérées, rangs, appréciations
- **Génération de bulletins en français et en arabe** (mise en page RTL pour l'arabe), export PDF

### 2.6 Examens scolaires islamiques
- Module national piloté par la LECIM : calendrier des sessions, inscription des candidats
  par établissement, remontée centralisée des résultats, statistiques par région

### 2.7 Tableau de bord national (LECIM)
- Nombre d'établissements et d'élèves actifs, taux de réussite agrégé, état des paiements
  consolidé, carte de couverture par région

## 3. Modèle de données (entités principales)

```
Etablissement 1---n Utilisateur (rôle: directeur|secretariat|comptable|enseignant)
Etablissement 1---n AnneeScolaire 1---n Classe
Classe 1---n Eleve
Eleve 1---n Inscription (année, statut: preinscrit|inscrit|radie)
Eleve 1---n Paiement ---1 EcheanceFrais
Classe 1---n Enseignant (via affectation matière)
Classe 1---n Matiere 1---n Note (eleve, periode, valeur)
Eleve 1---1 Bulletin (par période) → genere en FR et AR
Etablissement 1---n SessionExamen ---n Eleve (candidats)
```

Toutes les tables métier portent une clé `etablissement_id` pour l'isolation multi-tenant,
à l'exception des tables globales gérées par la LECIM (établissements, sessions d'examen
nationales).

## 4. Choix techniques proposés

- **Backend** : extension du projet FastAPI existant ([`backend/`](backend/)) — nouveau
  regroupement de routers (`ecoles/`, `eleves/`, `comptabilite/`, `notes/`, `examens/`) plutôt
  qu'un service séparé, pour partager l'authentification et l'infrastructure déjà en place.
- **Base de données** : PostgreSQL, tables partagées avec colonne `etablissement_id`
  (plus simple à maintenir qu'un schéma PostgreSQL par école ; l'isolation se fait via une
  dépendance FastAPI qui filtre systématiquement par l'établissement de l'utilisateur connecté).
- **Autorisations** : RBAC (rôle + établissement) porté par le JWT, vérifié à chaque requête.
- **Génération des bulletins PDF** : rendu HTML (Jinja2, comme l'espace admin actuel) →
  conversion PDF via WeasyPrint, avec un gabarit dédié `dir="rtl"` pour la version arabe.
- **Notifications de relance** : e-mail (déjà en place via SMTP) + option SMS via une
  passerelle locale (Orange/MTN Côte d'Ivoire) à évaluer selon budget.
- **Stockage des documents** (photos, pièces jointes) : disque local en développement,
  stockage compatible S3 (ex. MinIO) recommandé en production pour la sauvegarde.

## 5. Feuille de route suggérée

1. **MVP** — Établissements, utilisateurs par rôle, classes, élèves, inscriptions, saisie
   des notes, bulletin français simple (PDF).
2. **V2** — Comptabilité complète (frais, paiements, reçus, relances).
3. **V3** — Bulletin bilingue français/arabe, tableau de bord national LECIM.
4. **V4** — Module examens scolaires islamiques centralisé, espace parent/élève en lecture seule.

Chaque étape est livrable et utilisable seule ; il n'est pas nécessaire d'attendre la V4
pour qu'un établissement tire déjà de la valeur de l'outil.
