#!/usr/bin/env python3
"""shadow-cible — la cible de la mission en cours (mode Pentest de Shadow).

Fixer une cible :
  - l'affiche en permanence dans l'îlot ;
  - crée le dossier de mission (~/ctf/NOM : notes.md, scans/, butin/) ;
  - la fournit aux nouveaux terminaux, y compris ceux de la box Kali :
    $CIBLE et $TARGET (l'adresse), $MISSION (le dossier).

Usage :
  shadow-cible                    affiche la cible en cours
  shadow-cible ADRESSE [NOM]      fixe la cible (IP, nom d'hôte ou plage CIDR)
  shadow-cible fin                termine la mission (le dossier est conservé)
  shadow-cible json               état complet, pour le Centre Shadow
"""
import datetime
import json
import os
import re
import shlex
import sys

MAISON = os.path.expanduser('~')
ETAT_DIR = os.path.join(os.environ.get('XDG_STATE_HOME', MAISON + '/.local/state'), 'shadow-os')
ETAT = os.path.join(ETAT_DIR, 'cible')              # JSON, lu par l'îlot et le Centre
ENV = os.path.join(ETAT_DIR, 'cible.env')           # exports, lus par les shells
MISSIONS = os.path.join(MAISON, 'ctf')
MARQUE = '# Shadow : cible de mission (shadow-cible)'
LIGNE = f'[ -r "{ENV}" ] && . "{ENV}"  {MARQUE}'
ADRESSE = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9._:-]*[A-Za-z0-9])?(/\d{1,3})?$')


def lire():
    try:
        with open(ETAT) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def brancher_shells():
    """Ajoute, une seule fois, la lecture de la cible à la fin de ~/.bashrc et ~/.zshrc."""
    for rc in ('.bashrc', '.zshrc'):
        chemin = os.path.join(MAISON, rc)
        try:
            with open(chemin) as f:
                if MARQUE in f.read():
                    continue
            with open(chemin, 'a') as f:
                f.write(f'\n{LIGNE}\n')
        except OSError:
            pass


def fixer(adresse, nom=None):
    if not ADRESSE.match(adresse):
        sys.exit(f'adresse invalide : {adresse!r} (IP, nom d’hôte ou plage CIDR attendus)')
    nom = re.sub(r'[^A-Za-z0-9._-]+', '-', nom or adresse.replace('/', '_')).strip('-') or 'mission'
    dossier = os.path.join(MISSIONS, nom)
    for d in (dossier, os.path.join(dossier, 'scans'), os.path.join(dossier, 'butin')):
        os.makedirs(d, exist_ok=True)
    notes = os.path.join(dossier, 'notes.md')
    if not os.path.exists(notes):
        with open(notes, 'w') as f:
            f.write(f'# Mission {nom}\n\n- Cible : `{adresse}`\n- Début : {datetime.date.today().isoformat()}\n\n'
                    '## Reconnaissance\n\n## Accès initial\n\n## Élévation de privilèges\n\n## Preuves\n')
    os.makedirs(ETAT_DIR, exist_ok=True)
    etat = {'cible': adresse, 'nom': nom, 'dossier': dossier,
            'depuis': datetime.datetime.now().isoformat(timespec='seconds')}
    with open(ETAT, 'w') as f:
        json.dump(etat, f, indent=1)
    with open(ENV, 'w') as f:
        f.write(f'# cible de mission Shadow — géré par shadow-cible\n'
                f'export CIBLE={shlex.quote(adresse)}\nexport TARGET={shlex.quote(adresse)}\n'
                f'export MISSION={shlex.quote(dossier)}\n')
    brancher_shells()
    return etat


def terminer():
    for chemin in (ETAT, ENV):
        try:
            os.unlink(chemin)
        except OSError:
            pass


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ''
    if cmd in ('-h', '--help', 'aide'):
        print(__doc__.strip())
    elif cmd == 'json':
        print(json.dumps(lire() or {}))
    elif cmd in ('fin', 'stop', 'off'):
        avant = lire()
        terminer()
        print(f'Mission terminée ({avant["cible"]}) — dossier conservé : {avant["dossier"]}' if avant else 'Aucune cible en cours')
    elif cmd:
        e = fixer(cmd, argv[2] if len(argv) > 2 else None)
        print(f'Cible : {e["cible"]}\nMission : {e["dossier"]}\n'
              'Dans les nouveaux terminaux : $CIBLE, $TARGET et $MISSION')
    else:
        e = lire()
        print(f'Cible : {e["cible"]} · mission {e["nom"]} ({e["dossier"]})' if e else 'Aucune cible en cours (shadow cible ADRESSE [NOM])')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
