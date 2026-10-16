# -*- coding: utf-8 -*-
"""Monta a base completa + os pontos de Sao Paulo a partir do PDF extraido.

A coordenada NAO vem do campo lat/long da API de CEP (que tem erro em ~6% dos
CEPs): vem da base ja auditada quando o CEP ja existia, senao do proprio setor
de CEP, que e dado confiavel.
"""
import json, math, statistics as st, collections, re
NOVO='novo.json'
VELHO='/home/claude/rede/rede_credenciada.json'
CACHE='/home/claude/rede/cep_cache.json'
SWEEP='/home/claude/rede/cep_sweep.json'
OK='/tmp/claude-0/-home-claude-rede-credenciada-sp/0181ac0f-dbc6-5800-b9bf-408f428f8d00/scratchpad/ok.json'

novo=json.load(open(NOVO)); velho=json.load(open(VELHO))
cache=json.load(open(CACHE)); sweep=json.load(open(SWEEP)); limpos=set(json.load(open(OK)))

def km(a,b,c,d): return math.hypot((a-c)*111.32,(b-d)*111.32*math.cos(math.radians((a+c)/2)))
# 1. coordenada conhecida por CEP, vinda da base ja corrigida
porCep={}
for x in velho:
    if x['cep'] and x.get('latitude'): porCep.setdefault(x['cep'],[]).append((x['latitude'],x['longitude']))
porCep={c:(st.median([p[0] for p in v]),st.median([p[1] for p in v])) for c,v in porCep.items()}
# 2. setores de CEP limpos
pref5={k:(float(sweep[k]['latitude']),float(sweep[k]['longitude'])) for k in limpos}
def med(nd):
    g=collections.defaultdict(list)
    for k,v in pref5.items(): g[k[:nd]].append(v)
    return {p:(st.median([x[0] for x in v]),st.median([x[1] for x in v]),len(v)) for p,v in g.items()}
m4,m3=med(4),med(3)
# 3. centro de cada cidade, pela base antiga
porCidade=collections.defaultdict(list)
for x in velho:
    if x.get('latitude'): porCidade[x['cidade']].append((x['latitude'],x['longitude']))
cidadeMed={}
for c,v in porCidade.items():
    if len(v)<2: continue
    m=(st.median([p[0] for p in v]),st.median([p[1] for p in v]))
    bons=[p for p in v if km(p[0],p[1],m[0],m[1])<=(40 if c=='São Paulo' else 15)]
    if len(bons)>=2: cidadeMed[c]=(st.median([p[0] for p in bons]),st.median([p[1] for p in bons]))

def resolve(r):
    c=r['cep']; d=c.replace('-','')
    if c and c in porCep: return porCep[c],'CEP ja auditado'
    if d[:5] in pref5: return pref5[d[:5]],'faixa de CEP'
    if d[:4] in m4 and m4[d[:4]][2]>=3: return m4[d[:4]][:2],'setor de CEP (4 dig.)'
    if d[:3] in m3 and m3[d[:3]][2]>=4: return m3[d[:3]][:2],'setor de CEP (3 dig.)'
    if r['cidade'] in cidadeMed: return cidadeMed[r['cidade']],'centro da cidade'
    return None,'sem coordenada'

TIPOS={0:'Clínica (PJ)',1:'Dentista (PF)',2:'Profissional vinculado'}
base=[]; fontes=collections.Counter()
for i,r in enumerate(novo,1):
    co,fonte=resolve(r); fontes[fonte]+=1
    d=r['cep'].replace('-','')
    cp=cache.get(d) or sweep.get(d[:5]) or {}
    tel=' / '.join([t for t in (r['tel'].strip(),r['cel'].strip()) if t])
    base.append({'id':i,'cidade':r['cidade'],'bairro':r['bairro'],'tipo':TIPOS[r['tipo']],
        'nome':r['nome'],'cro':r['cro'],'cnpj':r['cnpj'],'vinculado_a':r['vinculado_a'],
        'data_associacao':r['data'],'especialidades':r['esp'],'qtd_especialidades':len(r['esp']),
        'endereco':r['endereco'],'cep':r['cep'],'cep_digits':d,
        'endereco_completo':(r['endereco']+' , '+r['cep']).strip(),
        'telefone':r['tel'],'celular':r['cel'],'horarios':r['atend'],
        'selos':['Título de Especialista'] if r['selo'] else [],
        'latitude':round(co[0],6) if co else None,'longitude':round(co[1],6) if co else None,
        'geo_fonte':fonte,
        'cep_logradouro':cp.get('logradouro',''),'cep_bairro':cp.get('bairro',''),
        'distrito':'','subprefeitura':''})
json.dump(base,open('base_nova.json','w'),ensure_ascii=False)
print('registros:',len(base))
print('origem da coordenada:',dict(fontes))
print('sem coordenada:',sum(1 for x in base if not x['latitude']))
