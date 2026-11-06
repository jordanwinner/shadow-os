#!/usr/bin/env bash
# shadow mode — bascule le bureau entre « flottant » (façon macOS) et « tuiles » (façon Omarchy).
#   shadow mode [flottant|tuiles|bascule|etat|restaurer]
# S'appuie sur Tiling Shell. Aucun sudo. Les réglages d'origine sont sauvegardés au premier
# lancement dans ~/.local/state/shadow-os/ et `restaurer` les remet.
set -euo pipefail

ETAT_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/shadow-os"
ETAT="$ETAT_DIR/mode"
ORIGINE="$ETAT_DIR/mode-origine.txt"
TS_EXT="$HOME/.local/share/gnome-shell/extensions/tilingshell@ferrarodomenico.com"
TS=(gsettings --schemadir "$TS_EXT/schemas")
TSS=org.gnome.shell.extensions.tilingshell
WM=org.gnome.desktop.wm.keybindings
ICONE=shadow-os
DIRS=(left right up down)
Dirs=(Left Right Up Down)

die(){ printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
[ -d "$TS_EXT/schemas" ] || die "Tiling Shell introuvable ($TS_EXT)"

# clés touchées, au format « schéma|clé »
cles(){
  for k in enable-autotiling enable-window-border; do echo "ts|$k"; done
  for d in "${DIRS[@]}"; do echo "ts|focus-window-$d"; echo "ts|move-window-$d"; echo "wm|move-to-monitor-$d"; done
}
lire(){ case "$1" in ts) "${TS[@]}" get $TSS "$2";; wm) gsettings get $WM "$2";; esac; }
ecrire(){ case "$1" in ts) "${TS[@]}" set $TSS "$2" "$3";; wm) gsettings set $WM "$2" "$3";; esac; }

sauver_origine(){
  [ -s "$ORIGINE" ] && return 0
  mkdir -p "$ETAT_DIR"
  { echo "# réglages avant le premier « shadow mode » — $(date '+%F %T')"
    cles | while IFS='|' read -r s k; do printf '%s|%s|%s\n' "$s" "$k" "$(lire "$s" "$k")"; done
  } > "$ORIGINE"
}

notifier(){ # titre, corps
  command -v notify-send >/dev/null || return 0
  notify-send -a Shadow -i "$ICONE" -t 2200 -e \
    -h string:x-canonical-private-synchronous:shadow-mode "$1" "$2" 2>/dev/null || true
}

mode_flottant(){
  sauver_origine
  ecrire ts enable-autotiling false
  ecrire ts enable-window-border false
  for i in 0 1 2 3; do
    ecrire ts "focus-window-${DIRS[i]}" "['']"
    ecrire ts "move-window-${DIRS[i]}" "['<Super>${Dirs[i]}']"
    ecrire wm "move-to-monitor-${DIRS[i]}" "['<Super><Shift>${Dirs[i]}']"
  done
  echo flottant > "$ETAT"
  notifier "Mode flottant" "Fenêtres libres · Super+flèches pour les ancrer"
}

mode_tuiles(){
  sauver_origine
  ecrire ts enable-autotiling true
  ecrire ts enable-window-border true
  for i in 0 1 2 3; do
    ecrire wm "move-to-monitor-${DIRS[i]}" "@as []"
    ecrire ts "move-window-${DIRS[i]}" "['<Super><Shift>${Dirs[i]}']"
    ecrire ts "focus-window-${DIRS[i]}" "['<Super>${Dirs[i]}']"
  done
  echo tuiles > "$ETAT"
  notifier "Mode tuiles" "Rangement auto · Super+flèches : focus · Super+Maj+flèches : déplacer"
}

mode_courant(){
  if [ -s "$ETAT" ]; then cat "$ETAT"
  elif [ "$(lire ts enable-autotiling)" = true ]; then echo tuiles
  else echo flottant; fi
}

restaurer(){
  [ -s "$ORIGINE" ] || die "aucune sauvegarde d'origine ($ORIGINE)"
  grep -v '^#' "$ORIGINE" | while IFS='|' read -r s k v; do ecrire "$s" "$k" "$v"; done
  rm -f "$ETAT"
  echo "Réglages d'origine restaurés."
}

case "${1:-bascule}" in
  flottant|float|floating) mode_flottant; echo "Mode flottant" ;;
  tuiles|tile|tiling)      mode_tuiles;   echo "Mode tuiles" ;;
  bascule|toggle)          if [ "$(mode_courant)" = tuiles ]; then mode_flottant; echo "Mode flottant"; else mode_tuiles; echo "Mode tuiles"; fi ;;
  etat|status)             mode_courant ;;
  restaurer|restore)       restaurer ;;
  *) echo "usage : shadow mode [flottant|tuiles|bascule|etat|restaurer]"; exit 1 ;;
esac
