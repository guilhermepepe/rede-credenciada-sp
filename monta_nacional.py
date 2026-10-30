import json, math, re, os
from collections import Counter, defaultdict

SC='/tmp/claude-0/-home-claude/0181ac0f-dbc6-5800-b9bf-408f428f8d00/scratchpad/'
regs=json.load(open(SC+'prodental.json'))
keys=[tuple(k) for k in json.load(open(SC+'prodental_keys.json'))]
geo=json.load(open(SC+'prodental_geo.json'))
coord={k:g for k,g in zip(keys,geo)}

def chave(r):
    e=re.sub(r'\s+',' ',(r['endereco'] or r['end'])).strip().upper()
    return (e, r['cep'], r['cidade'].upper(), r['uf'])

# ---------- bairros de Sao Paulo, para o nivel distrito ----------
areas=json.load(open('areas.json'))
BAI=[]
for f in areas['bairros']['features']:
    p=f['properties']; g=f['geometry']
    polys=[g['coordinates']] if g['type']=='Polygon' else g['coordinates']
    aneis=[poly[0] for poly in polys]
    xs=[c[0] for a in aneis for c in a]; ys=[c[1] for a in aneis for c in a]
    BAI.append({'b':p['b'],'d':p['d'],'z':p['z'],'aneis':aneis,
                'bb':(min(xs),min(ys),max(xs),max(ys)),'lat':p['lat'],'lng':p['lng']})

def dentro_anel(lat,lon,anel):
    d=False; n=len(anel)
    for i in range(n):
        x1,y1=anel[i][0],anel[i][1]; x2,y2=anel[(i+1)%n][0],anel[(i+1)%n][1]
        if (y1>lat)!=(y2>lat):
            if lon < (x2-x1)*(lat-y1)/(y2-y1+1e-18)+x1: d=not d
    return d

def acha_bairro(lat,lon):
    for B in BAI:
        x0,y0,x1,y1=B['bb']
        if not (x0<=lon<=x1 and y0<=lat<=y1): continue
        for a in B['aneis']:
            if dentro_anel(lat,lon,a): return B
    # fora de todos: o mais proximo pela ancora
    melhor=None; dm=1e9
    for B in BAI:
        dd=(B['lat']-lat)**2+(B['lng']-lon)**2
        if dd<dm: dm=dd; melhor=B
    return melhor

esp_set=sorted({e for r in regs for e in r['esp']})
esp_ix={e:i for i,e in enumerate(esp_set)}

pontos=[]; sem=0; fora_sp=0
for r in regs:
    g=coord.get(chave(r))
    if not g: sem+=1; continue
    p={'n':r['nome'],'uf':r['uf'],'ci':r['cidade'],'b':r['bairro'],
       'e':r['endereco'] or r['end'],'c':r['cep'],'f':r['cel'] or r['tel'],
       't':r['tipo'],'es':sorted(esp_ix[e] for e in r['esp']),
       'la':g[0],'lo':g[1]}
    if r.get('vinculado_a'): p['v']=r['vinculado_a']
    if g[2]!=1: p['ap']=1
    if r['uf']=='SP' and r['cidade'].strip().lower()=='são paulo':
        B=acha_bairro(g[0],g[1])
        if B: p['d']=B['d']; p['b']=B['b']; p['z']=B['z']
        else: fora_sp+=1
    pontos.append(p)

# ---------- espalha co-localizados ----------
grupos=defaultdict(list)
for p in pontos: grupos[(round(p['la'],6),round(p['lo'],6))].append(p)
esp_n=0
for (la,lo),g in grupos.items():
    if len(g)<2: continue
    raio=9.0/111320.0
    for i,p in enumerate(g):
        a=2*math.pi*i/len(g)
        p['la']=round(la+raio*math.cos(a),6)
        p['lo']=round(lo+raio*math.sin(a)/math.cos(math.radians(la)),6)
        esp_n+=1

UFNOME={'AC':'Acre','AL':'Alagoas','AM':'Amazonas','AP':'Amapá','BA':'Bahia','CE':'Ceará',
 'DF':'Distrito Federal','ES':'Espírito Santo','GO':'Goiás','MA':'Maranhão','MG':'Minas Gerais',
 'MS':'Mato Grosso do Sul','MT':'Mato Grosso','PA':'Pará','PB':'Paraíba','PE':'Pernambuco',
 'PI':'Piauí','PR':'Paraná','RJ':'Rio de Janeiro','RN':'Rio Grande do Norte','RO':'Rondônia',
 'RR':'Roraima','RS':'Rio Grande do Sul','SC':'Santa Catarina','SE':'Sergipe','SP':'São Paulo','TO':'Tocantins'}

out={'meta':{'rede':'Prodental','abrangencia':'Brasil','n':len(pontos),
      'fonte':'PDF "Encontre seu Dentista" — captura de 30/10/2026, 366 páginas',
      'geo':'Geocodificação do Google','ufs':len({p['uf'] for p in pontos}),
      'cidades':len({(p['uf'],p['ci']) for p in pontos}),
      'precisos':sum(1 for p in pontos if not p.get('ap'))},
     'esp':esp_set,'tipos':['Clínica (PJ)','Dentista (PF)','Profissional vinculado'],
     'ufnome':UFNOME,'pontos':pontos}
json.dump(out,open('rede.json','w'),ensure_ascii=False,separators=(',',':'))

sp=[p for p in pontos if p['uf']=='SP' and p['ci'].strip().lower()=='são paulo']
print('pontos            :', len(pontos), '(sem coordenada:', sem, ')')
print('estados           :', out['meta']['ufs'])
print('cidades           :', out['meta']['cidades'])
print('especialidades    :', len(esp_set))
print('espalhados        :', esp_n)
print('posicao aproximada:', sum(1 for p in pontos if p.get('ap')))
print('Sao Paulo capital :', len(sp), '| com distrito:', sum(1 for p in sp if p.get('d')))
print('distritos cobertos:', len({p['d'] for p in sp if p.get('d')}), 'de 96')
print('tamanho rede.json :', os.path.getsize('rede.json'), 'bytes')
print()
print('--- top 8 estados ---')
for u,c in Counter(p['uf'] for p in pontos).most_common(8): print(f'  {u}  {c:>5}')
