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

## Commandes

| Commande | Effet |
|---|---|
| `Super+T` ou `shadow mode bascule` | flottant (macOS) ⇄ tuiles (Omarchy) |
| `shadow mode restaurer` | remet les réglages d'avant le premier `shadow mode` |
| `theme/eclipse.sh apply` | palette Éclipse : thème shell + GTK « Shadow », tuiles, dock |
| `theme/eclipse.sh revert` | revient au thème d'avant (TokyoCombo / Tokyonight) |
| `theme/eclipse.sh build` | régénère les thèmes après une mise à jour de GNOME |
| `theme/applis.py apply` / `revert` / `check` | grille en dossiers, noms courts, doublons masqués, dock court |
| `theme/icones.sh apply` / `revert` | thème d'icônes Shadow (Papirus-Dark, dossiers violets) |
| `sudo systeme/installer-systeme.sh` | GRUB Éclipse, animation de démarrage, écran de connexion, nom « Shadow » |
| `sudo systeme/desinstaller-systeme.sh` | annule la partie système (sauvegardes dans `/var/backups/shadow-os`) |

Applis :
- `apps/vscode/` : thème VS Code « Shadow Éclipse » (`code --install-extension apps/vscode/shadow-eclipse-1.0.0.vsix`)
- `apps/obsidian/shadow-eclipse.css` : extrait CSS à copier dans `<coffre>/.obsidian/snippets/`
- `apps/bienvenue/bienvenue.py` : présentation au premier démarrage (Utilitaires › Bienvenue)
- `ulauncher/shadow-eclipse/` : thème Ulauncher
- Alt+Espace : recherche GNOME façon Spotlight (extension `shadow-os@jordan`)

Terminal : profil GNOME Terminal « Shadow · Éclipse » + `terminal/fastfetch.jsonc`
(ancienne config : `~/.config/backup-theme/fastfetch-config-avant-shadow.jsonc`).
Extension `extension/shadow-os@jordan` : accent Éclipse sur les tuiles des réglages rapides.

Sauvegardes : `~/.local/state/shadow-os/`, `~/.config/backup-theme/fond-avant-eclipse.txt`.

## Limites connues

- GNOME 50 impose l'accent système aux tuiles des réglages rapides (aucun CSS n'y peut rien) :
  corrigé par l'extension `shadow-os@jordan`, active après reconnexion.
- En mode tuiles, une appli qui se rouvre maximisée (kitty, éditeur de texte) n'est
  pas rangée : Tiling Shell ne range que les fenêtres non maximisées.
- `shadow theme apply` (ancien shadow-desktop) remettrait Tokyonight : utiliser `eclipse.sh`.

Nom de paquet prévu : `shadow-os-*` (le paquet Debian `shadow` existe déjà :
c'est celui de `passwd`/`login`).
