// Shadow OS — intégration du bureau.
// GNOME 50 peint les tuiles actives des réglages rapides avec l'accent système
// (choix limité à 10 couleurs), quel que soit le thème. On repeint donc chaque
// tuile active en style en ligne avec l'accent Éclipse, sans toucher au reste.
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const ACCENT = '#7C6CFF';
const SURVOL = '#8D7FFF';
const FLECHE = '#6E5DF2';

// Modes Shadow (apps/modes) : mode actif et définitions
const MODES_ETAT = `${GLib.get_user_state_dir()}/shadow-os/modes`;
const MODE_BASE = 'quotidien';

export default class ShadowOS extends Extension {
    enable() {
        // Barre du haut : ces deux réglages venaient de Just Perfection, qui coûtait
        // 10 à 16 s à chaque verrouillage pour les appliquer. Faits ici, sans feuille de style.
        this._amenagerBarre();
        this._indicateurMode();

        // Alt+Espace : la recherche de GNOME, façon Spotlight (elle respecte les applis masquées)
        this._reglages = this.getSettings();
        Main.wm.addKeybinding('lanceur', this._reglages, Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW, () => {
                if (Main.overview.visible && Main.overview.searchEntry?.has_key_focus?.())
                    Main.overview.hide();
                else
                    Main.overview.focusSearch();
            });

        this._suivis = new Map();
        this._menu = Main.panel.statusArea.quickSettings?.menu ?? null;
        if (!this._menu)
            return;
        this._ouvertId = this._menu.connect('open-state-changed', (_m, ouvert) => {
            if (ouvert)
                this._parcourir(this._menu.box);
        });
        this._parcourir(this._menu.box);
    }

    disable() {
        this._retablirBarre();
        this._retirerIndicateurMode();
        Main.wm.removeKeybinding('lanceur');
        this._reglages = null;
        if (this._menu && this._ouvertId)
            this._menu.disconnect(this._ouvertId);
        for (const [acteur, ids] of this._suivis ?? []) {
            try {
                ids.forEach(id => acteur.disconnect(id));
                acteur.set_style(null);
            } catch (_e) {}
        }
        this._suivis = null;
        this._menu = null;
        this._ouvertId = 0;
    }

    // ---------------- barre du haut : bouton Activités masqué, horloge à droite ----------------
    _amenagerBarre() {
        try {
            const activites = Main.panel.statusArea.activities;
            if (activites) {
                this._activitesVisibles = activites.container.visible;
                activites.container.hide();
            }
            const horloge = Main.panel.statusArea.dateMenu?.container;
            const parent = horloge?.get_parent();
            if (horloge && parent && parent !== Main.panel._rightBox) {
                this._horlogeOrigine = {parent, index: parent.get_children().indexOf(horloge)};
                parent.remove_child(horloge);
                Main.panel._rightBox.insert_child_at_index(horloge, 0);
            }
        } catch (e) {
            console.error(`[shadow-os] barre : ${e}`);
        }
    }

    _retablirBarre() {
        try {
            const activites = Main.panel.statusArea.activities;
            if (activites && this._activitesVisibles)
                activites.container.show();
            const o = this._horlogeOrigine;
            const horloge = Main.panel.statusArea.dateMenu?.container;
            if (o && horloge) {
                horloge.get_parent()?.remove_child(horloge);
                o.parent.insert_child_at_index(horloge, Math.min(o.index, o.parent.get_n_children()));
            }
        } catch (e) {
            console.error(`[shadow-os] barre : ${e}`);
        }
        this._horlogeOrigine = null;
    }

