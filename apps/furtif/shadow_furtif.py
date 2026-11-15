#!/usr/bin/env python3
"""shadow-furtif — le mode furtif de Shadow (façon AnonSurf, en un geste).

Usage :
  shadow furtif on            identité réseau masquée + tout le trafic par Tor
  shadow furtif on --sans-tor identité réseau seulement (compatible VPN de CTF)
  shadow furtif off           tout remettre comme avant
  shadow furtif etat          ce qui est actif, IP vue de l'extérieur
  shadow furtif json          état pour le Centre, l'îlot, le prompt

Identité réseau (connexion NetworkManager active) : adresse MAC aléatoire,
nom de la machine non envoyé au DHCP, adresses IPv6 temporaires. La
connexion se rétablit en quelques secondes.

Tor : une instance dédiée (ports 9040, 5353, 9150 ; le service tor du système
n'est pas touché) et des règles nftables qui envoient tout le TCP et le DNS
dans Tor et refusent le reste (UDP, IPv6) : rien ne sort en clair. Le réseau
local reste joignable. Avant d'activer, Tor doit être prêt ; après, Shadow
vérifie qu'on sort bien par Tor, et sinon il annule tout seul.

Le VPN d'un CTF (HTB, THM) ne passe pas par Tor : utilise --sans-tor.
Tout ce qui demande root passe par une seule fenêtre de mot de passe.
"""
import json
import os
import shlex
import subprocess
import sys
import time

MAISON = os.path.expanduser('~')
ETAT_DIR = os.path.join(os.environ.get('XDG_STATE_HOME', MAISON + '/.local/state'), 'shadow-os')
ETAT = os.path.join(ETAT_DIR, 'furtif')            # JSON lu par le Centre, l'îlot, shsh
MARQUE_TOR = '/run/shadow-furtif/tor'               # posé par root : disparaît au redémarrage
SAUVEGARDE = '/var/lib/shadow-os/furtif-nm.json'    # réglages réseau d'avant (root)
VERIF = 'https://check.torproject.org/api/ip'
TABLE = 'shadow_furtif'
LAN = '10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16'

TORRC = """# Shadow furtif — instance Tor dédiée (le service tor du système n'est pas touché)
User debian-tor
DataDirectory /var/lib/shadow-furtif-tor
RunAsDaemon 0
SocksPort 127.0.0.1:9150
TransPort 127.0.0.1:9040
DNSPort 127.0.0.1:5353
AutomapHostsOnResolve 1
VirtualAddrNetworkIPv4 10.192.0.0/10
ClientUseIPv6 0
Log notice syslog
"""

NFT = f"""table inet {TABLE} {{
  chain sortie_nat {{
    type nat hook output priority -100; policy accept;
    meta skuid "debian-tor" return
    oifname "lo" return
    # DNS d'abord, même vers la box du réseau local : sinon fuite DNS
    udp dport 53 redirect to :5353
    ip daddr {{ 127.0.0.0/8, {LAN} }} return
    meta l4proto tcp redirect to :9040
  }}
  chain sortie {{
    type filter hook output priority 0; policy drop;
    oifname "lo" accept
    meta skuid "debian-tor" accept
    tcp dport 53 reject
    ip daddr {{ 127.0.0.0/8, {LAN} }} accept
    ip6 daddr {{ ::1, fe80::/10 }} accept
    udp dport {{ 67, 68 }} accept
    reject
  }}
}}
"""


