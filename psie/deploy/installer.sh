#!/usr/bin/env bash
# Installe la PSIE sur un serveur PARTAGÉ avec la LECIM (reverse proxy déjà en place, mode A).
# Il ne touche à rien de la LECIM : la PSIE vit dans sa propre pile Docker « psie » (base, réseau et
# volumes à elle) et n'écoute que sur 127.0.0.1:PSIE_PORT.
#
# Usage, depuis ce dossier (psie/deploy) :
#   ./installer.sh                 installation guidée (pose quelques questions)
#   ./installer.sh --essai         essai privé : sans HTTPS ni e-mail, visible seulement par tunnel SSH
#   ./installer.sh --seulement-env prépare le fichier .env et s'arrête (rien n'est lancé)
# Sûr à relancer : un .env existant n'est jamais écrasé.
set -euo pipefail
cd "$(dirname "$0")"

ESSAI=0; SEULEMENT_ENV=0
for arg in "$@"; do
  case "$arg" in
    --essai) ESSAI=1 ;;
    --seulement-env) SEULEMENT_ENV=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Option inconnue : $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\nERREUR : %s\n' "$*" >&2; exit 1; }
secret() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }
ask() {   # ask "Question" "valeur par défaut"  (une variable d'environnement du même nom évite la question)
  local var="$1" question="$2" default="${3:-}" value
  value="${!var:-}"
  if [ -z "$value" ]; then
    if [ -t 0 ]; then read -r -p "$question${default:+ [$default]} : " value; fi
    value="${value:-$default}"
  fi
  printf '%s' "$value"
}
port_busy() { (ss -tln 2>/dev/null || netstat -tln 2>/dev/null) | grep -qE "[:.]$1[[:space:]]"; }

say "1/5 Vérifications"
command -v python3 >/dev/null || fail "python3 est requis (sudo apt install python3)"
if [ "$SEULEMENT_ENV" -eq 0 ]; then
  command -v docker >/dev/null || fail "Docker est absent. Installez-le : curl -fsSL https://get.docker.com | sudo sh"
  docker compose version >/dev/null 2>&1 || fail "Le plugin « docker compose » est absent."
  docker info >/dev/null 2>&1 || fail "Docker ne répond pas : l'utilisateur doit être dans le groupe docker (sudo usermod -aG docker \$USER, puis se reconnecter)."
fi
FREE_MB=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)
[ "$FREE_MB" -ge 600 ] || fail "Mémoire disponible insuffisante (${FREE_MB} Mo). La PSIE demande environ 500 Mo ; vérifiez ce que consomme la LECIM (Jitsi surtout)."
echo "Mémoire disponible : ${FREE_MB} Mo — correct."

say "2/5 Réglages"
if [ -f .env ]; then
  echo "Un fichier .env existe déjà : il est conservé tel quel."
else
  PORT="${PSIE_PORT:-8100}"
  if [ "$SEULEMENT_ENV" -eq 0 ] && port_busy "$PORT"; then
    fail "Le port $PORT est déjà utilisé sur ce serveur. Relancez avec un autre :  PSIE_PORT=8110 ./installer.sh"
  fi
  if [ "$ESSAI" -eq 1 ]; then
    DOMAINE="127.0.0.1"; PUBLIC="http://127.0.0.1:$PORT"; COOKIE=false; TWOFA=false
    SMTP_HOST=""; SMTP_PORT=587; SMTP_USER=""; SMTP_PASSWORD=""; SMTP_FROM="no-reply@psie.local"
  else
    DOMAINE=$(ask PSIE_DOMAIN "Nom de domaine de l'application (ex. app.psie-ci.org)")
    [ -n "$DOMAINE" ] || fail "Le nom de domaine est obligatoire (ou utilisez --essai pour un essai privé)."
    case "$DOMAINE" in *[!A-Za-z0-9.-]*|"."*|*"..") fail "Nom de domaine invalide : $DOMAINE" ;; esac
    PUBLIC="https://$DOMAINE"; COOKIE=true; TWOFA=true
    SMTP_HOST=$(ask SMTP_HOST "Serveur e-mail SMTP (obligatoire : code de connexion par e-mail)")
    [ -n "$SMTP_HOST" ] || fail "Sans serveur e-mail, la double authentification bloque la connexion. Voir DEPLOIEMENT.md, section e-mail (ou --essai)."
    SMTP_PORT=$(ask SMTP_PORT "Port SMTP" 587)
    SMTP_USER=$(ask SMTP_USER "Utilisateur SMTP")
    SMTP_PASSWORD=$(ask SMTP_PASSWORD "Mot de passe SMTP")
    SMTP_FROM=$(ask SMTP_FROM "Adresse d'expédition" "no-reply@$DOMAINE")
  fi
  ADMIN_EMAIL=$(ask ADMIN_EMAIL "E-mail du premier administrateur" "admin@psie.local")
  VITRINE_URL_V=$(ask VITRINE_URL "Adresse du site vitrine" "https://tolobayounousaa225-prog.github.io/PSIE/")
  VITRINE_ORIGIN=$(printf '%s' "$VITRINE_URL_V" | sed -E 's#^(https?://[^/]+).*#\1#')
  ADMIN_PASSWORD=$(secret 18)
  umask 077
  cat > .env <<ENV
