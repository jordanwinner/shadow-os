#!/usr/bin/env python3
"""Énergie — choisit le mode d'énergie du portable (Shadow OS, GTK 4 + libadwaita).

Trois modes : Frais (silencieux, économe), Équilibré, Performance. Le
changement passe par /usr/local/libexec/shadow-energie (via pkexec, autorisé
sans mot de passe pour la session active) et il est conservé au redémarrage.
"""
import glob
import os
import sys

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

APP_ID = 'os.shadow.Energie'
ICI = os.path.dirname(os.path.realpath(__file__))
ASSISTANT = '/usr/local/libexec/shadow-energie'
ETAT = '/etc/shadow-os/energie-profil'
CPU = '/sys/devices/system/cpu'
DEBUG = bool(os.environ.get('EN_DEBUG'))

# identifiant, titre, description, icône
MODES = (
    ('frais', 'Frais',
     'Silencieux et économe. Turbo coupé sur batterie, ventilation au minimum.',
     'power-profile-power-saver-symbolic'),
    ('equilibre', 'Équilibré',
     'Fluide au quotidien. Turbo actif, ventilation normale.',
     'power-profile-balanced-symbolic'),
    ('performance', 'Performance',
     'Toute la puissance sur secteur. Chauffe et consomme davantage.',
     'power-profile-performance-symbolic'),
)
TITRES = {m[0]: m[1] for m in MODES}
ICONES = {m[0]: m[3] for m in MODES}
PREFERENCES = {
    'power': 'économie maximale',
    'balance_power': 'priorité économie',
    'balance_performance': 'priorité fluidité',
    'performance': 'puissance maximale',
    'default': 'réglage par défaut',
}


def trace(*a):
    if DEBUG:
        print('[en]', *a, file=sys.stderr, flush=True)


CSS = """
.en-badge {
  min-width: 112px; min-height: 112px;
  border-radius: 999px;
  border: 1px solid transparent;
  transition: all 420ms cubic-bezier(0.22, 1, 0.36, 1);
}
.en-badge image { color: white; }
.en-badge.frais {
  background-image: linear-gradient(135deg, #36D1DC, #7C6CFF);
  box-shadow: 0 14px 40px alpha(#36D1DC, 0.30);
}
.en-badge.equilibre {
  background-image: linear-gradient(135deg, #7C6CFF, #FF4D8D);
  box-shadow: 0 14px 40px alpha(#7C6CFF, 0.38);
}
.en-badge.performance {
  background-image: linear-gradient(135deg, #FF4D8D, #FFA24D);
  box-shadow: 0 14px 40px alpha(#FF4D8D, 0.36);
}
.en-titre { font-size: 30px; font-weight: 800; letter-spacing: -0.4px; }
.en-etat { font-size: 17px; font-weight: 600; transition: color 320ms ease; }
.en-etat.frais { color: #5FD8E6; }
.en-etat.equilibre { color: #9B8CFF; }
.en-etat.performance { color: #FF7FA8; }

button.en-carte {
  padding: 14px 16px;
  border-radius: 18px;
  background-color: alpha(@window_fg_color, 0.05);
  background-image: none;
  border: 1px solid alpha(@window_fg_color, 0.08);
  box-shadow: none;
  font-weight: normal;
  transition: all 260ms cubic-bezier(0.22, 1, 0.36, 1);
}
button.en-carte:hover { background-color: alpha(@window_fg_color, 0.09); }
button.en-carte:active { background-color: alpha(@window_fg_color, 0.13); }
button.en-carte:focus-visible { outline: 2px solid alpha(@window_fg_color, 0.28); outline-offset: 2px; }
button.en-carte.frais:checked {
  background-color: alpha(#36D1DC, 0.12);
  border-color: alpha(#36D1DC, 0.60);
  box-shadow: 0 8px 26px alpha(#36D1DC, 0.14);
}
button.en-carte.equilibre:checked {
  background-color: alpha(#7C6CFF, 0.15);
  border-color: alpha(#7C6CFF, 0.65);
  box-shadow: 0 8px 26px alpha(#7C6CFF, 0.18);
}
button.en-carte.performance:checked {
  background-color: alpha(#FF4D8D, 0.13);
  border-color: alpha(#FF4D8D, 0.60);
  box-shadow: 0 8px 26px alpha(#FF4D8D, 0.16);
}
.en-puce {
  min-width: 46px; min-height: 46px;
  border-radius: 999px;
  background-color: alpha(@window_fg_color, 0.07);
  transition: all 260ms ease;
}
.en-puce image { color: alpha(@window_fg_color, 0.60); transition: color 260ms ease; }
button.en-carte:checked .en-puce image { color: white; }
button.en-carte.frais:checked .en-puce { background-image: linear-gradient(135deg, #36D1DC, #7C6CFF); }
button.en-carte.equilibre:checked .en-puce { background-image: linear-gradient(135deg, #7C6CFF, #FF4D8D); }
button.en-carte.performance:checked .en-puce { background-image: linear-gradient(135deg, #FF4D8D, #FFA24D); }
.en-carte-titre { font-size: 16px; font-weight: 700; }
.en-carte-desc { font-size: 13.5px; color: alpha(@window_fg_color, 0.58); }
.en-coche { opacity: 0; transition: opacity 220ms ease; }
button.en-carte:checked .en-coche { opacity: 1; }
button.en-carte.frais .en-coche { color: #5FD8E6; }
button.en-carte.equilibre .en-coche { color: #9B8CFF; }
button.en-carte.performance .en-coche { color: #FF7FA8; }

.en-section {
  font-size: 12px; font-weight: 700; letter-spacing: 1px;
  color: alpha(@window_fg_color, 0.42);
}
.en-tuile {
  padding: 13px 16px;
  border-radius: 16px;
  background-color: alpha(@window_fg_color, 0.05);
  border: 1px solid alpha(@window_fg_color, 0.06);
}
.en-tuile-nom { font-size: 12.5px; font-weight: 600; color: alpha(@window_fg_color, 0.50); }
.en-tuile-val { font-size: 21px; font-weight: 750; font-feature-settings: "tnum"; letter-spacing: -0.2px; }
.en-tuile-sous { font-size: 12.5px; color: alpha(@window_fg_color, 0.50); font-feature-settings: "tnum"; }
.en-note { font-size: 13.5px; color: alpha(@window_fg_color, 0.45); }
"""


