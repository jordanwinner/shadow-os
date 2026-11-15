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
sys.exit(0 if ok else 1)
