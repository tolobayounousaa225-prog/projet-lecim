# Déployer la PSIE sur un serveur

> **Important** : ce guide n'a pas pu être exécuté sur le vrai serveur (aucun accès). Les scripts de
> sauvegarde et de restauration et les migrations ont été testés sur PostgreSQL 16 ; la composition
> Docker est validée par la CI mais n'a jamais tourné sur la machine cible. Suivez les étapes une
> à une et gardez la checklist de la dernière section.

## 0. Ce qu'il faut avant de commencer

| Élément | Pourquoi | Statut |
|---|---|---|
| Accès SSH au serveur (Contabo) | installer et lancer | à vérifier |
| Un **nom de domaine** pour la PSIE (ex. `psie-ci.org`) avec un enregistrement DNS `A` vers l'IP du serveur | HTTPS et QR codes | à choisir |
| Un **serveur e-mail (SMTP)** | code de connexion (double authentification), relances, convocations | à obtenir |
| Les noms du DEN et du secrétaire aux finances | créer leurs comptes | à fournir |
| Le logo de la PSIE | identité visuelle | à fournir |

## 1. Vérifier le serveur (5 minutes)

Connectez-vous en SSH puis lancez ces commandes et **gardez les résultats** :

```bash
free -h                          # mémoire : il faut au moins 1 Go de libre une fois la LECIM démarrée
df -h /                          # disque : au moins 5 Go libres
docker --version && docker compose version
docker ps --format 'table {{.Names}}\t{{.Ports}}'    # qui occupe déjà les ports 80 et 443 ?
```

Si la mémoire libre est inférieure à 1 Go, ou si le disque est presque plein, **ne partagez pas le
serveur avec la LECIM** : prenez un petit serveur dédié (Hostinger ou autre) et utilisez le mode B.

## 2. Choisir le mode

- **Mode A : serveur partagé avec la LECIM (recommandé si la place le permet).** Un reverse proxy
  (Caddy) occupe déjà les ports 80 et 443 : la PSIE n'en lance pas un second, on ajoute simplement
  un site à celui qui existe. La base, les fichiers, la configuration et les sauvegardes de la PSIE
  restent **totalement séparés** de ceux de la LECIM.
- **Mode B : serveur dédié.** On lance aussi Caddy avec la PSIE (`--profile caddy`), qui obtient
  tout seul le certificat HTTPS.

## 3. Installation

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

Démarrage :

```bash
docker compose --env-file .env up -d --build                   # mode A
# ou, mode B :  docker compose --env-file .env --profile caddy up -d --build
docker compose ps                                              # api et db doivent être « healthy »
docker compose exec api python -m scripts.init_db              # crée le compte administrateur et les 6 fondateurs
curl -s http://127.0.0.1:8100/health/db                        # doit afficher {"status":"ok"}
```

Les migrations de base de données sont appliquées **automatiquement** à chaque démarrage.

## 4. Brancher le reverse proxy (mode A uniquement)

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
3. Créer les comptes du DEN, du secrétaire aux finances, etc. dans « Comptes ».
4. Compléter les fiches des 6 fondateurs (nom complet, e-mail, téléphone), saisir les mandats.

> **Limite actuelle** : il n'existe pas encore de page « changer mon mot de passe » ni de
> « mot de passe oublié ». Choisissez des mots de passe définitifs à la création des comptes ; en
> cas d'oubli, l'administrateur doit recréer le compte. C'est la prochaine amélioration à faire.

## 6. Sauvegardes (à mettre en place le premier jour)

```bash
cd ~/psie-app/psie/deploy
python3 -c "import secrets; print(secrets.token_urlsafe(32))" > backup.pass && chmod 600 backup.pass
cat backup.pass       # COPIEZ cette phrase dans un gestionnaire de mots de passe, HORS du serveur
```

> **Sans cette phrase, les sauvegardes sont illisibles pour toujours.** Ne la gardez pas seulement
> sur le serveur.

```bash
./backup.sh                                   # sauvegarde chiffrée dans ./backups
./restore.sh --test backups/psie-XXXX.sql.gz.enc   # prouve qu'elle est restaurable (sans toucher à la production)
crontab -e                                    # puis ajouter, pour une sauvegarde chaque nuit à 2 h :
# 0 2 * * * cd /home/UTILISATEUR/psie-app/psie/deploy && ./backup.sh >> backups/backup.log 2>&1
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
- [ ] Connexion de l'administrateur avec code reçu par e-mail
- [ ] Mot de passe administrateur par défaut changé (compte recréé avec un mot de passe fort)
- [ ] Les 6 fondateurs complétés, mandats saisis, comptes du DEN et du secrétaire aux finances créés
- [ ] Montant de la cotisation de l'année saisi
- [ ] Une sauvegarde faite **et** restaurée en test ; phrase secrète copiée hors du serveur
- [ ] Copie hors serveur configurée ; tâche cron en place
- [ ] Traductions arabes relues ; logo en place
- [ ] Un faux dépôt d'adhésion testé de bout en bout
