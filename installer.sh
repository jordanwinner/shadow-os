#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Shadow — installateur                                                     ║
# ║  Réapplique tout l'environnement Shadow sur une machine Ubuntu/Debian +    ║
# ║  GNOME : extensions, thème Éclipse, grille, scripts, terminal, apps.       ║
# ║  Modules optionnels : système (GRUB/Plymouth/login), arsenal Kali, bureau  ║
# ║  shadow-desktop (îlot, conky, fonds).                                      ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
#   ./installer.sh                 modules utilisateur (sans sudo lourd)
#   ./installer.sh --avec-systeme  + GRUB/Plymouth/écran de connexion (sudo)
#   ./installer.sh --avec-arsenal  + box Kali (distrobox, long)
#   ./installer.sh --avec-desktop  + îlot/conky/fonds (shadow-desktop)
#   ./installer.sh --tout          tout ce qui précède
#   ./installer.sh --seulement theme,applis   un ou plusieurs modules précis
#   ./installer.sh --sans extensions           en retirer
#   ./installer.sh --simuler       montre ce qui serait fait, ne fait rien
#   ./installer.sh --liste         liste les modules
#   ./installer.sh --help
#
set -euo pipefail

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_REPO="${SHADOW_DESKTOP_REPO:-$HOME/Dev/shadow-desktop}"
BIN="$HOME/.local/bin"
EXT_BASE="$HOME/.local/share/gnome-shell/extensions"
ETAT="${XDG_STATE_HOME:-$HOME/.local/state}/shadow-os"

# ── extensions GNOME tierces (extensions.gnome.org), par UUID ───────────────
EGO_EXT=(
  dash-to-dock@micxgx.gmail.com
  just-perfection-desktop@just-perfection
  caffeine@patapon.info
  blur-my-shell@aunetx
  tilingshell@ferrarodomenico.com
  space-bar@luchrioh
  logomenu@aryan_k
  rounded-window-corners@fxgn
  compiz-alike-magic-lamp-effect@hermes83.github.com
)
# fournies par un paquet apt plutôt que par EGO
APT_EXT_PKG="gnome-shell-extensions"   # user-theme@…
# dépendances système (apt)
APT_DEPS=(
  git curl wget jq python3 python3-gi gettext dconf-cli
  gnome-shell-extension-manager gnome-tweaks
  gnome-terminal fonts-inter papirus-icon-theme
)

# ── couleurs / log ──────────────────────────────────────────────────────────
C_T=$'\033[1;35m'; C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_ERR=$'\033[31m'; C_DIM=$'\033[2m'; C_RST=$'\033[0m'
SIMULER=0
titre(){ printf '\n%s▸ %s%s\n' "$C_T" "$*" "$C_RST"; }
ok(){ printf '  %s✓%s %s\n' "$C_OK" "$C_RST" "$*"; }
avert(){ printf '  %s⚠%s %s\n' "$C_WARN" "$C_RST" "$*"; }
info(){ printf '  %s%s%s\n' "$C_DIM" "$*" "$C_RST"; }
err(){ printf '%s✗ %s%s\n' "$C_ERR" "$*" "$C_RST" >&2; }
mort(){ err "$*"; exit 1; }
# exécute, ou affiche seulement si --simuler
faire(){ if [ "$SIMULER" = 1 ]; then printf '  %s[simulation]%s %s\n' "$C_DIM" "$C_RST" "$*"; else eval "$@"; fi; }

# ── détection de l'environnement ────────────────────────────────────────────
GSHELL_VER=""
verifier(){
  titre "Vérification de l'environnement"
  . /etc/os-release 2>/dev/null || true
  info "système : ${PRETTY_NAME:-inconnu}"
  case "${ID:-}${ID_LIKE:-}" in
    *debian*|*ubuntu*) ok "base Debian/Ubuntu détectée" ;;
    *) avert "distribution non Debian/Ubuntu : certains modules (apt, système) risquent d'échouer" ;;
  esac
  if command -v gnome-shell >/dev/null 2>&1; then
    GSHELL_VER="$(gnome-shell --version | grep -oE '[0-9]+\.[0-9]+' | head -1)"
    ok "GNOME Shell $GSHELL_VER"
  else
    avert "GNOME Shell introuvable : les extensions et le thème shell ne s'appliqueront pas"
  fi
  [ -d "$RACINE/theme" ] || mort "lancé hors du dépôt Shadow ($RACINE/theme manquant)"
}

