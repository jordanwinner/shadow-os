#!/usr/bin/env bash
# Shadow — annule installer-systeme.sh à partir des sauvegardes de /var/backups/shadow-os.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "À lancer avec sudo : sudo $0" >&2; exit 1; }
SAUV=/var/backups/shadow-os
ok(){ printf '  \033[32m✓\033[0m %s\n' "$*"; }

rm -f /etc/default/grub.d/99-shadow.cfg
update-grub >/dev/null 2>&1 && ok "GRUB : réglages d'avant Shadow"

if [ -f "$SAUV/plymouth.orig" ] && [ -f "$(cat "$SAUV/plymouth.orig")" ]; then
  update-alternatives --set default.plymouth "$(cat "$SAUV/plymouth.orig")" >/dev/null
  update-initramfs -u >/dev/null 2>&1
  ok "Plymouth : $(basename "$(cat "$SAUV/plymouth.orig")" .plymouth) rétabli"
fi

rm -f /etc/dconf/db/gdm.d/90-shadow
[ -f "$SAUV/profil-gdm-cree" ] && rm -f /etc/dconf/profile/gdm "$SAUV/profil-gdm-cree"
dconf update && ok "écran de connexion d'origine"

if [ -f "$SAUV/os-release.lien" ]; then
  lien=$(cat "$SAUV/os-release.lien")
  if [ -n "$lien" ]; then ln -sfn "$lien" /etc/os-release
  else command cp -a "$SAUV/os-release.fichier" /etc/os-release; fi
  ok "os-release d'origine"
fi
echo "Les fichiers Shadow (/boot/grub/themes/shadow-eclipse, /usr/share/plymouth/themes/shadow) restent en place, inactifs."
