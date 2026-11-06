#!/usr/bin/env python3
"""Bienvenue dans Shadow — présentation du système au premier démarrage (GTK 4 + libadwaita).

  bienvenue.py                     ouvre la présentation
  bienvenue.py --premier-lancement ne s'ouvre que si l'utilisateur ne l'a pas désactivée
"""
import os
import subprocess
import sys

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

ICI = os.path.dirname(os.path.realpath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
LOGO = os.path.join(RACINE, 'identite', 'logo.svg')
ETAT = os.path.expanduser('~/.local/state/shadow-os')
MASQUE = os.path.join(ETAT, 'bienvenue-masquee')
MODE = os.path.expanduser('~/.local/bin/shadow-mode')

CSS = """
.bv-titre { font-size: 40px; font-weight: 700; letter-spacing: -0.4px; }
.bv-sous-titre { font-size: 19px; color: alpha(@window_fg_color, 0.62); }
.bv-carte {
  background-color: alpha(@window_fg_color, 0.04);
  border: 1px solid alpha(#B7A9FF, 0.14);
  border-radius: 18px;
  padding: 28px;
}
.bv-carte.active { border-color: #7C6CFF; background-color: alpha(#7C6CFF, 0.12); }
.bv-carte-titre { font-size: 22px; font-weight: 700; }
.bv-carte-texte { font-size: 15px; color: alpha(@window_fg_color, 0.66); }
.bv-touche {
  font-family: 'JetBrainsMono Nerd Font', monospace;
  font-size: 15px; font-weight: 600;
  padding: 4px 11px; border-radius: 8px;
  background-color: alpha(@window_fg_color, 0.08);
  border: 1px solid alpha(@window_fg_color, 0.12);
  border-bottom-width: 2px;
}
.bv-plus { color: alpha(@window_fg_color, 0.4); }
.bv-pied { padding: 22px 36px 30px 36px; }
.bv-bouton { min-width: 180px; min-height: 48px; font-size: 16px; font-weight: 600; }
.bv-liste row { min-height: 56px; }
.bv-liste row .title { font-size: 16px; }
"""


def lancer(*cmd):
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def mode_courant():
    try:
        return subprocess.run([MODE, 'etat'], capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return 'flottant'


def touches(combo):
    """« Super+Maj+W » → rangée de touches stylées."""
    boite = Gtk.Box(spacing=4, valign=Gtk.Align.CENTER)
    for i, t in enumerate(combo.split('+')):
        if i:
            boite.append(Gtk.Label(label='+', css_classes=['bv-plus']))
        boite.append(Gtk.Label(label=t, css_classes=['bv-touche']))
    return boite


def page(titre, sous_titre, contenu=None, logo=False):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                  valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER,
                  margin_start=40, margin_end=40, hexpand=True, vexpand=True)
    if logo and os.path.isfile(LOGO):
        img = Gtk.Image.new_from_file(LOGO)
        img.set_pixel_size(176)
        img.set_margin_bottom(14)
        box.append(img)
    box.append(Gtk.Label(label=titre, css_classes=['bv-titre'], justify=Gtk.Justification.CENTER, wrap=True))
    box.append(Gtk.Label(label=sous_titre, css_classes=['bv-sous-titre'], justify=Gtk.Justification.CENTER,
                         wrap=True, max_width_chars=60))
    if contenu:
        contenu.set_margin_top(22)
        box.append(contenu)
    return box


class Bienvenue(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Bienvenue dans Shadow', default_width=1100, default_height=820)
        self.set_size_request(860, 700)

        self.carrousel = Adw.Carousel(hexpand=True, vexpand=True, allow_scroll_wheel=False)
        self.carrousel.connect('page-changed', lambda *_: self._maj_boutons())
        for p in (self._page_accueil(), self._page_modes(), self._page_raccourcis(), self._page_fin()):
            self.carrousel.append(p)

        points = Adw.CarouselIndicatorDots(carousel=self.carrousel)
        self.retour = Gtk.Button(label='Retour', css_classes=['pill', 'bv-bouton'])
        self.retour.connect('clicked', lambda *_: self._aller(-1))
        self.suite = Gtk.Button(label='Continuer', css_classes=['pill', 'suggested-action', 'bv-bouton'])
        self.suite.connect('clicked', lambda *_: self._aller(1))
        pied = Gtk.CenterBox(css_classes=['bv-pied'])
        pied.set_start_widget(self.retour)
        pied.set_center_widget(points)
        pied.set_end_widget(self.suite)

        vue = Adw.ToolbarView()
        vue.add_top_bar(Adw.HeaderBar(show_title=False, css_classes=['flat']))
        corps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        corps.append(self.carrousel)
        corps.append(pied)
        vue.set_content(corps)
        self.set_content(vue)

        clavier = Gtk.EventControllerKey()
        clavier.connect('key-pressed', self._touche)
        self.add_controller(clavier)
        self._maj_boutons()

    # ── pages ────────────────────────────────────────────────────────────────
    def _page_accueil(self):
        return page('Bienvenue dans Shadow',
                    'Ton système, pensé pour créer, coder et tester. '
                    'Quelques secondes pour en faire le tour.', logo=True)

    def _page_modes(self):
        grille = Gtk.Box(spacing=20, homogeneous=True, width_request=820)
        self.cartes = {}
        for cle, titre, texte, icone in (
                ('flottant', 'Flottant', 'Fenêtres libres, comme sur macOS.\nSuper + flèches pour les ancrer.',
                 'view-restore-symbolic'),
                ('tuiles', 'Tuiles', 'Les fenêtres se rangent seules, comme sur Omarchy.\n'
                 'Super + flèches pour passer de l’une à l’autre.', 'view-grid-symbolic')):
            carte = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=['bv-carte'])
            carte.append(Gtk.Image(icon_name=icone, pixel_size=44, halign=Gtk.Align.START))
            carte.append(Gtk.Label(label=titre, css_classes=['bv-carte-titre'], xalign=0))
            carte.append(Gtk.Label(label=texte, css_classes=['bv-carte-texte'], xalign=0, wrap=True))
            bouton = Gtk.Button(label=f'Passer en {titre.lower()}', css_classes=['pill'], margin_top=8)
            bouton.connect('clicked', self._choisir_mode, cle)
            carte.append(bouton)
            self.cartes[cle] = carte
            grille.append(carte)
        bas = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, margin_top=18)
        bas.append(Gtk.Label(label='Basculer à tout moment :', css_classes=['bv-carte-texte']))
        bas.append(touches('Super+T'))
        contenu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        contenu.append(grille)
        contenu.append(bas)
        self._marquer_mode(mode_courant())
        return page('Deux façons de travailler', 'Choisis ton style ; tu peux en changer quand tu veux.', contenu)

    def _page_raccourcis(self):
        liste = Gtk.ListBox(css_classes=['boxed-list', 'bv-liste'], selection_mode=Gtk.SelectionMode.NONE, width_request=620)
        for combo, quoi in (('Super', 'Vue d’ensemble'), ('Super+A', 'Toutes les applications'),
                            ('Alt+Espace', 'Rechercher, lancer une appli'), ('Super+T', 'Flottant ⇄ tuiles'),
                            ('Super+Maj+W', 'Fond d’écran suivant'), ('Super+Maj+K', 'Afficher les touches à l’écran')):
            ligne = Adw.ActionRow(title=quoi)
            ligne.add_suffix(touches(combo))
            liste.append(ligne)
        return page('Les raccourcis essentiels', 'Tout Shadow se pilote aussi au clavier.', liste)

    def _page_fin(self):
        boite = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, halign=Gtk.Align.CENTER)
        demarrage = Adw.SwitchRow(title='Afficher au démarrage', active=not os.path.exists(MASQUE))
        demarrage.connect('notify::active', self._basculer_demarrage)
        liste = Gtk.ListBox(css_classes=['boxed-list', 'bv-liste'], selection_mode=Gtk.SelectionMode.NONE, width_request=520)
        liste.append(demarrage)
        boite.append(liste)
        return page('Shadow est prêt', 'Bonne création. Tu retrouveras cette présentation dans Utilitaires › Bienvenue.',
                    boite, logo=True)

    # ── actions ──────────────────────────────────────────────────────────────
    def _choisir_mode(self, _bouton, cle):
        lancer(MODE, cle)
        self._marquer_mode(cle)

    def _marquer_mode(self, cle):
        for k, carte in self.cartes.items():
            (carte.add_css_class if k == cle else carte.remove_css_class)('active')

    def _basculer_demarrage(self, ligne, _p):
        os.makedirs(ETAT, exist_ok=True)
        if ligne.get_active():
            if os.path.exists(MASQUE):
                os.remove(MASQUE)
        else:
            open(MASQUE, 'w').close()

    def _aller(self, sens):
        n = self.carrousel.get_n_pages()
        i = round(self.carrousel.get_position()) + sens
        if i >= n:
            self.close()
            return
        if 0 <= i < n:
            self.carrousel.scroll_to(self.carrousel.get_nth_page(i), True)

    def _maj_boutons(self):
        i = round(self.carrousel.get_position())
        dernier = i >= self.carrousel.get_n_pages() - 1
        self.retour.set_sensitive(i > 0)
        self.retour.set_opacity(1 if i > 0 else 0)
        self.suite.set_label('Commencer' if dernier else 'Continuer')

    def _touche(self, _c, val, _code, _etat):
        if val in (Gdk.KEY_Right, Gdk.KEY_Return):
            self._aller(1)
            return True
        if val == Gdk.KEY_Left:
            self._aller(-1)
            return True
        if val == Gdk.KEY_Escape:
            self.close()
            return True
        return False


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id='os.shadow.Bienvenue', flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.connect('activate', self._activer)

    def _activer(self, _app):
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        css = Gtk.CssProvider()
        css.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        (self.get_active_window() or Bienvenue(self)).present()


if __name__ == '__main__':
    if '--premier-lancement' in sys.argv:
        if os.path.exists(MASQUE):
            sys.exit(0)
        sys.argv.remove('--premier-lancement')
    GLib.set_prgname('shadow-bienvenue')
    sys.exit(App().run(sys.argv))
