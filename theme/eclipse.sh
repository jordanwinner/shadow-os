#!/usr/bin/env bash
# Shadow — palette « Éclipse » appliquée au bureau GNOME (sans sudo, réversible).
#   eclipse.sh apply    sauvegarde puis applique (thème shell, libadwaita, tuiles, dock)
#   eclipse.sh revert   remet l'état sauvegardé avant le dernier apply
#   eclipse.sh build    régénère seulement le thème shell ~/.themes/Shadow
# Le thème shell est généré depuis le CSS Yaru-dark de la version de GNOME installée :
# la mise en page reste toujours celle d'origine, seules les couleurs changent.
# Relancer `build` après une mise à jour de GNOME.
set -euo pipefail

# ── Palette Éclipse ────────────────────────────────────────────────────────
VIDE='#07070B'      # fond le plus profond
ENCRE='#0E0E16'     # fond principal
NUIT='#14141F'      # barres, vues
ARDOISE='#1A1A28'   # cartes, popovers
BRUME='#232334'     # survol
CENDRE='#2C2C40'    # bordures fortes
TEXTE='#ECEBFA'
TEXTE_2='#A9A9C2'
ECLIPSE='#7C6CFF'   # accent
AURA='#B7A9FF'      # accent clair
BRAISE='#FF4D8D'    # erreurs, destructif
SOLEIL='#FFB454'    # avertissements
JADE='#4ADE9B'      # succès

SRC=/usr/share/gnome-shell/theme/Yaru-dark
THEME_DIR="$HOME/.themes/Shadow"
SAUV_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/shadow-os/eclipse-sauvegarde"
GTK4="$HOME/.config/gtk-4.0/gtk.css"
GTK3="$HOME/.config/gtk-3.0/gtk.css"
DEBUT="/* >>> SHADOW-DESKTOP >>> */"   # mêmes marqueurs que shadow-desktop :
FIN="/* <<< SHADOW-DESKTOP <<< */"     # un seul bloc palette, jamais deux
TS=(gsettings --schemadir "$HOME/.local/share/gnome-shell/extensions/tilingshell@ferrarodomenico.com/schemas")
SB=(gsettings --schemadir "$HOME/.local/share/gnome-shell/extensions/space-bar@luchrioh/schemas")
SBA=org.gnome.shell.extensions.space-bar.appearance
LM=(gsettings --schemadir "$HOME/.local/share/gnome-shell/extensions/logomenu@aryan_k/schemas")
LMS=org.gnome.shell.extensions.logo-menu
DTD=(gsettings --schemadir "$HOME/.local/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com/schemas")

ok(){ printf '  \033[32m✓\033[0m %s\n' "$*"; }
titre(){ printf '\033[1;35m▸ %s\033[0m\n' "$*"; }

