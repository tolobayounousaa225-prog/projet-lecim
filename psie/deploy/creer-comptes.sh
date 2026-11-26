#!/usr/bin/env bash
# Crée des comptes (secrétariats, faîtières…) à partir d'une liste, sans jamais choisir ni envoyer de mot de passe :
# chaque personne reçoit par e-mail un lien personnel (valable 7 jours) pour choisir le sien.
#   ./creer-comptes.sh mes-comptes.csv              simulation : montre ce qui serait créé, ne crée RIEN
#   ./creer-comptes.sh mes-comptes.csv --appliquer  crée les comptes et envoie les invitations
# Modèle de fichier : comptes-modele.csv (colonnes : nom ; email ; role ; faitiere ; origine), à ouvrir avec Excel.
set -euo pipefail
cd "$(dirname "$0")"
FILE="${1:-}"; shift || true
[ -n "$FILE" ] && [ -f "$FILE" ] || { echo "Usage : $0 FICHIER.csv [--appliquer] [--afficher-liens]" >&2; exit 2; }
docker compose ps -q api 2>/dev/null | grep -q . || { echo "ERREUR : l'application ne tourne pas (docker compose up -d)." >&2; exit 1; }
REMOTE="/tmp/comptes-$$.csv"
trap 'docker compose exec -T -u root api rm -f "$REMOTE" >/dev/null 2>&1 || true' EXIT
docker compose cp "$FILE" "api:$REMOTE" >/dev/null
docker compose exec -T api python -m scripts.creer_comptes "$REMOTE" "$@"