def lire(chemin, defaut=''):
    try:
        with open(chemin) as f:
            return f.read().strip()
    except OSError:
        return defaut


def entier(chemin, defaut=0):
    try:
        return int(lire(chemin))
    except ValueError:
        return defaut


def fr(nombre, decimales=1):
    return f'{nombre:.{decimales}f}'.replace('.', ',')


def mode_actuel():
    """Mode enregistré, sinon déduit de l'état réel du matériel."""
    mode = lire(ETAT)
    if mode in TITRES:
        return mode
    plateforme = lire('/sys/firmware/acpi/platform_profile')
    if plateforme in ('quiet', 'cool'):
        return 'frais'
    if plateforme == 'performance':
        return 'performance'
    return 'equilibre'


def _premier(motif):
    trouve = sorted(glob.glob(motif))
    return trouve[0] if trouve else None


ZONE_CPU = next((os.path.dirname(t) for t in glob.glob('/sys/class/thermal/thermal_zone*/type')
                 if lire(t) == 'x86_pkg_temp'), None)
VENTILATEUR = _premier('/sys/class/hwmon/hwmon*/fan1_input')
BATTERIE = _premier('/sys/class/power_supply/BAT*')
FREQUENCES = sorted(glob.glob(CPU + '/cpu[0-9]*/cpufreq/scaling_cur_freq'))


def mesures():
    """Relevé instantané : quatre tuiles (valeur, sous-titre)."""
    m = {}
    # Processeur
    actuelles = [entier(f) for f in FREQUENCES]
    pointe = max(actuelles) / 1e6 if actuelles else 0
    plafond = entier(CPU + '/cpu0/cpufreq/cpuinfo_max_freq') / 1e6
    m['cpu'] = (f'{fr(pointe)} GHz', f'plafond {fr(plafond)} GHz' if plafond else '')
    # Température
    temp = entier(ZONE_CPU + '/temp') / 1000 if ZONE_CPU else 0
    if VENTILATEUR:
        tours = entier(VENTILATEUR)
        sous = 'ventilateur à l’arrêt' if tours == 0 else f'ventilateur {tours} tr/min'
    else:
        sous = ''
    m['temp'] = (f'{temp:.0f} °C' if temp else '—', sous)
    # Turbo
    turbo = lire(CPU + '/intel_pstate/no_turbo', '?')
    pref = lire(CPU + '/cpu0/cpufreq/energy_performance_preference')
    m['turbo'] = ({'0': 'Actif', '1': 'Coupé'}.get(turbo, '—'), PREFERENCES.get(pref, pref))
    # Alimentation
    if BATTERIE:
        etat = lire(BATTERIE + '/status')
        charge = lire(BATTERIE + '/capacity', '?')
        watts = entier(BATTERIE + '/current_now') * entier(BATTERIE + '/voltage_now') / 1e12
        sur_batterie = etat == 'Discharging'
        sous = f'{charge} %'
        if sur_batterie and watts > 0.2:
            sous += f' · {fr(watts)} W'
        elif etat == 'Charging':
            sous += ' · en charge'
        m['alim'] = ('Batterie' if sur_batterie else 'Secteur', sous)
    else:
        m['alim'] = ('Secteur', '')
    return m


