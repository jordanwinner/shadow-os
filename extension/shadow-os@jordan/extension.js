// Shadow OS — intégration du bureau.
// GNOME 50 peint les tuiles actives des réglages rapides avec l'accent système
// (choix limité à 10 couleurs), quel que soit le thème. On repeint donc chaque
// tuile active en style en ligne avec l'accent Éclipse, sans toucher au reste.
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const ACCENT = '#7C6CFF';
const SURVOL = '#8D7FFF';
const FLECHE = '#6E5DF2';

export default class ShadowOS extends Extension {
    enable() {
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
