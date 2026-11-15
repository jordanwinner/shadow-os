#!/usr/bin/env python3
"""shadow-cible — la cible de la mission en cours (mode Pentest de Shadow).

Fixer une cible :
  - l'affiche en permanence dans l'îlot ;
  - crée le dossier de mission (~/ctf/NOM : notes.md, scans/, butin/) ;
  - écrit un fichier d'exports ($CIBLE, $TARGET, $MISSION) que tes terminaux
    peuvent lire. Ce branchement n'est jamais fait d'office : c'est toi qui
    le demandes, une fois, avec « shadow-cible terminaux ».

Usage :
  shadow-cible                    affiche la cible en cours
  shadow-cible ADRESSE [NOM]      fixe la cible (IP, nom d'hôte ou plage CIDR)
  shadow-cible fin                termine la mission (le dossier est conservé)
  shadow-cible terminaux          montre la ligne à ajouter à ~/.bashrc / ~/.zshrc
  shadow-cible terminaux installer  l'ajoute pour toi (une seule fois, ligne marquée)
  shadow-cible json               état complet, pour le Centre Shadow
  shadow-cible rapport [NOM] [--sortie FICHIER] [--pdf]
                                  rapport Markdown de la mission (en cours ou ~/ctf/NOM) :
                                  chronologie tirée du journal de shsh, ports trouvés
                                  dans scans/, butin (avec empreintes), notes
"""
import hashlib
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

MAISON = os.path.expanduser('~')
ETAT_DIR = os.path.join(os.environ.get('XDG_STATE_HOME', MAISON + '/.local/state'), 'shadow-os')
ETAT = os.path.join(ETAT_DIR, 'cible')              # JSON, lu par l'îlot et le Centre
ENV = os.path.join(ETAT_DIR, 'cible.env')           # exports, lus par les shells
MISSIONS = os.path.join(MAISON, 'ctf')
MARQUE = '# Shadow : cible de mission (shadow-cible)'
LIGNE = f'[ -r "{ENV}" ] && . "{ENV}"  {MARQUE}'
ADRESSE = re.compile(r'^[A-Za-z0-9]([A-Za-z0-9._:-]*[A-Za-z0-9])?(/\d{1,3})?$')


def lire():
    try:
        with open(ETAT) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def shells_branches():
    """Fichiers de démarrage (parmi ~/.bashrc, ~/.zshrc) qui lisent déjà la cible."""
    faits = []
    for rc in ('.bashrc', '.zshrc'):
        try:
            with open(os.path.join(MAISON, rc)) as f:
                if MARQUE in f.read():
                    faits.append(rc)
        except OSError:
            pass
    return faits


def brancher_shells():
    """Ajoute la lecture de la cible à ~/.bashrc et ~/.zshrc. Uniquement à la demande explicite."""
    ajoutes = []
    for rc in ('.bashrc', '.zshrc'):
        chemin = os.path.join(MAISON, rc)
        try:
            with open(chemin) as f:
                if MARQUE in f.read():
                    continue
            with open(chemin, 'a') as f:
                f.write(f'\n{LIGNE}\n')
            ajoutes.append(rc)
        except OSError:
            pass
    return ajoutes


def fixer(adresse, nom=None):
    if not ADRESSE.match(adresse):
        sys.exit(f'adresse invalide : {adresse!r} (IP, nom d’hôte ou plage CIDR attendus)')
    nom = re.sub(r'[^A-Za-z0-9._-]+', '-', nom or adresse.replace('/', '_')).strip('-') or 'mission'
    dossier = os.path.join(MISSIONS, nom)
    for d in (dossier, os.path.join(dossier, 'scans'), os.path.join(dossier, 'butin')):
        os.makedirs(d, exist_ok=True)
    notes = os.path.join(dossier, 'notes.md')
    if not os.path.exists(notes):
        with open(notes, 'w') as f:
            f.write(f'# Mission {nom}\n\n- Cible : `{adresse}`\n- Début : {datetime.date.today().isoformat()}\n\n'
                    '## Reconnaissance\n\n## Accès initial\n\n## Élévation de privilèges\n\n## Preuves\n')
    os.makedirs(ETAT_DIR, exist_ok=True)
    etat = {'cible': adresse, 'nom': nom, 'dossier': dossier,
            'depuis': datetime.datetime.now().isoformat(timespec='seconds')}
    marque = os.path.join(dossier, '.mission')
    if not os.path.exists(marque):
        with open(marque, 'w') as f:
            json.dump({'cible': adresse, 'debut': etat['depuis']}, f)
    with open(ETAT, 'w') as f:
        json.dump(etat, f, indent=1)
    with open(ENV, 'w') as f:
        f.write(f'# cible de mission Shadow — géré par shadow-cible\n'
                f'export CIBLE={shlex.quote(adresse)}\nexport TARGET={shlex.quote(adresse)}\n'
                f'export MISSION={shlex.quote(dossier)}\n')
    return etat


