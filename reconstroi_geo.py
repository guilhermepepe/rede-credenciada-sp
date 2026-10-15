# -*- coding: utf-8 -*-
import json, math, statistics as st, collections
from shapely.geometry import shape, Point, mapping, MultiPoint
from shapely.ops import voronoi_diagram
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

coord={k:(float(v['latitude']),float(v['longitude'])) if k in ok else (tuple(rec[k]) if k in rec else None)
       for k,v in sweep.items()}
pts=collections.defaultdict(list); ncep=collections.Counter()
for k,v in sweep.items():
    b=(v.get('bairro') or '').strip()
    if not b or not coord[k]: continue
    dd=distrito_de(*coord[k]); pts[(dd,b)].append(coord[k]); ncep[(dd,b)]+=1
cent={kk:(st.median([x[0] for x in v]),st.median([x[1] for x in v])) for kk,v in pts.items()}
print('pares distrito/bairro:',len(cent))

FIX={'03568000':(-23.542300,-46.481222),'03312050':(-23.542550,-46.564700)}
for p in dados['pontos']:
    c=p['c'].replace('-','')
    if c in FIX: p['la'],p['lo']=FIX[c]
mud=[]
for p in dados['pontos']:
    nd=distrito_de(p['la'],p['lo'])
    if nd!=p['d']: mud.append((p['n'][:34],p['c'],p['d'],nd))
    p['d']=nd           # o bairro p['b'] vem do CEP e NAO muda
print('\npontos com distrito alterado:',len(mud))
for a,b,c,e in mud: print('   %-34s %s  %s -> %s'%(a,b,c,e))
orf=[(p['d'],p['b']) for p in dados['pontos'] if (p['d'],p['b']) not in cent]
print('pontos cujo par distrito/bairro nao tem poligono:',len(orf), sorted(set(orf))[:6])
for p in dados['pontos']:
    if (p['d'],p['b']) not in cent: cent[(p['d'],p['b'])]=(p['la'],p['lo']); ncep[(p['d'],p['b'])]=ncep.get((p['d'],p['b']),0)

porDist=collections.defaultdict(list)
for (dd,b),(la,lo) in cent.items(): porDist[dd].append((b,la,lo))
SPMAP={pr['d']:pr['sp'] for pr,_ in DIST}; ZMAP={pr['d']:pr['z'] for pr,_ in DIST}
feats=[]
for pr,g in DIST:
    lst=porDist.get(pr['d'],[])
    if not lst: continue
    if len(lst)==1: polys=[g]
    else:
        vd=voronoi_diagram(MultiPoint([Point(lo,la) for _,la,lo in lst]), envelope=g.buffer(0.05))
        cells=list(vd.geoms); polys=[]
        for _,la,lo in lst:
            pt=Point(lo,la); cel=next((c for c in cells if c.contains(pt)),None)
            polys.append(g.intersection(cel) if cel is not None else None)
    for (b,la,lo),poly in zip(lst,polys):
        if poly is None or poly.is_empty: continue
        poly=poly.buffer(0).simplify(0.00025)
        if poly.is_empty: continue
        gj=mapping(poly)
        feats.append({'type':'Feature','properties':{'b':b,'d':pr['d'],'sp':SPMAP[pr['d']],'z':ZMAP[pr['d']],
            'cep':ncep.get((pr['d'],b),0),'lat':round(la,6),'lng':round(lo,6),'cred':0,'pj':0,'pf':0,'vi':0,'nesp':0},
            'geometry':{'type':gj['type'],'coordinates':rnd(gj['coordinates'])}})
print('poligonos de bairro:',len(feats))

cb=collections.defaultdict(collections.Counter); eb=collections.defaultdict(set)
cd=collections.defaultdict(collections.Counter); ed=collections.defaultdict(set); ld=collections.defaultdict(set)
for p in dados['pontos']:
    kb=p['d']+'|'+p['b']; t=['pj','pf','vi'][p['t']]
    cb[kb]['cred']+=1; cb[kb][t]+=1; eb[kb].update(p['es'])
    cd[p['d']]['cred']+=1; cd[p['d']][t]+=1; ed[p['d']].update(p['es']); ld[p['d']].add(p['e']+'|'+p['c'])
for f in feats:
    k=f['properties']['d']+'|'+f['properties']['b']; c=cb[k]
    f['properties'].update(cred=c['cred'],pj=c['pj'],pf=c['pf'],vi=c['vi'],nesp=len(eb[k]))
nb=collections.Counter(f['properties']['d'] for f in feats)
for pr,_ in DIST:
    c=cd[pr['d']]
    pr.update(cred=c['cred'],pj=c['pj'],pf=c['pf'],vi=c['vi'],nesp=len(ed[pr['d']]),loc=len(ld[pr['d']]),nbai=nb.get(pr['d'],0))
areas['distritos']['features']=[{'type':'Feature','properties':pr,
    'geometry':{'type':mapping(g)['type'],'coordinates':rnd(mapping(g)['coordinates'])}} for pr,g in DIST]
areas['bairros']={'type':'FeatureCollection','features':feats}
for f in areas['zonas']['features']:
    ds=[pr for pr,_ in DIST if pr['z']==f['properties']['z']]
    f['properties'].update(cred=sum(x['cred'] for x in ds),loc=sum(x['loc'] for x in ds),
        nbai=sum(x['nbai'] for x in ds),nd=len(ds))
dados['meta'].update(bairros=len(feats),bairros_com=sum(1 for f in feats if f['properties']['cred']),
    distritos_com=sum(1 for pr,_ in DIST if pr['cred']))
json.dump(areas,open(BASE+'areas.json','w'),ensure_ascii=False,separators=(',',':'))
json.dump(dados,open(BASE+'dados.json','w'),ensure_ascii=False,separators=(',',':'))
print('\nmeta:',{k:dados['meta'][k] for k in ('mapa','bairros','bairros_com','distritos_com')})
print('cred distritos:',sum(pr['cred'] for pr,_ in DIST),'| zonas:',sum(f['properties']['cred'] for f in areas['zonas']['features']))
