#!/usr/bin/env python3
"""Modes — choisis l'ambiance du bureau, comme sur un téléphone (Shadow OS).

Chaque mode est présenté par un aperçu dessiné du bureau qu'il produit :
fond, couleur d'accent, fenêtres flottantes ou en tuiles, HUD, lumière
nocturne. Le changement lui-même est fait par shadow_modes.py (même dossier).
"""
import math
import os
import sys

import cairo
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Gtk  # noqa: E402

ICI = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, ICI)
import shadow_modes as moteur  # noqa: E402

APP_ID = 'os.shadow.Modes'
MOTEUR = os.path.join(ICI, 'shadow_modes.py')
DEBUG = bool(os.environ.get('MO_DEBUG'))

ACCENTS = {  # couleurs d'accent de GNOME
    'blue': '#3584E4', 'teal': '#2190A4', 'green': '#3A944A', 'yellow': '#C88800', 'orange': '#ED5B00',
    'red': '#E62D42', 'pink': '#D56199', 'purple': '#9141AC', 'slate': '#6F8396', 'brown': '#986A44',
}
ACCENTS_FR = {'blue': 'bleu', 'teal': 'turquoise', 'green': 'vert', 'yellow': 'jaune', 'orange': 'orange',
              'red': 'rouge', 'pink': 'rose', 'purple': 'violet', 'slate': 'ardoise', 'brown': 'brun'}
ENERGIES = {'frais': 'Frais', 'equilibre': 'Équilibré', 'performance': 'Performance'}


def trace(*a):
    if DEBUG:
        print('[mo]', *a, file=sys.stderr, flush=True)


def rvb(hexa, alpha=1.0):
    h = hexa.lstrip('#')
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, alpha)


# =============================== APERÇU DESSINÉ ===============================
_IMAGES = {}


def image(chemin, largeur=1100):
    """Fond d'écran réduit, gardé en mémoire (les originaux font 3200 px et plus)."""
    if chemin not in _IMAGES:
        try:
            _IMAGES[chemin] = GdkPixbuf.Pixbuf.new_from_file_at_scale(chemin, largeur, -1, True)
        except GLib.Error:
            _IMAGES[chemin] = None
    return _IMAGES[chemin]


def arrondi(cr, x, y, w, h, r):
    r = max(0, min(r, w / 2, h / 2))
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def barre(cr, x, y, w, h, couleur):
    cr.set_source_rgba(*couleur)
    arrondi(cr, x, y, w, h, h / 2)
    cr.fill()


