#!/usr/bin/env bash
# shadow mode — bascule le bureau entre « flottant » (façon macOS) et « tuiles » (façon Omarchy).
#   shadow mode [flottant|tuiles|bascule|etat|restaurer]
#
# Le rangement en tuiles est fait par l'extension Shadow elle-même (tuiles.js) :
#   flottant : fenêtres libres ; Super+←/→ les cale sur une moitié d'écran, Super+↑ agrandit ;
#   tuiles   : les fenêtres se rangent seules ; Super+flèches change de fenêtre,
#              Super+Maj+flèches en échange deux.
# Aucun sudo. `restaurer` remet les raccourcis d'origine de GNOME.
set -euo pipefail

ETAT_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/shadow-os"
ETAT="$ETAT_DIR/mode"
EXT="$HOME/.local/share/gnome-shell/extensions/shadow-os@jordan"
SO=(gsettings --schemadir "$EXT/schemas")
SOS=org.gnome.shell.extensions.shadow-os
WM=org.gnome.desktop.wm.keybindings
MK=org.gnome.mutter.keybindings
ICONE=shadow-os
DIRS=(left right up down)
Dirs=(Left Right Up Down)

die(){ printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }
[ -d "$EXT/schemas" ] || die "extension Shadow introuvable ($EXT)"

notifier(){ # titre, corps (muet si SHADOW_MODE_SILENCE=1 : les Modes Shadow annoncent eux-mêmes)
  [ "${SHADOW_MODE_SILENCE:-0}" = 1 ] && return 0
  command -v notify-send >/dev/null || return 0
  notify-send -a Shadow -i "$ICONE" -t 2200 -e \
    -h string:x-canonical-private-synchronous:shadow-mode "$1" "$2" 2>/dev/null || true
}

mode_flottant(){
  "${SO[@]}" set $SOS tuiles false
  gsettings set org.gnome.mutter edge-tiling true
  gsettings set $MK toggle-tiled-left "['<Super>Left']"
  gsettings set $MK toggle-tiled-right "['<Super>Right']"
  gsettings set $WM maximize "['<Super>Up']"
  gsettings set $WM unmaximize "['<Super>Down']"
  for i in 0 1 2 3; do
    gsettings set $WM "move-to-monitor-${DIRS[i]}" "['<Super><Shift>${Dirs[i]}']"
  done
  mkdir -p "$ETAT_DIR"; echo flottant > "$ETAT"
  notifier "Mode flottant" "Fenêtres libres · Super+flèches pour les caler ou les agrandir"
}

mode_tuiles(){
  # les raccourcis de GNOME sur Super+flèches sont libérés pour le moteur de tuiles
  gsettings set org.gnome.mutter edge-tiling false
  gsettings set $MK toggle-tiled-left "@as []"
  gsettings set $MK toggle-tiled-right "@as []"
  gsettings set $WM maximize "@as []"
  gsettings set $WM unmaximize "@as []"
  for i in 0 1 2 3; do
    gsettings set $WM "move-to-monitor-${DIRS[i]}" "@as []"
  done
  "${SO[@]}" set $SOS tuiles true
  mkdir -p "$ETAT_DIR"; echo tuiles > "$ETAT"
  notifier "Mode tuiles" "Rangement auto · Super+flèches : fenêtre voisine · Super+Maj+flèches : échanger"
}

mode_courant(){
  if [ "$("${SO[@]}" get $SOS tuiles 2>/dev/null)" = true ]; then echo tuiles; else echo flottant; fi
}

restaurer(){
  "${SO[@]}" reset $SOS tuiles
  gsettings reset org.gnome.mutter edge-tiling
  gsettings reset $MK toggle-tiled-left; gsettings reset $MK toggle-tiled-right
  gsettings reset $WM maximize; gsettings reset $WM unmaximize
  for d in "${DIRS[@]}"; do gsettings reset $WM "move-to-monitor-$d"; done
  rm -f "$ETAT"
  echo "Raccourcis d'origine de GNOME restaurés."
}

case "${1:-bascule}" in
  flottant|float|floating) mode_flottant; echo "Mode flottant" ;;
  tuiles|tile|tiling)      mode_tuiles;   echo "Mode tuiles" ;;
  bascule|toggle)          if [ "$(mode_courant)" = tuiles ]; then mode_flottant; echo "Mode flottant"; else mode_tuiles; echo "Mode tuiles"; fi ;;
  etat|status)             mode_courant ;;
  restaurer|restore)       restaurer ;;
  *) echo "usage : shadow mode [flottant|tuiles|bascule|etat|restaurer]"; exit 1 ;;
esac