def lancer(*cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, '', str(e)


def lire_etat():
    try:
        with open(ETAT) as f:
            e = json.load(f)
            return e if isinstance(e, dict) else {}
    except (OSError, ValueError):
        return {}


def ecrire_etat(e):
    os.makedirs(ETAT_DIR, exist_ok=True)
    tmp = ETAT + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(e, f, indent=1)
    os.replace(tmp, ETAT)


def connexion_active():
    """(uuid, type, interface) de la connexion qui porte la route par défaut."""
    code, out, _ = lancer('nmcli', '-t', '-f', 'UUID,TYPE,DEVICE', 'connection', 'show', '--active')
    for ligne in out.splitlines():
        uuid, typ, dev = (ligne.split(':') + ['', '', ''])[:3]
        if typ in ('802-11-wireless', '802-3-ethernet') and dev:
            return uuid, typ, dev
    return None


def ip_vue(socks=False, timeout=20):
    """IP vue de l'extérieur et si elle est Tor (None si injoignable)."""
    cmd = ['curl', '-s', '--max-time', str(timeout)]
    if socks:
        cmd += ['--socks5-hostname', '127.0.0.1:9150']
    code, out, _ = lancer(*cmd, VERIF, timeout=timeout + 5)
    try:
        d = json.loads(out)
        return d.get('IP'), bool(d.get('IsTor'))
    except ValueError:
        return None


def tor_actif():
    return os.path.exists(MARQUE_TOR)


def racine(script):
    """Exécute un script bash en root avec une seule fenêtre de mot de passe (script passé en argument)."""
    r = subprocess.run(['pkexec', '/bin/bash', '-c', script])
    return r.returncode == 0


def script_identite_on(uuid, typ):
    mac = '802-11-wireless.cloned-mac-address' if typ == '802-11-wireless' else '802-3-ethernet.cloned-mac-address'
    u = shlex.quote(uuid)
    champs = f'{mac},ipv4.dhcp-send-hostname,ipv6.dhcp-send-hostname,ipv6.ip6-privacy'
    return f"""
mkdir -p /var/lib/shadow-os
# réglages d'avant, une seule fois (un second « on » ne doit pas écraser la sauvegarde)
if [ ! -f {SAUVEGARDE} ]; then
  nmcli -t -f {champs} connection show {u} > {SAUVEGARDE}.txt || exit 3
  printf '{{"uuid": "%s", "type": "%s"}}\\n' {u} {shlex.quote(typ)} > {SAUVEGARDE}
fi
nmcli connection modify {u} {mac} random ipv4.dhcp-send-hostname no ipv6.dhcp-send-hostname no ipv6.ip6-privacy 2 || exit 3
nmcli connection up {u} >/dev/null || exit 3
"""


def script_identite_off():
    return f"""
if [ -f {SAUVEGARDE} ]; then
  u="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["uuid"])' {SAUVEGARDE})"
  args=()
  while IFS= read -r l; do
    cle="${{l%%:*}}"; val="${{l#*:}}"
    args+=("$cle" "$val")          # valeur vide = réglage par défaut
  done < {SAUVEGARDE}.txt
  nmcli connection modify "$u" "${{args[@]}}" && nmcli connection up "$u" >/dev/null
  rm -f {SAUVEGARDE} {SAUVEGARDE}.txt
fi
"""


def script_tor_on():
    return f"""
install -d -m 700 -o debian-tor -g debian-tor /var/lib/shadow-furtif-tor
install -d -m 755 /etc/shadow-os /run/shadow-furtif
cat > /etc/shadow-os/furtif-torrc <<'FIN'
{TORRC}FIN
systemctl stop shadow-furtif-tor 2>/dev/null; systemctl reset-failed shadow-furtif-tor 2>/dev/null
systemd-run --unit=shadow-furtif-tor --description="Shadow furtif : Tor" /usr/sbin/tor -f /etc/shadow-os/furtif-torrc >/dev/null || exit 4
# Tor doit être prêt AVANT de lui confier le trafic (90 s au plus)
for i in $(seq 1 90); do
  journalctl -u shadow-furtif-tor -n 50 --no-pager 2>/dev/null | grep -q 'Bootstrapped 100%' && break
  sleep 1
done
journalctl -u shadow-furtif-tor -n 80 --no-pager | grep -q 'Bootstrapped 100%' || {{ systemctl stop shadow-furtif-tor; exit 5; }}
nft delete table inet {TABLE} 2>/dev/null
nft -f - <<'FIN' || {{ systemctl stop shadow-furtif-tor; exit 6; }}
{NFT}FIN
# connexions ouvertes avant : coupées, pour qu'aucune ne continue en clair
command -v conntrack >/dev/null && conntrack -F >/dev/null 2>&1
touch {MARQUE_TOR}
"""


def script_tor_off():
    return f"""
nft delete table inet {TABLE} 2>/dev/null
systemctl stop shadow-furtif-tor 2>/dev/null; systemctl reset-failed shadow-furtif-tor 2>/dev/null
rm -f {MARQUE_TOR}
"""


ERREURS = {3: 'NetworkManager a refusé le changement d\'identité',
           4: 'Tor n\'a pas pu démarrer', 5: 'Tor n\'est pas prêt après 90 s (réseau bloqué ?)',
           6: 'les règles nftables ont été refusées'}


def notifier(titre, texte):
    lancer('notify-send', '-a', 'Shadow', '-i', 'shadow-os', titre, texte)


def on(avec_tor=True):
    c = connexion_active()
    if not c:
        print('Aucune connexion Wi-Fi ou Ethernet active : rien à masquer.')
        return 1
    uuid, typ, dev = c
    avant = ip_vue()
    print(f'◐ Mode furtif sur {dev}' + (' (identité + Tor)' if avec_tor else ' (identité seulement)'))
    print('  · une fenêtre de mot de passe va s\'ouvrir ; la connexion va se couper quelques secondes')
    script = 'set -u\n' + script_identite_on(uuid, typ)
    if avec_tor:
        script += 'sleep 4\n' + script_tor_on()
    r = subprocess.run(['pkexec', '/bin/bash', '-c', script])
    if r.returncode != 0:
        print(f'  ✘ échec : {ERREURS.get(r.returncode, "mot de passe refusé ou erreur")}')
        if r.returncode in (5, 6):
            print('  · identité réseau gardée, trafic en clair (rien n\'a été redirigé)')
        return 1
    if avec_tor:
        # vérification de bout en bout : on doit sortir par Tor, sinon on annule tout
        verif = None
        for _ in range(4):
            verif = ip_vue(timeout=25)
            if verif and verif[1]:
                break
            time.sleep(3)
        if not (verif and verif[1]):
            print('  ✘ la sortie par Tor n\'a pas pu être vérifiée : annulation complète')
            racine('set -u\n' + script_tor_off() + script_identite_off())
            ecrire_etat({})
            return 1
        print(f'  ✔ trafic par Tor : IP vue {verif[0]} (avant : {avant[0] if avant else "?"})')
    print('  ✔ adresse MAC aléatoire, nom de la machine caché, IPv6 temporaire')
    ecrire_etat({'actif': True, 'tor': avec_tor, 'interface': dev,
                 'depuis': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                 'ip': verif[0] if avec_tor and verif else None})
    notifier('Mode furtif actif', 'Trafic par Tor, identité réseau masquée' if avec_tor else 'Identité réseau masquée')
    return 0


def off():
    print('◐ Fin du mode furtif (fenêtre de mot de passe ; la connexion va se couper quelques secondes)')
    if not racine('set -u\n' + script_tor_off() + script_identite_off()):
        print('  ✘ échec (mot de passe refusé ?) : rien n\'a changé')
        return 1
    ecrire_etat({})
    time.sleep(4)
    v = ip_vue()
    print('  ✔ réseau normal' + (f' : IP vue {v[0]}' if v else ' (connexion en cours de rétablissement)'))
    notifier('Mode furtif terminé', 'Réseau normal')
    return 0


def etat_json():
    e = lire_etat()
    actif = bool(e.get('actif'))
    tor = actif and e.get('tor') and tor_actif()
    return {'actif': actif, 'tor': bool(tor), 'tor_attendu': bool(e.get('tor')),
            'interface': e.get('interface'), 'depuis': e.get('depuis'),
            'identite_seule_apres_redemarrage': actif and bool(e.get('tor')) and not tor_actif()}


def etat():
    j = etat_json()
    if not j['actif']:
        print('Mode furtif : inactif')
        return 0
    print(f"Mode furtif : actif depuis {j['depuis']} sur {j['interface']}")
    print('  identité réseau : masquée (MAC aléatoire, nom caché)')
    if j['tor']:
        v = ip_vue(timeout=15)
        print(f"  trafic : par Tor — IP vue {v[0] if v else '?'}" + ('' if not v or v[1] else ' ⚠ pas Tor !'))
    elif j['identite_seule_apres_redemarrage']:
        print('  trafic : EN CLAIR — Tor s\'est arrêté au redémarrage (shadow furtif on pour le relancer)')
    else:
        print('  trafic : en clair (--sans-tor)')
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else 'etat'
    if cmd in ('-h', '--help', 'aide'):
        print(__doc__.strip())
        return 0
    if cmd == 'on':
        return on(avec_tor='--sans-tor' not in argv)
    if cmd == 'off':
        return off()
    if cmd == 'json':
        print(json.dumps(etat_json()))
        return 0
    if cmd in ('etat', 'état', 'status'):
        return etat()
    print(f'shadow furtif : « {cmd} » inconnu (shadow furtif aide)', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
