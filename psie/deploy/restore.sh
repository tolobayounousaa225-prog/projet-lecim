#!/usr/bin/env bash
# Restaure une sauvegarde chiffrée.
#   ./restore.sh --test FICHIER      restaure dans une base temporaire, vérifie, puis la supprime (sans risque)
#   ./restore.sh --prod FICHIER      REMPLACE la base de production (demande une confirmation)
# Pour tester sans Docker : PSQL_CMD="psql -h localhost -U psie" PGPASSWORD=... ./restore.sh --test FICHIER
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] && set -a && . ./.env && set +a

MODE="${1:-}"; FILE="${2:-}"
[ -n "$MODE" ] && [ -f "$FILE" ] || { echo "Usage : $0 --test|--prod FICHIER.sql.gz.enc" >&2; exit 2; }
PASSFILE="${BACKUP_PASSFILE:-./backup.pass}"
DB="${POSTGRES_DB:-psie}"
USER_DB="${POSTGRES_USER:-psie}"
PSQL_CMD="${PSQL_CMD:-docker compose exec -T db psql -v ON_ERROR_STOP=1 -U $USER_DB}"

decrypt() { openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$PASSFILE" -in "$FILE" | gunzip; }

case "$MODE" in
  --test)
    TARGET="psie_restore_test"
    # La base temporaire est supprimée quoi qu'il arrive (succès, mauvaise phrase secrète, erreur SQL)
    trap '$PSQL_CMD -d postgres -c "DROP DATABASE IF EXISTS $TARGET" > /dev/null 2>&1 || true' EXIT
    $PSQL_CMD -d postgres -c "DROP DATABASE IF EXISTS $TARGET" -c "CREATE DATABASE $TARGET"
    decrypt | $PSQL_CMD -q -d "$TARGET" > /dev/null
    TABLES=$($PSQL_CMD -d "$TARGET" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
    MEMBRES=$($PSQL_CMD -d "$TARGET" -tAc "SELECT count(*) FROM faitieres")
    echo "Restauration de test réussie : $TABLES tables, $MEMBRES membre(s). La base de production n'a pas été touchée."
    [ "$TABLES" -ge 10 ] || { echo "ERREUR : trop peu de tables, sauvegarde suspecte" >&2; exit 1; }
    ;;
  --prod)
    echo "ATTENTION : la base '$DB' va être REMPLACÉE par le contenu de $FILE."
    read -r -p "Tapez le nom de la base ($DB) pour confirmer : " CONFIRM
    [ "$CONFIRM" = "$DB" ] || { echo "Annulé."; exit 1; }
    decrypt | $PSQL_CMD -q -d "$DB" > /dev/null
    echo "Restauration terminée. Relancez l'application : docker compose restart api"
    ;;
  *) echo "Mode inconnu : $MODE" >&2; exit 2 ;;
esac
