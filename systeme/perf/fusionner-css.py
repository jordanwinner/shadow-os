#!/usr/bin/env python3
"""Fusionne les feuilles de style de quelques extensions dans le thème shell Shadow.

Pourquoi : à chaque verrouillage, GNOME coupe puis relance les extensions.
Chaque feuille de style déchargée ou rechargée oblige le shell à recalculer
le style de toute l'interface (plusieurs dixièmes de seconde à chaque fois).
Le thème Shadow, lui, reste chargé pendant le verrouillage. En y recopiant
les règles de ces extensions et en mettant leur feuille de côté, elles se
coupent et se relancent sans provoquer de recalcul. Les règles sont inertes
tant que l'extension est coupée (ses éléments n'existent pas).

Usage : fusionner-css.py appliquer | restaurer | etat
« appliquer » est rejouable : à relancer après une régénération du thème
(theme/eclipse.sh le fait) ou une mise à jour d'une des extensions.
"""
import os
import re
import sys

EXTS = ['dash-to-dock@micxgx.gmail.com', 'tilingshell@ferrarodomenico.com',
        'logomenu@aryan_k', 'rounded-window-corners@fxgn']
DOSSIER = os.path.expanduser('~/.local/share/gnome-shell/extensions')
THEME = os.path.expanduser('~/.themes/Shadow/gnome-shell/gnome-shell.css')
BLOC = re.compile(r'\n/\* >>> shadow-fusion (\S+) \*/.*?/\* <<< shadow-fusion \1 \*/\n', re.S)


def chemins(uuid):
    d = os.path.join(DOSSIER, uuid)
    return d, os.path.join(d, 'stylesheet.css'), os.path.join(d, 'stylesheet.css.fusionnee')


def sans_blocs(theme):
    return BLOC.sub('', theme)


def appliquer():
    with open(THEME) as f:
        theme = sans_blocs(f.read())
    for uuid in EXTS:
        d, css, cote = chemins(uuid)
        if os.path.exists(css):                     # feuille neuve (1re fois ou mise à jour) : elle fait foi
            os.replace(css, cote)
        if not os.path.exists(cote):
            print(f'  {uuid} : pas de feuille, ignorée')
            continue
        with open(cote) as f:
            regles = f.read()
        # les url() relatives pointaient vers le dossier de l'extension
        regles = re.sub(r'url\((["\']?)\./', lambda m: f'url({m.group(1)}{d}/', regles)
        theme += f'\n/* >>> shadow-fusion {uuid} */\n{regles}\n/* <<< shadow-fusion {uuid} */\n'
        print(f'  {uuid} : fusionnée ({len(regles) // 1024} Ko)')
    with open(THEME, 'w') as f:
        f.write(theme)


def restaurer():
    with open(THEME) as f:
        theme = f.read()
    with open(THEME, 'w') as f:
        f.write(sans_blocs(theme))
    for uuid in EXTS:
        _d, css, cote = chemins(uuid)
        if os.path.exists(cote) and not os.path.exists(css):
            os.replace(cote, css)
            print(f'  {uuid} : feuille remise en place')


def etat():
    with open(THEME) as f:
        dans_theme = set(m.group(1) for m in BLOC.finditer(f.read()))
    for uuid in EXTS:
        _d, css, cote = chemins(uuid)
        print(f'  {uuid} : {"fusionnée" if uuid in dans_theme and not os.path.exists(css) else "séparée"}')


cmd = sys.argv[1] if len(sys.argv) > 1 else 'etat'
if cmd not in ('appliquer', 'restaurer', 'etat'):
    sys.exit(__doc__.strip())
{'appliquer': appliquer, 'restaurer': restaurer, 'etat': etat}[cmd]()
if cmd != 'etat':
    print('→ effectif après rechargement du thème et des extensions (ou reconnexion)')
