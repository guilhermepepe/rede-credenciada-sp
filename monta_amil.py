import json, math, sys
from collections import Counter

SC = '/tmp/claude-0/-home-claude/0181ac0f-dbc6-5800-b9bf-408f428f8d00/scratchpad/'
prep = json.load(open(SC + 'amil_prep.json'))
keys = json.load(open(SC + 'amil_keys.json'))
geo  = json.load(open(SC + 'amil_geo.json'))          # [[lat,lon]|null, ...] na ordem de keys

assert len(keys) == len(geo), 'keys e geo com tamanhos diferentes'
coord = {k: g for k, g in zip(keys, geo) if g}

# ---- poligono do municipio, para descartar coordenada fora de SP ----
areas = json.load(open('areas.json'))
def anel_de(feat):
    g = feat['geometry']
    return (g['coordinates'] if g['type'] == 'Polygon'
            else [p[0] for p in g['coordinates']])
aneis = []
for f in areas['cidade']['features']:
    g = f['geometry']
    polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
    for poly in polys:
        aneis.append(poly[0])

def dentro(lat, lon):
    for anel in aneis:
        d, n = False, len(anel)
        for i in range(n):
            x1, y1 = anel[i][0], anel[i][1]
            x2, y2 = anel[(i + 1) % n][0], anel[(i + 1) % n][1]
            if (y1 > lat) != (y2 > lat):
                if lon < (x2 - x1) * (lat - y1) / (y2 - y1 + 1e-18) + x1:
                    d = not d
        if d:
            return True
    return False

# ---- especialidades ----
esp_set = sorted({e for r in prep['rows'] for e in r['es']})
esp_ix  = {e: i for i, e in enumerate(esp_set)}

pontos, sem_coord, fora = [], 0, 0
vistos = {}
for r in prep['rows']:
    g = coord.get(r['k'])
    if not g:
        sem_coord += 1
        continue
    la, lo = g[0], g[1]
    fino = (len(g) > 2 and g[2] == 1)
    if not dentro(la, lo):
        fora += 1
        continue
    chave = (r['n'].upper(), r['end_raw'].upper())
    if chave in vistos:                     # mesma clinica repetida: funde especialidades
        p = vistos[chave]
        for e in r['es']:
            if esp_ix[e] not in p['es']:
                p['es'].append(esp_ix[e])
        continue
    p = {'n': r['n'], 'e': r['end_raw'], 'b': r['ba'], 'f': r['f'],
         'la': la, 'lo': lo, 'es': sorted({esp_ix[e] for e in r['es']})}
    if not fino: p['ap'] = 1
    vistos[chave] = p
    pontos.append(p)

# ---- espalha os co-localizados num circulo de 9 m para todos ficarem clicaveis ----
grupos = {}
for p in pontos:
    grupos.setdefault((round(p['la'], 6), round(p['lo'], 6)), []).append(p)
espalhados = 0
for (la, lo), g in grupos.items():
    if len(g) < 2:
        continue
    raio = 9.0 / 111320.0
    for i, p in enumerate(g):
        a = 2 * math.pi * i / len(g)
        p['la'] = round(la + raio * math.cos(a), 6)
        p['lo'] = round(lo + raio * math.sin(a) / math.cos(math.radians(la)), 6)
        espalhados += 1

for p in pontos:
    p['es'] = sorted(p['es'])

out = {'meta': {'rede': 'Amil Dental', 'cidade': 'São Paulo', 'fonte': 'Lista de credenciados Amil Dental — cidade de São Paulo',
                'n': len(pontos), 'geo': 'Nominatim/OpenStreetMap'},
       'esp': esp_set, 'pontos': pontos}
json.dump(out, open('amil.json', 'w'), ensure_ascii=False, separators=(',', ':'))

print('linhas no csv        :', len(prep['rows']))
print('enderecos geocodados :', len(coord), '/', len(keys))
print('sem coordenada       :', sem_coord)
print('fora do municipio    :', fora)
print('duplicados fundidos  :', len(prep['rows']) - sem_coord - fora - len(pontos))
print('pontos em amil.json  :', len(pontos))
print('espalhados (mesmo end):', espalhados)
print('especialidades       :', len(esp_set))
import os; print('tamanho amil.json    :', os.path.getsize('amil.json'), 'bytes')
print()
print('--- bairros com mais credenciados Amil ---')
for b, c in Counter(p['b'] for p in pontos if p['b']).most_common(8):
    print(f'  {c:>4}  {b}')
