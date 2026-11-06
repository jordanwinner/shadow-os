#!/usr/bin/env bash
# Thème « Shadow » — harmonise tout le bureau GNOME en un dark/hacker cohérent.
#   apply    : sauvegarde l'état actuel puis applique le thème Shadow
#   revert   : restaure la dernière sauvegarde
#   status   : affiche l'état courant
#   save     : fait juste une sauvegarde horodatée (sans rien changer)
# Aucun sudo. Tout passe par gsettings/dconf + fichiers dans ~/.config.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=palette.sh
source "$HERE/palette.sh"

STATE_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/shadow-desktop/theme-backup"
GTK4="$HOME/.config/gtk-4.0/gtk.css"
GTK3="$HOME/.config/gtk-3.0/gtk.css"
MARK_BEGIN="/* >>> SHADOW-DESKTOP >>> */"
MARK_END="/* <<< SHADOW-DESKTOP <<< */"

c_ok(){ printf '  \033[32m✓\033[0m %s\n' "$1"; }
c_info(){ printf '\033[36m%s\033[0m\n' "$1"; }
c_warn(){ printf '  \033[33m!\033[0m %s\n' "$1"; }

# gsettings set, en silence si la clé/schema n'existe pas
gset(){ local s="$1" k="$2" v="$3"
  if gsettings writable "$s" "$k" >/dev/null 2>&1; then gsettings set "$s" "$k" "$v" 2>/dev/null && return 0; fi
  return 0; }

# ─────────────────────────────────────────────────────────── sauvegarde
snapshot(){
  local dir="$STATE_DIR/$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$dir"
  dconf dump /org/gnome/desktop/interface/      > "$dir/interface.dconf"   2>/dev/null || true
  dconf dump /org/gnome/desktop/wm/              > "$dir/wm.dconf"          2>/dev/null || true
  dconf dump /org/gnome/shell/extensions/user-theme/ > "$dir/usertheme.dconf" 2>/dev/null || true
  dconf dump /org/gnome/shell/extensions/dash-to-dock/ > "$dir/dock.dconf"  2>/dev/null || true
  [ -f "$GTK4" ] && cp "$GTK4" "$dir/gtk4.css" 2>/dev/null || true
  [ -f "$GTK3" ] && cp "$GTK3" "$dir/gtk3.css" 2>/dev/null || true
  [ -f "$HOME/.config/kitty/kitty.conf" ] && cp "$HOME/.config/kitty/kitty.conf" "$dir/kitty.conf" 2>/dev/null || true
  echo "$dir" > "$STATE_DIR/latest"
  c_ok "sauvegarde → $dir"
}

# ─────────────────────────────────────────────────── surcharge libadwaita
# Nautilus, Réglages GNOME, Text Editor… (apps GTK4/libadwaita) ignorent le
# thème shell : on leur injecte la palette via gtk.css (bloc délimité, retirable).
write_gtkcss(){
  local f="$1"; mkdir -p "$(dirname "$f")"; touch "$f"
  # retire un ancien bloc Shadow s'il existe, puis ré-ajoute
  if grep -qF "$MARK_BEGIN" "$f" 2>/dev/null; then
    sed -i "/$(printf '%s' "$MARK_BEGIN" | sed 's/[\/*]/\\&/g')/,/$(printf '%s' "$MARK_END" | sed 's/[\/*]/\\&/g')/d" "$f"
    sed -i -e :a -e '/^\n*$/{$d;N;ba}' "$f" 2>/dev/null || true
  fi
  cat >> "$f" <<EOF
$MARK_BEGIN
@define-color accent_color $SHADOW_ACCENT;
@define-color accent_bg_color $SHADOW_ACCENT;
@define-color accent_fg_color $SHADOW_BG;
@define-color window_bg_color $SHADOW_BG;
@define-color window_fg_color $SHADOW_FG;
@define-color view_bg_color $SHADOW_BG_DARK;
@define-color view_fg_color $SHADOW_FG;
@define-color headerbar_bg_color $SHADOW_BG_DARK;
@define-color headerbar_fg_color $SHADOW_FG;
@define-color headerbar_border_color $SHADOW_BG_DARK;
@define-color card_bg_color $SHADOW_BG_CARD;
@define-color card_fg_color $SHADOW_FG;
@define-color dialog_bg_color $SHADOW_BG;
@define-color dialog_fg_color $SHADOW_FG;
@define-color popover_bg_color $SHADOW_BG_CARD;
@define-color popover_fg_color $SHADOW_FG;
@define-color sidebar_bg_color $SHADOW_BG_DARK;
@define-color sidebar_fg_color $SHADOW_FG;
@define-color secondary_sidebar_bg_color $SHADOW_BG_DARK;
@define-color destructive_color $SHADOW_RED;
@define-color success_color $SHADOW_GREEN;
@define-color warning_color $SHADOW_YELLOW;
@define-color error_color $SHADOW_RED;
$MARK_END
EOF
}

