#!/usr/bin/env bash
# Shadow — session « Shadow » à l'écran de connexion (à lancer en root).
#
# Pourquoi : dans une session Ubuntu, les extensions de Shadow sont des extensions
# « utilisateur » : un seul réglage (disable-user-extensions) les coupe toutes et le
# bureau redevient un Ubuntu nu. Dans la session Shadow, elles sont déclarées par le
# MODE de GNOME Shell (comme le dock d'Ubuntu dans la session Ubuntu) : GNOME les
# charge toujours, quel que soit ce réglage.
#
#   installer-session.sh            installe la session (la session Ubuntu reste disponible)
#   installer-session.sh --retirer  retire tout
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "À lancer en root" >&2; exit 1; }
umask 022
ICI="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

MODE=/usr/share/gnome-shell/modes/shadow.json
SESSION_WL=/usr/share/wayland-sessions/shadow.desktop
SESSION_GS=/usr/share/gnome-session/sessions/shadow.session
CIBLE=/etc/systemd/user/gnome-session@shadow.target.d/shadow.session.conf
DONNEES=/usr/share/shadow
SCHEMA=/usr/share/glib-2.0/schemas/90_shadow-desktop.gschema.override

if [ "${1:-}" = --retirer ]; then
  rm -f "$MODE" "$SESSION_WL" "$SESSION_GS" "$CIBLE" "$SCHEMA"
  rmdir "$(dirname "$CIBLE")" 2>/dev/null || true
  [ -L "$DONNEES" ] && rm -f "$DONNEES"
  glib-compile-schemas /usr/share/glib-2.0/schemas
  echo "  ✓ session Shadow retirée (choisis « Ubuntu » à l'écran de connexion)"
  exit 0
fi

# 1. le mode de GNOME Shell : extensions obligatoires de Shadow
install -Dm644 "$ICI/shadow.json" "$MODE"

# 2. la session, proposée par l'écran de connexion
install -Dm644 /dev/stdin "$SESSION_WL" <<'EOF'
[Desktop Entry]
Name=Shadow
Comment=Shadow OS : le bureau Shadow, extensions intégrées au système
Exec=/usr/bin/gnome-session --session=shadow
TryExec=/usr/bin/gnome-session
Type=Application
DesktopNames=Shadow;GNOME
X-GDM-SessionRegisters=true
X-GDM-CanRunHeadless=true
EOF
install -Dm644 /dev/stdin "$SESSION_GS" <<'EOF'
[GNOME Session]
Name=Shadow
EOF
# gnome-session (systemd) : la cible de la session lance GNOME Shell en mode « shadow »
install -Dm644 /dev/stdin "$CIBLE" <<'EOF'
[Unit]
Requires=gnome-session-services.target
Requires=org.gnome.Shell@shadow.service
EOF

# 3. mêmes données de bureau que la session Ubuntu (applications par défaut…)
# (lien recréé s'il est cassé ; un vrai dossier existant n'est pas touché)
[ -d "$DONNEES" ] && [ ! -L "$DONNEES" ] || ln -sfn /usr/share/ubuntu "$DONNEES"

# 4. les réglages par défaut qu'Ubuntu réserve à son bureau valent aussi pour Shadow
#    (sections « [schéma:ubuntu] » recopiées en « [schéma:Shadow] »)
shopt -s nullglob
{
  echo "# Shadow OS — réglages par défaut d'Ubuntu, appliqués au bureau « Shadow » (généré)"
  for f in /usr/share/glib-2.0/schemas/*ubuntu*.gschema.override; do
    awk '/^\[/{garde = ($0 ~ /:ubuntu\]$/); if (garde) { sub(/:ubuntu\]$/, ":Shadow]"); print ""; } } garde' "$f"
  done
} > "$SCHEMA"
chmod 644 "$SCHEMA"
# compilation normale : --strict échouerait au moindre avertissement d'un AUTRE paquet
glib-compile-schemas /usr/share/glib-2.0/schemas >/dev/null 2>&1 || {
  # un schéma refusé ne doit jamais casser les réglages du système
  rm -f "$SCHEMA"; glib-compile-schemas /usr/share/glib-2.0/schemas
  echo "  ⚠ réglages par défaut d'Ubuntu non recopiés (schéma refusé)"
}
systemctl --global daemon-reload 2>/dev/null || true
echo "  ✓ session « Shadow » installée : choisis-la à l'écran de connexion (roue en bas à droite)"
# Filet de sécurité : dans cette session, GNOME ne peut plus couper ces extensions après un
# plantage (elles font partie du mode). Si une mise à jour en casse une, choisir « Ubuntu »
# à l'écran de connexion, puis « shadow docteur ».
