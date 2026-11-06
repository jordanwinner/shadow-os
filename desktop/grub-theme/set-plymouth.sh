#!/usr/bin/env bash
# Choisit le thème du splash de démarrage (Plymouth) et l'applique. NÉCESSITE sudo.
# usage : set-plymouth.sh [theme]        (défaut : mrrobot)
#   liste les thèmes : set-plymouth.sh --list
set -euo pipefail
THEME="${1:-mrrobot}"

if [ "$THEME" = "--list" ]; then
    echo "Thèmes Plymouth disponibles :"
    ls /usr/share/plymouth/themes 2>/dev/null | grep -vE '\.plymouth$'
    exit 0
fi

PLY="/usr/share/plymouth/themes/$THEME/$THEME.plymouth"
[ -f "$PLY" ] || { echo "thème « $THEME » introuvable ($PLY). Essaie : $0 --list"; exit 1; }

echo "▸ Sélection du thème : $THEME"
sudo update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth "$PLY" 100
sudo update-alternatives --set default.plymouth "$PLY"

echo "▸ Reconstruction de l'initramfs (peut prendre ~30 s)"
sudo update-initramfs -u

echo
echo "✓ Splash « $THEME » appliqué. Visible au prochain démarrage."
echo "  Changer : $0 <autre-theme>   ·   liste : $0 --list"
