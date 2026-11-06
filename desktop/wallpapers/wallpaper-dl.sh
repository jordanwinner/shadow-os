#!/usr/bin/env bash
# Télécharge des fonds d'écran depuis Wallhaven (SFW uniquement) dans ~/Images/Wallpapers/<theme>
# usage : wallpaper-dl.sh <anime|hacker|both> [nombre]   (défaut : 10 par thème)
set -euo pipefail
DEST="${WALLPAPER_DIR:-$HOME/Images/Wallpapers}"
API="https://wallhaven.cc/api/v1/search"
RES="${WALLPAPER_RES:-2560x1440}"   # résolution minimale (qualité + beaucoup de résultats)

# thème -> "catégorie;mot-clé1|mot-clé2|..."  (une recherche par mot-clé ; vide = catégorie seule)
theme_spec() {
  case "$1" in
    anime)  echo "010; " ;;
    hacker) echo "100;cyberpunk|hacking|matrix|neon city|dark technology|server room|glitch art|hacker" ;;
    *) return 1 ;;
  esac
}

dl_theme() {
  local theme="$1" want="$2" spec cat kws dir got=0
  spec="$(theme_spec "$theme")" || { echo "thème inconnu: $theme"; return 1; }
  cat="${spec%%;*}"; kws="${spec#*;}"
  dir="$DEST/$theme"; mkdir -p "$dir"
  echo "⬇  $theme : objectif $want (min ${RES}) → $dir"
  local KW; IFS='|' read -ra KW <<< "$kws"
  for q in "${KW[@]}"; do
    [ "$got" -ge "$want" ] && break
    local page=1
    while [ "$got" -lt "$want" ] && [ "$page" -le 4 ]; do
      local urls
      urls=$(curl -s -m 20 --get "$API" \
        --data-urlencode "categories=$cat" --data-urlencode "purity=100" \
        --data-urlencode "atleast=$RES" --data-urlencode "sorting=random" \
        --data-urlencode "q=$q" --data-urlencode "page=$page" \
        | jq -r '.data[].path' 2>/dev/null)
      [ -z "$urls" ] && break
      local u f
      for u in $urls; do
        [ "$got" -ge "$want" ] && break
        f="$dir/$(basename "$u")"
        [ -f "$f" ] && continue
        if curl -s -m 60 -o "$f" "$u" && [ -s "$f" ]; then
          got=$((got+1)); printf "   [%d/%d] %s\n" "$got" "$want" "$(basename "$u")"
        else rm -f "$f"; fi
      done
      page=$((page+1))
    done
  done
  echo "✅ $theme : +$got — total dans le dossier : $(ls -1 "$dir" 2>/dev/null | wc -l)"
}

N="${2:-10}"
case "${1:-both}" in
  anime)  dl_theme anime  "$N" ;;
  hacker) dl_theme hacker "$N" ;;
  both)   dl_theme anime  "$N"; dl_theme hacker "$N" ;;
  *) echo "usage: wallpaper-dl.sh <anime|hacker|both> [nombre]"; exit 1 ;;
esac