strip_gtkcss(){
  local f="$1"; [ -f "$f" ] || return 0
  if grep -qF "$MARK_BEGIN" "$f" 2>/dev/null; then
    sed -i "/$(printf '%s' "$MARK_BEGIN" | sed 's/[\/*]/\\&/g')/,/$(printf '%s' "$MARK_END" | sed 's/[\/*]/\\&/g')/d" "$f"
  fi
}

# ─────────────────────────────────────────────────────────── konsole
write_konsole(){
  local cdir="$HOME/.local/share/konsole"
  command -v konsole >/dev/null 2>&1 || return 0
  mkdir -p "$cdir"
  cat > "$cdir/Shadow.colorscheme" <<EOF
[General]
Description=Shadow (Tokyonight)
Opacity=0.94
Wallpaper=
[Background]
Color=26,27,38
[Foreground]
Color=192,202,245
[Color0]
Color=21,22,30
[Color1]
Color=247,118,142
[Color2]
Color=158,206,106
[Color3]
Color=224,175,104
[Color4]
Color=122,162,247
[Color5]
Color=187,154,247
[Color6]
Color=125,207,255
[Color7]
Color=169,177,214
[Color0Intense]
Color=65,72,104
[Color1Intense]
Color=247,118,142
[Color2Intense]
Color=158,206,106
[Color3Intense]
Color=224,175,104
[Color4Intense]
Color=122,162,247
[Color5Intense]
Color=187,154,247
[Color6Intense]
Color=125,207,255
[Color7Intense]
Color=192,202,245
EOF
  cat > "$cdir/Shadow.profile" <<EOF
[Appearance]
ColorScheme=Shadow
Font=JetBrainsMono Nerd Font,12,-1,5,50,0,0,0,0,0
[General]
Name=Shadow
Parent=FALLBACK/
[Scrolling]
HistoryMode=2
EOF
  c_ok "profil konsole « Shadow » installé (à choisir dans Konsole › Réglages)"
}

# ─────────────────────────────────────────────────────────── apply
apply(){
  c_info "▸ Sauvegarde de l'état actuel"
  snapshot

  c_info "▸ Thème & icônes"
  gset org.gnome.desktop.interface color-scheme 'prefer-dark'
  gset org.gnome.desktop.interface gtk-theme "$SHADOW_GTK_THEME"
  gset org.gnome.desktop.interface icon-theme "$SHADOW_ICON_THEME"
  gset org.gnome.desktop.interface cursor-theme "$SHADOW_CURSOR_THEME"
  gset org.gnome.shell.extensions.user-theme name "$SHADOW_SHELL_THEME"
  c_ok "GTK=$SHADOW_GTK_THEME · icônes=$SHADOW_ICON_THEME · curseur=$SHADOW_CURSOR_THEME · shell=$SHADOW_SHELL_THEME"

  c_info "▸ Polices & rendu (net sur écran HiDPI)"
  gset org.gnome.desktop.interface font-name "$SHADOW_FONT_UI"
  gset org.gnome.desktop.interface monospace-font-name "$SHADOW_FONT_MONO"
  gset org.gnome.desktop.interface document-font-name "$SHADOW_FONT_DOC"
  gset org.gnome.desktop.wm.preferences titlebar-font "$SHADOW_FONT_TITLE"
  gset org.gnome.desktop.interface font-antialiasing 'rgba'
  gset org.gnome.desktop.interface font-hinting 'slight'
  c_ok "UI=$SHADOW_FONT_UI · mono=$SHADOW_FONT_MONO · antialiasing=rgba"

  c_info "▸ Détails d'interface"
  gset org.gnome.desktop.interface clock-show-weekday true
  gset org.gnome.desktop.interface clock-show-seconds true
  gset org.gnome.desktop.interface show-battery-percentage true
  gset org.gnome.desktop.interface enable-animations true
  gset org.gnome.desktop.wm.preferences button-layout 'appmenu:minimize,maximize,close'
  c_ok "horloge (jour+secondes), batterie %, animations"

  c_info "▸ Dock (dash-to-dock) — look flottant translucide"
  gset org.gnome.shell.extensions.dash-to-dock transparency-mode 'DYNAMIC'
  gset org.gnome.shell.extensions.dash-to-dock background-opacity 0.55
  gset org.gnome.shell.extensions.dash-to-dock dash-max-icon-size 44
  gset org.gnome.shell.extensions.dash-to-dock custom-theme-shrink true
  gset org.gnome.shell.extensions.dash-to-dock running-indicator-style 'DOTS'
  gset org.gnome.shell.extensions.dash-to-dock apply-custom-theme false
  gset org.gnome.shell.extensions.dash-to-dock custom-theme-running-dots-color "$SHADOW_ACCENT"
  c_ok "dock translucide dynamique, pastilles accent"

  c_info "▸ Surcharge libadwaita (Nautilus, Réglages, Text Editor…)"
  write_gtkcss "$GTK4"
  write_gtkcss "$GTK3"
  c_ok "palette Tokyonight injectée dans gtk-4.0 et gtk-3.0"

  c_info "▸ Terminal konsole"
  write_konsole

  echo
  c_info "✅ Thème Shadow appliqué."
  c_warn "Les apps GTK déjà ouvertes doivent être relancées pour prendre la nouvelle palette."
  c_warn "Pour un rendu shell complet : Alt+F2 → 'r' (X11) ou déconnexion/reconnexion (Wayland)."
}

