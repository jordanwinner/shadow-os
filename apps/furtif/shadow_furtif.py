#!/usr/bin/env python3
"""shadow-furtif — le mode furtif de Shadow (façon AnonSurf, en un geste).

Usage :
  shadow furtif on            identité réseau masquée + tout le trafic par Tor
  shadow furtif on --sans-tor identité réseau seulement (compatible VPN de CTF)
  shadow furtif off           tout remettre comme avant
  shadow furtif etat          ce qui est actif, IP vue de l'extérieur
  shadow furtif json          état pour le Centre, l'îlot, le prompt

Identité réseau (réglage global de NetworkManager, donc aussi pour un autre
Wi-Fi rejoint pendant le mode) : adresse MAC aléatoire, nom de la machine non
envoyé au DHCP, adresses IPv6 temporaires. La connexion se rétablit en
quelques secondes. Un profil qui fixe lui-même sa MAC n'est pas concerné
(signalé par « shadow furtif etat »).

Tor : une instance dédiée (ports 9040, 5353, 9150 ; le service tor du système
n'est pas touché) et des règles nftables qui envoient tout le TCP et le DNS
dans Tor et refusent le reste (UDP, IPv6) : rien ne sort en clair. Le réseau
local reste joignable ; les conteneurs root, VM et partages de connexion
sont coupés (leur trafic contournerait Tor). Avant d'activer, Tor doit être
prêt ; après, la sortie par Tor est vérifiée dans la même étape root, et en
cas d'échec tout est annulé aussitôt (sans redemander le mot de passe).

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
NM_CONF = '/etc/NetworkManager/conf.d/99-shadow-furtif.conf'   # identité masquée, pour TOUS les réseaux
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
# adresses des .onion : hors du réseau local (10/8) pour être redirigées vers Tor
VirtualAddrNetworkIPv4 100.64.0.0/10
# par défaut fe80::/10 (lien-local) : inutilisable sans interface, les .onion échoueraient
VirtualAddrNetworkIPv6 [FC00::]/7
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
    ip daddr 100.64.0.0/10 meta l4proto tcp redirect to :9040
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
  chain transit {{
    # conteneurs root, VM, partage de connexion : leur trafic ne passe pas par « sortie »
    type filter hook forward priority 0; policy drop;
  }}
}}
"""

NM_CONTENU = """# Shadow furtif — identité réseau masquée pour toutes les connexions (retiré par « shadow furtif off »)
[connection-shadow-furtif]
wifi.cloned-mac-address=random
ethernet.cloned-mac-address=random
ipv4.dhcp-send-hostname=0
ipv6.dhcp-send-hostname=0
ipv6.ip6-privacy=2
"""

# codes de sortie du script root
ERREURS = {3: 'la connexion n\'a pas pu se rétablir avec l\'identité masquée (réglages remis)',
           4: 'Tor n\'a pas pu démarrer (tout a été annulé)',
           5: 'Tor n\'est pas prêt après 3 min, réseau bloqué ? (tout a été annulé)',
           6: 'les règles nftables ont été refusées (tout a été annulé)',
           7: 'la sortie par Tor n\'a pas pu être vérifiée (tout a été annulé)',
           126: 'mot de passe refusé : rien n\'a changé', 127: 'mot de passe refusé : rien n\'a changé'}
RIEN_APPLIQUE = (3, 4, 5, 6, 7, 126, 127)


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
    """(uuid, type, interface) de la connexion Wi-Fi ou Ethernet active."""
    code, out, _ = lancer('nmcli', '-t', '-f', 'UUID,TYPE,DEVICE', 'connection', 'show', '--active')
    for ligne in out.splitlines():
        uuid, typ, dev = (ligne.split(':') + ['', '', ''])[:3]
        if typ in ('802-11-wireless', '802-3-ethernet') and dev:
            return uuid, typ, dev
    return None


def mac_fixee(uuid, typ):
    """Vrai si le profil impose sa propre MAC : le réglage global ne s'y applique pas."""
    cle = '802-11-wireless.cloned-mac-address' if typ == '802-11-wireless' else '802-3-ethernet.cloned-mac-address'
    code, out, _ = lancer('nmcli', '-g', cle, 'connection', 'show', uuid)
    return code == 0 and out.strip() not in ('', 'random', 'stable')