class Peintre:
    """Dessine un bureau miniature à partir des réglages effectifs d'un mode."""

    def __init__(self, mode, base):
        self.mode = mode
        eff = dict(base)
        eff.update(moteur.reglages(mode))
        self.eff = eff
        fond = (eff.get('fond') or {}).get('uri') or ''
        self.fond = fond[7:] if fond.startswith('file://') else fond
        self.accent = ACCENTS.get(eff.get('accent'), '#7C6CFF')
        self.c1, self.c2 = (mode.get('couleurs') or ['#7C6CFF', '#FF4D8D'])[:2]
        self.tuiles = eff.get('fenetres') == 'tuiles'
        self.genre = mode.get('apercu', 'bureau')

    # --- fenêtres -------------------------------------------------------------
    def cadre(self, cr, x, y, w, h, u, actif=False, fond=(0.035, 0.035, 0.05, 0.90)):
        """Fenêtre : ombre, corps, liseré (coloré si active), boutons."""
        r = 1.5 * u
        if not self.tuiles:
            for i, a in enumerate((0.10, 0.08, 0.06)):
                cr.set_source_rgba(0, 0, 0, a)
                e = (i + 1) * 0.7 * u
                arrondi(cr, x - e, y - e + u, w + 2 * e, h + 2 * e, r + e)
                cr.fill()
        cr.set_source_rgba(*fond)
        arrondi(cr, x, y, w, h, r)
        cr.fill()
        cr.set_line_width(max(1, 0.22 * u if actif else 0.12 * u))
        cr.set_source_rgba(*(rvb(self.accent, 0.95) if actif else (1, 1, 1, 0.10)))
        arrondi(cr, x, y, w, h, r)
        cr.stroke()
        for i, c in enumerate(('#FF5F57', '#FEBC2E', '#28C840')):
            cr.set_source_rgba(*rvb(c, 0.9 if actif else 0.35))
            cr.arc(x + (1.6 + i * 1.5) * u, y + 1.6 * u, 0.42 * u, 0, 2 * math.pi)
            cr.fill()
        return x + 1.4 * u, y + 3.2 * u, w - 2.8 * u, h - 4.4 * u     # zone de contenu

    def terminal(self, cr, x, y, w, h, u):
        vert, gris = rvb('#3DDC84', 0.9), (1, 1, 1, 0.34)
        lignes = [(self.accent, 0.20, vert, 0.34), (None, 0, gris, 0.70), (None, 0, gris, 0.52),
                  (self.accent, 0.20, vert, 0.46), (None, 0, rvb('#FFB020', 0.8), 0.62), (None, 0, gris, 0.40),
                  (None, 0, gris, 0.66), (self.accent, 0.20, vert, 0.28), (None, 0, gris, 0.55),
                  (None, 0, rvb(self.accent, 0.85), 0.36), (None, 0, gris, 0.60), (self.accent, 0.20, vert, 0.18)]
        pas = 1.55 * u
        for i, (inv, li, coul, lt) in enumerate(lignes):
            yy = y + i * pas
            if yy + 0.6 * u > y + h:
                break
            xx = x
            if inv:
                barre(cr, xx, yy, li * w * 0.5, 0.62 * u, rvb(inv, 0.95))
                xx += li * w * 0.5 + 0.7 * u
            barre(cr, xx, yy, lt * w, 0.62 * u, coul)

    def liste(self, cr, x, y, w, h, u):
        pas = 1.7 * u
        for i in range(int(h / pas)):
            yy = y + i * pas
            cr.set_source_rgba(*rvb('#3DDC84' if i % 3 else self.accent, 0.9))
            cr.arc(x + 0.4 * u, yy + 0.35 * u, 0.36 * u, 0, 2 * math.pi)
            cr.fill()
            barre(cr, x + 1.5 * u, yy, w * (0.32, 0.5, 0.4, 0.28)[i % 4], 0.6 * u, (1, 1, 1, 0.42))
            barre(cr, x + w * 0.72, yy, w * 0.22, 0.6 * u, (1, 1, 1, 0.16))

    def graphe(self, cr, x, y, w, h, u):
        n = 14
        larg = w / n
        for i in range(n):
            v = 0.25 + 0.75 * abs(math.sin(i * 1.3 + 0.6) * math.cos(i * 0.37))
            cr.set_source_rgba(*rvb(self.accent if i % 4 == 2 else self.c2, 0.85 if i % 4 == 2 else 0.5))
            arrondi(cr, x + i * larg, y + h * (1 - v), larg * 0.62, h * v, 0.25 * u)
            cr.fill()

    def document(self, cr, x, y, w, h, u):
        barre(cr, x, y, w * 0.46, 1.1 * u, rvb(self.accent, 0.95))
        for i, lt in enumerate((0.92, 0.86, 0.95, 0.60, 0, 0.90, 0.82, 0.94, 0.70, 0, 0.88, 0.50)):
            yy = y + 2.6 * u + i * 1.45 * u
            if lt and yy + 0.6 * u < y + h:
                barre(cr, x, yy, w * lt, 0.55 * u, (1, 1, 1, 0.30))

    def navigateur(self, cr, x, y, w, h, u):
        barre(cr, x, y, w, 1.5 * u, (1, 1, 1, 0.10))
        cr.set_source_rgba(*rvb(self.c1, 0.55))
        arrondi(cr, x, y + 2.6 * u, w * 0.42, h - 2.6 * u, 0.8 * u)
        cr.fill()
        for i, lt in enumerate((0.5, 0.44, 0.48, 0.3)):
            barre(cr, x + w * 0.47, y + 3 * u + i * 1.6 * u, w * lt, 0.6 * u, (1, 1, 1, 0.32))
        barre(cr, x + w * 0.47, y + 10 * u, w * 0.2, 1.5 * u, rvb(self.accent, 0.95))

    def jeu(self, cr, x, y, w, h, u):
        g = cairo.LinearGradient(x, y + h, x + w, y)
        g.add_color_stop_rgba(0, *rvb(self.c2, 0.75))
        g.add_color_stop_rgba(1, *rvb(self.c1, 0.75))
        cr.set_source(g)
        arrondi(cr, x, y, w, h, u)
        cr.fill()
        cx, cy, t = x + w / 2, y + h / 2, 3.2 * u
        cr.set_source_rgba(1, 1, 1, 0.95)
        cr.move_to(cx - t * 0.7, cy - t)
        cr.line_to(cx + t, cy)
        cr.line_to(cx - t * 0.7, cy + t)
        cr.close_path()
        cr.fill()
        barre(cr, x + u, y + h - 2 * u, w * 0.28, 0.7 * u, (0, 0, 0, 0.35))
        barre(cr, x + u, y + h - 2 * u, w * 0.19, 0.7 * u, (1, 1, 1, 0.95))

    def media(self, cr, x, y, w, h, u):
        cote = min(h, w * 0.3)
        g = cairo.LinearGradient(x, y, x + cote, y + cote)
        g.add_color_stop_rgba(0, *rvb(self.c1, 0.9))
        g.add_color_stop_rgba(1, *rvb(self.c2, 0.9))
        cr.set_source(g)
        arrondi(cr, x, y, cote, cote, u)
        cr.fill()
        xx = x + cote + 1.6 * u
        barre(cr, xx, y + 0.6 * u, (w - cote) * 0.55, 0.9 * u, (1, 1, 1, 0.75))
        barre(cr, xx, y + 2.4 * u, (w - cote) * 0.36, 0.6 * u, (1, 1, 1, 0.32))
        barre(cr, xx, y + cote - 1.4 * u, w - cote - 1.6 * u, 0.5 * u, (1, 1, 1, 0.16))
        barre(cr, xx, y + cote - 1.4 * u, (w - cote) * 0.4, 0.5 * u, rvb(self.accent, 0.95))

    def fenetres(self, cr, x, y, w, h, u):
        """Dispose les fenêtres : en tuiles, ou flottantes selon le genre du mode."""
        contenus = {'terminal': ['terminal', 'liste', 'graphe'], 'document': ['document', 'liste'],
                    'jeu': ['jeu', 'liste'], 'repos': ['media', 'document'],
                    'bureau': ['navigateur', 'terminal', 'liste']}[self.genre]
        if self.tuiles:
            e = 0.9 * u                                     # écart entre tuiles
            lg = w * 0.58
            zones = [(x, y, lg - e / 2, h, True)]
            reste = contenus[1:]
            hd = (h - e * (len(reste) - 1)) / len(reste)
            for i, _c in enumerate(reste):
                zones.append((x + lg + e / 2, y + i * (hd + e), w - lg - e / 2, hd, False))
            for (zx, zy, zw, zh, actif), nom in zip(zones, contenus):
                getattr(self, nom)(cr, *self.cadre(cr, zx, zy, zw, zh, u, actif), u)
        elif self.genre == 'document':
            ww, hh = w * 0.50, h * 0.92
            self.document(cr, *self.cadre(cr, x + (w - ww) / 2, y + (h - hh) / 2, ww, hh, u, True), u)
        elif self.genre == 'jeu':
            ww, hh = w * 0.80, h * 0.94
            zx, zy = x + (w - ww) / 2, y + (h - hh) / 2
            cx, cy, cw, ch = self.cadre(cr, zx, zy, ww, hh, u, True)
            self.jeu(cr, cx, cy, cw, ch, u)
        elif self.genre == 'repos':
            ww, hh = w * 0.44, h * 0.42
            self.media(cr, *self.cadre(cr, x + (w - ww) / 2, y + h * 0.42, ww, hh, u, True), u)
        else:                                               # bureau : deux fenêtres qui se chevauchent
            self.terminal(cr, *self.cadre(cr, x + w * 0.44, y + h * 0.20, w * 0.50, h * 0.74, u), u)
            self.navigateur(cr, *self.cadre(cr, x + w * 0.06, y + h * 0.02, w * 0.56, h * 0.78, u, True), u)

    # --- bureau ---------------------------------------------------------------
    def dessiner(self, cr, w, h):
        u = w / 100                                         # unité : 1 % de la largeur
        # fond d'écran, recadré pour remplir
        cr.set_source_rgb(0.03, 0.03, 0.045)
        cr.paint()
        pix = image(self.fond) if self.fond else None
        if pix:
            ech = max(w / pix.get_width(), h / pix.get_height())
            cr.save()
            cr.translate((w - pix.get_width() * ech) / 2, (h - pix.get_height() * ech) / 2)
            cr.scale(ech, ech)
            Gdk.cairo_set_source_pixbuf(cr, pix, 0, 0)
            cr.paint()
            cr.restore()
        # barre du haut : espaces de travail, îlot, indicateurs
        hb = 4.2 * u
        cr.set_source_rgba(0, 0, 0, 0.42)
        cr.rectangle(0, 0, w, hb)
        cr.fill()
        for i in range(4):
            barre(cr, (2 + i * 2.6) * u, hb * 0.36, (2.6 if i == 0 else 1.5) * u * 0.8, hb * 0.28,
                  rvb(self.accent, 1) if i == 0 else (1, 1, 1, 0.35))
        li = 17 * u
        barre(cr, (w - li) / 2, hb * 0.14, li, hb * 0.72, (0, 0, 0, 0.92))
        stats = self.eff.get('ilot_repos') == 'stats'
        for i in range(3 if stats else 1):
            barre(cr, (w - li) / 2 + (2 + i * 4.6) * u, hb * 0.42, (3.4 if stats else 5.5) * u, hb * 0.16,
                  rvb((self.accent, '#3DDC84', '#FFB020')[i], 0.95) if stats else (1, 1, 1, 0.85))
        for i in range(3):
            cr.set_source_rgba(1, 1, 1, 0.55)
            cr.arc(w - (2.4 + i * 2.1) * u, hb / 2, 0.55 * u, 0, 2 * math.pi)
            cr.fill()
        if self.eff.get('ne_pas_deranger'):                 # croissant « ne pas déranger »
            cx, cy, r = w - 10 * u, hb / 2, 0.95 * u
            cr.push_group()
            cr.set_source_rgba(1, 1, 1, 0.9)
            cr.arc(cx, cy, r, 0, 2 * math.pi)
            cr.fill()
            cr.set_operator(cairo.OPERATOR_CLEAR)           # creuse le disque
            cr.arc(cx + 0.55 * u, cy - 0.35 * u, r * 0.88, 0, 2 * math.pi)
            cr.fill()
            cr.pop_group_to_source()
            cr.paint()
        # dock
        ld, hd = 34 * u, 5.4 * u
        yd = h - hd - 1.6 * u
        cr.set_source_rgba(0.07, 0.07, 0.10, 0.62)
        arrondi(cr, (w - ld) / 2, yd, ld, hd, 1.9 * u)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.10)
        cr.set_line_width(max(1, 0.1 * u))
        arrondi(cr, (w - ld) / 2, yd, ld, hd, 1.9 * u)
        cr.stroke()
        teintes = [self.accent, '#5E6B8C', self.c2, '#3DDC84', '#8A8FA3', self.c1, '#FFB020', '#6C7086']
        pas = ld / len(teintes)
        for i, t in enumerate(teintes):
            cote = hd * 0.62
            cr.set_source_rgba(*rvb(t, 0.92))
            arrondi(cr, (w - ld) / 2 + i * pas + (pas - cote) / 2, yd + (hd - cote) / 2, cote, cote, cote * 0.28)
            cr.fill()
        # fenêtres
        marge = 3.2 * u
        self.fenetres(cr, marge, hb + 2.2 * u, w - 2 * marge - (13 * u if self.eff.get('hud') else 0),
                      yd - hb - 4.2 * u, u)
        # HUD à droite
        if self.eff.get('hud'):
            xh, yh = w - 13.5 * u, hb + 3 * u
            for bloc in range(3):
                barre(cr, xh, yh, 5 * u, 0.6 * u, rvb(self.accent, 0.95))
                for i in range(4):
                    barre(cr, xh, yh + (1.5 + i * 1.25) * u, (10.5, 8, 9.4, 6.5)[i] * u, 0.42 * u, (1, 1, 1, 0.34))
                    barre(cr, xh, yh + (1.5 + i * 1.25) * u, (10.5, 8, 9.4, 6.5)[i] * u * (0.7, 0.4, 0.85, 0.5)[(i + bloc) % 4],
                          0.42 * u, rvb(self.accent, 0.8))
                yh += 8.2 * u
        # lumière nocturne : voile chaud sur tout l'écran
        if self.eff.get('lumiere_nocturne'):
            cr.set_source_rgba(1.0, 0.56, 0.18, 0.16)
            cr.paint()