# ─────────────────────────────────────────────────────────── revert
revert(){
  local dir; dir="$(cat "$STATE_DIR/latest" 2>/dev/null || true)"
  if [ -z "$dir" ] || [ ! -d "$dir" ]; then
    c_warn "aucune sauvegarde trouvée dans $STATE_DIR"; exit 1
  fi
  c_info "▸ Restauration depuis $dir"
  [ -f "$dir/interface.dconf" ] && dconf load /org/gnome/desktop/interface/ < "$dir/interface.dconf" 2>/dev/null && c_ok "interface"
  [ -f "$dir/wm.dconf" ]        && dconf load /org/gnome/desktop/wm/ < "$dir/wm.dconf" 2>/dev/null && c_ok "wm"
  [ -f "$dir/usertheme.dconf" ] && dconf load /org/gnome/shell/extensions/user-theme/ < "$dir/usertheme.dconf" 2>/dev/null && c_ok "thème shell"
  [ -f "$dir/dock.dconf" ]      && dconf load /org/gnome/shell/extensions/dash-to-dock/ < "$dir/dock.dconf" 2>/dev/null && c_ok "dock"
  if [ -f "$dir/gtk4.css" ]; then cp "$dir/gtk4.css" "$GTK4"; c_ok "gtk-4.0 restauré"; else strip_gtkcss "$GTK4"; c_ok "bloc Shadow retiré de gtk-4.0"; fi
  if [ -f "$dir/gtk3.css" ]; then cp "$dir/gtk3.css" "$GTK3"; c_ok "gtk-3.0 restauré"; else strip_gtkcss "$GTK3"; c_ok "bloc Shadow retiré de gtk-3.0"; fi
  echo
  c_info "✅ État précédent restauré. Relance tes apps / reconnecte-toi pour le shell."
}

status(){
  c_info "── État courant ──"
  printf "  GTK      : %s\n" "$(gsettings get org.gnome.desktop.interface gtk-theme 2>/dev/null)"
  printf "  Shell    : %s\n" "$(gsettings get org.gnome.shell.extensions.user-theme name 2>/dev/null)"
  printf "  Icônes   : %s\n" "$(gsettings get org.gnome.desktop.interface icon-theme 2>/dev/null)"
  printf "  Curseur  : %s\n" "$(gsettings get org.gnome.desktop.interface cursor-theme 2>/dev/null)"
  printf "  Police   : %s / %s\n" "$(gsettings get org.gnome.desktop.interface font-name 2>/dev/null)" "$(gsettings get org.gnome.desktop.interface monospace-font-name 2>/dev/null)"
  printf "  libadwaita: %s\n" "$(grep -qF "$MARK_BEGIN" "$GTK4" 2>/dev/null && echo 'Shadow actif' || echo 'non modifié')"
  local dir; dir="$(cat "$STATE_DIR/latest" 2>/dev/null || true)"
  printf "  Sauvegarde: %s\n" "${dir:-aucune}"
}

case "${1:-apply}" in
  apply)  apply ;;
  revert) revert ;;
  status) status ;;
  save)   snapshot ;;
  *) echo "usage: shadow-theme.sh [apply|revert|status|save]"; exit 1 ;;
esac
