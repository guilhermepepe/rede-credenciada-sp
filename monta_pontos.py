# -*- coding: utf-8 -*-
"""Gera dados_base.json (meta + especialidades + pontos de Sao Paulo)."""
import json, collections, unicodedata
base=json.load(open('base_nova.json'))
cache=json.load(open('/home/claude/rede/cep_cache.json'))
sweep=json.load(open('/home/claude/rede/cep_sweep.json'))
ESP=sorted({e for x in base for e in x['especialidades']})
IDX={e:i for i,e in enumerate(ESP)}
TIP={'Clínica (PJ)':0,'Dentista (PF)':1,'Profissional vinculado':2}
def titulo(s):
    p=[]
    for w in s.split():
        p.append(w if (len(w)<=3 and w.isupper() and w not in ('SAO','VIL')) else w.capitalize())
    return ' '.join(p)
sp=[x for x in base if x['cidade']=='São Paulo']
pontos=[]; semgeo=0
for x in sp:
    if not x['latitude']: semgeo+=1; continue
    d=x['cep_digits']
    cp=cache.get(d) or sweep.get(d[:5]) or {}
    bairro=(x['cep_bairro'] or cp.get('bairro') or titulo(x['bairro'])).strip()
    pontos.append({'n':x['nome'],'t':TIP[x['tipo']],'b':bairro,'d':'',
        'e':x['endereco'],'c':x['cep'],'ru':x['cep_logradouro'] or cp.get('logradouro',''),
        'la':x['latitude'],'lo':x['longitude'],
        'es':sorted(IDX[e] for e in x['especialidades'] if e in IDX),
        'f':' / '.join([t for t in (x['telefone'],x['celular']) if t]),
        'da':x['data_associacao'],'te':1 if x['selos'] else 0,
        'v':x['vinculado_a'],'h':x['horarios']})
# credenciados no mesmo endereco ficariam exatamente sobrepostos: espalha num
# circulo de ~9 m para que todos sejam clicaveis
import math
g=collections.defaultdict(list)
for p in pontos: g[(p['la'],p['lo'])].append(p)
for (la,lo),v in g.items():
    if len(v)<2: continue
    r=9.0/111320.0
    for i,p in enumerate(v):
        ang=2*math.pi*i/len(v)
        p['la']=round(la+r*math.cos(ang),6)
        p['lo']=round(lo+r*math.sin(ang)/math.cos(math.radians(la)),6)

meta={'fonte':'PDF "Encontre seu Dentista" — 16/10/2026, 163 páginas','total_rede':len(base),
      'cidades':len(set(x['cidade'] for x in base)),'sp':len(sp),'mapa':len(pontos),'semgeo':semgeo,
      'locais':len(set(p['e']+'|'+p['c'] for p in pontos)),'distritos':96,'distritos_com':0,
      'bairros':0,'bairros_com':0,'esp':len(ESP),
      'pj':sum(1 for p in pontos if p['t']==0),'pf':sum(1 for p in pontos if p['t']==1),
      'vi':sum(1 for p in pontos if p['t']==2),'pop':11240389}
json.dump({'meta':meta,'esp':ESP,'pontos':pontos},open('dados_base.json','w'),ensure_ascii=False)
print('SP:',len(sp),'| no mapa:',len(pontos),'| sem coordenada:',semgeo)
print('especialidades:',len(ESP))
print('tipos:',collections.Counter(p['t'] for p in pontos))
print('bairros distintos:',len(set(p['b'] for p in pontos)))
