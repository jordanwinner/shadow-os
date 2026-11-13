#!/usr/bin/env python3
"""shadow-modes — les Modes de Shadow, comme sur un téléphone.

Un mode change tout le bureau d'un coup : fond d'écran, couleur d'accent,
fenêtres (flottantes ou en tuiles), notifications, énergie, lumière nocturne,
îlot, HUD et box Kali. Le mode « quotidien » n'impose rien : c'est ton
bureau habituel. Il est photographié au moment où tu le quittes et remis à
l'identique quand tu y reviens.

Usage :
  shadow-modes                 liste des modes (● = actif)
  shadow-modes activer ID      active un mode (pentest, focus, jeu, nuit…)
  shadow-modes quotidien       revient au bureau habituel
  shadow-modes etat            identifiant du mode actif
  shadow-modes auto [on|off|etat] [DEBUT FIN]
                               routine « Nuit automatique » (ex. : auto on 22:00 06:00)
  shadow-modes json            tout l'état, pour l'appli Modes
"""
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys

ICI = os.path.dirname(os.path.realpath(__file__))
DEFINITIONS = os.path.join(ICI, 'definitions')
MAISON = os.path.expanduser('~')
ETAT_DIR = os.path.join(os.environ.get('XDG_STATE_HOME', MAISON + '/.local/state'), 'shadow-os', 'modes')
ACTUEL = os.path.join(ETAT_DIR, 'actuel')
BASE = os.path.join(ETAT_DIR, 'quotidien.json')
FONDS = MAISON + '/.local/share/backgrounds/shadow'
BASE_ID = 'quotidien'
# routine « Nuit automatique »
CONFIG = os.path.join(os.environ.get('XDG_CONFIG_HOME', MAISON + '/.config'), 'shadow-os', 'modes.json')
AUTO = os.path.join(ETAT_DIR, 'auto')               # présent : le mode en cours a été mis par la routine
PASSE = os.path.join(ETAT_DIR, 'nuit-passee')       # nuit que l'utilisateur a refusée (ne pas insister)
MODE_NUIT = 'nuit'
UNITES = MAISON + '/.config/systemd/user'
MINUTEUR = 'shadow-modes-routine.timer'

ILOT_SCHEMAS = MAISON + '/.local/share/gnome-shell/extensions/dynamic-island-v2@jordan/schemas'
ILOT = 'org.gnome.shell.extensions.dynamic-island-v2'
ENERGIE_ETAT = '/etc/shadow-os/energie-profil'
ENERGIE_ASSISTANT = '/usr/local/libexec/shadow-energie'
FENETRES = MAISON + '/.local/bin/shadow-mode'
HUD_CONF = MAISON + '/.config/conky/cyber.conf'
BOX = 'kali'


# --- outils -----------------------------------------------------------------
def sh(*cmd, delai=20, env=None):
    """Lance une commande, rend (ok, sortie). Ne lève jamais."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=delai,
                           env={**os.environ, **env} if env else None)
        return r.returncode == 0, r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False, ''


def detache(*cmd):
    """Lance une commande sans l'attendre (appli, démarrage de la box…)."""
    try:
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False


def gget(schema, cle, dossier=None):
    cmd = ['gsettings'] + (['--schemadir', dossier] if dossier else []) + ['get', schema, cle]
    ok, v = sh(*cmd)
    return v if ok else None


def gset(schema, cle, valeur, dossier=None):
    cmd = ['gsettings'] + (['--schemadir', dossier] if dossier else []) + ['set', schema, cle, valeur]
    return sh(*cmd)[0]


def chaine(v):          # "'rouge'" -> "rouge"
    return v[1:-1] if v and len(v) >= 2 and v[0] == v[-1] == "'" else v


# --- leviers : chacun sait lire et écrire UN aspect du bureau -----------------
class Levier:
    nom = ''            # clé dans les définitions de mode
    libelle = ''        # pour les messages

    def dispo(self):
        return True

    def lire(self):
        raise NotImplementedError

    def ecrire(self, valeur):
        raise NotImplementedError


class Accent(Levier):
    nom, libelle = 'accent', 'couleur d’accent'

    def lire(self):
        return chaine(gget('org.gnome.desktop.interface', 'accent-color'))

    def ecrire(self, v):
        return gset('org.gnome.desktop.interface', 'accent-color', v)