class Apercu(Gtk.DrawingArea):
    def __init__(self, mode, base):
        super().__init__()
        self.peintre = Peintre(mode, base)
        self.set_draw_func(self._dessiner)

    def _dessiner(self, _zone, cr, w, h):
        try:
            self.peintre.dessiner(cr, w, h)
        except Exception as e:                              # un aperçu raté ne doit jamais fermer l'appli
            trace('aperçu', e)


# ================================== INTERFACE ==================================
CSS = """
.mo-cadre {
  border-radius: 22px;
  box-shadow: 0 24px 60px alpha(black, 0.50), 0 0 0 1px alpha(@window_fg_color, 0.10);
}
.mo-puce { min-width: 58px; min-height: 58px; border-radius: 18px; }
.mo-puce image { color: white; }
.mo-nom { font-size: 34px; font-weight: 800; letter-spacing: -0.5px; }
.mo-accroche { font-size: 17px; color: alpha(@window_fg_color, 0.62); }
.mo-actif {
  font-size: 12.5px; font-weight: 800; letter-spacing: 0.8px;
  padding: 4px 11px; border-radius: 999px; color: white;
}
.mo-pastille {
  font-size: 14px; font-weight: 600;
  padding: 7px 13px; border-radius: 999px;
  background-color: alpha(@window_fg_color, 0.07);
  border: 1px solid alpha(@window_fg_color, 0.07);
  color: alpha(@window_fg_color, 0.85);
}
.mo-pastille image { color: alpha(@window_fg_color, 0.55); }
button.mo-activer {
  min-height: 52px; padding: 0 30px; border-radius: 999px;
  font-size: 16.5px; font-weight: 750; color: white;
  border: none; box-shadow: 0 10px 28px alpha(black, 0.35);
  transition: all 220ms cubic-bezier(0.22, 1, 0.36, 1);
}
button.mo-activer:hover { filter: brightness(1.12); }
button.mo-activer:active { filter: brightness(0.92); }
button.mo-activer:disabled {
  background-image: none; background-color: alpha(@window_fg_color, 0.08);
  color: alpha(@window_fg_color, 0.55); box-shadow: none;
}
button.mo-retour {
  min-height: 52px; padding: 0 24px; border-radius: 999px;
  font-size: 15.5px; font-weight: 650;
  background-image: none; background-color: alpha(@window_fg_color, 0.07);
  border: 1px solid alpha(@window_fg_color, 0.10); box-shadow: none;
  color: alpha(@window_fg_color, 0.85);
}
button.mo-retour:hover { background-color: alpha(@window_fg_color, 0.12); }
.mo-section { font-size: 12px; font-weight: 700; letter-spacing: 1px; color: alpha(@window_fg_color, 0.42); }
button.mo-carte {
  padding: 10px; border-radius: 20px;
  background-image: none; background-color: alpha(@window_fg_color, 0.045);
  border: 1.5px solid alpha(@window_fg_color, 0.07); box-shadow: none; font-weight: normal;
  transition: all 240ms cubic-bezier(0.22, 1, 0.36, 1);
}
button.mo-carte:hover { background-color: alpha(@window_fg_color, 0.085); }
button.mo-carte:focus-visible { outline: 2px solid alpha(@window_fg_color, 0.28); outline-offset: 2px; }
.mo-vignette { border-radius: 12px; box-shadow: 0 0 0 1px alpha(@window_fg_color, 0.10); }
.mo-carte-nom { font-size: 17px; font-weight: 750; }
.mo-carte-sous { font-size: 13px; color: alpha(@window_fg_color, 0.50); }
.mo-point { min-width: 9px; min-height: 9px; border-radius: 999px; }
.mo-routine {
  padding: 14px 16px; border-radius: 20px;
  background-color: alpha(@window_fg_color, 0.045);
  border: 1.5px solid alpha(@window_fg_color, 0.07);
}
.mo-routine-titre { font-size: 15.5px; font-weight: 700; }
"""


