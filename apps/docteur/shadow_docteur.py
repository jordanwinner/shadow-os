#!/usr/bin/env python3
"""shadow-docteur — vérifie que Shadow est entier et le répare.

Usage :
  shadow docteur              diagnostic complet (rien n'est modifié)
  shadow docteur reparer      applique toutes les réparations proposées
  shadow docteur photo        retient les extensions actives comme état de référence
  shadow docteur json         diagnostic en JSON (Centre Shadow, îlot)
  shadow docteur auto         passage discret (minuteur) : répare ce qui est sans risque,
                              prévient par une notification pour le reste
  shadow docteur minuteur [on|off]   passage automatique toutes les 15 min

Sans risque (fait aussi par « auto ») : rallumer les extensions coupées en bloc,
rallumer une extension de référence éteinte, masquer le bouton Activités en
double, remettre le thème Shadow. Si GNOME recoupe les extensions dans la même
session (signe d'un plantage), « auto » ne les rallume pas une seconde fois et
prévient seulement.
"""
import json
import os
import shutil
import subprocess
import sys

MAISON = os.path.expanduser('~')
ICI = os.path.dirname(os.path.realpath(__file__))
SHADOW = os.path.realpath(os.path.join(ICI, '..', '..'))
CONFIG = os.path.join(os.environ.get('XDG_CONFIG_HOME', MAISON + '/.config'), 'shadow-os', 'docteur.json')
ETAT_DIR = os.path.join(os.environ.get('XDG_STATE_HOME', MAISON + '/.local/state'), 'shadow-os')
GARDE = os.path.join(ETAT_DIR, 'docteur-garde.json')      # réparations automatiques déjà tentées
EXT_DIR = os.path.join(MAISON, '.local/share/gnome-shell/extensions')
SHSH_REPO = os.environ.get('SHADOW_SHSH_REPO', os.path.join(MAISON, 'Dev/shsh'))
SHADOW_EXT = 'shadow-os@jordan'
LOGOMENU = 'logomenu@aryan_k'
USER_THEME = 'user-theme@gnome-shell-extensions.gcampax.github.com'
ETATS_EXT = {1: 'active', 2: 'éteinte', 3: 'en erreur', 4: 'périmée', 5: 'en téléchargement',
             6: 'pas encore chargée', 7: 'en arrêt', 8: 'en démarrage'}

OK, AVERT, PANNE = 'ok', 'avert', 'panne'


def lancer(*cmd, entree=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, input=entree, timeout=20)
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 127, ''


def gs(schema, cle, schemadir=None):
    cmd = ['gsettings'] + (['--schemadir', schemadir] if schemadir else []) + ['get', schema, cle]
    code, sortie = lancer(*cmd)
    return sortie if code == 0 else None


def gs_set(schema, cle, valeur, schemadir=None):
    cmd = ['gsettings'] + (['--schemadir', schemadir] if schemadir else []) + ['set', schema, cle, valeur]
    return lancer(*cmd)[0] == 0


def extensions_shell():
    """État de chaque extension selon GNOME Shell lui-même (D-Bus), ou None hors session."""
    try:
        from gi.repository import Gio
        p = Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SESSION, 0, None, 'org.gnome.Shell.Extensions',
                                           '/org/gnome/Shell/Extensions', 'org.gnome.Shell.Extensions', None)
        return p.call_sync('ListExtensions', None, 0, 5000, None).unpack()[0]
    except Exception:
        return None


def lire_json(chemin, defaut):
    try:
        with open(chemin) as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def ecrire_json(chemin, donnees):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    tmp = chemin + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(donnees, f, indent=1, ensure_ascii=False)
    os.replace(tmp, chemin)


def id_demarrage():
    try:
        with open('/proc/sys/kernel/random/boot_id') as f:
            return f.read().strip()
    except OSError:
        return ''


def actives_gsettings():
    brut = gs('org.gnome.shell', 'enabled-extensions') or '[]'
    brut = brut.replace('@as ', '')
    try:
        import ast
        return list(ast.literal_eval(brut))
    except (ValueError, SyntaxError):
        return []


def reference():
    """Extensions qui doivent être actives. Créée à la première visite à partir de l'état du moment."""
    ref = lire_json(CONFIG, {}).get('extensions')
    if ref is None and gs('org.gnome.shell', 'disable-user-extensions') == 'false':
        ref = sorted(actives_gsettings())
        photo(ref)
    return ref or []


def photo(liste=None):
    liste = sorted(liste if liste is not None else actives_gsettings())
    conf = lire_json(CONFIG, {})
    conf['extensions'] = liste
    ecrire_json(CONFIG, conf)
    return liste