class Fond(Levier):
    """Fond d'écran (bureau + verrouillage) et diaporama."""
    nom, libelle = 'fond', 'fond d’écran'
    BG, VERROU = 'org.gnome.desktop.background', 'org.gnome.desktop.screensaver'

    def lire(self):
        return {
            'uri': chaine(gget(self.BG, 'picture-uri')),
            'uri_sombre': chaine(gget(self.BG, 'picture-uri-dark')),
            'verrou': chaine(gget(self.VERROU, 'picture-uri')),
            'diaporama': sh('systemctl', '--user', 'is-active', 'slideshow.timer')[1] == 'active',
        }

    def ecrire(self, v):
        # le diaporama d'abord : sinon il remplacerait le fond du mode
        sh('systemctl', '--user', 'start' if v.get('diaporama') else 'stop', 'slideshow.timer')
        ok = gset(self.BG, 'picture-uri', v['uri'])
        ok = gset(self.BG, 'picture-uri-dark', v['uri_sombre']) and ok
        gset(self.BG, 'picture-options', 'zoom')
        if v.get('verrou'):
            gset(self.VERROU, 'picture-uri', v['verrou'])
        return ok


class Fenetres(Levier):
    nom, libelle = 'fenetres', 'fenêtres'

    def dispo(self):
        return os.access(FENETRES, os.X_OK)

    def lire(self):
        ok, v = sh(FENETRES, 'etat')
        return v if ok and v in ('flottant', 'tuiles') else None

    def ecrire(self, v):
        return sh(FENETRES, v, env={'SHADOW_MODE_SILENCE': '1'})[0]


class NePasDeranger(Levier):
    nom, libelle = 'ne_pas_deranger', 'ne pas déranger'

    def lire(self):
        return gget('org.gnome.desktop.notifications', 'show-banners') == 'false'

    def ecrire(self, v):
        return gset('org.gnome.desktop.notifications', 'show-banners', 'false' if v else 'true')


class LumiereNocturne(Levier):
    nom, libelle = 'lumiere_nocturne', 'lumière nocturne'
    S = 'org.gnome.settings-daemon.plugins.color'

    def lire(self):
        return gget(self.S, 'night-light-enabled') == 'true'

    def ecrire(self, v):
        return gset(self.S, 'night-light-enabled', 'true' if v else 'false')


class Energie(Levier):
    nom, libelle = 'energie', 'énergie'

    def dispo(self):
        return os.access(ENERGIE_ASSISTANT, os.X_OK)

    def lire(self):
        try:
            with open(ENERGIE_ETAT) as f:
                v = f.read().strip()
            return v if v in ('frais', 'equilibre', 'performance') else None
        except OSError:
            return None

    def ecrire(self, v):
        return sh('pkexec', ENERGIE_ASSISTANT, v, delai=40)[0]


class IlotTheme(Levier):
    nom, libelle, cle = 'ilot_theme', 'thème de l’îlot', 'theme'

    def dispo(self):
        return os.path.isdir(ILOT_SCHEMAS)

    def lire(self):
        return chaine(gget(ILOT, self.cle, ILOT_SCHEMAS))

    def ecrire(self, v):
        return gset(ILOT, self.cle, v, ILOT_SCHEMAS)


class IlotRepos(IlotTheme):
    nom, libelle, cle = 'ilot_repos', 'îlot au repos', 'idle-mode'


class Hud(Levier):
    """HUD conky sur le bureau."""
    nom, libelle = 'hud', 'HUD'

    def dispo(self):
        return bool(shutil.which('conky')) and os.path.exists(HUD_CONF)

    def lire(self):
        return sh('pgrep', '-x', 'conky')[0]

    def ecrire(self, v):
        if v:
            return detache('conky', '--config=' + HUD_CONF)
        sh('pkill', '-x', 'conky')
        return True


class Arsenal(Levier):
    """Box Kali (distrobox/podman) démarrée ou arrêtée."""
    nom, libelle = 'arsenal', 'box Kali'

    def dispo(self):
        return bool(shutil.which('podman')) and sh('podman', 'container', 'exists', BOX)[0]

    def lire(self):
        return sh('podman', 'ps', '--filter', f'name=^{BOX}$', '--format', '{{.Names}}')[1] == BOX

    def ecrire(self, v):
        # long (plusieurs secondes) : en arrière-plan pour ne pas figer le changement de mode
        return detache('podman', 'start', BOX) if v else detache('podman', 'stop', '-t', '3', BOX)


LEVIERS = [Fond(), Accent(), Fenetres(), NePasDeranger(), LumiereNocturne(),
           IlotTheme(), IlotRepos(), Hud(), Energie(), Arsenal()]
PAR_NOM = {l.nom: l for l in LEVIERS}


