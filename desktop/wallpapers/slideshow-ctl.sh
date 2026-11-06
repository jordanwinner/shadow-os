#!/usr/bin/env bash
# Pilote le diaporama de fonds d'écran.
# usage : slideshow-ctl.sh <on|off|toggle|status|interval MINUTES>
set -euo pipefail
U="$HOME/.config/systemd/user"
case "${1:-status}" in
  on)   systemctl --user enable --now slideshow.timer; echo "Diaporama activé." ;;
  off)  systemctl --user disable --now slideshow.timer; echo "Diaporama désactivé." ;;
  toggle)
    if systemctl --user is-active --quiet slideshow.timer; then
      systemctl --user disable --now slideshow.timer; echo "Diaporama désactivé."
    else
      systemctl --user enable --now slideshow.timer; echo "Diaporama activé."
    fi ;;
  status) systemctl --user status slideshow.timer --no-pager 2>/dev/null | head -4 || echo "non installé" ;;
  interval)
    min="${2:?minutes ?}"
    sed -i "s/^OnUnitActiveSec=.*/OnUnitActiveSec=${min}min/" "$U/slideshow.timer"
    systemctl --user daemon-reload; systemctl --user restart slideshow.timer
    echo "Intervalle réglé sur ${min} min." ;;
  *) echo "usage: slideshow-ctl.sh <on|off|toggle|status|interval MINUTES>"; exit 1 ;;
esac
