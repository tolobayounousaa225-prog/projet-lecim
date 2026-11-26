# Déployer la PSIE sur un serveur

> **Important** : ce guide n'a pas pu être exécuté sur le vrai serveur (aucun accès). Les scripts de
> sauvegarde et de restauration et les migrations ont été testés sur PostgreSQL 16 ; la composition
> Docker est validée par la CI mais n'a jamais tourné sur la machine cible. Suivez les étapes une
> à une et gardez la checklist de la dernière section.

## 0. Architecture retenue

```
Site vitrine (dépôt « PSIE »)  →  GitHub Pages, gratuit
Application (ce dépôt, dossier psie/) →  VPS Contabo, partagé avec la LECIM (pile Docker séparée)
```

Le site public est un dépôt à part (voir son README). L'application, elle, porte la connexion, la
demande d'adhésion, le suivi, les QR codes et tout l'espace interne.

## 1. Ce qu'il faut avant de commencer

| Élément | Pourquoi | Statut |
|---|---|---|
| Le **VPS Contabo** qui héberge déjà la LECIM (Ubuntu, Docker) : la PSIE y tourne dans sa propre pile, sans toucher à la LECIM | héberger l'application | existant, à vérifier avec `diagnostic.sh` |
| Accès SSH au serveur | installer et lancer | à vérifier |
| Un **serveur e-mail (SMTP)** | code de connexion (double authentification), relances, convocations | à obtenir |
| Un **nom de domaine** | HTTPS propre et QR codes définitifs | **plus tard** (voir ci-dessous) |
| Les noms du DEN et du secrétaire aux finances | créer leurs comptes | à fournir |
| Le logo de la PSIE | identité visuelle | à fournir |

### En attendant le nom de domaine
Caddy sait obtenir un certificat HTTPS pour une adresse de type `IP-AVEC-DES-TIRETS.sslip.io`
(ex. pour l'IP `203.0.113.7` : `203-0-113-7.sslip.io`). Mettre cette adresse dans `DOMAIN` et
`PUBLIC_BASE_URL` permet de tester **tout de suite**, avec un vrai cadenas.

> **N'imprimez aucun reçu, attestation ou certificat à QR code avant d'avoir le vrai nom de domaine.**
> Le QR code contient l'adresse de l'application : s'il pointe vers une adresse provisoire, les documents
> déjà imprimés cesseront d'être vérifiables le jour où l'adresse change.

## 2. Vérifier le serveur Contabo (partagé avec la LECIM)

Le serveur porte déjà la LECIM : on n'y change **rien** de ce qui la concerne (pare-feu, ports 80 et 443,
reverse proxy en place). La PSIE s'ajoute à côté, dans une pile Docker nommée `psie` (base de données,
réseau et volumes à elle), et n'écoute que sur `127.0.0.1:8100`, donc jamais en conflit avec le port 8000 ou
5432 de la LECIM. C'est le **mode A**.

Avant d'installer, lancez ce contrôle en lecture seule et envoyez-moi le résultat (il vérifie la mémoire,
le disque, Docker, les ports et le reverse proxy en place) :

```bash
ssh utilisateur@IP-DU-SERVEUR
git clone https://github.com/tolobayounousaa225-prog/projet-lecim.git psie-app
cd psie-app/psie/deploy && bash diagnostic.sh
```

Si la mémoire disponible est inférieure à environ 1 Go (Jitsi est gourmand), ne pas installer :
prendre un VPS séparé (voir le cahier des charges, § 6.1).

### Variante : serveur neuf, réservé à la PSIE (mode B, la plus simple)

Sur un VPS vide (Ubuntu 24.04), on prépare d'abord la machine, puis on installe avec `--serveur-dedie`
(Caddy est inclus et obtient seul le certificat HTTPS).

```bash
# 1re connexion, en root : ssh root@IP-DU-SERVEUR
apt update && apt -y upgrade
adduser psie && usermod -aG sudo psie                      # utilisateur normal pour travailler
ufw allow OpenSSH && ufw allow 80,443/tcp && ufw --force enable   # pare-feu : SSH, HTTP, HTTPS seulement
curl -fsSL https://get.docker.com | sh && usermod -aG docker psie  # installe Docker
reboot                                                     # puis se reconnecter : ssh psie@IP-DU-SERVEUR
```

Puis, connecté en `psie` :

```bash
git clone https://github.com/tolobayounousaa225-prog/projet-lecim.git psie-app
cd psie-app/psie/deploy && ./installer.sh --serveur-dedie
```

### Passer de l'essai privé au mode public

