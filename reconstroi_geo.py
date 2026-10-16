# -*- coding: utf-8 -*-
"""Reconstroi areas.json/dados.json a partir dos CEPs limpos.

Cada distrito e dividido INTEIRO entre os seus bairros (Voronoi dos centroides
de CEP de cada bairro, recortado pelo distrito): sem buracos, sem ilhas, cada
bairro uma peca so. O credenciado e contado no bairro cuja area o contem, entao
o numero do painel e sempre igual aos pontos desenhados. O bairro do CEP fica
guardado em 'bc' e aparece na ficha do credenciado.
"""
import json, math, statistics as st, collections
from shapely.geometry import shape, Point, mapping, MultiPoint
from shapely.ops import voronoi_diagram, unary_union
BASE='/home/claude/rede-credenciada-sp/'
ORIG='/tmp/claude-0/-home-claude-rede-credenciada-sp/0181ac0f-dbc6-5800-b9bf-408f428f8d00/scratchpad/'
sweep=json.load(open('/home/claude/rede/cep_sweep.json'))
ok=set(json.load(open(ORIG+'ok.json'))); rec=json.load(open(ORIG+'rec_prefixos.json'))
areas=json.load(open(ORIG+'areas.bak.json')); dados=json.load(open(BASE+'dados_base.json'))
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
FIX={'03568000':(-23.542300,-46.481222),'03312050':(-23.542550,-46.564700)}
for p in dados['pontos']:
    c=p['c'].replace('-','')
    if c in FIX: p['la'],p['lo']=FIX[c]
    p['bc']=p['b']                       # bairro declarado no CEP
    p['d']=distrito_de(p['la'],p['lo'])

# 1. sementes: cada faixa de CEP do bairro e cada credenciado dele
sem=collections.defaultdict(list); ncep=collections.Counter(); vistos=collections.defaultdict(set)
def add(dd,b,la,lo):
    ch=(round(la,6),round(lo,6))
    if ch in vistos[dd]: return
    vistos[dd].add(ch); sem[dd].append((b,la,lo))
for k,v in sweep.items():
    b=(v.get('bairro') or '').strip()
    if not b or not coord[k]: continue
    la,lo=coord[k]; dd=distrito_de(la,lo); ncep[(dd,b)]+=1; add(dd,b,la,lo)
for p in dados['pontos']: add(p['d'],p['bc'],p['la'],p['lo'])
print('sementes:',sum(len(v) for v in sem.values()))

# 2. Voronoi das sementes, celulas unidas por bairro e recortadas pelo distrito:
#    divide o distrito inteiro, sem buraco, e cada CEP fica no seu proprio bairro
SPMAP={pr['d']:pr['sp'] for pr,_ in DIST}; ZMAP={pr['d']:pr['z'] for pr,_ in DIST}
feats=[]; geo={}
for pr,g in DIST:
    lst=sem.get(pr['d'],[])
    if not lst: continue
    porB=collections.defaultdict(list)
    if len(lst)==1:
        porB[lst[0][0]].append(g)
    else:
        vd=voronoi_diagram(MultiPoint([Point(lo,la) for _,la,lo in lst]), envelope=g.buffer(0.05))
        cells=list(vd.geoms)
        for b,la,lo in lst:
            cel=next((c for c in cells if c.contains(Point(lo,la))),None)
            if cel is None: continue
            inter=g.intersection(cel).buffer(0)
            if not inter.is_empty: porB[b].append(inter)
    bruto={}
    for b,parts in porB.items():
        poly=unary_union([x.buffer(0) for x in parts]).buffer(0)
        if poly.is_empty: continue
        poly=poly.buffer(0.00035,quad_segs=6).buffer(-0.00035,quad_segs=6).buffer(0).intersection(g).buffer(0)
        if not poly.is_empty: bruto[b]=poly
    # cada bairro fica com uma peca so: as partes soltas vao para o bairro
    # vizinho com quem dividem a maior fronteira, para o distrito seguir inteiro
    princ={}; soltas=[]
    for b,poly in bruto.items():
        if poly.geom_type=='MultiPolygon':
            gs=sorted(poly.geoms,key=lambda x:-x.area)
            meus=[Point(p['lo'],p['la']) for p in dados['pontos'] if p['d']==pr['d'] and p['bc']==b]
            fica=[gs[0]]+[x for x in gs[1:] if any(x.buffer(0.00015).covers(q) for q in meus)]
            princ[b]=unary_union(fica).buffer(0)
            soltas+= [x for x in gs[1:] if x not in fica]
        else: princ[b]=poly
    for _ in range(6):
        if not soltas: break
        resto=[]
        for frag in soltas:
            viz=None; melhor=0
            for b,poly in princ.items():
                try: comp=frag.buffer(0.00002).intersection(poly.buffer(0.00002)).length
                except Exception: comp=0
                if comp>melhor: melhor=comp; viz=b
            if viz: princ[viz]=unary_union([princ[viz],frag]).buffer(0)
            else: resto.append(frag)
        soltas=resto
    for b,poly in princ.items():
        poly=poly.intersection(g).buffer(0)
        if poly.is_empty: continue
        simp=poly.simplify(0.00022)
        if not simp.is_empty and simp.geom_type in ('Polygon','MultiPolygon'): poly=simp
        geo[(pr['d'],b)]=poly
        mior=max(poly.geoms,key=lambda x:x.area) if poly.geom_type=='MultiPolygon' else poly
        rp=mior.representative_point()
        gj=mapping(poly)
        feats.append({'type':'Feature','properties':{'b':b,'d':pr['d'],'sp':SPMAP[pr['d']],'z':ZMAP[pr['d']],
            'cep':ncep.get((pr['d'],b),0),'lat':round(rp.y,6),'lng':round(rp.x,6),
            'cred':0,'pj':0,'pf':0,'vi':0,'nesp':0},
            'geometry':{'type':gj['type'],'coordinates':rnd(gj['coordinates'])}})
print('poligonos de bairro:',len(feats))

# 3. o credenciado pertence ao bairro cuja area o contem
porD=collections.defaultdict(list)
for (dd,b),poly in geo.items(): porD[dd].append((b,poly))
mud=0
for p in dados['pontos']:
    q=Point(p['lo'],p['la'])
    achou=None
    for b,poly in porD.get(p['d'],[]):
        if poly.covers(q): achou=b; break
    if achou is None and porD.get(p['d']):
        achou=min(porD[p['d']],key=lambda x:x[1].distance(q))[0]
    if achou and achou!=p['b']: mud+=1
    if achou: p['b']=achou
print('credenciados cujo bairro no mapa difere do bairro do CEP: %d de %d'%(mud,len(dados['pontos'])))

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