a_sudo(){ command -v sudo >/dev/null 2>&1; }

# ── MODULE prerequis : paquets apt ──────────────────────────────────────────
mod_prerequis(){
  titre "Prérequis (paquets système)"
  if ! command -v apt-get >/dev/null 2>&1; then avert "apt absent : prérequis ignorés"; return 0; fi
  local manquants=()
  for p in "${APT_DEPS[@]}" "$APT_EXT_PKG"; do
    dpkg -s "$p" >/dev/null 2>&1 || manquants+=("$p")
  done
  if [ "${#manquants[@]}" -eq 0 ]; then ok "tous les paquets requis sont déjà là"; return 0; fi
  info "à installer : ${manquants[*]}"
  faire "sudo apt-get update -qq"
  faire "sudo apt-get install -y ${manquants[*]}"
  ok "prérequis installés"
}

# ── MODULE extensions : EGO + locales ───────────────────────────────────────
ego_installer(){                       # $1 = uuid
  local uuid="$1"
  if gnome-extensions info "$uuid" >/dev/null 2>&1; then info "déjà présent : $uuid"; return 0; fi
  [ -n "$GSHELL_VER" ] || { avert "version de shell inconnue : $uuid non installé"; return 1; }
  local url tmp
  url="$(curl -fsSL "https://extensions.gnome.org/extension-info/?uuid=${uuid}&shell_version=${GSHELL_VER}" 2>/dev/null \
        | python3 -c 'import sys,json;
try:
  d=json.load(sys.stdin); print("https://extensions.gnome.org"+d["download_url"])
except Exception: pass' 2>/dev/null)"
  [ -n "$url" ] || { avert "$uuid : pas de version pour GNOME $GSHELL_VER sur extensions.gnome.org"; return 1; }
  tmp="$(mktemp --suffix=.zip)"
  if faire "curl -fsSL '$url' -o '$tmp'" && faire "gnome-extensions install --force '$tmp'"; then
    ok "installé : $uuid"
  else
    avert "échec d'installation : $uuid"
  fi
  rm -f "$tmp"
}

mod_extensions(){
  titre "Extensions GNOME"
  command -v gnome-extensions >/dev/null 2>&1 || { avert "gnome-extensions absent : module ignoré"; return 0; }
  for u in "${EGO_EXT[@]}"; do ego_installer "$u"; done
  # extension locale Shadow : lien symbolique vers le dépôt
  faire "mkdir -p '$EXT_BASE'"
  if [ -d "$RACINE/extension/shadow-os@jordan" ]; then
    faire "ln -sfn '$RACINE/extension/shadow-os@jordan' '$EXT_BASE/shadow-os@jordan'"
    faire "glib-compile-schemas '$RACINE/extension/shadow-os@jordan/schemas' 2>/dev/null || true"
    ok "shadow-os@jordan lié"
  fi
  # îlot : fourni par shadow-desktop (copié, pas lié, car son install.sh le fait aussi)
  if [ -d "$DESKTOP_REPO/extension/dynamic-island-v2@jordan" ] && ! gnome-extensions info dynamic-island-v2@jordan >/dev/null 2>&1; then
    faire "cp -r '$DESKTOP_REPO/extension/dynamic-island-v2@jordan' '$EXT_BASE/'"
    faire "glib-compile-schemas '$EXT_BASE/dynamic-island-v2@jordan/schemas' 2>/dev/null || true"
    ok "dynamic-island-v2@jordan copié"
  fi
  # activer tout
  local tous=("${EGO_EXT[@]}" shadow-os@jordan dynamic-island-v2@jordan
              user-theme@gnome-shell-extensions.gcampax.github.com)
  for u in "${tous[@]}"; do
    gnome-extensions info "$u" >/dev/null 2>&1 && faire "gnome-extensions enable '$u' 2>/dev/null || true"
  done
  ok "extensions activées (effectives après reconnexion)"
}