Après `./installer.sh --essai` (sans domaine ni e-mail), quand l'envoi d'e-mails est prêt (Gmail : validation en
2 étapes + « mot de passe d'application » de 16 lettres) :

```bash
cd psie-app && git pull && cd psie/deploy
./ouvrir-au-public.sh      # sauvegarde .env, active HTTPS + e-mail + double vérification, teste l'envoi
```
Retour arrière en cas de problème : `cp .env.avant-public .env && docker compose --env-file .env up -d`.

## 3. Installation

### Installation automatique (recommandée)

```bash
cd psie-app/psie/deploy
./installer.sh            # pose 5 questions (domaine, e-mail…), génère les secrets, démarre, crée l'administrateur
./installer.sh --essai    # essai privé sans domaine ni e-mail, visible par tunnel SSH seulement
```

Le script vérifie la mémoire et le port, ne touche jamais à la LECIM, ne remplace jamais un `.env` existant et
termine en affichant le bloc exact à ajouter au reverse proxy. Les étapes manuelles ci-dessous disent la même
chose, pas à pas.

### Installation manuelle

```bash
# Sur le serveur
git clone https://github.com/tolobayounousaa225-prog/projet-lecim.git psie-app   # puis choisir la bonne branche
cd psie-app/psie/deploy
cp .env.example .env && chmod 600 .env
nano .env                         # remplacer TOUTES les valeurs « CHANGER »
```

Générer les secrets :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"    # pour SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"    # pour POSTGRES_PASSWORD
```

L'application **refuse de démarrer** (avec un message clair) si `COOKIE_SECURE=true` et que la
configuration est dangereuse : clé secrète faible, double authentification sans SMTP, adresse publique
en `http://`, etc.

Réglages importants du fichier `.env` (mode A, Contabo) :

| Variable | Valeur |
|---|---|
| `DOMAIN` | le nom de domaine du **serveur** (ex. `app.psie-ci.org`) ou, en attendant, `IP-AVEC-TIRETS.sslip.io` |
| `PUBLIC_BASE_URL` | `https://` + la même adresse |
| `VITRINE_URL` | `https://tolobayounousaa225-prog.github.io/PSIE/` (**majuscules à respecter**), puis le domaine du site quand il existe |
| `VITRINE_ORIGINS` | `https://tolobayounousaa225-prog.github.io` (**sans chemin**) |

Démarrage :

```bash
docker compose --env-file .env up -d --build                  # mode A (Contabo, reverse proxy déjà en place de la LECIM)
# mode B (serveur dédié sans reverse proxy) : ajouter --profile caddy, Caddy obtient alors le certificat HTTPS
docker compose ps                                              # api et db doivent être « healthy »
docker compose exec api python -m scripts.init_db              # crée le compte administrateur et les 6 fondateurs
curl -s http://127.0.0.1:8100/health/db                        # doit afficher {"status":"ok"}
```

Les migrations de base de données sont appliquées **automatiquement** à chaque démarrage.

## 4. Brancher le reverse proxy de la LECIM (mode A : c'est le cas sur le Contabo)

La PSIE écoute sur `127.0.0.1:8100` du serveur. Il faut dire au Caddy existant d'y envoyer le
trafic du nouveau domaine. Regardez d'abord comment il tourne :

```bash
docker ps | grep -i caddy        # une ligne = Caddy tourne dans Docker ; aucune = Caddy est installé sur le serveur
```

- **Caddy installé sur le serveur** : ajouter dans son `Caddyfile` (souvent `/etc/caddy/Caddyfile`) :
  ```
  psie-ci.org {
      encode gzip
      reverse_proxy 127.0.0.1:8100
  }
  ```
  puis `sudo systemctl reload caddy`.
- **Caddy dans Docker** : il ne voit pas `127.0.0.1` du serveur. Ajouter dans son `Caddyfile` le même
  bloc mais avec `reverse_proxy host.docker.internal:8100`, et donner à son conteneur l'accès à l'hôte
  (`extra_hosts: ["host.docker.internal:host-gateway"]` dans sa composition), puis le recharger.
  *Si vous hésitez, ne touchez à rien : envoyez-moi le résultat de `docker ps` et de la composition
  de la LECIM, je vous donnerai les lignes exactes.*

Vérifiez ensuite : `https://VOTRE-DOMAINE/health` doit répondre `{"status":"ok"}`.

## 5. Première connexion

1. Ouvrir `https://VOTRE-DOMAINE/login` avec `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD`.
2. Un code à 6 chiffres arrive par e-mail : le saisir. **Si rien n'arrive**, vérifier le SMTP
   (`docker compose logs api | tail -50`).
3. Créer les comptes du DEN, du secrétaire aux finances, etc. dans « Comptes ». **Pour le DEN et le secrétaire aux finances, choisir leur organisation d'origine** (celle qui les a proposés) : sans elle, ils ne pourront pas signer de dépense, et la plateforme refuse que les deux signataires viennent de la même organisation.
4. Compléter les fiches des 6 fondateurs (nom complet, e-mail, téléphone), saisir les mandats.

5. **Chaque personne change son mot de passe** à sa première connexion (menu « Mot de passe »).
   Mot de passe oublié : l'administrateur en définit un nouveau dans « Comptes » (cela débloque aussi
   un compte verrouillé). Il n'existe pas encore de lien « mot de passe oublié » automatique par e-mail.

