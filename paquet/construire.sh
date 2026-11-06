#!/usr/bin/env bash
# Shadow — construit les paquets Debian shadow-os-desktop et shadow-os (méta).
# Sortie : paquet/sortie/*.deb   (pas de sudo requis).
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(dirname "$ICI")"
CTRL="$ICI/controle"
OUT="$ICI/sortie"
VERSION="${1:-$(cat "$ICI/VERSION" 2>/dev/null || echo 1.0.0)}"

C_OK=$'\033[32m'; C_T=$'\033[1;35m'; C_RST=$'\033[0m'
titre(){ printf '%s▸ %s%s\n' "$C_T" "$*" "$C_RST"; }
ok(){ printf '  %s✓%s %s\n' "$C_OK" "$C_RST" "$*"; }

command -v dpkg-deb >/dev/null 2>&1 || { echo "dpkg-deb requis (apt install dpkg-dev)"; exit 1; }

rm -rf "$OUT/build"; mkdir -p "$OUT/build"

# ── 1) shadow-os-desktop ────────────────────────────────────────────────────
titre "Assemblage de shadow-os-desktop $VERSION"
PKG="$OUT/build/shadow-os-desktop"
CHARGE="$PKG/usr/share/shadow-os"
mkdir -p "$PKG/DEBIAN" "$CHARGE" "$PKG/usr/bin"

# charge utile : on copie les dossiers utiles du dépôt, sans rendus/ ni caches
for d in theme extension scripts terminal apps identite systeme ulauncher; do
  [ -d "$RACINE/$d" ] || continue
  cp -r "$RACINE/$d" "$CHARGE/"
done
cp "$RACINE/installer.sh" "$CHARGE/"
cp "$RACINE/README.md" "$CHARGE/" 2>/dev/null || true
# purge des éléments non distribuables
find "$CHARGE" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
rm -rf "$CHARGE/identite/rendus" 2>/dev/null || true
find "$CHARGE" -type f -name '*.pyc' -delete 2>/dev/null || true

# commande d'activation par compte
install -m 0755 "$CTRL/shadow-os.bin" "$PKG/usr/bin/shadow-os"

# métadonnées
SIZE=$(du -sk "$PKG/usr" | cut -f1)
sed -e "s/@VERSION@/$VERSION/g" -e "s/@SIZE@/$SIZE/g" "$CTRL/shadow-os-desktop.control" > "$PKG/DEBIAN/control"
install -m 0755 "$CTRL/shadow-os-desktop.postinst" "$PKG/DEBIAN/postinst"
install -m 0755 "$CTRL/shadow-os-desktop.prerm"    "$PKG/DEBIAN/prerm"
# permissions saines sur toute la charge utile
find "$PKG/usr/share/shadow-os" -type d -exec chmod 0755 {} +
find "$PKG/usr/share/shadow-os" -type f -exec chmod 0644 {} +
for f in installer.sh theme/eclipse.sh theme/icones.sh theme/applis.py scripts/shadow-mode.sh \
         scripts/rendre-svg.sh scripts/logo-ansi.py apps/bienvenue/bienvenue.py \
         systeme/installer-systeme.sh systeme/desinstaller-systeme.sh; do
  [ -f "$CHARGE/$f" ] && chmod 0755 "$CHARGE/$f"
done
chmod 0755 "$PKG/DEBIAN" "$PKG/usr" "$PKG/usr/bin" "$PKG/usr/share"
dpkg-deb --root-owner-group --build "$PKG" "$OUT/shadow-os-desktop_${VERSION}_all.deb" >/dev/null
ok "shadow-os-desktop_${VERSION}_all.deb (${SIZE} Ko)"

# ── 2) shadow-os (méta) ─────────────────────────────────────────────────────
titre "Assemblage de shadow-os (méta) $VERSION"
META="$OUT/build/shadow-os"
mkdir -p "$META/DEBIAN"
sed -e "s/@VERSION@/$VERSION/g" "$CTRL/shadow-os.control" > "$META/DEBIAN/control"
chmod 0755 "$META/DEBIAN"
dpkg-deb --root-owner-group --build "$META" "$OUT/shadow-os_${VERSION}_all.deb" >/dev/null
ok "shadow-os_${VERSION}_all.deb"

# ── vérifs ──────────────────────────────────────────────────────────────────
titre "Vérification"
for deb in "$OUT"/*.deb; do
  dpkg-deb --info "$deb" >/dev/null && ok "structure OK : $(basename "$deb")"
done
if command -v lintian >/dev/null 2>&1; then
  lintian --no-tag-display-limit "$OUT"/*.deb 2>&1 | head -20 || true
else
  printf '  (lintian absent : vérification de style ignorée)\n'
fi
echo
echo "Paquets dans : $OUT"
echo "Test : sudo apt install $OUT/shadow-os_${VERSION}_all.deb"