    // ---------------- indicateur du mode actif (Pentest, Focus, Jeu, Nuit) ----------------
    // Une pastille aux couleurs du mode, à gauche dans la barre ; masquée en mode Quotidien.
    // Un clic ouvre l'appli Modes.
    _indicateurMode() {
        try {
            // dossier de l'appli Modes : la commande shadow-modes est un lien vers son moteur
            const lien = `${GLib.get_home_dir()}/.local/bin/shadow-modes`;
            const cible = GLib.file_test(lien, GLib.FileTest.EXISTS)
                ? Gio.File.new_for_path(lien).query_info('standard::symlink-target', Gio.FileQueryInfoFlags.NONE, null).get_symlink_target()
                : null;
            if (!cible)
                return;
            this._modesDossier = GLib.path_get_dirname(cible);

            this._modeBouton = new PanelMenu.Button(0.5, 'Mode Shadow', true);
            this._modePastille = new St.BoxLayout({y_align: Clutter.ActorAlign.CENTER});
            this._modeIcone = new St.Icon({icon_size: 14, y_align: Clutter.ActorAlign.CENTER});
            this._modeNom = new St.Label({y_align: Clutter.ActorAlign.CENTER});
            this._modePastille.add_child(this._modeIcone);
            this._modePastille.add_child(this._modeNom);
            this._modeBouton.add_child(this._modePastille);
            this._modeBouton.connect('button-press-event', () => {
                try {
                    // de préférence la page Modes du Centre Shadow, sinon l'appli Modes seule
                    const centre = `${GLib.path_get_dirname(this._modesDossier)}/centre/centre.py`;
                    const argv = GLib.file_test(centre, GLib.FileTest.IS_EXECUTABLE)
                        ? [centre, '--page', 'modes'] : [`${this._modesDossier}/modes.py`];
                    Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
                } catch (_e) {}
                return Clutter.EVENT_STOP;
            });
            Main.panel.addToStatusArea('shadow-mode', this._modeBouton, 20, 'left');

            GLib.mkdir_with_parents(MODES_ETAT, 0o755);
            this._modeMoniteur = Gio.File.new_for_path(MODES_ETAT).monitor_directory(Gio.FileMonitorFlags.NONE, null);
            this._modeMoniteurId = this._modeMoniteur.connect('changed', () => this._modeRafraichir());
            this._modeRafraichir();
        } catch (e) {
            console.error(`[shadow-os] indicateur de mode : ${e}`);
        }
    }

    _lireTexte(chemin) {
        try {
            const [ok, octets] = GLib.file_get_contents(chemin);
            return ok ? new TextDecoder().decode(octets) : null;
        } catch (_e) {
            return null;
        }
    }

    _modeRafraichir() {
        if (!this._modeBouton)
            return;
        try {
            const id = (this._lireTexte(`${MODES_ETAT}/actuel`) ?? MODE_BASE).trim() || MODE_BASE;
            const brut = id === MODE_BASE ? null : this._lireTexte(`${this._modesDossier}/definitions/${id}.json`);
            if (!brut) {
                this._modeBouton.hide();
                return;
            }
            const mode = JSON.parse(brut);
            const [c1, c2] = mode.couleurs ?? [ACCENT, '#FF4D8D'];
            this._modeIcone.icon_name = mode.symbole ?? 'shadow-os-symbolic';
            this._modeNom.text = mode.nom ?? id;
            this._modePastille.set_style(
                `background-gradient-direction: horizontal; background-gradient-start: ${c1}; background-gradient-end: ${c2};` +
                'border-radius: 99px; padding: 2px 11px 2px 9px; margin: 4px 2px; spacing: 6px;');
            this._modeNom.set_style('color: #ffffff; font-weight: 700; font-size: 0.92em;');
            this._modeIcone.set_style('color: #ffffff;');
            this._modeBouton.show();
        } catch (e) {
            console.error(`[shadow-os] indicateur de mode : ${e}`);
            this._modeBouton.hide();
        }
    }

    _retirerIndicateurMode() {
        if (this._modeMoniteur) {
            if (this._modeMoniteurId)
                this._modeMoniteur.disconnect(this._modeMoniteurId);
            this._modeMoniteur.cancel();
        }
        this._modeBouton?.destroy();
        this._modeMoniteur = null;
        this._modeMoniteurId = 0;
        this._modeBouton = this._modePastille = this._modeIcone = this._modeNom = null;
    }

    _parcourir(acteur) {
        if (!acteur)
            return;
        try {
            if (acteur.has_style_class_name?.('quick-toggle') ||
                acteur.has_style_class_name?.('quick-toggle-menu-button'))
                this._suivre(acteur);
            for (const enfant of acteur.get_children())
                this._parcourir(enfant);
        } catch (_e) {}
    }

    _suivre(acteur) {
        if (this._suivis.has(acteur)) {
            this._peindre(acteur);
            return;
        }
        const ids = [
            acteur.connect('notify::checked', () => this._peindre(acteur)),
            acteur.connect('notify::hover', () => this._peindre(acteur)),
            acteur.connect('destroy', () => this._suivis?.delete(acteur)),
        ];
        this._suivis.set(acteur, ids);
        this._peindre(acteur);
    }

    _peindre(acteur) {
        try {
            if (!acteur.checked) {
                acteur.set_style(null);
                return;
            }
            const fleche = acteur.has_style_class_name('quick-toggle-menu-button');
            const fond = acteur.hover ? SURVOL : (fleche ? FLECHE : ACCENT);
            acteur.set_style(`background-color: ${fond}; color: #ffffff;`);
        } catch (_e) {}
    }
}