## 6. Sauvegardes (automatiques)

Une seule commande met tout en place :

```bash
cd ~/psie-app/psie/deploy        # le dossier où se trouve docker-compose.yml
./sauvegardes-auto.sh
```

Elle crée la phrase secrète (affichée **une seule fois** : copiez-la dans un gestionnaire de mots de passe,
**hors du serveur**), planifie une sauvegarde chiffrée **chaque nuit à 2 h 15** et un **test de restauration
chaque dimanche à 3 h 30**, puis fait tout de suite une première sauvegarde et la restaure en test.
Les sauvegardes de plus de 30 jours sont supprimées. Relancer la commande ne casse rien et ne change jamais la
phrase secrète.

> **Sans cette phrase, les sauvegardes sont illisibles pour toujours.** Ne la gardez pas seulement
> sur le serveur.

Vérifier quand vous voulez que tout tourne : `./sauvegardes-auto.sh --statut` (dernière sauvegarde, tâches
planifiées, fin du journal `backups/backup.log`).

Commandes manuelles (déjà utilisées par l'automatisation) :

```bash
./backup.sh                                   # une sauvegarde chiffrée tout de suite, dans ./backups
./restore.sh --test backups/psie-XXXX.sql.gz.enc   # prouve qu'elle est restaurable (sans toucher à la production)
```

**Copie hors du serveur** : un disque qui tombe en panne emporte aussi ses sauvegardes. Définissez dans
`.env` une commande de copie, par exemple `BACKUP_OFFSITE_CMD="scp {} utilisateur@autre-machine:psie/"`
(`{}` est remplacé par le fichier). **Refaites `./restore.sh --test` tous les mois.**

Restaurer en production (en cas de catastrophe uniquement) : `./restore.sh --prod FICHIER`.

## 7. Mettre à jour

```bash
cd ~/psie-app && git pull
cd psie/deploy
./backup.sh                                   # toujours sauvegarder avant
docker compose --env-file .env up -d --build  # les migrations s'appliquent toutes seules
docker compose ps && curl -s http://127.0.0.1:8100/health/db
```

Retour en arrière : `git checkout <ancienne-version>` puis la même commande `up -d --build`. Si une
migration avait modifié la base, restaurer la sauvegarde faite juste avant.

## 8. Surveillance et dépannage

| Besoin | Commande |
|---|---|
| Voir les erreurs | `docker compose logs --tail=100 api` |
| L'application répond-elle ? | `curl -s http://127.0.0.1:8100/health/db` |
| Redémarrer | `docker compose restart api` |
| L'API refuse de démarrer | lire le message « Configuration de production refusée » dans les logs |
| Pas d'e-mail de code | vérifier `SMTP_*` ; sans e-mail, l'administrateur et le secrétaire aux finances ne peuvent pas se connecter |
| Espace disque | `df -h /` puis `docker system df` |

Pare-feu conseillé (si ce n'est pas déjà fait) : `sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable`.
La base PostgreSQL n'a **aucun port publié** : elle n'est joignable que par l'application.

## 9. Checklist avant d'ouvrir au public

- [ ] `https://VOTRE-DOMAINE/health/db` répond `ok`, le cadenas HTTPS est valide
- [ ] Le site vitrine (dépôt `PSIE`) est en ligne, ses boutons « Adhérer » et « Connexion » mènent à l'application, et les membres et actualités s'affichent
- [ ] `VITRINE_URL` et `VITRINE_ORIGINS` renseignés ; la racine de l'application renvoie bien vers le site
- [ ] Vrai nom de domaine en place (`PUBLIC_BASE_URL`) **avant** d'imprimer le moindre reçu ou certificat
- [ ] Connexion de l'administrateur avec code reçu par e-mail
- [ ] Mot de passe administrateur par défaut changé (menu « Mot de passe »)
- [ ] Les 6 fondateurs complétés, mandats saisis, comptes du DEN et du secrétaire aux finances créés
- [ ] Montant de la cotisation de l'année saisi
- [ ] DEN et secrétaire aux finances créés **avec leur organisation d'origine** (organisations différentes) ; une dépense de test signée, payée puis annulée côté test
- [ ] Seuil de vérification renforcée des dons défini par le secrétaire aux finances
- [ ] `./sauvegardes-auto.sh` lancé ; phrase secrète copiée hors du serveur ; `--statut` tout vert
- [ ] Copie hors serveur configurée
- [ ] Traductions arabes relues ; logo en place
- [ ] Un faux dépôt d'adhésion testé de bout en bout