# ── Les vérifications ──────────────────────────────────────────────────────
# Chacune renvoie une liste de constats :
#   {id, titre, etat, detail, reparation (texte), auto (bool), _faire (fonction)}

def constat(id_, titre, etat, detail='', reparation=None, auto=False, faire=None):
    return {'id': id_, 'titre': titre, 'etat': etat, 'detail': detail,
            'reparation': reparation, 'auto': auto, '_faire': faire}


def v_extensions():
    out = []
    coupees = gs('org.gnome.shell', 'disable-user-extensions') == 'true'
    if coupees:
        out.append(constat('extensions-coupees', 'Extensions', PANNE,
                           'toutes les extensions sont coupées : plus d\'îlot, de barre ni de tuiles Shadow',
                           'les rallumer', True,
                           lambda: gs_set('org.gnome.shell', 'disable-user-extensions', 'false')))
    ref = reference()
    shell = extensions_shell()
    actives = set(actives_gsettings())
    eteintes = [u for u in ref if u not in actives]
    if eteintes:
        def rallumer(us=tuple(eteintes)):
            return all(lancer('gnome-extensions', 'enable', u)[0] == 0 for u in us)
        out.append(constat('extensions-eteintes', 'Extensions', AVERT,
                           'éteintes alors qu\'elles font partie de Shadow : ' + ', '.join(e.split('@')[0] for e in eteintes),
                           'les rallumer', True, rallumer))
    if shell is not None and not coupees:
        for u in ref:
            info = shell.get(u)
            if info is None:
                out.append(constat('extension-absente', 'Extensions', PANNE,
                                   f'{u.split("@")[0]} n\'est plus installée',
                                   'shadow maj --seulement extensions, ou ./installer.sh --seulement extensions'))
                continue
            etat = int(info.get('state', 0))
            if etat in (3, 4):
                erreur = (info.get('error') or '').strip().splitlines()
                out.append(constat('extension-erreur', 'Extensions', PANNE,
                                   f'{u.split("@")[0]} {ETATS_EXT[etat]}' + (f' : {erreur[0][:120]}' if erreur else ''),
                                   'shadow maj --seulement extensions puis reconnexion' if etat == 4 else
                                   'voir journalctl --user -b | grep -i "' + u.split('@')[0] + '"'))
    if not out:
        n = len(ref)
        out.append(constat('extensions', 'Extensions', OK, f'{n} extension(s) de Shadow actives' if n else 'aucune référence'))
    return out


def v_barre():
    if SHADOW_EXT not in actives_gsettings() or LOGOMENU not in actives_gsettings():
        return []
    schemas = os.path.join(EXT_DIR, LOGOMENU, 'schemas')
    if gs('org.gnome.shell.extensions.logo-menu', 'show-activities-button', schemas) == 'true':
        return [constat('barre-doublon', 'Barre du haut', AVERT,
                        'Logo Menu réaffiche le bouton Activités : deux indicateurs d\'espaces',
                        'masquer le bouton Activités', True,
                        lambda: gs_set('org.gnome.shell.extensions.logo-menu', 'show-activities-button', 'false', schemas))]
    return [constat('barre', 'Barre du haut', OK, 'un seul indicateur d\'espaces')]


