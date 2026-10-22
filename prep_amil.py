import csv, json, re, sys, unicodedata
from collections import Counter, defaultdict

SRC = sys.argv[1]
OUT = sys.argv[2]

def strip_acc(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

ABBR = [
    (r'^R\b\.?', 'RUA'), (r'^AV\b\.?', 'AVENIDA'), (r'^AL\b\.?', 'ALAMEDA'),
    (r'^PCA\b\.?', 'PRACA'), (r'^PC\b\.?', 'PRACA'), (r'^TV\b\.?', 'TRAVESSA'),
    (r'^ESTR\b\.?', 'ESTRADA'), (r'^EST\b\.?', 'ESTRADA'), (r'^ROD\b\.?', 'RODOVIA'),
    (r'^LGO\b\.?', 'LARGO'), (r'^VL\b\.?', 'VILA'), (r'^PQ\b\.?', 'PARQUE'),
    (r'^JD\b\.?', 'JARDIM'), (r'^MAL\b\.?', 'MARECHAL'), (r'^VD\b\.?', 'VIADUTO'),
]
# complementos que devem sair da query de geocodificacao
COMP = re.compile(r'\b(CONJ|CJ|SL|SLJ|SALA|SALAS|AND|ANDAR|BL|BLOCO|APTO|AP|TORRE|LOJA|LJ|CASA|FUNDOS|SOBRELOJA|EDIF|ED|PAV|GALPAO|BOX)\b', re.I)

def norm_street(s):
    s = strip_acc(s).upper().strip()
    s = re.sub(r'\s+', ' ', s)
    for pat, rep in ABBR:
        s2 = re.sub(pat, rep, s)
        if s2 != s:
            s = s2
            break
    return s.strip(' .,-')

def parse_end(end):
    """ENDERECO -> (logradouro, numero, complemento, bairro)"""
    raw = end.strip()
    parts = [p.strip() for p in raw.split(',')]
    bairro = ''
    # o bairro costuma ser o ultimo pedaco e nao conter digitos nem complemento
    if len(parts) >= 2:
        cand = parts[-1]
        if not re.search(r'\d', cand) and not COMP.search(cand):
            bairro = cand
            parts = parts[:-1]
    logr = parts[0] if parts else raw
    resto = ', '.join(parts[1:])
    m = re.match(r'\s*(\d+[A-Z]?)\b(.*)$', resto)
    numero, comp = '', resto
    if m:
        numero, comp = m.group(1), m.group(2)
    comp = comp.strip(' -,')
    return norm_street(logr), numero, strip_acc(comp).upper().strip(' -,'), strip_acc(bairro).upper().strip()

rows, vazios = [], 0
with open(SRC, encoding='utf-8-sig', newline='') as fh:
    for r in csv.DictReader(fh, delimiter=';'):
        nome = (r.get('NOME') or '').strip()
        end  = (r.get('ENDERECO') or '').strip()
        if not nome or not end:
            vazios += 1
            continue
        logr, num, comp, bairro = parse_end(end)
        esp = [e.strip() for e in (r.get('ESPECIALIDADES') or '').split(',') if e.strip()]
        rows.append({
            'n': nome, 'end_raw': end, 'lg': logr, 'nu': num, 'cp': comp, 'ba': bairro,
            'f': (r.get('TELEFONE') or '').strip(), 'es': esp,
        })

# chave de geocodificacao: logradouro + numero + bairro
for r in rows:
    r['k'] = (r['lg'] + '|' + r['nu'] + '|' + r['ba']).strip('|')

uniq = {}
for r in rows:
    uniq.setdefault(r['k'], {'lg': r['lg'], 'nu': r['nu'], 'ba': r['ba']})

sem_num = sum(1 for r in rows if not r['nu'])
print('registros        :', len(rows), '(descartados sem nome/endereco:', vazios, ')')
print('enderecos unicos :', len(uniq))
print('sem numero       :', sem_num)
print('bairros distintos:', len(set(r['ba'] for r in rows if r['ba'])))
print('especialidades   :', len(set(e for r in rows for e in r['es'])))
print()
print('--- amostra de parse ---')
for r in rows[:6]:
    print(f"  {r['end_raw'][:62]:<62} -> lg={r['lg'][:28]:<28} nu={r['nu']:<6} ba={r['ba'][:20]}")
print()
print('--- bairros mais comuns ---')
for b, c in Counter(r['ba'] for r in rows if r['ba']).most_common(10):
    print(f'  {c:>4}  {b}')

json.dump({'rows': rows, 'uniq': uniq}, open(OUT, 'w'), ensure_ascii=False)
print('\ngravado em', OUT)
