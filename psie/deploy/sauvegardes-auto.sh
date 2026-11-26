#!/usr/bin/env bash
# Met en place les sauvegardes AUTOMATIQUES de la base PSIE, en une seule commande.
#   ./sauvegardes-auto.sh              installe (ou répare) : phrase secrète, tâche de 2 h 15 chaque nuit,
#                                      test de restauration chaque dimanche, première sauvegarde + test tout de suite
#   ./sauvegardes-auto.sh --statut     dit si tout fonctionne (dernière sauvegarde, tâches planifiées)
#   ./sauvegardes-auto.sh --sans-docker --sans-test     (pour les tests automatiques seulement)
# Relancer la commande ne change rien de ce qui marche déjà : la phrase secrète n'est jamais remplacée.
set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"
MODE="install"; DOCKER=1; TEST=1
for a in "$@"; do
  case "$a" in
    --statut) MODE="statut" ;;
    --sans-docker) DOCKER=0 ;;
    --sans-test) TEST=0 ;;
    *) echo "Option inconnue : $a" >&2; exit 2 ;;
  esac
done
[ -f .env ] && set -a && . ./.env && set +a
BACKUP_DIR="${BACKUP_DIR:-./backups}"
PASSFILE="${BACKUP_PASSFILE:-./backup.pass}"
MARK="# psie-sauvegarde"
CRON_BACKUP="15 2 * * * cd $DIR && ./backup.sh >> backups/backup.log 2>&1 $MARK"
CRON_TEST="30 3 * * 0 cd $DIR && ./restore.sh --test \"\$(ls -1t backups/psie-*.sql.gz.enc | head -1)\" >> backups/backup.log 2>&1 $MARK"

latest() { ls -1t "$BACKUP_DIR"/psie-*.sql.gz.enc 2>/dev/null | head -1 || true; }
cron_ok() { crontab -l 2>/dev/null | grep -c "$MARK" || true; }

statut() {
  echo "=== Sauvegardes PSIE ==="
  local last; last="$(latest)"
  if [ -z "$last" ]; then
    echo "✗ Aucune sauvegarde trouvée dans $BACKUP_DIR"; return 1
  fi
  local age_h=$(( ( $(date +%s) - $(stat -c %Y "$last") ) / 3600 ))
  echo "Dernière sauvegarde : $(basename "$last") (il y a ${age_h} h, $(du -h "$last" | cut -f1))"
  echo "Nombre de sauvegardes conservées : $(ls -1 "$BACKUP_DIR"/psie-*.sql.gz.enc | wc -l) (les plus anciennes que ${BACKUP_KEEP_DAYS:-30} jours sont supprimées)"
  local rc=0
  if [ "$age_h" -gt 26 ]; then echo "✗ ATTENTION : la dernière sauvegarde a plus de 26 h — la tâche de nuit ne tourne pas ?"; rc=1
  else echo "✓ Sauvegarde récente"; fi
  if [ "$(cron_ok)" -ge 2 ]; then echo "✓ Tâches planifiées en place (sauvegarde 2 h 15 chaque nuit, test chaque dimanche)"
  else echo "✗ Tâches planifiées absentes : relancez ./sauvegardes-auto.sh"; rc=1; fi
  [ -n "${BACKUP_OFFSITE_CMD:-}" ] && echo "✓ Copie hors serveur configurée" || echo "• Copie hors serveur NON configurée (conseillé, voir DEPLOIEMENT.md §6)"
  [ -f backups/backup.log ] && { echo "--- Fin du journal (backups/backup.log)"; tail -n 5 backups/backup.log; }
  return $rc
}

if [ "$MODE" = "statut" ]; then statut; exit $?; fi

echo "=== Mise en place des sauvegardes automatiques ==="
[ -x ./backup.sh ] && [ -x ./restore.sh ] || { echo "ERREUR : backup.sh / restore.sh introuvables ou non exécutables (chmod +x)." >&2; exit 1; }
command -v openssl >/dev/null || { echo "ERREUR : openssl est absent (apt install openssl)." >&2; exit 1; }
command -v crontab >/dev/null || { echo "ERREUR : crontab est absent (apt install cron)." >&2; exit 1; }
if [ "$DOCKER" = 1 ]; then
  docker compose ps -q db 2>/dev/null | grep -q . || { echo "ERREUR : la base ne tourne pas. Lancez d'abord : docker compose up -d" >&2; exit 1; }
fi

# 1. Phrase secrète : créée une seule fois, jamais remplacée (sinon les anciennes sauvegardes deviendraient illisibles)
if [ -s "$PASSFILE" ]; then
  echo "✓ Phrase secrète déjà présente ($PASSFILE) : conservée."
else
  openssl rand -base64 33 | tr -d '\n=' > "$PASSFILE"; chmod 600 "$PASSFILE"
  echo
  echo "┌──────────────────────────────────────────────────────────────────────────┐"
  echo "│ PHRASE SECRÈTE DES SAUVEGARDES — à COPIER MAINTENANT dans un gestionnaire │"
  echo "│ de mots de passe (ou la noter), HORS du serveur. Elle ne sera plus        │"
  echo "│ jamais affichée. Sans elle, les sauvegardes sont illisibles pour toujours.│"
  echo "└──────────────────────────────────────────────────────────────────────────┘"
  cat "$PASSFILE"; echo; echo
  if [ -t 0 ]; then read -r -p "Appuyez sur Entrée quand vous l'avez copiée... " _; fi
fi

# 2. Tâches planifiées (idempotent : on remplace les anciennes lignes marquées, on touche à rien d'autre)
mkdir -p backups; chmod 700 backups
OLD="$(crontab -l 2>/dev/null | grep -v "$MARK" || true)"     # lu en entier avant d'écrire (pas de lecture/écriture simultanées)
{ [ -n "$OLD" ] && printf '%s\n' "$OLD"; echo "$CRON_BACKUP"; echo "$CRON_TEST"; } | crontab -
echo "✓ Tâches planifiées : sauvegarde chaque nuit à 2 h 15, test de restauration chaque dimanche à 3 h 30."

# 3. Première sauvegarde + preuve qu'elle se restaure
./backup.sh
if [ "$TEST" = 1 ]; then
  ./restore.sh --test "$(latest)"
fi
echo
statut || true
echo
echo "Terminé. Vérifiez quand vous voulez avec : ./sauvegardes-auto.sh --statut"
