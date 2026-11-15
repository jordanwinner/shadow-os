#!/usr/bin/env bash
# shadow-maj — met tout Shadow à jour en une commande, avec un seul mot de passe.
#
#   shadow maj              tout : système (apt, snap), Flatpak, extensions GNOME,
#                           arsenal Kali, shsh ; puis bilan et notification
#   shadow maj verifier     montre ce qui attend, sans rien changer (pas de mot de passe)
#   shadow maj --sans X…    saute des étapes : systeme flatpak extensions arsenal shsh
#   shadow maj --seulement X…
#   shadow maj veille       compte ce qui attend et le note pour l'îlot (minuteur, sans bruit)
#   shadow maj fenetre      ouvre un terminal qui lance « shadow maj » (clic sur l'îlot)
#   shadow maj minuteur [on|off]   veille automatique : 10 min après le démarrage, puis toutes les 6 h
#   shadow maj instantanes  les instantanés pris avant chaque mise à jour (3 derniers gardés)
#   shadow maj retour [ID]  revient aux versions de paquets et de snaps d'avant (le dernier par défaut)
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

etape_valide(){ local e; for e in "${ETAPES[@]}"; do [ "$e" = "$1" ] && return 0; done
  printf 'shadow maj : étape « %s » inconnue (étapes : %s)\n' "$1" "${ETAPES[*]}" >&2; exit 2; }
mode=faire; choisies=("${ETAPES[@]}"); liste=""
for a in "$@"; do                      # « verifier » compte où qu'il soit placé
  case "$a" in
    verifier|vérifier|-n|--verifier) mode=verifier ;;
    veille) mode=veille ;;
    minuteur) mode=minuteur ;;
    fenetre|fenêtre) mode=fenetre ;;
    instantanes|instantanés) mode=instantanes ;;
    retour) mode=retour ;;
  esac
done
while [ $# -gt 0 ]; do
  case "$1" in
    verifier|vérifier|-n|--verifier|veille|fenetre|fenêtre) ;;
    minuteur) shift; MINUTEUR="${1:-etat}"; break ;;
    instantanes|instantanés) ;;
    retour) shift; RETOUR_ID="${1:-}"; break ;;
    --sans|--seulement) liste="$1"; [ "$1" = --seulement ] && choisies=() ;;
    -h|--help|aide) sed -n '2,/^[^#]/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
    -*) printf 'shadow maj : option « %s » inconnue (shadow maj aide)\n' "$1" >&2; exit 2 ;;
    *)
      [ -n "$liste" ] || { printf 'shadow maj : « %s » inconnu (shadow maj aide)\n' "$1" >&2; exit 2; }
      etape_valide "$1"
      if [ "$liste" = --seulement ]; then choisies+=("$1")
      else garde=(); for e in "${choisies[@]}"; do [ "$e" = "$1" ] || garde+=("$e"); done; choisies=("${garde[@]}"); fi ;;
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