build(){
  [ -f "$SRC/gnome-shell.css" ] || { echo "Yaru-dark introuvable ($SRC)" >&2; exit 1; }
  mkdir -p "$THEME_DIR/gnome-shell"
  cp "$SRC"/*.svg "$THEME_DIR/gnome-shell/" 2>/dev/null || true
  sed -E \
    -e "s/-st-accent-fg-color/#ffffff/g" \
    -e "s/-st-accent-color/${ECLIPSE}/g" \
    -e "s/#f2f2f2|#e8e8e8|#d8d8d8|#d7d7d8/${TEXTE}/gI" \
    -e 's/rgba\((242, 242, 242|238, 238, 238),/rgba(236, 235, 250,/g' \
    -e "s/#131313/${VIDE}/gI" \
    -e "s/#222222|#202020/${ENCRE}/gI" \
    -e "s/#2f2f2f/${NUIT}/gI" \
    -e "s/#36363a|#333333|#353535/${ARDOISE}/gI" \
    -e "s/#373737/${BRUME}/gI" \
    -e "s/#424247|#424242|#48484c/${CENDRE}/gI" \
    -e "s/#4d4d4d|#47474c|#4a4a4f/#34344C/gI" \
    -e "s/#54545a|#56565c/#45455F/gI" \
    -e "s/#9b9b9d|#a5a5a5|#a8a8aa/${TEXTE_2}/gI" \
    -e "s/#b2b2b4|#b3b3b3|#cccccc/#BDBCD6/gI" \
    -e "s/#fea320|#ffbd45/${SOLEIL}/gI" \
    -e "s/#ea5b29|#ee7b53|#ef825c|#ec6d40/${ECLIPSE}/gI" \
    -e "s/#de1930|#c7162b|#e82d43|#e7243b|#fe9d96|#a71224/${BRAISE}/gI" \
    -e 's/rgba\(254, 163, 32,/rgba(255, 180, 84,/g' \
    "$SRC/gnome-shell.css" > "$THEME_DIR/gnome-shell/gnome-shell.css"
  cat >> "$THEME_DIR/gnome-shell/gnome-shell.css" <<CSS

/* ===== Shadow · Éclipse : finitions (couleurs seulement, formes = Yaru officiel) ===== */
.quick-settings {
  background-color: rgba(14, 14, 22, 0.94);
  border: 1px solid rgba(183, 169, 255, 0.10); }
.popup-menu-content, .candidate-popup-content {
  background-color: rgba(14, 14, 22, 0.96);
  border: 1px solid rgba(183, 169, 255, 0.08); }
.search-entry { border: 1px solid rgba(183, 169, 255, 0.10); }
.search-entry:focus { border-color: ${ECLIPSE}; }
/* GNOME 50 peint les tuiles actives avec l'accent système : on force Éclipse */
.quick-toggle:checked, .quick-toggle-has-menu .quick-toggle-menu-button:checked {
  background-color: ${ECLIPSE} !important; color: #ffffff !important; }
.quick-toggle:checked:hover, .quick-toggle-has-menu .quick-toggle-menu-button:checked:hover {
  background-color: #8D7FFF !important; }
.quick-toggle-has-menu .quick-toggle-menu-button:checked { background-color: #6E5DF2 !important; }
.quick-toggle-has-menu:checked .quick-toggle-separator { background-color: rgba(255,255,255,0.25) !important; }

/* Dock flottant façon macOS : décollé du bord, verre teinté, liseré fin */
#dashtodockContainer.bottom:ltr { padding-bottom: 10px; }
#dashtodockContainer.bottom:ltr #dash .dash-background { margin-bottom: 0; border-radius: 22px; }
#dashtodockContainer #dash .dash-background {
  border-radius: 22px;
  background-color: rgba(14, 14, 22, 0.55);
  border: 1px solid rgba(183, 169, 255, 0.12);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35); }
#dashtodockContainer .dash-item-container .overview-tile:hover .overview-icon,
#dashtodockContainer .show-apps:hover .overview-icon { background-color: rgba(236, 235, 250, 0.08); border-radius: 14px; }
#dashtodockContainer .show-apps .overview-icon { background-color: transparent; }
#dashtodockContainer .show-apps:checked .overview-icon { background-color: rgba(124, 108, 255, 0.30); border-radius: 14px; }
#dashtodockContainer .dash-separator { background-color: rgba(236, 235, 250, 0.14); width: 1px; margin: 6px 4px; }

/* Dock : verre plus net (dégradé, liseré lumineux, reflet haut) */
#dashtodockContainer #dash .dash-background {
  border-radius: 26px;
  background-color: rgba(16, 16, 26, 0.62);
  background-gradient-direction: vertical;
  background-gradient-start: rgba(44, 41, 72, 0.66);
  background-gradient-end: rgba(12, 12, 20, 0.66);
  border: 1px solid rgba(183, 169, 255, 0.22);
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.10); }
#dashtodockContainer.bottom:ltr #dash .dash-background { border-radius: 26px; }
#dashtodockContainer .dash-item-container .overview-tile .overview-icon { transition-duration: 160ms; border-radius: 16px; }
#dashtodockContainer .dash-item-container .overview-tile:hover .overview-icon,
#dashtodockContainer .show-apps:hover .overview-icon {
  background-color: rgba(183, 169, 255, 0.16); border-radius: 16px; }
#dashtodockContainer .dash-item-container .overview-tile:active .overview-icon { background-color: rgba(124, 108, 255, 0.34); }

/* ===== Barre du haut en pilules flottantes =====
   La barre elle-même est transparente ; les groupes gauche et droit flottent chacun dans
   une capsule de verre, à la même hauteur que l'îlot central. */
#panel, #panel:overview, #panel.transparent-panel, #panel.dark-panel {
  background-color: transparent !important;
  box-shadow: none !important;
  height: 42px; }
