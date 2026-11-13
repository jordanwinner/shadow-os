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
  shadow-modes json            tout l'état, pour l'appli Modes
"""
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


def activer(ident, annoncer=True):
    """Active un mode. Rend la liste des réglages qui ont échoué."""
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
    return {'actuel': actuel(), 'base': base(), 'modes': modes()}


# --- ligne de commande --------------------------------------------------------
def main(argv):
    cmd = argv[1] if len(argv) > 1 else 'liste'
    if cmd in ('liste', 'list'):
        a = actuel()
        for m in modes():
            print(f'{"●" if m["id"] == a else "○"} {m["id"]:<10} {m["nom"]:<11} {m.get("accroche", "")}')
    elif cmd in ('etat', 'status'):
        print(actuel())
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