# ── Ce qui attend, compté une fois pour « verifier » et « veille » ──────────
compter(){
  N_APT=0; N_DIFF=0; N_SNAP=0; N_FLATPAK=0; N_EXT=0
  if veut systeme; then
    local sim; sim="$(LC_ALL=C apt-get -s full-upgrade 2>/dev/null)"
    N_APT="$(grep -c '^Inst ' <<<"$sim")"
    N_DIFF="$(sed -n '/phasing/,/^[^ ]/p' <<<"$sim" | grep '^ ' | wc -w)"
    N_SNAP="$(snap refresh --list 2>/dev/null | tail -n +2 | wc -l)"
  fi
  veut flatpak && command -v flatpak >/dev/null && N_FLATPAK="$(flatpak remote-ls --updates 2>/dev/null | wc -l)"
  if veut extensions; then verifier_extensions; N_EXT=${#ext_a_jour[@]}; fi
  veut shsh && verifier_shsh
  N_TOTAL=$(( N_APT + N_SNAP + N_FLATPAK + N_EXT + shsh_a_jour ))
}

ATTENTE="$ETAT/maj-attente"        # lu par l'îlot : JSON, absent quand tout est à jour
EN_COURS="$ETAT/maj-en-cours"      # présent pendant « shadow maj » : « PID date-ISO »
VERROU="$ETAT/maj.lock"            # un seul « shadow maj » à la fois

# « en cours » orphelin (PC éteint, processus tué : le trap n'a pas tourné) → on le retire
en_cours_vivant(){
  [ -f "$EN_COURS" ] || return 1
  local pid; read -r pid _ < "$EN_COURS" 2>/dev/null
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then return 0; fi
  rm -f "$EN_COURS"; return 1
}
ecrire_attente(){                  # $1 = 1 pour prévenir par une notification si le nombre a augmenté
  mkdir -p "$ETAT"
  local avant=0
  [ -f "$ATTENTE" ] && avant="$(python3 -c 'import json,sys;print(int(json.load(open(sys.argv[1])).get("total",0)))' "$ATTENTE" 2>/dev/null || echo 0)"
  if [ "$N_TOTAL" -eq 0 ]; then rm -f "$ATTENTE"; return 0; fi
  printf '{"total": %d, "apt": %d, "snap": %d, "flatpak": %d, "extensions": %d, "shsh": %d, "redemarrage": %s, "date": "%s"}\n' \
    "$N_TOTAL" "$N_APT" "$N_SNAP" "$N_FLATPAK" "$N_EXT" "$shsh_a_jour" \
    "$([ -f /var/run/reboot-required ] && echo true || echo false)" "$(date -Iseconds)" > "$ATTENTE.$$.tmp" \
    && mv -f "$ATTENTE.$$.tmp" "$ATTENTE"
  if [ "${1:-0}" = 1 ] && [ "$N_TOTAL" -gt "$avant" ]; then
    notify-send -a Shadow -i shadow-os "$N_TOTAL mise(s) à jour disponible(s)" \
      "Touche l'îlot pour tout mettre à jour (shadow maj)" 2>/dev/null || true
  fi
}

# ════════════════════════════════════════════════════════════════════════════
# ── Instantanés légers : versions des paquets, /etc, révisions snap, et les .deb
#    actuels de tout ce que la mise à jour va changer (pour pouvoir y revenir).
INST_DIR=/var/lib/shadow-os/instantanes
script_instantane(){
  cat <<'FIN'
# rien à mettre à jour : pas d'instantané (il chasserait un instantané utile de la rotation)
LC_ALL=C apt-get -s full-upgrade 2>/dev/null > /tmp/shadow-maj-sim.$$
snaps_maj="$(command -v snap >/dev/null && snap refresh --list 2>/dev/null | tail -n +2)"
if ! grep -q '^Inst ' /tmp/shadow-maj-sim.$$ && [ -z "$snaps_maj" ]; then
  echo "  · rien à mettre à jour : pas d'instantané"
else
  base=/var/lib/shadow-os/instantanes
  install -d -m 755 /var/lib/shadow-os "$base"
  # place d'abord : on garde les 2 derniers, le nouveau fera le 3e
  ls -1d "$base"/2* 2>/dev/null | head -n -2 | xargs -r rm -rf
  libre_ko="$(df --output=avail -k "$base" | tail -1 | tr -d ' ')"
  if [ "${libre_ko:-0}" -lt 3145728 ]; then
    echo "  ✘ moins de 3 Go libres : pas d'instantané cette fois (la mise à jour continue)"
  else
    inst="$base/$(date +%Y%m%d-%H%M%S)"
    install -d -m 755 "$inst" "$inst/debs"
    dpkg-query -W -f='${binary:Package}\t${Architecture}\t${Version}\n' > "$inst/paquets.tsv"
    # /etc contient des secrets (mots de passe hachés, clés) : créé d'emblée en accès root seul
    ( umask 077; tar -czf "$inst/etc.tar.gz" -C / etc 2>/dev/null )
    command -v snap >/dev/null && snap list 2>/dev/null | awk 'NR>1{print $1"\t"$3}' > "$inst/snaps.tsv"
    # paquets mis à jour (avec leur version actuelle), nouveaux et retirés
    sed -n 's/^Inst \([^ ]*\) \[\([^]]*\)\].*/\1\t\2/p' /tmp/shadow-maj-sim.$$ > "$inst/changent.tsv"
    sed -n 's/^Inst \([^ ]*\) (\([^ ]*\) .*/\1\t\2/p' /tmp/shadow-maj-sim.$$ > "$inst/nouveaux.tsv"
    sed -n 's/^Remv \([^ ]*\) \[\([^]]*\)\].*/\1\t\2/p' /tmp/shadow-maj-sim.$$ > "$inst/retires.tsv"
    if [ -s "$inst/changent.tsv" ]; then
      command -v dpkg-repack >/dev/null || apt-get install -y -q dpkg-repack >/dev/null 2>&1 || true
      ( cd "$inst/debs" && while IFS=$'\t' read -r p v; do
          apt-get download -q "$p=$v" >/dev/null 2>&1 || dpkg-repack "$p" >/dev/null 2>&1 || echo "$p" >> ../manquants.txt
        done < ../changent.tsv )
    fi
    echo "  · instantané $(basename "$inst") : $(wc -l < "$inst/changent.tsv") paquet(s) gardé(s) dans leur version actuelle$( [ -s "$inst/manquants.txt" ] && echo ", $(wc -l < "$inst/manquants.txt") introuvable(s)")"
  fi
fi
rm -f /tmp/shadow-maj-sim.$$
FIN
}

if [ "$mode" = instantanes ]; then
  titre "Instantanés (avant chaque mise à jour)"
  trouve=0
  for d in $(ls -1d "$INST_DIR"/2* 2>/dev/null | sort -r); do
    trouve=1
    n=$(wc -l < "$d/changent.tsv" 2>/dev/null || echo 0)
    m=$( [ -s "$d/manquants.txt" ] && echo " · $(wc -l < "$d/manquants.txt") introuvable(s)" )
    info "$(basename "$d") · $n paquet(s) récupérable(s)$m · $(du -sh "$d" 2>/dev/null | cut -f1)"
  done
  [ $trouve = 1 ] || info "aucun : le premier sera pris au prochain « shadow maj »"
  exit 0
fi

if [ "$mode" = retour ]; then
  dernier="$(ls -1d "$INST_DIR"/2* 2>/dev/null | sort | tail -1 | xargs -r basename)"
  id="${RETOUR_ID:-$dernier}"
  [[ "$id" =~ ^[0-9]{8}-[0-9]{6}$ ]] && [ -d "$INST_DIR/$id" ] || { printf 'shadow maj retour : instantané « %s » introuvable (shadow maj instantanes)\n' "$id" >&2; exit 2; }
  if [ "$id" != "$dernier" ]; then
    # revenir à un instantané plus ancien laisserait en place les mises à jour faites depuis
    printf 'shadow maj retour : seul le dernier instantané (%s) peut être rejoué ; reviens d'\''abord à celui-là\n' "$dernier" >&2
    exit 2
  fi
  titre "Retour à l'instantané $id (un seul mot de passe)"
  retour="$(printf 'inst=%q\n' "$INST_DIR/$id"; cat <<'FIN'
export DEBIAN_FRONTEND=noninteractive
cd "$inst" || exit 2
native="$(dpkg --print-architecture)"
declare -A deb
for f in debs/*.deb; do
  [ -e "$f" ] || continue
  deb["$(dpkg-deb -f "$f" Package):$(dpkg-deb -f "$f" Architecture):$(dpkg-deb -f "$f" Version)"]="$f"
done
a_remettre=()
while IFS=$'\t' read -r p v; do
  cur="$(dpkg-query -W -f='${Version}' "$p" 2>/dev/null)"
  [ "$cur" = "$v" ] && continue
  nom="${p%%:*}"; arch="${p#*:}"; [ "$arch" = "$p" ] && arch="$native"
  f="${deb[$nom:$arch:$v]:-${deb[$nom:all:$v]:-}}"
  [ -n "$f" ] && a_remettre+=("./$f") || echo "  ✘ $p $v : pas de paquet gardé"
done < changent.tsv
if [ ${#a_remettre[@]} -gt 0 ]; then
  echo "  · ${#a_remettre[@]} paquet(s) remis dans leur version d'avant"
  apt-get install -y -q --allow-downgrades -o Dpkg::Options::=--force-confold "${a_remettre[@]}" || exit 3
else
  echo "  · paquets : déjà dans les versions de l'instantané"
fi
if [ -s snaps.tsv ] && command -v snap >/dev/null; then
  while IFS=$'\t' read -r n rev; do
    cur="$(snap list "$n" 2>/dev/null | awk 'NR==2{print $3}')"
    [ -n "$cur" ] && [ "$cur" != "$rev" ] && { echo "  · snap $n : révision $cur → $rev"; snap revert "$n" --revision "$rev" >/dev/null || echo "  ✘ snap $n : retour impossible"; }
  done < snaps.tsv
fi
[ -s nouveaux.tsv ] && echo "  · ajoutés par la mise à jour (laissés en place) : $(cut -f1 nouveaux.tsv | tr '\n' ' ')"
[ -s retires.tsv ] && echo "  · retirés par la mise à jour (à réinstaller avec apt si besoin) : $(cut -f1 retires.tsv | tr '\n' ' ')"
echo "  · /etc d'avant (non restauré automatiquement) : $inst/etc.tar.gz"
FIN
)"
  if pkexec /bin/bash -c "$retour"; then ok "retour à $id terminé"; else avert "retour à $id interrompu ou incomplet"; exit 1; fi
  exit 0
fi

if [ "$mode" = minuteur ]; then
  U="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  case "${MINUTEUR:-etat}" in
    on)
      mkdir -p "$U"
      printf '[Unit]\nDescription=Shadow : compte les mises à jour pour l’îlot\n\n[Service]\nType=oneshot\nNice=10\nExecStart=%s veille\n' \
        "$HOME/.local/bin/shadow-maj" > "$U/shadow-maj-veille.service"
      printf '[Unit]\nDescription=Shadow : veille des mises à jour\n\n[Timer]\nOnStartupSec=10min\nOnUnitActiveSec=6h\nRandomizedDelaySec=5min\n\n[Install]\nWantedBy=timers.target\n' \
        > "$U/shadow-maj-veille.timer"
      systemctl --user daemon-reload && systemctl --user enable --now shadow-maj-veille.timer \
        && echo "Veille des mises à jour : 10 min après le démarrage, puis toutes les 6 h" ;;
    off)
      systemctl --user disable --now shadow-maj-veille.timer 2>/dev/null
      rm -f "$U/shadow-maj-veille.service" "$U/shadow-maj-veille.timer" "$ATTENTE"
      systemctl --user daemon-reload; echo "Veille des mises à jour arrêtée" ;;
    *) printf 'Veille des mises à jour : %s\n' "$(systemctl --user is-active shadow-maj-veille.timer 2>/dev/null)" ;;
  esac
  exit 0
fi

if [ "$mode" = veille ]; then
  # un « shadow maj » en cours s'occupe déjà de tout
  # un « shadow maj » en cours tient le verrou : on attend qu'il ait fini (10 min au plus)
  exec 9>"$VERROU"
  flock -w 600 9 || exit 0
  flock -u 9; exec 9>&-          # on ne garde pas le verrou : compter ne doit jamais bloquer « shadow maj »
  en_cours_vivant && exit 0
  compter
  # une mise à jour a démarré pendant le comptage : son propre recompte fera foi
  en_cours_vivant && exit 0
  ecrire_attente 1
  exit 0
fi

if [ "$mode" = fenetre ]; then
  # banc d'essai : on prouve que le clic arrive ici, sans rien lancer
  if [ -n "${SHADOW_MAJ_ESSAI:-}" ]; then date -Iseconds >> "$ETAT/maj-fenetre-essai"; exit 0; fi
  # terminal de l'utilisateur, sinon le premier trouvé ; la fenêtre reste ouverte pour lire le bilan
  # chemin absolu : le PATH hérité de GNOME Shell ne contient pas forcément ~/.local/bin
  cmd=(bash -c '"$0"; echo; read -rp "Entrée pour fermer… " _' "${SHADOW_MAJ_CMD:-$HOME/.local/bin/shadow-maj}")
  for t in "${TERMINAL:-}" kitty ptyxis gnome-terminal kgx xterm; do
    [ -n "$t" ] && command -v "$t" >/dev/null || continue
    case "$t" in
      gnome-terminal|ptyxis|kgx) exec "$t" --title "Shadow · mise à jour" -- "${cmd[@]}" ;;
      kitty) exec kitty --title "Shadow · mise à jour" "${cmd[@]}" ;;
      *) exec "$t" -e "${cmd[@]}" ;;
    esac
  done
  notify-send -a Shadow -i shadow-os "Aucun terminal trouvé" "Lance « shadow maj » toi-même" 2>/dev/null
  exit 1
fi

if [ "$mode" = verifier ]; then
  titre "Ce qui attend une mise à jour"
  compter
  if veut systeme; then
    # ce qu'apt installerait vraiment (hors paquets différés par le déploiement progressif d'Ubuntu)
    [ "$N_APT" -gt 0 ] && info "apt : $N_APT paquet(s)" || ok "apt : à jour"
    [ "$N_DIFF" -gt 0 ] && info "apt : $N_DIFF paquet(s) retenus par Ubuntu (déploiement progressif), rien à faire"
    [ "$N_SNAP" -gt 0 ] && info "snap : $N_SNAP paquet(s)" || ok "snap : à jour"
    [ -f /var/run/reboot-required ] && info "redémarrage demandé par une mise à jour précédente"
  fi
  if veut flatpak && command -v flatpak >/dev/null; then
    [ "$N_FLATPAK" -gt 0 ] && info "Flatpak : $N_FLATPAK élément(s)" || ok "Flatpak : à jour"
  fi
  if veut extensions; then
    if [ "$N_EXT" -eq 0 ]; then ok "extensions GNOME : à jour (GNOME $GSHELL_VER)"
    else for e in "${ext_a_jour[@]}"; do read -r u l d _ <<<"$e"; info "extension $u : v$l → v$d"; done; fi
  fi
  if veut shsh; then
    [ $shsh_a_jour = 1 ] && info "shsh : dépôt $SHSH_DEP, installé $SHSH_INST (à recompiler)" || ok "shsh : à jour"
  fi
  veut arsenal && info "arsenal Kali : « shadow arsenal update » (vérifié pendant la mise à jour)"
  # une vérification complète met aussi l'îlot à jour (sans notification)
  [ ${#choisies[@]} -eq ${#ETAPES[@]} ] && ecrire_attente 0
  exit 0
fi

mkdir -p "$ETAT"
# l'îlot affiche « Mise à jour… » tant que ce fichier existe
exec 9>"$VERROU"
if ! flock -n 9; then
  printf '%s◐ Une mise à jour de Shadow est déjà en cours.%s\n' "$V$B" "$Z"
  exit 1
fi
printf '%s %s\n' "$$" "$(date -Iseconds)" > "$EN_COURS"
trap 'rm -f "$EN_COURS"' EXIT
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
    compat="$(mktemp)"
    # la sortie du compilateur va dans le fichier (dernière ligne = bilan des tests, ou l'erreur)
    if (cd "$SHSH_REPO" && cargo build --release -q >"$compat" 2>&1 && cargo build -q >>"$compat" 2>&1 \
          && tests/compat.sh >>"$compat" 2>&1); then
      SHSH_BIN="$SHSH_REPO/target/release/shsh"
      # empreinte prise juste après les tests : l'étape root refuse un binaire modifié entre-temps
      SHSH_SHA="$(sha256sum "$SHSH_BIN" | cut -d' ' -f1)"
      ok "compilé, $(tail -1 "$compat")"
    else
      avert "shsh : compilation ou tests en échec, version actuelle gardée ($(tail -1 "$compat" 2>/dev/null))"
    fi
    rm -f "$compat"
  fi
fi

# 2. Tout ce qui demande root, en un seul pkexec
if veut systeme || [ -n "$SHSH_BIN" ]; then
  titre "Système (un seul mot de passe)"
  # Le script root est passé en argument à pkexec, jamais écrit dans un fichier
  # que le compte utilisateur pourrait modifier pendant la saisie du mot de passe.
  racine="$(
    echo '#!/bin/bash'
    echo 'export DEBIAN_FRONTEND=noninteractive'
    echo 'r=0'
    if veut systeme; then
      echo 'echo "  · apt : liste des paquets…"; apt-get update -q || r=1'
      # instantané juste avant de toucher aux paquets (versions actuelles gardées pour « shadow maj retour »)
      script_instantane
      echo 'apt-get -y -q -o Dpkg::Options::=--force-confold full-upgrade || r=1'
      echo 'apt-get -y -q autoremove --purge || true'
      echo 'command -v snap >/dev/null && { echo "  · snap…"; snap refresh || r=1; }'
    fi
    # copie root d'abord, puis contrôle de l'empreinte sur cette copie (que l'utilisateur ne peut plus toucher)
    [ -n "$SHSH_BIN" ] && printf 'install -m 755 %q /usr/local/bin/shsh.nouveau && echo %q | sha256sum -c --status && mv -f /usr/local/bin/shsh.nouveau /usr/local/bin/shsh && echo "  · shsh installé" || { rm -f /usr/local/bin/shsh.nouveau; echo "  ✘ shsh : empreinte différente, installation refusée"; r=1; }\n' "$SHSH_BIN" "$SHSH_SHA  /usr/local/bin/shsh.nouveau"
    echo 'exit $r'
  )"
  if pkexec /bin/bash -c "$racine"; then
    veut systeme && ok "apt et snap à jour" && BILAN_OK+=("système")
    [ -n "$SHSH_BIN" ] && ok "shsh $(/usr/local/bin/shsh --version | awk '{print $2}') installé" && BILAN_OK+=("shsh")
  else
    avert "étape système interrompue ou en échec (mot de passe refusé ?)"
  fi
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

# L'îlot se recalcule sur tout ce qui reste, en arrière-plan pour ne pas retarder le bilan
# L'ancien compte n'a plus de sens : on l'efface, puis une veille détachée du terminal
# (qui peut être fermé tout de suite) recompte ce qui reste, une fois ce script terminé.
rm -f "$ATTENTE"
setsid -f bash -c 'exec "$0" veille' "$HOME/.local/bin/shadow-maj" </dev/null >/dev/null 2>&1 9>&- || true

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
