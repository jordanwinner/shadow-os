// Shadow OS — rangement automatique des fenêtres en tuiles (remplace Tiling Shell).
//
// Disposition « principale + pile », par espace de travail et par écran :
//   1 fenêtre  : tout l'écran ;
//   2 fenêtres : côte à côte ;
//   3 et plus  : la principale à gauche, les autres empilées à droite.
// Super+flèches : passer à la fenêtre voisine. Super+Maj+flèches : échanger deux fenêtres.
// Glisser une fenêtre sur une autre les échange aussi.
//
// Le moteur ne garde aucune table : chaque fenêtre porte un numéro d'ordre, et la
// disposition se recalcule à partir de la liste des fenêtres présentes.
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';

const SENS = {gauche: [-1, 0], droite: [1, 0], haut: [0, -1], bas: [0, 1]};
const BORDURE = 'border: 2px solid #7C6CFF; border-radius: 12px;';
const TRACE = GLib.getenv('SHADOW_ESSAI') === '1';      // banc d'essai : écrit chaque disposition dans le journal

export class Tuiles {
    constructor(reglages) {
        this._reglages = reglages;
        this._actif = false;
        this._ordre = 0;
        this._reglageId = reglages.connect('changed', (_r, cle) => {
            if (cle === 'tuiles') this._basculer();
            else if (cle.startsWith('tuiles-') && this._actif) { this._majBordure(); this._demander(); }
        });
        this._basculer();
    }

    destroy() {
        this._reglages.disconnect(this._reglageId);
        this._arreter();
        this._reglages = null;
    }

    _basculer() {
        const voulu = this._reglages.get_boolean('tuiles');
        if (TRACE) console.log(`[shadow-tuiles] réglage tuiles=${voulu}`);
        if (voulu === this._actif) return;
        if (voulu) this._demarrer(); else this._arreter();
    }

    // ------------------------------------------------------------------ cycle de vie
    _demarrer() {
        this._actif = true;
        this._ids = [];
        const suivre = (objet, signal, rappel) => this._ids.push([objet, objet.connect(signal, rappel)]);
        suivre(global.window_manager, 'map', (_g, acteur) => this._adopter(acteur.meta_window));
        suivre(global.window_manager, 'destroy', () => this._demander());
        suivre(global.window_manager, 'minimize', () => this._demander());
        suivre(global.window_manager, 'unminimize', () => this._demander());
        suivre(global.display, 'grab-op-end', (_d, fenetre, op) => this._finGlisser(fenetre, op));
        suivre(global.display, 'workareas-changed', () => this._demander());
        suivre(global.display, 'notify::focus-window', () => this._majBordure());
        suivre(global.display, 'restacked', () => this._replacerBordure());
        suivre(global.workspace_manager, 'active-workspace-changed', () => { this._demander(); this._majBordure(); });
        suivre(Main.overview, 'showing', () => this._majBordure());
        suivre(Main.overview, 'hidden', () => this._majBordure());

        for (const sens of Object.keys(SENS)) {
            Main.wm.addKeybinding(`tuiles-focus-${sens}`, this._reglages, Meta.KeyBindingFlags.NONE,
                Shell.ActionMode.NORMAL, () => this._voisine(sens, false));
            Main.wm.addKeybinding(`tuiles-deplacer-${sens}`, this._reglages, Meta.KeyBindingFlags.NONE,
                Shell.ActionMode.NORMAL, () => this._voisine(sens, true));
        }

        this._bordure = new St.Widget({style: BORDURE, reactive: false, visible: false});
        global.window_group.add_child(this._bordure);

        for (const acteur of global.get_window_actors())
            this._adopter(acteur.meta_window, false);
        this._demander();
        this._majBordure();
    }

    _arreter() {
        if (!this._actif) return;
        this._actif = false;
        for (const [objet, id] of this._ids) objet.disconnect(id);
        this._ids = [];
        for (const sens of Object.keys(SENS)) {
            Main.wm.removeKeybinding(`tuiles-focus-${sens}`);
            Main.wm.removeKeybinding(`tuiles-deplacer-${sens}`);
        }
        if (this._attente) GLib.source_remove(this._attente);
        if (this._rappel) GLib.source_remove(this._rappel);
        this._attente = this._rappel = 0;
        for (const acteur of global.get_window_actors()) {
            const f = acteur.meta_window;
            if (f?._shadowIds) {
                f._shadowIds.forEach(id => f.disconnect(id));
                delete f._shadowIds;
            }
        }
        this._suivreFenetre(null);
        this._bordure?.destroy();
        this._bordure = null;
    }

