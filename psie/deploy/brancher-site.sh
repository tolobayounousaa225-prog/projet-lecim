#!/usr/bin/env bash
# Branche le site vitrine à l'application : le site se reconstruit tout seul quand un éditeur modifie le contenu.
#   ./brancher-site.sh                  fait tout : jeton GitHub, reprise du contenu actuel du site, redémarrage, contrôles
#   ./brancher-site.sh --seulement-env  écrit seulement le jeton dans .env (pour les tests)
# Le jeton GitHub est saisi ICI, en caché : il n'est jamais affiché, jamais envoyé dans une conversation.
set -euo pipefail
cd "$(dirname "$0")"
# Lit .env ligne par ligne SANS l'exécuter : une valeur avec des espaces (ex. « Administrateur PSIE ») ne pose aucun problème.
load_env() {
  local line key val
  [ -f .env ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|\#*) continue ;; esac
    key="${line%%=*}"; val="${line#*=}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    val="${val%\"}"; val="${val#\"}"
    export "$key=$val"
  done < .env
}
ONLY_ENV=0
for a in "$@"; do
  case "$a" in
    --seulement-env) ONLY_ENV=1 ;;
    *) echo "Option inconnue : $a" >&2; exit 2 ;;
  esac
done
[ -f .env ] || { echo "ERREUR : .env introuvable (lancez d'abord installer.sh)." >&2; exit 1; }
SITE_REPO="${SITE_REPO:-tolobayounousaa225-prog/PSIE}"
[[ "$SITE_REPO" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || { echo "ERREUR : nom de dépôt invalide : $SITE_REPO" >&2; exit 2; }

echo "=== Brancher le site vitrine ($SITE_REPO) ==="
if [ -z "${PSIE_TOKEN:-}" ]; then
  cat <<'TXT'

Avant de continuer, créez le jeton GitHub (2 minutes) :
  1. GitHub → votre photo → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token
  2. Nom : psie-site ; durée : 1 an ; « Repository access » : Only select repositories → PSIE (uniquement)
  3. « Permissions » → Repository permissions → Contents : Read and write
  4. Generate token, puis copiez le jeton (il commence par github_pat_)
TXT
  read -r -s -p "Collez le jeton ici (rien ne s'affiche) puis Entrée : " PSIE_TOKEN; echo
fi
[[ "$PSIE_TOKEN" =~ ^(github_pat_|ghp_)[A-Za-z0-9_]{30,}$ ]] || { echo "ERREUR : ce n'est pas un jeton GitHub (il commence par github_pat_ et ne contient ni espace ni guillemet)." >&2; exit 1; }

set_env() {   # remplace la ligne KEY=... ou l'ajoute ; ne touche à aucune autre ligne
  local key="$1" value="$2" tmp; tmp="$(mktemp)"
  grep -v "^${key}=" .env > "$tmp" || true
  printf '%s=%s\n' "$key" "$value" >> "$tmp"
  cat "$tmp" > .env; rm -f "$tmp"
}
cp -p .env .env.avant-site; chmod 600 .env.avant-site .env
set_env GITHUB_DISPATCH_REPO "$SITE_REPO"
set_env GITHUB_DISPATCH_TOKEN "$PSIE_TOKEN"
echo "✓ Jeton enregistré dans .env (copie de l'ancien .env : .env.avant-site)"
[ "$ONLY_ENV" = 1 ] && exit 0

load_env
code=$(curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $GITHUB_DISPATCH_TOKEN" -H "Accept: application/vnd.github+json" "https://api.github.com/repos/$SITE_REPO" || true)
if [ "$code" != "200" ]; then
  echo "ERREUR : GitHub refuse ce jeton pour $SITE_REPO (code $code). Vérifiez le dépôt choisi et la permission « Contents : Read and write »." >&2
  echo "Le jeton est déjà dans .env ; relancez ce script après correction." >&2
  exit 1
fi
echo "✓ GitHub accepte le jeton pour $SITE_REPO"

echo "→ Redémarrage de l'application pour prendre en compte le jeton…"
docker compose up -d --force-recreate api >/dev/null
for i in $(seq 1 30); do
  docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/db', timeout=3)" >/dev/null 2>&1 && break
  sleep 2
done

echo "→ Reprise du contenu actuel du site (rien n'est écrasé s'il existe déjà)…"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
git clone --depth 1 "https://github.com/$SITE_REPO.git" "$WORK/site" >/dev/null 2>&1 \
  || { echo "ERREUR : impossible de télécharger le dépôt $SITE_REPO (privé ? renseignez-le avec SITE_REPO=... )." >&2; exit 1; }
docker compose cp "$WORK/site" api:/tmp/psie-site
docker compose exec -T api python -m scripts.import_site_content /tmp/psie-site
docker compose exec -T -u root api rm -rf /tmp/psie-site

BASE="${PUBLIC_BASE_URL:-https://$DOMAIN}"; BASE="${BASE%/}"
n=$(curl -s "$BASE/api/public/site.json" | python3 -c "import json,sys; d=json.load(sys.stdin); print(sum(len(v) for v in d.values() if isinstance(v,(list,dict))))" 2>/dev/null || echo 0)
echo "✓ L'application publie $n élément(s) de contenu à $BASE/api/public/site.json"
[ "$n" -gt 0 ] || { echo "ERREUR : le contenu publié est vide : NE configurez PAS CONTENT_URL tant que ce n'est pas réglé." >&2; exit 1; }

cat <<TXT

=== Dernière étape, à faire sur GitHub (je ne peux pas la faire à votre place) ===
  Dépôt PSIE → Settings → Secrets and variables → Actions → onglet « Variables » → New repository variable
    Nom    : CONTENT_URL
    Valeur : $BASE/api/public/site.json
  Puis testez : modifiez l'annonce dans « Contenu du site » de l'application, regardez l'onglet Actions du dépôt PSIE :
  une construction « Site vitrine » démarre seule et le site change en 1 à 2 minutes.
TXT
