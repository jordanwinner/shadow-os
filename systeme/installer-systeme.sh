#!/usr/bin/env bash
# Shadow — installe l'identité au niveau système (à lancer avec sudo) :
#   1. GRUB      : thème « Éclipse », entrées nommées « Shadow », 1920×1080
#   2. Plymouth  : animation de démarrage Shadow (+ initramfs)
#   3. Connexion : fond Éclipse + logo Shadow sur l'écran de connexion (GDM)
#   4. À propos  : « Shadow (base Ubuntu …) » + logo dans Réglages › À propos
# Tout est sauvegardé dans /var/backups/shadow-os ; annuler : desinstaller-systeme.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "À lancer avec sudo : sudo $0" >&2; exit 1; }
# sudo peut hériter d'un umask strict (027) : les fichiers système doivent rester
# lisibles par gdm et les autres utilisateurs.
umask 022

ICI="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
RACINE="$(dirname "$ICI")"
SAUV=/var/backups/shadow-os
mkdir -p "$SAUV"
ok(){ printf '  \033[32m✓\033[0m %s\n' "$*"; }
titre(){ printf '\033[1;35m▸ %s\033[0m\n' "$*"; }

# ── 0. fichiers communs ─────────────────────────────────────────────────────
FOND="$RACINE/identite/rendus/fond-eclipse.png"
[ -f "$FOND" ] || FOND="$(getent passwd "${SUDO_USER:-root}" | cut -d: -f6)/.local/share/backgrounds/shadow/eclipse.png"
[ -f "$FOND" ] || { echo "fond Éclipse introuvable : lance d'abord scripts/rendre-svg.sh" >&2; exit 1; }
install -Dm644 "$FOND" /usr/share/backgrounds/shadow/eclipse.png
install -Dm644 "$RACINE/identite/logo.svg" /usr/share/icons/hicolor/scalable/apps/shadow-os.svg
install -Dm644 "$RACINE/identite/icones/shadow-symbolic.svg" /usr/share/icons/hicolor/symbolic/apps/shadow-os-symbolic.svg
gtk-update-icon-cache -q -f /usr/share/icons/hicolor 2>/dev/null || true