def v_theme():
    out = []
    theme_dir = os.path.join(MAISON, '.themes/Shadow/gnome-shell/gnome-shell.css')
    schemas = os.path.join(EXT_DIR, USER_THEME, 'schemas')
    nom = gs('org.gnome.shell.extensions.user-theme', 'name', schemas if os.path.isdir(schemas) else None)
    if not os.path.isfile(theme_dir):
        out.append(constat('theme-absent', 'Thème', PANNE, 'le thème Shadow n\'est plus dans ~/.themes',
                           'theme/eclipse.sh apply'))
    elif nom is not None and nom.strip("'") != 'Shadow':
        out.append(constat('theme-change', 'Thème', AVERT, f'thème du shell : {nom.strip(chr(39)) or "celui de GNOME"}',
                           'remettre le thème Shadow', True,
                           lambda: gs_set('org.gnome.shell.extensions.user-theme', 'name', 'Shadow',
                                          schemas if os.path.isdir(schemas) else None)))
    gtk = os.path.join(MAISON, '.config/gtk-4.0/gtk.css')
    if os.path.islink(gtk) and not os.path.exists(gtk):
        out.append(constat('gtk-casse', 'Thème', PANNE, '~/.config/gtk-4.0/gtk.css pointe vers un fichier disparu',
                           'theme/eclipse.sh apply'))
    code, etat = lancer(sys.executable, os.path.join(SHADOW, 'systeme/perf/fusionner-css.py'), 'etat')
    pas_fusionnees = [l.split(':')[0].strip() for l in etat.splitlines() if ':' in l and 'fusionnée' not in l]
    if code == 0 and pas_fusionnees:
        out.append(constat('css-fusion', 'Thème', AVERT,
                           'styles non fusionnés (verrouillage plus lent) : ' + ', '.join(p.split('@')[0] for p in pas_fusionnees),
                           'les refusionner (effet à la reconnexion)', False,
                           lambda: lancer(sys.executable, os.path.join(SHADOW, 'systeme/perf/fusionner-css.py'), 'appliquer')[0] == 0))
    code, etat = lancer(sys.executable, os.path.join(SHADOW, 'systeme/perf/alleger-blur-css.py'), 'etat')
    if code == 0 and etat and not etat.startswith('allégée') and os.path.isdir(os.path.join(EXT_DIR, 'blur-my-shell@aunetx')):
        out.append(constat('css-blur', 'Thème', AVERT, 'Blur my Shell n\'est plus allégé (verrouillage plus lent)',
                           'l\'alléger à nouveau', False,
                           lambda: lancer(sys.executable, os.path.join(SHADOW, 'systeme/perf/alleger-blur-css.py'), 'appliquer')[0] == 0))
    if not out:
        out.append(constat('theme', 'Thème', OK, 'Éclipse en place, styles fusionnés'))
    return out


def v_commandes():
    out = []
    bin_ = os.path.join(MAISON, '.local/bin')
    manquantes = [c for c in ('shadow', 'shadow-mode', 'shadow-modes', 'shadow-cible', 'shadow-maj', 'shadow-docteur')
                  if not os.access(os.path.join(bin_, c), os.X_OK)]
    if manquantes:
        out.append(constat('commandes', 'Commandes', AVERT, 'introuvables ou cassées : ' + ', '.join(manquantes),
                           './installer.sh --seulement scripts'))
    else:
        out.append(constat('commandes', 'Commandes', OK, 'shadow et ses outils répondent'))
    return out


def v_shsh():
    out = []
    try:
        import pwd
        connexion = pwd.getpwuid(os.getuid()).pw_shell
    except KeyError:
        connexion = ''
    shsh = '/usr/local/bin/shsh'
    if connexion == shsh and not os.access(shsh, os.X_OK):
        return [constat('shsh-absent', 'Shell', PANNE, 'shsh est le shell de connexion mais n\'est plus installé',
                        f'cd {SHSH_REPO} && outils/installer.sh (sinon : chsh -s /usr/bin/zsh)')]
    if not os.access(shsh, os.X_OK):
        return []
    code, sortie = lancer(shsh, '--version')
    installee = sortie.split()[-1] if code == 0 and sortie else '?'
    if code != 0:
        out.append(constat('shsh-casse', 'Shell', PANNE, 'shsh ne démarre plus', 'shadow maj --seulement shsh'))
    else:
        depot = ''
        try:
            with open(os.path.join(SHSH_REPO, 'Cargo.toml')) as f:
                depot = next((l.split('"')[1] for l in f if l.startswith('version')), '')
        except (OSError, IndexError):
            pass
        if depot and depot != installee:
            out.append(constat('shsh-version', 'Shell', AVERT, f'shsh {installee} installé, {depot} dans le dépôt',
                               'shadow maj --seulement shsh'))
        else:
            role = 'shell de connexion' if connexion == shsh else 'installé'
            out.append(constat('shsh', 'Shell', OK, f'shsh {installee}, {role}'))
    return out


def v_systeme():
    out = []
    if os.path.exists('/var/run/reboot-required'):
        out.append(constat('redemarrage', 'Système', AVERT, 'une mise à jour demande un redémarrage', 'redémarrer'))
    disque = shutil.disk_usage(MAISON)
    pris = 100 * (disque.total - disque.free) / disque.total
    if pris >= 95:
        out.append(constat('disque', 'Système', PANNE, f'disque plein à {pris:.0f} %', 'faire de la place'))
    elif pris >= 90:
        out.append(constat('disque', 'Système', AVERT, f'disque plein à {pris:.0f} %', 'faire de la place'))
    code, sortie = lancer('systemctl', '--user', '--failed', '--no-legend', '--plain')
    rates = [l.split()[0] for l in sortie.splitlines() if l.strip()]
    if rates:
        out.append(constat('services', 'Système', AVERT, 'services en échec : ' + ', '.join(rates),
                           'systemctl --user status ' + rates[0]))
    if not out:
        out.append(constat('systeme', 'Système', OK, f'disque à {pris:.0f} %, aucun service en échec'))
    return out


