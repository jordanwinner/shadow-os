#!/usr/bin/env python3
"""Centre Shadow — tous les réglages propres à Shadow dans une seule fenêtre.

Pages : Accueil, Modes, Énergie, Apparence, Arsenal, Système. Les pages Modes
et Énergie sont les panneaux des applis du même nom, intégrés tels quels.

Usage : centre.py [--page accueil|modes|energie|apparence|arsenal|systeme]
"""
import json
import os
import shutil
import subprocess
import sys
import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

ICI = os.path.dirname(os.path.realpath(__file__))
APPS = os.path.dirname(ICI)
for dossier in ('modes', 'energie', 'arsenal', 'furtif'):
    sys.path.insert(0, os.path.join(APPS, dossier))
import energie   # noqa: E402
import modes     # noqa: E402
import shadow_cible  # noqa: E402
import shadow_modes as moteur  # noqa: E402
import shadow_furtif  # noqa: E402

APP_ID = 'os.shadow.Centre'
MAISON = os.path.expanduser('~')
FONDS = MAISON + '/.local/share/shadow-desktop/wallpapers'
FENETRES = MAISON + '/.local/bin/shadow-mode'
SHADOW = MAISON + '/.local/bin/shadow'
ILOT_SCHEMAS = MAISON + '/.local/share/gnome-shell/extensions/dynamic-island-v2@jordan/schemas'
ILOT = 'org.gnome.shell.extensions.dynamic-island-v2'
TACTILE = '/usr/local/libexec/shadow-ecran-tactile'
TACTILE_DRAPEAU = '/etc/shadow-os/ecran-tactile-desactive'
BOX = 'kali'

PAGES = (  # identifiant, titre, icône
    ('accueil', 'Accueil', 'go-home-symbolic'),
    ('modes', 'Modes', 'weather-clear-night-symbolic'),
    ('energie', 'Énergie', 'power-profile-balanced-symbolic'),
    ('apparence', 'Apparence', 'preferences-desktop-wallpaper-symbolic'),
    ('arsenal', 'Arsenal', 'utilities-terminal-symbolic'),
    ('systeme', 'Système', 'computer-symbolic'),
)
ILOT_THEMES = (('eclipse', 'Éclipse'), ('oled', 'OLED'), ('graphite', 'Graphite'),
               ('midnight', 'Minuit'), ('purple', 'Violet'), ('fluent', 'Fluent'))
ILOT_REPOS = (('weather', 'Heure et météo'), ('quotes', 'Citations'),
              ('stats', 'Moniteur système'), ('mascot', 'Mascotte'))
ENERGIES = {'frais': 'Frais', 'equilibre': 'Équilibré', 'performance': 'Performance'}

CSS = """
.cs-marque { font-size: 19px; font-weight: 800; letter-spacing: -0.2px; }
.cs-liste { background: none; }
.cs-liste row { border-radius: 12px; margin: 2px 8px; padding: 9px 10px; }
.cs-liste row label { font-size: 15.5px; font-weight: 600; }
.cs-liste row:selected { background-color: alpha(#7C6CFF, 0.22); }
.cs-liste row:selected image { color: #B7A9FF; }
.cs-logo {
  min-width: 108px; min-height: 108px; border-radius: 30px;
  background-image: linear-gradient(135deg, #1B1930, #0B0B12);
  border: 1px solid alpha(#B7A9FF, 0.22);
  box-shadow: 0 18px 46px alpha(#7C6CFF, 0.30);
}
.cs-titre { font-size: 44px; font-weight: 800; letter-spacing: -1px; }
.cs-sous { font-size: 17px; color: alpha(@window_fg_color, 0.60); }
.cs-fiche {
  font-size: 13.5px; font-weight: 600; padding: 6px 13px; border-radius: 999px;
  background-color: alpha(@window_fg_color, 0.07); color: alpha(@window_fg_color, 0.78);
}
button.cs-tuile {
  padding: 18px; border-radius: 22px;
  background-image: none; background-color: alpha(@window_fg_color, 0.05);
  border: 1px solid alpha(@window_fg_color, 0.08); box-shadow: none; font-weight: normal;
  transition: all 220ms cubic-bezier(0.22, 1, 0.36, 1);
}
button.cs-tuile:hover { background-color: alpha(@window_fg_color, 0.09); border-color: alpha(#B7A9FF, 0.35); }
button.cs-tuile:active { background-color: alpha(#7C6CFF, 0.20); }
.cs-puce { min-width: 46px; min-height: 46px; border-radius: 14px; }
.cs-puce image { color: white; }
.cs-puce.violet { background-image: linear-gradient(135deg, #7C6CFF, #FF4D8D); }
.cs-puce.bleu { background-image: linear-gradient(135deg, #36D1DC, #7C6CFF); }
.cs-puce.rouge { background-image: linear-gradient(135deg, #FF2D55, #FF7A3D); }
.cs-puce.vert { background-image: linear-gradient(135deg, #2DD4BF, #4C8DFF); }
.cs-puce.orange { background-image: linear-gradient(135deg, #FF9A4D, #FF4D8D); }
.cs-puce.gris { background-image: linear-gradient(135deg, #5E6B8C, #34344C); }
.cs-tuile-nom { font-size: 13.5px; font-weight: 600; color: alpha(@window_fg_color, 0.55); }
.cs-tuile-val { font-size: 21px; font-weight: 750; letter-spacing: -0.2px; }
.cs-tuile-sous { font-size: 13.5px; color: alpha(@window_fg_color, 0.50); }
"""