def css_des_modes(modes):
    """Couleurs propres à chaque mode (puce, bouton, carte sélectionnée, badge)."""
    regles = []
    for m in modes:
        c1, c2 = (m.get('couleurs') or ['#7C6CFF', '#FF4D8D'])[:2]
        i = m['id']
        regles.append(f"""
.mo-puce.m-{i}, button.mo-activer.m-{i}, .mo-actif.m-{i}, .mo-point.m-{i} {{ background-image: linear-gradient(135deg, {c1}, {c2}); }}
.mo-puce.m-{i} {{ box-shadow: 0 10px 28px alpha({c1}, 0.35); }}
button.mo-carte.m-{i}:checked {{
  background-color: alpha({c1}, 0.13); border-color: alpha({c1}, 0.70);
  box-shadow: 0 10px 30px alpha({c1}, 0.18);
}}""")
    return '\n'.join(regles)


def pastilles(mode):
    """Ce que le mode change, en clair : liste de (icône, texte)."""
    r = mode.get('reglages') or {}
    if not r:
        return [('preferences-desktop-wallpaper-symbolic', 'Ton fond et ton diaporama'),
                ('preferences-color-symbolic', 'Tes couleurs'),
                ('focus-windows-symbolic', 'Tes fenêtres'),
                ('power-profile-balanced-symbolic', 'Ton réglage d’énergie')]
    p = []
    if 'fond' in r:
        p.append(('preferences-desktop-wallpaper-symbolic', 'Fond dédié'))
    if 'accent' in r:
        p.append(('preferences-color-symbolic', f'Accent {ACCENTS_FR.get(r["accent"], r["accent"])}'))
    if 'fenetres' in r:
        p.append(('focus-windows-symbolic', 'Fenêtres en tuiles' if r['fenetres'] == 'tuiles' else 'Fenêtres flottantes'))
    if r.get('ne_pas_deranger'):
        p.append(('notifications-disabled-symbolic', 'Ne pas déranger'))
    if 'lumiere_nocturne' in r:
        p.append(('night-light-symbolic', 'Lumière nocturne' if r['lumiere_nocturne'] else 'Lumière nocturne coupée'))
    if 'energie' in r:
        p.append(('power-profile-performance-symbolic' if r['energie'] == 'performance' else 'power-profile-power-saver-symbolic',
                  f'Énergie {ENERGIES.get(r["energie"], r["energie"])}'))
    if r.get('ilot_repos') == 'stats':
        p.append(('utilities-system-monitor-symbolic', 'Îlot en moniteur système'))
    if 'hud' in r:
        p.append(('video-display-symbolic', 'HUD à l’écran' if r['hud'] else 'HUD masqué'))
    if r.get('arsenal'):
        p.append(('security-high-symbolic', 'Box Kali démarrée'))
    if mode.get('lancer'):
        p.append(('utilities-terminal-symbolic', 'Ouvre un terminal Kali' if r.get('arsenal') else 'Ouvre ses applis'))
    return p