#panel #panelLeft, #panel #panelRight {
  background-color: rgba(12, 12, 20, 0.78);
  background-gradient-direction: vertical;
  background-gradient-start: rgba(34, 32, 56, 0.80);
  background-gradient-end: rgba(12, 12, 20, 0.80);
  border: 1px solid rgba(183, 169, 255, 0.18);
  border-radius: 999px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  margin-top: 4px; margin-bottom: 4px;
  padding: 0 4px; }
#panel #panelLeft { margin-left: 8px; }
#panel #panelRight { margin-right: 8px; }
#panel .panel-button { border-radius: 999px; margin: 3px 1px; -natural-hpadding: 9px; -minimum-hpadding: 6px; }
#panel .panel-button:hover { background-color: rgba(183, 169, 255, 0.14); box-shadow: none; }
#panel .panel-button:active, #panel .panel-button:checked, #panel .panel-button:focus {
  background-color: rgba(124, 108, 255, 0.30); box-shadow: none; }
/* l'horloge : petite pastille Éclipse en tête de la capsule de droite */
#panel #panelRight .clock {
  background-color: rgba(124, 108, 255, 0.20);
  border-radius: 999px;
  padding: 0 12px; margin: 0 1px;
  color: #ECEBFA; font-weight: 600; font-feature-settings: "tnum"; }
#panel #panelRight .clock-display:hover .clock { background-color: rgba(124, 108, 255, 0.32); }
#panel.unlock-screen #panelLeft, #panel.login-screen #panelLeft { background-color: transparent; border-color: transparent; box-shadow: none; }

/* Alt+Tab, sélecteur d'espaces, bulles volume/luminosité : verre Éclipse */
.switcher-list, .workspace-switcher, .osd-window, .resize-popup {
  background-color: rgba(14, 14, 22, 0.90);
  border: 1px solid rgba(183, 169, 255, 0.14);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45); }
