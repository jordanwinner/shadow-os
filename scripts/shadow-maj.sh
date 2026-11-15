#!/usr/bin/env bash
# shadow-maj — met tout Shadow à jour en une commande, avec un seul mot de passe.
#
#   shadow maj              tout : système (apt, snap), Flatpak, extensions GNOME,
#                           arsenal Kali, shsh ; puis bilan et notification
#   shadow maj verifier     montre ce qui attend, sans rien changer (pas de mot de passe)
#   shadow maj --sans X…    saute des étapes : systeme flatpak extensions arsenal shsh
#   shadow maj --seulement X…
#
# Les étapes root (apt, snap, installation de shsh) sont regroupées dans un
# script unique lancé par pkexec : la fenêtre de mot de passe ne s'ouvre qu'une fois.
set -uo pipefail

SHSH_REPO="${SHADOW_SHSH_REPO:-$HOME/Dev/shsh}"
SHADOW_REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
EXT_BASE="$HOME/.local/share/gnome-shell/extensions"
ETAT="${XDG_STATE_HOME:-$HOME/.local/state}/shadow-os"
JOURNAL="$ETAT/maj.log"
ETAPES=(systeme flatpak extensions arsenal shsh)

V=$'\033[38;2;124;108;255m'; R=$'\033[38;2;255;77;141m'; G=$'\033[38;2;120;220;160m'
D=$'\033[38;2;110;106;150m'; B=$'\033[1m'; Z=$'\033[0m'
[ -t 1 ] || { V=; R=; G=; D=; B=; Z=; }
titre(){ printf '\n%s◐ %s%s\n' "$V$B" "$*" "$Z"; }
ok(){ printf '  %s✔%s %s\n' "$G" "$Z" "$*"; }
info(){ printf '  %s·%s %s\n' "$D" "$Z" "$*"; }
avert(){ printf '  %s✘%s %s\n' "$R" "$Z" "$*"; BILAN_KO+=("$*"); }
BILAN_OK=(); BILAN_KO=()

mode=faire; choisies=("${ETAPES[@]}")
while [ $# -gt 0 ]; do
  case "$1" in
    verifier|vérifier|-n|--verifier) mode=verifier ;;
    --sans) shift; while [ $# -gt 0 ] && [[ $1 != --* ]]; do choisies=("${choisies[@]/$1}"); shift; done; continue ;;
    --seulement) shift; choisies=(); while [ $# -gt 0 ] && [[ $1 != --* ]]; do choisies+=("$1"); shift; done; continue ;;
    -h|--help|aide) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'shadow maj : « %s » inconnu (shadow maj aide)\n' "$1" >&2; exit 2 ;;
  esac
  shift
done
veut(){ local e; for e in "${choisies[@]}"; do [ "$e" = "$1" ] && return 0; done; return 1; }