# --- définitions de mode ------------------------------------------------------
def modes():
    """Tous les modes, dans l'ordre d'affichage."""
    liste = []
    for chemin in glob.glob(os.path.join(DEFINITIONS, '*.json')):
        try:
            with open(chemin) as f:
                m = json.load(f)
            m.setdefault('id', os.path.splitext(os.path.basename(chemin))[0])
            liste.append(m)
        except (OSError, ValueError) as e:
            print(f'définition ignorée ({chemin}) : {e}', file=sys.stderr)
    return sorted(liste, key=lambda m: (m.get('ordre', 99), m['id']))


def mode(ident):
    return next((m for m in modes() if m['id'] == ident), None)


def chemin_fond(nom):
    return nom if os.path.isabs(nom) else os.path.join(FONDS, nom)


def reglages(m):
    """Réglages voulus par un mode, au format des leviers."""
    r = {}
    for nom, v in (m.get('reglages') or {}).items():
        if nom not in PAR_NOM:
            continue
        if nom == 'fond':
            uri = 'file://' + chemin_fond(v)
            v = {'uri': uri, 'uri_sombre': uri, 'verrou': uri, 'diaporama': False}
        r[nom] = v
    return r


# --- état -----------------------------------------------------------------------
def actuel():
    try:
        with open(ACTUEL) as f:
            ident = f.read().strip()
        return ident if mode(ident) else BASE_ID
    except OSError:
        return BASE_ID


def base():
    """Bureau habituel : la photo prise en quittant « quotidien », sinon l'état présent."""
    try:
        with open(BASE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return photographier()


def photographier():
    return {l.nom: l.lire() for l in LEVIERS if l.dispo()}


def activer(ident, annoncer=True, auto=False):
    """Active un mode. Rend la liste des réglages qui ont échoué.

    auto=True : appel de la routine. Un changement fait à la main pendant une nuit
    automatique est respecté : la routine ne réactivera pas la nuit avant le lendemain.
    """
    m = mode(ident)
    if not m:
        raise ValueError(f'mode inconnu : {ident}')
    avant = actuel()
    os.makedirs(ETAT_DIR, exist_ok=True)
    if avant == BASE_ID and not os.path.exists(BASE):
        if ident == BASE_ID:
            return []
        photo = photographier()
        with open(BASE, 'w') as f:
            json.dump(photo, f, indent=1, ensure_ascii=False)
    else:
        photo = base()

    # cible = bureau habituel + ce que le mode impose ; on ne touche qu'à ce qui diffère
    cible = dict(photo)
    cible.update(reglages(m))
    echecs = []
    for l in LEVIERS:
        if l.nom not in cible or cible[l.nom] is None or not l.dispo():
            continue
        try:
            if l.lire() != cible[l.nom] and not l.ecrire(cible[l.nom]):
                echecs.append(l.libelle)
        except Exception:                                   # un levier en panne ne bloque pas les autres
            echecs.append(l.libelle)

    with open(ACTUEL, 'w') as f:
        f.write(ident + '\n')
    if auto and ident != BASE_ID:
        open(AUTO, 'w').close()
    else:
        if not auto and os.path.exists(AUTO) and avant == MODE_NUIT and ident != MODE_NUIT:
            with open(PASSE, 'w') as f:
                f.write(nuit_en_cours(config()) or '')
        try:
            os.unlink(AUTO)
        except OSError:
            pass
    if ident == BASE_ID:
        try:
            os.unlink(BASE)
        except OSError:
            pass
    elif ident != avant:
        for cmd in m.get('lancer') or []:
            detache(*[os.path.expanduser(a) for a in cmd])
    if annoncer:
        corps = m.get('accroche', '')
        if echecs:
            corps = 'Non appliqué : ' + ', '.join(echecs)
        sh('notify-send', '-a', 'Shadow', '-i', m.get('icone', 'shadow-os'), '-t', '2600', '-e',
           '-h', 'string:x-canonical-private-synchronous:shadow-modes', f'Mode {m["nom"]}', corps)
    return echecs


def etat_complet():
    return {'actuel': actuel(), 'base': base(), 'modes': modes(), 'routine': config()}


# --- routine « Nuit automatique » ----------------------------------------------
def config():
    c = {'nuit_auto': False, 'nuit_debut': '22:00', 'nuit_fin': '06:00'}
    try:
        with open(CONFIG) as f:
            c.update(json.load(f))
    except (OSError, ValueError):
        pass
    return c


def heure(texte):
    h, m = texte.split(':')
    h, m = int(h), int(m)
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(texte)
    return datetime.time(h, m)


def nuit_en_cours(c, maintenant=None):
    """Identifiant de la nuit en cours (date de son début), ou None en journée."""
    n = maintenant or datetime.datetime.now()
    debut, fin = heure(c['nuit_debut']), heure(c['nuit_fin'])
    t = n.time()
    if debut <= fin:                                    # plage dans la même journée
        return n.date().isoformat() if debut <= t < fin else None
    if t >= debut:                                      # plage à cheval sur minuit, côté soir
        return n.date().isoformat()
    if t < fin:                                         # … côté matin : la nuit a commencé la veille
        return (n.date() - datetime.timedelta(days=1)).isoformat()
    return None


def routine(maintenant=None):
    """Appelée toutes les 5 min : met le mode Nuit le soir, rend le bureau habituel le matin."""
    c = config()
    nuit = nuit_en_cours(c, maintenant) if c['nuit_auto'] else None
    a, par_routine = actuel(), os.path.exists(AUTO)
    if nuit and a == BASE_ID:
        try:
            with open(PASSE) as f:
                if f.read().strip() == nuit:            # refusée ce soir : on n'insiste pas
                    return 'nuit refusée ce soir'
        except OSError:
            pass
        if mode(MODE_NUIT):
            activer(MODE_NUIT, auto=True)
            return 'nuit activée'
    elif not nuit and par_routine and a == MODE_NUIT:
        activer(BASE_ID, auto=True)
        return 'retour au quotidien'
    return 'rien à faire'


def regler_auto(actif, debut=None, fin=None):
    """Enregistre la routine et (dés)active son minuteur systemd utilisateur."""
    c = config()
    c['nuit_auto'] = bool(actif)
    if debut:
        heure(debut); c['nuit_debut'] = debut
    if fin:
        heure(fin); c['nuit_fin'] = fin
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, 'w') as f:
        json.dump(c, f, indent=1)
    os.makedirs(UNITES, exist_ok=True)
    moi = os.path.realpath(__file__)
    with open(os.path.join(UNITES, 'shadow-modes-routine.service'), 'w') as f:
        f.write(f'[Unit]\nDescription=Shadow — routine des modes (Nuit automatique)\n\n'
                f'[Service]\nType=oneshot\nExecStart={moi} routine\n')
    with open(os.path.join(UNITES, MINUTEUR), 'w') as f:
        f.write('[Unit]\nDescription=Shadow — routine des modes, toutes les 5 minutes\n\n'
                '[Timer]\nOnCalendar=*:0/5\nOnStartupSec=45\nPersistent=false\n\n'
                '[Install]\nWantedBy=timers.target\n')
    sh('systemctl', '--user', 'daemon-reload')
    sh('systemctl', '--user', 'enable' if actif else 'disable', '--now', MINUTEUR)
    if actif:
        routine()
    elif os.path.exists(AUTO) and actuel() == MODE_NUIT:    # coupée en pleine nuit automatique : on rend le bureau
        activer(BASE_ID, auto=True)
    return c