# --- outils -------------------------------------------------------------------
def sortie(*cmd, delai=6):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=delai)
        return r.stdout.strip() if r.returncode == 0 else ''
    except (OSError, subprocess.SubprocessError):
        return ''


def lancer(argv, fin=None):
    """Lance une commande sans bloquer ; fin(ok) est rappelée à la fin."""
    try:
        proc = Gio.Subprocess.new(list(argv), Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE)
    except GLib.Error:
        if fin:
            fin(False)
        return

    def termine(p, res):
        try:
            p.wait_finish(res)
            ok = p.get_successful()
        except GLib.Error:
            ok = False
        if fin:
            fin(ok)
    proc.wait_async(None, termine)


def ilot(cle, valeur=None):
    base = ['gsettings', '--schemadir', ILOT_SCHEMAS]
    if valeur is None:
        return sortie(*base, 'get', ILOT, cle).strip("'")
    return sortie(*base, 'set', ILOT, cle, valeur)


def lire_fichier(chemin):
    try:
        with open(chemin) as f:
            return f.read()
    except OSError:
        return ''


def etat_systeme():
    """Relevé de tout ce que le Centre affiche (appelé hors du fil d'interface)."""
    e = {}
    e['mode'] = moteur.actuel()
    e['energie'] = lire_fichier('/etc/shadow-os/energie-profil').strip()
    e['fenetres'] = sortie(FENETRES, 'etat') if os.access(FENETRES, os.X_OK) else ''
    e['diaporama'] = sortie('systemctl', '--user', 'is-active', 'slideshow.timer') == 'active' or \
        subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'slideshow.timer']).returncode == 0
    fond = sortie('gsettings', 'get', 'org.gnome.desktop.background', 'picture-uri-dark').strip("'")
    e['fond'] = os.path.basename(fond)
    e['ilot_theme'] = ilot('theme') if os.path.isdir(ILOT_SCHEMAS) else ''
    e['ilot_repos'] = ilot('idle-mode') if os.path.isdir(ILOT_SCHEMAS) else ''
    e['box_existe'] = bool(shutil.which('podman')) and subprocess.run(
        ['podman', 'container', 'exists', BOX], capture_output=True).returncode == 0
    e['box_active'] = e['box_existe'] and sortie('podman', 'ps', '--filter', f'name=^{BOX}$', '--format', '{{.Names}}') == BOX
    e['cible'] = shadow_cible.lire() or {}
    e['terminaux'] = shadow_cible.shells_branches()
    e['tactile_dispo'] = os.access(TACTILE, os.X_OK)
    e['tactile'] = not os.path.exists(TACTILE_DRAPEAU)
    e['furtif'] = shadow_furtif.etat_json()
    e['mission_rapport'] = mission_pour_rapport(e['cible'])
    return e


def mission_pour_rapport(cible):
    """(nom, dossier, résumé du dernier rapport) : la mission en cours, sinon la plus récente de ~/ctf."""
    if cible.get('nom') and cible.get('dossier') and os.path.isdir(cible['dossier']):
        nom, dossier = cible['nom'], cible['dossier']
    else:
        racine = os.path.join(MAISON, 'ctf')
        try:
            dossiers = [os.path.join(racine, d) for d in os.listdir(racine)
                        if os.path.isdir(os.path.join(racine, d)) and not d.startswith('.')]
        except OSError:
            return None
        if not dossiers:
            return None
        dossier = max(dossiers, key=os.path.getmtime)
        nom = os.path.basename(dossier)
    resume = None
    try:
        with open(os.path.join(dossier, '.rapport.json')) as f:
            resume = json.load(f)
    except (OSError, ValueError):
        pass
    return {'nom': nom, 'dossier': dossier, 'resume': resume,
            'pdf': os.path.exists(os.path.join(dossier, 'rapport.pdf'))}