class Carte(Gtk.ToggleButton):
    def __init__(self, mode, base):
        super().__init__()
        self.mode = mode
        self.add_css_class('mo-carte')
        self.add_css_class(f'm-{mode["id"]}')
        ligne = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        vignette = Gtk.Frame()
        vignette.add_css_class('mo-vignette')
        vignette.set_overflow(Gtk.Overflow.HIDDEN)
        vignette.set_valign(Gtk.Align.CENTER)
        self.apercu = Apercu(mode, base)
        self.apercu.set_content_width(140)
        self.apercu.set_content_height(79)
        vignette.set_child(self.apercu)
        ligne.append(vignette)
        textes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        textes.set_valign(Gtk.Align.CENTER)
        textes.set_hexpand(True)
        nom = Gtk.Label(label=mode['nom'], xalign=0)
        nom.add_css_class('mo-carte-nom')
        etat = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        self.point = Gtk.Box()
        self.point.add_css_class('mo-point')
        self.point.add_css_class(f'm-{mode["id"]}')
        self.point.set_valign(Gtk.Align.CENTER)
        self.sous = Gtk.Label(xalign=0)
        self.sous.add_css_class('mo-carte-sous')
        etat.append(self.point)
        etat.append(self.sous)
        textes.append(nom)
        textes.append(etat)
        ligne.append(textes)
        self.set_child(ligne)
        n = len(mode.get('reglages') or {})
        self._repos = f'{n} réglages' if n else 'Tes réglages'
        self.marquer(False)

    def marquer(self, actif):
        self.point.set_visible(actif)
        self.sous.set_label('Actif' if actif else self._repos)