# ── MODULE theme / applis / scripts / terminal / apps ───────────────────────
mod_theme(){
  titre "Thème Éclipse + icônes"
  faire "bash '$RACINE/theme/eclipse.sh' apply"
  faire "bash '$RACINE/theme/icones.sh' apply"
  ok "thème et icônes appliqués"
}
mod_applis(){
  titre "Grille d'applications (dossiers, noms courts, dock)"
  faire "python3 -I '$RACINE/theme/applis.py' apply"
  ok "grille réorganisée"
}
mod_scripts(){
  titre "Scripts et commandes"
  faire "mkdir -p '$BIN'"
  faire "ln -sfn '$RACINE/scripts/shadow-mode.sh' '$BIN/shadow-mode'"
  faire "chmod +x '$RACINE/scripts/shadow-mode.sh'"
  ok "shadow-mode lié dans ~/.local/bin"
  if [ -f "$DESKTOP_REPO/bin/shadow" ]; then
    faire "ln -sfn '$DESKTOP_REPO/bin/shadow' '$BIN/shadow'"
    ok "commande shadow liée (depuis shadow-desktop)"
  fi
}
mod_terminal(){
  titre "Terminal (fastfetch)"
  faire "mkdir -p '$HOME/.config/fastfetch' '$HOME/.local/share/shadow-os'"
  [ -f "$RACINE/terminal/fastfetch.jsonc" ] && faire "cp '$RACINE/terminal/fastfetch.jsonc' '$HOME/.config/fastfetch/config.jsonc'"
  [ -f "$RACINE/terminal/logo.ansi" ] && faire "cp '$RACINE/terminal/logo.ansi' '$HOME/.local/share/shadow-os/logo.ansi'"
  ok "fastfetch configuré"
}
mod_apps(){
  titre "Applications maison"
  # VS Code
  if command -v code >/dev/null 2>&1; then
    local vsix; vsix="$(ls "$RACINE"/apps/vscode/*.vsix 2>/dev/null | head -1)"
    [ -n "$vsix" ] && faire "code --install-extension '$vsix' --force" && ok "thème VS Code installé"
  else
    info "VS Code absent : thème non installé"
  fi
  # Bienvenue : desktop + autostart
  if [ -f "$RACINE/apps/bienvenue/bienvenue.py" ]; then
    faire "mkdir -p '$HOME/.local/share/applications' '$HOME/.config/autostart'"
    local desk="$HOME/.local/share/applications/os.shadow.Bienvenue.desktop"
    faire "cat > '$desk' <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Bienvenue
Name[fr]=Bienvenue
Comment=Présentation de Shadow
Exec=python3 $RACINE/apps/bienvenue/bienvenue.py
Icon=$RACINE/identite/logo.svg
Terminal=false
Categories=System;
EOF"
    faire "sed 's/^Exec=.*/Exec=python3 $RACINE\\/apps\\/bienvenue\\/bienvenue.py --premier-lancement/; s/^X-GNOME-Autostart-Delay=.*//' '$desk' > '$HOME/.config/autostart/os.shadow.Bienvenue.desktop'"
    ok "appli Bienvenue installée (+ autostart)"
  fi
}

# ── MODULES optionnels lourds ───────────────────────────────────────────────
mod_arsenal(){
  titre "Arsenal Kali (distrobox)"
  if [ -x "$DESKTOP_REPO/arsenal/shadow-arsenal.sh" ]; then
    faire "'$DESKTOP_REPO/arsenal/shadow-arsenal.sh' setup"
  else
    avert "arsenal/shadow-arsenal.sh introuvable dans $DESKTOP_REPO"
  fi
}
mod_systeme(){
  titre "Système (GRUB, Plymouth, écran de connexion) — sudo"
  if [ -f "$RACINE/systeme/installer-systeme.sh" ]; then
    faire "sudo bash '$RACINE/systeme/installer-systeme.sh'"
  else
    avert "systeme/installer-systeme.sh introuvable"
  fi
}
mod_desktop(){
  titre "Bureau shadow-desktop (îlot, conky, fonds)"
  if [ -x "$DESKTOP_REPO/install.sh" ]; then
    faire "(cd '$DESKTOP_REPO' && ./install.sh --no-theme)"
  else
    avert "shadow-desktop/install.sh introuvable dans $DESKTOP_REPO"
  fi
}

