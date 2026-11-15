"""Simule « toutes les extensions coupées » sans toucher au bureau."""
import importlib.util, os, sys, tempfile, json
spec = importlib.util.spec_from_file_location('d', os.path.expanduser('~/Shadow/apps/docteur/shadow_docteur.py'))
d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
tmp = tempfile.mkdtemp(); d.GARDE = os.path.join(tmp, 'garde.json')
etat = {'coupees': 'true'}; appels = []; notifs = []
vrai_gs = d.gs
d.gs = lambda sch, cle, sd=None: etat['coupees'] if cle == 'disable-user-extensions' else vrai_gs(sch, cle, sd)
def faux_set(sch, cle, val, sd=None):
    appels.append((cle, val)); etat['coupees'] = val if cle == 'disable-user-extensions' else etat['coupees']; return True
d.gs_set = faux_set
d.notifier = lambda t, x, critique=False: notifs.append((t, x, critique))
d.VERIFS = (d.v_extensions,)
ok = True
def verif(nom, cond):
    global ok; ok &= cond; print(('✓ ' if cond else '✗ ') + nom)
c = d.diagnostic()
verif('panne détectée', any(x['id'] == 'extensions-coupees' and x['etat'] == d.PANNE for x in c))
d.auto()
verif('1er passage : rallumées', ('disable-user-extensions', 'false') in appels and notifs and 'réparé' in notifs[-1][0])
etat['coupees'] = 'true'; appels.clear()   # GNOME les recoupe : plantage probable
d.auto()
verif('2e coupure, même démarrage : pas de nouvelle tentative', not appels)
verif('2e coupure : notification critique', notifs[-1][2] is True and 'souci' in notifs[-1][0])
n = len(notifs); d.auto()
verif('pas de notification en boucle', len(notifs) == n)
g = json.load(open(d.GARDE)); g['boot'] = 'autre'; json.dump(g, open(d.GARDE, 'w'))
d.auto()
verif('nouveau démarrage : nouvelle tentative', ('disable-user-extensions', 'false') in appels)
# Extension éteinte exprès : signalée, jamais rallumée par « auto »
etat['coupees'] = 'false'; appels.clear()
d.reference = lambda: ['a@x', 'b@x']
d.actives_gsettings = lambda: ['a@x']
d.extensions_shell = lambda: {'a@x': {'state': 1.0}, 'b@x': {'state': 2.0}}
lances = []
d.lancer = lambda *cmd, entree=None: (lances.append(cmd), (0, ''))[1]
json.dump({'boot': d.id_demarrage(), 'deja': [], 'signale': []}, open(d.GARDE, 'w'))
d.auto()
verif('éteinte exprès : pas de rallumage auto', not any('enable' in c for c in lances))
verif('éteinte exprès : signalée', 'souci' in notifs[-1][0])
# Garde corrompue : pas de plantage
open(d.GARDE, 'w').write('[1, 2]')
try:
    d.auto(); verif('garde corrompue : pas de plantage', True)
except Exception as e:
    verif(f'garde corrompue : pas de plantage ({e})', False)
# Référence absente : jamais créée en douce
spec2 = importlib.util.spec_from_file_location('d2', os.path.expanduser('~/Shadow/apps/docteur/shadow_docteur.py'))
d2 = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(d2)
d2.CONFIG = os.path.join(tmp, 'absent', 'docteur.json')
verif('référence absente : None', d2.reference() is None)
verif('référence absente : rien écrit', not os.path.exists(d2.CONFIG))
open(os.path.join(tmp, 'corrompu.json'), 'w').write('["pas", "un", "dict"]')
d2.CONFIG = os.path.join(tmp, 'corrompu.json')
verif('référence corrompue : None', d2.reference() is None)
sys.exit(0 if ok else 1)
