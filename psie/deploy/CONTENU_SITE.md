# Contenu du site vitrine : fonctionnement et mise en place

## Qui peut modifier quoi

| Rôle | Contenu du site |
|---|---|
| Secrétariat Information et Communication | oui (double authentification obligatoire) |
| Administrateur | oui (double authentification obligatoire) |
| Tous les autres rôles | non |

Chaque ajout, modification, suppression ou changement d'ordre est publié **immédiatement** et inscrit au journal d'audit.

## Comment le site se met à jour

1. Un éditeur enregistre dans `/gestion/contenu`.
2. L'application prévient GitHub (événement `contenu-modifie`), si `GITHUB_DISPATCH_REPO` et `GITHUB_DISPATCH_TOKEN` sont définis.
3. Le site vitrine se reconstruit à partir de `https://<application>/api/public/site.json` et se republie (1 à 2 minutes).

Si GitHub est injoignable, le contenu est quand même enregistré ; il sera repris à la prochaine reconstruction.
**Le site ne doit jamais se reconstruire avec un contenu incomplet** : si le téléchargement du contenu échoue, la reconstruction
doit s'arrêter et laisser en ligne la version précédente.

## Mise en place (une seule fois)

1. **Créer le jeton GitHub** : GitHub → Settings → Developer settings → Fine-grained personal access tokens. Dépôt : **PSIE
   uniquement**. Permission : *Contents : Read and write* (nécessaire pour déclencher un événement). Durée : 1 an (à renouveler).
2. Renseigner dans `.env` : `GITHUB_DISPATCH_REPO=tolobayounousaa225-prog/PSIE` et `GITHUB_DISPATCH_TOKEN=…`, puis redémarrer.
3. Appliquer la migration (`alembic upgrade head`, faite par `python -m scripts.init_db`).
4. **Reprendre le contenu actuel du site** (une fois) :
   `python -m scripts.import_site_content /chemin/du/depot/PSIE`
   (sans `--remplacer`, une rubrique déjà renseignée n'est jamais écrasée).
5. Créer les comptes des secrétariats dans « Comptes » (rôle choisi dans la liste).
6. Côté dépôt du site : faire lire `CONTENT_URL` à la construction (étape suivante, dans le dépôt PSIE).

## Fichiers envoyés (logos, photos, PDF)

- Images JPG, PNG, WebP (8 Mo maximum) : ré-encodées, métadonnées (GPS, appareil) supprimées, réduites à 2400 px.
- PDF (15 Mo maximum) : vérifiés à l'en-tête. **Le contenu d'un PDF n'est pas analysé** : n'envoyer que des PDF produits par la PSIE.
- SVG refusé (code actif possible). Les fichiers sont conservés en base, donc sauvegardés avec le reste.