# ── orchestration ───────────────────────────────────────────────────────────
MODULES_UTILISATEUR=(prerequis extensions theme applis scripts terminal apps)
declare -A DESC=(
  [prerequis]="paquets système (apt)"
  [extensions]="extensions GNOME (EGO + locales)"
  [theme]="thème Éclipse + icônes"
  [applis]="grille d'applications"
  [scripts]="scripts et commandes (shadow, shadow-mode)"
  [terminal]="fastfetch"
  [apps]="VS Code, Bienvenue"
  [arsenal]="box Kali (long)"
  [systeme]="GRUB/Plymouth/login (sudo)"
  [desktop]="îlot, conky, fonds (shadow-desktop)"
)

usage(){ sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//; s/^#//'; }
lister(){
  titre "Modules"
  for m in "${MODULES_UTILISATEUR[@]}" arsenal systeme desktop; do
    printf '  %s%-11s%s %s\n' "$C_OK" "$m" "$C_RST" "${DESC[$m]:-}"
  done
}

main(){
  local avec_systeme=0 avec_arsenal=0 avec_desktop=0 tout=0
  local seulement="" sans=""
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --avec-systeme) avec_systeme=1 ;;
      --avec-arsenal) avec_arsenal=1 ;;
      --avec-desktop) avec_desktop=1 ;;
      --tout) tout=1 ;;
      --seulement) seulement="$2"; shift ;;
      --seulement=*) seulement="${1#*=}" ;;
      --sans) sans="$2"; shift ;;
      --sans=*) sans="${1#*=}" ;;
      --simuler|-n) SIMULER=1 ;;
      --liste) lister; exit 0 ;;
      -h|--help) usage; exit 0 ;;
      *) mort "option inconnue : $1 (voir --help)" ;;
    esac
    shift
  done

  verifier

  # construire la liste de modules à exécuter
  local liste=()
  if [ -n "$seulement" ]; then
    IFS=',' read -r -a liste <<< "$seulement"
  else
    liste=("${MODULES_UTILISATEUR[@]}")
    [ "$tout" = 1 ] && { avec_systeme=1; avec_arsenal=1; avec_desktop=1; }
    [ "$avec_desktop" = 1 ] && liste+=(desktop)
    [ "$avec_arsenal" = 1 ] && liste+=(arsenal)
    [ "$avec_systeme" = 1 ] && liste+=(systeme)   # système en dernier
  fi
  # retirer ceux de --sans
  if [ -n "$sans" ]; then
    local garde=() s; IFS=',' read -r -a _sans <<< "$sans"
    for m in "${liste[@]}"; do
      local skip=0; for s in "${_sans[@]}"; do [ "$m" = "$s" ] && skip=1; done
      [ "$skip" = 0 ] && garde+=("$m")
    done
    liste=("${garde[@]}")
  fi

  [ "$SIMULER" = 1 ] && avert "mode simulation : aucune modification ne sera faite"
  info "modules : ${liste[*]}"

  for m in "${liste[@]}"; do
    case "$m" in
      prerequis) mod_prerequis ;;
      extensions) mod_extensions ;;
      theme) mod_theme ;;
      applis) mod_applis ;;
      scripts) mod_scripts ;;
      terminal) mod_terminal ;;
      apps) mod_apps ;;
      arsenal) mod_arsenal ;;
      systeme) mod_systeme ;;
      desktop) mod_desktop ;;
      *) avert "module inconnu ignoré : $m" ;;
    esac
  done

  titre "Terminé"
  ok "Shadow installé."
  info "Déconnecte-toi puis reconnecte-toi pour que les extensions et le thème prennent effet."
}

main "$@"
