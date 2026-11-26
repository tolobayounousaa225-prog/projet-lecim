# En cas d'urgence

Tout se fait en SSH sur le serveur, dossier `~/psie-app/psie/deploy`. Garder ce document hors du serveur aussi.

## Le site ne répond plus
```bash
cd ~/psie-app/psie/deploy
docker compose -p psie ps                       # db et api doivent être « Up »
docker compose -p psie logs api --tail 50       # chercher Traceback / Error
docker compose -p psie up -d                    # relance ce qui est arrêté
bash diagnostic.sh                              # lecture seule : mémoire, disque, ports
```
- **Disque plein** : `df -h` ; supprimer d'anciennes sauvegardes de `backups/` (`ls -lh backups/`) ou des images Docker inutiles (`docker image prune`).
- **Après une mise à jour qui casse** : revenir à la version précédente (`git log --oneline`, `git checkout <ancien-commit>`, `docker compose -p psie up -d --build`), puis restaurer la base **seulement** si une migration l'a abîmée.

## Restaurer une sauvegarde
```bash
./restore.sh --test backups/psie-AAAA-MM-JJ_HHMM.sql.gz.enc    # essai sur une base temporaire (sans risque)
./restore.sh --prod backups/psie-AAAA-MM-JJ_HHMM.sql.gz.enc    # REMPLACE la production (demande confirmation)
docker compose -p psie restart api
```
Il faut la **phrase secrète** (`backup.pass`, copiée hors du serveur). Sans elle les sauvegardes sont illisibles.

## Plus personne ne peut se connecter
- Compte verrouillé (trop d'échecs) : se débloque seul après quelques minutes, ou l'administrateur définit un nouveau mot de passe (menu **Comptes**).
- L'administrateur lui-même est bloqué : relancer l'initialisation, qui recrée le compte amorce si besoin :
  `docker compose -p psie exec api python -m scripts.init_db` (utilise `ADMIN_BOOTSTRAP_*` du fichier `.env`).
- Le code de double authentification n'arrive pas : vérifier le courrier indésirable, puis `docker compose -p psie logs api | grep -i smtp`. Mot de passe d'application Gmail révoqué ? En générer un nouveau et corriger `SMTP_PASSWORD` dans `.env`, puis `docker compose -p psie up -d --force-recreate api`.

## Une fuite est suspectée (mot de passe, jeton)
1. **Jeton GitHub** : le révoquer sur GitHub (Settings → Developer settings), puis `./brancher-site.sh` avec un nouveau.
2. **Mot de passe d'application Gmail** : le révoquer chez Google, en créer un autre, corriger `.env`.
3. **`SECRET_KEY`** : la changer dans `.env` et relancer (toutes les sessions sont fermées).
4. Consulter le **Journal d'audit** (filtre « sensibles ») et en informer le DEN.

## Contacts à compléter
| Qui | Nom | Téléphone / e-mail |
|---|---|---|
| Responsable technique | | |
| Hébergeur (Contabo) | | |
| Fournisseur de domaine | | |
