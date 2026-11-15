#!/usr/bin/env python3
"""shadow-cible — la cible de la mission en cours (mode Pentest de Shadow).

Fixer une cible :
  - l'affiche en permanence dans l'îlot ;
  - crée le dossier de mission (~/ctf/NOM : notes.md, scans/, butin/) ;
  - écrit un fichier d'exports ($CIBLE, $TARGET, $MISSION) que tes terminaux
    peuvent lire. Ce branchement n'est jamais fait d'office : c'est toi qui
    le demandes, une fois, avec « shadow-cible terminaux ».

Usage :
  shadow-cible                    affiche la cible en cours
  shadow-cible ADRESSE [NOM]      fixe la cible (IP, nom d'hôte ou plage CIDR)
  shadow-cible fin                termine la mission (le dossier est conservé)
  shadow-cible terminaux          montre la ligne à ajouter à ~/.bashrc / ~/.zshrc
  shadow-cible terminaux installer  l'ajoute pour toi (une seule fois, ligne marquée)
  shadow-cible json               état complet, pour le Centre Shadow
  shadow-cible rapport [NOM] [--sortie FICHIER]
                                  rapport Markdown de la mission (en cours ou ~/ctf/NOM) :
                                  chronologie tirée du journal de shsh, ports trouvés
                                  dans scans/, butin (avec empreintes), notes
"""
import hashlib
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


def shells_branches():
    """Fichiers de démarrage (parmi ~/.bashrc, ~/.zshrc) qui lisent déjà la cible."""
    faits = []
    for rc in ('.bashrc', '.zshrc'):
        try:
            with open(os.path.join(MAISON, rc)) as f:
                if MARQUE in f.read():
                    faits.append(rc)
        except OSError:
            pass
    return faits


def brancher_shells():
    """Ajoute la lecture de la cible à ~/.bashrc et ~/.zshrc. Uniquement à la demande explicite."""
    ajoutes = []
    for rc in ('.bashrc', '.zshrc'):
        chemin = os.path.join(MAISON, rc)
        try:
            with open(chemin) as f:
                if MARQUE in f.read():
                    continue
            with open(chemin, 'a') as f:
                f.write(f'\n{LIGNE}\n')
            ajoutes.append(rc)
        except OSError:
            pass
    return ajoutes


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
    return etat


def terminer():
    for chemin in (ETAT, ENV):
        try:
            os.unlink(chemin)
        except OSError:
            pass


LIGNE_JOURNAL = re.compile(r'^- (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) · (✔|✘ -?\d+) · ([^·]+) · (`+) ?(.*?) ?\4 — (`+) ?(.*?) ?\6$')
PORT_NMAP = re.compile(r'^(\d+)/(tcp|udp)\s+open\s+(\S+)\s*(.*)$')


def _cellule(t):
    return t.replace('|', '\\|').replace('\n', ' ')


def _code(t):
    """Code en ligne Markdown qui garde les accents graves de la commande."""
    t = _cellule(t)
    n = 1
    while '`' * n in t:
        n += 1
    pad = ' ' if t.startswith('`') or t.endswith('`') or n > 1 else ''
    return f"{'`' * n}{pad}{t}{pad}{'`' * n}"


