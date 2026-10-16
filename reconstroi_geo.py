# -*- coding: utf-8 -*-
"""Reconstroi areas.json/dados.json a partir dos CEPs limpos.

A area de cada bairro e a envoltoria concava dos CEPs que os Correios
classificam naquele bairro (mais os credenciados dele), com uma folga curta.
Ela e recortada pelo distrito e pela regiao de Voronoi do proprio bairro, para
nao invadir o vizinho. Sao Paulo nao tem limite oficial de bairro: esta e a
delimitacao que o dado de CEP permite, e ela acompanha de perto as ruas que
pertencem ao bairro.
"""
import json, math, statistics as st, collections
import shapely
from shapely.geometry import shape, Point, mapping, MultiPoint, Polygon, MultiPolygon
from shapely.ops import voronoi_diagram, unary_union
BASE='/home/claude/rede-credenciada-sp/'
SCR='/tmp/claude-0/-home-claude/0181ac0f-dbc6-5800-b9bf-408f428f8d00/scratchpad/'
ORIG='/tmp/claude-0/-home-claude-rede-credenciada-sp/0181ac0f-dbc6-5800-b9bf-408f428f8d00/scratchpad/'
sweep=json.load(open('/home/claude/rede/cep_sweep.json'))
ok=set(json.load(open(ORIG+'ok.json'))); rec=json.load(open(ORIG+'rec_prefixos.json'))
areas=json.load(open(ORIG+'areas.bak.json')); dados=json.load(open(ORIG+'dados.bak.json'))
DIST=[(dict(f['properties']),shape(f['geometry'])) for f in areas['distritos']['features']]
GR=1/111.32                      # 1 km em graus de latitude
COS=math.cos(math.radians(-23.55))
FOLGA=0.13*GR                    # 130 m de folga em volta dos CEPs do bairro
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
FIX={'03568000':(-23.542300,-46.481222),'03312050':(-23.542550,-46.564700)}
for p in dados['pontos']:
    c=p['c'].replace('-','')
    if c in FIX: p['la'],p['lo']=FIX[c]
for p in dados['pontos']:
    p['d']=distrito_de(p['la'],p['lo'])     # o bairro p['b'] vem do CEP e nao muda

sem=collections.defaultdict(list); ncep=collections.Counter(); vistos=collections.defaultdict(set)
def add(dd,b,la,lo):
    ch=(round(la,6),round(lo,6))
    if ch in vistos[dd]: return
    vistos[dd].add(ch); sem[dd].append((b,la,lo))
for k,v in sweep.items():
    b=(v.get('bairro') or '').strip()
    if not b or not coord[k]: continue
    la,lo=coord[k]; dd=distrito_de(la,lo); ncep[(dd,b)]+=1; add(dd,b,la,lo)
for p in dados['pontos']: add(p['d'],p['b'],p['la'],p['lo'])
print('sementes:',sum(len(v) for v in sem.values()))

SPMAP={pr['d']:pr['sp'] for pr,_ in DIST}; ZMAP={pr['d']:pr['z'] for pr,_ in DIST}
feats=[]
for pr,g in DIST:
    lst=sem.get(pr['d'],[])
    if not lst: continue
    porB=collections.defaultdict(list)
    for b,la,lo in lst: porB[b].append((la,lo))
    # regiao de Voronoi de cada bairro, para nao invadir o vizinho
    reg={}
    if len(lst)>1:
        vd=voronoi_diagram(MultiPoint([Point(lo,la) for _,la,lo in lst]), envelope=g.buffer(0.05))
        cells=list(vd.geoms)
        acc=collections.defaultdict(list)
        for b,la,lo in lst:
            c=next((x for x in cells if x.contains(Point(lo,la))),None)
            if c is not None: acc[b].append(c)
        reg={b:unary_union([x.buffer(0) for x in v]) for b,v in acc.items()}
    for b,pts in porB.items():
        mp=MultiPoint([Point(lo,la) for la,lo in pts])
        if len(pts)>=4:
            env=shapely.concave_hull(mp,ratio=0.62)
        elif len(pts)>1:
            env=mp.convex_hull
        else:
            env=mp
        area=env.buffer(FOLGA if len(pts)>2 else 0.26*GR, quad_segs=10)
        if b in reg: area=area.intersection(reg[b])
        area=area.intersection(g).buffer(0)
        if area.is_empty: continue
        meus=[Point(p['lo'],p['la']) for p in dados['pontos'] if p['d']==pr['d'] and p['b']==b]
        if area.geom_type=='MultiPolygon':
            tot=area.area
            keep=[x for x in area.geoms if x.area>=tot*0.08 or any(x.buffer(0.00015).covers(q) for q in meus)]
            if keep: area=unary_union(keep).buffer(0)
        area=area.buffer(0.07*GR,quad_segs=8).buffer(-0.07*GR,quad_segs=8).buffer(0)   # tira bicos
        area=area.intersection(g).buffer(0)
        if area.is_empty: continue
        simp=area.simplify(0.00025)
        if not simp.is_empty and simp.geom_type!='GeometryCollection': area=simp
        falta=[q for q in meus if not area.covers(q)]
        if falta: area=unary_union([area]+[q.buffer(0.00013) for q in falta]).buffer(0)
        mior=max(area.geoms,key=lambda x:x.area) if area.geom_type=='MultiPolygon' else area
        rp=mior.representative_point()
        gj=mapping(area)
        feats.append({'type':'Feature','properties':{'b':b,'d':pr['d'],'sp':SPMAP[pr['d']],'z':ZMAP[pr['d']],
            'cep':ncep.get((pr['d'],b),0),'lat':round(rp.y,6),'lng':round(rp.x,6),
            'cred':0,'pj':0,'pf':0,'vi':0,'nesp':0},
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
    pr.update(cred=c['cred'],pj=c['pj'],pf=c['pf'],vi=c['vi'],nesp=len(ed[pr['d']]),
              loc=len(ld[pr['d']]),nbai=nb.get(pr['d'],0))
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
print('meta:',{k:dados['meta'][k] for k in ('mapa','bairros','bairros_com','distritos_com')})
