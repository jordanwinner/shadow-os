#!/usr/bin/env python3
"""Shadow — organisation des applications (grille + dock), sans sudo et réversible.

  applis.py apply    masque les doublons, raccourcit les noms, unifie des icônes,
                     range la grille en dossiers et compose le dock
  applis.py revert   remet exactement l'état sauvegardé avant le premier apply
  applis.py check    liste les applis visibles qui ne sont dans aucun dossier

Les modifications de lanceurs passent par des copies dans ~/.local/share/applications
(les fichiers système ne sont jamais touchés). Tout ce qui existait déjà est sauvegardé.
"""
import ast, configparser, glob, json, os, re, shutil, subprocess, sys

HOME = os.path.expanduser('~')
USER_APPS = f'{HOME}/.local/share/applications'
ETAT = f'{HOME}/.local/state/shadow-os/applis'
DIRS = [USER_APPS, f'{HOME}/.local/share/flatpak/exports/share/applications',
        '/var/lib/flatpak/exports/share/applications', '/var/lib/snapd/desktop/applications',
        '/usr/local/share/applications', '/usr/share/applications']

# ── doublons et outils techniques à masquer ────────────────────────────────
MASQUER = [
    'arduino_arduino.desktop',              # doublon (snap) de l'AppImage Arduino IDE
    'bleachbit-root.desktop',               # variante root de BleachBit
    'emacs-term.desktop',                   # doublon d'Emacs
    'chromium_daemon.desktop',              # lanceur vide (Exec=/usr/bin/false)
    'scrcpy-console.desktop',               # variante console de scrcpy
    'steam.desktop',                        # doublon du Steam flatpak
    'org.gnome.Ptyxis.desktop',             # second « Terminal »
    'qterminal-drop.desktop',               # variante déroulante de QTerminal
    'org.torproject.torbrowser-launcher.settings.desktop',
    'lstopo.desktop', 'ksh93.desktop', 'display-im7.q16.desktop',
    'texdoctk.desktop', 'info.desktop', 'ocaml.desktop', 'xjadeo.desktop',
    'kdesystemsettings.desktop', 'org.kde.kwalletmanager.desktop',
    'org.kde.discover.desktop', 'org.kde.plasma-systemmonitor.desktop', 'org.kde.sweeper.desktop',
    'chrome-akpamiohjfcnimfljfndmaldlcfphjmp-Default.desktop',  # Instagram (Chrome) : doublon d'Instagram Electron
    'org.gnome.Evince.desktop',             # doublon du lecteur de documents (Papers)
    # Waydroid désinstallé : lanceurs morts
    'waydroid.com.android.vending.desktop', 'waydroid.com.google.android.contacts.desktop',
    'waydroid.com.google.android.apps.messaging.desktop',
]