def rapport(nom=None, sortie=None):
    """Assemble le rapport Markdown d'une mission. Renvoie le chemin écrit."""
    etat = lire() or {}
    if nom:
        if '/' in nom or nom in ('.', '..') or nom.startswith('.'):
            sys.exit(f'nom de mission invalide : {nom!r} (un dossier de ~/ctf, sans « / »)')
        dossier = os.path.join(MISSIONS, nom)
        adresse = etat.get('cible') if etat.get('nom') == nom else None
    else:
        if not etat:
            sys.exit('Aucune mission en cours : shadow rapport NOM (dossier ~/ctf/NOM)')
        dossier, nom, adresse = etat['dossier'], etat['nom'], etat['cible']
    if not os.path.isdir(dossier):
        sys.exit(f'mission introuvable : {dossier}')
    notes = ''
    try:
        with open(os.path.join(dossier, 'notes.md')) as f:
            notes = f.read()
    except OSError:
        pass
    if not adresse:
        m = re.search(r'Cible : `([^`]+)`', notes)
        adresse = m.group(1) if m else '?'

    # Chronologie : journal écrit par shsh pendant la mission
    entrees = []
    try:
        with open(os.path.join(dossier, 'journal.md')) as f:
            for ligne in f:
                m = LIGNE_JOURNAL.match(ligne.rstrip('\n'))
                if m:
                    entrees.append({'quand': m.group(1), 'code': m.group(2), 'duree': m.group(3).strip(),
                                    'dossier': m.group(5), 'commande': m.group(7)})
    except OSError:
        pass
    echecs = sum(1 for e in entrees if e['code'] != '✔')

    # Ports ouverts trouvés dans les sorties nmap (-oN / -oA) rangées dans scans/
    ports = {}
    scans = os.path.join(dossier, 'scans')
    for racine, _, fichiers in os.walk(scans):
        for nomf in sorted(fichiers):
            if not nomf.endswith(('.nmap', '.txt', '.log')):
                continue
            try:
                with open(os.path.join(racine, nomf), errors='replace') as f:
                    for ligne in f:
                        m = PORT_NMAP.match(ligne.strip())
                        if m:
                            ports.setdefault((int(m.group(1)), m.group(2)), (m.group(3), m.group(4).strip(), nomf))
            except OSError:
                pass

    # Butin : fichiers récupérés, avec taille et empreinte (preuve d'intégrité)
    butin = []
    for racine, _, fichiers in os.walk(os.path.join(dossier, 'butin')):
        for nomf in sorted(fichiers):
            chemin = os.path.join(racine, nomf)
            if os.path.islink(chemin) or not os.path.isfile(chemin):
                continue                                   # liens, FIFO, périphériques : ignorés
            try:
                h = hashlib.sha256()
                with open(chemin, 'rb') as f:
                    for bloc in iter(lambda: f.read(1 << 16), b''):
                        h.update(bloc)
                butin.append((os.path.relpath(chemin, dossier), os.path.getsize(chemin), h.hexdigest()))
            except OSError:
                pass

    debut = entrees[0]['quand'] if entrees else '—'
    fin = entrees[-1]['quand'] if entrees else '—'
    o = [f'# Rapport de mission — {nom}', '',
         f'*Généré par Shadow le {datetime.datetime.now():%Y-%m-%d à %H:%M}.*', '',
         '| | |', '|---|---|',
         f'| Cible | `{_cellule(adresse)}` |',
         f'| Période | {debut} → {fin} |',
         f'| Commandes notées | {len(entrees)} (dont {echecs} en échec) |',
         f'| Ports ouverts | {len(ports)} |',
         f'| Fichiers de butin | {len(butin)} |', '']
    o += ['## Ports et services', '']
    if ports:
        o += ['| Port | Service | Version | Source |', '|---|---|---|---|']
        o += [f'| {p}/{proto} | {_cellule(svc)} | {_cellule(ver) or "—"} | `{src}` |'
              for (p, proto), (svc, ver, src) in sorted(ports.items())]
    else:
        o.append('Aucune sortie nmap dans `scans/` (astuce : `nmap -oA scans/initial $CIBLE`).')
    o += ['', '## Chronologie', '']
    if entrees:
        o += ['| Heure | Résultat | Durée | Commande |', '|---|---|---|---|']
        for e in entrees:
            o.append(f'| {e["quand"]} | {e["code"]} | {e["duree"]} | {_code(e["commande"])} |')
    else:
        o.append('Aucune commande notée : le journal est tenu par shsh pendant une mission (`journal mission`).')
    o += ['', '## Butin', '']
    if butin:
        o += ['| Fichier | Taille | SHA-256 |', '|---|---|---|']
        o += [f'| `{_cellule(c)}` | {t} o | `{h}` |' for c, t, h in butin]
    else:
        o.append('Rien dans `butin/`.')
    o += ['', '## Notes', '']
    corps = re.sub(r'\A# .*\n', '', notes)                 # le titre est déjà en tête du rapport
    # titres décalés d'un niveau, sauf dans les blocs de code (commentaires, shebang)
    lignes, dans_code = [], False
    for ligne in corps.split('\n'):
        if ligne.lstrip().startswith(('```', '~~~')):
            dans_code = not dans_code
        elif not dans_code and re.match(r'#+ ', ligne):
            ligne = '#' + ligne
        lignes.append(ligne)
    corps = '\n'.join(lignes)
    o.append(corps.strip() or '—')
    sortie = sortie or os.path.join(dossier, 'rapport.md')
    with open(sortie, 'w') as f:
        f.write('\n'.join(o) + '\n')
    return sortie, len(entrees), len(ports), len(butin)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ''
    if cmd in ('-h', '--help', 'aide'):
        print(__doc__.strip())
    elif cmd == 'json':
        print(json.dumps(lire() or {}))
    elif cmd == 'terminaux':
        if len(argv) > 2 and argv[2] == 'installer':
            ajoutes = brancher_shells()
            print(('Ligne ajoutée à : ' + ', '.join('~/' + a for a in ajoutes)) if ajoutes else 'Déjà en place, rien à faire')
        else:
            faits = shells_branches()
            print('shsh, le shell de Shadow, reçoit déjà $CIBLE, $TARGET et $MISSION tout seul.\n'
                  'Pour bash et zsh, ajoute cette ligne à la fin de ~/.bashrc et de ~/.zshrc\n'
                  '(ou lance « shadow-cible terminaux installer ») :\n\n'
                  f'  {LIGNE}\n\n'
                  + ('Déjà en place dans : ' + ', '.join('~/' + f for f in faits) if faits else 'Pas encore en place.'))
    elif cmd == 'rapport':
        reste, nom, sortie = argv[2:], None, None
        while reste:
            a = reste.pop(0)
            if a in ('--sortie', '-o') and reste:
                sortie = os.path.abspath(reste.pop(0))
            elif not a.startswith('-'):
                nom = a
        chemin, n, p, b = rapport(nom, sortie)
        print(f'Rapport : {chemin}\n  {n} commande(s), {p} port(s) ouvert(s), {b} fichier(s) de butin')
    elif cmd in ('fin', 'stop', 'off'):
        avant = lire()
        terminer()
        print(f'Mission terminée ({avant["cible"]}) — dossier conservé : {avant["dossier"]}' if avant else 'Aucune cible en cours')
    elif cmd:
        e = fixer(cmd, argv[2] if len(argv) > 2 else None)
        print(f'Cible : {e["cible"]}\nMission : {e["dossier"]}')
        print('Dans les nouveaux terminaux : $CIBLE, $TARGET et $MISSION' if shells_branches()
              else 'Terminaux non branchés : voir « shadow-cible terminaux »')
    else:
        e = lire()
        print(f'Cible : {e["cible"]} · mission {e["nom"]} ({e["dossier"]})' if e else 'Aucune cible en cours (shadow cible ADRESSE [NOM])')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
