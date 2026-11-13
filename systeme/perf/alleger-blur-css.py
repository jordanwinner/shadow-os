#!/usr/bin/env python3
"""Allège la feuille de style de Blur my Shell (Shadow OS).

Pourquoi : cette feuille contient ~2 250 sélecteurs, dont les deux tiers
servent des variantes d'apparence que Shadow n'utilise jamais (thème clair,
popups transparents, dock clair/sombre). Or GNOME Shell teste TOUS les
sélecteurs chargés à chaque recalcul de style : sur ce PC, elle représentait
à elle seule plus de la moitié du temps de blocage au verrouillage.

Shadow est toujours sombre, avec dock « transparent » et popups « sombres » :
on ne garde que ces variantes. L'original est conservé à côté.

Usage : alleger-blur-css.py appliquer | restaurer | etat
À relancer après une mise à jour de Blur my Shell ; faire « restaurer » avant
de choisir un style clair ou transparent dans ses réglages.
"""
import os
import re
import shutil
import sys

EXT = os.path.expanduser('~/.local/share/gnome-shell/extensions/blur-my-shell@aunetx')
CSS = os.path.join(EXT, 'stylesheet.css')
ORIGINE = os.path.join(EXT, 'stylesheet.css.origine')
MARQUE = '/* allégé par Shadow (alleger-blur-css.py) — original : stylesheet.css.origine */\n'
INUTILES = re.compile(r'\.(bms-popup-(background|surface)-(light|transparent)'
                      r'|overview-components-(light|transparent)|light-dash|dark-dash|light-panel)(?![\w-])')


def alleger(texte):
    sans_com = re.sub(r'/\*.*?\*/', '', texte, flags=re.S)
    if '@' in sans_com:
        raise SystemExit('règle @ inattendue dans la feuille : abandon, rien modifié')
    sortie, gardes, retires = [MARQUE], 0, 0
    for selecteurs, corps in re.findall(r'([^{}]+)\{([^{}]*)\}', sans_com):
        tous = [s.strip() for s in selecteurs.split(',') if s.strip()]
        utiles = [s for s in tous if not INUTILES.search(s)]
        gardes += len(utiles)
        retires += len(tous) - len(utiles)
        if utiles:
            sortie.append(',\n'.join(utiles) + ' {' + corps.rstrip() + '\n}\n')
    return '\n'.join(sortie), gardes, retires


def est_allege():
    with open(CSS) as f:
        return f.read(len(MARQUE)) == MARQUE


cmd = sys.argv[1] if len(sys.argv) > 1 else 'etat'
if cmd == 'appliquer':
    if est_allege():
        sys.exit('déjà allégée')
    with open(CSS) as f:
        texte = f.read()
    nouveau, gardes, retires = alleger(texte)
    shutil.copy2(CSS, ORIGINE)
    with open(CSS, 'w') as f:
        f.write(nouveau)
    print(f'{retires} sélecteurs retirés, {gardes} gardés ({len(texte) // 1024} Ko -> {len(nouveau) // 1024} Ko)')
elif cmd == 'restaurer':
    if not os.path.exists(ORIGINE):
        sys.exit('pas de copie d’origine')
    shutil.copy2(ORIGINE, CSS)
    print('feuille d’origine restaurée')
else:
    print('allégée' if est_allege() else 'd’origine')
print('→ recharger : gnome-extensions disable blur-my-shell@aunetx && gnome-extensions enable blur-my-shell@aunetx')