# ── noms courts (la grille coupe au-delà d'environ 10 caractères) ──────────
NOMS = {
    # français, ≤ 10 caractères environ (la grille coupe au-delà) ; noms de macOS quand ils existent
    'software-properties-drivers.desktop': 'Pilotes',
    'nm-connection-editor.desktop': 'Connexions',
    'remote-viewer.desktop': 'Virt Viewer',
    'firmware-updater_firmware-updater.desktop': 'Firmware',
    'org.gnome.tweaks.desktop': 'Tweaks',
    'arduino-ide.desktop': 'Arduino',
    'byobu.desktop': 'Byobu',
    'snap-store_snap-store.desktop': 'Logithèque',
    'desktop-security-center_desktop-security-center.desktop': 'Sécurité',
    'org.gnome.baobab.desktop': 'Occupation',
    'org.gnome.Papers.desktop': 'Documents',
    'simple-scan.desktop': 'Scanner',
    'org.kde.dragonplayer.desktop': 'Dragon',
    'emacsclient.desktop': 'Emacs',
    'org.gnome.FileRoller.desktop': 'Archives',
    'freedownloadmanager.desktop': 'FDM',
    'virt-manager.desktop': 'Machines',
    'org.kde.partitionmanager.desktop': 'Partitions',
    'com.mattjakeman.ExtensionManager.desktop': 'Extensions+',
    'gmail-app_gmail-app.desktop': 'Gmail',
    'google-chrome.desktop': 'Chrome',
    'io.github.realmazharhussain.GdmSettings.desktop': 'Écran GDM',
    'lynis.desktop': 'Lynis',
    'org.gnome.Loupe.desktop': 'Images',
    'org.gnome.seahorse.Application.desktop': 'Trousseau',
    'gnome-language-selector.desktop': 'Langues',
    'vlc.desktop': 'VLC',
    'libreoffice-startcenter.desktop': 'LibreOffice',
    'libreoffice-calc.desktop': 'Calc', 'libreoffice-draw.desktop': 'Draw',
    'libreoffice-impress.desktop': 'Impress', 'libreoffice-math.desktop': 'Math',
    'libreoffice-writer.desktop': 'Writer',
    'minecraft-launcher.desktop': 'Minecraft',
    'org.gnome.SystemMonitor.desktop': 'Moniteur',
    'chromium_chromium.desktop': 'Chromium',
    'thunderbird_thunderbird.desktop': 'Thunderbird',
    'nethack-console.desktop': 'NetHack',
    'com.nvidia.geforcenow.desktop': 'GeForce',
    'remotegamepad.desktop': 'Manette',
    'software-properties-gtk.desktop': 'Sources',
    'update-manager.desktop': 'Mise à jour',
    'usb-creator-gtk.desktop': 'Créer USB',
    'synaptic.desktop': 'Synaptic',
    'teams-for-linux_teams-for-linux.desktop': 'Teams',
    'org.torproject.torbrowser-launcher.desktop': 'Tor',
    'windows-app-for-linux_windows-app-for-linux.desktop': 'Windows',
    'whatsapp-linux-desktop_whatsapp-linux-desktop.desktop': 'WhatsApp',
    'org.gnome.Showtime.desktop': 'Vidéos',
    'gimp.desktop': 'GIMP',
    'code_code.desktop': 'VS Code',
    'instagram-electron_instagram-electron.desktop': 'Instagram',
    'mpv.desktop': 'mpv',
    'org.gnome.Calculator.desktop': 'Calculette',
    'org.gnome.TextEditor.desktop': 'Éditeur',
    'org.gnome.DejaDup.desktop': 'Sauvegarde',
    'transmission-gtk.desktop': 'Torrents',
    'net.nokyan.Resources.desktop': 'Ressources',
}

# ── icônes : style Papirus partout où il existe ─────────────────────────────
ICONES = {
    'chrome-nlalbmkafgmoifbeooblidblkmlhhpnc-Default.desktop': 'tiktok',
    'dev.warp.Warp.desktop': 'dev.warp.Warp',        # icône officielle (remplacée à tort par celle de WezTerm)
}

