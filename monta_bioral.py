import json, math
from collections import Counter

SC = '/tmp/claude-0/-home-claude/0181ac0f-dbc6-5800-b9bf-408f428f8d00/scratchpad/'
prep = json.load(open(SC + 'bioral_prep.json'))
geo  = json.load(open(SC + 'bioral_geo.json'))
pontos, esp = prep['pontos'], prep['esp']
assert len(pontos) == len(geo), 'tamanhos diferentes'

# ---- municipio de Sao Paulo, para descartar coordenada fora ----
areas = json.load(open('areas.json'))
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

final, sem, fora = [], 0, 0
for p, g in zip(pontos, geo):
    if not g:
        sem += 1
        continue
    if not dentro(g[0], g[1]):
        fora += 1
        continue
    q = dict(p)
    q['la'], q['lo'] = g[0], g[1]
    if g[2] != 1:
        q['ap'] = 1                      # posicao aproximada
    final.append(q)

# ---- espalha os co-localizados num circulo de 9 m ----
grupos = {}
for p in final:
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

out = {'meta': {'rede': 'Bioral', 'cidade': 'São Paulo',
                'fonte': 'Portal Athena — rede credenciada Bioral, captura de 22/10/2026',
                'n': len(final), 'prof': sum(p['np'] for p in final),
                'geo': 'Geocodificação do Google'},
       'esp': esp, 'tipos': ['Clínica (PJ)', 'Dentista (PF)'], 'pontos': final}
json.dump(out, open('bioral.json', 'w'), ensure_ascii=False, separators=(',', ':'))

import os
print('estabelecimentos  :', len(final))
print('sem coordenada    :', sem)
print('fora do municipio :', fora)
print('profissionais     :', sum(p['np'] for p in final))
print('espalhados        :', espalhados)
print('posicao aproximada:', sum(1 for p in final if p.get('ap')))
print('tamanho bioral.json:', os.path.getsize('bioral.json'), 'bytes')
print()
print('--- bairros com mais estabelecimentos Bioral ---')
for b, c in Counter(p['b'] for p in final if p['b']).most_common(8):
    print(f'  {c:>4}  {b}')