    // ------------------------------------------------------------------ fenêtres
    _rangeable(f) {
        return f && f.get_window_type() === Meta.WindowType.NORMAL && !f.is_skip_taskbar() &&
            !f.get_transient_for() && !f.minimized && !f.is_on_all_workspaces() &&
            f.resizeable && !f.is_fullscreen() && !f.is_above?.();        // (allows_resize() est faux si maximisée)
    }

    _adopter(f, retiler = true) {
        if (!f || f._shadowIds) return;
        if (TRACE) console.log(`[shadow-tuiles] fenêtre ${f.get_wm_class()} type=${f.get_window_type()} rangeable=${this._rangeable(f)}`);
        if (f.get_window_type() !== Meta.WindowType.NORMAL) return;
        f._shadowOrdre = ++this._ordre;                 // les nouvelles fenêtres arrivent en fin de pile
        f._shadowIds = [
            f.connect('workspace-changed', () => this._demander()),
            f.connect('notify::fullscreen', () => { this._demander(); this._majBordure(); }),
            f.connect('unmanaged', () => this._demander()),
        ];
        if (retiler) this._demander();
    }

    _fenetres(espace, ecran) {
        return espace.list_windows()
            .filter(f => f.get_monitor() === ecran && this._rangeable(f))
            .sort((a, b) => (a._shadowOrdre ?? 0) - (b._shadowOrdre ?? 0));
    }

