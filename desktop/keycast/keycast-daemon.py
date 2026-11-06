#!/usr/bin/env python3
"""
Afficheur de touches (keycast) — lit /dev/input directement (aucune dépendance).
Nécessite d'être dans le groupe 'input'. Affiche chaque appui/raccourci sur stdout,
une ligne par événement : l'extension Dynamic Island lit ces lignes et les montre à l'écran.

Rien n'est enregistré sur disque : les touches sont seulement relayées en direct.
  --selftest : décode un évènement factice et quitte (vérifie l'analyse struct).
"""
import glob, os, select, struct, sys, time

# struct input_event (64 bits) : tv_sec(q) tv_usec(q) type(H) code(H) value(i)
_FMT = "qqHHi"
_SZ = struct.calcsize(_FMT)
EV_KEY = 0x01

MODS = {29: "Ctrl", 97: "Ctrl", 42: "Shift", 54: "Shift",
        56: "Alt", 100: "AltGr", 125: "Super", 126: "Super"}

# keycodes Linux -> libellé (AZERTY pour les touches qui diffèrent)
KEYS = {
    1:"Échap", 14:"⌫", 15:"Tab", 28:"Entrée", 57:"Espace", 58:"Verr.Maj",
    111:"Suppr", 102:"Début", 107:"Fin", 104:"PgPréc", 109:"PgSuiv",
    105:"←", 106:"→", 103:"↑", 108:"↓",
    59:"F1",60:"F2",61:"F3",62:"F4",63:"F5",64:"F6",65:"F7",66:"F8",67:"F9",68:"F10",87:"F11",88:"F12",
    # rangée chiffres AZERTY (sans Shift)
    2:"&",3:"é",4:'"',5:"'",6:"(",7:"-",8:"è",9:"_",10:"ç",11:"à",12:")",13:"=",
    # lettres (positions AZERTY)
    16:"A",17:"Z",18:"E",19:"R",20:"T",21:"Y",22:"U",23:"I",24:"O",25:"P",
    30:"Q",31:"S",32:"D",33:"F",34:"G",35:"H",36:"J",37:"K",38:"L",39:"M",
    44:"W",45:"X",46:"C",47:"V",48:"B",49:"N",
    # ponctuation AZERTY
    50:",",51:";",52:":",53:"!",40:"ù",43:"*",26:"^",27:"$",86:"<",
    55:"*", 98:"/", 74:"-", 78:"+", 96:"Entrée",
}

def label(code):
    return KEYS.get(code, f"[{code}]")

def keyboards():
    devs = []
    for path in glob.glob("/dev/input/event*"):
        try:
            devs.append(open(path, "rb", buffering=0))
        except OSError:
            pass
    return devs

def run():
    devs = keyboards()
    if not devs:
        print("ERR: aucun périphérique /dev/input lisible (groupe 'input' ?)", file=sys.stderr)
        sys.exit(1)
    held = set()
    fds = {d.fileno(): d for d in devs}
    while True:
        r, _, _ = select.select(list(fds), [], [], 1.0)
        for fd in r:
            data = fds[fd].read(_SZ)
            if not data or len(data) < _SZ:
                continue
            _, _, etype, code, value = struct.unpack(_FMT, data)
            if etype != EV_KEY:
                continue
            if code in MODS:
                if value == 1: held.add(MODS[code])
                elif value == 0: held.discard(MODS[code])
                continue
            if value != 1:        # on n'affiche que les appuis (pas les relâchements)
                continue
            mods = [m for m in ("Super","Ctrl","Alt","AltGr","Shift") if m in held]
            combo = "+".join(mods + [label(code)]) if mods else label(code)
            sys.stdout.write(combo + "\n"); sys.stdout.flush()

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        buf = struct.pack(_FMT, 0, 0, EV_KEY, 46, 1)   # appui sur 'C'
        _,_,t,c,v = struct.unpack(_FMT, buf)
        print("selftest:", "OK" if (t==EV_KEY and label(c)=="C" and v==1) else "FAIL", "->", label(c))
    else:
        run()
