#!/usr/bin/env python3
"""Génère le cadre de sélection du menu GRUB (9 morceaux) : une pilule violette translucide.
GRUB dessine ces morceaux AUTOUR de la ligne choisie : leur taille (R) s'ajoute en haut et en bas,
d'où item_spacing >= 2*R dans theme.txt."""
import os
import sys
from PIL import Image, ImageDraw

R = 14                      # rayon = taille des coins
X = 4                       # suréchantillonnage pour des bords lisses
FOND = (124, 108, 255, 62)
BORD = (183, 169, 255, 170)
dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), 'shadow')

taille = 2 * R + 2
grand = Image.new('RGBA', (taille * X, taille * X), (0, 0, 0, 0))
d = ImageDraw.Draw(grand)
d.rounded_rectangle([0, 0, taille * X - 1, taille * X - 1], radius=R * X, fill=FOND, outline=BORD, width=int(1.5 * X))
img = grand.resize((taille, taille), Image.LANCZOS)
morceaux = {
    'nw': (0, 0, R, R), 'n': (R, 0, R + 2, R), 'ne': (R + 2, 0, taille, R),
    'w': (0, R, R, R + 2), 'c': (R, R, R + 2, R + 2), 'e': (R + 2, R, taille, R + 2),
    'sw': (0, R + 2, R, taille), 's': (R, R + 2, R + 2, taille), 'se': (R + 2, R + 2, taille, taille),
}
for nom, boite in morceaux.items():
    img.crop(boite).save(os.path.join(dest, f'select_{nom}.png'))
print(f'cadre de sélection écrit dans {dest} (coins de {R} px)')