# ── dossiers de la grille (ordre = ordre d'affichage) ───────────────────────
DOSSIERS = [
    ('Arsenal', 'Arsenal', [
        'lynis.desktop', 'proton.vpn.app.gtk.desktop', 'proton-pass_proton-pass.desktop',
        'windscribe.desktop', 'org.torproject.torbrowser-launcher.desktop',
        'org.gnome.seahorse.Application.desktop',
        'desktop-security-center_desktop-security-center.desktop']),
    ('Dev', 'Code', [
        'code_code.desktop', 'arduino-ide.desktop', 'emacsclient.desktop', 'org.kde.kate.desktop',
        'org.kde.kwrite.desktop', 'nvim.desktop', 'vim.desktop', 'org.gnome.Sysprof.desktop']),
    ('Terminaux', 'Terminaux', [
        'org.gnome.Terminal.desktop', 'kitty.desktop', 'org.kde.konsole.desktop', 'qterminal.desktop',
        'dev.warp.Warp.desktop', 'waveterm.desktop', 'byobu.desktop', 'btop.desktop',
        'htop.desktop', 'cmatrix.desktop']),
    ('Internet', 'Internet', [
        'google-chrome.desktop', 'chromium_chromium.desktop', 'firefox_firefox.desktop',
        'thunderbird_thunderbird.desktop', 'freedownloadmanager.desktop', 'transmission-gtk.desktop',
        'filezilla.desktop', 'megasync.desktop', 'org.remmina.Remmina.desktop',
        'remote-viewer.desktop', 'windows-app-for-linux_windows-app-for-linux.desktop']),
    ('Social', 'Social', [
        'whatsapp-linux-desktop_whatsapp-linux-desktop.desktop', 'discord_discord.desktop',
        'telegram-desktop_telegram-desktop.desktop', 'teams-for-linux_teams-for-linux.desktop',
        'gmail-app_gmail-app.desktop', 'outlook-ew_outlook-ew.desktop',
        'instagram-electron_instagram-electron.desktop',
        'chrome-nlalbmkafgmoifbeooblidblkmlhhpnc-Default.desktop',
        'chrome-gfgbgjphjkdhefmnmbhogcpckgpapbag-Default.desktop']),
    ('Multimedia', 'Multimédia', [
        'spotify_spotify.desktop', 'spotify-qt_spotify-qt.desktop', 'vlc.desktop', 'mpv.desktop',
        'org.gnome.Showtime.desktop', 'org.gnome.Rhythmbox3.desktop', 'audacity.desktop',
        'ardour.desktop', 'org.mixxx.Mixxx.desktop', 'com.obsproject.Studio.desktop',
        'org.kde.dragonplayer.desktop', 'org.kde.juk.desktop', 'org.gnome.Snapshot.desktop',
        'org.kde.qrca.desktop']),
    ('Graphisme', 'Graphisme', [
        'gimp.desktop', 'org.gnome.Loupe.desktop', 'org.kde.gwenview.desktop',
        'org.gnome.Shotwell.desktop', 'org.kde.spectacle.desktop', 'wonderwall_wonderwall.desktop',
        'variety.desktop', 'simple-scan.desktop']),
    ('Bureautique', 'Bureau', [
        'obsidian.desktop', 'libreoffice-writer.desktop', 'libreoffice-calc.desktop',
        'libreoffice-impress.desktop', 'libreoffice-draw.desktop', 'libreoffice-math.desktop',
        'libreoffice-startcenter.desktop', 'org.gnome.Papers.desktop', 'org.kde.okular.desktop',
        'org.gnome.Calendar.desktop', 'algobox.desktop',
        'chrome-cdofinfgbgcpdhahkdompcdaegijgddd-Default.desktop']),
    ('Jeux', 'Jeux', [
        'com.valvesoftware.Steam.desktop', 'minecraft-launcher.desktop', 'com.nvidia.geforcenow.desktop',
        'supertux2.desktop', 'pacman.desktop', 'nsnake.desktop', 'bastet.desktop',
        'nethack-console.desktop', 'fortune.desktop', 'remotegamepad.desktop']),
    ('Systeme', 'Système', [
        'org.gnome.tweaks.desktop', 'org.gnome.Extensions.desktop',
        'com.mattjakeman.ExtensionManager.desktop', 'io.github.realmazharhussain.GdmSettings.desktop',
        'org.gnome.SystemMonitor.desktop', 'net.nokyan.Resources.desktop', 'org.gnome.Logs.desktop',
        'conky.desktop', 'org.gnome.DiskUtility.desktop', 'gparted.desktop',
        'org.kde.partitionmanager.desktop', 'org.gnome.baobab.desktop', 'org.gnome.DejaDup.desktop',
        'org.bleachbit.BleachBit.desktop', 'snap-store_snap-store.desktop', 'synaptic.desktop',
        'software-properties-gtk.desktop', 'update-manager.desktop', 'software-properties-drivers.desktop',
        'firmware-updater_firmware-updater.desktop', 'gnome-language-selector.desktop',
        'nm-connection-editor.desktop', 'usb-creator-gtk.desktop', 'virt-manager.desktop',
        'winetricks.desktop', 'ulauncher.desktop', 'org.kde.dolphin.desktop']),
    ('Utilities', 'Utilitaires', [
        'org.gnome.Calculator.desktop', 'org.kde.kcalc.desktop', 'org.gnome.TextEditor.desktop',
        'org.gnome.Characters.desktop', 'org.gnome.clocks.desktop', 'org.gnome.font-viewer.desktop',
        'org.gnome.FileRoller.desktop', 'org.kde.ark.desktop', 'scrcpy.desktop', 'org.gnome.Yelp.desktop',
        'os.shadow.Bienvenue.desktop']),
]
# hors dossiers, en tête de grille (façon Launchpad : les applis courantes, puis les dossiers).
# GNOME n'affiche pas dans la grille les applis épinglées au dock.
EN_TETE = [
    'firefox_firefox.desktop', 'org.torproject.torbrowser-launcher.desktop', 'proton.vpn.app.gtk.desktop',
    'outlook-ew_outlook-ew.desktop', 'instagram-electron_instagram-electron.desktop',
    'chrome-nlalbmkafgmoifbeooblidblkmlhhpnc-Default.desktop',
    'chrome-gfgbgjphjkdhefmnmbhogcpckgpapbag-Default.desktop', 'teams-for-linux_teams-for-linux.desktop',
    'vlc.desktop', 'com.obsproject.Studio.desktop', 'gimp.desktop', 'org.gnome.Loupe.desktop',
    'org.gnome.Papers.desktop', 'libreoffice-writer.desktop', 'libreoffice-impress.desktop',
    'org.gnome.TextEditor.desktop', 'org.gnome.Calculator.desktop', 'kitty.desktop',
    'dev.warp.Warp.desktop', 'waveterm.desktop', 'arduino-ide.desktop', 'com.valvesoftware.Steam.desktop',
    'algobox.desktop', 'chrome-cdofinfgbgcpdhahkdompcdaegijgddd-Default.desktop',
    'org.gnome.Nautilus.desktop', 'org.gnome.Settings.desktop',
]

