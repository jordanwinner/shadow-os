#!/usr/bin/env python3
"""Génère les fonds d'écran des modes Shadow (variantes du fond « Éclipse »).

Chaque mode a sa palette et, parfois, un habillage (viseur pour Pentest,
étoiles pour Nuit). Le SVG est rendu en PNG par scripts/rendre-svg.sh.

Usage : fonds.py [mode ...]      (sans argument : tous les modes)
Sortie : ~/.local/share/backgrounds/shadow/mode-<id>.png
"""
import math
import os
import random
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.realpath(__file__))
RENDRE = os.path.join(ICI, '..', '..', 'scripts', 'rendre-svg.sh')
SORTIE = os.path.expanduser('~/.local/share/backgrounds/shadow')
L, H = 3200, 1800

# ciel (centre, milieu, bord) · lumière (bas, milieu, haut) · aura · braise · éclat · ombre
PALETTES = {
    'pentest': dict(ciel=('#220A10', '#0E0608', '#050304'), lumiere=('#FF7A3D', '#FF2D55', '#FFD9D2'),
                    aura='#FF2D55', braise='#FF7A3D', eclat='#FFB4A8', ombre='#0A0506', force=1.0),
    'focus':   dict(ciel=('#0C1A2E', '#070C16', '#04060A'), lumiere=('#2DD4BF', '#4C8DFF', '#E3EEFF'),
                    aura='#4C8DFF', braise='#2DD4BF', eclat='#B9D4FF', ombre='#05080D', force=0.85),
    'jeu':     dict(ciel=('#24102C', '#100814', '#060308'), lumiere=('#FFB020', '#FF3D81', '#FFE4F0'),
                    aura='#FF3D81', braise='#FFB020', eclat='#FFC2DA', ombre='#0A050C', force=1.0),
    'nuit':    dict(ciel=('#17100A', '#0A0705', '#040302'), lumiere=('#B8501B', '#FF9A4D', '#FFE6CC'),
                    aura='#FF9A4D', braise='#B8501B', eclat='#FFD2A6', ombre='#070504', force=0.55),
}


def viseur():
    """Habillage Pentest : l'éclipse devient une cible (anneaux, graduations, grille)."""
    cx, cy = 2110, 820
    p = ['<g fill="none" stroke="#FF5A6E" stroke-linecap="round">']
    # grille fine qui s'efface loin de la cible
    p.append('<g stroke-width="1.5" opacity="0.5" mask="url(#fonduGrille)">')
    for x in range(0, L + 1, 100):
        p.append(f'<path d="M{x} 0V{H}"/>')
    for y in range(0, H + 1, 100):
        p.append(f'<path d="M0 {y}H{L}"/>')
    p.append('</g>')
    # anneaux
    for r, larg, op, tirets in ((590, 2.5, 0.50, ''), (690, 1.5, 0.30, '6 18'), (820, 1.5, 0.20, '2 26')):
        d = f' stroke-dasharray="{tirets}"' if tirets else ''
        p.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke-width="{larg}" opacity="{op}"{d}/>')
    # graduations tous les 5°, plus longues tous les 30°
    p.append('<g opacity="0.55" stroke-width="2.5">')
    for a in range(0, 360, 5):
        r1 = 590
        r2 = 632 if a % 30 == 0 else 606
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        p.append(f'<path d="M{cx + r1 * c:.1f} {cy + r1 * s:.1f}L{cx + r2 * c:.1f} {cy + r2 * s:.1f}"/>')
    p.append('</g>')
    # réticule : quatre traits qui s'arrêtent avant le disque
    p.append('<g opacity="0.45" stroke-width="2">')
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        p.append(f'<path d="M{cx + dx * 700} {cy + dy * 700}L{cx + dx * 1010} {cy + dy * 1010}"/>')
    p.append('</g>')
    # coins de cadrage
    p.append('<g opacity="0.6" stroke-width="4">')
    k, g = 760, 70
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        x, y = cx + sx * k, cy + sy * k
        p.append(f'<path d="M{x - sx * g} {y}H{x}V{y - sy * g}"/>')
    p.append('</g></g>')
    # légende discrète
    p.append('<g font-family="JetBrains Mono, DejaVu Sans Mono, monospace" font-size="26" fill="#FF8A98" '
             'letter-spacing="6" opacity="0.55">'
             '<text x="140" y="1650">SHADOW // ARSENAL</text>'
             '<text x="140" y="1694" opacity="0.6">MODE PENTEST</text></g>')
    return '\n'.join(p)


def etoiles():
    """Habillage Nuit : semis d'étoiles discret, toujours le même."""
    alea = random.Random(41)
    p = ['<g fill="#FFE6CC">']
    for _ in range(170):
        x, y = alea.uniform(0, L), alea.uniform(0, H)
        r = alea.choice((1.2, 1.2, 1.6, 1.6, 2.2, 3.0))
        p.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" opacity="{alea.uniform(0.12, 0.6):.2f}"/>')
    p.append('</g>')
    return '\n'.join(p)


HABILLAGES = {'pentest': viseur, 'nuit': etoiles}