    // ------------------------------------------------------------------ disposition
    _demander() {
        if (!this._actif || this._attente) return;
        this._attente = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 70, () => {
            this._attente = 0;
            this._ranger();
            // certaines applis n'acceptent leur taille qu'après leur première image : second passage
            if (this._rappel) GLib.source_remove(this._rappel);
            this._rappel = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 320, () => {
                this._rappel = 0;
                if (this._actif) this._ranger();
                return GLib.SOURCE_REMOVE;
            });
            return GLib.SOURCE_REMOVE;
        });
    }

    _zones(aire, n) {
        const e = this._reglages.get_int('tuiles-ecart');
        const x = aire.x + e, y = aire.y + e, l = aire.width - 2 * e, h = aire.height - 2 * e;
        if (n === 1) return [[x, y, l, h]];
        const part = Math.min(0.8, Math.max(0.3, this._reglages.get_double('tuiles-part-principale')));
        const lp = n === 2 ? Math.floor((l - e) / 2) : Math.floor((l - e) * part);
        const zones = [[x, y, lp, h]];
        const reste = n - 1, xd = x + lp + e, ld = l - lp - e;
        const hd = Math.floor((h - e * (reste - 1)) / reste);
        for (let i = 0; i < reste; i++)
            zones.push([xd, y + i * (hd + e), ld, i === reste - 1 ? h - i * (hd + e) : hd]);
        return zones;
    }

    _ranger() {
        try {
            const gestion = global.workspace_manager;
            const ecrans = global.display.get_n_monitors();
            for (let i = 0; i < gestion.n_workspaces; i++) {
                const espace = gestion.get_workspace_by_index(i);
                for (let ecran = 0; ecran < ecrans; ecran++) {
                    const liste = this._fenetres(espace, ecran);
                    if (!liste.length) continue;
                    const zones = this._zones(espace.get_work_area_for_monitor(ecran), liste.length);
                    liste.forEach((f, k) => this._placer(f, zones[k]));
                    if (TRACE)
                        console.log(`[shadow-tuiles] espace ${i} : ${liste.map((f, k) => `${f.get_wm_class()}=${zones[k].join(',')}`).join(' | ')}`);
                }
            }
            this._majBordure();
        } catch (e) {
            console.error(`[shadow-os] tuiles : ${e}`);
        }
    }

    _placer(f, [x, y, l, h]) {
        // l'API de maximisation a changé avec GNOME 49
        const maximisee = f.is_maximized ? f.is_maximized() : f.get_maximized?.() !== 0;
        if (maximisee) {
            try { f.unmaximize(); } catch (_e) { f.unmaximize(Meta.MaximizeFlags.BOTH); }
        }
        const r = f.get_frame_rect();
        if (r.x !== x || r.y !== y || r.width !== l || r.height !== h)
            f.move_resize_frame(true, x, y, l, h);
    }

    // ------------------------------------------------------------------ clavier et souris
    _voisine(sens, echanger) {
        const active = global.display.focus_window;
        if (!active || !this._rangeable(active)) return;
        const [dx, dy] = SENS[sens];
        const a = active.get_frame_rect();
        const ax = a.x + a.width / 2, ay = a.y + a.height / 2;
        let meilleure = null, score = Infinity;
        for (const f of this._fenetres(active.get_workspace(), active.get_monitor())) {
            if (f === active) continue;
            const r = f.get_frame_rect();
            const ex = r.x + r.width / 2 - ax, ey = r.y + r.height / 2 - ay;
            const avance = ex * dx + ey * dy;               // distance dans le sens demandé
            if (avance <= 1) continue;
            const ecart = Math.abs(ex * dy) + Math.abs(ey * dx);    // décalage sur l'autre axe
            const s = avance + 2 * ecart;
            if (s < score) { score = s; meilleure = f; }
        }
        if (!meilleure) return;
        if (echanger) {
            [active._shadowOrdre, meilleure._shadowOrdre] = [meilleure._shadowOrdre, active._shadowOrdre];
            this._demander();
        } else {
            meilleure.activate(global.get_current_time());
        }
    }

    _finGlisser(f, op) {
        if (!this._actif || !f || !this._rangeable(f)) return;
        const deplacement = op === Meta.GrabOp.MOVING || op === Meta.GrabOp.KEYBOARD_MOVING ||
            (Meta.GrabOp.MOVING_UNCONSTRAINED !== undefined && op === Meta.GrabOp.MOVING_UNCONSTRAINED);
        if (deplacement) {
            // lâchée sur une autre tuile : les deux échangent leur place
            const [px, py] = global.get_pointer();
            const cible = this._fenetres(f.get_workspace(), f.get_monitor()).find(autre => {
                if (autre === f) return false;
                const r = autre.get_frame_rect();
                return px >= r.x && px < r.x + r.width && py >= r.y && py < r.y + r.height;
            });
            if (cible)
                [f._shadowOrdre, cible._shadowOrdre] = [cible._shadowOrdre, f._shadowOrdre];
        }
        this._demander();                                   // déplacée ou redimensionnée : elle reprend sa tuile
    }

    // ------------------------------------------------------------------ liseré de la fenêtre active
    _suivreFenetre(f) {
        if (this._suivie && this._suivieIds) {
            try { this._suivieIds.forEach(id => this._suivie.disconnect(id)); } catch (_e) {}
        }
        this._suivie = f;
        this._suivieIds = f ? [
            f.connect('position-changed', () => this._poserBordure()),
            f.connect('size-changed', () => this._poserBordure()),
        ] : null;
    }

    _majBordure() {
        if (!this._bordure) return;
        const f = global.display.focus_window;
        const montrer = this._actif && this._reglages.get_boolean('tuiles-bordure') && !Main.overview.visible &&
            f && this._rangeable(f) && f.get_workspace() === global.workspace_manager.get_active_workspace();
        if (!montrer) {
            this._bordure.hide();
            this._suivreFenetre(null);
            return;
        }
        if (f !== this._suivie) this._suivreFenetre(f);
        this._poserBordure();
        this._bordure.show();
        this._replacerBordure();
    }

    _poserBordure() {
        if (!this._bordure || !this._suivie) return;
        const r = this._suivie.get_frame_rect();
        this._bordure.set_position(r.x - 1, r.y - 1);
        this._bordure.set_size(r.width + 2, r.height + 2);
    }

    _replacerBordure() {
        if (!this._bordure?.visible || !this._suivie) return;
        const acteur = this._suivie.get_compositor_private();
        if (acteur && acteur.get_parent() === global.window_group)
            global.window_group.set_child_above_sibling(this._bordure, acteur);
    }
}