# ── dock : court, du plus utilisé au réglage ────────────────────────────────
DOCK = [
    'org.gnome.Nautilus.desktop', 'org.gnome.Terminal.desktop', 'google-chrome.desktop',
    'code_code.desktop', 'obsidian.desktop',
    'whatsapp-linux-desktop_whatsapp-linux-desktop.desktop', 'discord_discord.desktop',
    'telegram-desktop_telegram-desktop.desktop', 'gmail-app_gmail-app.desktop',
    'spotify_spotify.desktop', 'org.gnome.Settings.desktop',
]


def gs(*a):
    return subprocess.run(['gsettings', *a], capture_output=True, text=True, check=True).stdout.strip()


def trouver(did):
    for d in DIRS:
        p = os.path.join(d, did)
        if os.path.isfile(p):
            return p
    return None


def executable(cmd):
    import shlex
    try:
        prog = shlex.split(cmd)[0] if cmd else ''
    except ValueError:
        prog = cmd.split()[0] if cmd else ''
    if not prog:
        return False
    if prog in ('env', 'sh', 'bash', '/bin/sh'):
        return True
    return bool(shutil.which(os.path.expanduser(prog)) or os.path.isfile(os.path.expanduser(prog)))


def visibles():
    vus, res = set(), []
    for d in DIRS:
        for f in sorted(glob.glob(d + '/*.desktop')):
            did = os.path.basename(f)
            if did in vus:
                continue
            vus.add(did)
            c = configparser.RawConfigParser(strict=False, interpolation=None)
            c.optionxform = str
            try:
                c.read(f, encoding='utf-8')
                e = c['Desktop Entry']
            except Exception:
                continue
            if e.get('Type', 'Application') != 'Application':
                continue
            if e.get('NoDisplay', 'false').lower() == 'true' or e.get('Hidden', 'false').lower() == 'true':
                continue
            if e.get('OnlyShowIn') and 'GNOME' not in e.get('OnlyShowIn'):
                continue
            if 'GNOME' in e.get('NotShowIn', ''):
                continue
            if not executable(e.get('TryExec') or e.get('Exec', '')):
                continue
            res.append(did)
    return res


