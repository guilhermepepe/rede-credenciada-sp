# -*- coding: utf-8 -*-
"""Reconstroi areas.json/dados.json a partir dos CEPs limpos.

Os poligonos de bairro sao Voronoi MULTI-SEMENTE: cada CEP do bairro e cada
credenciado nele entram como semente, e as celulas sao unidas por bairro. Assim
a area desenhada acompanha a distribuicao real dos CEPs e todo credenciado cai
dentro do bairro em que esta contado.
"""
import json, math, statistics as st, collections
from shapely.geometry import shape, Point, mapping, MultiPoint, Polygon, MultiPolygon
from shapely.ops import voronoi_diagram, unary_union
BASE='/home/claude/rede-credenciada-sp/'
SCR='/tmp/claude-0/-home-claude-rede-credenciada-sp/0181ac0f-dbc6-5800-b9bf-408f428f8d00/scratchpad/'
sweep=json.load(open('/home/claude/rede/cep_sweep.json'))
ok=set(json.load(open(SCR+'ok.json'))); rec=json.load(open(SCR+'rec_prefixos.json'))
areas=json.load(open(SCR+'areas.bak.json')); dados=json.load(open(SCR+'dados.bak.json'))
DIST=[(dict(f['properties']),shape(f['geometry'])) for f in areas['distritos']['features']]
def distrito_de(la,lo):
    p=Point(lo,la)
    for pr,g in DIST:
        if g.contains(p): return pr['d']
    return min(DIST,key=lambda x:x[1].distance(p))[0]['d']
def rnd(x):
    if isinstance(x,(list,tuple)):
        if x and isinstance(x[0],(int,float)): return [round(x[0],5),round(x[1],5)]
        return [rnd(i) for i in x]
    return x

# --- coordenada de cada prefixo: limpa, ou recuperada pelo proprio setor
coord={k:(float(v['latitude']),float(v['longitude'])) if k in ok else (tuple(rec[k]) if k in rec else None)
       for k,v in sweep.items()}

# --- corrige os CEPs cuja coordenada a API devolveu errada
FIX={'03568000':(-23.542300,-46.481222),'03312050':(-23.542550,-46.564700)}
for p in dados['pontos']:
    c=p['c'].replace('-','')
    if c in FIX: p['la'],p['lo']=FIX[c]
for p in dados['pontos']:
    p['d']=distrito_de(p['la'],p['lo'])     # bairro p['b'] vem do CEP e nao muda

# --- sementes por distrito: (bairro, lat, lng)
sem=collections.defaultdict(list); ncep=collections.Counter(); vistos=collections.defaultdict(set)
def add(dd,b,la,lo):
    ch=(round(la,6),round(lo,6))
    if ch in vistos[dd]: return
    vistos[dd].add(ch); sem[dd].append((b,la,lo))
for k,v in sweep.items():
    b=(v.get('bairro') or '').strip()
    if not b or not coord[k]: continue
    la,lo=coord[k]; dd=distrito_de(la,lo)
    ncep[(dd,b)]+=1; add(dd,b,la,lo)
for p in dados['pontos']:
    add(p['d'],p['b'],p['la'],p['lo'])      # garante que o credenciado fique dentro do seu bairro
print('sementes:',sum(len(v) for v in sem.values()))

SPMAP={pr['d']:pr['sp'] for pr,_ in DIST}; ZMAP={pr['d']:pr['z'] for pr,_ in DIST}
# Sao Paulo nao tem limite oficial de bairro e nenhuma base publica traz esses
# poligonos, entao o bairro NAO e desenhado: fica so o nome, posicionado na
# mediana dos CEPs dele, e as contagens.
porDB=collections.defaultdict(list)
for dd,lst in sem.items():
    for b,la,lo in lst: porDB[(dd,b)].append((la,lo))
feats=[]
for (dd,b),v in sorted(porDB.items()):
    feats.append({'b':b,'d':dd,'sp':SPMAP[dd],'z':ZMAP[dd],'cep':ncep.get((dd,b),0),
        'lat':round(st.median([x[0] for x in v]),6),'lng':round(st.median([x[1] for x in v]),6),
        'cred':0,'pj':0,'pf':0,'vi':0,'nesp':0})
print('bairros (sem geometria):',len(feats))

cb=collections.defaultdict(collections.Counter); eb=collections.defaultdict(set)
cd=collections.defaultdict(collections.Counter); ed=collections.defaultdict(set); ld=collections.defaultdict(set)
for p in dados['pontos']:
    kb=p['d']+'|'+p['b']; t=['pj','pf','vi'][p['t']]
    cb[kb]['cred']+=1; cb[kb][t]+=1; eb[kb].update(p['es'])
    cd[p['d']]['cred']+=1; cd[p['d']][t]+=1; ed[p['d']].update(p['es']); ld[p['d']].add(p['e']+'|'+p['c'])
for f in feats:
    k=f['d']+'|'+f['b']; c=cb[k]
    f.update(cred=c['cred'],pj=c['pj'],pf=c['pf'],vi=c['vi'],nesp=len(eb[k]))
nb=collections.Counter(f['d'] for f in feats)
for pr,_ in DIST:
    c=cd[pr['d']]
    pr.update(cred=c['cred'],pj=c['pj'],pf=c['pf'],vi=c['vi'],nesp=len(ed[pr['d']]),
              loc=len(ld[pr['d']]),nbai=nb.get(pr['d'],0))
areas['distritos']['features']=[{'type':'Feature','properties':pr,
    'geometry':{'type':mapping(g)['type'],'coordinates':rnd(mapping(g)['coordinates'])}} for pr,g in DIST]
areas['bairros']=feats
for f in areas['zonas']['features']:
    ds=[pr for pr,_ in DIST if pr['z']==f['properties']['z']]
    f['properties'].update(cred=sum(x['cred'] for x in ds),loc=sum(x['loc'] for x in ds),
        nbai=sum(x['nbai'] for x in ds),nd=len(ds))
dados['meta'].update(bairros=len(feats),bairros_com=sum(1 for f in feats if f['cred']),
    distritos_com=sum(1 for pr,_ in DIST if pr['cred']))
json.dump(areas,open(BASE+'areas.json','w'),ensure_ascii=False,separators=(',',':'))
json.dump(dados,open(BASE+'dados.json','w'),ensure_ascii=False,separators=(',',':'))
print('meta:',{k:dados['meta'][k] for k in ('mapa','bairros','bairros_com','distritos_com')})
print('cred distritos:',sum(pr['cred'] for pr,_ in DIST))