# ── Extensions GNOME : version installée vs extensions.gnome.org ────────────
GSHELL_VER="$(gnome-shell --version 2>/dev/null | grep -oE '[0-9]+(\.[0-9]+)?' | head -1)"
ext_a_jour=()   # "uuid installée distante url"
verifier_extensions(){
  local dir uuid locale info distante url
  for dir in "$EXT_BASE"/*/; do
    [ -L "${dir%/}" ] && continue                       # extensions maison liées au dépôt
    uuid="$(basename "$dir")"
    [[ $uuid == *@jordan ]] && continue                  # îlot, Shadow : livrés par nos dépôts
    # copie retouchée par Shadow (thème gardé pendant le verrouillage) : ne pas l'écraser
    [ "$uuid" = user-theme@gnome-shell-extensions.gcampax.github.com ] && continue
    locale="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("version",0))' "$dir/metadata.json" 2>/dev/null || echo 0)"
    info="$(curl -fsSL --max-time 10 "https://extensions.gnome.org/extension-info/?uuid=${uuid}&shell_version=${GSHELL_VER}" 2>/dev/null)" || continue
    read -r distante url < <(python3 -c 'import json,sys
d=json.loads(sys.argv[1]); print(d.get("version",0), "https://extensions.gnome.org"+d.get("download_url",""))' "$info" 2>/dev/null) || continue
    [ "${locale:-0}" -gt 0 ] 2>/dev/null || continue     # sans numéro de version : copie locale
    if [ "${distante:-0}" -gt "${locale:-0}" ] 2>/dev/null; then ext_a_jour+=("$uuid $locale $distante $url"); fi
  done
}

# ── shsh : le binaire installé est-il plus vieux que le dépôt ? ─────────────
shsh_a_jour=0
verifier_shsh(){
  [ -f "$SHSH_REPO/Cargo.toml" ] || return 0
  local dep inst
  dep="$(sed -n 's/^version = "\(.*\)"/\1/p' "$SHSH_REPO/Cargo.toml" | head -1)"
  inst="$(/usr/local/bin/shsh --version 2>/dev/null | awk '{print $2}')"
  local plus_recent
  plus_recent="$(find "$SHSH_REPO/src" "$SHSH_REPO/Cargo.lock" -newer /usr/local/bin/shsh -print -quit 2>/dev/null)"
  if [ "$dep" != "$inst" ] || [ -n "$plus_recent" ]; then shsh_a_jour=1; SHSH_DEP="$dep"; SHSH_INST="${inst:-absent}"; fi
}

# ════════════════════════════════════════════════════════════════════════════
if [ "$mode" = verifier ]; then
  titre "Ce qui attend une mise à jour"
  if veut systeme; then
    n="$(apt list --upgradable 2>/dev/null | tail -n +2 | wc -l)"
    [ "$n" -gt 0 ] && info "apt : $n paquet(s)" || ok "apt : à jour"
    n="$(snap refresh --list 2>/dev/null | tail -n +2 | wc -l)"
    [ "$n" -gt 0 ] && info "snap : $n paquet(s)" || ok "snap : à jour"
    [ -f /var/run/reboot-required ] && info "redémarrage demandé par une mise à jour précédente"
  fi
  if veut flatpak && command -v flatpak >/dev/null; then
    n="$(flatpak remote-ls --updates 2>/dev/null | wc -l)"
    [ "$n" -gt 0 ] && info "Flatpak : $n élément(s)" || ok "Flatpak : à jour"
  fi
  if veut extensions; then
    verifier_extensions
    if [ ${#ext_a_jour[@]} -eq 0 ]; then ok "extensions GNOME : à jour (GNOME $GSHELL_VER)"
    else for e in "${ext_a_jour[@]}"; do read -r u l d _ <<<"$e"; info "extension $u : v$l → v$d"; done; fi
  fi
  if veut shsh; then
    verifier_shsh
    [ $shsh_a_jour = 1 ] && info "shsh : dépôt $SHSH_DEP, installé $SHSH_INST (à recompiler)" || ok "shsh : à jour"
  fi
  veut arsenal && info "arsenal Kali : « shadow arsenal update » (vérifié pendant la mise à jour)"
  exit 0
fi

mkdir -p "$ETAT"
exec > >(tee -a "$JOURNAL") 2>&1
printf '\n===== shadow maj · %s =====\n' "$(date '+%F %T')"

# 1. shsh d'abord (compilation sans root), l'installation part avec l'étape root
SHSH_BIN=""
if veut shsh; then
  titre "shsh"
  verifier_shsh
  if [ $shsh_a_jour = 0 ]; then ok "déjà à jour ($( /usr/local/bin/shsh --version 2>/dev/null))"
  elif ! command -v cargo >/dev/null; then avert "cargo absent : shsh non recompilé"
  else
    info "compilation de shsh $SHSH_DEP…"
    if (cd "$SHSH_REPO" && cargo build --release -q && cargo build -q && tests/compat.sh >/tmp/shsh-compat.$$ 2>&1); then
      SHSH_BIN="$SHSH_REPO/target/release/shsh"
      ok "compilé, $(tail -1 /tmp/shsh-compat.$$)"
    else
      avert "shsh : compilation ou tests en échec, version actuelle gardée ($(tail -1 /tmp/shsh-compat.$$ 2>/dev/null))"
    fi
    rm -f /tmp/shsh-compat.$$
  fi
fi

# 2. Tout ce qui demande root, en un seul pkexec
if veut systeme || [ -n "$SHSH_BIN" ]; then
  titre "Système (un seul mot de passe)"
  racine="$(mktemp --suffix=-shadow-maj.sh)"
  {
    echo '#!/bin/bash'
    echo 'export DEBIAN_FRONTEND=noninteractive'
    echo 'r=0'
    if veut systeme; then
      echo 'echo "  · apt : liste des paquets…"; apt-get update -q || r=1'
      echo 'apt-get -y -q -o Dpkg::Options::=--force-confold full-upgrade || r=1'
      echo 'apt-get -y -q autoremove --purge || true'
      echo 'command -v snap >/dev/null && { echo "  · snap…"; snap refresh || r=1; }'
    fi
    [ -n "$SHSH_BIN" ] && printf 'install -m 755 %q /usr/local/bin/shsh.nouveau && mv -f /usr/local/bin/shsh.nouveau /usr/local/bin/shsh && echo "  · shsh installé" || r=1\n' "$SHSH_BIN"
    echo 'exit $r'
  } > "$racine"
  chmod 700 "$racine"
  if pkexec bash "$racine"; then
    veut systeme && ok "apt et snap à jour"; BILAN_OK+=("système")
    [ -n "$SHSH_BIN" ] && ok "shsh $(/usr/local/bin/shsh --version | awk '{print $2}') installé" && BILAN_OK+=("shsh")
  else
    avert "étape système interrompue ou en échec (mot de passe refusé ?)"
  fi
  rm -f "$racine"
fi

# 3. Flatpak
if veut flatpak && command -v flatpak >/dev/null; then
  titre "Flatpak"
  if flatpak update -y --noninteractive; then flatpak uninstall --unused -y --noninteractive >/dev/null 2>&1; ok "Flatpak à jour"; BILAN_OK+=("Flatpak")
  else avert "Flatpak : échec"; fi
fi

# 4. Extensions GNOME (effectives à la prochaine connexion)
if veut extensions; then
  titre "Extensions GNOME"
  verifier_extensions
  if [ ${#ext_a_jour[@]} -eq 0 ]; then ok "à jour pour GNOME $GSHELL_VER"
  else
    blur_maj=0
    for e in "${ext_a_jour[@]}"; do
      read -r u l d url <<<"$e"
      zip="$(mktemp --suffix=.zip)"
      if curl -fsSL "$url" -o "$zip" && gnome-extensions install --force "$zip"; then
        ok "$u : v$l → v$d"; [ "$u" = blur-my-shell@aunetx ] && blur_maj=1
      else avert "$u : échec de la mise à jour"; fi
      rm -f "$zip"
    done
    # Les feuilles de style allégées/fusionnées sont écrasées par une mise à jour : on les refait
    [ $blur_maj = 1 ] && python3 "$SHADOW_REPO/systeme/perf/alleger-blur-css.py" appliquer >/dev/null && ok "Blur my Shell réallégé"
    python3 "$SHADOW_REPO/systeme/perf/fusionner-css.py" appliquer >/dev/null && ok "styles refusionnés dans le thème"
    info "nouvelles versions actives après déconnexion/reconnexion"
    BILAN_OK+=("extensions")
  fi
fi

# 5. Arsenal Kali (box distrobox)
if veut arsenal; then
  titre "Arsenal Kali"
  if ! command -v distrobox >/dev/null || ! podman container exists kali 2>/dev/null; then info "pas d'arsenal installé"
  elif shadow arsenal update; then ok "arsenal à jour"; BILAN_OK+=("arsenal")
  else avert "arsenal : échec de la mise à jour"; fi
fi

# Bilan
titre "Bilan"
[ ${#BILAN_OK[@]} -gt 0 ] && ok "à jour : ${BILAN_OK[*]}"
redemarrer=""
[ -f /var/run/reboot-required ] && redemarrer="Redémarrage nécessaire (nouveau noyau ou bibliothèque système)." && info "$redemarrer"
info "journal : $JOURNAL"
if [ ${#BILAN_KO[@]} -eq 0 ]; then
  notify-send -a Shadow -i shadow-os "Shadow est à jour" "${BILAN_OK[*]:-rien à faire}. $redemarrer" 2>/dev/null || true
  exit 0
else
  notify-send -a Shadow -i shadow-os -u critical "Mise à jour incomplète" "${#BILAN_KO[@]} problème(s) : voir shadow maj" 2>/dev/null || true
  exit 1
fi