def modifier(did, cles):
    """Écrit les clés dans la copie utilisateur du lanceur (sauvegarde l'original une fois)."""
    src = trouver(did)
    if not src:
        print(f'  · absent, ignoré : {did}')
        return False
    dst = os.path.join(USER_APPS, did)
    man = charger_manifeste()
    if did not in man['lanceurs']:
        if os.path.isfile(dst):
            os.makedirs(f'{ETAT}/lanceurs', exist_ok=True)
            shutil.copy2(dst, f'{ETAT}/lanceurs/{did}')
            man['lanceurs'][did] = 'sauvegarde'
        else:
            man['lanceurs'][did] = 'cree'
        sauver_manifeste(man)
    lignes = open(src, encoding='utf-8').read().splitlines()
    out, dans, faits = [], False, set()
    for l in lignes:
        if l.startswith('['):
            if dans:
                out += [f'{k}={v}' for k, v in cles.items() if k not in faits]
                faits |= set(cles)
            dans = (l.strip() == '[Desktop Entry]')
            out.append(l)
            continue
        if dans:
            k = l.split('=', 1)[0].strip()
            base = re.sub(r'\[.*\]$', '', k)
            if k in cles:
                out.append(f'{k}={cles[k]}'); faits.add(k); continue
            if base == 'Name' and 'Name' in cles and k != 'Name':
                continue                      # noms traduits : remplacés par le nom court
        out.append(l)
    if dans:
        out += [f'{k}={v}' for k, v in cles.items() if k not in faits]
    with open(dst, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(out) + '\n')
    return True


def charger_manifeste():
    p = f'{ETAT}/manifeste.json'
    if os.path.isfile(p):
        return json.load(open(p))
    return {'lanceurs': {}, 'dconf': None}


def sauver_manifeste(m):
    os.makedirs(ETAT, exist_ok=True)
    json.dump(m, open(f'{ETAT}/manifeste.json', 'w'), indent=1)


