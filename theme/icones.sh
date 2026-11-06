#!/usr/bin/env bash
# Shadow — thème d'icônes « Shadow » : Papirus-Dark, mais dossiers en violet (sans sudo).
#   icones.sh apply    construit ~/.local/share/icons/Shadow puis l'active
#   icones.sh revert   remet le thème d'icônes précédent
# Le thème ne contient que des liens vers les dossiers violets de Papirus ;
# tout le reste est hérité de Papirus-Dark.
set -euo pipefail
PAP=/usr/share/icons/Papirus
DST="$HOME/.local/share/icons/Shadow"
SAUV="${XDG_STATE_HOME:-$HOME/.local/state}/shadow-os/icones-avant.txt"
COULEUR=violet

build(){
  [ -d "$PAP" ] || { echo "Papirus introuvable ($PAP)" >&2; exit 1; }
  rm -rf "${DST:?}"; mkdir -p "$DST"
  local dirs=() n=0
  for d in "$PAP"/*/places; do
    local taille; taille=$(basename "$(dirname "$d")")
    mkdir -p "$DST/$taille/places"
    for f in "$d"/folder-$COULEUR*.svg "$d"/user-$COULEUR-*.svg; do
      [ -e "$f" ] || continue
      local nom; nom=$(basename "$f"); nom=${nom/-$COULEUR/}
      ln -s "$f" "$DST/$taille/places/$nom"; n=$((n+1))
    done
    dirs+=("$taille/places")
  done
  { echo "[Icon Theme]"
    echo "Name=Shadow"
    echo "Comment=Shadow OS — Papirus-Dark aux dossiers violets"
    echo "Inherits=Papirus-Dark,breeze-dark,hicolor"
    echo "Example=folder"
    echo "Directories=$(IFS=,; echo "${dirs[*]}")"
    echo
    for t in "${dirs[@]}"; do
      local s=${t%%x*}; local scale=1
      [[ $t == *@2x* ]] && scale=2
      echo "[$t]"; echo "Context=Places"; echo "Size=$s"; echo "Scale=$scale"; echo "Type=Fixed"; echo
    done
  } > "$DST/index.theme"
  gtk-update-icon-cache -q -f -t "$DST" 2>/dev/null || true
  echo "  ✓ thème d'icônes Shadow : $n liens de dossiers"
}

case "${1:-}" in
  apply)
    mkdir -p "$(dirname "$SAUV")"
    [ -f "$SAUV" ] || gsettings get org.gnome.desktop.interface icon-theme > "$SAUV"
    build
    gsettings set org.gnome.desktop.interface icon-theme 'Shadow'
    echo "  ✓ icon-theme = Shadow" ;;
  revert)
    [ -f "$SAUV" ] && gsettings set org.gnome.desktop.interface icon-theme "$(cat "$SAUV")"
    echo "  ✓ thème d'icônes précédent restauré" ;;
  build) build ;;
  *) echo "usage : icones.sh apply|revert|build"; exit 1 ;;
esac
