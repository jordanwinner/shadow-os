#!/usr/bin/env bash
# Rend un SVG en PNG avec Chrome headless (filtres, dégradés et polices fidèles).
# Usage : rendre-svg.sh entree.svg sortie.png LARGEUR HAUTEUR
set -euo pipefail
entree=$(realpath "$1"); sortie=$(realpath -m "$2"); l=$3; h=$4
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/p.html" <<EOF
<!doctype html><html><head><style>
html,body{margin:0;background:transparent;overflow:hidden}
img{display:block;width:${l}px;height:${h}px}
</style></head><body><img src="file://$entree"></body></html>
EOF
google-chrome --headless=new --disable-gpu --hide-scrollbars \
  --user-data-dir="$tmp/profil" --default-background-color=00000000 \
  --window-size="$l,$h" --screenshot="$sortie" "file://$tmp/p.html" >/dev/null 2>&1
test -s "$sortie" && echo "$sortie"
