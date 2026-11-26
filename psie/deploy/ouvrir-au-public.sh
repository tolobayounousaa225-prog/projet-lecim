#!/usr/bin/env bash
# Passe la PSIE du « mode essai privé » au mode public : HTTPS automatique (Caddy), e-mail et double
# vérification activés. À lancer sur le serveur, depuis ce dossier :   ./ouvrir-au-public.sh
# Il sauvegarde d'abord le .env (.env.avant-public) et dit comment revenir en arrière.
#   --sans-docker   modifie seulement le .env puis s'arrête (pour tester)
set -euo pipefail
cd "$(dirname "$0")"

SANS_DOCKER=0
for arg in "$@"; do
  case "$arg" in
    --sans-docker) SANS_DOCKER=1 ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "Option inconnue : $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\nERREUR : %s\n' "$*" >&2; exit 1; }
ask() {
  local var="$1" question="$2" default="${3:-}" value
  value="${!var:-}"
  if [ -z "$value" ] && [ -t 0 ]; then read -r -p "$question${default:+ [$default]} : " value; fi
  printf '%s' "${value:-$default}"
}
ask_secret() {
  local var="$1" question="$2" value
  value="${!var:-}"
  if [ -z "$value" ] && [ -t 0 ]; then read -r -s -p "$question : " value; echo; fi
  printf '%s' "$value"
}
get_env() { grep -E "^$1=" .env | head -1 | cut -d= -f2- || true; }
set_env() {   # remplace la ligne KEY=... (ou l'ajoute) sans interpréter les caractères spéciaux
  KEY="$1" VALUE="$2" python3 - <<'PY'
import os, re
key, value = os.environ["KEY"], os.environ["VALUE"]
lines = open(".env", encoding="utf-8").read().splitlines()
out, done = [], False
for line in lines:
    if re.match(rf"{re.escape(key)}=", line):
        out.append(f"{key}={value}"); done = True
    else:
        out.append(line)
if not done:
    out.append(f"{key}={value}")
open(".env", "w", encoding="utf-8").write("\n".join(out) + "\n")
PY
}
port_busy() { (ss -tln 2>/dev/null || netstat -tln 2>/dev/null) | grep -qE "[:.]$1[[:space:]]"; }

say "1/5 Vérifications"
[ -f .env ] || fail "Pas de fichier .env ici : lancez d'abord ./installer.sh"
if [ "$(get_env COOKIE_SECURE)" = "true" ]; then fail "L'application est déjà en mode public (COOKIE_SECURE=true). Rien à faire."; fi
if [ "$SANS_DOCKER" -eq 0 ]; then
  command -v docker >/dev/null && docker info >/dev/null 2>&1 || fail "Docker ne répond pas."
  for p in 80 443; do port_busy "$p" && fail "Le port $p est déjà utilisé : ce serveur partage-t-il un autre site ? Voir DEPLOIEMENT.md (installation partagée)."; done
fi

say "2/5 Réponses"
DOMAINE=$(ask PSIE_DOMAIN "Nom de domaine (laissez vide pour l'adresse provisoire en .sslip.io)")
if [ -z "$DOMAINE" ]; then
  IP=$(ask PSIE_IP "Adresse IP de ce serveur (ex. 203.0.113.7)")
  printf '%s' "$IP" | grep -qE '^([0-9]{1,3}\.){3}[0-9]{1,3}$' || fail "Adresse IP invalide : « $IP »."
  DOMAINE="$(printf '%s' "$IP" | tr . -).sslip.io"
  echo "Adresse provisoire : $DOMAINE"