def terminer():
    for chemin in (ETAT, ENV):
        try:
            os.unlink(chemin)
        except OSError:
            pass


LIGNE_JOURNAL = re.compile(r'^- (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) · (✔|✘ -?\d+) · ([^·]+) · (`+) ?(.*?) ?\4 — (`+) ?(.*?) ?\6'
                           r'((?: · preuve : \[preuves/[^\]/]+\]\(preuves/[^)/]+\))*)$')
PREUVE_LIEN = re.compile(r' · preuve : \[(preuves/[^\]/]+)\]')
PREUVE_LIGNES = 60                       # extrait de chaque preuve dans le rapport
PORT_NMAP = re.compile(r'^(\d+)/(tcp|udp)\s+open\s+(\S+)\s*(.*)$')


def _cellule(t):
    return t.replace('|', '\\|').replace('\n', ' ')


def _code(t):
    """Code en ligne Markdown qui garde les accents graves de la commande."""
    t = _cellule(t)
    n = 1
    while '`' * n in t:
        n += 1
    pad = ' ' if t.startswith('`') or t.endswith('`') or n > 1 else ''
    return f"{'`' * n}{pad}{t}{pad}{'`' * n}"


def rapport(nom=None, sortie=None):
    """Assemble le rapport Markdown d'une mission. Renvoie le chemin écrit."""
    etat = lire() or {}
    if nom:
        if '/' in nom or nom in ('.', '..') or nom.startswith('.'):
            sys.exit(f'nom de mission invalide : {nom!r} (un dossier de ~/ctf, sans « / »)')
        dossier = os.path.join(MISSIONS, nom)
        adresse = etat.get('cible') if etat.get('nom') == nom else None
    else:
        if not etat:
            sys.exit('Aucune mission en cours : shadow rapport NOM (dossier ~/ctf/NOM)')
        dossier, nom, adresse = etat['dossier'], etat['nom'], etat['cible']
    if not os.path.isdir(dossier):
        sys.exit(f'mission introuvable : {dossier}')
    notes = ''
    try:
        with open(os.path.join(dossier, 'notes.md')) as f:
            notes = f.read()
    except OSError:
        pass
    if not adresse:
        m = re.search(r'Cible : `([^`]+)`', notes)
        adresse = m.group(1) if m else '?'

    # Chronologie : journal écrit par shsh pendant la mission
    entrees = []
    try:
        with open(os.path.join(dossier, 'journal.md')) as f:
            for ligne in f:
                m = LIGNE_JOURNAL.match(ligne.rstrip('\n'))
                if m:
                    entrees.append({'quand': m.group(1), 'code': m.group(2), 'duree': m.group(3).strip(),
                                    'dossier': m.group(5), 'commande': m.group(7),
                                    'preuves': PREUVE_LIEN.findall(m.group(8) or '')})
    except OSError:
        pass
    echecs = sum(1 for e in entrees if e['code'] != '✔')

    # Ports ouverts trouvés dans les sorties nmap (-oN / -oA) rangées dans scans/
    ports = {}
    scans = os.path.join(dossier, 'scans')
    for racine, _, fichiers in os.walk(scans):
        for nomf in sorted(fichiers):
            if not nomf.endswith(('.nmap', '.txt', '.log')):
                continue
            try:
                with open(os.path.join(racine, nomf), errors='replace') as f:
                    for ligne in f:
                        m = PORT_NMAP.match(ligne.strip())
                        if m:
                            ports.setdefault((int(m.group(1)), m.group(2)), (m.group(3), m.group(4).strip(), nomf))
            except OSError:
                pass

    # Butin : fichiers récupérés, avec taille et empreinte (preuve d'intégrité)
    butin = []
    for racine, _, fichiers in os.walk(os.path.join(dossier, 'butin')):
        for nomf in sorted(fichiers):
            chemin = os.path.join(racine, nomf)
            if os.path.islink(chemin) or not os.path.isfile(chemin):
                continue                                   # liens, FIFO, périphériques : ignorés
            try:
                h = hashlib.sha256()
                with open(chemin, 'rb') as f:
                    for bloc in iter(lambda: f.read(1 << 16), b''):
                        h.update(bloc)
                butin.append((os.path.relpath(chemin, dossier), os.path.getsize(chemin), h.hexdigest()))
            except OSError:
                pass

    debut = entrees[0]['quand'] if entrees else '—'
    fin = entrees[-1]['quand'] if entrees else '—'
    o = [f'# Rapport de mission — {nom}', '',
         f'*Généré par Shadow le {datetime.datetime.now():%Y-%m-%d à %H:%M}.*', '',
         '| | |', '|---|---|',
         f'| Cible | `{_cellule(adresse)}` |',
         f'| Période | {debut} → {fin} |',
         f'| Commandes notées | {len(entrees)} (dont {echecs} en échec) |',
         f'| Preuves gardées | {sum(len(e["preuves"]) for e in entrees)} |',
         f'| Ports ouverts | {len(ports)} |',
         f'| Fichiers de butin | {len(butin)} |', '']
    o += ['## Ports et services', '']
    if ports:
        o += ['| Port | Service | Version | Source |', '|---|---|---|---|']
        o += [f'| {p}/{proto} | {_cellule(svc)} | {_cellule(ver) or "—"} | `{src}` |'
              for (p, proto), (svc, ver, src) in sorted(ports.items())]
    else:
        o.append('Aucune sortie nmap dans `scans/` (astuce : `nmap -oA scans/initial $CIBLE`).')
    o += ['', '## Chronologie', '']
    if entrees:
        o += ['| Heure | Résultat | Durée | Commande |', '|---|---|---|---|']
        for i, e in enumerate(entrees):
            lien = ''.join(f' · [preuve](#preuve-{i}-{k})' for k in range(len(e['preuves'])))
            o.append(f'| {e["quand"]} | {e["code"]} | {e["duree"]} | {_code(e["commande"])}{lien} |')
    else:
        o.append('Aucune commande notée : le journal est tenu par shsh pendant une mission (`journal mission`).')
    # Preuves : sortie gardée par « preuve COMMANDE » dans shsh, extrait sous chaque commande
    preuves = [(i, k, e, p) for i, e in enumerate(entrees) for k, p in enumerate(e['preuves'])]
    if preuves:
        o += ['', '## Preuves', '']
        for i, k, e, p in preuves:
            chemin = os.path.join(dossier, p)
            texte = None
            # nom borné à preuves/<fichier> par la regex ; liens symboliques et noms piégés refusés
            if '\0' not in p and os.path.basename(p) not in ('.', '..') and not os.path.islink(chemin):
                try:
                    with open(chemin, errors='replace') as f:
                        texte = f.read()
                except (OSError, ValueError):
                    texte = None
            # titre : la commande lue dans l'en-tête de la preuve (fiable même pour « cd x && preuve … »)
            titre = next((l[len('# Preuve — '):] for l in (texte or '').split('\n')[:1] if l.startswith('# Preuve — ')),
                         re.sub(r'^preuve\s+', '', e['commande']))
            o += [f'<a id="preuve-{i}-{k}"></a>', f'### {_code(titre)}', '',
                  f'{e["quand"]} · {e["code"]} · {e["duree"]} · fichier complet : [{p}]({p})', '']
            if texte is None:
                o += ['*Fichier de preuve introuvable.*', '']
                continue
            corps = texte.split('\n---\n', 1)[-1].strip('\n').split('\n')
            extrait = corps[:PREUVE_LIGNES]
            barrieres = max([len(x) for x in re.findall(r'`{3,}', '\n'.join(extrait))] + [2]) + 1
            o += ['`' * barrieres + 'text', *extrait, '`' * barrieres]
            if len(corps) > PREUVE_LIGNES:
                o.append(f'*… {len(corps) - PREUVE_LIGNES} ligne(s) de plus dans le fichier.*')
            o.append('')
    # Captures d'écran prises pendant la mission (copiées dans captures/, jamais déplacées)
    captures = collecter_captures(dossier, *fenetre_mission(dossier, etat if etat.get('dossier') == dossier else {}, entrees))
    if captures:
        o += ['', '## Captures d’écran', '']
        for rel, quand in captures:
            o += [f'![Capture du {quand}]({rel})', '', f'*{quand} · `{rel}`*', '']
    o += ['', '## Butin', '']
    if butin:
        o += ['| Fichier | Taille | SHA-256 |', '|---|---|---|']
        o += [f'| `{_cellule(c)}` | {t} o | `{h}` |' for c, t, h in butin]
    else:
        o.append('Rien dans `butin/`.')
    o += ['', '## Notes', '']
    corps = re.sub(r'\A# .*\n', '', notes)                 # le titre est déjà en tête du rapport
    # titres décalés d'un niveau, sauf dans les blocs de code (commentaires, shebang)
    lignes, dans_code = [], False
    for ligne in corps.split('\n'):
        if ligne.lstrip().startswith(('```', '~~~')):
            dans_code = not dans_code
        elif not dans_code and re.match(r'#+ ', ligne):
            ligne = '#' + ligne
        lignes.append(ligne)
    corps = '\n'.join(lignes)
    o.append(corps.strip() or '—')
    sortie = sortie or os.path.join(dossier, 'rapport.md')
    with open(sortie, 'w') as f:
        f.write('\n'.join(o) + '\n')
    resume = {'commandes': len(entrees), 'echecs': echecs, 'preuves': sum(len(e['preuves']) for e in entrees),
              'ports': len(ports), 'butin': len(butin), 'captures': len(captures), 'cible': adresse, 'nom': nom}
    with open(os.path.join(dossier, '.rapport.json'), 'w') as f:
        json.dump(resume, f)
    return sortie, len(entrees), len(ports), len(butin)


