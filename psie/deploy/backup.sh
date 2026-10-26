#!/usr/bin/env bash
# Sauvegarde chiffrée de la base PSIE.
#   ./backup.sh            -> crée backups/psie-AAAA-MM-JJ_HHMM.sql.gz.enc et supprime les anciennes
# Variables (lues dans .env) : BACKUP_DIR, BACKUP_KEEP_DAYS, BACKUP_PASSFILE, POSTGRES_USER, POSTGRES_DB.
# Pour tester sans Docker : PGDUMP_CMD="pg_dump -h localhost -U psie" PGPASSWORD=... ./backup.sh
set -euo pipefail
cd "$(dirname "$0")"
[ -f .env ] && set -a && . ./.env && set +a

BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"
PASSFILE="${BACKUP_PASSFILE:-./backup.pass}"
DB="${POSTGRES_DB:-psie}"
USER_DB="${POSTGRES_USER:-psie}"
PGDUMP_CMD="${PGDUMP_CMD:-docker compose exec -T db pg_dump -U $USER_DB}"

[ -s "$PASSFILE" ] || { echo "ERREUR : fichier de phrase secrète absent ou vide : $PASSFILE" >&2; exit 1; }
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

OUT="$BACKUP_DIR/psie-$(date +%Y-%m-%d_%H%M).sql.gz.enc"
TMP="$OUT.partial"
trap 'rm -f "$TMP"' EXIT

# pg_dump | compression | chiffrement AES-256 : rien n'est jamais écrit en clair sur le disque
$PGDUMP_CMD --no-owner --clean --if-exists "$DB" | gzip -9 \
  | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass "file:$PASSFILE" > "$TMP"

# Une sauvegarde vide ou minuscule est un échec silencieux : on le refuse
SIZE=$(wc -c < "$TMP")
[ "$SIZE" -gt 500 ] || { echo "ERREUR : sauvegarde anormalement petite ($SIZE octets)" >&2; exit 1; }
mv "$TMP" "$OUT"
chmod 600 "$OUT"
echo "Sauvegarde créée : $OUT ($SIZE octets)"

find "$BACKUP_DIR" -name 'psie-*.sql.gz.enc' -mtime "+$KEEP_DAYS" -delete

# Copie hors serveur (facultatif) : définir BACKUP_OFFSITE_CMD, ex. "rclone copy {} remote:psie"
if [ -n "${BACKUP_OFFSITE_CMD:-}" ]; then
  eval "${BACKUP_OFFSITE_CMD//\{\}/$OUT}" && echo "Copie hors serveur effectuée."
fi