# Généré par installer.sh — ne jamais commiter ce fichier.
POSTGRES_USER=psie
POSTGRES_DB=psie
POSTGRES_PASSWORD=$(secret 24)
SECRET_KEY=$(secret 48)
COOKIE_SECURE=$COOKIE
DEBUG=false
TWO_FACTOR_ENABLED=$TWOFA
SCHEDULER_ENABLED=true
PUBLIC_BASE_URL=$PUBLIC
DOMAIN=$DOMAINE
VITRINE_URL=$VITRINE_URL_V
VITRINE_ORIGINS=$VITRINE_ORIGIN
GITHUB_DISPATCH_REPO=
GITHUB_DISPATCH_TOKEN=
PSIE_PORT=$PORT
ADMIN_BOOTSTRAP_EMAIL=$ADMIN_EMAIL
ADMIN_BOOTSTRAP_PASSWORD=$ADMIN_PASSWORD
ADMIN_BOOTSTRAP_NAME=Administrateur PSIE
SMTP_HOST=$SMTP_HOST
SMTP_PORT=$SMTP_PORT
SMTP_USER=$SMTP_USER
SMTP_PASSWORD=$SMTP_PASSWORD
SMTP_FROM=$SMTP_FROM
ENV
  chmod 600 .env
  echo "Fichier .env créé (droits 600)."
  echo "Mot de passe du premier administrateur (notez-le, à changer dès la 1re connexion) : $ADMIN_PASSWORD"
fi
[ "$SEULEMENT_ENV" -eq 1 ] && { say "Terminé : .env prêt, rien n'a été lancé."; exit 0; }

say "3/5 Démarrage de la pile « psie » (ne touche pas à la LECIM)"
docker compose --env-file .env up -d --build

say "4/5 Attente de l'application et création du compte administrateur"
PORT=$(grep -E '^PSIE_PORT=' .env | cut -d= -f2)
for i in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${PORT}/health/db" >/dev/null 2>&1; then OK=1; break; fi
  sleep 3
done
[ "${OK:-0}" = 1 ] || { docker compose logs --tail=40 api >&2; fail "L'application ne répond pas (voir les messages ci-dessus)."; }
docker compose exec -T api python -m scripts.init_db
echo "Application prête : $(curl -fsS "http://127.0.0.1:${PORT}/health/db")"

say "5/5 Prochaine étape : brancher le reverse proxy de la LECIM"
DOM=$(grep -E '^DOMAIN=' .env | cut -d= -f2)
if grep -q '^COOKIE_SECURE=false' .env; then
  cat <<TXT
Mode essai : l'application n'est visible que depuis le serveur. Depuis votre ordinateur :
    ssh -L ${PORT}:127.0.0.1:${PORT} utilisateur@IP-DU-SERVEUR
puis ouvrez http://127.0.0.1:${PORT}/login
TXT
else
  cat <<TXT
Dans le reverse proxy déjà en place (voir DEPLOIEMENT.md, section 4), ajoutez le site :

  ${DOM} {
      encode gzip
      reverse_proxy 127.0.0.1:${PORT}
  }

Chez votre fournisseur de domaine, l'enregistrement DNS « A » de ${DOM} doit pointer vers l'IP de ce serveur.
Vérification finale :  https://${DOM}/health   doit répondre {"status":"ok"}
TXT
fi
say "Installation terminée. Pensez à programmer les sauvegardes (DEPLOIEMENT.md, section 6)."