class Carte(Gtk.ToggleButton):
    """Carte de mode : pastille, titre, description, coche ou attente."""

    def __init__(self, mode, titre, description, icone):
        super().__init__()
        self.mode = mode
        self.add_css_class('en-carte')
        self.add_css_class(mode)

        ligne = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        puce = Gtk.Box()
        puce.add_css_class('en-puce')
        puce.set_valign(Gtk.Align.CENTER)
        img = Gtk.Image.new_from_icon_name(icone)
        img.set_pixel_size(22)
        img.set_hexpand(True)
        puce.append(img)
        ligne.append(puce)

        textes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        textes.set_hexpand(True)
        textes.set_valign(Gtk.Align.CENTER)
        t = Gtk.Label(label=titre, xalign=0)
        t.add_css_class('en-carte-titre')
        d = Gtk.Label(label=description, xalign=0, wrap=True)
        d.add_css_class('en-carte-desc')
        textes.append(t)
        textes.append(d)
        ligne.append(textes)

        self.pile = Gtk.Stack()
        self.pile.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.pile.set_transition_duration(180)
        self.pile.set_valign(Gtk.Align.CENTER)
        coche = Gtk.Image.new_from_icon_name('object-select-symbolic')
        coche.set_pixel_size(20)
        coche.add_css_class('en-coche')
        self.pile.add_named(coche, 'coche')
        self.pile.add_named(Adw.Spinner(), 'attente')
        ligne.append(self.pile)
        self.set_child(ligne)

    def attente(self, oui):
        self.pile.set_visible_child_name('attente' if oui else 'coche')


class Tuile(Gtk.Box):
    def __init__(self, nom):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.add_css_class('en-tuile')
        self.set_hexpand(True)
        n = Gtk.Label(label=nom, xalign=0)
        n.add_css_class('en-tuile-nom')
        self.valeur = Gtk.Label(xalign=0)
        self.valeur.add_css_class('en-tuile-val')
        self.sous = Gtk.Label(xalign=0, ellipsize=3)
        self.sous.add_css_class('en-tuile-sous')
        self.append(n)
        self.append(self.valeur)
        self.append(self.sous)

    def afficher(self, valeur, sous):
        if self.valeur.get_label() != valeur:
            self.valeur.set_label(valeur)
        if self.sous.get_label() != sous:
            self.sous.set_label(sous)