def ip_vue(timeout=20):
    """IP vue de l'extérieur et si elle est Tor (None si injoignable)."""
    code, out, _ = lancer('curl', '-s', '--max-time', str(timeout), VERIF, timeout=timeout + 5)
    try:
        d = json.loads(out)
        return d.get('IP'), bool(d.get('IsTor'))
    except ValueError:
        return None


def tor_actif():
    return os.path.exists(MARQUE_TOR)


def _identite_on(uuid):
    u = shlex.quote(uuid)
    return f"""
cat > {NM_CONF} <<'FIN'
{NM_CONTENU}FIN
nmcli general reload conf || {{ rm -f {NM_CONF}; exit 3; }}
if ! nmcli connection up {u} >/dev/null 2>&1; then
  # le réseau ne revient pas avec l'identité masquée : on remet tout et on reconnecte
  rm -f {NM_CONF}; nmcli general reload conf; nmcli connection up {u} >/dev/null 2>&1
  exit 3
fi
"""


def _identite_off(uuid):
    reconnecte = f'nmcli connection up {shlex.quote(uuid)} >/dev/null 2>&1 || true' if uuid else ''
    return f"""
if [ -f {NM_CONF} ]; then
  rm -f {NM_CONF}
  nmcli general reload conf || true
  {reconnecte}
fi
"""


def _tor_off():
    return f"""
nft delete table inet {TABLE} 2>/dev/null
systemctl stop shadow-furtif-tor 2>/dev/null; systemctl reset-failed shadow-furtif-tor 2>/dev/null
rm -f {MARQUE_TOR}
"""


def _tor_on(uuid):
    annule = _tor_off() + _identite_off(uuid)
    return f"""
annuler() {{
{annule}
}}
install -d -m 700 -o debian-tor -g debian-tor /var/lib/shadow-furtif-tor
install -d -m 755 /etc/shadow-os /run/shadow-furtif
cat > /etc/shadow-os/furtif-torrc <<'FIN'
{TORRC}FIN
# les .onion peuvent revenir en adresse IPv6 virtuelle : Tor écoute aussi sur ::1, s'il existe
# (un port impossible à ouvrir empêcherait Tor de démarrer : IPv6 désactivé, conteneur…)
if ip -6 addr show dev lo 2>/dev/null | grep -q 'inet6 ::1'; then
  echo 'TransPort [::1]:9040' >> /etc/shadow-os/furtif-torrc
fi
systemctl stop shadow-furtif-tor 2>/dev/null; systemctl reset-failed shadow-furtif-tor 2>/dev/null
systemd-run --unit=shadow-furtif-tor --description="Shadow furtif : Tor" /usr/sbin/tor -f /etc/shadow-os/furtif-torrc >/dev/null \\
  || {{ annuler; exit 4; }}
# Tor prêt AVANT de lui confier le trafic (3 min au plus : premier démarrage à froid sur
# une connexion lente ; ensuite le cache rend cela rapide). Journal de CETTE instance seulement.
inv="$(systemctl show -p InvocationID --value shadow-furtif-tor)"
pret=0
for i in $(seq 1 180); do
  journalctl _SYSTEMD_INVOCATION_ID="$inv" --no-pager -q 2>/dev/null | grep -q 'Bootstrapped 100%' && {{ pret=1; break; }}
  sleep 1
done
[ $pret = 1 ] || {{ annuler; exit 5; }}
nft delete table inet {TABLE} 2>/dev/null
nft -f - <<'FIN' || {{ annuler; exit 6; }}
{NFT}FIN
# vérification de bout en bout, ici même : root passe aussi par Tor
ok=0
for i in 1 2 3; do
  curl -s --max-time 25 {VERIF} | grep -q '"IsTor":true' && {{ ok=1; break; }}
  sleep 3
done
[ $ok = 1 ] || {{ annuler; exit 7; }}
touch {MARQUE_TOR}
"""


