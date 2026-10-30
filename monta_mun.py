import json, os, unicodedata, collections, sys
from shapely.geometry import shape, Point, mapping
import topojson as tp

RAIZ='/home/claude/rede-credenciada-sp'
SAIDA=os.path.join(RAIZ,'mun'); os.makedirs(SAIDA,exist_ok=True)
TOL=float(sys.argv[1]) if len(sys.argv)>1 else 0.0008

def nz(s):
    s=unicodedata.normalize('NFD',str(s))
    s=''.join(c for c in s if unicodedata.category(c)!='Mn')
    return ' '.join(s.lower().replace("'"," ").replace('-',' ').split())

d=json.load(open(os.path.join(RAIZ,'rede.json')))
porCid=collections.defaultdict(list)
for p in d['pontos']: porCid[(p['uf'],p['ci'])].append(p)
ufs=sorted({u for u,_ in porCid})

relat=[]; total=0
for uf in ufs:
    feats=json.load(open(uf+'.json'))['features']
    geoms=[(f['properties']['name'], f['properties']['id'], shape(f['geometry'])) for f in feats]
    idx={}
    for nome,cod,g in geoms: idx.setdefault(nz(nome),(nome,cod,g))
    quer=sorted(c for u,c in porCid if u==uf)

    escolhidos=[]
    for ci in quer:
        hit=idx.get(nz(ci))
        via='nome'
        if not hit:                               # resolve pelo ponto do credenciado
            pts=[Point(p['lo'],p['la']) for p in porCid[(uf,ci)]]
            melhor=None
            for nome,cod,g in geoms:
                if any(g.contains(pt) for pt in pts): melhor=(nome,cod,g); break
            if melhor is None:
                relat.append((uf,ci,'SEM POLIGONO','')); continue
            hit=melhor; via='ponto'
            relat.append((uf,ci,'casado por ponto',hit[0]))
        escolhidos.append({'ci':ci,'ibge':hit[1],'ibgeNome':hit[0],'g':hit[2],'n':len(porCid[(uf,ci)])})

    if not escolhidos: continue
    fc={'type':'FeatureCollection','features':[
        {'type':'Feature','properties':{'ci':e['ci'],'ibge':e['ibge'],'n':e['n']},
         'geometry':mapping(e['g'])} for e in escolhidos]}
    # simplificacao topologica: fronteiras compartilhadas continuam coladas
    topo=tp.Topology(fc, prequantize=False, shared_coords=True, toposimplify=TOL)
    out=json.loads(topo.to_geojson())
    for a,b in zip(out['features'],fc['features']): a['properties']=b['properties']
    cam=os.path.join(SAIDA,uf+'.json')
    with open(cam,'w') as fh: json.dump(out,fh,ensure_ascii=False,separators=(',',':'))
    tam=os.path.getsize(cam); total+=tam
    print('%-3s %3d municipios  %7.1f KB'%(uf,len(escolhidos),tam/1024))

print('TOTAL %.1f KB em %d arquivos'%(total/1024,len(os.listdir(SAIDA))))
print('--- divergencias ---')
for r in relat: print('  ',' | '.join(r))
