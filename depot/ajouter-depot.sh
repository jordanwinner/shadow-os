#!/usr/bin/env bash
# Shadow — ajoute le dépôt APT Shadow sur cette machine (à lancer avec sudo).
#   sudo ajouter-depot.sh "file:/chemin/vers/depot/sortie"
#   sudo ajouter-depot.sh "https://exemple.org/shadow"
#   sudo ajouter-depot.sh --retirer        enlève le dépôt
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE="shadow"
COMPOSANT="main"
KEYRING="/etc/apt/keyrings/shadow-os.gpg"
SOURCES="/etc/apt/sources.list.d/shadow-os.sources"

[ "$(id -u)" = 0 ] || { echo "À lancer avec sudo : sudo $0 $*" >&2; exit 1; }

if [ "${1:-}" = "--retirer" ]; then
  rm -f "$KEYRING" "$SOURCES"
  echo "Dépôt Shadow retiré. Pense à : apt update"
  exit 0
fi

BASE="${1:-}"
[ -n "$BASE" ] || { echo "Usage: sudo $0 <URI du dépôt>  (file:… ou https://…)"; exit 1; }
BASE="${BASE%/}"

# clé publique : fournie à côté du script (après construire-depot.sh) ou dans le dépôt file:
PUB=""
for cand in "$ICI/sortie/shadow-os-archive-keyring.gpg" "${BASE#file:}/shadow-os-archive-keyring.gpg"; do
  [ -f "$cand" ] && PUB="$cand" && break
done
if [ -z "$PUB" ] && [ "${BASE#https://}" != "$BASE" -o "${BASE#http://}" != "$BASE" ]; then
  PUB="$(mktemp)"; curl -fsSL "$BASE/shadow-os-archive-keyring.gpg" -o "$PUB" || { echo "clé publique introuvable à $BASE/shadow-os-archive-keyring.gpg"; exit 1; }
fi
[ -n "$PUB" ] || { echo "clé publique introuvable (shadow-os-archive-keyring.gpg)"; exit 1; }

install -d -m 0755 /etc/apt/keyrings
install -m 0644 "$PUB" "$KEYRING"

cat > "$SOURCES" <<EOF
Types: deb
URIs: $BASE
Suites: $SUITE
Components: $COMPOSANT
Signed-By: $KEYRING
EOF

echo "Dépôt Shadow ajouté :"
echo "  clé     : $KEYRING"
echo "  sources : $SOURCES  (URI $BASE)"
echo
echo "Ensuite :"
echo "  apt update && apt install shadow-os"