def v_mission():
    etat = lire_json(os.path.join(ETAT_DIR, 'cible'), None)
    if not etat:
        return []
    dossier = etat.get('dossier', '')
    if dossier and not os.path.isdir(dossier):
        return [constat('mission', 'Mission', AVERT, f'la mission {etat.get("nom")} pointe vers un dossier disparu',
                        'terminer la mission', False,
                        lambda: lancer(os.path.join(MAISON, '.local/bin/shadow-cible'), 'fin')[0] == 0)]
    return [constat('mission', 'Mission', OK, f'{etat.get("cible")} · {etat.get("nom")}')]


def v_arsenal():
    if not shutil.which('distrobox') or not shutil.which('podman'):
        return []
    code, _ = lancer('podman', 'container', 'exists', 'kali')
    if code != 0:
        return [constat('arsenal', 'Arsenal', AVERT, 'la box Kali a disparu', 'shadow arsenal setup')]
    return [constat('arsenal', 'Arsenal', OK, 'box Kali présente')]


VERIFS = (v_extensions, v_barre, v_theme, v_commandes, v_shsh, v_systeme, v_mission, v_arsenal)


def diagnostic():
    constats = []
    for v in VERIFS:
        try:
            constats += v()
        except Exception as e:                 # une vérification cassée ne doit pas masquer les autres
            constats.append(constat(v.__name__, v.__name__[2:].capitalize(), AVERT, f'vérification impossible : {e}'))
    return constats


# ── Affichage ──────────────────────────────────────────────────────────────
TTY = sys.stdout.isatty()
C = {'v': '\033[38;2;124;108;255m', 'r': '\033[38;2;255;77;141m', 'j': '\033[38;2;233;185;73m',
     'g': '\033[38;2;120;220;160m', 'd': '\033[38;2;110;106;150m', 'b': '\033[1m', 'z': '\033[0m'}
if not TTY:
    C = {k: '' for k in C}
SIGNE = {OK: f"{C['g']}✔{C['z']}", AVERT: f"{C['j']}!{C['z']}", PANNE: f"{C['r']}✘{C['z']}"}


def afficher(constats):
    print(f"\n{C['v']}{C['b']}◐ Shadow docteur{C['z']}")
    groupe = None
    for c in constats:
        if c['titre'] != groupe:
            groupe = c['titre']
            print(f"\n  {C['b']}{groupe}{C['z']}")
        print(f"   {SIGNE[c['etat']]} {c['detail']}")
        if c['etat'] != OK and c['reparation']:
            fleche = 'réparable : ' if c['_faire'] else 'à faire : '
            print(f"     {C['d']}→ {fleche}{c['reparation']}{C['z']}")
    soucis = [c for c in constats if c['etat'] != OK]
    reparables = [c for c in soucis if c['_faire']]
    print()
    if not soucis:
        print(f"  {C['g']}Shadow est en bonne santé.{C['z']}")
    else:
        print(f"  {len(soucis)} souci(s)" + (f", dont {len(reparables)} réparable(s) : {C['v']}shadow docteur reparer{C['z']}"
                                             if reparables else ''))
    return 1 if any(c['etat'] == PANNE for c in constats) else 0


def reparer(constats, seulement_auto=False):
    faites, ratees = [], []
    for c in constats:
        if c['etat'] == OK or not c['_faire'] or (seulement_auto and not c['auto']):
            continue
        try:
            (faites if c['_faire']() is not False else ratees).append(c)
        except Exception:
            ratees.append(c)
    return faites, ratees


def notifier(titre, texte, critique=False):
    cmd = ['notify-send', '-a', 'Shadow', '-i', 'shadow-os', titre, texte]
    if critique:
        cmd[1:1] = ['-u', 'critical']
    lancer(*cmd)