def infos_machine():
    nom = ''
    for ligne in lire_fichier('/etc/os-release').splitlines():
        if ligne.startswith('PRETTY_NAME='):
            nom = ligne.split('=', 1)[1].strip('"')
    cpu = next((l.split(':', 1)[1].strip() for l in lire_fichier('/proc/cpuinfo').splitlines()
                if l.startswith('model name')), '')
    mem = next((int(l.split()[1]) for l in lire_fichier('/proc/meminfo').splitlines() if l.startswith('MemTotal')), 0)
    disque = shutil.disk_usage('/')
    duree = float((lire_fichier('/proc/uptime') or '0').split()[0])
    h, m = int(duree // 3600), int(duree % 3600 // 60)
    return [
        ('Système', nom or 'Shadow'),
        ('Noyau', os.uname().release),
        ('Bureau', sortie('gnome-shell', '--version') or 'GNOME'),
        ('Processeur', cpu.replace('(R)', '').replace('(TM)', '').replace(' CPU', '')),
        ('Mémoire', f'{mem / 1048576:.0f} Go'.replace('.', ',')),
        ('Disque', f'{disque.free / 1e9:.0f} Go libres sur {disque.total / 1e9:.0f} Go'),
        ('Allumé depuis', f'{h} h {m:02d}' if h else f'{m} min'),
    ]


# --- fenêtre --------------------------------------------------------------------
class Centre(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Shadow')
        self.set_default_size(1580, 880)
        self._maj = False                                   # vrai pendant qu'on reporte l'état dans les widgets
        self.e = {}
        self.toasts = Adw.ToastOverlay()

        # barre latérale
        self.liste = Gtk.ListBox()
        self.liste.add_css_class('cs-liste')
        self.liste.add_css_class('navigation-sidebar')
        for ident, titre, icone in PAGES:
            ligne = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            img = Gtk.Image.new_from_icon_name(icone)
            img.set_pixel_size(18)
            ligne.append(img)
            ligne.append(Gtk.Label(label=titre, xalign=0))
            rangee = Gtk.ListBoxRow(child=ligne)
            rangee.ident = ident
            self.liste.append(rangee)
        self.liste.connect('row-selected', self._sur_rangee)
        marque = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        logo = Gtk.Image.new_from_icon_name('shadow-os')
        logo.set_pixel_size(26)
        nom = Gtk.Label(label='Shadow')
        nom.add_css_class('cs-marque')
        marque.append(logo)
        marque.append(nom)
        entete_g = Adw.HeaderBar()
        entete_g.set_title_widget(marque)
        vue_g = Adw.ToolbarView()
        vue_g.add_top_bar(entete_g)
        vue_g.set_content(self.liste)

        # contenu
        self.pile = Gtk.Stack()
        self.pile.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.pile.set_transition_duration(200)
        self.pile.add_named(self._page_accueil(), 'accueil')
        self.panneau_modes = modes.PanneauModes(self.toasts.add_toast)
        self.pile.add_named(self._centrer(self.panneau_modes), 'modes')
        self.panneau_energie = energie.PanneauEnergie(self.toasts.add_toast)
        self.pile.add_named(self._centrer(self.panneau_energie, 520), 'energie')
        self.pile.add_named(self._page_apparence(), 'apparence')
        self.pile.add_named(self._page_arsenal(), 'arsenal')
        self.pile.add_named(self._page_systeme(), 'systeme')
        self.titre_page = Adw.WindowTitle(title='Accueil')
        entete_d = Adw.HeaderBar()
        entete_d.set_title_widget(self.titre_page)
        vue_d = Adw.ToolbarView()
        vue_d.add_top_bar(entete_d)
        vue_d.set_content(self.pile)

        partage = Adw.NavigationSplitView()
        partage.set_min_sidebar_width(250)
        partage.set_max_sidebar_width(270)
        partage.set_sidebar(Adw.NavigationPage(child=vue_g, title='Shadow'))
        partage.set_content(Adw.NavigationPage(child=vue_d, title='Accueil'))
        self.toasts.set_child(partage)
        self.set_content(self.toasts)

        self.connect('notify::is-active', lambda *_a: self.is_active() and self.rafraichir())
        self.aller('accueil')

    # --- navigation -----------------------------------------------------------
    def aller(self, ident):
        for rangee in self.liste:
            if rangee.ident == ident:
                self.liste.select_row(rangee)
                return

    def _sur_rangee(self, _liste, rangee):
        if not rangee:
            return
        self.pile.set_visible_child_name(rangee.ident)
        self.titre_page.set_title(next(t for i, t, _ic in PAGES if i == rangee.ident))
        self.rafraichir()

    @staticmethod
    def _centrer(widget, largeur=None):
        """Place un panneau au centre d'une page défilante (largeur plafonnée si demandé)."""
        defil = Gtk.ScrolledWindow()
        defil.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        widget.set_valign(Gtk.Align.CENTER)
        widget.set_margin_top(12)
        if largeur:
            defil.set_child(Adw.Clamp(maximum_size=largeur, child=widget))
        else:
            widget.set_halign(Gtk.Align.CENTER)
            defil.set_child(widget)
        return defil

    def toast(self, texte):
        t = Adw.Toast(title=texte)
        t.set_timeout(2)
        self.toasts.add_toast(t)

    # --- état -------------------------------------------------------------------
    def rafraichir(self):
        """Relit l'état du système en arrière-plan puis met l'interface à jour."""
        def travail():
            e = etat_systeme()
            GLib.idle_add(self._appliquer, e)
        threading.Thread(target=travail, daemon=True).start()

    def _appliquer(self, e):
        self.e = e
        self._maj = True
        try:
            m = moteur.mode(e['mode']) or {'nom': e['mode']}
            self.t_mode.regler(m['nom'], 'Ambiance du bureau')
            self.t_energie.regler(ENERGIES.get(e['energie'], '—'), 'Puissance et ventilation')
            self.t_fenetres.regler('Tuiles' if e['fenetres'] == 'tuiles' else 'Flottantes', 'Super+T pour basculer')
            self.t_fond.regler('Diaporama' if e['diaporama'] else 'Fond fixe', e['fond'][:26])
            cible = e['cible'].get('cible')
            self.t_arsenal.regler('Démarrée' if e['box_active'] else ('Arrêtée' if e['box_existe'] else 'Non installée'),
                                  f'Cible : {cible}' if cible else 'Box Kali')
            self.r_cible.set_title(cible or 'Aucune cible')
            self.r_cible.set_subtitle(f'Mission {e["cible"]["nom"]} · {e["cible"]["dossier"]}' if cible
                                      else 'Fixe une cible pour l’afficher dans l’îlot')
            self.b_fin.set_visible(bool(cible))
            self.b_dossier.set_visible(bool(cible))
            self.r_terminaux.set_subtitle(('Branchés : ' + ', '.join('~/' + t for t in e['terminaux'])) if e['terminaux']
                                          else 'Non branchés. Dans un terminal : shadow-cible terminaux')
            self.fiche_mode.set_label(f'Mode {m["nom"]}')

            self.r_fenetres.set_selected(1 if e['fenetres'] == 'tuiles' else 0)
            self.r_fond.set_subtitle(e['fond'] or '—')
            self.r_diapo.set_active(e['diaporama'])
            self.r_theme.set_selected(next((i for i, (k, _n) in enumerate(ILOT_THEMES) if k == e['ilot_theme']), 0))
            self.r_repos.set_selected(next((i for i, (k, _n) in enumerate(ILOT_REPOS) if k == e['ilot_repos']), 0))
            self.bandeau.set_revealed(e['mode'] != moteur.BASE_ID)
            self.bandeau.set_title(f'Mode {m["nom"]} actif : ces réglages reviendront à ceux du Quotidien quand tu le quitteras.')

            self.r_box.set_subtitle('Démarrée' if e['box_active'] else ('Arrêtée' if e['box_existe'] else 'Pas encore créée (shadow arsenal setup)'))
            self.b_box.set_label('Arrêter' if e['box_active'] else 'Démarrer')
            self.b_box.set_sensitive(e['box_existe'])
            self.b_terminal.set_sensitive(e['box_existe'])
            self.r_tactile.set_sensitive(e['tactile_dispo'])
            self.r_tactile.set_active(e['tactile'])
            m = e.get('mission_rapport')
            occupe = getattr(self, '_rapport_en_cours', False)
            self.b_apercu.set_sensitive(bool(m) and not occupe)
            self.b_pdf.set_sensitive(bool(m) and not occupe)
            if not m:
                self.r_rapport.set_title('Rapport de mission')
                self.r_rapport.set_subtitle('Aucune mission dans ~/ctf')
            else:
                self.r_rapport.set_title(f'Rapport · {m["nom"]}' + ('' if cible else ' (dernière mission)'))
                r = m['resume']
                self.r_rapport.set_subtitle(
                    'Pas encore généré : journal, preuves, ports, butin et captures d’écran' if not r else
                    f'{r["commandes"]} commandes · {r["preuves"]} preuves · {r["ports"]} ports · '
                    f'{r["butin"]} butin · {r["captures"]} captures')
            f = e['furtif']
            self.r_furtif.set_active(f['actif'])
            self.r_furtif.set_sensitive(not getattr(self, '_furtif_en_cours', False))
            self.r_sans_tor.set_sensitive(not f['actif'])
            if f['actif'] and f['tor']:
                self.r_furtif.set_subtitle('Actif : trafic par Tor, MAC aléatoire, nom de la machine caché')
            elif f['identite_seule_apres_redemarrage']:
                self.r_furtif.set_subtitle('⚠ Tor arrêté au redémarrage : trafic en clair. Désactive puis réactive.')
            elif f['actif']:
                self.r_furtif.set_subtitle('Actif : identité réseau masquée, trafic en clair (sans Tor)')
            else:
                self.r_furtif.set_subtitle('Tout le trafic par Tor, adresse MAC aléatoire, nom de la machine caché')
        finally:
            self._maj = False
        return GLib.SOURCE_REMOVE

    def _apres(self, message):
        def fin(ok):
            self.toast(message if ok else 'Échec de l’opération')
            self.rafraichir()
        return fin

    # --- page Accueil -------------------------------------------------------------
    def _tuile(self, nom, icone, couleur, page):
        bouton = Gtk.Button()
        bouton.add_css_class('cs-tuile')
        boite = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        puce = Gtk.Box()
        puce.add_css_class('cs-puce')
        puce.add_css_class(couleur)
        puce.set_halign(Gtk.Align.START)
        puce.set_hexpand(False)
        img = Gtk.Image.new_from_icon_name(icone)
        img.set_pixel_size(22)
        img.set_hexpand(True)
        puce.append(img)
        boite.append(puce)
        textes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        n = Gtk.Label(label=nom, xalign=0)
        n.add_css_class('cs-tuile-nom')
        valeur = Gtk.Label(label='…', xalign=0)
        valeur.add_css_class('cs-tuile-val')
        sous = Gtk.Label(label='', xalign=0, ellipsize=3)
        sous.add_css_class('cs-tuile-sous')
        for w in (n, valeur, sous):
            textes.append(w)
        boite.append(textes)
        bouton.set_child(boite)
        bouton.connect('clicked', lambda *_a: self.aller(page))
        bouton.regler = lambda v, s: (valeur.set_label(v), sous.set_label(s))
        return bouton

    def _page_accueil(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.set_margin_start(56)
        page.set_margin_end(56)
        page.set_margin_top(28)
        page.set_margin_bottom(40)

        haut = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=28)
        logo = Gtk.Box()
        logo.add_css_class('cs-logo')
        logo.set_valign(Gtk.Align.CENTER)
        logo.set_hexpand(False)
        img = Gtk.Image.new_from_icon_name('shadow-os')
        img.set_pixel_size(68)
        img.set_hexpand(True)
        logo.append(img)
        haut.append(logo)
        textes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        textes.set_valign(Gtk.Align.CENTER)
        titre = Gtk.Label(label='Shadow', xalign=0)
        titre.add_css_class('cs-titre')
        sous = Gtk.Label(label='Ton système, à ta façon.', xalign=0)
        sous.add_css_class('cs-sous')
        fiches = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        fiches.set_margin_top(8)
        infos = dict(infos_machine())
        self.fiche_mode = Gtk.Label(label='Mode …')
        for w in (self.fiche_mode, Gtk.Label(label=infos['Système']), Gtk.Label(label=infos['Bureau'])):
            w.add_css_class('cs-fiche')
            fiches.append(w)
        for w in (titre, sous, fiches):
            textes.append(w)
        haut.append(textes)
        page.append(haut)

        grille = Gtk.Grid(column_spacing=16, row_spacing=16, column_homogeneous=True)
        grille.set_margin_top(40)
        self.t_mode = self._tuile('Mode', 'shadow-os-symbolic', 'violet', 'modes')
        self.t_energie = self._tuile('Énergie', 'power-profile-balanced-symbolic', 'bleu', 'energie')
        self.t_fenetres = self._tuile('Fenêtres', 'focus-windows-symbolic', 'vert', 'apparence')
        self.t_fond = self._tuile('Fond d’écran', 'preferences-desktop-wallpaper-symbolic', 'orange', 'apparence')
        self.t_arsenal = self._tuile('Arsenal', 'utilities-terminal-symbolic', 'rouge', 'arsenal')
        self.t_systeme = self._tuile('Système', 'computer-symbolic', 'gris', 'systeme')
        self.t_systeme.regler(infos['Mémoire'] + ' · ' + infos['Disque'].split(' sur')[0], infos['Processeur'][:34])
        for i, t in enumerate((self.t_mode, self.t_energie, self.t_fenetres, self.t_fond, self.t_arsenal, self.t_systeme)):
            grille.attach(t, i % 3, i // 3, 1, 1)
        page.append(grille)

        defil = Gtk.ScrolledWindow()
        defil.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        cadre = Adw.Clamp(maximum_size=1120, child=page)
        defil.set_child(cadre)
        return defil

    # --- page Apparence -------------------------------------------------------------
    def _page_apparence(self):
        page = Adw.PreferencesPage()
        self.bandeau = Adw.Banner(title='')
        groupe = Adw.PreferencesGroup(title='Bureau')
        self.r_fenetres = Adw.ComboRow(title='Fenêtres', subtitle='Flottantes façon macOS, ou rangées en tuiles façon Omarchy',
                                       model=Gtk.StringList.new(['Flottantes', 'Tuiles']))
        self.r_fenetres.connect('notify::selected', self._sur_fenetres)
        groupe.add(self.r_fenetres)
        self.r_fond = Adw.ActionRow(title='Fond d’écran')
        suivant = Gtk.Button(label='Suivant', valign=Gtk.Align.CENTER)
        suivant.connect('clicked', lambda *_a: lancer([FONDS + '/wallpaper-next.sh', 'all'], self._apres('Fond changé')))
        self.r_fond.add_suffix(suivant)
        groupe.add(self.r_fond)
        self.r_diapo = Adw.SwitchRow(title='Diaporama', subtitle='Change de fond d’écran tout seul, à intervalle régulier')
        self.r_diapo.connect('notify::active', self._sur_diapo)
        groupe.add(self.r_diapo)
        page.add(groupe)

        groupe = Adw.PreferencesGroup(title='Îlot', description='La pastille au centre de la barre du haut')
        self.r_theme = Adw.ComboRow(title='Thème', model=Gtk.StringList.new([n for _k, n in ILOT_THEMES]))
        self.r_theme.connect('notify::selected', lambda r, _p: self._sur_ilot('theme', ILOT_THEMES[r.get_selected()][0]))
        groupe.add(self.r_theme)
        self.r_repos = Adw.ComboRow(title='Au repos', subtitle='Ce que l’îlot affiche quand rien ne se passe',
                                    model=Gtk.StringList.new([n for _k, n in ILOT_REPOS]))
        self.r_repos.connect('notify::selected', lambda r, _p: self._sur_ilot('idle-mode', ILOT_REPOS[r.get_selected()][0]))
        groupe.add(self.r_repos)
        page.add(groupe)

        boite = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        boite.append(self.bandeau)
        page.set_vexpand(True)
        boite.append(page)
        return boite

    def _sur_fenetres(self, rangee, _p):
        if self._maj:
            return
        voulu = 'tuiles' if rangee.get_selected() == 1 else 'flottant'
        lancer([FENETRES, voulu], self._apres('Fenêtres en tuiles' if voulu == 'tuiles' else 'Fenêtres flottantes'))

    def _sur_diapo(self, rangee, _p):
        if self._maj:
            return
        actif = rangee.get_active()
        lancer([FONDS + '/slideshow-ctl.sh', 'on' if actif else 'off'],
               self._apres('Diaporama activé' if actif else 'Diaporama arrêté'))

    def _sur_ilot(self, cle, valeur):
        if self._maj:
            return
        ilot(cle, valeur)

    # --- page Arsenal -----------------------------------------------------------------
    def _page_arsenal(self):
        page = Adw.PreferencesPage()
        groupe = Adw.PreferencesGroup(title='Box Kali', description='Tes outils de pentest, isolés dans un conteneur : Ubuntu reste intact')
        self.r_box = Adw.ActionRow(title='État')
        self.b_box = Gtk.Button(label='Démarrer', valign=Gtk.Align.CENTER)
        self.b_box.connect('clicked', self._sur_box)
        self.r_box.add_suffix(self.b_box)
        groupe.add(self.r_box)
        rangee = Adw.ActionRow(title='Terminal Kali', subtitle='Ouvre un terminal dans la box')
        self.b_terminal = Gtk.Button(label='Ouvrir', valign=Gtk.Align.CENTER)
        self.b_terminal.connect('clicked', lambda *_a: lancer(['kitty', '--title', 'Shadow Arsenal', '-e', SHADOW, 'arsenal', 'enter']))
        rangee.add_suffix(self.b_terminal)
        groupe.add(rangee)
        rangee = Adw.ActionRow(title='Packs d’outils', subtitle='Voir et installer les packs par catégorie (web, réseau, mots de passe…)')
        bouton = Gtk.Button(label='Gérer', valign=Gtk.Align.CENTER)
        bouton.connect('clicked', lambda *_a: lancer(['kitty', '--hold', '--title', 'Packs Arsenal', '-e', SHADOW, 'arsenal', 'packs']))
        rangee.add_suffix(bouton)
        groupe.add(rangee)
        page.add(groupe)

        groupe = Adw.PreferencesGroup(title='Mission', description='La cible de la mission s’affiche en permanence dans l’îlot')
        self.r_cible = Adw.ActionRow(title='Aucune cible')
        self.b_dossier = Gtk.Button(label='Dossier', valign=Gtk.Align.CENTER)
        self.b_dossier.connect('clicked', lambda *_a: self.e.get('cible', {}).get('dossier') and
                               lancer(['xdg-open', self.e['cible']['dossier']]))
        self.b_fin = Gtk.Button(label='Terminer', valign=Gtk.Align.CENTER)
        self.b_fin.connect('clicked', self._sur_fin_mission)
        self.r_cible.add_suffix(self.b_dossier)
        self.r_cible.add_suffix(self.b_fin)
        groupe.add(self.r_cible)
        self.s_adresse = Adw.EntryRow(title='Adresse (IP, nom d’hôte ou plage)')
        self.s_nom = Adw.EntryRow(title='Nom de la mission (facultatif)')
        fixer = Gtk.Button(label='Fixer la cible', valign=Gtk.Align.CENTER)
        fixer.add_css_class('suggested-action')
        fixer.connect('clicked', self._sur_cible)
        self.s_adresse.connect('entry-activated', self._sur_cible)
        self.s_nom.connect('entry-activated', self._sur_cible)
        self.s_nom.add_suffix(fixer)
        groupe.add(self.s_adresse)
        groupe.add(self.s_nom)
        self.r_terminaux = Adw.ActionRow(title='Variables $CIBLE, $TARGET et $MISSION dans les terminaux')
        groupe.add(self.r_terminaux)
        # rapport : journal, preuves, ports, butin, captures d'écran de la mission, en HTML et PDF
        self.r_rapport = Adw.ActionRow(title='Rapport de mission')
        self.b_apercu = Gtk.Button(label='Aperçu', valign=Gtk.Align.CENTER)
        self.b_apercu.connect('clicked', lambda *_a: self._sur_rapport(pdf=False))
        self.b_pdf = Gtk.Button(label='PDF', valign=Gtk.Align.CENTER)
        self.b_pdf.add_css_class('suggested-action')
        self.b_pdf.connect('clicked', lambda *_a: self._sur_rapport(pdf=True))
        self.r_rapport.add_suffix(self.b_apercu)
        self.r_rapport.add_suffix(self.b_pdf)
        groupe.add(self.r_rapport)
        page.add(groupe)

        groupe = Adw.PreferencesGroup(title='Mode furtif',
                                      description='Comme AnonSurf : rien ne sort en clair. Mot de passe demandé.')
        self.r_furtif = Adw.SwitchRow(title='Mode furtif')
        self.r_furtif.connect('notify::active', self._sur_furtif)
        groupe.add(self.r_furtif)
        self.r_sans_tor = Adw.SwitchRow(title='Sans Tor',
                                        subtitle='Identité masquée seulement : pour le VPN d’un CTF (HTB, THM)')
        groupe.add(self.r_sans_tor)
        page.add(groupe)

        groupe = Adw.PreferencesGroup(title='Mode Pentest')
        rangee = Adw.ActionRow(title='Passer en mode Pentest',
                               subtitle='Fond « cible », tuiles, ne pas déranger, HUD, box démarrée et terminal ouvert')
        bouton = Gtk.Button(label='Voir le mode', valign=Gtk.Align.CENTER)
        bouton.add_css_class('suggested-action')
        bouton.connect('clicked', lambda *_a: self.aller('modes'))
        rangee.add_suffix(bouton)
        groupe.add(rangee)
        page.add(groupe)
        return page

    def _sur_cible(self, *_a):
        adresse = self.s_adresse.get_text().strip()
        if not adresse:
            return
        if not shadow_cible.ADRESSE.match(adresse):
            self.toast('Adresse invalide : IP, nom d’hôte ou plage CIDR attendus')
            return
        try:
            shadow_cible.fixer(adresse, self.s_nom.get_text().strip() or None)
        except (OSError, SystemExit) as err:
            self.toast(f'Échec : {err}')
            return
        self.s_adresse.set_text('')
        self.s_nom.set_text('')
        self.toast(f'Cible fixée : {adresse}')
        self.rafraichir()

    def _sur_fin_mission(self, _b):
        shadow_cible.terminer()
        self.toast('Mission terminée, dossier conservé')
        self.rafraichir()

    def _sur_rapport(self, pdf):
        m = (self.e or {}).get('mission_rapport')
        if not m or getattr(self, '_rapport_en_cours', False):
            return
        self._rapport_en_cours = True
        self.b_apercu.set_sensitive(False)
        self.b_pdf.set_sensitive(False)
        self.r_rapport.set_subtitle('Génération du rapport…')

        def travail():
            try:
                md, *_ = shadow_cible.rapport(m['nom'])
                html, fichier_pdf = shadow_cible.exporter(md, pdf=pdf)
                cible = fichier_pdf if pdf else html
                erreur = None if cible else 'PDF impossible : Chrome ou Chromium introuvable'
            except (Exception, SystemExit) as err:     # le fil doit toujours rendre la main à l'interface
                cible, erreur = None, f'Échec du rapport : {err}'
            GLib.idle_add(fin, cible, erreur)

        def fin(cible, erreur):
            self._rapport_en_cours = False
            if cible:
                lancer(['xdg-open', cible])
                self.toast('Rapport PDF prêt' if pdf else 'Aperçu du rapport ouvert')
            else:
                self.toast(erreur)
            self.rafraichir()
            return GLib.SOURCE_REMOVE
        threading.Thread(target=travail, daemon=True).start()

    def _sur_furtif(self, rangee, _p):
        if self._maj:
            return
        voulu = rangee.get_active()
        argv = [MAISON + '/.local/bin/shadow-furtif', 'on' if voulu else 'off']
        if voulu and self.r_sans_tor.get_active():
            argv.append('--sans-tor')
        self._furtif_en_cours = True
        rangee.set_sensitive(False)
        rangee.set_subtitle('Activation… (Tor : jusqu’à 3 min la première fois)' if voulu else 'Retour au réseau normal…')

        def fin(ok):
            self._furtif_en_cours = False
            self.toast(('Mode furtif actif' if voulu else 'Mode furtif terminé') if ok
                       else 'Échec : voir « shadow furtif etat » dans un terminal')
            self.rafraichir()
        lancer(argv, fin)

    def _sur_box(self, _b):
        if self.e.get('box_active'):
            lancer(['podman', 'stop', '-t', '3', BOX], self._apres('Box Kali arrêtée'))
        else:
            lancer(['podman', 'start', BOX], self._apres('Box Kali démarrée'))
        self.b_box.set_sensitive(False)

    # --- page Système -----------------------------------------------------------------
    def _page_systeme(self):
        page = Adw.PreferencesPage()
        groupe = Adw.PreferencesGroup(title='Matériel')
        self.r_tactile = Adw.SwitchRow(title='Écran tactile', subtitle='Toucher, défiler et zoomer au doigt')
        self.r_tactile.connect('notify::active', self._sur_tactile)
        groupe.add(self.r_tactile)
        page.add(groupe)
        groupe = Adw.PreferencesGroup(title='À propos')
        for nom, valeur in infos_machine():
            rangee = Adw.ActionRow(title=nom, subtitle=valeur)
            rangee.add_css_class('property')
            groupe.add(rangee)
        page.add(groupe)
        return page

    def _sur_tactile(self, rangee, _p):
        if self._maj:
            return
        actif = rangee.get_active()
        lancer(['pkexec', TACTILE, 'on' if actif else 'off'],
               self._apres('Écran tactile activé' if actif else 'Écran tactile désactivé'))


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

    def do_startup(self):
        Adw.Application.do_startup(self)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        affichage = Gdk.Display.get_default()
        modes.charger_css(affichage)
        energie.charger_css(affichage)
        css = Gtk.CssProvider()
        css.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(affichage, css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        quitter = Gio.SimpleAction.new('quitter', None)
        quitter.connect('activate', lambda *_a: self.quit())
        self.add_action(quitter)
        self.set_accels_for_action('app.quitter', ['<Control>q', '<Control>w'])

    def do_command_line(self, ligne):
        args = ligne.get_arguments()[1:]
        page = args[args.index('--page') + 1] if '--page' in args and args.index('--page') + 1 < len(args) else None
        fen = self.get_active_window() or Centre(self)
        if page in [p[0] for p in PAGES]:
            fen.aller(page)
        fen.present()
        fen.set_focus_visible(False)
        return 0


if __name__ == '__main__':
    sys.exit(App().run(sys.argv))