class PanneauModes(Gtk.Box):
    """Tout le contenu de l'appli Modes, réutilisable tel quel dans le Centre Shadow."""

    def __init__(self, toast):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=32)
        self._toast = toast                                 # fonction(Adw.Toast) de la fenêtre hôte
        self._en_cours = False
        self._ignore = False
        etat = moteur.etat_complet()
        self.modes = etat['modes']
        self.base = etat['base']
        self.actif = etat['actuel']
        self.choisi = self.actif

        racine = self
        racine.set_margin_start(36)
        racine.set_margin_end(32)
        racine.set_margin_bottom(32)

        # ------------------------- colonne de gauche : aperçu + détail
        gauche = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        gauche.set_size_request(832, -1)
        cadre = Gtk.Frame()
        cadre.set_size_request(832, 468)
        cadre.set_halign(Gtk.Align.START)
        cadre.add_css_class('mo-cadre')
        cadre.set_overflow(Gtk.Overflow.HIDDEN)
        self.pile = Gtk.Stack()
        self.pile.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.pile.set_transition_duration(340)
        for m in self.modes:
            self.pile.add_named(Apercu(m, self.base), m['id'])
        cadre.set_child(self.pile)
        gauche.append(cadre)

        titre = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        titre.set_margin_top(26)
        self.puce = Gtk.Box()
        self.puce.add_css_class('mo-puce')
        self.puce.set_valign(Gtk.Align.CENTER)
        self.puce.set_hexpand(False)                        # sinon l'icône (extensible) étire la puce
        self.puce_icone = Gtk.Image()
        self.puce_icone.set_pixel_size(30)
        self.puce_icone.set_hexpand(True)
        self.puce.append(self.puce_icone)
        titre.append(self.puce)
        noms = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        noms.set_hexpand(True)
        noms.set_valign(Gtk.Align.CENTER)
        ligne_nom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.nom = Gtk.Label(xalign=0)
        self.nom.add_css_class('mo-nom')
        self.badge = Gtk.Label(label='ACTIF')
        self.badge.add_css_class('mo-actif')
        self.badge.set_valign(Gtk.Align.CENTER)
        ligne_nom.append(self.nom)
        ligne_nom.append(self.badge)
        self.accroche = Gtk.Label(xalign=0, wrap=True)
        self.accroche.add_css_class('mo-accroche')
        noms.append(ligne_nom)
        noms.append(self.accroche)
        titre.append(noms)

        boutons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        boutons.set_valign(Gtk.Align.CENTER)
        self.retour = Gtk.Button(label='Revenir au Quotidien')
        self.retour.add_css_class('mo-retour')
        self.retour.connect('clicked', lambda *_a: self._activer(moteur.BASE_ID))
        self.activer = Gtk.Button()
        self.activer.add_css_class('mo-activer')
        contenu = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        contenu.set_halign(Gtk.Align.CENTER)
        self.attente = Adw.Spinner()
        self.attente.set_visible(False)
        self.activer_texte = Gtk.Label()
        contenu.append(self.attente)
        contenu.append(self.activer_texte)
        self.activer.set_child(contenu)
        self.activer.connect('clicked', lambda *_a: self._activer(self.choisi))
        boutons.append(self.retour)
        boutons.append(self.activer)
        titre.append(boutons)
        gauche.append(titre)

        self.zone_pastilles = Adw.WrapBox(child_spacing=8, line_spacing=8, natural_line_length=832)
        self.zone_pastilles.set_margin_top(20)
        gauche.append(self.zone_pastilles)
        racine.append(gauche)

        # ------------------------- colonne de droite : les modes
        droite = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        droite.set_size_request(360, -1)
        droite.set_valign(Gtk.Align.START)
        section = Gtk.Label(label='MODES', xalign=0)
        section.add_css_class('mo-section')
        section.set_margin_start(6)
        section.set_margin_bottom(2)
        droite.append(section)
        self.cartes = {}
        premiere = None
        for m in self.modes:
            carte = Carte(m, self.base)
            if premiere is None:
                premiere = carte
            else:
                carte.set_group(premiere)
            carte.connect('toggled', self._sur_carte)
            self.cartes[m['id']] = carte
            droite.append(carte)

        # routine façon téléphone : le mode Nuit se met tout seul le soir
        routine = etat.get('routine') or moteur.config()
        section2 = Gtk.Label(label='ROUTINE', xalign=0)
        section2.add_css_class('mo-section')
        section2.set_margin_start(6)
        section2.set_margin_top(10)
        section2.set_margin_bottom(2)
        droite.append(section2)
        ligne = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        ligne.add_css_class('mo-routine')
        textes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        textes.set_hexpand(True)
        textes.set_valign(Gtk.Align.CENTER)
        t = Gtk.Label(label='Nuit automatique', xalign=0)
        t.add_css_class('mo-routine-titre')
        d = Gtk.Label(label=f'De {routine["nuit_debut"]} à {routine["nuit_fin"]}, puis retour au Quotidien', xalign=0, wrap=True)
        d.add_css_class('mo-carte-sous')
        textes.append(t)
        textes.append(d)
        ligne.append(textes)
        self.bascule_nuit = Gtk.Switch()
        self.bascule_nuit.set_valign(Gtk.Align.CENTER)
        self.bascule_nuit.set_active(bool(routine.get('nuit_auto')))
        self.bascule_nuit.connect('notify::active', self._sur_routine)
        ligne.append(self.bascule_nuit)
        droite.append(ligne)
        racine.append(droite)


        # suit les changements faits ailleurs (commande shadow-modes, raccourci…)
        os.makedirs(moteur.ETAT_DIR, exist_ok=True)
        self._moniteur = Gio.File.new_for_path(moteur.ETAT_DIR).monitor_directory(Gio.FileMonitorFlags.NONE, None)
        self._moniteur.connect('changed', lambda *_a: self._relire())

        self._choisir(self.actif)

    # --- sélection ---------------------------------------------------------------
    def _mode(self, ident):
        return next(m for m in self.modes if m['id'] == ident)

    def _sur_carte(self, carte):
        if self._ignore or not carte.get_active():
            return
        self._choisir(carte.mode['id'])

    def _choisir(self, ident):
        avant, self.choisi = self.choisi, ident
        m = self._mode(ident)
        self._ignore = True
        self.cartes[ident].set_active(True)
        self._ignore = False
        self.pile.set_visible_child_name(ident)
        for w in (self.puce, self.activer, self.badge):
            w.remove_css_class(f'm-{avant}')
            w.add_css_class(f'm-{ident}')
        self.puce_icone.set_from_icon_name(m.get('symbole', 'shadow-os-symbolic'))
        self.nom.set_label(m['nom'])
        self.accroche.set_label(m.get('accroche', ''))
        enfant = self.zone_pastilles.get_first_child()
        while enfant:
            suivant = enfant.get_next_sibling()
            self.zone_pastilles.remove(enfant)
            enfant = suivant
        for icone, texte in pastilles(m):
            boite = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            boite.add_css_class('mo-pastille')
            img = Gtk.Image.new_from_icon_name(icone)
            img.set_pixel_size(16)
            boite.append(img)
            boite.append(Gtk.Label(label=texte))
            self.zone_pastilles.append(boite)
        self._boutons()

    def _boutons(self):
        est_actif = self.choisi == self.actif
        self.badge.set_visible(est_actif)
        self.attente.set_visible(self._en_cours)
        self.activer.set_visible(not est_actif)
        self.activer.set_sensitive(not self._en_cours)
        self.activer_texte.set_label('Activation…' if self._en_cours else f'Activer {self._mode(self.choisi)["nom"]}')
        self.retour.set_visible(self.actif != moteur.BASE_ID and self.choisi != moteur.BASE_ID)
        self.retour.set_sensitive(not self._en_cours)
        for ident, carte in self.cartes.items():
            carte.marquer(ident == self.actif)

    # --- routine ---------------------------------------------------------------------
    def _sur_routine(self, bascule, _pspec):
        voulu = bascule.get_active()
        trace('routine', voulu)
        try:
            proc = Gio.Subprocess.new([MOTEUR, 'auto', 'on' if voulu else 'off'],
                                      Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
        except GLib.Error as e:
            self._toast(Adw.Toast(title=e.message))
            return

        def fini(p, res):
            try:
                p.communicate_utf8_finish(res)
                ok = p.get_successful()
            except GLib.Error:
                ok = False
            texte = ('Nuit automatique activée' if voulu else 'Nuit automatique désactivée') if ok else 'Échec du réglage de la routine'
            toast = Adw.Toast(title=texte)
            toast.set_timeout(2)
            self._toast(toast)
            self._relire()
        proc.communicate_utf8_async(None, None, fini)

    # --- activation --------------------------------------------------------------
    def _activer(self, ident):
        if self._en_cours or ident == self.actif:
            return
        trace('activer', ident)
        self._en_cours = True
        self._boutons()
        try:
            proc = Gio.Subprocess.new([MOTEUR, 'activer', ident],
                                      Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE)
        except GLib.Error as e:
            self._fin(ident, False, e.message)
            return
        proc.communicate_utf8_async(None, None, self._termine, ident)

    def _termine(self, proc, res, ident):
        try:
            _ok, sortie, err = proc.communicate_utf8_finish(res)
            ok = proc.get_successful()
            message = (sortie or err or '').strip()
        except GLib.Error as e:
            ok, message = False, e.message
        self._fin(ident, ok, message)

    def _fin(self, ident, ok, message):
        trace('fin', ident, ok, message)
        self._en_cours = False
        self._relire()
        if ok:
            texte = f'Mode {self._mode(ident)["nom"]} activé'
        else:
            texte = (message.splitlines()[-1] if message else 'Échec du changement de mode')
        toast = Adw.Toast(title=texte)
        toast.set_timeout(3)
        self._toast(toast)

    def _relire(self):
        if self._en_cours:
            return
        self.actif = moteur.actuel()
        self._boutons()


def charger_css(affichage):
    """Styles et icônes de Modes ; appelé par l'appli comme par le Centre Shadow."""
    Gtk.IconTheme.get_for_display(affichage).add_search_path(os.path.join(ICI, 'icones'))
    css = Gtk.CssProvider()
    css.load_from_string(CSS + css_des_modes(moteur.modes()))
    # au-dessus du thème GTK de l'utilisateur, qui recolore sinon « button:checked »
    Gtk.StyleContext.add_provider_for_display(affichage, css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)


class Fenetre(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Modes')
        self.set_resizable(False)                           # taille naturelle : aperçu 16:9 fixe
        toasts = Adw.ToastOverlay()
        vue = Adw.ToolbarView()
        entete = Adw.HeaderBar()
        entete.set_show_title(False)
        vue.add_top_bar(entete)
        self.panneau = PanneauModes(toasts.add_toast)
        vue.set_content(self.panneau)
        toasts.set_child(vue)
        self.set_content(toasts)
        self.set_focus(self.panneau.cartes[self.panneau.actif])


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_startup(self):
        Adw.Application.do_startup(self)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        charger_css(Gdk.Display.get_default())
        quitter = Gio.SimpleAction.new('quitter', None)
        quitter.connect('activate', lambda *_a: self.quit())
        self.add_action(quitter)
        self.set_accels_for_action('app.quitter', ['<Control>q', '<Control>w', 'Escape'])

    def do_activate(self):
        fen = self.get_active_window() or Fenetre(self)
        fen.present()
        fen.set_focus_visible(False)


if __name__ == '__main__':
    sys.exit(App().run(sys.argv))