# --- ligne de commande --------------------------------------------------------
def main(argv):
    cmd = argv[1] if len(argv) > 1 else 'liste'
    if cmd in ('liste', 'list'):
        a = actuel()
        for m in modes():
            print(f'{"●" if m["id"] == a else "○"} {m["id"]:<10} {m["nom"]:<11} {m.get("accroche", "")}')
    elif cmd in ('etat', 'status'):
        print(actuel())
    elif cmd == 'routine':
        print(routine())
    elif cmd == 'auto':
        sous = argv[2] if len(argv) > 2 else 'etat'
        try:
            if sous in ('on', 'off'):
                c = regler_auto(sous == 'on', *(argv[3:5]))
            elif sous == 'etat':
                c = config()
            else:
                sys.exit('usage : shadow-modes auto [on|off|etat] [DEBUT FIN]')
        except ValueError:
            sys.exit('heure invalide (format HH:MM)')
        print(f'Nuit automatique : {"activée" if c["nuit_auto"] else "désactivée"} · {c["nuit_debut"]} → {c["nuit_fin"]}')
    elif cmd == 'json':
        json.dump(etat_complet(), sys.stdout, indent=1, ensure_ascii=False)
        print()
    elif cmd in ('activer', 'quotidien') or mode(cmd):
        ident = BASE_ID if cmd == 'quotidien' else (argv[2] if cmd == 'activer' and len(argv) > 2 else cmd)
        if cmd == 'activer' and len(argv) < 3:
            sys.exit('usage : shadow-modes activer ID')
        try:
            echecs = activer(ident)
        except ValueError as e:
            sys.exit(str(e))
        print(f'Mode {mode(ident)["nom"]}' + (f' (non appliqué : {", ".join(echecs)})' if echecs else ''))
        return 1 if echecs else 0
    else:
        print(__doc__.strip())
        return 0 if cmd in ('-h', '--help', 'aide') else 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
