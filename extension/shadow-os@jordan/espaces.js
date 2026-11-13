// Shadow OS — indicateur des espaces de travail dans la barre (remplace Space Bar).
// Une pastille par espace : numéro, en Éclipse pour l'espace courant ; le dernier
// espace vide (celui que GNOME garde en réserve) s'affiche « + ».
// Aucune feuille de style : tout est en style en ligne, donc rien à recharger au verrouillage.
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import St from 'gi://St';

const BASE = 'border-radius: 99px; padding: 2px 9px; margin: 0 2px; font-weight: 700;';
const STYLES = {
    actif: `${BASE} background-color: #7C6CFF; color: #ffffff;`,
    occupe: `${BASE} background-color: rgba(236,235,250,0.07); color: rgba(236,235,250,0.85);`,
    vide: `${BASE} background-color: rgba(0,0,0,0); color: rgba(169,169,194,0.45);`,
};

export class Espaces {
    constructor() {
        this._signature = '';
        this._bouton = new PanelMenu.Button(0.0, 'Espaces de travail', true);
        this._bouton.set_style('-natural-hpadding: 4px; -minimum-hpadding: 2px;');
        this._boite = new St.BoxLayout({y_align: Clutter.ActorAlign.CENTER});
        this._bouton.add_child(this._boite);
        this._bouton.connect('scroll-event', (_a, evenement) => {
            const sens = evenement.get_scroll_direction();
            if (sens === Clutter.ScrollDirection.UP) this._voisin(-1);
            else if (sens === Clutter.ScrollDirection.DOWN) this._voisin(1);
            return Clutter.EVENT_STOP;
        });
        Main.panel.addToStatusArea('shadow-espaces', this._bouton, 1, 'left');

        const gestion = global.workspace_manager;
        this._ids = [
            [gestion, gestion.connect('notify::n-workspaces', () => this._demander())],
            [gestion, gestion.connect('active-workspace-changed', () => this._demander())],
            [global.display, global.display.connect('restacked', () => this._demander())],
        ];
        this._maj();
    }

    // plusieurs signaux arrivent en rafale : une seule mise à jour, au repos
    _demander() {
        if (this._attente) return;
        this._attente = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._attente = 0;
            this._maj();
            return GLib.SOURCE_REMOVE;
        });
    }

    _voisin(pas) {
        const gestion = global.workspace_manager;
        const cible = gestion.get_active_workspace_index() + pas;
        if (cible >= 0 && cible < gestion.n_workspaces)
            gestion.get_workspace_by_index(cible).activate(global.get_current_time());
    }

    _maj() {
        const gestion = global.workspace_manager;
        const n = gestion.n_workspaces, courant = gestion.get_active_workspace_index();
        const etats = [];
        for (let i = 0; i < n; i++) {
            const occupe = gestion.get_workspace_by_index(i).list_windows().some(f => !f.is_on_all_workspaces() && !f.is_skip_taskbar());
            etats.push(i === courant ? 'actif' : occupe ? 'occupe' : 'vide');
        }
        // le dernier espace, vide et non courant, est la réserve de GNOME : « + »
        const reserve = n > 1 && etats[n - 1] === 'vide';
        const signature = `${etats.join(',')}|${reserve}`;
        if (signature === this._signature) return;
        this._signature = signature;
        this._boite.destroy_all_children();
        etats.forEach((etat, i) => {
            const pastille = new St.Button({
                label: reserve && i === n - 1 ? '+' : String(i + 1),
                style: STYLES[etat], y_align: Clutter.ActorAlign.CENTER,
            });
            pastille.connect('clicked', () => gestion.get_workspace_by_index(i)?.activate(global.get_current_time()));
            this._boite.add_child(pastille);
        });
    }

    destroy() {
        if (this._attente) GLib.source_remove(this._attente);
        this._attente = 0;
        for (const [objet, id] of this._ids) objet.disconnect(id);
        this._ids = [];
        this._bouton.destroy();
        this._bouton = null;
    }
}
