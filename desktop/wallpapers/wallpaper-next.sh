#!/usr/bin/env bash
# Choisit un fond d'écran au hasard et l'applique (clair + sombre + écran de verrouillage).
# usage : wallpaper-next.sh [anime|hacker|all|auto]   (défaut : all)
#   auto = anime en journée (7 h–19 h), hacker la nuit
set -euo pipefail
DEST="${WALLPAPER_DIR:-$HOME/Images/Wallpapers}"
theme="${1:-all}"
if [ "$theme" = "auto" ]; then
  h=$(date +%-H)
  if [ "$h" -ge 7 ] && [ "$h" -lt 19 ]; then theme="anime"; else theme="hacker"; fi
  # repli sur « all » si le dossier du thème choisi est vide
  [ -d "$DEST/$theme" ] && [ -n "$(find "$DEST/$theme" -type f -print -quit 2>/dev/null)" ] || theme="all"
fi
case "$theme" in
  anime|hacker) search="$DEST/$theme" ;;
  all|*)        search="$DEST" ;;
esac
mapfile -d '' -t imgs < <(find "$search" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) -print0 2>/dev/null)
[ "${#imgs[@]}" -eq 0 ] && { echo "Aucun fond dans $search (lance d'abord wallpaper-dl.sh)"; exit 1; }
cur="$(gsettings get org.gnome.desktop.background picture-uri 2>/dev/null | sed "s/^'file:\/\///;s/'$//")"
# tire un fond différent de l'actuel (si possible)
for _ in 1 2 3 4 5; do
  pick="${imgs[RANDOM % ${#imgs[@]}]}"
  [ "$pick" != "$cur" ] && break
done
uri="file://$pick"
gsettings set org.gnome.desktop.background picture-uri "$uri"
gsettings set org.gnome.desktop.background picture-uri-dark "$uri"
gsettings set org.gnome.desktop.background picture-options 'zoom'
gsettings set org.gnome.desktop.screensaver picture-uri "$uri" 2>/dev/null || true
echo "🖼  $(basename "$pick")"