fi
case "$DOMAINE" in *[!A-Za-z0-9.-]*|"."*|*"..") fail "Nom de domaine invalide : $DOMAINE" ;; esac
SMTP_HOST=$(ask SMTP_HOST "Serveur e-mail SMTP" "smtp.gmail.com")
SMTP_PORT=$(ask SMTP_PORT "Port SMTP" 587)
SMTP_USER=$(ask SMTP_USER "Utilisateur SMTP (pour Gmail : l'adresse Gmail complète)")
[ -n "$SMTP_USER" ] || fail "L'utilisateur SMTP est obligatoire."
SMTP_PASSWORD=$(ask_secret SMTP_PASSWORD "Mot de passe SMTP (pour Gmail : le code de 16 lettres ; invisible pendant la saisie)")
SMTP_PASSWORD="${SMTP_PASSWORD//[[:space:]]/}"   # Google affiche le code par blocs de 4 lettres : les espaces sont inutiles
[ -n "$SMTP_PASSWORD" ] || fail "Le mot de passe SMTP est obligatoire."
if printf '%s' "$SMTP_PASSWORD" | grep -q '[$#"'"'"'\\`]'; then
  fail "Ce mot de passe contient un caractère non pris en charge dans le fichier .env. Pour Gmail, utilisez le code d'application de 16 lettres."
fi
SMTP_FROM=$(ask SMTP_FROM "Adresse d'expédition (pour Gmail : la même adresse)" "$SMTP_USER")

say "3/5 Mise à jour du fichier .env"
cp -p .env .env.avant-public
for kv in "DOMAIN=$DOMAINE" "PUBLIC_BASE_URL=https://$DOMAINE" "COOKIE_SECURE=true" "TWO_FACTOR_ENABLED=true" \
          "SMTP_HOST=$SMTP_HOST" "SMTP_PORT=$SMTP_PORT" "SMTP_USER=$SMTP_USER" "SMTP_PASSWORD=$SMTP_PASSWORD" "SMTP_FROM=$SMTP_FROM"; do
  set_env "${kv%%=*}" "${kv#*=}"
done
chmod 600 .env
echo "Ancien fichier conservé : .env.avant-public"
[ "$SANS_DOCKER" -eq 1 ] && { say "Terminé : .env modifié, rien n'a été relancé."; exit 0; }

say "4/5 Redémarrage avec HTTPS automatique (Caddy)"
if ! docker compose --env-file .env --profile caddy up -d --build; then
  echo "Retour arrière :  cp .env.avant-public .env && docker compose --env-file .env up -d" >&2
  fail "Le démarrage a échoué (voir ci-dessus)."
fi

say "5/5 Attente du certificat HTTPS (1 à 3 minutes)"
OK=0
for i in $(seq 1 60); do
  if curl -fsS "https://${DOMAINE}/health" >/dev/null 2>&1; then OK=1; break; fi
  sleep 5
done
if [ "$OK" -ne 1 ]; then
  docker compose --env-file .env --profile caddy logs --tail=30 api caddy >&2 || true
  echo "Retour arrière :  cp .env.avant-public .env && docker compose --env-file .env up -d" >&2
  fail "https://${DOMAINE}/health ne répond pas encore. Vérifiez que les ports 80 et 443 sont ouverts chez le fournisseur."
fi
echo "Application publique : $(curl -fsS "https://${DOMAINE}/health")"

ADMIN=$(get_env ADMIN_BOOTSTRAP_EMAIL)
say "Test d'envoi d'e-mail vers ${ADMIN}"
if docker compose --env-file .env exec -T -e TO="$ADMIN" api python -c "
import os
from app.emailing import send_email
print('Envoyé.' if send_email(os.environ['TO'], 'PSIE — test d\'envoi', 'Si vous lisez ce message, l\'envoi d\'e-mails de la PSIE fonctionne.') else 'ÉCHEC : le serveur e-mail a refusé.')
"; then :; fi

cat <<TXT

Terminé. L'application est en ligne :
    https://${DOMAINE}/login
Vérifiez votre boîte e-mail (et les courriers indésirables) : le message de test doit être arrivé.
Pour que le bouton « Se connecter » du site mène directement ici, ajoutez dans GitHub (dépôt PSIE,
Settings > Secrets and variables > Actions > Variables) :  APP_URL = https://${DOMAINE}
TXT