# ── Captures d'écran de la mission ──────────────────────────────────────────
def _dossiers_captures():
    images = subprocess.run(['xdg-user-dir', 'PICTURES'], capture_output=True, text=True).stdout.strip() \
        if shutil.which('xdg-user-dir') else ''
    images = images or os.path.join(MAISON, 'Images')
    return [os.path.join(images, d) for d in ('Captures d’écran', "Captures d'écran", 'Screenshots')]


def fenetre_mission(dossier, etat, entrees):
    """(début, fin) de la mission en secondes : .mission, sinon le journal, sinon la date des notes."""
    debut = fin = None
    try:
        with open(os.path.join(dossier, '.mission')) as f:
            debut = datetime.datetime.fromisoformat(json.load(f)['debut']).timestamp()
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if debut is None and etat.get('depuis'):
        debut = datetime.datetime.fromisoformat(etat['depuis']).timestamp()
    stamps = [datetime.datetime.strptime(e['quand'], '%Y-%m-%d %H:%M:%S').timestamp() for e in entrees]
    if debut is None and stamps:
        debut = min(stamps) - 600
    if etat.get('dossier') == dossier:
        fin = datetime.datetime.now().timestamp()          # mission en cours
    elif stamps:
        fin = max(stamps) + 1800                           # mission finie : 30 min après la dernière commande
    return debut, fin