# ── 1. GRUB ─────────────────────────────────────────────────────────────────
titre "GRUB"
[ -f "$SAUV/grub-default.orig" ] || command cp -a /etc/default/grub "$SAUV/grub-default.orig"
rm -rf /boot/grub/themes/shadow-eclipse
install -d /boot/grub/themes/shadow-eclipse
install -m644 "$ICI"/grub/shadow/* /boot/grub/themes/shadow-eclipse/
install -Dm644 /dev/stdin /etc/default/grub.d/99-shadow.cfg <<'EOF'
# Shadow OS — surcharge GRUB (retirer ce fichier puis update-grub pour annuler)
GRUB_DISTRIBUTOR="Shadow"
GRUB_THEME="/boot/grub/themes/shadow-eclipse/theme.txt"
GRUB_GFXMODE="1920x1080,auto"
GRUB_GFXPAYLOAD_LINUX="keep"
EOF
update-grub 2>&1 | grep -vE "^(Sourcing|Generating|Found|Adding|done)" || true
ok "thème GRUB Éclipse, entrées « Shadow »"

# ── 2. Plymouth ─────────────────────────────────────────────────────────────
titre "Démarrage (Plymouth)"
[ -f "$SAUV/plymouth.orig" ] || readlink -f /etc/alternatives/default.plymouth > "$SAUV/plymouth.orig"
install -d /usr/share/plymouth/themes/shadow
install -m644 "$ICI"/plymouth/shadow/* /usr/share/plymouth/themes/shadow/
update-alternatives --install /usr/share/plymouth/themes/default.plymouth default.plymouth \
  /usr/share/plymouth/themes/shadow/shadow.plymouth 150 >/dev/null
update-alternatives --set default.plymouth /usr/share/plymouth/themes/shadow/shadow.plymouth >/dev/null
echo "  … reconstruction de l'initramfs (≈ 30 s)"
update-initramfs -u >/dev/null 2>&1
ok "animation Shadow (ancien thème : $(basename "$(cat "$SAUV/plymouth.orig")" .plymouth))"

# ── 3. Écran de connexion ───────────────────────────────────────────────────
titre "Écran de connexion"
install -Dm644 "$ICI/gdm/logo-connexion.png" /usr/share/pixmaps/shadow-os-connexion.png
install -d /etc/dconf/db/gdm.d /etc/dconf/profile
if [ ! -f /etc/dconf/profile/gdm ]; then
  printf 'user-db:user\nsystem-db:gdm\nfile-db:/usr/share/gdm/greeter-dconf-defaults\n' > /etc/dconf/profile/gdm
  touch "$SAUV/profil-gdm-cree"
fi
rm -f /etc/dconf/db/gdm.d/90-shadow   # ancien nom (lu avant gdm-settings)
cat > /etc/dconf/db/gdm.d/99-shadow <<'EOF'
# Shadow OS — écran de connexion
[com/ubuntu/login-screen]
background-picture-uri='file:///usr/share/backgrounds/shadow/eclipse.png'
background-size='cover'
background-color='#07070B'

[org/gnome/login-screen]
logo='/usr/share/pixmaps/shadow-os-connexion.png'

[org/gnome/desktop/interface]
color-scheme='prefer-dark'
accent-color='purple'
EOF
dconf update
chmod 644 /etc/dconf/db/gdm.d/99-shadow /etc/dconf/db/gdm
ok "fond Éclipse + logo Shadow (visible à la prochaine déconnexion)"

# ── 4. Nom du système (Réglages › À propos) ────────────────────────────────
titre "Nom du système"
if [ ! -f "$SAUV/os-release.lien" ]; then
  if [ -L /etc/os-release ]; then readlink /etc/os-release > "$SAUV/os-release.lien"
  else command cp -a /etc/os-release "$SAUV/os-release.fichier"; echo "" > "$SAUV/os-release.lien"; fi
fi
base_pretty=$(. /usr/lib/os-release; echo "$PRETTY_NAME")
tmp=$(mktemp)
grep -vE '^(PRETTY_NAME|LOGO)=' /usr/lib/os-release > "$tmp"
{ echo "PRETTY_NAME=\"Shadow (base $base_pretty)\""; echo "LOGO=shadow-os"; cat "$tmp"; } > /etc/os-release.shadow
rm -f "$tmp"; chmod 644 /etc/os-release.shadow
mv -f /etc/os-release.shadow /etc/os-release
ok "« Shadow (base $base_pretty) » — ID=ubuntu conservé (apt et les outils Ubuntu ne voient pas de différence)"

# ── 4b. logo de Réglages › À propos (Ubuntu le charge en dur depuis /usr/share/pixmaps) ──
for v in "ubuntu-logo-text-dark.svg:sombre" "ubuntu-logo-text.svg:clair"; do
  f="/usr/share/pixmaps/${v%%:*}"
  if ! dpkg-divert --list "$f" | grep -q shadow; then
    command cp -a "$f" "$f.ubuntu"
    dpkg-divert --package shadow-os --no-rename --divert "$f.ubuntu" --add "$f" >/dev/null
  fi
  install -m644 "$ICI/a-propos/shadow-logo-texte-${v##*:}.svg" "$f"
done
ok "logo Shadow dans Réglages › À propos (originaux mis de côté par dpkg-divert)"

# ── 5. droits : tout ce que Shadow installe doit être lisible ──────────────
chmod 755 /usr/share/backgrounds/shadow /usr/share/plymouth/themes/shadow /boot/grub/themes/shadow-eclipse
chmod 644 /usr/share/backgrounds/shadow/eclipse.png /usr/share/pixmaps/shadow-os-connexion.png \
  /usr/share/plymouth/themes/shadow/* /boot/grub/themes/shadow-eclipse/* /etc/default/grub.d/99-shadow.cfg /etc/os-release
ok "droits vérifiés (lisibles par gdm)"

echo
printf '\033[1;35m✓ Shadow est installé au niveau système.\033[0m Redémarre pour voir GRUB et l’animation.\n'
echo "  Annuler : sudo $ICI/desinstaller-systeme.sh"