class Fenetre(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Énergie')
        self.set_default_size(480, -1)
        self.set_resizable(False)
        self._en_cours = False
        self._ignore_signal = False
        self._mode_affiche = None
        self._minuteur = 0

        self.toasts = Adw.ToastOverlay()
        vue = Adw.ToolbarView()
        entete = Adw.HeaderBar()
        entete.set_show_title(False)
        vue.add_top_bar(entete)

        boite = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        boite.set_margin_start(32)
        boite.set_margin_end(32)
        boite.set_margin_bottom(28)

        # En-tête : pastille du mode en cours
        self.badge = Gtk.Box()
        self.badge.add_css_class('en-badge')
        self.badge.set_halign(Gtk.Align.CENTER)
        self.badge.set_vexpand(False)   # sinon l'icône (extensible) étire la pastille
        self.badge.set_margin_top(6)
        self.pile_badge = Gtk.Stack()
        self.pile_badge.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.pile_badge.set_transition_duration(320)
        self.pile_badge.set_hexpand(True)
        self.pile_badge.set_vexpand(True)
        for mode, _t, _d, icone in MODES:
            img = Gtk.Image.new_from_icon_name(icone)
            img.set_pixel_size(52)
            self.pile_badge.add_named(img, mode)
        self.badge.append(self.pile_badge)
        boite.append(self.badge)

        titre = Gtk.Label(label='Énergie')
        titre.add_css_class('en-titre')
        titre.set_margin_top(22)
        boite.append(titre)

        self.etat = Gtk.Label()
        self.etat.add_css_class('en-etat')
        self.etat.set_margin_top(4)
        boite.append(self.etat)

        # Les trois modes
        cartes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        cartes.set_margin_top(26)
        self.cartes = {}
        premiere = None
        for mode, t, d, icone in MODES:
            carte = Carte(mode, t, d, icone)
            if premiere is None:
                premiere = carte
            else:
                carte.set_group(premiere)
            carte.connect('toggled', self._sur_choix)
            self.cartes[mode] = carte
            cartes.append(carte)
        boite.append(cartes)

        # Relevé en direct
        section = Gtk.Label(label='EN DIRECT', xalign=0)
        section.add_css_class('en-section')
        section.set_margin_top(26)
        section.set_margin_start(4)
        boite.append(section)

        grille = Gtk.Grid(column_spacing=10, row_spacing=10, column_homogeneous=True)
        grille.set_margin_top(10)
        self.tuiles = {}
        for i, (cle, nom) in enumerate((('cpu', 'Processeur'), ('temp', 'Température'),
                                        ('turbo', 'Turbo'), ('alim', 'Alimentation'))):
            tuile = Tuile(nom)
            self.tuiles[cle] = tuile
            grille.attach(tuile, i % 2, i // 2, 1, 1)
        boite.append(grille)

        note = Gtk.Label(label='Ton choix est conservé au redémarrage.')
        note.add_css_class('en-note')
        note.set_margin_top(18)
        boite.append(note)

        vue.set_content(boite)
        self.toasts.set_child(vue)
        self.set_content(self.toasts)

        # Suit les changements faits ailleurs (commande shadow-energie, autre fenêtre)
        dossier = Gio.File.new_for_path(os.path.dirname(ETAT))
        self._moniteur = dossier.monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self._moniteur.connect('changed', lambda *a: self._rafraichir())

        # Les mesures ne tournent que lorsque la fenêtre est affichée
        self.connect('map', self._demarrer_mesures)
        self.connect('unmap', self._arreter_mesures)

        self._rafraichir()
        self._mesurer()
        self.set_focus(self.cartes[mode_actuel()])

    # --- mesures en direct ---------------------------------------------------
    def _demarrer_mesures(self, *_a):
        if not self._minuteur:
            self._mesurer()
            self._minuteur = GLib.timeout_add_seconds(2, self._mesurer)

    def _arreter_mesures(self, *_a):
        if self._minuteur:
            GLib.source_remove(self._minuteur)
            self._minuteur = 0

    def _mesurer(self):
        for cle, (valeur, sous) in mesures().items():
            self.tuiles[cle].afficher(valeur, sous)
        return GLib.SOURCE_CONTINUE

    # --- mode en cours ---------------------------------------------------------
    def _rafraichir(self):
        if self._en_cours:
            return
        self._afficher(mode_actuel())

    def _afficher(self, mode, libelle=None):
        self._ignore_signal = True
        self.cartes[mode].set_active(True)
        self._ignore_signal = False
        self.etat.set_label(libelle or f'Mode {TITRES[mode]}')
        if mode != self._mode_affiche:
            for w in (self.badge, self.etat):
                if self._mode_affiche:
                    w.remove_css_class(self._mode_affiche)
                w.add_css_class(mode)
            self.pile_badge.set_visible_child_name(mode)
            self._mode_affiche = mode

    def _sur_choix(self, carte):
        trace('choix', carte.mode, carte.get_active(), 'ignore', self._ignore_signal)
        if self._ignore_signal or self._en_cours or not carte.get_active():
            return
        voulu = carte.mode
        if voulu == mode_actuel() and os.path.exists(ETAT):
            return
        self._en_cours = True
        for c in self.cartes.values():
            c.set_can_target(False)
        carte.attente(True)
        self._afficher(voulu, 'Application…')
        try:
            proc = Gio.Subprocess.new(
                ['pkexec', ASSISTANT, voulu],
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
        for c in self.cartes.values():
            c.set_can_target(True)
            c.attente(False)
        self._rafraichir()
        self._mesurer()
        if ok:
            msg = f'Mode {TITRES[voulu]} appliqué'
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
        # Priorité au-dessus du thème GTK de l'utilisateur (~/.config/gtk-4.0/gtk.css),
        # qui recolore sinon « button:checked ». Les règles ne visent que les classes .en-*.
        Gtk.StyleContext.add_provider_for_display(
            affichage, css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        quitter = Gio.SimpleAction.new('quitter', None)
        quitter.connect('activate', lambda *a: self.quit())
        self.add_action(quitter)
        self.set_accels_for_action('app.quitter', ['<Control>q', '<Control>w', 'Escape'])

    def do_activate(self):
        fen = self.get_active_window() or Fenetre(self)
        fen.present()
        fen.set_focus_visible(False)   # anneau de focus seulement au clavier


if __name__ == '__main__':
    sys.exit(App().run(sys.argv))