def collecter_captures(dossier, debut, fin):
    """Copie dans captures/ les captures prises entre début et fin ; renvoie [(chemin relatif, date)]."""
    cible = os.path.join(dossier, 'captures')
    if debut is not None and fin is not None:
        for d in _dossiers_captures():
            try:
                noms = os.listdir(d)
            except OSError:
                continue
            for n in noms:
                src = os.path.join(d, n)
                if not n.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) or os.path.islink(src):
                    continue
                try:
                    t = os.path.getmtime(src)
                except OSError:
                    continue
                if debut <= t <= fin and not os.path.exists(os.path.join(cible, n)):
                    os.makedirs(cible, exist_ok=True)
                    shutil.copy2(src, os.path.join(cible, n))
    out = []
    try:
        for n in sorted(os.listdir(cible), key=lambda n: os.path.getmtime(os.path.join(cible, n))):
            ch = os.path.join(cible, n)
            if n.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) and os.path.isfile(ch) and not os.path.islink(ch):
                out.append((f'captures/{n}', datetime.datetime.fromtimestamp(os.path.getmtime(ch)).strftime('%Y-%m-%d %H:%M')))
    except OSError:
        pass
    return out


# ── Export HTML et PDF ──────────────────────────────────────────────────────
STYLE = """
@page { size: A4; margin: 18mm 16mm; }
:root { --encre:#16152A; --doux:#5D5A7E; --eclipse:#5A48E8; --braise:#D6246A; --trait:#DDD9F2; --fond:#F6F5FC; }
* { box-sizing: border-box; }
body { font-family: "Inter", "Segoe UI", system-ui, sans-serif; color: var(--encre); font-size: 10.5pt; line-height: 1.5; margin: 0; }
h1 { font-size: 22pt; margin: 0 0 4pt; letter-spacing: -0.02em; }
h1::before { content: "◐ "; color: var(--eclipse); }
h2 { font-size: 14pt; margin: 22pt 0 8pt; padding-bottom: 4pt; border-bottom: 2px solid var(--eclipse); break-after: avoid; }
h3 { font-size: 11.5pt; margin: 14pt 0 6pt; break-after: avoid; }
p { margin: 4pt 0; }
em { color: var(--doux); }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; font-size: 9pt; break-inside: auto; }
th, td { border: 1px solid var(--trait); padding: 4pt 6pt; text-align: left; vertical-align: top; }
th { background: var(--fond); }
tr { break-inside: avoid; }
code { font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace; font-size: 8.6pt; background: var(--fond); padding: 0 3pt; border-radius: 3pt; overflow-wrap: anywhere; }
pre { background: #0E0E16; color: #E9E7F7; padding: 8pt 10pt; border-radius: 6pt; font-size: 8.4pt; white-space: pre-wrap; overflow-wrap: anywhere; }
table.resume td:first-child { color: var(--doux); width: 32%; }
pre code { background: none; color: inherit; padding: 0; }
img { max-width: 100%; border: 1px solid var(--trait); border-radius: 4pt; break-inside: avoid; }
a { color: var(--eclipse); text-decoration: none; }
.pied { margin-top: 24pt; font-size: 8pt; color: var(--doux); border-top: 1px solid var(--trait); padding-top: 6pt; }
"""


