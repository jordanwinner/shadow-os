#!/usr/bin/env python3
"""Écran tactile — active ou désactive l'écran tactile (Shadow OS, GTK 4 + libadwaita).

La bascule passe par /usr/local/libexec/shadow-ecran-tactile (via pkexec,
autorisé sans mot de passe pour la session active). Le choix est conservé
au redémarrage.
"""
import os
import sys

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

APP_ID = 'os.shadow.EcranTactile'
ICI = os.path.dirname(os.path.realpath(__file__))
ASSISTANT = '/usr/local/libexec/shadow-ecran-tactile'
DRAPEAU = '/etc/shadow-os/ecran-tactile-desactive'
DEBUG = bool(os.environ.get('ET_DEBUG'))


def trace(*a):
    if DEBUG:
        print('[et]', *a, file=sys.stderr, flush=True)

CSS = """
.et-badge {
  min-width: 132px; min-height: 132px;
  border-radius: 999px;
  background-color: alpha(@window_fg_color, 0.06);
  border: 1px solid alpha(@window_fg_color, 0.10);
  transition: all 320ms cubic-bezier(0.22, 1, 0.36, 1);
}
.et-badge image { color: alpha(@window_fg_color, 0.35); transition: all 320ms ease; }
.et-badge.actif {
  background-image: linear-gradient(135deg, #7C6CFF, #FF4D8D);
  border-color: transparent;
  box-shadow: 0 14px 40px alpha(#7C6CFF, 0.38);
}
.et-badge.actif image { color: white; }
.et-titre { font-size: 30px; font-weight: 800; letter-spacing: -0.4px; }
.et-etat { font-size: 17px; font-weight: 600; color: alpha(@window_fg_color, 0.55); }
.et-etat.actif { color: #9B8CFF; }
.et-note { font-size: 14px; color: alpha(@window_fg_color, 0.5); }
.et-liste row { min-height: 64px; }
.et-liste row .title { font-size: 16px; font-weight: 600; }
"""


def est_actif():
    return not os.path.exists(DRAPEAU)


class Fenetre(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Écran tactile')
        self.set_default_size(460, 560)
        self.set_resizable(False)
        self._en_cours = False
        self._ignore_signal = False

        self.toasts = Adw.ToastOverlay()
        vue = Adw.ToolbarView()
        entete = Adw.HeaderBar()
        entete.set_show_title(False)
        vue.add_top_bar(entete)

        boite = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        boite.set_margin_start(36)
        boite.set_margin_end(36)
        boite.set_margin_bottom(36)
        boite.set_valign(Gtk.Align.CENTER)
        boite.set_vexpand(True)

        self.badge = Gtk.Box()
        self.badge.add_css_class('et-badge')
        self.badge.set_halign(Gtk.Align.CENTER)
        icone = Gtk.Image.new_from_icon_name('os.shadow.EcranTactile-symbolic')
        icone.set_pixel_size(64)
        icone.set_hexpand(True)
        icone.set_vexpand(True)
        self.badge.append(icone)
        boite.append(self.badge)

        titre = Gtk.Label(label='Écran tactile')
        titre.add_css_class('et-titre')
        titre.set_margin_top(28)
        boite.append(titre)

        self.etat = Gtk.Label()
        self.etat.add_css_class('et-etat')
        self.etat.set_margin_top(6)
        boite.append(self.etat)

        liste = Gtk.ListBox()
        liste.add_css_class('boxed-list')
        liste.add_css_class('et-liste')
        liste.set_selection_mode(Gtk.SelectionMode.NONE)
        liste.set_margin_top(32)
        self.ligne = Adw.SwitchRow(title='Activer l’écran tactile')
        self.ligne.set_subtitle('Toucher, défiler et zoomer au doigt')
        self.spinner = Adw.Spinner()
        self.spinner.set_visible(False)
        self.ligne.add_suffix(self.spinner)
        self.ligne.connect('notify::active', self._sur_bascule)
        liste.append(self.ligne)
        boite.append(liste)

        note = Gtk.Label(label='Ton choix est conservé au redémarrage.')
        note.add_css_class('et-note')
        note.set_margin_top(14)
        boite.append(note)

        vue.set_content(boite)
        self.toasts.set_child(vue)
        self.set_content(self.toasts)

        # Suit les changements faits ailleurs (commande ecran-tactile, autre fenêtre)
        self._moniteur = Gio.File.new_for_path(os.path.dirname(DRAPEAU)).monitor_directory(
            Gio.FileMonitorFlags.NONE, None)
        self._moniteur.connect('changed', lambda *a: self._rafraichir())

        self._rafraichir()

    def _rafraichir(self):
        if self._en_cours:
            return
        actif = est_actif()
        self._ignore_signal = True
        self.ligne.set_active(actif)
        self._ignore_signal = False
        self.etat.set_label('Activé' if actif else 'Désactivé')
        for w in (self.badge, self.etat):
            if actif:
                w.add_css_class('actif')
            else:
                w.remove_css_class('actif')

    def _sur_bascule(self, ligne, _pspec):
        trace('bascule', ligne.get_active(), 'ignore', self._ignore_signal, 'en_cours', self._en_cours)
        if self._ignore_signal or self._en_cours:
            return
        voulu = ligne.get_active()
        if voulu == est_actif():
            return
        self._en_cours = True
        self.ligne.set_sensitive(False)
        self.spinner.set_visible(True)
        self.etat.set_label('Activation…' if voulu else 'Désactivation…')
        try:
            proc = Gio.Subprocess.new(
                ['pkexec', ASSISTANT, 'on' if voulu else 'off'],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
        except GLib.Error as e:
            self._fin(voulu, False, e.message)
            return
        proc.communicate_utf8_async(None, None, self._termine, voulu)

    def _termine(self, proc, res, voulu):
        try:
            ok, _out, err = proc.communicate_utf8_finish(res)
            ok = ok and proc.get_successful()
        except GLib.Error as e:
            ok, err = False, e.message
        self._fin(voulu, ok, (err or '').strip())

    def _fin(self, voulu, ok, erreur):
        trace('fin', voulu, ok, erreur)
        self._en_cours = False
        self.ligne.set_sensitive(True)
        self.spinner.set_visible(False)
        self._rafraichir()
        if ok:
            msg = 'Écran tactile activé' if voulu else 'Écran tactile désactivé'
        elif 'aucun écran tactile' in erreur:
            msg = 'Aucun écran tactile détecté'
        elif 'dismissed' in erreur.lower() or 'not authorized' in erreur.lower():
            msg = 'Autorisation refusée'
        else:
            msg = 'Échec : ' + (erreur.splitlines()[-1] if erreur else 'erreur inconnue')
        toast = Adw.Toast(title=msg)
        toast.set_timeout(2)
        self.toasts.add_toast(toast)


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_startup(self):
        Adw.Application.do_startup(self)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        affichage = Gdk.Display.get_default()
        theme = Gtk.IconTheme.get_for_display(affichage)
        theme.add_search_path(os.path.join(ICI, 'icones'))
        css = Gtk.CssProvider()
        css.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            affichage, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        quitter = Gio.SimpleAction.new('quitter', None)
        quitter.connect('activate', lambda *a: self.quit())
        self.add_action(quitter)
        self.set_accels_for_action('app.quitter', ['<Control>q', '<Control>w', 'Escape'])

    def do_activate(self):
        fen = self.get_active_window() or Fenetre(self)
        fen.present()


if __name__ == '__main__':
    sys.exit(App().run(sys.argv))