def svg(mode):
    c = PALETTES[mode]
    f = c['force']
    habillage = HABILLAGES[mode]() if mode in HABILLAGES else ''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {L} {H}" width="{L}" height="{H}">
  <!-- Shadow — fond du mode « {mode} » (généré par apps/modes/fonds.py) -->
  <defs>
    <radialGradient id="ciel" gradientUnits="userSpaceOnUse" cx="2000" cy="900" r="2300">
      <stop offset="0" stop-color="{c['ciel'][0]}"/><stop offset="0.45" stop-color="{c['ciel'][1]}"/><stop offset="1" stop-color="{c['ciel'][2]}"/>
    </radialGradient>
    <linearGradient id="lumiere" gradientUnits="userSpaceOnUse" x1="1500" y1="1450" x2="2500" y2="350">
      <stop offset="0" stop-color="{c['lumiere'][0]}"/><stop offset="0.5" stop-color="{c['lumiere'][1]}"/><stop offset="1" stop-color="{c['lumiere'][2]}"/>
    </linearGradient>
    <radialGradient id="aura" gradientUnits="userSpaceOnUse" cx="1960" cy="960" r="1100">
      <stop offset="0" stop-color="{c['aura']}" stop-opacity="{0.30 * f:.2f}"/>
      <stop offset="0.5" stop-color="{c['aura']}" stop-opacity="{0.10 * f:.2f}"/>
      <stop offset="1" stop-color="{c['aura']}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="braise" gradientUnits="userSpaceOnUse" cx="1700" cy="1300" r="700">
      <stop offset="0" stop-color="{c['braise']}" stop-opacity="{0.16 * f:.2f}"/><stop offset="1" stop-color="{c['braise']}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="eclat">
      <stop offset="0" stop-color="#fff" stop-opacity="0.9"/>
      <stop offset="0.07" stop-color="{c['lumiere'][2]}" stop-opacity="0.5"/>
      <stop offset="0.3" stop-color="{c['eclat']}" stop-opacity="0.16"/>
      <stop offset="0.6" stop-color="{c['aura']}" stop-opacity="0.05"/>
      <stop offset="1" stop-color="{c['aura']}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="fonduG" gradientUnits="userSpaceOnUse" cx="2110" cy="820" r="1500">
      <stop offset="0.3" stop-color="#fff" stop-opacity="0.34"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
    </radialGradient>
    <mask id="fonduGrille"><rect width="{L}" height="{H}" fill="url(#fonduG)"/></mask>
    <linearGradient id="rai"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="0.5" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
    <linearGradient id="raiV" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="0.5" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
    <mask id="eclipse"><rect width="{L}" height="{H}" fill="#fff"/><circle cx="2110" cy="820" r="500" fill="#000"/></mask>
    <clipPath id="zoneLumiere"><circle cx="2040" cy="890" r="528"/></clipPath>
    <filter id="flouLarge" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="70"/></filter>
    <filter id="flouMoyen" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="18"/></filter>
    <filter id="grain">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="b"/>
      <feColorMatrix in="b" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.045 0"/>
    </filter>
  </defs>
  <rect width="{L}" height="{H}" fill="url(#ciel)"/>
  <rect width="{L}" height="{H}" fill="url(#aura)"/>
  <rect width="{L}" height="{H}" fill="url(#braise)"/>
  {habillage}
  <g opacity="{f:.2f}">
    <g filter="url(#flouLarge)" opacity="0.75"><circle cx="2040" cy="890" r="520" fill="url(#lumiere)" mask="url(#eclipse)"/></g>
    <g filter="url(#flouMoyen)" opacity="0.8"><circle cx="2040" cy="890" r="520" fill="url(#lumiere)" mask="url(#eclipse)"/></g>
    <circle cx="2040" cy="890" r="520" fill="url(#lumiere)" mask="url(#eclipse)"/>
  </g>
  <circle cx="2110" cy="820" r="500" fill="{c['ombre']}"/>
  <circle cx="2110" cy="820" r="500" fill="none" stroke="url(#lumiere)" stroke-opacity="0.45" stroke-width="3" clip-path="url(#zoneLumiere)"/>
  <g opacity="{f:.2f}">
    <circle cx="1796" cy="431" r="130" fill="url(#eclat)"/>
    <g transform="translate(1796 431) rotate(-45)" opacity="0.55">
      <rect x="-150" y="-1.2" width="300" height="2.4" rx="1.2" fill="url(#rai)"/>
      <rect x="-1.2" y="-70" width="2.4" height="140" rx="1.2" fill="url(#raiV)"/>
    </g>
    <circle cx="1796" cy="431" r="5" fill="#fff"/>
  </g>
  <rect width="{L}" height="{H}" filter="url(#grain)"/>
</svg>
'''


def generer(mode):
    os.makedirs(SORTIE, exist_ok=True)
    cible = os.path.join(SORTIE, f'mode-{mode}.png')
    with tempfile.NamedTemporaryFile('w', suffix='.svg', delete=False) as f:
        f.write(svg(mode))
    try:
        subprocess.run([RENDRE, f.name, cible, str(L), str(H)], check=True, stdout=subprocess.DEVNULL)
    finally:
        os.unlink(f.name)
    return cible


if __name__ == '__main__':
    for m in (sys.argv[1:] or list(PALETTES)):
        if m not in PALETTES:
            sys.exit(f'mode inconnu : {m} (choix : {", ".join(PALETTES)})')
        print(generer(m))
