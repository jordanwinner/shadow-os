# Shadow

Système d'exploitation de Jordan : base Debian/Ubuntu, finition façon macOS,
pilotage clavier façon Omarchy, arsenal Kali/Parrot, compatibilité Windows.

Ce dépôt devient la source de vérité de Shadow. L'outil existant
`shadow-desktop` (`~/.local/share/shadow-desktop`, CLI `~/.local/bin/shadow`,
depuis le 2026-10-23) y sera intégré.

## Feuille de route

| Phase | Contenu | État |
|---|---|---|
| 1. Fondations | identité, thème, flottant + tuiles avec bascule, arsenal cyber, couche Windows | quasi fini |
| 2. Distribution | installateur ✅, paquet `.deb` ✅, dépôt APT ✅, ISO (`live-build`) | en cours |
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

## Installation

Pour (ré)appliquer Shadow sur une machine Ubuntu/Debian + GNOME :

```bash
./installer.sh              # modules utilisateur (extensions, thème, grille, scripts, terminal, apps)
./installer.sh --avec-shell # + shsh, le shell de Shadow (dépôt ~/Dev/shsh : mission et mode dans le prompt)
./installer.sh --tout       # + shell, système (GRUB/Plymouth/login), arsenal Kali, bureau shadow-desktop
./installer.sh --simuler --tout   # montre le plan sans rien modifier
./installer.sh --liste      # liste les modules
```

L'installateur télécharge les extensions GNOME tierces depuis extensions.gnome.org
selon la version du shell, lie l'extension Shadow, applique le thème et la grille,
installe les scripts, le terminal et les apps. Idempotent : relançable sans risque.

### Paquets Debian

```bash
paquet/construire.sh            # produit paquet/sortie/shadow-os*_1.0.0_all.deb
sudo apt install ./paquet/sortie/shadow-os_1.0.0_all.deb   # méta : bureau + dépendances
shadow-os                       # active Shadow sur le compte (puis reconnexion)
shadow-os --revert              # revient au bureau d'avant
```

- `shadow-os-desktop` : charge utile dans `/usr/share/shadow-os` + commande `shadow-os`.
- `shadow-os` : méta-paquet qui tire le bureau et toutes les dépendances
  (GNOME Shell, gestionnaire d'extensions, polices, terminal ; distrobox/podman en recommandés).

### Dépôt APT

```bash
depot/construire-depot.sh       # construit depot/sortie/ (pool + dists signés + clé publique)
sudo depot/ajouter-depot.sh "file:$PWD/depot/sortie"   # ajoute le dépôt (local)
sudo apt update && sudo apt install shadow-os
```

Le dépôt est signé par une clé GPG dédiée (trousseau local `depot/.gnupg`, jamais
le trousseau personnel). Pour publier sur une URL (GitHub Pages, serveur) : copier
`depot/sortie/` à la racine web, puis sur chaque machine :
`sudo depot/ajouter-depot.sh "https://<domaine>/shadow"`. La clé publique est
`depot/sortie/shadow-os-archive-keyring.gpg`.

## Commandes

| Commande | Effet |
|---|---|
| `Super+T` ou `shadow mode bascule` | flottant (macOS) ⇄ tuiles (Omarchy) |
| `shadow arsenal setup` | crée la box Kali isolée (distrobox + podman, sans toucher à Ubuntu) |
| `shadow arsenal install <pack>` | installe un pack d'outils Kali (web, recon, reverse, passwords…) |
| `shadow arsenal export <appli>` | ajoute une appli Kali à la grille (dossier « Arsenal ») |
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
- `shadow theme apply` (ancien shadow-desktop) remettrait Tokyonight : utiliser `eclipse.sh`.

Nom de paquet prévu : `shadow-os-*` (le paquet Debian `shadow` existe déjà :
c'est celui de `passwd`/`login`).
