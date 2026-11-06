# Shadow

Système d'exploitation de Jordan : base Debian/Ubuntu, finition façon macOS,
pilotage clavier façon Omarchy, arsenal Kali/Parrot, compatibilité Windows.

Ce dépôt devient la source de vérité de Shadow. L'outil existant
`shadow-desktop` (`~/.local/share/shadow-desktop`, CLI `~/.local/bin/shadow`,
depuis le 2026-10-23) y sera intégré.

## Feuille de route

| Phase | Contenu | État |
|---|---|---|
| 1. Fondations | identité, thème, flottant + tuiles avec bascule, arsenal cyber, couche Windows | en cours |
| 2. Distribution | script d'installation, ISO (`live-build`), dépôt APT | — |
| 3. Composants maison | centre de contrôle, lanceur, mode pentest, installateur, boutique | — |
| 4. Bureau maison | shell/compositeur Shadow | — |

## Identité « Éclipse »

Un disque d'ombre passe devant la lumière : il ne reste qu'un croissant.

| Rôle | Nom | Valeur |
|---|---|---|
| Fond | Vide | `#07070B` |
| Surface | Encre | `#0E0E16` |
| Surface haute | Ardoise | `#1A1A30` |
| Accent | Éclipse | `#7C6CFF` |
| Accent clair | Aura | `#D9D2FF` |
| Secondaire | Braise | `#FF4D8D` |

- `identite/logo.svg` : icône (squircle)
- `identite/fond-eclipse.svg` : fond d'écran 3200×1800
- `scripts/rendre-svg.sh` : rendu SVG → PNG via Chrome headless
- les PNG se régénèrent dans `identite/rendus/` (non versionnés)

Nom de paquet prévu : `shadow-os-*` (le paquet Debian `shadow` existe déjà :
c'est celui de `passwd`/`login`).
