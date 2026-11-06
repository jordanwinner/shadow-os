#!/usr/bin/env bash
# Shadow — construit un dépôt APT signé à partir des .deb de paquet/sortie/.
# Aucune dépendance exotique : apt-ftparchive + dpkg-scanpackages + gpg.
# Sortie : depot/sortie/  (pool + dists signés + clé publique). Pas de sudo.
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(dirname "$ICI")"
DEBS="$RACINE/paquet/sortie"
OUT="$ICI/sortie"
GNUPGHOME="$ICI/.gnupg"          # trousseau dédié, gitignoré
SUITE="shadow"
COMPOSANT="main"
ARCH="amd64"                     # les paquets sont 'all' → listés dans binary-amd64
ORIGINE="Shadow OS"
LABEL="Shadow OS"
SIGN_UID="Shadow OS Archive Signing Key <shadow-os@users.noreply.github.com>"
KEYRING_PUB="$OUT/shadow-os-archive-keyring.gpg"

C_OK=$'\033[32m'; C_T=$'\033[1;35m'; C_WARN=$'\033[33m'; C_RST=$'\033[0m'
titre(){ printf '\n%s▸ %s%s\n' "$C_T" "$*" "$C_RST"; }
ok(){ printf '  %s✓%s %s\n' "$C_OK" "$C_RST" "$*"; }
avert(){ printf '  %s⚠%s %s\n' "$C_WARN" "$C_RST" "$*"; }

ls "$DEBS"/*.deb >/dev/null 2>&1 || { echo "Aucun .deb dans $DEBS — lance d'abord paquet/construire.sh"; exit 1; }

# ── 1) clé de signature dédiée (créée une seule fois) ───────────────────────
titre "Clé de signature Shadow"
mkdir -p "$GNUPGHOME"; chmod 700 "$GNUPGHOME"
export GNUPGHOME
if gpg --list-secret-keys "$SIGN_UID" >/dev/null 2>&1; then
  ok "clé déjà présente"
else
  cat > "$GNUPGHOME/gen" <<EOF
%no-protection
Key-Type: RSA
Key-Length: 3072
Name-Real: Shadow OS Archive Signing Key
Name-Email: shadow-os@users.noreply.github.com
Expire-Date: 0
%commit
EOF
  gpg --batch --quiet --gen-key "$GNUPGHOME/gen"
  rm -f "$GNUPGHOME/gen"
  ok "clé générée (trousseau local $GNUPGHOME)"
fi
KEYID="$(gpg --list-secret-keys --with-colons "$SIGN_UID" | awk -F: '/^sec:/{print $5; exit}')"

# ── 2) pool + index ─────────────────────────────────────────────────────────
titre "Arborescence du dépôt"
rm -rf "$OUT"; mkdir -p "$OUT/pool/$COMPOSANT/s/shadow-os" "$OUT/dists/$SUITE/$COMPOSANT/binary-$ARCH"
cp "$DEBS"/*.deb "$OUT/pool/$COMPOSANT/s/shadow-os/"
ok "paquets copiés dans pool/$COMPOSANT/s/shadow-os/"

cd "$OUT"
dpkg-scanpackages --arch "$ARCH" "pool/$COMPOSANT" /dev/null > "dists/$SUITE/$COMPOSANT/binary-$ARCH/Packages" 2>/dev/null
gzip -9kf "dists/$SUITE/$COMPOSANT/binary-$ARCH/Packages"
ok "index Packages (+ .gz) généré"

# ── 3) Release + signatures ─────────────────────────────────────────────────
titre "Fichier Release (signé)"
cat > "$OUT/aptftp.conf" <<EOF
APT::FTPArchive::Release::Origin "$ORIGINE";
APT::FTPArchive::Release::Label "$LABEL";
APT::FTPArchive::Release::Suite "$SUITE";
APT::FTPArchive::Release::Codename "$SUITE";
APT::FTPArchive::Release::Architectures "$ARCH";
APT::FTPArchive::Release::Components "$COMPOSANT";
APT::FTPArchive::Release::Description "Dépôt APT de Shadow OS";
EOF
apt-ftparchive -c "$OUT/aptftp.conf" release "dists/$SUITE" > "dists/$SUITE/Release"
rm -f "$OUT/aptftp.conf"
gpg --default-key "$KEYID" --batch --yes -abo "dists/$SUITE/Release.gpg" "dists/$SUITE/Release"
gpg --default-key "$KEYID" --batch --yes --clearsign -o "dists/$SUITE/InRelease" "dists/$SUITE/Release"
ok "Release signé (Release.gpg + InRelease)"

# ── 4) clé publique pour les clients ────────────────────────────────────────
gpg --export "$KEYID" > "$KEYRING_PUB"
gpg --export --armor "$KEYID" > "${KEYRING_PUB%.gpg}.asc"
ok "clé publique exportée : $(basename "$KEYRING_PUB")"

# ── récapitulatif ─────────────────────────────────────────────────────────
titre "Dépôt prêt"
echo "  Racine : $OUT"
echo "  Empreinte clé : $KEYID"
echo
echo "  Pour l'utiliser en local :"
echo "    sudo $ICI/ajouter-depot.sh \"file:$OUT\""
echo "  Ou publié sur une URL (GitHub Pages, serveur…) :"
echo "    sudo $ICI/ajouter-depot.sh \"https://<ton-domaine>/shadow\""
echo "  Puis : sudo apt update && sudo apt install shadow-os"
