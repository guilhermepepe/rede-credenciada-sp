# -*- coding: utf-8 -*-
"""Audita as coordenadas da base: todo ponto deve estar dentro do municipio
de Sao Paulo e perto do seu proprio setor de CEP. Sai com codigo 1 se achar erro."""
import json, math, statistics as st, sys, os
from shapely.geometry import shape, Point
BASE=os.path.dirname(os.path.abspath(__file__))+'/'
SWEEP='/home/claude/rede/cep_sweep.json'
a=json.load(open(BASE+'areas.json')); d=json.load(open(BASE+'dados.json'))
cid=shape(a['cidade']['features'][0]['geometry'])
def km(x1,y1,x2,y2): return math.hypot((x1-x2)*111.32,(y1-y2)*111.32*math.cos(math.radians((x1+x2)/2)))
erros=[]
for p in d['pontos']:
    if not cid.contains(Point(p['lo'],p['la'])):
        erros.append(('fora do municipio',p['c'],p['e'],p['d']))
if os.path.exists(SWEEP):
    s=json.load(open(SWEEP))
    E=[(k,float(v['latitude']),float(v['longitude'])) for k,v in s.items() if v.get('latitude')]
    def med(e,nd):
        g={}
        for k,la,lo in e: g.setdefault(k[:nd],[]).append((la,lo))
        return {q:(st.median([x[0] for x in v]),st.median([x[1] for x in v]),len(v)) for q,v in g.items()}
    lim=E
    for _ in range(3):
        m3=med(lim,3); lim=[x for x in lim if km(x[1],x[2],m3[x[0][:3]][0],m3[x[0][:3]][1])<=6]
    m4=med(lim,4)
    for p in d['pontos']:
        q=p['c'].replace('-','')[:4]
        if q in m4 and m4[q][2]>=3:
            dd=km(p['la'],p['lo'],m4[q][0],m4[q][1])
            if dd>8: erros.append(('%.1f km do setor de CEP'%dd,p['c'],p['e'],p['d']))
for e in erros: print('ERRO:',' | '.join(e))
print('%d pontos auditados, %d problemas'%(len(d['pontos']),len(erros)))
sys.exit(1 if erros else 0)