def apply():
    man = charger_manifeste()
    if man['dconf'] is None:
        man['dconf'] = {
            'favorite-apps': gs('get', 'org.gnome.shell', 'favorite-apps'),
            'app-picker-layout': gs('get', 'org.gnome.shell', 'app-picker-layout'),
            'app-folders': subprocess.run(['dconf', 'dump', '/org/gnome/desktop/app-folders/'],
                                          capture_output=True, text=True).stdout,
        }
        sauver_manifeste(man)
        print('  ✓ état d’origine sauvegardé →', ETAT)

    n = sum(modifier(d, {'NoDisplay': 'true'}) for d in MASQUER)
    print(f'  ✓ {n} doublons / outils techniques masqués')
    n = sum(modifier(d, {'Name': nom}) for d, nom in NOMS.items() if d not in MASQUER)
    print(f'  ✓ {n} noms raccourcis')
    n = sum(modifier(d, {'Icon': ic}) for d, ic in ICONES.items())
    print(f'  ✓ {n} icônes unifiées')
    subprocess.run(['update-desktop-database', USER_APPS], capture_output=True)

    # dossiers : une appli en tête de grille ou dans le dock n'y figure pas ;
    # un dossier qui garderait moins de 2 applis est dissous (ses applis vont en tête).
    vis = set(visibles())
    hors = set(EN_TETE) | set(DOCK)
    ids, tete = [], [a for a in EN_TETE if a in vis]
    for fid, nom, apps in DOSSIERS:
        p = f'/org/gnome/desktop/app-folders/folders/{fid}/'
        subprocess.run(['dconf', 'reset', '-f', p])
        utiles = [a for a in apps if a in vis and a not in hors]
        if len(utiles) < 2:
            tete += utiles
            continue
        presentes = [a for a in apps if a in vis and a not in set(EN_TETE)]
        for k, v in (('name', repr(nom)), ('translate', 'false'), ('apps', str(presentes))):
            subprocess.run(['dconf', 'write', p + k, v], check=True)
        ids.append(fid)
    subprocess.run(['dconf', 'write', '/org/gnome/desktop/app-folders/folder-children', str(ids)], check=True)
    noms = {f: n for f, n, _ in DOSSIERS}
    print(f'  ✓ {len(ids)} dossiers : ' + ' · '.join(noms[i] for i in ids))

    # ordre de la grille : applis courantes puis dossiers (les favoris du dock sont ignorés par GNOME)
    ordre = [a for a in tete if a not in set(DOCK)] + ids
    page = '{' + ', '.join(f"'{x}': <{{'position': <{i}>}}>" for i, x in enumerate(ordre)) + '}'
    import time
    for _ in range(5):                       # GNOME réécrit sa disposition après un changement de dossiers
        gs('set', 'org.gnome.shell', 'app-picker-layout', f'[{page}]')
        time.sleep(1.5)
        if gs('get', 'org.gnome.shell', 'app-picker-layout').startswith(f"[{{'{ordre[0]}'"):
            break
    ok = gs('get', 'org.gnome.shell', 'app-picker-layout').startswith(f"[{{'{ordre[0]}'")
    print(f'  {"✓" if ok else "!"} grille : {len(ordre) - len(ids)} applis en tête + {len(ids)} dossiers'
          + ('' if ok else ' (GNOME a réécrit l’ordre)'))

    dock = [a for a in DOCK if trouver(a)]
    gs('set', 'org.gnome.shell', 'favorite-apps', str(dock))
    print(f'  ✓ dock : {len(dock)} applis')
    check()


def check():
    rangees = {a for _, _, l in DOSSIERS for a in l} | set(EN_TETE)
    reste = [a for a in visibles() if a not in rangees]
    if reste:
        print('  ! hors dossiers :', ', '.join(reste))
    else:
        print('  ✓ toutes les applis visibles sont rangées')


def revert():
    man = charger_manifeste()
    for did, etat in man['lanceurs'].items():
        dst = os.path.join(USER_APPS, did)
        if etat == 'cree':
            if os.path.isfile(dst):
                os.remove(dst)
        else:
            shutil.copy2(f'{ETAT}/lanceurs/{did}', dst)
    if man['dconf']:
        d = man['dconf']
        gs('set', 'org.gnome.shell', 'favorite-apps', d['favorite-apps'])
        gs('set', 'org.gnome.shell', 'app-picker-layout', d['app-picker-layout'])
        subprocess.run(['dconf', 'reset', '-f', '/org/gnome/desktop/app-folders/'])
        subprocess.run(['dconf', 'load', '/org/gnome/desktop/app-folders/'], input=d['app-folders'], text=True)
    subprocess.run(['update-desktop-database', USER_APPS], capture_output=True)
    os.rename(f'{ETAT}/manifeste.json', f'{ETAT}/manifeste-annule.json')
    print('  ✓ grille, dossiers, dock et lanceurs remis comme avant')


if __name__ == '__main__':
    {'apply': apply, 'revert': revert, 'check': check}.get(
        sys.argv[1] if len(sys.argv) > 1 else '', lambda: print(__doc__))()