.switcher-list { border-radius: 26px; }
.switcher-list .item-box { border-radius: 18px; }
.switcher-list .item-box:selected { background-color: rgba(124, 108, 255, 0.30); }
.switcher-list .item-box:hover { background-color: rgba(236, 235, 250, 0.07); }
.switcher-list .thumbnail-box { border-radius: 12px; }
.osd-window { border-radius: 999px; color: #ECEBFA; }
.osd-window .level, .osd-window .level:ltr, .osd-window .level:rtl {
  -barlevel-background-color: rgba(236, 235, 250, 0.12);
  -barlevel-active-background-color: #B7A9FF;
  -barlevel-overdrive-color: #FF4D8D; }
.ws-switcher-indicator:active, .workspace-switcher .ws-switcher-active-up, .workspace-switcher .ws-switcher-active-down {
  background-color: #7C6CFF; }

/* Écran de verrouillage : grande heure façon iOS / macOS */
.unlock-dialog-clock { color: #ECEBFA; }
.unlock-dialog-clock .unlock-dialog-clock-time {
  font-family: "Inter Display", "Inter", sans-serif;
  font-size: 7.4em;
  font-weight: 600 !important; }
.unlock-dialog-clock .unlock-dialog-clock-date {
  font-family: "Inter", sans-serif;
  font-size: 1.35em;
  font-weight: 500 !important;
  color: #D9D2FF; }
.unlock-dialog-clock .unlock-dialog-clock-hint {
  background-color: rgba(14, 14, 22, 0.55);
  border: 1px solid rgba(183, 169, 255, 0.14);
  color: #A9A9C2; }
.unlock-dialog .login-dialog-prompt-entry { border-radius: 999px; }
.unlock-dialog .login-dialog-prompt-entry:focus { border-color: #7C6CFF; }
CSS
  cat > "$THEME_DIR/index.theme" <<EOF
[Desktop Entry]
Type=X-GNOME-Metatheme
Name=Shadow
Comment=Shadow OS — palette Éclipse
EOF
  ok "thème shell Shadow généré ($(wc -l < "$THEME_DIR/gnome-shell/gnome-shell.css") lignes)"
  # les feuilles d'extensions fusionnées dans le thème (verrouillage rapide) doivent y être remises
  local fusion; fusion="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../systeme/perf/fusionner-css.py"
  if [ -x "$fusion" ] && compgen -G "$HOME/.local/share/gnome-shell/extensions/*/stylesheet.css.fusionnee" >/dev/null; then
    "$fusion" appliquer >/dev/null && ok "feuilles d'extensions refusionnées"
  fi
}

bloc_gtk(){ # fichier
  local f="$1"; mkdir -p "$(dirname "$f")"; touch "$f"
  python3 - "$f" "$DEBUT" "$FIN" <<'PY'
import sys,re
f,a,b=sys.argv[1:4]; s=open(f).read()
s=re.sub(re.escape(a)+r'.*?'+re.escape(b)+r'\n?','',s,flags=re.S).rstrip('\n')
open(f,'w').write(s+('\n' if s else ''))
PY
  cat >> "$f" <<EOF
$DEBUT
/* Shadow · palette Éclipse */
@define-color accent_color $AURA;
@define-color accent_bg_color $ECLIPSE;
@define-color accent_fg_color #ffffff;
@define-color window_bg_color $ENCRE;
@define-color window_fg_color $TEXTE;
@define-color view_bg_color $NUIT;
@define-color view_fg_color $TEXTE;
@define-color headerbar_bg_color $ENCRE;
@define-color headerbar_fg_color $TEXTE;
@define-color headerbar_border_color $VIDE;
@define-color headerbar_backdrop_color $ENCRE;
@define-color card_bg_color $ARDOISE;
@define-color card_fg_color $TEXTE;
@define-color dialog_bg_color $NUIT;
@define-color dialog_fg_color $TEXTE;
@define-color popover_bg_color $ARDOISE;
@define-color popover_fg_color $TEXTE;
@define-color sidebar_bg_color $VIDE;
@define-color sidebar_fg_color $TEXTE;
@define-color sidebar_backdrop_color $VIDE;
@define-color secondary_sidebar_bg_color $NUIT;
@define-color destructive_color $BRAISE;
@define-color destructive_bg_color $BRAISE;
@define-color success_color $JADE;
@define-color warning_color $SOLEIL;
@define-color error_color $BRAISE;
$FIN
EOF
}

cle(){ "$@" 2>/dev/null || echo "?"; }
ICI="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
# ── Barre du haut : logo Shadow + pastilles d'espaces de travail ─────────────
SB_KEYS=(active-workspace-background-color active-workspace-text-color inactive-workspace-background-color
         inactive-workspace-text-color empty-workspace-text-color application-styles)
barre(){
  if [ ! -f "$SAUV_DIR/barre.txt" ]; then
    { for k in "${SB_KEYS[@]}"; do printf 'sb|%s|%s\n' "$k" "$("${SB[@]}" get $SBA "$k")"; done
      for k in use-custom-icon custom-icon-path; do printf 'lm|%s|%s\n' "$k" "$("${LM[@]}" get $LMS "$k")"; done
    } > "$SAUV_DIR/barre.txt"
  fi
  local ico="$HOME/.local/share/icons/hicolor/scalable/apps"
  mkdir -p "$ico"
  command cp -f "$ICI/../identite/icones/shadow-symbolic.svg" "$ico/shadow-os-eclipse-symbolic.svg"
  "${LM[@]}" set $LMS custom-icon-path "$ico/shadow-os-eclipse-symbolic.svg"
  "${LM[@]}" set $LMS use-custom-icon true
  local act='rgba(124,108,255,1)' act_t='rgba(255,255,255,1)' ina='rgba(236,235,250,0.07)'
  local ina_t='rgba(236,235,250,0.85)' vide_t='rgba(169,169,194,0.45)'
  "${SB[@]}" set $SBA active-workspace-background-color "$act"
  "${SB[@]}" set $SBA active-workspace-text-color "$act_t"
  "${SB[@]}" set $SBA inactive-workspace-background-color "$ina"
  "${SB[@]}" set $SBA inactive-workspace-text-color "$ina_t"
  "${SB[@]}" set $SBA empty-workspace-text-color "$vide_t"
  local css; css=$("${SB[@]}" get $SBA application-styles)
  css=${css//rgba(122,162,247,1)/$act}; css=${css//rgba(22,22,30,1)/$act_t}
  css=${css//rgba(192,202,245,0.08)/$ina}; css=${css//rgba(192,202,245,0.9)/$ina_t}
  css=${css//rgba(169,177,214,0.45)/$vide_t}
  "${SB[@]}" set $SBA application-styles "$css"
  ok "logo Shadow dans la barre · pastilles d'espaces en Éclipse"
}
barre_revert(){
  [ -f "$SAUV_DIR/barre.txt" ] || return 0
  while IFS='|' read -r s k v; do
    case "$s" in sb) "${SB[@]}" set $SBA "$k" "$v";; lm) "${LM[@]}" set $LMS "$k" "$v";; esac
  done < "$SAUV_DIR/barre.txt"
}


# ── Thème GTK3/GTK4 « Shadow » : Tokyonight-Dark recoloré en Éclipse ───────────
GTK_SRC="$HOME/.themes/Tokyonight-Dark"
build_gtk(){
  [ -d "$GTK_SRC/gtk-4.0" ] || { echo "thème source introuvable ($GTK_SRC)" >&2; exit 1; }
  for v in gtk-3.0 gtk-4.0; do
    rm -rf "${THEME_DIR:?}/$v"; mkdir -p "$THEME_DIR/$v"
    command cp -rL "$GTK_SRC/$v/." "$THEME_DIR/$v/"
  done
  python3 - "$THEME_DIR" "$DEBUT" "$FIN" <<'PY'
import sys, re, pathlib
root, a, b = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
hexmap = {  # Tokyonight → Éclipse
  '1a1b26':'0E0E16', '15161e':'07070B', '14141f':'0B0B12', '1f2231':'14141F', '262732':'1A1A28',
  '292e42':'232334', '323449':'1A1A28', '43444e':'2C2C40', '4b4c5f':'34344C', '5e5c64':'4A4A66',
  'e9e9ed':'ECEBFA', 'e1e2e7':'E4E3F4', 'e2e3e8':'E4E3F4', 'c0caf5':'ECEBFA',
  '27a1b9':'7C6CFF', '4aafca':'9488FF', '247d92':'6E5DF2',
  '2e7de9':'8D7FFF', '1c71d8':'6E5DF2', '2861c6':'5B4BE0', '7aa2f7':'8D7FFF',
  'f52a65':'FF4D8D', 'e10b49':'E8336F', 'f41253':'E8336F', 'f7768e':'FF4D8D',
}
rgbamap = {
  (26,27,38):(14,14,22), (39,161,185):(124,108,255), (245,42,101):(255,77,141),
  (46,125,233):(141,127,255), (20,21,29):(11,11,18), (50,52,73):(26,26,40),
  (36,125,146):(110,93,242), (65,72,104):(52,52,76), (41,46,66):(35,35,52),
  (233,233,237):(236,235,250),
}
hexre = re.compile(r'#([0-9a-fA-F]{6})\b')
rgbre = re.compile(r'rgba?\((\d+),\s*(\d+),\s*(\d+)')
blk = re.compile(re.escape(a)+r'.*?'+re.escape(b)+r'\n?', re.S)
n = 0
for f in root.glob('gtk-*/**/*.css'):
    t = f.read_text(errors='ignore'); t = blk.sub('', t)
    t = hexre.sub(lambda m: '#'+hexmap.get(m.group(1).lower(), m.group(1)), t)
    def rg(m):
        k = tuple(int(x) for x in m.groups())
        v = rgbamap.get(k, k)
        return m.group(0).split('(')[0] + '(%d, %d, %d' % v
    t = rgbre.sub(rg, t)
    f.write_text(t); n += 1
print(n)
PY
  # palette libadwaita à la fin des feuilles GTK4 (les apps libadwaita ignorent gtk-theme)
  for f in "$THEME_DIR/gtk-4.0/gtk.css" "$THEME_DIR/gtk-4.0/gtk-dark.css"; do bloc_gtk "$f"; done
  ok "thème GTK Shadow généré (gtk-3.0 + gtk-4.0)"
}

lier_gtk4(){ # pointe ~/.config/gtk-4.0 vers un thème
  local cible="$1"
  for l in gtk.css gtk-dark.css assets; do
    [ -e "$cible/gtk-4.0/$l" ] || continue
    [ -e "$HOME/.config/gtk-4.0/$l" ] && [ ! -L "$HOME/.config/gtk-4.0/$l" ] && \
      command cp -rf "$HOME/.config/gtk-4.0/$l" "$SAUV_DIR/gtk4-$l.orig"
    ln -sfn "$cible/gtk-4.0/$l" "$HOME/.config/gtk-4.0/$l"
  done
}

apply(){
  titre "Sauvegarde"
  mkdir -p "$SAUV_DIR"
  if [ -f "$SAUV_DIR/reglages.txt" ]; then ok "sauvegarde d'origine déjà présente, conservée"; else
  for f in "$GTK4" "$GTK3"; do [ -f "$f" ] && command cp -f "$f" "$SAUV_DIR/$(basename "$(dirname "$f")").css"; done
  { echo "user-theme=$(cle gsettings get org.gnome.shell.extensions.user-theme name)"
    echo "accent=$(cle gsettings get org.gnome.desktop.interface accent-color)"
    echo "ts-border=$(cle "${TS[@]}" get org.gnome.shell.extensions.tilingshell window-border-color)"
    echo "ts-custom=$(cle "${TS[@]}" get org.gnome.shell.extensions.tilingshell window-use-custom-border-color)"
    echo "dock-dots=$(cle "${DTD[@]}" get org.gnome.shell.extensions.dash-to-dock custom-theme-running-dots-color)"
  } > "$SAUV_DIR/reglages.txt"
  ok "état précédent → $SAUV_DIR"; fi
  [ -f "$SAUV_DIR/gtk-theme.txt" ] || gsettings get org.gnome.desktop.interface gtk-theme > "$SAUV_DIR/gtk-theme.txt"
  [ -f "$SAUV_DIR/liens-gtk4.txt" ] || for l in gtk.css gtk-dark.css assets; do
    echo "$l -> $(readlink "$HOME/.config/gtk-4.0/$l" 2>/dev/null)"; done > "$SAUV_DIR/liens-gtk4.txt"

  titre "Thème du shell"
  build
  gsettings set org.gnome.desktop.interface accent-color 'purple'
  gsettings set org.gnome.shell.extensions.user-theme name 'Shadow'
  ok "shell = Shadow · accent système = violet (le plus proche, imposé aux tuiles par GNOME 50)"

  titre "Applis GTK3 / GTK4 / libadwaita"
  build_gtk
  lier_gtk4 "$THEME_DIR"
  gsettings set org.gnome.desktop.interface gtk-theme 'Shadow'
  [ -L "$GTK3" ] || bloc_gtk "$GTK3"
  ok "gtk-theme = Shadow · ~/.config/gtk-4.0 → ~/.themes/Shadow (relancer les applis ouvertes)"

  titre "Barre du haut"
  barre

  titre "Tuiles et dock"
  "${TS[@]}" set org.gnome.shell.extensions.tilingshell window-use-custom-border-color true
  "${TS[@]}" set org.gnome.shell.extensions.tilingshell window-border-color "$ECLIPSE"
  "${DTD[@]}" set org.gnome.shell.extensions.dash-to-dock custom-theme-running-dots-color "$AURA"
  ok "liseré des tuiles $ECLIPSE · pastilles du dock $AURA"
}

revert(){
  [ -f "$SAUV_DIR/reglages.txt" ] || { echo "aucune sauvegarde ($SAUV_DIR)" >&2; exit 1; }
  get(){ grep "^$1=" "$SAUV_DIR/reglages.txt" | cut -d= -f2-; }
  gsettings set org.gnome.shell.extensions.user-theme name "$(get user-theme)"
  gsettings set org.gnome.desktop.interface accent-color "$(get accent)"
  "${TS[@]}" set org.gnome.shell.extensions.tilingshell window-border-color "$(get ts-border)"
  "${TS[@]}" set org.gnome.shell.extensions.tilingshell window-use-custom-border-color "$(get ts-custom)"
  "${DTD[@]}" set org.gnome.shell.extensions.dash-to-dock custom-theme-running-dots-color "$(get dock-dots)"
  [ -f "$SAUV_DIR/gtk-theme.txt" ] && gsettings set org.gnome.desktop.interface gtk-theme "$(cat "$SAUV_DIR/gtk-theme.txt")"
  if [ -f "$SAUV_DIR/liens-gtk4.txt" ]; then
    while read -r l _ cible; do [ -n "$cible" ] && ln -sfn "$cible" "$HOME/.config/gtk-4.0/$l"; done < "$SAUV_DIR/liens-gtk4.txt"
  fi
  [ ! -L "$GTK3" ] && [ -f "$SAUV_DIR/gtk-3.0.css" ] && command cp -f "$SAUV_DIR/gtk-3.0.css" "$GTK3"
  barre_revert
  ok "état d'avant Éclipse restauré"
}

case "${1:-}" in
  apply) apply ;;
  revert) revert ;;
  build) build; build_gtk ;;
  *) echo "usage : eclipse.sh apply|revert|build"; exit 1 ;;
esac