def auto():
    """Passage du minuteur : réparations sans risque, une seule fois par démarrage pour les extensions."""
    constats = diagnostic()
    garde = lire_json(GARDE, {})
    boot = id_demarrage()
    if garde.get('boot') != boot:
        garde = {'boot': boot, 'deja': [], 'signale': []}
    a_faire = []
    for c in constats:
        if c['etat'] == OK or not c['auto'] or not c['_faire']:
            continue
        if c['id'] in RISQUEES and c['id'] in garde['deja']:
            c['_faire'] = None                # déjà réparé depuis le démarrage et revenu : on prévient seulement
            c['auto'] = False
            continue
        a_faire.append(c)
    faites, ratees = reparer(a_faire, seulement_auto=True)
    garde['deja'] += [c['id'] for c in faites if c['id'] in RISQUEES and c['id'] not in garde['deja']]
    if faites:
        notifier('Shadow s\'est réparé', ' · '.join(f"{c['titre']} : {c['reparation']}" for c in faites))
    restants = [c for c in constats if c['etat'] != OK and c not in faites]
    nouveaux = [c for c in restants if c['id'] not in garde['signale']]
    if nouveaux:
        pannes = [c for c in nouveaux if c['etat'] == PANNE]
        notifier(f'Shadow docteur : {len(nouveaux)} souci(s)',
                 nouveaux[0]['detail'] + (' …' if len(nouveaux) > 1 else '') + ' — lance « shadow docteur »',
                 critique=bool(pannes))
        garde['signale'] += [c['id'] for c in nouveaux]
    # un souci réglé peut être signalé de nouveau s'il revient
    garde['signale'] = [i for i in garde['signale'] if any(c['id'] == i for c in restants)]
    ecrire_json(GARDE, garde)
    return 0


# Rallumer des extensions coupées par GNOME après un plantage peut le faire replanter :
# une seule tentative automatique par démarrage pour celles-ci.
RISQUEES = {'extensions-coupees', 'extensions-eteintes'}

UNITE = os.path.join(MAISON, '.config/systemd/user')


def minuteur(action):
    service = os.path.join(UNITE, 'shadow-docteur.service')
    timer = os.path.join(UNITE, 'shadow-docteur.timer')
    if action == 'off':
        lancer('systemctl', '--user', 'disable', '--now', 'shadow-docteur.timer')
        for f in (service, timer):
            if os.path.exists(f):
                os.unlink(f)
        lancer('systemctl', '--user', 'daemon-reload')
        print('Passage automatique arrêté')
        return 0
    if action == 'on':
        os.makedirs(UNITE, exist_ok=True)
        cmd = os.path.join(MAISON, '.local/bin/shadow-docteur')
        with open(service, 'w') as f:
            f.write('[Unit]\nDescription=Shadow docteur : vérifie et répare le bureau Shadow\n\n'
                    f'[Service]\nType=oneshot\nExecStart={cmd} auto\n')
        with open(timer, 'w') as f:
            f.write('[Unit]\nDescription=Shadow docteur toutes les 15 minutes\n\n'
                    '[Timer]\nOnStartupSec=90s\nOnUnitActiveSec=15min\n\n[Install]\nWantedBy=timers.target\n')
        lancer('systemctl', '--user', 'daemon-reload')
        code, _ = lancer('systemctl', '--user', 'enable', '--now', 'shadow-docteur.timer')
        print('Passage automatique toutes les 15 minutes' if code == 0 else 'Échec : systemctl --user enable shadow-docteur.timer')
        return code
    code, sortie = lancer('systemctl', '--user', 'is-active', 'shadow-docteur.timer')
    print('Passage automatique : ' + ('actif (toutes les 15 min)' if sortie == 'active' else 'arrêté'))
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ''
    if cmd in ('-h', '--help', 'aide'):
        print(__doc__.strip())
        return 0
    if cmd == 'photo':
        liste = photo()
        print(f'Référence enregistrée : {len(liste)} extension(s) actives\n  ' + '\n  '.join(liste))
        return 0
    if cmd == 'json':
        print(json.dumps([{k: v for k, v in c.items() if k != '_faire'} | {'reparable': bool(c['_faire'])}
                          for c in diagnostic()], ensure_ascii=False))
        return 0
    if cmd == 'auto':
        return auto()
    if cmd == 'minuteur':
        return minuteur(argv[2] if len(argv) > 2 else 'etat')
    if cmd in ('reparer', 'réparer'):
        faites, ratees = reparer(diagnostic())
        for c in faites:
            print(f"  {SIGNE[OK]} {c['titre']} : {c['reparation']}")
        for c in ratees:
            print(f"  {SIGNE[PANNE]} {c['titre']} : échec de « {c['reparation']} »")
        if not faites and not ratees:
            print('  Rien à réparer automatiquement.')
        return afficher(diagnostic())
    if cmd:
        print(f'shadow docteur : « {cmd} » inconnu (shadow docteur aide)', file=sys.stderr)
        return 2
    return afficher(diagnostic())


if __name__ == '__main__':
    sys.exit(main(sys.argv))