def exporter(md, pdf=True):
    """rapport.md → rapport.html (+ rapport.pdf via Chrome headless). Renvoie (html, pdf ou None)."""
    import markdown
    dossier = os.path.dirname(os.path.abspath(md))
    with open(md) as f:
        texte = f.read()
    corps = assainir(markdown.markdown(texte, extensions=['tables', 'fenced_code'], output_format='html'))
    # tableau de résumé (en-tête vide en Markdown) : pas de ligne d'en-tête vide dans le PDF
    corps = re.sub(r'<table>\s*<thead>\s*<tr>\s*(?:<th>\s*</th>\s*)+</tr>\s*</thead>', '<table class="resume">', corps, count=1)
    titre = re.search(r'^# (.+)$', texte, re.M)
    titre = html_echappe(titre.group(1)) if titre else 'Rapport de mission'
    # CSP : aucun script, aucune ressource distante, même si quelque chose passait le filtre
    csp = "default-src 'none'; img-src 'self' file:; style-src 'unsafe-inline'"
    page = (f'<!doctype html><html lang="fr"><head><meta charset="utf-8">'
            f'<meta http-equiv="Content-Security-Policy" content="{csp}"><title>{titre}</title>'
            f'<style>{STYLE}</style></head><body>{corps}'
            f'<p class="pied">Rapport généré par Shadow OS · usage restreint au périmètre de la mission</p></body></html>')
    html = os.path.join(dossier, 'rapport.html')
    with open(html, 'w') as f:
        f.write(page)
    if not pdf:
        return html, None
    chrome = shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser')
    if not chrome:
        return html, None
    sortie_pdf = os.path.join(dossier, 'rapport.pdf')
    # jamais d'ancien PDF présenté comme neuf si Chrome échoue
    try:
        os.unlink(sortie_pdf)
    except OSError:
        pass
    import tempfile
    with tempfile.TemporaryDirectory(prefix='shadow-rapport-') as profil:
        # profil jetable : ne touche jamais au Chrome de l'utilisateur
        r = subprocess.run([chrome, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
                            f'--user-data-dir={profil}', '--no-first-run',
                            f'--print-to-pdf={sortie_pdf}', 'file://' + html],
                           capture_output=True, text=True, timeout=120)
    return html, (sortie_pdf if r.returncode == 0 and os.path.exists(sortie_pdf) else None)


