#!/usr/bin/env bash
# Diagnostic du serveur AVANT d'installer la PSIE à côté de la LECIM. Il ne modifie RIEN : il lit seulement.
# Usage :  bash diagnostic.sh        puis copier-coller tout le résultat dans la conversation.
set -u
title() { printf '\n=== %s ===\n' "$1"; }

title "Système"
. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"
uptime

title "Mémoire (RAM et swap)"
free -h

title "Disque"
df -h / /var/lib/docker 2>/dev/null | sort -u

title "Docker"
if command -v docker >/dev/null; then
  docker --version
  docker compose version 2>/dev/null || echo "docker compose : ABSENT (installer le plugin compose)"
  echo "--- conteneurs en marche"
  docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}' 2>&1 | head -40
  echo "--- projets compose"
  docker compose ls 2>/dev/null | head -20
else
  echo "Docker : ABSENT"
fi

title "Ports à l'écoute (80, 443, 8000, 8100, 5432)"
(ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null) | grep -E ':(80|443|8000|8100|5432)\b' || echo "aucun de ces ports n'est utilisé"

title "Serveur web / reverse proxy"
for p in caddy nginx apache2 httpd traefik; do
  if systemctl is-active --quiet "$p" 2>/dev/null; then echo "$p : actif (installé sur le serveur)"; fi
done
docker ps --format '{{.Names}} {{.Image}}' 2>/dev/null | grep -Ei 'caddy|nginx|traefik|proxy' | sed 's/^/dans Docker : /' || true
ls /etc/caddy/Caddyfile /etc/nginx/sites-enabled 2>/dev/null

title "Pare-feu"
sudo -n ufw status 2>/dev/null || echo "(ufw non lisible sans mot de passe : lancer « sudo ufw status »)"

title "Jitsi / gros consommateurs"
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' 2>/dev/null | head -20

printf '\nFin du diagnostic. Aucun fichier n'"'"'a été modifié.\n'