def notifier(titre, texte):
    lancer('notify-send', '-a', 'Shadow', '-i', 'shadow-os', titre, texte)


def on(avec_tor=True):
    c = connexion_active()
    if not c:
        print('Aucune connexion Wi-Fi ou Ethernet active : rien à masquer.')
        return 1
    uuid, typ, dev = c
    print(f'◐ Mode furtif sur {dev}' + (' (identité + Tor)' if avec_tor else ' (identité seulement)'))
    if mac_fixee(uuid, typ):
        print('  ⚠ ce réseau impose sa propre adresse MAC : elle ne sera pas changée')
    print('  · une fenêtre de mot de passe va s\'ouvrir ; la connexion va se couper quelques secondes')
    if avec_tor:
        print('  · Tor démarre : jusqu\'à 3 minutes la première fois, quelques secondes ensuite')
    # état écrit AVANT : si quoi que ce soit s'interrompt, le mode apparaît actif et « off » nettoie
    ecrire_etat({'actif': True, 'tor': avec_tor, 'interface': dev, 'uuid': uuid, 'en_cours': True,
                 'depuis': time.strftime('%Y-%m-%dT%H:%M:%S%z')})
    script = 'set -u\n' + _identite_on(uuid) + ('sleep 4\n' + _tor_on(uuid) if avec_tor else '')
    r = subprocess.run(['pkexec', '/bin/bash', '-c', script])
    if r.returncode != 0:
        print(f'  ✘ échec : {ERREURS.get(r.returncode, "interrompu")}')
        if r.returncode in RIEN_APPLIQUE:
            ecrire_etat({})
        else:
            print('  · état incertain : lance « shadow furtif off » pour tout remettre')
        return 1
    e = lire_etat()
    e.pop('en_cours', None)
    ecrire_etat(e)
    if avec_tor:
        v = ip_vue(timeout=20)
        print('  ✔ trafic par Tor' + (f' : IP vue {v[0]}' if v else ''))
    print('  ✔ adresse MAC aléatoire, nom de la machine caché, IPv6 temporaire (tous les réseaux)')
    notifier('Mode furtif actif', 'Trafic par Tor, identité réseau masquée' if avec_tor else 'Identité réseau masquée')
    return 0


def off():
    e = lire_etat()
    c = connexion_active()
    uuid = (c[0] if c else None) or e.get('uuid')
    print('◐ Fin du mode furtif (fenêtre de mot de passe ; la connexion va se couper quelques secondes)')
    r = subprocess.run(['pkexec', '/bin/bash', '-c', 'set -u\n' + _tor_off() + _identite_off(uuid)])
    if r.returncode != 0:
        print('  ✘ échec (mot de passe refusé ?) : le mode furtif est toujours actif')
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
            'en_cours': bool(e.get('en_cours')),
            'interface': e.get('interface'), 'depuis': e.get('depuis'),
            'identite_seule_apres_redemarrage': actif and bool(e.get('tor')) and not e.get('en_cours') and not tor_actif()}


def etat():
    j = etat_json()
    if not j['actif']:
        print('Mode furtif : inactif')
        return 0
    if j['en_cours']:
        print('Mode furtif : activation en cours ou interrompue — « shadow furtif off » pour tout remettre')
        return 0
    print(f"Mode furtif : actif depuis {j['depuis']} sur {j['interface']}")
    c = connexion_active()
    if c and mac_fixee(c[0], c[1]):
        print('  identité réseau : ⚠ ce réseau impose sa propre MAC (non masquée) ; nom de la machine caché')
    else:
        print('  identité réseau : masquée (MAC aléatoire, nom caché), sur tous les réseaux')
    if j['tor']:
        v = ip_vue(timeout=15)
        print(f"  trafic : par Tor — IP vue {v[0] if v else '?'}" + ('' if not v or v[1] else ' ⚠ pas Tor !'))
    elif j['identite_seule_apres_redemarrage']:
        print('  trafic : EN CLAIR — Tor s\'est arrêté au redémarrage (shadow furtif off puis on)')
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