def html_echappe(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# Le rapport contient des textes venus de la cible (bannières nmap, sorties de commandes) :
# seul un HTML sûr, produit par le Markdown, est gardé. Tout autre balise est affichée comme texte.
_BALISES = {'h1', 'h2', 'h3', 'h4', 'p', 'em', 'strong', 'code', 'pre', 'table', 'thead', 'tbody', 'tr', 'th',
            'td', 'ul', 'ol', 'li', 'a', 'img', 'br', 'hr', 'blockquote'}
_ATTRS = {'a': {'id', 'href'}, 'img': {'src', 'alt'}, 'table': {'class'}, 'td': {'align'}, 'th': {'align'},
          'code': {'class'}}


def assainir(html):
    from html.parser import HTMLParser

    class Filtre(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.o = []

        def _attrs(self, tag, attrs):
            garde = []
            for k, v in attrs:
                v = v or ''
                if k not in _ATTRS.get(tag, set()):
                    continue
                if k in ('href', 'src'):
                    bas = v.strip().lower()
                    # ni script ni ressource distante : liens internes (#…) et fichiers de la mission
                    if bas.startswith(('javascript:', 'data:', 'vbscript:', '//')) or '://' in bas:
                        if not (k == 'href' and bas.startswith(('http://', 'https://'))):
                            continue
                    if k == 'src' and ('://' in bas or bas.startswith(('/', '//')) or '..' in bas):
                        continue
                garde.append(f' {k}="{html_echappe(v).replace(chr(34), "&quot;")}"')
            return ''.join(garde)

        def handle_starttag(self, tag, attrs):
            if tag in _BALISES:
                self.o.append(f'<{tag}{self._attrs(tag, attrs)}>')
            else:
                self.o.append(html_echappe(self.get_starttag_text() or ''))

        def handle_startendtag(self, tag, attrs):
            if tag in _BALISES:
                self.o.append(f'<{tag}{self._attrs(tag, attrs)}>')
            else:
                self.o.append(html_echappe(self.get_starttag_text() or ''))

        def handle_endtag(self, tag):
            self.o.append(f'</{tag}>' if tag in _BALISES else html_echappe(f'</{tag}>'))

        def handle_data(self, d):
            self.o.append(d)

        def handle_entityref(self, n):
            self.o.append(f'&{n};')

        def handle_charref(self, n):
            self.o.append(f'&#{n};')

        def handle_comment(self, d):
            pass

        def handle_decl(self, d):
            pass

        def unknown_decl(self, d):
            pass

    f = Filtre()
    f.feed(html)
    f.close()
    return ''.join(f.o)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ''
    if cmd in ('-h', '--help', 'aide'):
        print(__doc__.strip())
    elif cmd == 'json':
        print(json.dumps(lire() or {}))
    elif cmd == 'terminaux':
        if len(argv) > 2 and argv[2] == 'installer':
            ajoutes = brancher_shells()
            print(('Ligne ajoutée à : ' + ', '.join('~/' + a for a in ajoutes)) if ajoutes else 'Déjà en place, rien à faire')
        else:
            faits = shells_branches()
            print('shsh, le shell de Shadow, reçoit déjà $CIBLE, $TARGET et $MISSION tout seul.\n'
                  'Pour bash et zsh, ajoute cette ligne à la fin de ~/.bashrc et de ~/.zshrc\n'
                  '(ou lance « shadow-cible terminaux installer ») :\n\n'
                  f'  {LIGNE}\n\n'
                  + ('Déjà en place dans : ' + ', '.join('~/' + f for f in faits) if faits else 'Pas encore en place.'))
    elif cmd == 'rapport':
        reste, nom, sortie, pdf = argv[2:], None, None, False
        while reste:
            a = reste.pop(0)
            if a in ('--sortie', '-o') and reste:
                sortie = os.path.abspath(reste.pop(0))
            elif a == '--pdf':
                pdf = True
            elif not a.startswith('-'):
                nom = a
        chemin, n, p, b = rapport(nom, sortie)
        print(f'Rapport : {chemin}\n  {n} commande(s), {p} port(s) ouvert(s), {b} fichier(s) de butin')
        if pdf:
            html, fichier_pdf = exporter(chemin)
            print(f'  HTML : {html}')
            print(f'  PDF  : {fichier_pdf}' if fichier_pdf else '  PDF : échec (Chrome ou Chromium introuvable ?)')
    elif cmd in ('fin', 'stop', 'off'):
        avant = lire()
        terminer()
        print(f'Mission terminée ({avant["cible"]}) — dossier conservé : {avant["dossier"]}' if avant else 'Aucune cible en cours')
    elif cmd:
        e = fixer(cmd, argv[2] if len(argv) > 2 else None)
        print(f'Cible : {e["cible"]}\nMission : {e["dossier"]}')
        print('Dans les nouveaux terminaux : $CIBLE, $TARGET et $MISSION' if shells_branches()
              else 'Terminaux non branchés : voir « shadow-cible terminaux »')
    else:
        e = lire()
        print(f'Cible : {e["cible"]} · mission {e["nom"]} ({e["dossier"]})' if e else 'Aucune cible en cours (shadow cible ADRESSE [NOM])')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
